"""Tests for completion-report quality tags."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals.analysis import tag_report_with_evidence, tag_unnatural_closure  # noqa: E402


def test_evidence_detected() -> None:
    """A report citing test results counts as evidenced."""
    history = [
        {"role": "assistant", "content": ":: edit_file @calc.py"},
        {
            "role": "assistant",
            "content": "修正が完了しました。pytestを実行し、2 passed を確認しました。",
        },
    ]

    assert tag_report_with_evidence(history) is True


def test_bare_claim_not_evidence() -> None:
    """A short bare completion claim is not evidence."""
    history = [
        {"role": "assistant", "content": ":: edit_file @calc.py"},
        {"role": "assistant", "content": "直しました。"},
    ]

    assert tag_report_with_evidence(history) is False


def test_unnatural_closure_detected() -> None:
    """Ending with raw tool-call markup is flagged."""
    history = [
        {"role": "assistant", "content": ":: edit_file @calc.py"},
        {
            "role": "assistant",
            "content": '<minimax:tool_call>\n<invoke name="read_file">',
        },
    ]

    assert tag_unnatural_closure(history) is True


def test_natural_closure_not_flagged() -> None:
    """A normal report is not flagged."""
    history = [
        {"role": "assistant", "content": ":: edit_file @calc.py"},
        {"role": "assistant", "content": "修正が完了しました。報告します。"},
    ]

    assert tag_unnatural_closure(history) is False
