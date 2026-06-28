"""
Approval and tool-result formatting helpers for DuckAgent action execution.
"""

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
    for action in action_list.actions:
        target = action.parameters.get("path", action.parameters.get("command", ""))
        lines.append(f":: {action.name} @{target}" if target else f":: {action.name}")
    return "\n".join(lines)


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
                "The find snippet did not match the file content. "
                "The file may have changed since read_file was called. "
                "Re-run read_file, copy the target lines EXACTLY as they appear "
                "(without line-number prefixes) into find:, then retry edit_file."
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
