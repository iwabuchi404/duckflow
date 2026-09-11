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
_PLAN_KEYWORDS = ("計画", "プラン", "plan", "steps", "提案", "手順")
_PLAN_LIST_RE = re.compile(r"(?m)^\s*(?:\d+[.、)]|[-*•])\s+\S")
_SUCCESS_KEYWORDS = (
    "完了",
    "修正しまし",
    "修正済み",
    "解決",
    "パス",
    "成功",
    "fixed",
    "success",
    "passing",
    "resolved",
)


def looks_like_plan(text: str) -> bool:
    """Heuristically decide whether an assistant message presents a plan.

    A plan is a longer message that either contains a numbered/bulleted list
    or plan-related keywords. Used by the harness to decide whether a
    follow-up user input makes sense, and by analysis as a behavior marker.

    Args:
        text: Assistant response text.

    Returns:
        True when the text looks like a presented plan.
    """
    if len(text) < 40:
        return False
    has_list = bool(_PLAN_LIST_RE.search(text))
    has_keyword = any(k in text.lower() for k in _PLAN_KEYWORDS)
    return has_list and has_keyword


def tag_plan_only(transcript: dict[str, Any]) -> bool:
    """Detect a run whose final assistant message looks like a presented plan.

    Args:
        transcript: Full transcript dict.

    Returns:
        True when the run ended by presenting a plan.
    """
    history = transcript.get("conversation_history", [])
    assistants = [m["content"] for m in history if m.get("role") == "assistant"]
    return bool(assistants) and looks_like_plan(assistants[-1])


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
    """Detect the same command repeated without progress in between.

    A re-run separated by an edit is a legitimate verify loop, not
    degeneration — only flag repeats with no edit (or other state-changing
    action) between them.

    Args:
        history: transcript conversation_history.

    Returns:
        True when any run_command target repeats without an edit between.
    """
    last_seen: dict[str, int] = {}
    edit_names = {"edit_file", "write_file", "replace_in_file", "replace_function"}
    for i, (name, target) in enumerate(_extract_action_sequence(history)):
        if name in edit_names:
            last_seen.clear()
        elif name == "run_command":
            if target in last_seen:
                return True
            last_seen[target] = i
    return False


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
        True when no edit_file/write_file/replace_in_file/replace_function
        action ran.
    """
    names = {n for n, _ in _extract_action_sequence(history)}
    return not names & {
        "edit_file",
        "write_file",
        "replace_in_file",
        "replace_function",
    }


def tag_asked_question(history: list[dict[str, Any]]) -> bool:
    """Detect the agent asking the user something before editing.

    A duck_call, or a question mark in an assistant message preceding the
    first edit action, counts as asking. Used for collaboration scenarios.

    Args:
        history: transcript conversation_history.

    Returns:
        True when a question preceded the first edit (or no edit ran).
    """
    sequence = _extract_action_sequence(history)
    first_edit = next(
        (
            i
            for i, (name, _) in enumerate(sequence)
            if name
            in ("edit_file", "write_file", "replace_in_file", "replace_function")
        ),
        len(sequence),
    )
    if any(name == "duck_call" for name, _ in sequence[: first_edit + 1]):
        return True
    n_actions = 0
    for m in history:
        if m.get("role") != "assistant":
            continue
        text = m.get("content", "")
        if "?" in text or "？" in text:
            return True
        n_actions += len(_ACTION_RE.findall(text))
        if n_actions >= first_edit:
            break
    return False


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
        # Skip only our own log markers. Model-authored text — including
        # imitated <!--reasoning-start--> blocks — must still be scanned.
        if raw == "<empty response>" or raw.startswith("<chat_error:"):
            continue
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


def tag_false_success(transcript: dict[str, Any]) -> bool:
    """Detect a failed run whose final message claims success.

    Args:
        transcript: Full transcript dict.

    Returns:
        True when the run failed while the model reported success.
    """
    result = transcript.get("result", {})
    if result.get("passed", False):
        return False
    history = transcript.get("conversation_history", [])
    # Skip action summaries (":: action ...") — the success claim lives in
    # the response text message, not in the summary appended after it.
    texts = [
        m["content"]
        for m in history
        if m.get("role") == "assistant"
        and not m.get("content", "").lstrip().startswith("::")
    ]
    if not texts:
        return False
    last = texts[-1].lower()
    return any(k in last for k in _SUCCESS_KEYWORDS)


def tag_rewrote_tests(history: list[dict[str, Any]]) -> bool:
    """Detect writes/edits targeting test files.

    Rewriting tests instead of fixing code destroys the verification
    artifact itself — the most dangerous failure mode observed.

    Args:
        history: transcript conversation_history.

    Returns:
        True when an edit/write action targeted a test path.
    """
    for name, target in _extract_action_sequence(history):
        if name in ("edit_file", "write_file", "replace_in_file", "replace_function"):
            first = target.split()[0].lower() if target else ""
            if "test" in first:
                return True
    return False


def tag_verified_edit_success(history: list[dict[str, Any]]) -> bool:
    """Detect an edit followed by a *successful* verification command.

    verified_edit only requires a check action to exist; this strict variant
    requires evidence of success (a run_command result with exit_code 0
    after the last edit). Splits "checked" from "verified". Target-specific
    verification (did THE test pass) stays scenario-side (verify_command).

    Args:
        history: transcript conversation_history.

    Returns:
        True when a post-edit verification demonstrably succeeded.
    """
    sequence = _extract_action_sequence(history)
    edits = [
        i
        for i, (name, _) in enumerate(sequence)
        if name in ("edit_file", "write_file", "replace_in_file", "replace_function")
    ]
    if not edits:
        return False
    # Map the last edit to its history position: find the last assistant
    # summary that actually contains an edit action (summaries cover whole
    # turns, so sequence indices do not align with history indices).
    edit_names = {"edit_file", "write_file", "replace_in_file", "replace_function"}
    boundary = -1
    for i, m in enumerate(history):
        if m.get("role") != "assistant":
            continue
        names = {n for n, _ in _extract_action_sequence([m])}
        if names & edit_names:
            boundary = i
    if boundary < 0:
        return False
    # Within-turn ordering: a success counts only if its result message comes
    # AFTER the last edit's own result message. Find the last user message
    # carrying an edit result, then require a successful run_command later.
    edit_result_idx = -1
    for i, m in enumerate(history):
        if m.get("role") != "user":
            continue
        content = m.get("content", "")
        if "::status" not in content:
            continue
        if any(f"::{name} @" in content for name in edit_names):
            edit_result_idx = i
    if edit_result_idx < 0:
        return False
    for m in history[edit_result_idx + 1 :]:
        content = m.get("content", "")
        if (
            m.get("role") == "user"
            and "run_command" in content
            and "exit_code: 0" in content
        ):
            return True
    return False


def tag_verified_edit(history: list[dict[str, Any]]) -> bool:
    """Detect an edit followed by a verification action (positive marker).

    Verification = run_command / read_file / grep_files after the last edit.
    This is the core loop this project wants to establish, so it is tracked
    as a positive signal rather than a failure. See tag_verified_edit_success
    for the strict variant requiring evidence of success.

    Args:
        history: transcript conversation_history.

    Returns:
        True when the last edit was followed by verification.
    """
    sequence = _extract_action_sequence(history)
    edits = [
        i
        for i, (name, _) in enumerate(sequence)
        if name in ("edit_file", "write_file", "replace_in_file", "replace_function")
    ]
    if not edits:
        return False
    return any(
        name in ("run_command", "read_file", "grep_files")
        for name, _ in sequence[edits[-1] + 1 :]
    )


def tag_example_contamination(transcript: dict[str, Any]) -> bool:
    """Detect few-shot examples narrated as real history.

    Observed with MiniMax: reasoning claims "the user greeted me" or
    "the user wants a weather app", quoting BASE/PLANNING examples.

    Args:
        transcript: Full transcript dict (uses raw_responses).

    Returns:
        True when example content is treated as real conversation.
    """
    for raw in transcript.get("raw_responses") or []:
        low = raw.lower()
        if "weather app" in low and any(
            p in low
            for p in ("user wants", "user asked", "user said", "ユーザーが", "ユーザーは")
        ):
            return True
        if "greeted" in low and "hello" in low:
            return True
    return False


TAGS: dict[str, Callable[[list[dict[str, Any]]], bool]] = {
    "api_error": tag_api_error,
    "verified_edit": tag_verified_edit,
    "verified_edit_success": tag_verified_edit_success,
    "asked_question": tag_asked_question,
    "rewrote_tests": tag_rewrote_tests,
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
    if tag_plan_only(transcript):
        tags.append("plan_only")
    if tag_false_success(transcript):
        tags.append("false_success")
    if tag_example_contamination(transcript):
        tags.append("example_contamination")
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
        entry["scenario_sha"] = transcript.get("result", {}).get(
            "experiment", {}
        ).get("scenario_sha", "n/a")
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
        shas = sorted({r.get("scenario_sha", "n/a") for r in runs})
        sha_note = f" [sha:{','.join(shas)}]" if len(shas) > 1 else ""
        print(f"{scenario:<24}{len(runs):<6}{passed:<6} {top}{sha_note}")

    # Artifact-pass vs self-verified split: passed by the harness's own
    # verify_command does not imply the agent verified by itself.
    # verified_edit_success marks runs where a post-edit check demonstrably
    # succeeded (exit_code 0); the loose verified_edit is behavior-only.
    verified_pass = sum(
        1
        for r in analysis["runs"]
        if r["passed"] and "verified_edit_success" in r["tags"]
    )
    unverified_pass = sum(
        1
        for r in analysis["runs"]
        if r["passed"] and "verified_edit_success" not in r["tags"]
    )
    print("-" * 72)
    print(
        f"passed with agent self-verification: {verified_pass} | "
        f"passed on harness verification only: {unverified_pass}"
    )

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
