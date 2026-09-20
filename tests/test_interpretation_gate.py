"""Tests for the Interpretation Gate prompt circuit (DUCKFLOW_INTERPRETATION_GATE)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from companion.prompts.builder import (  # noqa: E402
    PromptBuilder,
    interpretation_gate_enabled,
)
from companion.prompts.templates import INTERPRETATION_GATE_PROMPT  # noqa: E402
from companion.state.agent_state import AgentState  # noqa: E402


def test_gate_disabled_by_default(monkeypatch) -> None:
    """Without the env var the gate is off and nothing is injected."""
    monkeypatch.delenv("DUCKFLOW_INTERPRETATION_GATE", raising=False)

    assert interpretation_gate_enabled() is False
    state = AgentState(working_directory=".", user_id="u1")
    messages = PromptBuilder(state).build_messages("tools")
    assert not any(m["content"] == INTERPRETATION_GATE_PROMPT for m in messages)


def test_gate_enabled_injects_block(monkeypatch) -> None:
    """With the env var the gate block appears exactly once, before the
    dynamic context."""
    monkeypatch.setenv("DUCKFLOW_INTERPRETATION_GATE", "1")

    assert interpretation_gate_enabled() is True
    state = AgentState(working_directory=".", user_id="u1")
    messages = PromptBuilder(state).build_messages("tools")
    gate_msgs = [m for m in messages if m["content"] == INTERPRETATION_GATE_PROMPT]
    assert len(gate_msgs) == 1
    idx = messages.index(gate_msgs[0])
    # Must sit after the static protocol/mode blocks and before the
    # dynamic context (the last system message holds Current State).
    assert idx >= 2
    dynamic_idx = next(
        i for i, m in enumerate(messages) if "Current State" in m["content"]
    )
    assert idx < dynamic_idx


def test_gate_enabled_native(monkeypatch) -> None:
    """Native protocol also receives the gate (it is protocol-agnostic)."""
    monkeypatch.setenv("DUCKFLOW_INTERPRETATION_GATE", "1")

    state = AgentState(working_directory=".", user_id="u1")
    messages = PromptBuilder(state).build_messages("", protocol="native")
    assert any(m["content"] == INTERPRETATION_GATE_PROMPT for m in messages)
