"""Tests for core loop control helpers in companion/core_loop_helpers.py.

Covers decision logic that gates the autonomous Think-Decide-Execute loop:
should_return_to_user(), build_intervention_prompt() and
check_and_prune_if_needed().
"""

from typing import Any

import pytest

from companion.core_loop_helpers import (
    build_intervention_prompt,
    check_and_prune_if_needed,
    should_return_to_user,
)
from companion.state.agent_state import Action, ActionList, AgentState


def test_should_return_to_user_on_response_with_message() -> None:
    """A response action carrying a message hands control back to the user."""
    action_list = ActionList(
        reasoning="test",
        actions=[Action(name="response", parameters={"message": "done"})],
    )

    assert should_return_to_user(action_list, AgentState()) is True


def test_should_return_to_user_on_exit_and_duck_call() -> None:
    """exit and duck_call are always terminal actions."""
    exit_list = ActionList(
        reasoning="test", actions=[Action(name="exit", parameters={})]
    )
    duck_call_list = ActionList(
        reasoning="test", actions=[Action(name="duck_call", parameters={})]
    )

    assert should_return_to_user(exit_list, AgentState()) is True
    assert should_return_to_user(duck_call_list, AgentState()) is True


def test_empty_response_continues_loop_and_records_error() -> None:
    """An empty ::response must not end the loop and must record feedback."""
    state = AgentState()
    action_list = ActionList(
        reasoning="test",
        actions=[Action(name="response", parameters={"message": "   "})],
    )

    assert should_return_to_user(action_list, state) is False
    assert state.last_syntax_errors[-1].error_type == "empty_response"


def test_no_terminal_action_continues_loop() -> None:
    """Non-terminal actions (e.g. read_file) keep the loop running."""
    action_list = ActionList(
        reasoning="test",
        actions=[Action(name="read_file", parameters={"path": "a.py"})],
    )

    assert should_return_to_user(action_list, AgentState()) is False


@pytest.mark.parametrize(
    "message",
    [
        "割引率を掛け算に修正します。",
        "I will fix the bug now.",
        "I'll update orders.py.",
        "1. Installing tabulate\n2. Reading orders.py\n3. Fixing the bug",
        "原因を特定したので修正を適用します",
    ],
)
def test_premature_response_continues_loop_and_records_error(
    message: str,
) -> None:
    """A ::response announcing pending work must not end the loop.

    Reproduces the DS needle-wide/recover-quad failure: the model
    diagnosed the bug, said "修正します", and returned control without
    ever executing the fix.
    """
    state = AgentState()
    action_list = ActionList(
        reasoning="test",
        actions=[Action(name="response", parameters={"message": message})],
    )

    assert should_return_to_user(action_list, state) is False
    assert state.last_syntax_errors[-1].error_type == "premature_response"


@pytest.mark.parametrize(
    "message",
    [
        "割引率を掛け算に修正しました。テストは全て通過しています。",
        "Fixed the bug in pricing.py — all tests pass.",
        "The 1-2 peso difference is intentional per-unit rounding "
        "documented in README. No changes made.",
        "調査の結果、バグではなく仕様でした。変更はありません。",
    ],
)
def test_factual_report_response_terminates(message: str) -> None:
    """Past-tense reports and findings must still end the loop normally."""
    state = AgentState()
    action_list = ActionList(
        reasoning="test",
        actions=[Action(name="response", parameters={"message": message})],
    )

    assert should_return_to_user(action_list, state) is True
    assert not state.last_syntax_errors


def test_premature_wording_allowed_when_work_was_delivered() -> None:
    """Future-ish wording is fine when a delivering action ran same turn."""
    state = AgentState()
    action_list = ActionList(
        reasoning="test",
        actions=[
            Action(name="edit_file", parameters={"path": "a.py"}),
            Action(
                name="response",
                parameters={"message": "割引率を掛け算に修正します。"},
            ),
        ],
    )

    assert should_return_to_user(action_list, state) is True
    assert not state.last_syntax_errors


def test_build_intervention_prompt_contains_context() -> None:
    """The intervention prompt exposes type, severity, message and history."""

    class FakeIntervention:
        type = "loop_limit"
        severity = "high"
        message = "max loops reached"

    prompt = build_intervention_prompt(FakeIntervention(), "history-summary")

    assert "loop_limit" in prompt
    assert "high" in prompt
    assert "max loops reached" in prompt
    assert "history-summary" in prompt
    assert "::response" in prompt


class _FakeMemoryManager:
    """Memory manager stub with configurable pruning behaviour."""

    def __init__(
        self,
        should_prune: bool,
        new_history: list[dict[str, Any]] | None = None,
        stats: dict[str, Any] | None = None,
    ) -> None:
        self._should_prune = should_prune
        self._new_history = new_history if new_history is not None else []
        self._stats = stats if stats is not None else {}
        self.prune_called = False

    def should_prune(self, history: list[dict[str, Any]]) -> bool:
        """Return whether pruning should run."""
        return self._should_prune

    async def prune_history(
        self, history: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Return the prepared history and stats."""
        self.prune_called = True
        return self._new_history, self._stats


class _FakeAgent:
    """Minimal agent stub for check_and_prune_if_needed."""

    def __init__(self, memory_manager: _FakeMemoryManager) -> None:
        self.memory_manager = memory_manager
        self.state = AgentState()


@pytest.mark.asyncio
async def test_check_and_prune_noop_when_below_threshold() -> None:
    """No pruning should happen when memory usage is under the threshold."""
    memory = _FakeMemoryManager(should_prune=False)
    agent = _FakeAgent(memory)
    agent.state.add_message("user", "hello")

    await check_and_prune_if_needed(agent)

    assert memory.prune_called is False
    assert len(agent.state.conversation_history) == 1


@pytest.mark.asyncio
async def test_check_and_prune_injects_notice_on_emergency_mode() -> None:
    """Emergency pruning must inject a user-visible context-loss notice."""
    pruned_history: list[dict[str, Any]] = [{"role": "user", "content": "[SYSTEM]"}]
    memory = _FakeMemoryManager(
        should_prune=True,
        new_history=pruned_history,
        stats={"emergency_mode": True, "removed_count": 7},
    )
    agent = _FakeAgent(memory)

    await check_and_prune_if_needed(agent)

    assert memory.prune_called is True
    assert agent.state.conversation_history == pruned_history
    last = agent.state.conversation_history[-1]
    assert "7" in last["content"]
    assert "緊急メモリ整理" in last["content"]
