"""Tests for the Decision Engine (H-1 experiment).

Covers the Pacemaker firing point, Context Compiler output, binary
decision parsing, provider fallback, and the core-loop gate behavior
(ASK injects a clarification note; CONTINUE leaves history untouched).
"""

import pytest

from companion.decision import (
    DECISION_NEEDS_CLARIFICATION,
    DecisionEngine,
    decision_engine_enabled,
)
from companion.decision.compiler import ContextCompiler
from companion.decision.engine import build_clarification_note
from companion.decision.models import (
    ACTION_ASK_USER,
    ACTION_CONTINUE,
    DecisionRequest,
    DecisionResult,
)
from companion.decision.provider import (
    SameModelDecisionProvider,
    parse_binary_decision,
    render_decision_messages,
)
from companion.modules.pacemaker import DuckPacemaker
from companion.state.agent_state import AgentState

# ---------------------------------------------------------------------------
# Pacemaker firing point
# ---------------------------------------------------------------------------


def test_pacemaker_fires_needs_clarification_at_task_start() -> None:
    """Task receipt is the only v1 firing point."""
    pacemaker = DuckPacemaker(AgentState())
    assert pacemaker.pending_decisions_for_task_start() == [
        DECISION_NEEDS_CLARIFICATION
    ]


# ---------------------------------------------------------------------------
# Context Compiler
# ---------------------------------------------------------------------------


def test_compiler_builds_minimal_context() -> None:
    """Compiler extracts the task and mode, not the whole prompt."""
    state = AgentState()
    context = ContextCompiler().build(state, task="rename the function")
    assert context.user_request == "rename the function"
    assert context.mode == state.current_mode.value
    assert context.recent_actions == []


def test_compiler_extracts_recent_actions() -> None:
    """Recent action names are pulled from assistant history lines."""
    state = AgentState()
    state.conversation_history.append(
        {"role": "assistant", "content": "::read_file @a.py\n::note x"}
    )
    state.conversation_history.append({"role": "user", "content": "task"})
    context = ContextCompiler().build(state, task="task")
    assert context.recent_actions == ["read_file", "note"]


def test_render_messages_contains_task_and_request_type() -> None:
    """Rendered messages carry the judge prompt and the task text."""
    state = AgentState()
    context = ContextCompiler().build(state, task="delete the old tests")
    request = DecisionRequest(type=DECISION_NEEDS_CLARIFICATION, task="t")
    messages = render_decision_messages(context, request)
    assert messages[0]["role"] == "system"
    assert "DECISION:" in messages[0]["content"]
    assert "delete the old tests" in messages[1]["content"]
    assert DECISION_NEEDS_CLARIFICATION in messages[1]["content"]


# ---------------------------------------------------------------------------
# Binary decision parsing
# ---------------------------------------------------------------------------


def test_parse_ask_with_focus() -> None:
    """ASK verdict extracts the focus line."""
    result = parse_binary_decision("DECISION: ASK\nFOCUS: which file to modify")
    assert result.action == ACTION_ASK_USER
    assert result.focus == "which file to modify"


def test_parse_continue() -> None:
    """CONTINUE verdict maps to continue."""
    result = parse_binary_decision("DECISION: CONTINUE")
    assert result.action == ACTION_CONTINUE
    assert result.focus == ""


def test_parse_garbage_falls_back_to_continue() -> None:
    """Unparseable output never blocks the agent."""
    for raw in ("", "I think you should ask", "DECISION:", "none"):
        result = parse_binary_decision(raw)
        assert result.action == ACTION_CONTINUE


def test_parse_case_insensitive() -> None:
    """Verdict tokens are matched case-insensitively."""
    assert parse_binary_decision("decision: ask").action == ACTION_ASK_USER


# ---------------------------------------------------------------------------
# SameModel provider + engine
# ---------------------------------------------------------------------------


