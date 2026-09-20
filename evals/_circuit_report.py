"""Quick circuit-v1 A/B report."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals.analysis import stage_summary  # noqa: E402

ROOT = Path(__file__).resolve().parent / "results" / "circuit-v1"

EXPECT = {
    "ambiguous-spontaneous": True,
    "complete-no-question": False,
}

for cond_dir in sorted(ROOT.iterdir()):
    if not cond_dir.is_dir():
        continue
    print(f"=== {cond_dir.name} ===")
    for sc_dir in sorted(cond_dir.iterdir()):
        if not sc_dir.is_dir():
            continue
        for run_dir in sorted(sc_dir.iterdir()):
            rj = run_dir / "result.json"
            tj = run_dir / "transcript.json"
            if not rj.is_file():
                continue
            r = json.loads(rj.read_text(encoding="utf-8"))
            gate = r.get("experiment", {}).get("interpretation_gate")
            asked = None
            if tj.is_file():
                t = json.loads(tj.read_text(encoding="utf-8"))
                st = stage_summary(t, EXPECT.get(sc_dir.name))
                asked = st["confirmed"]
            print(
                f"  {sc_dir.name} {run_dir.name.split('-')[-2]}: "
                f"passed={r.get('passed')} status={r.get('status')} "
                f"gate={gate} stage1_confirmed={asked}"
            )
