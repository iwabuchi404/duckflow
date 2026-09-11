"""Tests for script_after_question response-question handling."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from companion.state.agent_state import AgentPhase, AgentState  # noqa: E402
from evals.runner import _make_input_provider  # noqa: E402


class _FakeAgent:
    """Minimal agent stub exposing state."""

    def __init__(self, state: AgentState) -> None:
        self.state = state


def _run(coro):
    """Drive an async callable synchronously."""
    return asyncio.get_event_loop().run_until_complete(coro())


def test_script_served_after_response_question() -> None:
    """A '?' in the latest response triggers the scripted answer."""
    state = AgentState()
    state.add_message("assistant", "対象商品はどれですか？")
    agent_ref = {"agent": _FakeAgent(state)}

    provider = _make_input_provider(
        "task", None, ["appleとbananaで"], agent_ref, True
    )

    assert _run(provider) == "task"
    assert _run(provider) == "appleとbananaで"
    assert _run(provider) == "exit"


def test_script_withheld_without_question() -> None:
    """No question means no scripted answer."""
    state = AgentState()
    state.add_message("assistant", ":: write_file @report.json")
    agent_ref = {"agent": _FakeAgent(state)}

    provider = _make_input_provider(
        "task", None, ["appleとbananaで"], agent_ref, True
    )

    assert _run(provider) == "task"
    assert _run(provider) == "exit"
