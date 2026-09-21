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
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[1]
SCENARIO_DIR = Path(__file__).resolve().parent / "scenarios"


def _load_yaml_no_duplicates(path: Path) -> dict[str, Any]:
    """Load a YAML file, rejecting duplicate keys.

    PyYAML silently keeps the last of duplicated keys, which hides editing
    mistakes in scenario files (e.g. two verify_command entries).

    Args:
        path: YAML file path.

    Returns:
        Parsed content.

    Raises:
        ValueError: On duplicate keys.
    """

    class _UniqueLoader(yaml.SafeLoader):
        pass

    def _construct_mapping(loader, node, deep=False):
        seen: set[str] = set()
        for key_node, _ in node.value:
            key = loader.construct_object(key_node, deep=True)
            if key in seen:
                raise ValueError(f"Duplicate key {key!r} in {path}")
            seen.add(key)
        return yaml.constructor.SafeConstructor.construct_mapping(loader, node, deep)

    _UniqueLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
    )
    with open(path, encoding="utf-8") as f:
        return yaml.load(f, Loader=_UniqueLoader)


def load_scenarios(paths: list[Path]) -> list[dict[str, Any]]:
    """Load scenario definitions from YAML files.

    Args:
        paths: Scenario YAML file paths.

    Returns:
        List of scenario dicts with at least 'id' and 'task'.
    """
    scenarios = []
    for path in paths:
        data = _load_yaml_no_duplicates(path)
        data["_path"] = str(path)
        scenarios.append(data)
    return scenarios


def _make_input_provider(
    task: str,
    follow_ups: list[str] | None,
    user_script: list[str] | None,
    agent_ref: dict[str, Any],
    script_after_question: bool = False,
) -> Callable[[], Any]:
    """Build a get_user_input replacement with scripted user behavior.

    Serves the task first, then unconditional user_script lines (for
    collaboration scenarios where the user answers questions), then
    plan-conditional follow-ups, then exit.

    Args:
        task: Scenario task sent as the first user input.
        follow_ups: Follow-up inputs for plan-presentation turns.
        user_script: Unconditional follow-up inputs, in order.
        agent_ref: Mutable dict holding the agent under key "agent"; filled
            in later by run_scenario once the agent exists.
        script_after_question: When True, serve script lines only while the
            agent awaits user input after a question (duck_call phase).

    Returns:
        Async callable returning the next input.
    """
    from evals.analysis import looks_like_plan

    queue = [task]
    script = list(user_script or [])
    # Copy per provider: pop() below must not drain the scenario dict's
    # shared list, or runs after the first would silently get no
    # follow-up inputs.
    follow_ups = list(follow_ups or [])

    async def _next_input() -> str:
        """Return the next scripted input, with plan-aware follow-ups."""
        if queue:
            return queue.pop(0)
        if script:
            # For question-scenarios (script_after_question), serve the
            # scripted answer while the agent is awaiting user input after
            # a duck_call pause, or when its latest message asks a question
            # via ::response. Otherwise the agent guessed without asking
            # and the run should end.
            if script_after_question:
                agent = agent_ref.get("agent")
                from companion.state.agent_state import AgentPhase

                awaiting = (
                    agent is not None and agent.state.phase == AgentPhase.AWAITING_USER
                )
                if not awaiting and agent is not None:
                    recent = [
                        m["content"]
                        for m in agent.state.conversation_history
                        if m.get("role") == "assistant"
                    ][-2:]
                    awaiting = any("?" in c or "？" in c for c in recent)
                if not awaiting:
                    return "exit"
            return script.pop(0)
        if follow_ups:
            agent = agent_ref.get("agent")
            if agent is not None:
                assistants = [
                    m["content"]
                    for m in agent.state.conversation_history
                    if m.get("role") == "assistant"
                ]
                # The response text is stored as its own assistant message,
                # separate from the action summary appended after it.
                if any(looks_like_plan(c) for c in assistants[-3:]):
                    return follow_ups.pop(0)
                # A structured plan via propose_plan lives in state, not in
                # message text. Treat an existing stepped plan as a presented
                # plan awaiting user go-ahead.
                plan = getattr(agent.state, "current_plan", None)
                if plan is not None and getattr(plan, "steps", []):
                    return follow_ups.pop(0)
        return "exit"

    return _next_input


