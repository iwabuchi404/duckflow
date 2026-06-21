from companion.core_action_results import (
    build_action_summary,
    action_target,
    build_denial_context,
    build_tool_result_message,
    get_approval_request,
)
from companion.state.agent_state import Action
from companion.state.agent_state import ActionList
from companion.tools.results import ToolStatus, is_tool_result_message


def test_get_approval_request_requires_mutating_actions() -> None:
    """
    Mutating file actions should always require approval.

    Args:
        None.

    Returns:
        None.
    """
    action = Action(name="edit_file", parameters={"path": "app.py"})

    request = get_approval_request(action, file_exists=lambda _: False)

    assert request.required is True
    assert "app.py" in request.warning


def test_get_approval_request_requires_write_overwrite_only() -> None:
    """
    write_file should require approval only when the target already exists.

    Args:
        None.

    Returns:
        None.
    """
    action = Action(name="write_file", parameters={"path": "new.py"})

    assert get_approval_request(action, file_exists=lambda _: False).required is False
    assert get_approval_request(action, file_exists=lambda _: True).required is True


def test_build_denial_context_mentions_action_and_warning() -> None:
    """
    Denial feedback should preserve the refused action and approval warning.

    Args:
        None.

    Returns:
        None.
    """
    action = Action(name="delete_file", parameters={"path": "old.py"})

    context = build_denial_context(action, "Delete old.py?")

    assert "delete_file" in context
    assert "Delete old.py?" in context
    assert "refused" in context


def test_action_target_prefers_path_then_command_then_task() -> None:
    """
    Action target formatting should prefer concrete file or command targets.

    Args:
        None.

    Returns:
        None.
    """
    assert (
        action_target(Action(name="read_file", parameters={"path": "a.py"})) == "a.py"
    )
    assert (
        action_target(Action(name="run_command", parameters={"command": "pytest"}))
        == "pytest"
    )
    assert action_target(Action(name="note", parameters={})) == "task"


def test_build_tool_result_message_wraps_error_and_approval_note() -> None:
    """
    Tool-result history messages should be enveloped and retain approval notes.

    Args:
        None.

    Returns:
        None.
    """
    action = Action(name="edit_file", parameters={"path": "app.py"})

    message = build_tool_result_message(
        action,
        ValueError("no match"),
        status=ToolStatus.ERROR,
        approved=True,
    )

    assert is_tool_result_message(message)
    assert "::status error" in message
    assert "::edit_file @app.py" in message
    assert "Exception: no match" in message
    assert "User approved action" in message


def test_build_action_summary_formats_reasoning_and_targets() -> None:
    """
    Action summaries should retain model reasoning and concise action targets.

    Args:
        None.

    Returns:
        None.
    """
    action_list = ActionList(
        reasoning="inspect then report",
        actions=[
            Action(name="read_file", parameters={"path": "app.py"}),
            Action(name="run_command", parameters={"command": "pytest"}),
            Action(name="response", parameters={"message": "done"}),
        ],
    )

    summary = build_action_summary(action_list)

    assert summary.splitlines() == [
        ">> inspect then report",
        ":: read_file @app.py",
        ":: run_command @pytest",
        ":: response",
    ]
