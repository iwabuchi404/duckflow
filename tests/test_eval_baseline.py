"""Tests for evals/baseline.py — snapshot aggregation and comparability."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals.baseline import (  # noqa: E402
    aggregate,
    collect_runs,
    comparability_warnings,
)


def _write_run(
    results_dir: Path,
    scenario: str,
    run_name: str,
    *,
    model: str = "m1",
    protocol: str = "symops",
    passed: bool = True,
    tokens: int = 1000,
    loops: int = 3,
    seconds: float = 30.0,
    status: str = "completed",
) -> None:
    """Write a minimal result.json under <dir>/<scenario>/<run_name>/."""
    run_dir = results_dir / scenario / run_name
    run_dir.mkdir(parents=True)
    result = {
        "scenario_id": scenario,
        "provider": "openrouter",
        "model": model,
        "experiment": {"tool_protocol": protocol, "git_commit": "abc123"},
        "status": status,
        "passed": passed,
        "duration_seconds": seconds,
        "loops_used": loops,
        "usage": {"total_tokens": tokens},
    }
    (run_dir / "result.json").write_text(json.dumps(result), encoding="utf-8")


def test_collect_runs_gathers_all_result_json(tmp_path: Path) -> None:
    """collect_runs finds every */result.json under the results dir."""
    results_dir = tmp_path / "results"
    _write_run(results_dir, "s1", "r1")
    _write_run(results_dir, "s1", "r2")
    _write_run(results_dir, "s2", "r1", model="m2", protocol="native")
    runs = collect_runs([results_dir])
    assert len(runs) == 3
    assert {r["scenario_id"] for r in runs} == {"s1", "s2"}


def test_aggregate_groups_by_scenario_model_protocol(tmp_path: Path) -> None:
    """aggregate produces per (scenario, model, protocol) stats."""
    results_dir = tmp_path / "results"
    _write_run(results_dir, "s1", "r1", passed=True, tokens=100, loops=2)
    _write_run(results_dir, "s1", "r2", passed=False, tokens=300, loops=6)
    _write_run(results_dir, "s1", "r3", passed=True, tokens=200, loops=4)
    _write_run(results_dir, "s1", "r4", protocol="native", tokens=50)
    stats = aggregate(collect_runs([results_dir]))

    symops = stats["s1|m1|symops"]
    assert symops["runs"] == 3
    assert symops["passed"] == 2
    assert symops["median_tokens"] == 200
    assert symops["median_loops"] == 4
    assert symops["statuses"] == {"completed": 3}

    native = stats["s1|m1|native"]
    assert native["runs"] == 1
    assert native["median_tokens"] == 50


def test_comparability_warns_on_missing_scenario(tmp_path: Path) -> None:
    """A baseline scenario absent from current runs produces a warning."""
    baseline = {
        "name": "b",
        "git": {"head": "unknown", "dirty": False},
        "run_commits": ["abc"],
        "scenario_shas": {"fix-typo": "abc"},
        "stats": {},
    }
    warnings = comparability_warnings(baseline, [])
    assert any("fix-typo" in w and "missing" in w for w in warnings)


def test_comparability_warns_on_scenario_change(tmp_path: Path) -> None:
    """A changed scenario fingerprint produces a warning."""
    baseline = {
        "name": "b",
        "git": {"head": "unknown", "dirty": False},
        "run_commits": ["abc"],
        # Deliberately wrong sha → mismatch with the real fingerprint.
        "scenario_shas": {"fix-typo": "deadbeef"},
        "stats": {},
    }
    results_dir = tmp_path / "results"
    _write_run(results_dir, "fix-typo", "r1")
    warnings = comparability_warnings(baseline, collect_runs([results_dir]))
    assert any("fix-typo" in w and "modified" in w for w in warnings)


def test_comparability_warns_on_new_scenario(tmp_path: Path) -> None:
    """A scenario not present in the baseline produces a warning."""
    baseline = {
        "name": "b",
        "git": {"head": "unknown", "dirty": False},
        "run_commits": ["abc"],
        "scenario_shas": {},
        "stats": {},
    }
    results_dir = tmp_path / "results"
    _write_run(results_dir, "brand-new", "r1")
    warnings = comparability_warnings(baseline, collect_runs([results_dir]))
    assert any("brand-new" in w for w in warnings)


def test_comparability_clean_when_matching(tmp_path: Path, monkeypatch) -> None:
    """Matching conditions produce no code-drift warnings (git aside)."""
    from evals import baseline as bl

    monkeypatch.setattr(bl, "_git", lambda *a: "")
    monkeypatch.setattr(bl, "scenario_fingerprint", lambda sid: "samesha")
    baseline = {
        "name": "b",
        "git": {"head": "samecommit", "dirty": False},
        "run_commits": ["abc"],
        "scenario_shas": {"s1": "samesha"},
        "stats": {},
    }
    results_dir = tmp_path / "results"
    _write_run(results_dir, "s1", "r1")
    warnings = comparability_warnings(baseline, collect_runs([results_dir]))
    # HEAD lookup returns "" → "unknown"; the only permitted noise is none.
    assert warnings == []
