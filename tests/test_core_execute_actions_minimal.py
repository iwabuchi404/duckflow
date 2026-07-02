import pytest

from companion.core import DuckAgent
from companion.state.agent_state import Action, ActionList
from companion.tools.results import ToolResult, is_tool_result_message


class DummyLLM:
    """Minimal LLM stub for DuckAgent tests."""

    usage_stats = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "estimated_cost": 0.0,
    }


def _agent() -> DuckAgent:
    """Create a DuckAgent with an inert LLM client."""
    return DuckAgent(llm_client=DummyLLM())


@pytest.mark.asyncio
async def test_execute_actions_filters_unknown_tools_before_execution() -> None:
    """
    Unknown tools should be filtered before dispatch and recorded as syntax
    feedback for the next LLM turn.
    """
    agent = _agent()
    action_list = ActionList(
        reasoning="try a hallucinated tool",
        actions=[Action(name="does_not_exist", parameters={})],
    )

    results = await agent.execute_actions(action_list)

    assert results == []
    assert action_list.actions == []
    assert agent.state.last_syntax_errors
    assert agent.state.last_syntax_errors[-1].error_type == "unknown_tool"


@pytest.mark.asyncio
async def test_execute_actions_blocks_edits_in_investigation_mode() -> None:
    """
    Investigation mode is read-only; edit actions must not reach the tool
    implementation.
    """
    agent = _agent()
    agent.state.enter_investigation_mode()

    action_list = ActionList(
        reasoning="attempt unsafe edit while investigating",
        actions=[
            Action(
                name="write_file",
                parameters={"path": "blocked.txt", "content": "nope"},
            )
        ],
    )

    results = await agent.execute_actions(action_list)

    assert len(results) == 1
    assert "[BLOCKED]" in results[0]
    assert agent.state.last_syntax_errors[-1].error_type == "investigation_edit_blocked"
    tool_msg = agent.state.conversation_history[-2]
    assert tool_msg["role"] == "user"
    assert is_tool_result_message(tool_msg["content"])
    assert "Investigation Mode" in tool_msg["content"]


@pytest.mark.asyncio
async def test_execute_actions_fail_fast_aborts_after_two_consecutive_errors() -> None:
    """
    Two consecutive tool errors should abort remaining actions in the same turn.
    """
    agent = _agent()
    calls = []

    def fail_one() -> str:
        """Failing test tool."""
        calls.append("fail_one")
        raise RuntimeError("first failure")

    def fail_two() -> str:
        """Failing test tool."""
        calls.append("fail_two")
        raise RuntimeError("second failure")

    def should_not_run() -> str:
        """Tool that must be skipped by fail-fast."""
        calls.append("should_not_run")
        return "unexpected"

    agent.register_tool("fail_one", fail_one)
    agent.register_tool("fail_two", fail_two)
    agent.register_tool("should_not_run", should_not_run)

    action_list = ActionList(
        reasoning="trigger fail-fast",
        actions=[
            Action(name="fail_one", parameters={}),
            Action(name="fail_two", parameters={}),
            Action(name="should_not_run", parameters={}),
        ],
    )

    results = await agent.execute_actions(action_list)

    assert calls == ["fail_one", "fail_two"]
    assert len(results) == 2
    assert all("failed" in item for item in results)
    assert any(
        "連続2回のエラー" in msg["content"] for msg in agent.state.conversation_history
    )


@pytest.mark.asyncio
async def test_execute_actions_limits_actions_per_turn() -> None:
    """Only the first six valid actions should run in one execution turn."""
    agent = _agent()
    calls = []

    def ping(index: int) -> str:
        """Record that a test action was executed."""
        calls.append(index)
        return f"pong-{index}"

    agent.register_tool("ping", ping)
    action_list = ActionList(
        reasoning="too many actions",
        actions=[
            Action(name="ping", parameters={"index": index}) for index in range(8)
        ],
    )

    results = await agent.execute_actions(action_list)

    assert calls == [0, 1, 2, 3, 4, 5]
    assert results == ["pong-0", "pong-1", "pong-2", "pong-3", "pong-4", "pong-5"]
    assert len(action_list.actions) == 6


