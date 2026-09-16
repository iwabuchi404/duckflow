"""Tests for narrowed evaluation specs (ambiguous/no-change/new scenarios).

施策1: 出力構造の自由度を依頼に明記し、採点の階層特例を廃止。
施策3: 自発的確認の別種シナリオと対照課題の存在を保証。
"""

import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals.runner import (  # noqa: E402
    SCENARIO_DIR,
    _run_verify_command,
    load_scenarios,
)


def _load(name: str) -> dict:
    """Load a scenario YAML by file name."""
    path = SCENARIO_DIR / name
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_explicit_task_specifies_top_level_structure() -> None:
    """explicit課題はトップレベル形式と階層禁止を依頼に明記する。"""
    scenario = _load("ambiguous-explicit.yaml")
    assert "トップレベル" in scenario["task"]
    assert "summary" in scenario["task"]


def test_explicit_verify_rejects_wrapper_hierarchies() -> None:
    """explicit採点はsummary等のラッパー階層を許容しない。"""
    scenario = _load("ambiguous-explicit.yaml")
    verify: str = scenario["verify_command"]
    assert "s=d.get(" not in verify
    for wrapper in ("summary", "report", "products", "sales_report"):
        assert f"'{wrapper}' not in d" in verify


def test_spontaneous_task_specifies_top_level_structure() -> None:
    """spontaneous課題も構造は指定し、対象の曖昧さだけを測る。"""
    scenario = _load("ambiguous-spontaneous.yaml")
    assert "トップレベル" in scenario["task"]
    assert "summary" in scenario["task"]
    verify: str = scenario["verify_command"]
    assert "s=d.get(" not in verify


def test_no_change_task_states_input_premise() -> None:
    """no-change課題は入力前提を明記し、範囲外拡張を禁じる。"""
    scenario = _load("no-change.yaml")
    assert "low <= high" in scenario["task"]


@pytest.mark.parametrize(
    "report,expected",
    [
        ('{"apple": 300, "cherry": 500}', True),
        ('{"summary": {"apple": 300, "cherry": 500}}', False),
        ('{"products": {"apple": 300, "cherry": 500}}', False),
        ('{"report": {"apple": 300, "cherry": 500}}', False),
        ('{"apple": 300, "cherry": 500, "banana": 150}', False),
    ],
)
def test_strict_verify_accepts_only_top_level(
    tmp_path: Path, report: str, expected: bool
) -> None:
    """厳密化したverifyが階層ラッパーを落とし、正規形を通す。"""
    scenario = _load("ambiguous-explicit.yaml")
    (tmp_path / "report.json").write_text(report, encoding="utf-8")
    result = _run_verify_command(scenario["verify_command"], tmp_path)
    assert result["passed"] is expected


def test_unit_tasks_use_amount_neutral_example() -> None:
    """集計単位を問う課題の例示は金額を連想させない。"""
    for name in ("ambiguous-unit.yaml", "ambiguous-unit-count.yaml"):
        scenario = _load(name)
        assert '"apple": 300' not in scenario["task"]
        assert "集計値" in scenario["task"]


def test_new_collaboration_scenarios_load() -> None:
    """施策3の新規4課題が重複キーなく読み込める。"""
    scenarios = load_scenarios(sorted(SCENARIO_DIR.glob("*.yaml")))
    by_id = {s["id"]: s for s in scenarios}
    for sid in (
        "ambiguous-period",
        "ambiguous-output",
        "ambiguous-unit",
        "complete-no-question",
    ):
        assert sid in by_id, f"missing scenario: {sid}"
        assert by_id[sid].get("fixture"), f"{sid} has no fixture"
        assert by_id[sid].get("verify_command"), f"{sid} has no verify"


def test_new_ambiguous_scenarios_wait_for_question() -> None:
    """新規の不足情報3種は質問待ち設計、対照は質問なし設計。"""
    scenarios = load_scenarios(sorted(SCENARIO_DIR.glob("*.yaml")))
    by_id = {s["id"]: s for s in scenarios}
    for sid in ("ambiguous-period", "ambiguous-output", "ambiguous-unit"):
        assert by_id[sid].get("script_after_question") is True
        assert by_id[sid].get("user_script"), f"{sid} needs an answer script"
    control = by_id["complete-no-question"]
    assert not control.get("user_script")
    assert not control.get("script_after_question")


def test_period_fixture_supports_month_filtering() -> None:
    """period用fixtureは月で絞れる日付列を持つ。"""
    rows = (SCENARIO_DIR / "fixtures" / "period_ws" / "sales.csv").read_text(
        encoding="utf-8"
    )
    assert "date" in rows.splitlines()[0]
    jan_apple = sum(
        int(line.split(",")[2])
        for line in rows.splitlines()[1:]
        if line.startswith("2024-01") and ",apple," in line
    )
    assert jan_apple == 300
    assert "cherry" in rows
    assert not any(
        line.startswith("2024-01") and ",cherry," in line
        for line in rows.splitlines()[1:]
    )


def test_period_verify_matches_january_totals(tmp_path: Path) -> None:
    """period採点は1月分（apple 300 / banana 150 / cherryなし）を要求する。"""
    scenario = _load("ambiguous-period.yaml")
    (tmp_path / "report.json").write_text(
        json.dumps({"apple": 300, "banana": 150}), encoding="utf-8"
    )
    assert _run_verify_command(scenario["verify_command"], tmp_path)["passed"] is True
    (tmp_path / "report.json").write_text(
        json.dumps({"apple": 350, "banana": 150, "cherry": 500}),
        encoding="utf-8",
    )
    assert _run_verify_command(scenario["verify_command"], tmp_path)["passed"] is False
