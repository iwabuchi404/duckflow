"""Tests for plan detection, false-success tagging and verify command."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals.analysis import looks_like_plan, tag_false_success  # noqa: E402
from evals.runner import _run_verify_command  # noqa: E402


def test_looks_like_plan_true_for_numbered_plan() -> None:
    """A numbered list with plan keywords is detected as a plan."""
    text = (
        "修正の方針は以下の計画です。\n"
        "1. テストを実行して失敗を確認\n"
        "2. calc.py の原因を調査\n"
        "3. 修正を適用して再実行\n"
    )

    assert looks_like_plan(text) is True


def test_looks_like_plan_false_for_short_response() -> None:
    """Short plain responses are not plans."""
    assert looks_like_plan("修正しました。") is False


def test_looks_like_plan_false_for_list_without_keywords() -> None:
    """A bare list without plan keywords is not treated as a plan."""
    text = "calc.py\n- test_calc.py\n- README\n- setup.cfg\n"

    assert looks_like_plan(text) is False


def test_false_success_detected_on_failed_run() -> None:
    """A failed run whose last message claims success is tagged."""
    transcript = {
        "result": {"passed": False},
        "conversation_history": [
            {"role": "assistant", "content": ":: edit_file @calc.py"},
            {"role": "assistant", "content": "## 結論\ncalc.py のバグを修正し、全テストがパスするようになりました。"},
        ],
    }

    assert tag_false_success(transcript) is True


def test_false_success_not_tagged_on_passed_run() -> None:
    """Passed runs are never tagged false_success."""
    transcript = {
        "result": {"passed": True},
        "conversation_history": [
            {"role": "assistant", "content": "修正が完了しました。"},
        ],
    }

    assert tag_false_success(transcript) is False


def test_false_success_not_tagged_for_honest_failure() -> None:
    """A failed run admitting failure is not tagged."""
    transcript = {
        "result": {"passed": False},
        "conversation_history": [
            {"role": "assistant", "content": "申し訳ありません、修正できませんでした。"},
        ],
    }

    assert tag_false_success(transcript) is False


def test_verify_command_passes_on_success(tmp_path) -> None:
    """A zero-exit verify command passes."""
    result = _run_verify_command("exit 0", tmp_path)

    assert result["passed"] is True


def test_verify_command_fails_on_nonzero_exit(tmp_path) -> None:
    """A non-zero-exit verify command fails with captured output."""
    result = _run_verify_command('python -c "import sys; print(\'bad\'); sys.exit(1)"', tmp_path)

    assert result["passed"] is False
    assert "bad" in result["detail"]
