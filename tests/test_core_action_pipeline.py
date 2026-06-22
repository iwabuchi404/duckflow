from companion.core_action_pipeline import (
    build_fail_fast_history_message,
    build_fail_fast_warning,
    build_investigation_edit_block,
    build_unknown_tool_hint,
    filter_known_actions,
    is_edit_action,
    limit_actions_per_turn,
    move_terminal_actions_to_end,
    remaining_actions_after,
    should_block_investigation_edit,
    should_fail_fast,
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


def test_is_edit_action_detects_file_mutations() -> None:
    """
    Edit-action classification should cover file mutation tools only.

    Args:
        None.

    Returns:
        None.
    """
    assert is_edit_action(Action(name="edit_file", parameters={})) is True
    assert is_edit_action(Action(name="delete_lines", parameters={})) is True
    assert is_edit_action(Action(name="read_file", parameters={})) is False


def test_investigation_edit_block_helpers() -> None:
    """
    Investigation Mode should block edit actions with correction feedback.

    Args:
        None.

    Returns:
        None.
    """
    action = Action(name="write_file", parameters={"path": "app.py"})

    assert should_block_investigation_edit(action, "investigation") is True
    assert should_block_investigation_edit(action, "task") is False
    assert (
        should_block_investigation_edit(
            Action(name="read_file", parameters={"path": "app.py"}),
            "investigation",
        )
        is False
    )

    block = build_investigation_edit_block(action)

    assert "[BLOCKED]" in block.message
    assert "Investigation Mode" in block.message
    assert block.syntax_error.error_type == "investigation_edit_blocked"
    assert block.syntax_error.raw_snippet == "::write_file"


def test_fail_fast_helpers() -> None:
    """
    Fail-fast helpers should count remaining actions and build feedback.

    Args:
        None.

    Returns:
        None.
    """
    action_list = ActionList(
        reasoning="fail",
        actions=[
            Action(name="fail_one", parameters={}),
            Action(name="fail_two", parameters={}),
            Action(name="later", parameters={}),
        ],
    )

    assert should_fail_fast(1) is False
    assert should_fail_fast(2) is True
    assert remaining_actions_after(action_list, action_list.actions[1]) == 1
    assert "残り1件" in build_fail_fast_warning(2, 1)
    assert "[SYSTEM]" in build_fail_fast_history_message(2, 1)