def _patch_ui(
    task: str,
    follow_ups: list[str] | None,
    user_script: list[str] | None,
    agent_ref: dict[str, Any],
    script_after_question: bool = False,
) -> None:
    """Patch the UI module: scripted input and auto-approval.

    Args:
        task: Scenario task sent as the first user input.
        follow_ups: Follow-up inputs for plan-presentation turns.
        user_script: Unconditional follow-up inputs, in order.
        agent_ref: Mutable dict receiving the agent instance.
        script_after_question: Serve script only after a question.
    """
    from companion.ui import ui as ui_instance

    ui_instance.get_user_input = _make_input_provider(
        task, follow_ups, user_script, agent_ref, script_after_question
    )
    ui_instance.request_confirmation = lambda warning: True


def _ensure_clean_env(fixture: Path | None) -> None:
    """Uninstall packages declared in fixture/requirements.txt before each run.

    Scenarios that rely on a missing dependency being installed during the
    run (e.g. recover-quad) lose their failure condition if a previous run
    left the package installed in the shared Python environment. This reset
    keeps every run independent.

    Args:
        fixture: Fixture directory for the scenario.
    """
    if not fixture:
        return
    req_path = fixture / "requirements.txt"
    if not req_path.is_file():
        return
    packages = [
        line.strip()
        for line in req_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    for pkg in packages:
        pkg_name = pkg.split("=")[0].split(">")[0].split("<")[0].strip()
        if not pkg_name:
            continue
        show = subprocess.run(
            [sys.executable, "-m", "pip", "show", pkg_name],
            capture_output=True,
            text=True,
        )
        if show.returncode != 0:
            continue
        result = subprocess.run(
            [sys.executable, "-m", "pip", "uninstall", "-y", pkg_name],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.warning(f"Failed to uninstall {pkg_name}: {result.stderr}")


_WORKSPACE_DIFF_IGNORE = {"__pycache__", ".pytest_cache"}


def _workspace_matches_fixture(workspace: Path, fixture: Path | None) -> bool:
    """Compare an entire workspace tree against its fixture, byte for byte.

    Used by ``workspace_unmodified`` checks for scenarios whose correct
    outcome is "change nothing" (e.g. a reported bug that turns out to be
    intended behavior). Any modified, new, or deleted file fails the check,
    except generated noise (``__pycache__``, ``.pytest_cache``, ``*.pyc``)
    that pytest/Python creates merely by running the verification command.

    Args:
        workspace: Run workspace root.
        fixture: Fixture directory the workspace was copied from.

    Returns:
        True when the trees are identical apart from ignored entries.
    """
    import filecmp

    if fixture is None or not fixture.is_dir():
        return False

    def _ignored(name: str) -> bool:
        return name in _WORKSPACE_DIFF_IGNORE or name.endswith(".pyc")

    def _walk(root: Path) -> dict[str, Path]:
        files: dict[str, Path] = {}
        for path in sorted(root.rglob("*")):
            rel = path.relative_to(root)
            if any(_ignored(part) for part in rel.parts):
                continue
            if path.is_file():
                files[str(rel)] = path
        return files

    fixture_files = _walk(fixture)
    workspace_files = _walk(workspace)
    if set(fixture_files) != set(workspace_files):
        return False
    return all(
        filecmp.cmp(str(fixture_files[rel]), str(workspace_files[rel]), shallow=False)
        for rel in fixture_files
    )


def _last_report_text(history: list[dict[str, Any]] | None) -> str:
    """Extract the last assistant prose message (the final report).

    In transcripts the ::response message is stored as its own assistant
    message separate from the action summary, so the report is the last
    assistant message that is not a bare action marker. Runs that ended
    via duck_call/exit have a question (or nothing) here, which lets
    ``report_contains`` distinguish a real report from a vacuous exit.

    Args:
        history: Agent conversation history (may be None).

    Returns:
        The last prose assistant message, or "" when none exists.
    """
    for m in reversed(history or []):
        if m.get("role") != "assistant":
            continue
        content = str(m.get("content", "")).strip()
        if not content or content.startswith("::"):
            continue
        return content
    return ""


def _run_checks(
    checks: list[dict[str, Any]],
    workspace: Path,
    fixture: Path | None = None,
    history: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Evaluate mechanical checks against the run workspace.

    Supported check types: file_exists, file_not_exists, file_contains,
    file_not_contains, unmodified (byte-identical to the fixture file),
    workspace_unmodified (whole tree byte-identical to the fixture, ignoring
    __pycache__/.pytest_cache/*.pyc), report_contains (any of the given
    `texts` appears in the final assistant report — fails when the run
    ended without a report, e.g. mid-question exit).

    Args:
        checks: Check dicts from the scenario YAML.
        workspace: Run workspace root.
        fixture: Fixture directory (required for unmodified checks).
        history: Conversation history (required for report_contains).

    Returns:
        List of {check, passed} results.
    """
    import hashlib

    results = []
    for check in checks or []:
        kind = check.get("type")
        path = workspace / check.get("path", "")
        text = check.get("text", "")
        content = (
            path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
        )

        if kind == "file_exists":
            passed = path.exists()
        elif kind == "file_not_exists":
            passed = not path.exists()
        elif kind == "file_contains":
            passed = text in content
        elif kind == "file_not_contains":
            passed = text not in content
        elif kind == "unmodified":
            original = fixture / check.get("path", "") if fixture else None
            passed = (
                original is not None
                and original.is_file()
                and path.is_file()
                and hashlib.sha256(path.read_bytes()).hexdigest()
                == hashlib.sha256(original.read_bytes()).hexdigest()
            )
        elif kind == "workspace_unmodified":
            passed = _workspace_matches_fixture(workspace, fixture)
        elif kind == "report_contains":
            report = _last_report_text(history)
            texts = check.get("texts") or [check.get("text", "")]
            passed = bool(report) and any(t in report for t in texts if t)
        else:
            passed = False

        results.append({"check": check, "passed": passed})
    return results


def _run_verify_command(command: str, workspace: Path) -> dict[str, Any]:
    """Execute a scenario verification command inside the workspace.

    Args:
        command: Command string run with cwd=workspace.
        workspace: Run workspace root.

    Returns:
        Check result dict in the same shape as _run_checks entries.
    """
    import sys as _sys

    command = command.replace("{python}", f'"{_sys.executable}"')
    # NOTE: do NOT use text=True — console output may mix encodings
    # (e.g. pytest echoing CP932 docstrings); decode defensively instead.
    proc = subprocess.run(
        command,
        shell=True,
        cwd=str(workspace),
        capture_output=True,
        timeout=120,
    )
    stdout = proc.stdout.decode("utf-8", errors="replace") if proc.stdout else ""
    stderr = proc.stderr.decode("utf-8", errors="replace") if proc.stderr else ""
    passed = proc.returncode == 0
    detail = "" if passed else (stdout + stderr)[-500:]
    return {
        "check": {"type": "command_exit_zero", "command": command},
        "passed": passed,
        "detail": detail,
    }


def _collect_experiment_meta(scenario: dict[str, Any]) -> dict[str, Any]:
    """Record the exact experiment conditions for reproducibility.

    Captures git commit, uncommitted diff stat, model/provider settings,
    few-shot framing, and a hash of the scenario definition. Comparisons
    across runs are only valid when these match.

    Args:
        scenario: Scenario definition dict.

    Returns:
        Metadata dict stored in result.json and transcript.json.
    """
    import hashlib
    import subprocess

    meta: dict[str, Any] = {}
    try:
        meta["git_commit"] = (
            subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(REPO_ROOT),
            ).stdout.strip()
            or "unknown"
        )
        meta["git_dirty"] = (
            subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(REPO_ROOT),
            ).stdout.strip()
            or ""
        )
    except Exception:
        meta["git_commit"] = "unknown"
        meta["git_dirty"] = "unknown"
    from companion.prompts.few_shot import get_effective_framing
    from companion.prompts.builder import interpretation_gate_enabled
    from companion.decision import decision_engine_enabled

    meta["few_shot_framing"] = get_effective_framing()
    # Experiment circuit: records whether the Interpretation Gate block
    # was injected so A/B comparisons stay honest.
    meta["interpretation_gate"] = interpretation_gate_enabled()
    # H-1 experiment: records whether the Decision Engine entry gate was
    # active (Pacemaker → Context Compiler → SameModel binary decision).
    meta["decision_engine"] = decision_engine_enabled()
    try:
        from companion.config.config_loader import config as _cfg

        meta["llm_settings"] = {
            "temperature": _cfg.get("llm.temperature"),
            "top_p": _cfg.get("llm.top_p"),
            "max_output_tokens": _cfg.get("llm.max_output_tokens"),
            "reasoning": _cfg.get("llm.reasoning"),
        }
    except Exception:
        meta["llm_settings"] = "unknown"
    scenario_text = json.dumps(
        {k: v for k, v in scenario.items() if not k.startswith("_")},
        ensure_ascii=False,
        sort_keys=True,
    )
    meta["scenario_id"] = scenario.get("id")
    meta["scenario_sha"] = hashlib.sha256(scenario_text.encode("utf-8")).hexdigest()[
        :12
    ]
    # Snapshot the resolved scenario so each run's exact conditions
    # (follow-ups, checks, verify command) are recoverable without
    # consulting the current YAML, which may have drifted since the run.
    meta["scenario"] = json.loads(scenario_text)
    flag = scenario.get("expects_question")
    meta["expects_question"] = flag if isinstance(flag, bool) else None
    import os as _os

    from companion.base.native_protocol import resolve_protocol

    meta["tool_protocol"] = _os.getenv("DUCKFLOW_TOOL_PROTOCOL") or resolve_protocol()
    return meta


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

    # Use microsecond + pid in the run name so parallel invocations (or
    # async/concurrent callers) never share a workspace, even if they start
    # in the same second with the same run_index.
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    run_name = f"{timestamp}-r{run_index}-{os.getpid()}"
    run_dir = results_dir / scenario_id / run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    # Workspace lives outside the repo: get_project_tree hides gitignored
    # paths, so a workspace under evals/results/ would appear empty to the
    # agent and corrupt the scenario.
    import tempfile

    workspace_base = Path(tempfile.gettempdir()) / "duckflow-evals"
    workspace = workspace_base / scenario_id / run_name
    workspace.mkdir(parents=True, exist_ok=True)

    fixture = Path(scenario["_path"]).parent / scenario.get("fixture", "")
    if fixture.is_dir():
        shutil.copytree(
            fixture,
            workspace,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )

    # Reset any dependency that a previous run may have installed, so
    # scenarios that require the agent to discover and install a missing
    # package start from the intended failure state every time.
    _ensure_clean_env(fixture)

    agent_ref: dict[str, Any] = {}
    _patch_ui(
        scenario["task"],
        scenario.get("follow_up_inputs"),
        scenario.get("user_script"),
        agent_ref,
        bool(scenario.get("script_after_question", False)),
    )
    file_ops.set_workspace_root(str(workspace))

    # Align every workspace-root consumer with the run workspace.
    # AgentState.working_directory feeds the repo map prompt injection, and
    # the repo map generator is a process-wide singleton that keeps the first
    # root it sees — without a reset, eval prompts would describe the
    # duckflow repo itself instead of the scenario workspace.
    import companion.modules.repo_map as repo_map_module

    repo_map_module._repo_map_generator = None
    repo_map_module.get_repo_map_generator(str(workspace))

    api_key: str | None = None

    if provider == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit(f"API key for provider '{provider}' is not set. Check .env")

    llm = LLMClient(provider=provider, model=model)
    agent = DuckAgent(llm_client=llm, session_manager=None)
    agent_ref["agent"] = agent
    agent.state.working_directory = str(workspace)

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
    # llm_calls stores the exact sent messages + generation settings per
    # call (with an input hash) so replay can resend them verbatim.
    import hashlib as _hashlib

    raw_responses: list[str] = []
    llm_calls: list[dict[str, Any]] = []
    _original_chat = llm.chat

    async def _chat_and_record(
        messages: Any, response_model: Any = None, **kw: Any
    ) -> Any:
        """Call the original chat and archive the raw response or error."""
        try:
            result = await _original_chat(messages, response_model=response_model, **kw)
        except Exception as exc:
            raw_responses.append(f"<chat_error: {type(exc).__name__}: {exc}>")
            raise
        raw = getattr(llm, "last_raw_response", "")
        raw_responses.append(raw if raw else "<empty response>")
        try:
            dumped = json.dumps(messages, ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError):
            dumped = str(messages)
        # Resolve effective generation settings: explicit kwargs win,
        # otherwise fall back to configured defaults (never store nulls —
        # replay must reproduce the actual conditions).
        settings: dict[str, Any] = {
            "temperature": kw.get("temperature"),
            "max_tokens": kw.get("max_tokens"),
        }
        try:
            from companion.config.config_loader import config as _cfg

            if settings["temperature"] is None:
                settings["temperature"] = _cfg.get("llm.temperature")
            if settings["max_tokens"] is None:
                settings["max_tokens"] = _cfg.get("llm.max_output_tokens")
            settings["reasoning"] = _cfg.get("llm.reasoning")
        except Exception:
            pass
        llm_calls.append(
            {
                "messages": messages,
                "response_model": getattr(
                    response_model, "__name__", str(response_model)
                ),
                "settings": settings,
                "input_sha": _hashlib.sha256(dumped.encode("utf-8")).hexdigest()[:16],
            }
        )
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

    fixture_dir = Path(scenario["_path"]).parent / scenario.get("fixture", "")
    checks = _run_checks(
        scenario.get("checks"),
        workspace,
        fixture=fixture_dir if fixture_dir.is_dir() else None,
        history=agent.state.conversation_history,
    )
    verify_command = scenario.get("verify_command")
    if verify_command:
        try:
            checks.append(_run_verify_command(verify_command, workspace))
        except subprocess.TimeoutExpired:
            checks.append(
                {
                    "check": {
                        "type": "command_exit_zero",
                        "command": verify_command,
                    },
                    "passed": False,
                    "detail": "verify command timed out",
                }
            )
    passed = status == "completed" and all(c["passed"] for c in checks)

    usage = getattr(llm, "usage_stats", {}) or {}
    result: dict[str, Any] = {
        "scenario_id": scenario_id,
        "provider": provider,
        "model": model,
        "experiment": _collect_experiment_meta(scenario),
        "run": run_index,
        "status": status,
        "passed": passed,
        "duration_seconds": round(duration, 1),
        "loops_used": max(_last_loop_count["value"], agent.pacemaker.loop_count),
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
        "llm_calls": llm_calls,
        "decisions": list(getattr(agent, "decision_log", []) or []),
        "vitals": (
            agent.state.vitals.model_dump()
            if hasattr(agent.state.vitals, "model_dump")
            else vars(agent.state.vitals)
        ),
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
    print(f"{'scenario':<28}{'run':<5}{'status':<11}{'loops':<7}{'sec':<8}{'pass'}")
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
    parser.add_argument("--scenario", action="append", help="Scenario id (repeatable)")
    parser.add_argument("--all", action="store_true", help="Run all scenarios")
    parser.add_argument("--provider", default="openrouter")
    parser.add_argument("--model", default=None, help="Model id (provider-specific)")
    parser.add_argument("--runs", type=int, default=1, help="Runs per scenario")
    parser.add_argument(
        "--few-shot",
        choices=["bare", "framed", "minimal"],
        default=None,
        help="Few-shot example framing experiment switch "
        "(sets DUCKFLOW_FEW_SHOT_FRAMING; default keeps current behavior)",
    )
    parser.add_argument(
        "--tool-protocol",
        choices=["symops", "native"],
        default=None,
        help="Tool protocol experiment switch "
        "(sets DUCKFLOW_TOOL_PROTOCOL; default keeps current behavior)",
    )
    parser.add_argument(
        "--results-dir",
        default=str(Path(__file__).resolve().parent / "results"),
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)

    # NOTE: --all covers only the top-level Quick set. Gauntlet scenarios
    # live in subdirectories (e.g. scenarios/gauntlet/) and run only when
    # named explicitly, so routine runs never pick them up by accident.
    if args.scenario:
        files = sorted(SCENARIO_DIR.rglob("*.yaml"))
    else:
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
            f"No model specified. Use --model or set llm.{args.provider}.model in duckflow.yaml"
        )

    results_dir = Path(args.results_dir)
    if args.few_shot:
        os.environ["DUCKFLOW_FEW_SHOT_FRAMING"] = args.few_shot
    if args.tool_protocol:
        os.environ["DUCKFLOW_TOOL_PROTOCOL"] = args.tool_protocol
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
