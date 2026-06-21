"""
Pre-dispatch action list normalization helpers for DuckAgent.
"""

import difflib
import logging
from dataclasses import dataclass
from typing import Collection

from companion.state.agent_state import Action, ActionList, SyntaxErrorInfo

logger = logging.getLogger(__name__)

MAX_ACTIONS_PER_TURN = 6
TERMINAL_ACTIONS = {"response", "exit", "duck_call"}
EDIT_ACTIONS = {"edit_file", "write_file", "delete_file", "delete_lines"}
SAFETY_CONFIRMATION_THRESHOLD = 0.5


@dataclass(frozen=True)
class InvestigationBlock:
    """
    Feedback generated when an edit action is blocked in Investigation Mode.

    Attributes:
        message: Tool-result content shown to the model.
        syntax_error: Correction hint for the next model turn.
    """

    message: str
    syntax_error: SyntaxErrorInfo


def filter_known_actions(
    action_list: ActionList,
    known_tool_names: Collection[str],
    mode_tool_names: Collection[str],
    syntax_errors: list[SyntaxErrorInfo],
) -> list[str]:
    """
    Remove unknown tools from an action list and record correction hints.

    Args:
        action_list: Action list to mutate in place.
        known_tool_names: All registered tool names.
        mode_tool_names: Tool names currently exposed to the model.
        syntax_errors: State-owned syntax error list to append hints to.

    Returns:
        Names of tools removed from the action list.
    """
    known_actions = []
    removed_tools = []
    known_names = set(known_tool_names)

    for action in action_list.actions:
        if action.name in known_names:
            known_actions.append(action)
            continue

        logger.warning("Filtered out unknown tool: %s", action.name)
        removed_tools.append(action.name)
        syntax_errors.append(
            SyntaxErrorInfo(
                error_type="unknown_tool",
                raw_snippet=action.name,
                correction_hint=build_unknown_tool_hint(
                    action.name, known_names, mode_tool_names
                ),
            )
        )

    action_list.actions = known_actions
    return removed_tools


def build_unknown_tool_hint(
    tool_name: str,
    known_tool_names: Collection[str],
    mode_tool_names: Collection[str],
) -> str:
    """
    Build a concise correction hint for an unknown tool call.

    Args:
        tool_name: Invalid tool name emitted by the model.
        known_tool_names: All registered tool names.
        mode_tool_names: Tool names valid in the current mode.

    Returns:
        Human-readable correction hint.
    """
    close = difflib.get_close_matches(tool_name, known_tool_names, n=2, cutoff=0.5)
    if close:
        hint = f"'{tool_name}' is not a valid tool. Did you mean: {', '.join(close)}?"
    else:
        hint = f"'{tool_name}' is not a valid tool."

    valid_tools = ", ".join(sorted(mode_tool_names))
    return f"{hint} Valid tools in this mode: {valid_tools}"


def limit_actions_per_turn(
    action_list: ActionList, max_actions: int = MAX_ACTIONS_PER_TURN
) -> int:
    """
    Truncate an action list to the per-turn maximum.

    Args:
        action_list: Action list to mutate in place.
        max_actions: Maximum number of actions to keep.

    Returns:
        Number of dropped actions.
    """
    if len(action_list.actions) <= max_actions:
        return 0

    dropped = len(action_list.actions) - max_actions
    logger.warning(
        "Action limit exceeded: %s actions, dropping last %s",
        len(action_list.actions),
        dropped,
    )
    action_list.actions = action_list.actions[:max_actions]
    return dropped


def move_terminal_actions_to_end(action_list: ActionList) -> None:
    """
    Move user-facing terminal actions after operational actions.

    Args:
        action_list: Action list to mutate in place.

    Returns:
        None.
    """
    action_list.actions = sorted(action_list.actions, key=_terminal_sort_key)


def action_list_safety_score(action_list: ActionList) -> float:
    """
    Resolve the action list safety score.

    Args:
        action_list: Action list with optional vitals metadata.

    Returns:
        Safety score, defaulting to 1.0.
    """
    if not action_list.vitals:
        return 1.0
    return float(action_list.vitals.get("safety", 1.0))


def requires_safety_confirmation(action_list: ActionList) -> bool:
    """
    Determine whether an action list needs low-safety confirmation.

    Args:
        action_list: Action list with optional vitals metadata.

    Returns:
        True when the safety score is below the confirmation threshold.
    """
    return action_list_safety_score(action_list) < SAFETY_CONFIRMATION_THRESHOLD


def build_safety_cancel_message(safety_score: float) -> str:
    """
    Build feedback for a denied low-safety action list.

    Args:
        safety_score: Safety score that triggered confirmation.

    Returns:
        Conversation-history message for the next model turn.
    """
    return (
        f"Safety Score が低いため ({safety_score:.2f})、"
        "ユーザーがすべてのアクションをキャンセルしました。"
        "安全な代替手段を検討してください。"
    )


def is_edit_action(action: Action) -> bool:
    """
    Check whether an action mutates files.

    Args:
        action: Action to classify.

    Returns:
        True for file mutation actions.
    """
    return action.name in EDIT_ACTIONS


def should_block_investigation_edit(action: Action, context_mode: str) -> bool:
    """
    Determine whether an action should be blocked in Investigation Mode.

    Args:
        action: Action to classify.
        context_mode: Current agent context mode.

    Returns:
        True when a file mutation is attempted during investigation.
    """
    return context_mode == "investigation" and is_edit_action(action)


def build_investigation_edit_block(action: Action) -> InvestigationBlock:
    """
    Build feedback for a blocked Investigation Mode edit action.

    Args:
        action: Blocked file mutation action.

    Returns:
        Block message and syntax correction hint.
    """
    message = (
        f"[BLOCKED] '{action.name}' is not allowed during Investigation Mode. "
        "Investigation is read-only. "
        "Allowed: read_file, grep_files, list_directory, run_command, "
        "submit_hypothesis, finish_investigation. "
        "Call ::finish_investigation @<conclusion> when root cause is confirmed, "
        "then re-enter Task mode to apply edits."
    )
    syntax_error = SyntaxErrorInfo(
        error_type="investigation_edit_blocked",
        raw_snippet=f"::{action.name}",
        correction_hint=(
            f"'{action.name}' cannot be called during Investigation Mode. "
            "Close investigation first: ::finish_investigation @<conclusion>, "
            "then re-enter Task mode to apply edits."
        ),
    )
    return InvestigationBlock(message=message, syntax_error=syntax_error)


def _terminal_sort_key(action: Action) -> int:
    """
    Sort non-terminal actions before terminal actions.

    Args:
        action: Action to classify.

    Returns:
        1 for terminal actions, 0 otherwise.
    """
    return 1 if action.name in TERMINAL_ACTIONS else 0
