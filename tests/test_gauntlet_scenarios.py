"""Tests for Gauntlet scenario placement and scoring."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals.runner import SCENARIO_DIR, _run_checks, load_scenarios  # noqa: E402

GAUNTLET_IDS = ["rename-hard", "recover-quad", "needle-wide"]


def test_all_glob_excludes_gauntlet() -> None:
    """Routine --all runs (top-level glob) never pick up Gauntlet scenarios."""
    top_level_ids = [
        path.stem for path in sorted(SCENARIO_DIR.glob("*.yaml"))
    ]
    for scenario_id in GAUNTLET_IDS:
        assert scenario_id not in top_level_ids


def test_gauntlet_scenarios_load_with_fixtures() -> None:
    """Gauntlet scenarios load by id and resolve their fixture directories."""
    files = sorted(SCENARIO_DIR.rglob("*.yaml"))
    scenarios = {
        s["id"]: s for s in load_scenarios(files) if s["id"] in GAUNTLET_IDS
    }
    assert set(scenarios) == set(GAUNTLET_IDS)
    for scenario in scenarios.values():
        fixture = Path(scenario["_path"]).parent / scenario["fixture"]
        assert fixture.is_dir(), f"missing fixture for {scenario['id']}"


def test_recover_orders_check_accepts_correct_variants(tmp_path: Path) -> None:
    """The orders.py check accepts correct spellings, rejects the bug."""
    scenarios = {
        s["id"]: s
        for s in load_scenarios(
            [SCENARIO_DIR / "gauntlet" / "recover-quad.yaml"]
        )
    }
    check = next(
        c
        for c in scenarios["recover-quad"]["checks"]
        if c["path"] == "orders.py" and c["type"] == "file_contains"
    )
    workspace = tmp_path / "ws"
    workspace.mkdir()
    target = workspace / "orders.py"
    for body in (
        "return price * (1 - rate)",
        "return price * (1.0 - rate)",
        "return price - (price * rate)",
    ):
        target.write_text(f"def discount(price, rate):\n    {body}\n", encoding="utf-8")
        assert _run_checks([check], workspace)[0]["passed"] is True, body
    target.write_text(
        "def discount(price, rate):\n    return price - rate\n", encoding="utf-8"
    )
    assert _run_checks([check], workspace)[0]["passed"] is False
