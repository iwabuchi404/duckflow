"""Baseline snapshots and run-to-run comparison for eval results.

A baseline is a small committable JSON (evals/baselines/<name>.json) that
captures, alongside the aggregated scores, *where in history the runs were
made*: the repo HEAD at snapshot time, dirty-tree state with a diff hash,
the distinct git commits embedded in each run's experiment meta, and a
fingerprint per scenario (YAML + fixture contents). --compare then warns
whenever a new run set is not strictly comparable to the baseline.

Usage:
    uv run python -X utf8 evals/baseline.py --save gauntlet-2026-09 \
        --dir evals/results/gauntlet
    uv run python -X utf8 evals/baseline.py --compare gauntlet-2026-09 \
        --dir evals/results/gauntlet-new
"""

import argparse
import hashlib
import json
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPO_ROOT = Path(__file__).resolve().parents[1]
SCENARIO_DIR = Path(__file__).resolve().parent / "scenarios"
BASELINE_DIR = Path(__file__).resolve().parent / "baselines"
DEFAULT_RESULTS_DIR = Path(__file__).resolve().parent / "results"


def _git(*args: str) -> str:
    """Run a git command in the repo and return stripped stdout.

    Args:
        *args: git subcommand arguments.

    Returns:
        Stripped stdout, or empty string on failure.
    """
    proc = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        timeout=15,
        cwd=str(REPO_ROOT),
    )
    return proc.stdout.strip() if proc.returncode == 0 else ""