class _StubLLM:
    """LLM stub returning a canned raw decision string."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list = []

    async def chat(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return self.response


class _FailingLLM:
    """LLM stub whose chat always raises."""

    async def chat(self, messages, **kwargs):
        raise RuntimeError("provider down")


@pytest.mark.asyncio
async def test_same_model_provider_ask() -> None:
    """Provider parses ASK output from the same-model call."""
    llm = _StubLLM("DECISION: ASK\nFOCUS: ambiguous target")
    provider = SameModelDecisionProvider(llm)
    result = await provider.decide(
        ContextCompiler().build(AgentState(), "task"),
        DecisionRequest(type=DECISION_NEEDS_CLARIFICATION),
    )
    assert result.action == ACTION_ASK_USER
    assert result.focus == "ambiguous target"
    # raw=True must be used so the call bypasses Sym-Ops parsing.
    assert llm.calls[0][1]["raw"] is True


@pytest.mark.asyncio
async def test_engine_logs_decision_and_returns_result() -> None:
    """Engine.check records the verdict in its log."""
    engine = DecisionEngine(_StubLLM("DECISION: CONTINUE"))
    result = await engine.check(
        DECISION_NEEDS_CLARIFICATION, task="add a test", state=AgentState()
    )
    assert result.action == ACTION_CONTINUE
    assert len(engine.log) == 1
    assert engine.log[0]["type"] == DECISION_NEEDS_CLARIFICATION
    assert engine.log[0]["action"] == ACTION_CONTINUE


@pytest.mark.asyncio
async def test_engine_provider_failure_falls_back_to_continue() -> None:
    """A provider error must never block the agent's normal flow."""
    engine = DecisionEngine(_FailingLLM())
    result = await engine.check(
        DECISION_NEEDS_CLARIFICATION, task="t", state=AgentState()
    )
    assert result.action == ACTION_CONTINUE
    assert "error" in engine.log[0]


# ---------------------------------------------------------------------------
# Core-loop gate
# ---------------------------------------------------------------------------


class _GateLLM:
    """LLM stub for DuckAgent gate tests."""

    usage_stats = {}

    def __init__(self, response: str = "DECISION: CONTINUE") -> None:
        self.response = response
        self.calls: list = []

    async def chat(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return self.response


def _make_agent(monkeypatch, enabled: bool, response: str = "DECISION: CONTINUE"):
    """Build a DuckAgent with the env flag toggled."""
    from companion.core import DuckAgent

    monkeypatch.setenv("DUCKFLOW_DECISION_ENGINE", "1" if enabled else "")
    return DuckAgent(llm_client=_GateLLM(response))


@pytest.mark.asyncio
async def test_gate_skipped_when_flag_off(monkeypatch) -> None:
    """No decision call is made when the experiment flag is off."""
    agent = _make_agent(monkeypatch, enabled=False)
    await agent._run_decision_gate("some task")
    assert agent._decision_engine is None
    assert agent.decision_log == []


@pytest.mark.asyncio
async def test_gate_continue_leaves_history_unchanged(monkeypatch) -> None:
    """CONTINUE injects nothing into the conversation."""
    agent = _make_agent(monkeypatch, enabled=True)
    before = len(agent.state.conversation_history)
    await agent._run_decision_gate("a clear task")
    assert len(agent.state.conversation_history) == before
    assert agent.decision_log[0]["action"] == ACTION_CONTINUE


@pytest.mark.asyncio
async def test_gate_ask_injects_clarification_note(monkeypatch) -> None:
    """ASK injects a system note instructing the agent to ask."""
    agent = _make_agent(
        monkeypatch, enabled=True, response="DECISION: ASK\nFOCUS: which target"
    )
    await agent._run_decision_gate("ambiguous task")
    notes = [
        m
        for m in agent.state.conversation_history
        if m.get("role") == "system" and "[DECISION ENGINE]" in m.get("content", "")
    ]
    assert len(notes) == 1
    assert "which target" in notes[0]["content"]
    assert "duck_call" in notes[0]["content"]
    assert agent.decision_log[0]["action"] == ACTION_ASK_USER


@pytest.mark.asyncio
async def test_gate_provider_error_does_not_raise(monkeypatch) -> None:
    """Provider failure inside the gate is swallowed into continue."""
    agent = _make_agent(monkeypatch, enabled=True)
    agent._decision_engine = DecisionEngine(_FailingLLM())
    await agent._run_decision_gate("task")
    assert agent.decision_log[0]["action"] == ACTION_CONTINUE
    assert "error" in agent.decision_log[0]


def test_decision_engine_enabled_flag(monkeypatch) -> None:
    """Env flag parsing matches the existing experiment-switch pattern."""
    monkeypatch.delenv("DUCKFLOW_DECISION_ENGINE", raising=False)
    assert decision_engine_enabled() is False
    monkeypatch.setenv("DUCKFLOW_DECISION_ENGINE", "1")
    assert decision_engine_enabled() is True
    monkeypatch.setenv("DUCKFLOW_DECISION_ENGINE", "true")
    assert decision_engine_enabled() is True


def test_clarification_note_includes_focus_and_reason() -> None:
    """The injected note carries the unresolved focus for the agent."""
    result = DecisionResult(
        action=ACTION_ASK_USER, focus="target file", reason="two candidates"
    )
    note = build_clarification_note(result)
    assert "target file" in note
    assert "two candidates" in note
    assert "ask the user" in note
