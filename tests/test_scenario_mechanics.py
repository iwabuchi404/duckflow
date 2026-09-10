"""Tests for new scenario mechanics: unmodified check, asked_question tag."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals.analysis import tag_asked_question  # noqa: E402
from evals.runner import _run_checks  # noqa: E402


def test_unmodified_passes_for_identical_file(tmp_path: Path) -> None:
    """Byte-identical workspace/fixture files pass."""
    fixture = tmp_path / "fix"
    workspace = tmp_path / "ws"
    fixture.mkdir()
    workspace.mkdir()
    (fixture / "a.py").write_text("x = 1\n", encoding="utf-8")
    (workspace / "a.py").write_text("x = 1\n", encoding="utf-8")

    results = _run_checks(
        [{"type": "unmodified", "path": "a.py"}], workspace, fixture=fixture
    )

    assert results[0]["passed"] is True


def test_unmodified_fails_for_edited_file(tmp_path: Path) -> None:
    """Edited workspace files fail the unmodified check."""
    fixture = tmp_path / "fix"
    workspace = tmp_path / "ws"
    fixture.mkdir()
    workspace.mkdir()
    (fixture / "a.py").write_text("x = 1\n", encoding="utf-8")
    (workspace / "a.py").write_text("x = 2\n", encoding="utf-8")

    results = _run_checks(
        [{"type": "unmodified", "path": "a.py"}], workspace, fixture=fixture
    )

    assert results[0]["passed"] is False


def test_asked_question_via_duck_call() -> None:
    """duck_call before editing counts as asking."""
    history = [
        {"role": "assistant", "content": ":: read_file @sales.csv"},
        {"role": "assistant", "content": ":: duck_call @task"},
    ]

    assert tag_asked_question(history) is True


def test_asked_question_via_question_mark() -> None:
    """A question sentence before editing counts as asking."""
    history = [
        {
            "role": "assistant",
            "content": "出力形式はJSONでよろしいですか？",
        },
        {"role": "assistant", "content": ":: write_file @report.json"},
    ]

    assert tag_asked_question(history) is True


def test_no_question_when_editing_directly() -> None:
    """Editing without any question is not tagged."""
    history = [
        {"role": "assistant", "content": ":: read_file @sales.csv"},
        {"role": "assistant", "content": ":: write_file @report.json"},
    ]

    assert tag_asked_question(history) is False
