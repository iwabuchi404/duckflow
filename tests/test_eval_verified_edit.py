"""Tests for the verified_edit positive tag (evals/analysis.py)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals.analysis import tag_verified_edit  # noqa: E402


def _history(*assistant_contents: str) -> list[dict]:
    """Build a conversation history from assistant action summaries."""
    return [{"role": "assistant", "content": c} for c in assistant_contents]


def test_verified_edit_true_when_tested_after_edit() -> None:
    """An edit followed by a test run is verified."""
    history = _history(
        ":: edit_file @calc.py",
        ":: run_command @pytest test_calc.py -v",
    )

    assert tag_verified_edit(history) is True


def test_verified_edit_true_when_reread_after_edit() -> None:
    """An edit followed by re-reading the file is verified."""
    history = _history(
        ":: edit_file @calc.py",
        ":: read_file @calc.py",
    )

    assert tag_verified_edit(history) is True


def test_verified_edit_false_when_response_follows_edit() -> None:
    """An edit with no verification afterwards is not verified."""
    history = _history(
        ":: edit_file @calc.py",
        ":: response",
    )

    assert tag_verified_edit(history) is False


def test_verified_edit_false_without_any_edit() -> None:
    """Runs without edits are not tagged."""
    history = _history(":: read_file @calc.py")

    assert tag_verified_edit(history) is False


def test_verified_edit_uses_last_edit() -> None:
    """Only verification after the LAST edit counts."""
    history = _history(
        ":: edit_file @a.py",
        ":: run_command @pytest",
        ":: edit_file @b.py",
    )

    assert tag_verified_edit(history) is False
