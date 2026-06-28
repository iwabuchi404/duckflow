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
    build_tool_result_message,
    get_approval_request,
    normalize_tool_result,
)
from companion.core_action_invocation import invoke_tool
from companion.tool_history_policy import compress_for_history
from companion.execution.result_pipeline import summarize_result
from companion.modules.repo_map import get_repo_map_generator
from companion.modules.event_logger import event_logger
from companion.tools.file_ops import file_ops
from pathlib import Path
from companion.tools.results import (
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

    mode_val = agent.state.current_mode.value if agent.state.current_mode else None
    if mode_val and mode_val in agent.MODE_TOOL_MAPPING:
        mode_tools = agent.UNIVERSAL_TOOLS | agent.MODE_TOOL_MAPPING[mode_val]
    else:
        mode_tools = agent.UNIVERSAL_TOOLS

    removed_tools = filter_known_actions(
        action_list,
        agent.tools.keys(),
        mode_tools,
        agent.state.last_syntax_errors,
    )
    for tool_name in removed_tools:
        ui.print_warning(f"Unknown tool '{tool_name}' was ignored.")

    # --- Action Count Limiter ---
    dropped = limit_actions_per_turn(action_list)
    if dropped:
        ui.print_warning(
            f"アクション数が上限(6)を超えたため、末尾{dropped}件を切り捨てました。"
        )

    # --- Fail-fast: consecutive error counter ---
    consecutive_errors = 0

    # Move terminal actions to the end
    move_terminal_actions_to_end(action_list)

    def _handle_error(action, error_content, t0, t1):
        """Record a tool/action error, update history, and check fail-fast."""
        nonlocal consecutive_errors
        error_msg = f"Action '{action.name}' failed: {error_content}"
        logger.error(error_msg)
        agent.state.last_action_result = error_msg
        ui.print_result(str(error_content), is_error=True)

        agent.state.add_message(
            "user",
            build_tool_result_message(
                action, error_content, status=ToolStatus.ERROR
            ),
        )

        results.append(error_msg)

        agent.pacemaker.update_vitals(action, error_msg, is_error=True)

        dur_ms = (t1 - t0) * 1000
        agent.timeline.record(
            action_name=action.name,
            start_ts=t0,
            end_ts=t1,
            is_error=True,
            result_summary=error_msg,
        )
        event_logger.log_action_end(
            action.name, dur_ms, is_error=True,
            result_len=len(error_msg),
        )

        consecutive_errors += 1
        if should_fail_fast(consecutive_errors):
            remaining = remaining_actions_after(action_list, action)
            if remaining > 0:
                logger.warning(
                    f"Fail-fast: {consecutive_errors} consecutive errors, aborting {remaining} remaining actions"
                )
                ui.print_warning(
                    build_fail_fast_warning(
                        consecutive_errors, remaining
                    )
                )
                agent.state.add_message(
                    "user",
                    build_fail_fast_history_message(
                        consecutive_errors, remaining
                    ),
                )
            return True
        return False

    try:
        for action in action_list.actions:
            ui.print_action(action.name, action.parameters, action.thought)

            # --- Skip redundant mode-switch actions ---
            # If already in the target mode, skip the mode-switch action
            # to prevent loops where LLM repeatedly calls ::investigate.
            _current_mode = agent.state.get_context_mode()
            if action.name == "investigate" and _current_mode == "investigation":
                logger.warning("Skipping investigate: already in investigation mode")
                ui.print_warning("investigate: 既にInvestigation Modeです。::read_file等で観察してください")
                continue

            # --- Investigation Mode Guard ---
            # Investigation mode is read-only. File mutations are blocked and
            # reported as syntax feedback so the agent explicitly closes
            # investigation with ::finish_investigation before editing.
            if should_block_investigation_edit(
                action, agent.state.get_context_mode()
            ):
                logger.info(
                    f"Blocking {action.name}: file mutations are not allowed "
                    f"during Investigation Mode"
                )
                block = build_investigation_edit_block(action)
                agent.state.last_syntax_errors.append(block.syntax_error)
                agent.state.add_message(
                    "user",
                    build_tool_result_message(
                        action, block.message, status=ToolStatus.ERROR
                    ),
                )
                agent.pacemaker.update_vitals(action, block.message, is_error=True)
                results.append(block.message)
                continue

            # --- Approval Check ---
            was_approved = False
            approval_request = get_approval_request(action, file_ops.file_exists)

            if approval_request.required:
                if not ui.request_confirmation(approval_request.warning):
                    msg = f"Action '{action.name}' denied by user."
                    ui.print_result(msg, is_error=True)
                    agent.state.last_action_result = msg

                    agent.state.add_message(
                        "user",
                        build_denial_context(action, approval_request.warning),
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
                        func, action.parameters
                    )
                    _t1 = time.monotonic()

                    if dropped_params:
                        logger.warning(
                            f"Tool '{action.name}': dropping unexpected params: {dropped_params}"
                        )

                    # Normalize pre-formatted Sym-Ops results (e.g. from file_ops,
                    # sub_llm_tools) so we wrap them once in the canonical envelope.
                    result_status, result = normalize_tool_result(raw_result)

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
                        result_str = result if isinstance(result, str) else serialize_to_text(result)
                        history_content, _cache_id = summarize_result(
                            action.name, result_str, agent
                        )

                        agent.state.add_message(
                            "user",
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
                    if action.name in ("write_file", "edit_file", "delete_file", "delete_lines"):
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
                        action.name, _dur_ms, is_error=False,
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
                if _handle_error(action, error_content, _t0, time.monotonic()):
                    break
    except KeyboardInterrupt:
        ui.print_warning("Execution interrupted by user.")
        agent.state.add_message(
            "user",
            "[System: Execution was interrupted by the user (Ctrl+C). Please wait for new instructions.]",
        )

    action_summary = build_action_summary(action_list)
    if action_summary:
        agent.state.add_message("assistant", action_summary)

    if ui:
        ui.print_token_usage(agent.llm.usage_stats)

    logger.info("Finished executing actions")
    return results
