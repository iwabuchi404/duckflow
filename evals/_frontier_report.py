"""Quick frontier-v1 report: per-run pass/stage-1 confirmation."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals.analysis import stage_summary, tag_asked_question  # noqa: E402

ROOT = Path(__file__).resolve().parent / "results" / "frontier-v1"

EXPECT = {
    "frontier-ambiguous-semantic": True,
    "frontier-replan": False,
    "frontier-cross-impact": False,
    "frontier-contradiction": None,
    "frontier-partial-evidence": False,
}

for model_dir in sorted(ROOT.iterdir()):
    if not model_dir.is_dir():
        continue
    print(f"=== {model_dir.name} ===")
    for sc_dir in sorted(model_dir.iterdir()):
        if not sc_dir.is_dir():
            continue
        for run_dir in sorted(sc_dir.iterdir()):
            tj = run_dir / "transcript.json"
            rj = run_dir / "result.json"
            if not tj.is_file():
                continue
            t = json.loads(tj.read_text(encoding="utf-8"))
            r = json.loads(rj.read_text(encoding="utf-8")) if rj.is_file() else {}
            hist = t.get("conversation_history", [])
            asked = tag_asked_question(hist)
            st = stage_summary(t, EXPECT.get(sc_dir.name))
            print(
                f"  {sc_dir.name} {run_dir.name.split('-')[-2]}: "
                f"passed={r.get('passed')} status={r.get('status')} "
                f"asked={asked} confirmed={st['confirmed']} "
                f"natural={st['natural_completion']}"
            )
