"""
Action execution dispatcher extracted from DuckAgent.

Handles the per-action loop: approval checks, tool invocation, error handling,
fail-fast, and conversation history injection.
"""

import logging

from companion.core_action_pipeline import (
    action_list_safety_score,
    build_fail_fast_history_message,
    build_fail_fast_warning,
    build_safety_cancel_message,
    build_investigation_edit_block,
    limit_actions_per_turn,
    filter_known_actions,
    move_terminal_actions_to_end,
    remaining_actions_after,
    requires_safety_confirmation,
    should_block_investigation_edit,
    should_fail_fast,
)
from companion.core_action_results import (
    build_action_summary,
    build_action_exception_syntax_error,
    build_denial_context,
    build_tool_result_message,
    get_approval_request,
)
from companion.core_action_invocation import invoke_tool
from companion.tools.file_ops import file_ops
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

    # --- Safety Score Interceptor (Sym-Ops v3.1) ---
    safety_score = action_list_safety_score(action_list)
    if requires_safety_confirmation(action_list):
        ui.print_safety_warning(safety_score)
        if not ui.request_confirmation("低い Safety Score で実行を続けますか？"):
            agent.state.add_message(
                "user", build_safety_cancel_message(safety_score)
            )
            return results

    # --- Fail-fast: consecutive error counter ---
    consecutive_errors = 0

    # Move terminal actions to the end
    move_terminal_actions_to_end(action_list)

    try:
        for action in action_list.actions:
            ui.print_action(action.name, action.parameters, action.thought)

            # --- Investigation Mode Guard ---
            if should_block_investigation_edit(
                action, agent.state.get_context_mode()
            ):
                investigation_block = build_investigation_edit_block(action)
                ui.print_warning(
                    f"Investigation Mode中のファイル変更をブロック: {action.name}"
                )
                logger.warning(
                    f"Blocked edit action in Investigation Mode: {action.name}"
                )
                agent.state.last_action_result = investigation_block.message
                agent.state.last_syntax_errors.append(
                    investigation_block.syntax_error
                )
                agent.state.add_message(
                    "user",
                    build_tool_result_message(
                        action,
                        investigation_block.message,
                        status=ToolStatus.ERROR,
                    ),
                )
                results.append(investigation_block.message)
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

            if action.name in agent.tools:
                try:
                    func = agent.tools[action.name]
                    logger.info(f"Calling tool: {action.name}")

                    result, dropped_params = await invoke_tool(
                        func, action.parameters
                    )
                    if dropped_params:
                        logger.warning(
                            f"Tool '{action.name}': dropping unexpected params: {dropped_params}"
                        )

                    logger.info(
                        f"Tool {action.name} returned. Result length: {len(str(result))}"
                    )

                    agent.state.last_action_result = (
                        f"Action '{action.name}' succeeded: {result}"
                    )

                    if action.name not in ("response",):
                        agent.state.add_message(
                            "user",
                            build_tool_result_message(
                                action,
                                result,
                                status=ToolStatus.OK,
                                approved=was_approved,
                            ),
                        )

                        if isinstance(result, str):
                            ui.print_result(result)
                        else:
                            ui.print_result(serialize_to_text(result))

                    results.append(result)

                    agent.pacemaker.update_vitals(action, result, is_error=False)
                    consecutive_errors = 0

                except Exception as e:
                    error_msg = f"Action '{action.name}' failed: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    agent.state.last_action_result = error_msg
                    ui.print_result(str(e), is_error=True)

                    syntax_error = build_action_exception_syntax_error(action, e)
                    if syntax_error is not None:
                        agent.state.last_syntax_errors.append(syntax_error)

                    agent.state.add_message(
                        "user",
                        build_tool_result_message(
                            action, e, status=ToolStatus.ERROR
                        ),
                    )

                    results.append(error_msg)

                    agent.pacemaker.update_vitals(action, error_msg, is_error=True)

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
                        break
            else:
                msg = f"Unknown tool: {action.name}"
                logger.warning(msg)
                agent.state.last_action_result = msg
                ui.print_result(msg, is_error=True)

                available_tools = ", ".join(agent.tools.keys())
                agent.state.add_message(
                    "user",
                    f"[Error] Tool '{action.name}' does not exist. "
                    f"Available tools: {available_tools}. "
                    f"Please use one of the available tools.",
                )

                results.append(msg)

                agent.pacemaker.update_vitals(action, msg, is_error=True)
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
