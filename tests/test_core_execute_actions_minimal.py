import pytest

from companion.core import DuckAgent
from companion.state.agent_state import Action, ActionList
from companion.tools.results import is_tool_result_message


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
    assert any("連続2回のエラー" in msg["content"] for msg in agent.state.conversation_history)
