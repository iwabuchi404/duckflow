"""Tests for eval transcript heuristic tagging (evals/analysis.py)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals.analysis import (  # noqa: E402
    tag_duck_call,
    tag_empty_response,
    tag_investigation_reentry,
    tag_no_edit_applied,
    tag_output_echo,
    tag_repeated_command,
    tag_transcript,
)


def _history(*assistant_contents: str) -> list[dict]:
    """Build a conversation history from assistant action summaries."""
    return [{"role": "assistant", "content": c} for c in assistant_contents]


def test_output_echo_detected_from_pasted_banner() -> None:
    """A run_command target containing pytest banner text is an echo."""
    history = _history(
        ":: run_command @============================= test session starts ========="
    )

    assert tag_output_echo(history) is True


def test_output_echo_not_triggered_by_normal_command() -> None:
    """Short, clean command targets are not echoes."""
    history = _history(":: run_command @pytest test_calc.py -v")

    assert tag_output_echo(history) is False


def test_investigation_reentry_detected() -> None:
    """investigate after finish_investigation must be flagged."""
    history = _history(
        ":: investigate @task",
        ":: submit_hypothesis @task",
        ":: finish_investigation @task",
        ":: investigate @task",
    )

    assert tag_investigation_reentry(history) is True


def test_investigation_single_pass_not_flagged() -> None:
    """A single investigate/finish cycle is normal."""
    history = _history(
        ":: investigate @task",
        ":: finish_investigation @task",
        ":: edit_file @calc.py",
    )

    assert tag_investigation_reentry(history) is False


def test_repeated_command_detected() -> None:
    """The same command run twice is flagged."""
    history = _history(
        ":: run_command @pytest calc.py -v",
        ":: run_command @pytest calc.py -v",
    )

    assert tag_repeated_command(history) is True


def test_empty_response_detected_from_tool_result() -> None:
    """empty_response markers inside tool results are flagged."""
    history = [
        {"role": "user", "content": "[TOOL_RESULT]\nempty_response: ::response (empty)"}
    ]

    assert tag_empty_response(history) is True


def test_duck_call_detected() -> None:
    """duck_call in the sequence is flagged."""
    assert tag_duck_call(_history(":: duck_call @task")) is True


def test_no_edit_applied_when_only_reads() -> None:
    """Read-only runs are flagged as having applied no edit."""
    history = _history(":: read_file @calc.py", ":: list_files @.")

    assert tag_no_edit_applied(history) is True


def test_tag_transcript_combines_tags_and_stats() -> None:
    """tag_transcript returns scenario stats plus active tags."""
    transcript = {
        "result": {"scenario_id": "s1", "passed": False, "loops_used": 10},
        "conversation_history": _history(
            ":: investigate @task",
            ":: finish_investigation @task",
            ":: investigate @task",
        ),
    }

    tagged = tag_transcript(transcript)

    assert tagged["scenario_id"] == "s1"
    assert tagged["passed"] is False
    assert tagged["loops"] == 10
    assert "investigation_reentry" in tagged["tags"]