@pytest.mark.asyncio
async def test_execute_actions_low_safety_no_longer_blocks_execution(
    monkeypatch,
) -> None:
    """Safety Score Interceptor is removed; low safety should not cancel actions."""
    agent = _agent()
    calls = []

    def ping() -> str:
        """Tool that should execute regardless of declared safety score."""
        calls.append("ping")
        return "pong"

    agent.register_tool("ping", ping)
    action_list = ActionList(
        reasoning="unsafe action",
        vitals={"safety": 0.2},
        actions=[Action(name="ping", parameters={})],
    )

    results = await agent.execute_actions(action_list)

    assert results == ["pong"]
    assert calls == ["ping"]
    # No safety cancel message should be in conversation history
    assert not any(
        "Safety Score が低いため" in msg["content"]
        for msg in agent.state.conversation_history
    )


@pytest.mark.asyncio
async def test_execute_actions_moves_terminal_actions_to_the_end() -> None:
    """Terminal user-facing actions should run after operational actions."""
    agent = _agent()
    calls = []

    def ping() -> str:
        """Operational action used to verify execution order."""
        calls.append("ping")
        return "pong"

    agent.register_tool("ping", ping)
    action_list = ActionList(
        reasoning="respond after work",
        actions=[
            Action(name="response", parameters={"message": "done"}),
            Action(name="ping", parameters={}),
        ],
    )

    results = await agent.execute_actions(action_list)

    assert calls == ["ping"]
    assert results == ["pong", "Responded to user."]
    assert [action.name for action in action_list.actions] == ["ping", "response"]


@pytest.mark.asyncio
async def test_execute_actions_wraps_tool_error_with_error_status() -> None:
    """
    When a tool returns a pre-formatted Sym-Ops error string, the executor must
    wrap it in a [TOOL_RESULT] envelope with ::status error, not ::status ok.
    """
    agent = _agent()

    def failing_tool() -> ToolResult:
        return ToolResult.error("failing_tool", "task", "Something went wrong")

    agent.register_tool("failing_tool", failing_tool)
    action_list = ActionList(
        reasoning="tool will fail",
        actions=[Action(name="failing_tool", parameters={})],
    )

    results = await agent.execute_actions(action_list)

    assert len(results) == 1
    assert "Something went wrong" in results[0]
    assert "failed" in results[0]

    tool_msg = agent.state.conversation_history[-2]
    assert tool_msg["role"] == "user"
    assert is_tool_result_message(tool_msg["content"])
    assert "::status error" in tool_msg["content"]
    assert "::failing_tool" in tool_msg["content"]
    assert "Something went wrong" in tool_msg["content"]
    assert "::status ok" not in tool_msg["content"]


@pytest.mark.asyncio
async def test_execute_actions_reports_missing_required_parameter() -> None:
    """
    Missing required parameters must produce explicit feedback to the LLM
    instead of silently skipping the action.
    """
    agent = _agent()

    def ping(index: int) -> str:
        return f"pong-{index}"

    agent.register_tool("ping", ping)
    action_list = ActionList(
        reasoning="missing required param",
        actions=[Action(name="ping", parameters={})],
    )

    results = await agent.execute_actions(action_list)

    assert len(results) == 1
    assert "Required parameter 'index' is missing" in results[0]
    assert "failed" in results[0]

    tool_msg = agent.state.conversation_history[-2]
    assert tool_msg["role"] == "user"
    assert is_tool_result_message(tool_msg["content"])
    assert "::status error" in tool_msg["content"]
    assert "::ping" in tool_msg["content"]


@pytest.mark.asyncio
async def test_execute_actions_reports_dropped_unexpected_params() -> None:
    """
    Extra parameters the model passes but the tool does not accept must be
    fed back as syntax feedback, not silently discarded — otherwise the
    model repeats the same invalid parameter every turn.
    """
    agent = _agent()

    def ping(index: int) -> str:
        return f"pong-{index}"

    agent.register_tool("ping", ping)
    action_list = ActionList(
        reasoning="pass an unsupported extra param",
        actions=[Action(name="ping", parameters={"index": 1, "bogus": "x"})],
    )

    results = await agent.execute_actions(action_list)

    assert results == ["pong-1"]
    assert agent.state.last_syntax_errors
    error = agent.state.last_syntax_errors[-1]
    assert error.error_type == "unexpected_params"
    assert "bogus" in error.correction_hint
