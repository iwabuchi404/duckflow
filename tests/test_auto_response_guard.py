"""Tests for the auto-generated response guard.

Repair fallbacks (bare <<<>>> blocks, thought-only output) create response
actions the model never explicitly chose. They must neither terminate the
autonomous loop nor be shown to the user.
"""

import pytest

from companion.core import DuckAgent
from companion.core_loop_helpers import should_return_to_user
from companion.state.agent_state import Action, ActionList, AgentState
from companion.utils.sym_ops import SymOpsProcessor


def test_auto_generated_response_does_not_end_loop() -> None:
    """An auto-generated response continues the loop with guidance."""
    state = AgentState()
    action_list = ActionList(
        reasoning="test",
        actions=[
            Action(
                name="response",
                parameters={"message": "quoted content"},
                auto_generated=True,
            )
        ],
    )

    assert should_return_to_user(action_list, state) is False
    assert state.last_syntax_errors[-1].error_type == "auto_response"


def test_explicit_response_still_ends_loop() -> None:
    """A model-explicit response terminates the loop as before."""
    state = AgentState()
    action_list = ActionList(
        reasoning="test",
        actions=[Action(name="response", parameters={"message": "done"})],
    )

    assert should_return_to_user(action_list, state) is True


def test_bare_block_marks_response_auto_generated() -> None:
    """A <<<>>> block without an action parses to an auto response."""
    result = SymOpsProcessor().process("<<<\ncalc.py\ntest_calc.py\n>>>\n")

    assert len(result.actions) == 1
    assert result.actions[0].type == "response"
    assert result.actions[0].auto_generated is True


def test_explicit_action_not_marked_auto_generated() -> None:
    """Normally parsed actions are not marked auto-generated."""
    result = SymOpsProcessor().process("::read_file @calc.py\n")

    assert result.actions[0].auto_generated is False


class _StubLLM:
    """Minimal LLM stub for DuckAgent tests."""

    usage_stats = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "estimated_cost": 0.0,
    }


@pytest.mark.asyncio
async def test_execute_actions_skips_auto_generated_response() -> None:
    """Auto-generated responses are skipped, later actions still run."""
    agent = DuckAgent(llm_client=_StubLLM())
    calls: list[str] = []

    def ping() -> str:
        """Record execution."""
        calls.append("ping")
        return "pong"

    agent.register_tool("ping", ping)
    action_list = ActionList(
        reasoning="test",
        actions=[
            Action(
                name="response",
                parameters={"message": "should not be shown"},
                auto_generated=True,
            ),
            Action(name="ping", parameters={}),
        ],
    )

    results = await agent.execute_actions(action_list)

    assert calls == ["ping"]
    assert any("SKIPPED" in r for r in results)
    shown = [
        m for m in agent.state.conversation_history
        if m.get("role") == "assistant" and "should not be shown" in m.get("content", "")
    ]
    assert shown == []
