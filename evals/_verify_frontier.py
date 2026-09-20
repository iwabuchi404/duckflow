"""Local validation for frontier scenarios.

For each scenario YAML under evals/scenarios/frontier/:
  1. YAML loads and fixture dir exists.
  2. Copy fixture to a temp workspace, run checks + verify on the INITIAL
     state (expected: fix-type scenarios fail, contradiction passes
     workspace_unmodified but has no report yet — checks still pass since
     report_contains needs history; we only inspect check outcomes).
  3. Apply a reference solution, re-run checks + verify (expected: pass).
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
FRONTIER = REPO / "evals" / "scenarios" / "frontier"


def run_cmd(cmd: str, cwd: Path) -> tuple[int, str]:
    cmd = cmd.replace("{python}", f'"{sys.executable}"')
    p = subprocess.run(cmd, shell=True, cwd=str(cwd), capture_output=True, timeout=120)
    out = (p.stdout or b"").decode("utf-8", errors="replace")
    err = (p.stderr or b"").decode("utf-8", errors="replace")
    return p.returncode, out + err


def file_checks(checks: list[dict], ws: Path, report: str = "") -> list[tuple[dict, bool]]:
    import hashlib

    results = []
    for c in checks:
        kind = c["type"]
        path = ws / c.get("path", "")
        content = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
        if kind == "file_exists":
            ok = path.exists()
        elif kind == "file_not_exists":
            ok = not path.exists()
        elif kind == "file_contains":
            ok = c.get("text", "") in content
        elif kind == "file_not_contains":
            ok = c.get("text", "") not in content
        elif kind == "report_contains":
            texts = c.get("texts") or [c.get("text", "")]
            ok = bool(report) and any(t in report for t in texts if t)
        else:
            ok = None  # workspace_unmodified etc. handled by caller
        results.append((c, ok))
    return results


# --- reference solutions -------------------------------------------------

def solve_ambig_sem(ws: Path) -> None:
    seen, out = set(), []
    import csv

    for row in csv.DictReader(open(ws / "members.csv", encoding="utf-8")):
        n = row["name"]
        if n not in seen:
            seen.add(n)
            out.append(row["email"])
    (ws / "members.json").write_text(json.dumps(out), encoding="utf-8")


def solve_replan(ws: Path) -> None:
    (ws / "report.py").write_text(
        '''"""Generate an aggregated sales report in pure Python."""

import csv
from collections import defaultdict


def main() -> None:
    totals = defaultdict(int)
    with open("sales.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            totals[row["product"]] += int(row["amount"])
    lines = [f"total: {sum(totals.values())}"]
    lines += [f"{p}: {totals[p]}" for p in sorted(totals)]
    with open("report.txt", "w", encoding="utf-8") as f:
        f.write("\\n".join(lines) + "\\n")


if __name__ == "__main__":
    main()
''',
        encoding="utf-8",
    )


def solve_cross_impact(ws: Path) -> None:
    d = (ws / "dates.py").read_text(encoding="utf-8").replace("%Y-%m-%d", "%d/%m/%Y")
    (ws / "dates.py").write_text(d, encoding="utf-8")
    i = (ws / "importer.py").read_text(encoding="utf-8").replace("%Y-%m-%d", "%d/%m/%Y")
    (ws / "importer.py").write_text(i, encoding="utf-8")


def solve_contradiction(ws: Path) -> None:
    # Correct solution = change nothing; report the contradiction.
    pass


def solve_partial_evidence(ws: Path) -> None:
    p = (ws / "pipeline.py").read_text(encoding="utf-8").replace('"actve"', '"active"')
    (ws / "pipeline.py").write_text(p, encoding="utf-8")


SOLVERS = {
    "frontier-ambiguous-semantic": solve_ambig_sem,
    "frontier-replan": solve_replan,
    "frontier-cross-impact": solve_cross_impact,
    "frontier-contradiction": solve_contradiction,
    "frontier-partial-evidence": solve_partial_evidence,
}

# Report text used to evaluate report_contains checks for the reference
# "solution" of contradiction.
REPORT_CONTRADICTION = "ソート要求と README の順序不変規約は矛盾（conflict）しており両立できません。"


def main() -> int:
    ok_all = True
    for yml in sorted(FRONTIER.glob("*.yaml")):
        sc = yaml.safe_load(yml.read_text(encoding="utf-8"))
        sid = sc["id"]
        fixture = yml.parent / sc["fixture"]
        assert fixture.is_dir(), f"{sid}: missing fixture {fixture}"

        ws = Path(tempfile.mkdtemp(prefix=f"frontier-{sid}-"))
        shutil.copytree(fixture, ws, dirs_exist_ok=True)

        # --- initial state ---
        init_notes = []
        vc = sc.get("verify_command")
        if vc:
            rc, out = run_cmd(vc, ws)
            init_notes.append(f"verify rc={rc}")
        for c, ok in file_checks(sc.get("checks") or [], ws):
            if ok is not None:
                init_notes.append(f"{c['type']}:{c.get('path','-')}={ok}")

        # --- reference solution ---
        SOLVERS[sid](ws)
        rc2, out2 = (None, "")
        if vc:
            rc2, out2 = run_cmd(vc, ws)
        report = REPORT_CONTRADICTION if sid == "frontier-contradiction" else "done"
        post = file_checks(sc.get("checks") or [], ws, report=report)
        post_ok = all(ok for _, ok in post if ok is not None) and (rc2 in (None, 0))
        status = "OK " if post_ok else "FAIL"
        if not post_ok:
            ok_all = False
        print(f"[{status}] {sid}\n  initial: {'; '.join(init_notes) or '(no checks)'}")
        print(f"  after-fix: verify rc={rc2} checks={post_ok}")
        if not post_ok:
            for c, ok in post:
                if ok is False:
                    print(f"    failed: {c}")
            if rc2 not in (None, 0):
                print("    verify out:", (out2 or "")[-300:])
        shutil.rmtree(ws, ignore_errors=True)
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
