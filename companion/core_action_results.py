"""
Approval and tool-result formatting helpers for DuckAgent action execution.
"""

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from companion.state.agent_state import Action
from companion.state.agent_state import SyntaxErrorInfo
from companion.tools.results import (
    ToolResult,
    ToolStatus,
    format_symops_response,
    wrap_tool_result,
)

MUTATING_ACTIONS = {"delete_file", "delete_lines", "edit_file"}


@dataclass(frozen=True)
class ApprovalRequest:
    """
    Approval requirement metadata for an action.

    Attributes:
        required: Whether the action needs user approval.
        warning: User-facing approval prompt.
    """

    required: bool
    warning: str = ""


def get_approval_request(
    action: Action, file_exists: Callable[[str], bool]
) -> ApprovalRequest:
    """
    Determine whether an action requires user approval.

    Args:
        action: Action to inspect.
        file_exists: Function used to check write_file overwrite risk.

    Returns:
        Approval request metadata.
    """
    if action.name in MUTATING_ACTIONS:
        path = action.parameters.get("path", "unknown")
        return ApprovalRequest(
            required=True,
            warning=f"This action will modify/delete '{path}'. Are you sure?",
        )

    if action.name == "write_file":
        path = action.parameters.get("path")
        if path and file_exists(path):
            return ApprovalRequest(
                required=True,
                warning=f"File '{path}' already exists. Overwrite?",
            )

    return ApprovalRequest(required=False)


def build_denial_context(action: Action, warning: str) -> str:
    """
    Build conversation-history feedback for a denied approval request.

    Args:
        action: Denied action.
        warning: Approval warning shown to the user.

    Returns:
        Context message for the next LLM turn.
    """
    return (
        f"[User denied approval for action '{action.name}'] "
        f"Reason: {warning}. "
        f"The user refused to proceed with this operation. "
        f"Please either: 1) Ask the user what to do instead, "
        f"2) Try a different approach, or 3) Explain the situation."
    )


def action_target(action: Action) -> str:
    """
    Resolve the display target for an action result.

    Args:
        action: Action whose target should be displayed.

    Returns:
        Path, command, or generic task target.
    """
    return action.parameters.get("path", action.parameters.get("command", "task"))


def build_tool_result_message(
    action: Action,
    content: Any,
    status: ToolStatus = ToolStatus.OK,
    approved: bool = False,
    history_content: str | None = None,
) -> str:
    """
    Build an enveloped tool-result message for conversation history.

    Args:
        action: Executed action.
        content: Tool result payload (used for UI display).
        status: Tool execution status.
        approved: Whether the user approved this action before execution.
        history_content: Compressed content for LLM history injection.
            When None, the raw content is used (backward compatible).

    Returns:
        Enveloped message suitable for role="user" history injection.
    """
    if isinstance(content, ToolResult):
        # Tool already formatted its own result; use it directly.
        tool_res = content
        if history_content is not None:
            tool_res = ToolResult(
                status=tool_res.status,
                tool_name=tool_res.tool_name,
                target=tool_res.target,
                content=history_content,
            )
    else:
        # Use history_content for the envelope if provided, otherwise raw content
        envelope_content = history_content if history_content is not None else content
        tool_res = ToolResult(
            status=status,
            tool_name=action.name,
            target=action_target(action),
            content=envelope_content,
        )
    formatted_res = wrap_tool_result(format_symops_response(tool_res))
    if not approved:
        return formatted_res

    return (
        f"{formatted_res}\n\n"
        "[System: User approved action. Proceed with next steps.]"
    )


def build_action_summary(action_list: Any) -> str:
    """
    Format executed action names for assistant history.

    Reasoning is excluded from the summary to avoid bloating conversation
    history with potentially large reasoning text from reasoning models.
    Reasoning is displayed to the user via ui.print_thinking() but does
    not need to be persisted in conversation history.

    Args:
        action_list: ActionList-like object with reasoning and actions.

    Returns:
        Assistant-role summary text, or an empty string.
    """
    lines = []
    notes = []
    for action in action_list.actions:
        target = action.parameters.get("path", action.parameters.get("command", ""))
        lines.append(f":: {action.name} @{target}" if target else f":: {action.name}")
        # Body-bearing actions: record on a SEPARATE line that content WAS
        # passed (with its size). Appending to the action line itself caused
        # models to copy the note into the next @target ("File not found").
        # The full body lives in the tool result.
        for key in ("content", "body", "text"):
            value = action.parameters.get(key)
            if isinstance(value, str) and value:
                notes.append(
                    f"履歴注記：{action.name} の本文{len(value)}文字を送信済み。"
                    "本文は省略。確認は実行結果で行うこと。"
                )
                break
    return "\n".join(lines + notes)


