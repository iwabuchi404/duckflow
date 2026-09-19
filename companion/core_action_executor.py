"""
Action execution dispatcher extracted from DuckAgent.

Handles the per-action loop: approval checks, tool invocation, error handling,
fail-fast, and conversation history injection.
"""

import logging
import time

from companion.core_action_pipeline import (
    build_fail_fast_history_message,
    build_fail_fast_warning,
    build_investigation_edit_block,
    limit_actions_per_turn,
    filter_known_actions,
    move_terminal_actions_to_end,
    remaining_actions_after,
    should_block_investigation_edit,
    should_fail_fast,
)
from companion.core_action_results import (
    build_action_summary,
    build_action_exception_syntax_error,
    build_denial_context,
    build_dropped_params_syntax_error,
    build_no_progress_syntax_error,
    build_repeated_failure_syntax_error,
    build_tool_result_message,
    get_approval_request,
)
from companion.base.native_protocol import sanitize_tool_references
from companion.core_action_invocation import invoke_tool
from companion.tool_history_policy import compress_for_history
from companion.execution.result_pipeline import summarize_result
from companion.modules.repo_map import get_repo_map_generator
from companion.modules.event_logger import event_logger
from companion.tools.file_ops import file_ops
from pathlib import Path
from companion.tools.results import (
    ToolResult,
    ToolStatus,
    serialize_to_text,
)
from companion.ui import ui

logger = logging.getLogger(__name__)


