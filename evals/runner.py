"""Live-model evaluation harness for Duckflow.

Scenario-based evaluation that drives the real DuckAgent.run() loop with a
real LLM (OpenRouter by default), records full conversation transcripts as
JSON, and applies optional lightweight mechanical checks.

Usage:
    uv run python -X utf8 evals/runner.py --all
    uv run python -X utf8 evals/runner.py --scenario fix-typo --model qwen/qwen3-30b-a3b --runs 3

Scenarios live in evals/scenarios/*.yaml. Results (transcripts + checks) are
written to evals/results/<scenario_id>/<timestamp>-r<n>/.
"""

import argparse
import asyncio
import json
import logging
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[1]
SCENARIO_DIR = Path(__file__).resolve().parent / "scenarios"


def load_scenarios(paths: list[Path]) -> list[dict[str, Any]]:
    """Load scenario definitions from YAML files.

    Args:
        paths: Scenario YAML file paths.

    Returns:
        List of scenario dicts with at least 'id' and 'task'.
    """
    scenarios = []
    for path in paths:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        data["_path"] = str(path)
        scenarios.append(data)
    return scenarios


def _make_input_provider(inputs: list[str]) -> Callable[[], Any]:
    """Build a get_user_input replacement serving queued inputs.

    Args:
        inputs: Queued inputs (task first, 'exit' last).

    Returns:
        Async callable returning each input in order (matches the awaited
        ui.get_user_input interface).
    """
    queue = list(inputs)

    async def _next_input() -> str:
        """Return the next queued input, or 'exit' when exhausted."""
        if queue:
            return queue.pop(0)
        return "exit"

    return _next_input


def _patch_ui(task: str) -> None:
    """Patch the UI module: scripted input and auto-approval.

    Args:
        task: Scenario task sent as the first user input.
    """
    from companion.ui import ui as ui_instance

    ui_instance.get_user_input = _make_input_provider([task, "exit"])
    ui_instance.request_confirmation = lambda warning: True


def _run_checks(
    checks: list[dict[str, Any]], workspace: Path
) -> list[dict[str, Any]]:
    """Evaluate mechanical checks against the run workspace.

    Supported check types: file_exists, file_not_exists, file_contains,
    file_not_contains.

    Args:
        checks: Check dicts from the scenario YAML.
        workspace: Run workspace root.

    Returns:
        List of {check, passed} results.
    """
    results = []
    for check in checks or []:
        kind = check.get("type")
        path = workspace / check.get("path", "")
        text = check.get("text", "")
        content = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""

        if kind == "file_exists":
            passed = path.exists()
        elif kind == "file_not_exists":
            passed = not path.exists()
        elif kind == "file_contains":
            passed = text in content
        elif kind == "file_not_contains":
            passed = text not in content
        else:
            passed = False

        results.append({"check": check, "passed": passed})
    return results


