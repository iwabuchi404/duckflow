"""Tests for few-shot framing switch and example-contamination tag."""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from companion.prompts.few_shot import get_examples_for_mode  # noqa: E402
from evals.analysis import tag_example_contamination  # noqa: E402


def test_bare_is_default_and_unchanged() -> None:
    """Default framing keeps bare user/assistant messages."""
    examples = get_examples_for_mode("task")

    assert examples[0]["role"] == "user"
    assert any(m["role"] == "assistant" for m in examples)
    assert get_examples_for_mode("task", framing="bare") == examples


def test_framed_packs_into_single_system_message() -> None:
    """Framed mode returns one system message marked as reference."""
    examples = get_examples_for_mode("task", framing="framed")

    assert len(examples) == 1
    assert examples[0]["role"] == "system"
    assert "参考例" in examples[0]["content"]
    assert "実際に起きた会話ではありません" in examples[0]["content"]


def test_minimal_returns_base_only() -> None:
    """Minimal mode returns only the base greeting exchange."""
    examples = get_examples_for_mode("task", framing="minimal")

    assert len(examples) <= 2
    assert all(
        "weather" not in str(m.get("content", "")).lower() for m in examples
    )


def test_contamination_detected_for_weather_narration() -> None:
    """Reasoning that treats the weather example as real is flagged."""
    transcript = {
        "raw_responses": [
            ">> The user wants me to build a weather app. Let me propose a plan."
        ]
    }

    assert tag_example_contamination(transcript) is True


def test_contamination_detected_for_greeting_narration() -> None:
    """Reasoning that treats the Hello example as real is flagged."""
    transcript = {
        "raw_responses": ["The user greeted me with 'Hello' earlier."]
    }

    assert tag_example_contamination(transcript) is True


def test_no_contamination_for_clean_reasoning() -> None:
    """Ordinary reasoning without example quotes is not flagged."""
    transcript = {"raw_responses": [">> I will read calc.py to find the bug."]}

    assert tag_example_contamination(transcript) is False


@pytest.mark.asyncio
async def test_builder_respects_framing_env(monkeypatch) -> None:
    """Builder passes the env framing switch to example selection."""
    from companion.prompts.builder import PromptBuilder
    from companion.state.agent_state import AgentState

    monkeypatch.setenv("DUCKFLOW_FEW_SHOT_FRAMING", "framed")
    builder = PromptBuilder(AgentState())
    messages = builder.build_messages("read_file: test tool")

    systems = [m for m in messages if m.get("role") == "system"]
    assert any("参考例" in m.get("content", "") for m in systems)

    monkeypatch.delenv("DUCKFLOW_FEW_SHOT_FRAMING")
    builder = PromptBuilder(AgentState())
    messages = builder.build_messages("read_file: test tool")
    assert not any(
        "参考例" in m.get("content", "")
        for m in messages
        if m.get("role") == "system"
    )
    assert any(
        m.get("role") == "user" and m.get("content") == "Hello" for m in messages
    )
