import json
from pathlib import Path
from typing import Dict, Any

def _load_json(path: Path) -> Dict:
    """Utility to load a JSON file."""
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def calculate_hallucination_rate(unit_report: Dict) -> float:
    """
    Calculate hallucination rate from a unit test report.

    Expected format (example):
    {
        "total": 100,
        "failed": 5,
        ...
    }
    """
    total = unit_report.get("total", 0)
    failed = unit_report.get("failed", 0)
    if total == 0:
        return 0.0
    return failed / total

def calculate_context_retention(unit_report: Dict) -> float:
    """
    Calculate context retention rate from a unit test report.

    Expected keys:
    - "total_interactions": total number of interactions
    - "context_correct": number of interactions where context was correctly retained
    """
    total_interactions = unit_report.get("total_interactions", 0)
    context_correct = unit_report.get("context_correct", 0)
    if total_interactions == 0:
        return 0.0
    return context_correct / total_interactions

def extract_e2e_metrics(e2e_report_path: str) -> Dict[str, Any]:
    """
    Load E2E report and extract simple metrics.
    Expected JSON format:
    {
        "total_interactions": int,
        "e2e_success": int,
        ...
    }
    Returns a dict with at least:
    - "e2e_success_rate": float
    """
    path = Path(e2e_report_path)
    data = _load_json(path)

    total_interactions = data.get("total_interactions", 0)
    e2e_success = data.get("e2e_success", 0)

    if total_interactions == 0:
        e2e_success_rate = 0.0
    else:
        e2e_success_rate = e2e_success / total_interactions

    return {
        "e2e_success_rate": e2e_success_rate,
        "total_interactions": total_interactions,
        "e2e_success": e2e_success,
    }
