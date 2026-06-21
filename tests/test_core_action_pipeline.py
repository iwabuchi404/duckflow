from companion.core_action_pipeline import (
    build_unknown_tool_hint,
    filter_known_actions,
    limit_actions_per_turn,
    move_terminal_actions_to_end,
)
from companion.state.agent_state import Action, ActionList


def test_filter_known_actions_removes_unknown_and_records_hint() -> None:
    """
    Unknown actions should be removed before dispatch with a correction hint.

    Args:
        None.

    Returns:
        None.
    """
    action_list = ActionList(
        reasoning="filter",
        actions=[
            Action(name="read_file", parameters={}),
            Action(name="read_flie", parameters={}),
        ],
    )
    syntax_errors = []

    removed = filter_known_actions(
        action_list,
        known_tool_names={"read_file", "response"},
        mode_tool_names={"read_file", "response"},
        syntax_errors=syntax_errors,
    )

    assert removed == ["read_flie"]
    assert [action.name for action in action_list.actions] == ["read_file"]
    assert syntax_errors[0].error_type == "unknown_tool"
    assert "read_file" in syntax_errors[0].correction_hint


def test_limit_actions_per_turn_truncates_tail() -> None:
    """
    Action limiting should keep the first actions and report drop count.

    Args:
        None.

    Returns:
        None.
    """
    action_list = ActionList(
        reasoning="limit",
        actions=[Action(name="note", parameters={"message": str(i)}) for i in range(4)],
    )

    dropped = limit_actions_per_turn(action_list, max_actions=2)

    assert dropped == 2
    assert [action.parameters["message"] for action in action_list.actions] == [
        "0",
        "1",
    ]


def test_move_terminal_actions_to_end_preserves_relative_groups() -> None:
    """
    Terminal actions should move after operational actions.

    Args:
        None.

    Returns:
        None.
    """
    action_list = ActionList(
        reasoning="order",
        actions=[
            Action(name="response", parameters={}),
            Action(name="read_file", parameters={}),
            Action(name="duck_call", parameters={}),
            Action(name="grep_files", parameters={}),
        ],
    )

    move_terminal_actions_to_end(action_list)

    assert [action.name for action in action_list.actions] == [
        "read_file",
        "grep_files",
        "response",
        "duck_call",
    ]


def test_build_unknown_tool_hint_uses_mode_scoped_valid_tools() -> None:
    """
    Unknown-tool hints should list mode-scoped tools, not every registered tool.

    Args:
        None.

    Returns:
        None.
    """
    hint = build_unknown_tool_hint(
        "delete",
        known_tool_names={"delete_file", "read_file", "execute_tasks"},
        mode_tool_names={"read_file"},
    )

    assert "delete_file" in hint
    assert "Valid tools in this mode: read_file" in hint
    assert "execute_tasks" not in hint