def collect_runs(results_dirs: list[Path]) -> list[dict[str, Any]]:
    """Load every per-run result.json under the given results directories.

    Args:
        results_dirs: Directories laid out as <scenario_id>/<run>/result.json.

    Returns:
        Result dicts, each annotated with its source path.
    """
    runs: list[dict[str, Any]] = []
    for results_dir in results_dirs:
        for path in sorted(results_dir.glob("*/*/result.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            data["_path"] = str(path)
            runs.append(data)
    return runs


def scenario_fingerprint(scenario_id: str) -> str:
    """Hash a scenario YAML plus its fixture tree.

    Changes to the scenario definition or any fixture file change the
    fingerprint, so comparisons against runs made under a different
    fingerprint are only indicative, not strict.

    Args:
        scenario_id: Scenario id (matched to a YAML by 'id' field).

    Returns:
        Truncated sha256 hex, or "missing" when the YAML no longer exists.
    """
    from evals.runner import load_scenarios

    for path in sorted(SCENARIO_DIR.rglob("*.yaml")):
        data = load_scenarios([path])[0]
        if data.get("id") != scenario_id:
            continue
        hasher = hashlib.sha256()
        hasher.update(path.read_bytes())
        fixture = path.parent / data.get("fixture", "")
        if fixture.is_dir():
            for file in sorted(fixture.rglob("*")):
                if file.is_file():
                    rel = str(file.relative_to(fixture)).replace("\\", "/")
                    hasher.update(rel.encode("utf-8"))
                    hasher.update(file.read_bytes())
        return hasher.hexdigest()[:12]
    return "missing"


def aggregate(runs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Aggregate run results per (scenario, model, protocol).

    Args:
        runs: Result dicts from collect_runs.

    Returns:
        Mapping "<scenario>|<model>|<protocol>" -> stats dict with run
        count, pass count, and median tokens/loops/duration.
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    for run in runs:
        protocol = (run.get("experiment") or {}).get("tool_protocol") or "?"
        key = f"{run.get('scenario_id')}|{run.get('model')}|{protocol}"
        groups.setdefault(key, []).append(run)

    stats: dict[str, dict[str, Any]] = {}
    for key, group in groups.items():
        tokens = [
            (r.get("usage") or {}).get("total_tokens")
            for r in group
            if (r.get("usage") or {}).get("total_tokens") is not None
        ]
        loops = [r.get("loops_used") for r in group if r.get("loops_used") is not None]
        seconds = [
            r.get("duration_seconds")
            for r in group
            if r.get("duration_seconds") is not None
        ]
        statuses: dict[str, int] = {}
        for r in group:
            statuses[r.get("status", "?")] = statuses.get(r.get("status", "?"), 0) + 1
        stats[key] = {
            "runs": len(group),
            "passed": sum(1 for r in group if r.get("passed")),
            "median_tokens": statistics.median(tokens) if tokens else None,
            "median_loops": statistics.median(loops) if loops else None,
            "median_seconds": statistics.median(seconds) if seconds else None,
            "statuses": statuses,
        }
    return stats


def _git_state() -> dict[str, Any]:
    """Capture the repo's current commit/dirty state and diff hash.

    Returns:
        Dict with head commit, porcelain status text, dirty flag, and a
        truncated sha256 of `git diff HEAD` (empty when clean).
    """
    head = _git("rev-parse", "HEAD") or "unknown"
    porcelain = _git("status", "--porcelain")
    diff_text = _git("diff", "HEAD")
    diff_sha = (
        hashlib.sha256(diff_text.encode("utf-8")).hexdigest()[:16] if diff_text else ""
    )
    return {
        "head": head,
        "dirty": bool(porcelain),
        "porcelain": porcelain,
        "diff_sha": diff_sha,
    }


def build_baseline(name: str, results_dirs: list[Path]) -> dict[str, Any]:
    """Build the baseline snapshot dict.

    Args:
        name: Baseline name (used as the JSON filename).
        results_dirs: Directories to collect run results from.

    Returns:
        Baseline dict ready for JSON serialization.
    """
    runs = collect_runs(results_dirs)
    scenario_ids = sorted({r.get("scenario_id") for r in runs if r.get("scenario_id")})
    run_commits = sorted(
        {
            (r.get("experiment") or {}).get("git_commit")
            for r in runs
            if (r.get("experiment") or {}).get("git_commit")
        }
    )
    return {
        "name": name,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "git": _git_state(),
        "run_commits": run_commits,
        "scenario_shas": {sid: scenario_fingerprint(sid) for sid in scenario_ids},
        "results_dirs": [str(d) for d in results_dirs],
        "stats": aggregate(runs),
    }


def save_baseline(name: str, results_dirs: list[Path]) -> Path:
    """Write a baseline snapshot under evals/baselines/.

    Args:
        name: Baseline name.
        results_dirs: Directories to collect run results from.

    Returns:
        Path of the written JSON file.
    """
    baseline = build_baseline(name, results_dirs)
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    out = BASELINE_DIR / f"{name}.json"
    out.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def comparability_warnings(
    baseline: dict[str, Any], current_runs: list[dict[str, Any]]
) -> list[str]:
    """Check whether current runs are strictly comparable to the baseline.

    Args:
        baseline: Stored baseline dict.
        current_runs: Newly collected run results.

    Returns:
        Warning strings; empty means fully comparable conditions.
    """
    warnings: list[str] = []
    git = baseline.get("git", {})
    base_head = git.get("head", "unknown")
    now_head = _git("rev-parse", "HEAD") or "unknown"

    if base_head != "unknown" and now_head != "unknown" and base_head != now_head:
        between = _git("rev-list", "--count", f"{base_head}..HEAD")
        if between:
            warnings.append(
                f"code drift: {between} commit(s) between baseline ({base_head[:8]}) "
                f"and HEAD ({now_head[:8]})"
            )
        else:
            warnings.append(
                f"code drift: HEAD ({now_head[:8]}) is not a descendant of "
                f"baseline ({base_head[:8]})"
            )
    if len(baseline.get("run_commits", [])) > 1:
        warnings.append(
            "baseline spans multiple commits: "
            + ", ".join(c[:8] for c in baseline["run_commits"])
        )
    if git.get("dirty"):
        warnings.append(
            f"baseline was recorded on a dirty tree (diff_sha:{git.get('diff_sha')})"
        )
    if _git("status", "--porcelain"):
        warnings.append("current working tree is dirty")

    current_ids = {r.get("scenario_id") for r in current_runs if r.get("scenario_id")}
    for sid, sha in baseline.get("scenario_shas", {}).items():
        now_sha = scenario_fingerprint(sid)
        if now_sha != sha:
            note = "deleted" if now_sha == "missing" else "modified"
            warnings.append(
                f"scenario {note}: {sid} (baseline sha {sha}, now {now_sha})"
            )
        if sid not in current_ids:
            warnings.append(f"scenario missing from current runs: {sid}")
    extra = current_ids - set(baseline.get("scenario_shas", {}))
    for sid in sorted(extra):
        warnings.append(f"new scenario not in baseline: {sid}")
    return warnings


def _stat_delta(
    base: dict[str, Any] | None, now: dict[str, Any] | None, field: str
) -> str:
    """Format the delta of a numeric stat field between two stat dicts.

    Args:
        base: Baseline stats dict (or None when absent).
        now: Current stats dict (or None when absent).
        field: Stat key to compare.

    Returns:
        Signed delta string, or "-" when either side is missing.
    """
    if not base or not now:
        return "-"
    b, n = base.get(field), now.get(field)
    if b is None or n is None:
        return "-"
    return f"{n - b:+g}"


def print_comparison(
    baseline: dict[str, Any], current_runs: list[dict[str, Any]]
) -> None:
    """Print baseline-vs-current comparison with comparability warnings.

    Args:
        baseline: Stored baseline dict.
        current_runs: Newly collected run results.
    """
    print(f"baseline: {baseline.get('name')} (recorded {baseline.get('recorded_at')})")
    print(f"baseline HEAD: {baseline.get('git', {}).get('head', '?')[:8]}")

    warnings = comparability_warnings(baseline, current_runs)
    if warnings:
        print("\n! comparability warnings:")
        for w in warnings:
            print(f"  - {w}")
    else:
        print("\nconditions: fully comparable")

    current_stats = aggregate(current_runs)
    keys = sorted(set(baseline.get("stats", {})) | set(current_stats))
    print(
        f"\n{'scenario|model|protocol':<58}{'base':<9}{'now':<9}"
        f"{'pass d':<8}{'tok d':<12}{'loop d'}"
    )
    print("-" * 96)
    for key in keys:
        base = baseline.get("stats", {}).get(key)
        now = current_stats.get(key)
        base_pass = f"{base['passed']}/{base['runs']}" if base else "-"
        now_pass = f"{now['passed']}/{now['runs']}" if now else "-"
        pass_d = (
            f"{now['passed'] / now['runs'] - base['passed'] / base['runs']:+.0%}"
            if base and now
            else "-"
        )

        print(
            f"{key:<58}{base_pass:<9}{now_pass:<9}{pass_d:<8}"
            f"{_stat_delta(base, now, 'median_tokens'):<12}"
            f"{_stat_delta(base, now, 'median_loops')}"
        )


def main() -> None:
    """CLI entry point for baseline save/compare."""
    parser = argparse.ArgumentParser(description="Eval baseline snapshots")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--save", metavar="NAME", help="Save runs as baseline NAME")
    group.add_argument(
        "--compare", metavar="NAME", help="Compare current runs against baseline NAME"
    )
    parser.add_argument(
        "--dir",
        action="append",
        default=None,
        help="Results directory (repeatable; default evals/results)",
    )
    args = parser.parse_args()

    results_dirs = [Path(d) for d in (args.dir or [str(DEFAULT_RESULTS_DIR)])]

    if args.save:
        out = save_baseline(args.save, results_dirs)
        print(f"saved: {out}")
        return

    baseline_path = BASELINE_DIR / f"{args.compare}.json"
    if not baseline_path.is_file():
        parser.error(f"baseline not found: {baseline_path}")
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    current_runs = collect_runs(results_dirs)
    if not current_runs:
        parser.error(f"no runs found under: {results_dirs}")
    print_comparison(baseline, current_runs)


if __name__ == "__main__":
    main()