async def run_scenario(
    scenario: dict[str, Any],
    provider: str,
    model: str,
    run_index: int,
    results_dir: Path,
) -> dict[str, Any]:
    """Execute a single scenario run with a live model.

    Args:
        scenario: Scenario definition dict.
        provider: LLM provider (e.g. 'openrouter').
        model: Model identifier for the provider.
        run_index: 1-based run number within this invocation.
        results_dir: Base results directory.

    Returns:
        Result summary dict (also written as result.json in the run dir).
    """
    from companion.base.llm_client import LLMClient
    from companion.core import DuckAgent
    from companion.tools.file_ops import file_ops

    scenario_id = scenario["id"]
    max_loops = int(scenario.get("max_loops", 15))
    timeout_seconds = float(scenario.get("timeout_seconds", 300))

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_dir = results_dir / scenario_id / f"{timestamp}-r{run_index}"
    run_dir.mkdir(parents=True, exist_ok=True)

    # Workspace lives outside the repo: get_project_tree hides gitignored
    # paths, so a workspace under evals/results/ would appear empty to the
    # agent and corrupt the scenario.
    import tempfile

    workspace_base = Path(tempfile.gettempdir()) / "duckflow-evals"
    workspace = workspace_base / scenario_id / f"{timestamp}-r{run_index}"
    workspace.mkdir(parents=True, exist_ok=True)

    fixture = Path(scenario["_path"]).parent / scenario.get("fixture", "")
    if fixture.is_dir():
        shutil.copytree(fixture, workspace, dirs_exist_ok=True)

    _patch_ui(scenario["task"])
    file_ops.set_workspace_root(str(workspace))

    api_key: str | None = None
    import os

    if provider == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit(
            f"API key for provider '{provider}' is not set. Check .env"
        )

    llm = LLMClient(provider=provider, model=model)
    agent = DuckAgent(llm_client=llm, session_manager=None)

    # core.py recalculates max_loops from the tier profile on every user
    # turn, overriding any direct assignment. Force the scenario budget by
    # pinning calculate_max_loops to the scenario value.
    def _fixed_max_loops(tier_profile: Any = None) -> int:
        """Return the scenario's loop budget unchanged."""
        return max_loops

    agent.pacemaker.calculate_max_loops = _fixed_max_loops  # type: ignore[method-assign]
    agent.pacemaker.max_loops = max_loops

    # Record every raw LLM response for post-hoc heuristic analysis.
    # Failed / empty calls are recorded as "<chat_error: ...>" markers so
    # that turn counts in the log match actual LLM invocations.
    raw_responses: list[str] = []
    _original_chat = llm.chat

    async def _chat_and_record(messages: Any, response_model: Any = None, **kw: Any) -> Any:
        """Call the original chat and archive the raw response or error."""
        try:
            result = await _original_chat(messages, response_model=response_model, **kw)
        except Exception as exc:
            raw_responses.append(f"<chat_error: {type(exc).__name__}: {exc}>")
            raise
        raw = getattr(llm, "last_raw_response", "")
        raw_responses.append(raw if raw else "<empty response>")
        return result

    llm.chat = _chat_and_record  # type: ignore[method-assign]

    # pacemaker.reset() clears loop_count on turn completion; capture the
    # last non-zero value so the metric survives the reset.
    _original_reset = agent.pacemaker.reset
    _last_loop_count = {"value": 0}

    def _reset_and_capture() -> None:
        """Record loop_count, then delegate to the original reset."""
        _last_loop_count["value"] = max(
            _last_loop_count["value"], agent.pacemaker.loop_count
        )
        _original_reset()

    agent.pacemaker.reset = _reset_and_capture

    start = time.monotonic()
    status = "completed"
    try:
        await asyncio.wait_for(agent.run(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        status = "timeout"
        agent.running = False
    duration = time.monotonic() - start

    checks = _run_checks(scenario.get("checks"), workspace)
    passed = status == "completed" and all(c["passed"] for c in checks)

    usage = getattr(llm, "usage_stats", {}) or {}
    result: dict[str, Any] = {
        "scenario_id": scenario_id,
        "provider": provider,
        "model": model,
        "run": run_index,
        "status": status,
        "passed": passed,
        "duration_seconds": round(duration, 1),
        "loops_used": max(
            _last_loop_count["value"], agent.pacemaker.loop_count
        ),
        "max_loops": max_loops,
        "usage": usage,
        "parse_errors": len(agent.state.last_syntax_errors),
        "checks": checks,
        "workspace": str(workspace),
    }

    transcript = {
        "result": result,
        "task": scenario["task"],
        "conversation_history": agent.state.conversation_history,
        "syntax_errors": [
            {
                "error_type": err.error_type,
                "raw_snippet": err.raw_snippet,
                "correction_hint": err.correction_hint,
            }
            for err in agent.state.last_syntax_errors
        ],
        "raw_responses": raw_responses,
        "vitals": agent.state.vitals.model_dump()
        if hasattr(agent.state.vitals, "model_dump")
        else vars(agent.state.vitals),
    }
    (run_dir / "transcript.json").write_text(
        json.dumps(transcript, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (run_dir / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


def print_summary(results: list[dict[str, Any]]) -> None:
    """Print a compact pass/fail summary table for all runs.

    Args:
        results: Result dicts from run_scenario calls.
    """
    print("\n" + "=" * 72)
    print(
        f"{'scenario':<28}{'run':<5}{'status':<11}{'loops':<7}{'sec':<8}{'pass'}"
    )
    print("-" * 72)
    for r in results:
        print(
            f"{r['scenario_id']:<28}{r['run']:<5}{r['status']:<11}"
            f"{r['loops_used']:<7}{r['duration_seconds']:<8}{r['passed']}"
        )
    total = len(results)
    ok = sum(1 for r in results if r["passed"])
    print("-" * 72)
    print(f"pass: {ok}/{total}")


async def main() -> None:
    """Entry point: parse args, run scenarios, write results."""
    parser = argparse.ArgumentParser(description="Duckflow live-model eval runner")
    parser.add_argument(
        "--scenario", action="append", help="Scenario id (repeatable)"
    )
    parser.add_argument("--all", action="store_true", help="Run all scenarios")
    parser.add_argument("--provider", default="openrouter")
    parser.add_argument("--model", default=None, help="Model id (provider-specific)")
    parser.add_argument("--runs", type=int, default=1, help="Runs per scenario")
    parser.add_argument(
        "--results-dir",
        default=str(Path(__file__).resolve().parent / "results"),
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)

    files = sorted(SCENARIO_DIR.glob("*.yaml"))
    scenarios = load_scenarios(files)
    if args.scenario:
        scenarios = [s for s in scenarios if s["id"] in args.scenario]
    if not scenarios:
        parser.error("No scenarios matched. Use --scenario <id> or --all")

    model = args.model
    if not model:
        from companion.config.config_loader import config

        provider_key = f"llm.{args.provider}.model"
        model = config.get(provider_key) or config.get("llm.model")
    if not model:
        parser.error(
            "No model specified. Use --model or set llm.%s.model in duckflow.yaml"
            % args.provider
        )

    results_dir = Path(args.results_dir)
    results: list[dict[str, Any]] = []
    for scenario in scenarios:
        for run_index in range(1, args.runs + 1):
            print(f"\n=== {scenario['id']} run {run_index}/{args.runs} ===")
            result = await run_scenario(
                scenario, args.provider, model, run_index, results_dir
            )
            results.append(result)

    summary_path = results_dir / "summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nsummary: {summary_path}")
    print_summary(results)


if __name__ == "__main__":
    asyncio.run(main())
