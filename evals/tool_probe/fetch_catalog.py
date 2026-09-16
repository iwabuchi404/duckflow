"""Fetch OpenRouter model catalog and save a tool-calling snapshot.

Reproducible extraction for docs/research/tool-calling-support-*.md:
fetches the public model list, extracts the configured OpenRouter IDs
plus evaluation/control IDs, and saves supported_parameters with
tools/tool_choice/structured_outputs flags.

Usage:
    uv run python -X utf8 evals/tool_probe/fetch_catalog.py
    uv run python -X utf8 evals/tool_probe/fetch_catalog.py --out path.json
"""

import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"

# Control IDs kept to demonstrate that JSON output and Tool Calling
# are separate features within the same source.
CONTROL_IDS = [
    "inference-net/schematron-v2-small",
    "tencent/hy-mt2-1.8b",
]

# Live E2E models passed via --model (not registered in duckflow.yaml).
# Listed explicitly so catalog coverage never silently drops them.
EVAL_IDS = [
    "z-ai/glm-4.5-air",
    "minimax/minimax-m2.1",
    "deepseek/deepseek-v4.1-flash",
]


def configured_openrouter_ids(repo_root: Path) -> list[str]:
    """Collect OpenRouter model IDs from duckflow.yaml plus known extras.

    The :free paid-ID variant and retired IDs are intentionally included:
    absence from the catalog is itself a finding (do not reuse the paid
    ID's flags for the free variant).

    Args:
        repo_root: Repository root containing duckflow.yaml.

    Returns:
        Ordered, de-duplicated model ID list.
    """
    import yaml

    with open(repo_root / "duckflow.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    ids: list[str] = []
    for entry in (cfg.get("llm", {}).get("available_models", []) or []):
        model = (entry or {}).get("model", "")
        if isinstance(model, str) and "/" in model and not model.startswith("@cf/"):
            ids.append(model)
    extras = [
        "z-ai/glm-4.5-air:free",
        "anthropic/claude-3-5-sonnet-20241022",
        "deepseek/deepseek-v4-flash-0731",
    ]
    seen: set[str] = set()
    ordered = [
        i
        for i in ids + EVAL_IDS + extras + CONTROL_IDS
        if not (i in seen or seen.add(i))
    ]
    return ordered


def extract_catalog(models_data: list[dict], ids: list[str]) -> list[dict]:
    """Extract tool-calling flags for target IDs from catalog data.

    Args:
        models_data: Raw "data" list from the OpenRouter models API.
        ids: Target model IDs.

    Returns:
        Per-ID dicts with found flag, supported_parameters excerpt,
        and tools/tool_choice/structured_outputs advertisement flags
        (None when the ID is not listed).
    """
    by_id = {m.get("id"): m for m in models_data if isinstance(m, dict)}
    entries = []
    for target in ids:
        raw = by_id.get(target)
        if raw is None:
            entries.append(
                {
                    "id": target,
                    "found": False,
                    "supported_parameters": [],
                    "tools_advertised": None,
                    "tool_choice_advertised": None,
                    "structured_outputs_advertised": None,
                }
            )
            continue
        params = raw.get("supported_parameters", []) or []
        entries.append(
            {
                "id": target,
                "found": True,
                "supported_parameters": sorted(params),
                "tools_advertised": "tools" in params,
                "tool_choice_advertised": "tool_choice" in params,
                "structured_outputs_advertised": "structured_outputs" in params,
            }
        )
    return entries


def fetch_models_data() -> list[dict]:
    """Fetch the raw OpenRouter model list.

    Returns:
        The "data" list from the public models API.

    Raises:
        RuntimeError: On network or decode failure.
    """
    req = urllib.request.Request(
        OPENROUTER_MODELS_URL, headers={"User-Agent": "duckflow-eval-probe"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        raise RuntimeError(f"failed to fetch {OPENROUTER_MODELS_URL}: {e}")
    data = payload.get("data", [])
    if not isinstance(data, list):
        raise RuntimeError("unexpected models API shape: 'data' is not a list")
    return data


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Fetch tool-calling catalog")
    parser.add_argument(
        "--out",
        default=str(
            Path(__file__).resolve().parents[2]
            / "docs"
            / "research"
            / "tool-calling-catalog-2026-09-13.json"
        ),
        help="Snapshot output path",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    ids = configured_openrouter_ids(repo_root)
    snapshot = {
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": OPENROUTER_MODELS_URL,
        "scope": "Configured OpenRouter IDs, evaluation models, and two catalog controls",
        "live_tool_calls_tested": False,
        "models": extract_catalog(fetch_models_data(), ids),
    }
    out = Path(args.out)
    out.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1), encoding="utf-8")
    found = sum(1 for m in snapshot["models"] if m["found"])
    print(f"saved: {out} ({found}/{len(snapshot['models'])} IDs listed)")


if __name__ == "__main__":
    main()
