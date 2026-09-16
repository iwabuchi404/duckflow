"""Tests for three-stage collaboration aggregation (施策2).

合格を「必要な確認を変更前に行った」「回答に沿う成果物を作った」
「自然な完了報告で終えた」の3段階で分けて集計する。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals.analysis import (  # noqa: E402
    classify_end_state,
    load_question_expectations,
    stage_summary,
)
from evals.runner import SCENARIO_DIR as RUNNER_SCENARIO_DIR  # noqa: E402


def _transcript(
    history: list[dict[str, str]], passed: bool = True
) -> dict:
    """Build a minimal transcript dict."""
    return {
        "conversation_history": history,
        "result": {"scenario_id": "ambiguous-period", "passed": passed},
    }


def test_full_collaboration_marks_all_stages() -> None:
    """質問→成果物→自然な報告の完遂は3段階ともTrue。"""
    stages = stage_summary(
        _transcript(
            [
                {"role": "assistant", "content": ":: duck_call @task"},
                {"role": "assistant", "content": ":: write_file @report.json"},
                {
                    "role": "assistant",
                    "content": "report.json を作成しました。apple 300 を確認済みです。",
                },
            ]
        ),
        expects_question=True,
    )
    assert stages == {
        "confirmed": True,
        "artifact_ok": True,
        "natural_completion": True,
    }


def test_missing_question_fails_stage1_only() -> None:
    """質問なしの成果物成功は段階1だけがFalse。"""
    stages = stage_summary(
        _transcript(
            [
                {"role": "assistant", "content": ":: write_file @report.json"},
                {
                    "role": "assistant",
                    "content": "report.json を作成しました。apple 300 を確認済みです。",
                },
            ]
        ),
        expects_question=True,
    )
    assert stages["confirmed"] is False
    assert stages["artifact_ok"] is True
    assert stages["natural_completion"] is True


def test_control_scenario_rewards_silence() -> None:
    """情報完備の対照では質問しないことが段階1の正解。"""
    stages = stage_summary(
        _transcript(
            [
                {"role": "assistant", "content": ":: write_file @report.json"},
                {"role": "assistant", "content": "report.json を作成しました。"},
            ]
        ),
        expects_question=False,
    )
    assert stages["confirmed"] is True


def test_control_scenario_flags_over_asking() -> None:
    """情報完備なのに質問すると段階1がFalse。"""
    stages = stage_summary(
        _transcript(
            [
                {"role": "assistant", "content": ":: duck_call @task"},
                {"role": "assistant", "content": ":: write_file @report.json"},
                {"role": "assistant", "content": "report.json を作成しました。"},
            ]
        ),
        expects_question=False,
    )
    assert stages["confirmed"] is False


def test_tool_syntax_closure_fails_stage3() -> None:
    """独自XMLを表示して終わると段階3だけがFalse。"""
    stages = stage_summary(
        _transcript(
            [
                {"role": "assistant", "content": ":: duck_call @task"},
                {"role": "assistant", "content": ":: write_file @report.json"},
                {
                    "role": "assistant",
                    "content": '<minimax:tool_call>\n<invoke name="read_file">',
                },
            ]
        ),
        expects_question=True,
    )
    assert stages["confirmed"] is True
    assert stages["artifact_ok"] is True
    assert stages["natural_completion"] is False


def test_unknown_expectation_leaves_stage1_none() -> None:
    """期待未宣言の課題では段階1を判定しない。"""
    stages = stage_summary(
        _transcript([{"role": "assistant", "content": ":: response @done"}]),
        expects_question=None,
    )
    assert stages["confirmed"] is None


def test_empty_history_is_not_completion() -> None:
    """履歴なしは完了扱いしない。"""
    assert classify_end_state({"conversation_history": [], "result": {}}) == "empty"
    stages = stage_summary(
        {"conversation_history": [], "result": {}}, expects_question=True
    )
    assert stages["natural_completion"] is None


def test_duck_call_ending_is_awaiting_not_reported() -> None:
    """相談で終わった試行は待機扱いで、完了率は付かない。"""
    transcript = _transcript(
        [
            {"role": "assistant", "content": ":: edit_file @a.py"},
            {"role": "assistant", "content": ":: duck_call @task"},
        ],
        passed=False,
    )
    assert classify_end_state(transcript) == "awaiting_user"
    stages = stage_summary(transcript, expects_question=True)
    assert stages["confirmed"] is False
    assert stages["natural_completion"] is None


def test_trailing_question_counts_as_awaiting() -> None:
    """response経由の質問で終わった場合も待機扱い。"""
    transcript = _transcript(
        [
            {"role": "assistant", "content": ":: read_file @sales.csv"},
            {"role": "assistant", "content": "出力先はどちらにしますか？"},
        ]
    )
    assert classify_end_state(transcript) == "awaiting_user"


def test_timeout_end_state() -> None:
    """ハーネスのタイムアウトは専用の終了状態。"""
    transcript = _transcript(
        [{"role": "assistant", "content": ":: read_file @a.py"}]
    )
    transcript["result"]["status"] = "timeout"
    assert classify_end_state(transcript) == "timeout"


def test_action_only_ending_is_unknown() -> None:
    """報告なしの動作だけの終了は不明扱い。"""
    transcript = _transcript(
        [
            {"role": "assistant", "content": ":: read_file @sales.csv"},
            {"role": "assistant", "content": ":: response"},
        ]
    )
    assert classify_end_state(transcript) == "unknown"
    stages = stage_summary(transcript, expects_question=True)
    assert stages["natural_completion"] is None


def test_reported_clean_run_completes_naturally() -> None:
    """実質的な報告で終われば自然な完了。"""
    transcript = _transcript(
        [
            {"role": "assistant", "content": ":: write_file @report.json"},
            {"role": "assistant", "content": "report.json を作成しました。"},
        ]
    )
    assert classify_end_state(transcript) == "reported"
    stages = stage_summary(transcript, expects_question=False)
    assert stages["natural_completion"] is True


def test_expectations_cover_collaboration_scenarios() -> None:
    """協業6種＋変種＋対照にexpects_questionが宣言されている。"""
    expectations = load_question_expectations(RUNNER_SCENARIO_DIR)
    for sid in (
        "ambiguous-explicit",
        "ambiguous-spontaneous",
        "ambiguous-period",
        "ambiguous-period-feb",
        "ambiguous-output",
        "ambiguous-output-alt",
        "ambiguous-unit",
        "ambiguous-unit-count",
    ):
        assert expectations.get(sid) is True, f"{sid} should expect a question"
    assert expectations.get("complete-no-question") is False
