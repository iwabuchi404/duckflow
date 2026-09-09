"""Heuristic analysis of eval transcripts.

Scans transcript.json files produced by evals/runner.py and tags known
failure patterns observed with weak models (output echo, investigation
re-entry, empty responses, repeated commands, blocked edits, duck-call
give-ups). The tagging set is intentionally easy to extend: add a function
returning a bool and register it in TAGS.

Usage:
    uv run python -X utf8 -m evals.analysis            # analyze evals/results/
    uv run python -X utf8 -m evals.analysis --dir path # analyze another dir
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Callable

_ACTION_RE = re.compile(r"::\s*([a-z_]+)(?:\s+@([^\n]+))?")
_ECHO_MARKERS = ("=====", "test session starts", "cachedir:")


def _extract_action_sequence(history: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """Extract (action_name, target) pairs from assistant action summaries.

    Args:
        history: transcript conversation_history.

    Returns:
        Ordered list of (name, target) tuples; target is "" when absent.
    """
    sequence: list[tuple[str, str]] = []
    for msg in history:
        if msg.get("role") != "assistant":
            continue
        for name, target in _ACTION_RE.findall(msg.get("content", "")):
            sequence.append((name, target.strip()[:120]))
    return sequence


def tag_output_echo(history: list[dict[str, Any]]) -> bool:
    """Detect commands whose target is pasted tool output (echo degeneration).

    Args:
        history: transcript conversation_history.

    Returns:
        True when a run_command target contains output artifacts.
    """
    for name, target in _extract_action_sequence(history):
        if name == "run_command" and any(m in target for m in _ECHO_MARKERS):
            return True
        if name == "run_command" and ("\n" in target or len(target) > 100):
            return True
    return False


def tag_investigation_reentry(history: list[dict[str, Any]]) -> bool:
    """Detect ::investigate called again after ::finish_investigation.

    Args:
        history: transcript conversation_history.

    Returns:
        True when investigation is re-entered after being closed.
    """
    finished = False
    for name, _ in _extract_action_sequence(history):
        if name == "finish_investigation":
            finished = True
        elif name == "investigate" and finished:
            return True
    return False


def _has_error_type(history: list[dict[str, Any]], error_type: str) -> bool:
    """Check whether a [TOOL_RESULT] with the given error marker exists."""
    return any(
        msg.get("role") == "user" and error_type in msg.get("content", "")
        for msg in history
    )


def tag_blocked_edit(history: list[dict[str, Any]]) -> bool:
    """Detect edits blocked by Investigation Mode.

    Args:
        history: transcript conversation_history.

    Returns:
        True when at least one edit was blocked.
    """
    return _has_error_type(history, "investigation_edit_blocked")


def tag_empty_response(history: list[dict[str, Any]]) -> bool:
    """Detect empty ::response turns.

    Args:
        history: transcript conversation_history.

    Returns:
        True when at least one empty response was recorded.
    """
    return _has_error_type(history, "empty_response")


def tag_repeated_command(history: list[dict[str, Any]]) -> bool:
    """Detect the same command target executed two or more times.

    Args:
        history: transcript conversation_history.

    Returns:
        True when any run_command target repeats.
    """
    commands = [t for n, t in _extract_action_sequence(history) if n == "run_command"]
    return len(commands) != len(set(commands))


def tag_duck_call(history: list[dict[str, Any]]) -> bool:
    """Detect the run ending in (or containing) a duck_call consultation.

    Args:
        history: transcript conversation_history.

    Returns:
        True when duck_call appears in the action sequence.
    """
    return any(n == "duck_call" for n, _ in _extract_action_sequence(history))


def tag_no_edit_applied(history: list[dict[str, Any]]) -> bool:
    """Detect tasks that never performed an edit/write action.

    Args:
        history: transcript conversation_history.

    Returns:
        True when no edit_file/write_file/replace_in_file action ran.
    """
    names = {n for n, _ in _extract_action_sequence(history)}
    return not names & {"edit_file", "write_file", "replace_in_file"}


def tag_api_error(history: list[dict[str, Any]]) -> bool:
    """Detect environment/API failures (not model behavior).

    Args:
        history: transcript conversation_history.

    Returns:
        True when an LLM API error message is present.
    """
    return any(
        msg.get("role") == "assistant" and "LLM API Error" in msg.get("content", "")
        for msg in history
    )


def tag_fabricated_tool_result(transcript: dict[str, Any]) -> bool:
    """Detect the model writing [TOOL_RESULT]/::status in its own raw output.

    Args:
        transcript: Full transcript dict (uses raw_responses).

    Returns:
        True when any raw response contains tool-result artifacts.
    """
    for raw in transcript.get("raw_responses") or []:
        if raw.startswith("<"):
            continue  # skip chat_error / empty markers
        if "[TOOL_RESULT]" in raw or re.search(
            r"^\s*::\s*status\s+\w+", raw, re.MULTILINE
        ):
            return True
    return False


def tag_empty_llm_response(transcript: dict[str, Any]) -> bool:
    """Detect at least one empty LLM response in the run.

    Args:
        transcript: Full transcript dict (uses raw_responses).

    Returns:
        True when an empty response marker is present.
    """
    return any(r == "<empty response>" for r in transcript.get("raw_responses") or [])


def tag_llm_call_error(transcript: dict[str, Any]) -> bool:
    """Detect at least one failed (exception) LLM call in the run.

    Args:
        transcript: Full transcript dict (uses raw_responses).

    Returns:
        True when a chat_error marker is present.
    """
    return any(
        r.startswith("<chat_error:") for r in transcript.get("raw_responses") or []
    )


TAGS: dict[str, Callable[[list[dict[str, Any]]], bool]] = {
    "api_error": tag_api_error,
    "output_echo": tag_output_echo,
    "investigation_reentry": tag_investigation_reentry,
    "blocked_edit": tag_blocked_edit,
    "empty_response": tag_empty_response,
    "repeated_command": tag_repeated_command,
    "duck_call": tag_duck_call,
    "no_edit_applied": tag_no_edit_applied,
}


def tag_transcript(transcript: dict[str, Any]) -> dict[str, Any]:
    """Compute heuristic tags and basic stats for one transcript.

    Args:
        transcript: Parsed transcript.json content.

    Returns:
        Dict with scenario_id, passed, loops, tags list.
    """
    history = transcript.get("conversation_history", [])
    result = transcript.get("result", {})
    tags = [name for name, fn in TAGS.items() if fn(history)]
    if tag_fabricated_tool_result(transcript):
        tags.append("fabricated_tool_result")
    if tag_empty_llm_response(transcript):
        tags.append("empty_llm_response")
    if tag_llm_call_error(transcript):
        tags.append("llm_call_error")
    return {
        "scenario_id": result.get("scenario_id", "unknown"),
        "passed": result.get("passed", False),
        "loops": result.get("loops_used", 0),
        "tags": tags,
    }


def analyze_dir(results_dir: Path) -> dict[str, Any]:
    """Analyze every transcript under a results directory.

    Args:
        results_dir: Directory containing <scenario>/<run>/transcript.json.

    Returns:
        {"runs": [...], "tag_counts": {scenario: {tag: count}}}
    """
    runs = []
    tag_counts: dict[str, Counter] = {}
    for path in sorted(results_dir.glob("*/*/transcript.json")):
        try:
            transcript = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        entry = tag_transcript(transcript)
        entry["path"] = str(path)
        runs.append(entry)
        counts = tag_counts.setdefault(entry["scenario_id"], Counter())
        for tag in entry["tags"]:
            counts[tag] += 1
    return {
        "runs": runs,
        "tag_counts": {k: dict(v) for k, v in tag_counts.items()},
    }


def print_report(analysis: dict[str, Any]) -> None:
    """Print a human-readable analysis report.

    Args:
        analysis: Result of analyze_dir().
    """
    by_scenario: dict[str, list[dict[str, Any]]] = {}
    for run in analysis["runs"]:
        by_scenario.setdefault(run["scenario_id"], []).append(run)

    print(f"{'scenario':<24}{'runs':<6}{'pass':<6} top tags")
    print("-" * 72)
    for scenario, runs in sorted(by_scenario.items()):
        passed = sum(1 for r in runs if r["passed"])
        counts = Counter()
        for r in runs:
            counts.update(r["tags"])
        top = ", ".join(f"{t}:{c}" for t, c in counts.most_common(4)) or "-"
        print(f"{scenario:<24}{len(runs):<6}{passed:<6} {top}")

    for run in analysis["runs"]:
        if not run["passed"] and run["tags"]:
            print(f"\n[FAIL] {run['path']}")
            print(f"       tags: {', '.join(run['tags'])}")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Analyze eval transcripts")
    parser.add_argument(
        "--dir",
        default=str(Path(__file__).resolve().parent / "results"),
        help="Results directory",
    )
    args = parser.parse_args()

    results_dir = Path(args.dir)
    analysis = analyze_dir(results_dir)
    print_report(analysis)

    out_path = results_dir / "analysis.json"
    out_path.write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nwritten: {out_path}")


if __name__ == "__main__":
    main()
