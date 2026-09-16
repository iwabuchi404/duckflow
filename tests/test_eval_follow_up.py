"""Tests for content-aware follow-up input selection (evals/runner.py)."""

import asyncio
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from companion.state.agent_state import AgentState, Plan  # noqa: E402
from evals.runner import _make_input_provider  # noqa: E402


class _FakeAgent:
    """Minimal agent stub exposing state."""

    def __init__(self, state: AgentState) -> None:
        self.state = state


def _run(coro):
    """Drive an async callable synchronously."""
    return asyncio.get_event_loop().run_until_complete(coro())


def test_task_then_exit_without_plan() -> None:
    """Without a plan in state, the second input is already exit.

    Regression test: a fixed [task, "exit"] queue exits before any
    follow-up logic runs, so follow-ups must be decided per request.
    """
    provider = _make_input_provider("do thing", ["go ahead"], None, {"agent": _FakeAgent(AgentState())})

    assert _run(provider) == "do thing"
    assert _run(provider) == "exit"
    assert _run(provider) == "exit"


def test_follow_up_served_when_stepped_plan_exists() -> None:
    """A stepped plan in state triggers the follow-up input."""
    state = AgentState()
    plan = Plan(goal="fix the bug")
    plan.add_step(title="investigate", description="find the cause")
    state.current_plan = plan

    provider = _make_input_provider("do thing", ["go ahead"], None, {"agent": _FakeAgent(state)})

    assert _run(provider) == "do thing"
    # Queue exhausted; stepped plan exists -> follow-up, not exit.
    assert _run(provider) == "go ahead"
    assert _run(provider) == "exit"


def test_follow_up_served_for_plan_like_response() -> None:
    """A plan-like final response triggers the follow-up input."""
    state = AgentState()
    state.add_message(
        "assistant",
        "calc.py 修正の計画は次の通りです。\n1. テストを実行して失敗を確認する\n2. 原因を調査して特定する\n3. 修正を適用して再実行する",
    )

    provider = _make_input_provider("do thing", ["go ahead"], None, {"agent": _FakeAgent(state)})

    assert _run(provider) == "do thing"
    assert _run(provider) == "go ahead"


def test_follow_ups_not_shared_across_runs() -> None:
    """Each provider gets its own follow-up copy.

    Regression: pop() previously drained the scenario dict's shared list,
    so --runs N served follow-ups only on the first run.
    """
    shared = ["go ahead"]

    def _provider() -> Any:
        state = AgentState()
        plan = Plan(goal="g")
        plan.add_step(title="s", description="d")
        state.current_plan = plan
        return _make_input_provider(
            "task", shared, None, {"agent": _FakeAgent(state)}
        )

    first = _provider()
    assert _run(first) == "task"
    assert _run(first) == "go ahead"
    assert shared == ["go ahead"]  # scenario list untouched

    second = _provider()
    assert _run(second) == "task"
    assert _run(second) == "go ahead"