def build_action_exception_syntax_error(
    action: Action, error: Exception
) -> SyntaxErrorInfo | None:
    """
    Build syntax correction feedback for common action execution errors.

    Args:
        action: Action that raised an exception.
        error: Exception raised by the action.

    Returns:
        SyntaxErrorInfo when the error should be fed back to the model,
        otherwise None.
    """
    if action.name in ("edit_file", "delete_lines") and isinstance(error, ValueError):
        return SyntaxErrorInfo(
            error_type="edit_find_mismatch",
            raw_snippet=str(error)[:300],
            correction_hint=(
                "The SEARCH block did not match the file content. "
                "The file may have changed since read_file was called. "
                "Next: run ::read_file on the file, copy the target lines EXACTLY "
                "as they appear (without line-number prefixes) into a new SEARCH "
                "block, then retry ::edit_file. "
                "Do not resend the identical SEARCH text unchanged."
            ),
        )

    if isinstance(error, TypeError):
        return SyntaxErrorInfo(
            error_type="missing_param",
            raw_snippet=str(error)[:300],
            correction_hint=(
                f"Wrong or missing parameter for '{action.name}'. "
                "Check the tool description for correct parameter names and format."
            ),
        )

    return None


def build_repeated_failure_syntax_error(action: Action, count: int) -> SyntaxErrorInfo:
    """
    Build escalated feedback for a call that keeps failing identically.

    The standard per-error hint is injected for one turn only; a model that
    resends the same malformed call across turns (observed: GLM resent an
    empty-body edit_file 6x, burning ~140k tokens) needs an explicit
    stop-and-change-form message.

    Args:
        action: The repeatedly-failing action.
        count: How many times this call/error kind has already failed.

    Returns:
        SyntaxErrorInfo with a hard-stop recovery instruction.
    """
    target = str(
        action.parameters.get("path") or action.parameters.get("command") or ""
    )
    return SyntaxErrorInfo(
        error_type="repeated_failure",
        raw_snippet=f"{action.name}({target}) repeated x{count}",
        correction_hint=(
            f"STOP: '{action.name}' has already failed {count} times the "
            "same way. Repeating it unchanged CANNOT succeed. Required "
            f"recovery: (1) ::read_file @{target or 'path/to/file'} to "
            "re-confirm the current state, (2) retry with a DIFFERENT form "
            "— for edit_file the <<< >>> body must contain <<<<<<< SEARCH / "
            "======= / >>>>>>> REPLACE markers; if you cannot produce that "
            "format, use ::write_file to rewrite the file."
        ),
    )


def build_dropped_params_syntax_error(
    action: Action, dropped_params: set[str], func: Callable[..., Any]
) -> SyntaxErrorInfo:
    """
    Build syntax correction feedback for parameters silently dropped
    because a tool does not accept them.

    Without this feedback the model never learns that its extra parameters
    were ignored and tends to repeat them turn after turn.

    Args:
        action: Action whose parameters included unsupported keys.
        dropped_params: Parameter names that were dropped before invocation.
        func: The tool implementation, used to list its accepted parameters.

    Returns:
        SyntaxErrorInfo describing the dropped parameters and valid ones.
    """
    valid_params = [
        name
        for name, param in inspect.signature(func).parameters.items()
        if param.kind != inspect.Parameter.VAR_KEYWORD
    ]
    dropped_list = ", ".join(sorted(dropped_params))
    return SyntaxErrorInfo(
        error_type="unexpected_params",
        raw_snippet=f"{action.name}: {dropped_list}",
        correction_hint=(
            f"Tool '{action.name}' does not accept parameter(s): {dropped_list}. "
            f"They were ignored. Valid parameters: {', '.join(valid_params) or '(none)'}."
        ),
    )