async def execute_actions(agent, action_list) -> list:
    """Dispatch and execute a list of actions.

    Args:
        agent: DuckAgent instance with tools, state, pacemaker, etc.
        action_list: ActionList to execute.

    Returns:
        List of results from each action.
    """
    logger.info(f"Executing actions: {[a.name for a in action_list.actions]}")
    results = []

    # --- Causal history ordering ---
    # Tool results are user-role messages. If they are appended during
    # execution and the assistant action summary afterwards, the turn ends
    # with the model's own summary — inviting the model to continue writing
    # (e.g. fabricating further results). Instead, buffer user-role messages
    # and flush them AFTER the summary, so history ends with the latest tool
    # result: call → result order.
    pending_user_messages: list[str] = []
    history_flushed = False

    def _queue_user_message(content: str) -> None:
        """Buffer a user-role history message for end-of-turn flush."""
        pending_user_messages.append(content)

    def _flush_history() -> None:
        """Write summary first, then buffered results in execution order."""
        nonlocal history_flushed
        if history_flushed:
            return
        history_flushed = True
        action_summary = build_action_summary(action_list)
        # Stamp the native turn id so history rebuild pairs this summary
        # with the correct verbatim assistant log entry by identity
        # instead of position (stable across task resets, pruning, and
        # non-LLM forced executions).
        turn = next(
            (
                a.native_turn
                for a in action_list.actions
                if getattr(a, "native_turn", None)
            ),
            None,
        ) or next(
            (
                a.native_turn
                for a in proposed_actions
                if getattr(a, "native_turn", None)
            ),
            None,
        )
        if not action_summary and turn is not None:
            # Every proposed call was filtered/dropped before execution,
            # leaving no action lines. Still anchor the turn so its
            # journal results reach the rebuilt native history.
            action_summary = ":: (all proposed actions filtered)"
        if action_summary:
            agent.state.add_message("assistant", action_summary)
            if turn is not None:
                agent.state.conversation_history[-1]["_native_turn"] = turn
        for content in pending_user_messages:
            agent.state.add_message("user", content)

    mode_val = agent.state.current_mode.value if agent.state.current_mode else None
    if mode_val and mode_val in agent.MODE_TOOL_MAPPING:
        mode_tools = agent.UNIVERSAL_TOOLS | agent.MODE_TOOL_MAPPING[mode_val]
    else:
        mode_tools = agent.UNIVERSAL_TOOLS

    # Snapshot the proposed actions before filter/limit mutations so every
    # native tool_call can be accounted for in the execution journal — an
    # unrecorded call would reach the API as an orphaned tool_call.
    proposed_actions = list(action_list.actions)
    recorded_call_ids: set = set()

    def _record_native_event(action, status, executed, body) -> None:
        """Record a native tool-call outcome for ID-based history rebuild.

        No-op for actions without a tool_call_id (Sym-Ops path and
        text-derived control actions).
        """
        call_id = getattr(action, "tool_call_id", None)
        if not call_id:
            return
        recorded_call_ids.add(call_id)
        record = getattr(agent.llm, "record_native_event", None)
        if callable(record):
            # Tool-result bodies were written for the Sym-Ops surface and
            # may embed "::name @target" guidance; rewrite those references
            # so the native model is not taught to emit Sym-Ops text.
            record(
                call_id,
                action.name,
                status,
                executed,
                sanitize_tool_references(str(body)),
            )

    # filter_known_actions removes unknown actions in place, so the
    # pre-filter snapshot is what identifies which calls were dropped.
    removed_tools = filter_known_actions(
        action_list,
        agent.tools.keys(),
        mode_tools,
        agent.state.last_syntax_errors,
    )
    removed_names = set(removed_tools)
    for tool_name in removed_tools:
        ui.print_warning(f"Unknown tool '{tool_name}' was ignored.")
    for action in proposed_actions:
        if action.name in removed_names:
            _record_native_event(
                action,
                "filtered",
                False,
                f"Unknown or unavailable tool '{action.name}' was ignored.",
            )

    # --- Action Count Limiter ---
    pre_limit_actions = list(action_list.actions)
    dropped = limit_actions_per_turn(action_list)
    if dropped:
        ui.print_warning(
            f"アクション数が上限(6)を超えたため、末尾{dropped}件を切り捨てました。"
        )
        for action in pre_limit_actions[len(pre_limit_actions) - dropped :]:
            _record_native_event(
                action,
                "dropped",
                False,
                "Not executed: exceeded the per-turn action limit.",
            )

    # --- Fail-fast: consecutive error counter ---
    consecutive_errors = 0

    # Move terminal actions to the end
    move_terminal_actions_to_end(action_list)

    def _handle_error(action, error_content, t0, t1, executed=True):
        """Record a tool/action error, update history, and check fail-fast."""
        nonlocal consecutive_errors
        _record_native_event(action, "error", executed, str(error_content))
        error_msg = f"Action '{action.name}' failed: {error_content}"
        logger.error(error_msg)
        agent.state.last_action_result = error_msg
        ui.print_result(str(error_content), is_error=True)

        _queue_user_message(
            build_tool_result_message(action, error_content, status=ToolStatus.ERROR),
        )

        results.append(error_msg)

        agent.pacemaker.update_vitals(action, error_msg, is_error=True)

        # Escalate the Correction Guide when this call/error kind keeps
        # failing across turns — the standard one-turn hint is being
        # ignored (observed: GLM resent an empty-body edit_file 6x).
        repeat_n = agent.pacemaker.repeat_escalation_count(action)
        if repeat_n:
            agent.state.last_syntax_errors.append(
                build_repeated_failure_syntax_error(action, repeat_n)
            )

        dur_ms = (t1 - t0) * 1000
        agent.timeline.record(
            action_name=action.name,
            start_ts=t0,
            end_ts=t1,
            is_error=True,
            result_summary=error_msg,
        )
        event_logger.log_action_end(
            action.name,
            dur_ms,
            is_error=True,
            result_len=len(error_msg),
        )

        consecutive_errors += 1
        if should_fail_fast(consecutive_errors):
            remaining = remaining_actions_after(action_list, action)
            if remaining > 0:
                logger.warning(
                    f"Fail-fast: {consecutive_errors} consecutive errors, aborting {remaining} remaining actions"
                )
                ui.print_warning(build_fail_fast_warning(consecutive_errors, remaining))
                _queue_user_message(
                    build_fail_fast_history_message(consecutive_errors, remaining),
                )
            return True
        return False

    try:
        for action in action_list.actions:
            ui.print_action(action.name, action.parameters, action.thought)

            # --- Skip auto-generated responses ---
            # Repair fallbacks (bare <<<>>> blocks, thought-only output) create
            # response actions the model never explicitly chose. Executing them
            # would show unintended content to the user; the loop-level guard
            # (should_return_to_user) asks for an explicit action instead.
            if action.name == "response" and getattr(action, "auto_generated", False):
                logger.warning(
                    "Skipping auto-generated ::response (not model-explicit)."
                )
                results.append(
                    "[SKIPPED] auto-generated response (awaiting explicit action)"
                )
                continue

            # --- Skip redundant mode-switch actions ---
            # If already in the target mode, skip the mode-switch action
            # to prevent loops where LLM repeatedly calls ::investigate.
            _current_mode = agent.state.get_context_mode()
            if action.name == "investigate" and _current_mode == "investigation":
                logger.warning("Skipping investigate: already in investigation mode")
                ui.print_warning(
                    "investigate: 既にInvestigation Modeです。::read_file等で観察してください"
                )
                _record_native_event(
                    action,
                    "skipped",
                    False,
                    "Already in investigation mode; observe with read_file instead.",
                )
                continue

            # --- Investigation Mode Guard ---
            # Investigation mode is read-only. File mutations are blocked and
            # reported as syntax feedback so the agent explicitly closes
            # investigation with ::finish_investigation before editing.
            if should_block_investigation_edit(action, agent.state.get_context_mode()):
                logger.info(
                    f"Blocking {action.name}: file mutations are not allowed "
                    f"during Investigation Mode"
                )
                block = build_investigation_edit_block(action)
                _record_native_event(action, "blocked", False, block.message)
                agent.state.last_syntax_errors.append(block.syntax_error)
                _queue_user_message(
                    build_tool_result_message(
                        action, block.message, status=ToolStatus.ERROR
                    ),
                )
                agent.pacemaker.update_vitals(action, block.message, is_error=True)
                results.append(block.message)
                continue

            # --- Repeated identical-failure block ---
            # A verbatim repeat of a call that already failed with a
            # contract (format/permission) error is deterministically
            # doomed — refuse it before execution so the model cannot
            # burn turns resending the same malformed call. Recorded as
            # an error so persistent repeats still feed the cascade.
            repeat_refusal = agent.pacemaker.check_repeat_block(action)
            if repeat_refusal is not None:
                logger.warning(
                    f"Blocked doomed repeat of '{action.name}' "
                    f"({agent.pacemaker.repeated_call_count(action)} prior failures)"
                )
                _record_native_event(action, "blocked", False, repeat_refusal)
                agent.state.last_syntax_errors.append(
                    build_repeated_failure_syntax_error(
                        action, agent.pacemaker.repeated_call_count(action)
                    )
                )
                _queue_user_message(
                    build_tool_result_message(
                        action, repeat_refusal, status=ToolStatus.ERROR
                    ),
                )
                agent.pacemaker.update_vitals(action, repeat_refusal, is_error=True)
                results.append(repeat_refusal)
                continue

            # --- No-progress stall gate ---
            # Planning/bookkeeping churn that produces no observable
            # change is refused once the streak crosses the funnel
            # threshold — the refusal names the three exits (concrete
            # action, ::response report, ::duck_call question). Blocked
            # attempts count as errors so persistent churn still feeds
            # the cascade/no-progress machinery.
            stall_refusal = agent.pacemaker.check_stall_block(action)
            if stall_refusal is not None:
                logger.warning(
                    f"Blocked meta-action churn '{action.name}' "
                    f"(streak={agent.pacemaker.meta_streak})"
                )
                _record_native_event(action, "blocked", False, stall_refusal)
                agent.state.last_syntax_errors.append(
                    build_no_progress_syntax_error(action, agent.pacemaker.meta_streak)
                )
                _queue_user_message(
                    build_tool_result_message(
                        action, stall_refusal, status=ToolStatus.ERROR
                    ),
                )
                agent.pacemaker.update_vitals(action, stall_refusal, is_error=True)
                results.append(stall_refusal)
                continue

            # --- Approval Check ---
            was_approved = False
            approval_request = get_approval_request(action, file_ops.file_exists)

            if approval_request.required:
                if not ui.request_confirmation(approval_request.warning):
                    msg = f"Action '{action.name}' denied by user."
                    ui.print_result(msg, is_error=True)
                    agent.state.last_action_result = msg

                    denial_context = build_denial_context(
                        action, approval_request.warning
                    )
                    _record_native_event(action, "denied", False, denial_context)
                    _queue_user_message(
                        denial_context,
                    )

                    agent.pacemaker.update_vitals(action, msg, is_error=True)

                    results.append(msg)
                    continue
                else:
                    was_approved = True
                    logger.info(f"User approved action: {action.name}")

            _t0 = time.monotonic()

            if action.name in agent.tools:
                try:
                    func = agent.tools[action.name]
                    logger.info(f"Calling tool: {action.name}")
                    event_logger.log_action_start(action.name, action.parameters)

                    raw_result, dropped_params = await invoke_tool(
                        func, action.parameters, tool_name=action.name
                    )
                    _t1 = time.monotonic()

                    if dropped_params:
                        logger.warning(
                            f"Tool '{action.name}': dropping unexpected params: {dropped_params}"
                        )
                        agent.state.last_syntax_errors.append(
                            build_dropped_params_syntax_error(
                                action, dropped_params, func
                            )
                        )

                    # Tool implementations may return ToolResult objects directly. Plain
                    # strings / dicts are treated as successful results.
                    if isinstance(raw_result, ToolResult):
                        result_status = raw_result.status
                        result = raw_result.content
                    else:
                        result_status = ToolStatus.OK
                        result = raw_result

                    logger.info(
                        f"Tool {action.name} returned. status={result_status.value}, length={len(str(result))}"
                    )

                    if result_status == ToolStatus.ERROR:
                        if _handle_error(action, result, _t0, _t1):
                            break
                        continue

                    agent.state.last_action_result = (
                        f"Action '{action.name}' succeeded: {result}"
                    )

                    if action.name not in ("response",):
                        # Multi-stage summarization pipeline (S3-1)
                        result_str = (
                            result
                            if isinstance(result, str)
                            else serialize_to_text(result)
                        )
                        history_content, _cache_id = summarize_result(
                            action.name, result_str, agent
                        )

                        _record_native_event(
                            action, "ok", True, history_content or result_str
                        )
                        _queue_user_message(
                            build_tool_result_message(
                                action,
                                result,
                                status=ToolStatus.OK,
                                approved=was_approved,
                                history_content=history_content,
                            ),
                        )

                        if isinstance(result, str):
                            ui.print_result(result)
                        else:
                            ui.print_result(serialize_to_text(result))

                    results.append(result)

                    # Invalidate repo map cache for file-modifying actions
                    if action.name in (
                        "write_file",
                        "edit_file",
                        "delete_file",
                        "delete_lines",
                    ):
                        file_path = action.parameters.get("path", "")
                        if file_path:
                            try:
                                gen = get_repo_map_generator()
                                rel = str(Path(file_path)).replace("\\", "/")
                                gen.invalidate(rel)
                            except Exception:
                                pass  # Best-effort, don't block execution

                    agent.pacemaker.update_vitals(action, result, is_error=False)
                    consecutive_errors = 0

                    # Stall gate stage 1: warn via Correction Guide when
                    # bookkeeping churn reaches the notify threshold —
                    # one streak step later it is refused outright.
                    stall_n = agent.pacemaker.stall_escalation_count(action)
                    if stall_n:
                        agent.state.last_syntax_errors.append(
                            build_no_progress_syntax_error(action, stall_n)
                        )

                    _dur_ms = (_t1 - _t0) * 1000
                    _result_str = str(result)
                    agent.timeline.record(
                        action_name=action.name,
                        start_ts=_t0,
                        end_ts=_t1,
                        is_error=False,
                        result_summary=_result_str,
                    )
                    event_logger.log_action_end(
                        action.name,
                        _dur_ms,
                        is_error=False,
                        result_len=len(_result_str),
                    )

                except Exception as e:
                    logger.error(f"Action '{action.name}' failed: {e}", exc_info=True)

                    syntax_error = build_action_exception_syntax_error(action, e)
                    if syntax_error is not None:
                        agent.state.last_syntax_errors.append(syntax_error)

                    if _handle_error(action, e, _t0, time.monotonic()):
                        break
            else:
                msg = f"Unknown tool: {action.name}"
                logger.warning(msg)
                agent.state.last_action_result = msg
                ui.print_result(msg, is_error=True)

                available_tools = ", ".join(agent.tools.keys())
                error_content = (
                    f"Tool '{action.name}' does not exist. "
                    f"Available tools: {available_tools}. "
                    f"Please use one of the available tools."
                )
                if _handle_error(
                    action, error_content, _t0, time.monotonic(), executed=False
                ):
                    break
    except KeyboardInterrupt:
        ui.print_warning("Execution interrupted by user.")
        _queue_user_message(
            "[System: Execution was interrupted by the user (Ctrl+C). Please wait for new instructions.]",
        )

    # Account for calls that never reached a record point (fail-fast
    # break, interruption) so no tool_call is left unanswered in the
    # rebuilt native history.
    for action in proposed_actions:
        call_id = getattr(action, "tool_call_id", None)
        if call_id and call_id not in recorded_call_ids:
            _record_native_event(
                action,
                "skipped",
                False,
                "Not executed: the turn was aborted before this call ran.",
            )

    _flush_history()

    if ui:
        ui.print_token_usage(agent.llm.usage_stats)

    logger.info("Finished executing actions")
    return results
