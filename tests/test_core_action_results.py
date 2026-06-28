from companion.core_action_results import (
    build_action_exception_syntax_error,
    build_action_summary,
    action_target,
    build_denial_context,
    build_tool_result_message,
    get_approval_request,
    normalize_tool_result,
)
from companion.state.agent_state import Action
from companion.state.agent_state import ActionList
from companion.tools.results import ToolResult, ToolStatus, is_tool_result_message


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


def test_build_action_summary_formats_targets_without_reasoning() -> None:
    """
    Action summaries should list executed action targets without reasoning.

    Reasoning is displayed to the user via ui.print_thinking() and is
    intentionally excluded from the history summary to avoid bloating the
    context window with large reasoning-model outputs.

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
        ":: read_file @app.py",
        ":: run_command @pytest",
        ":: response",
    ]


def test_build_action_exception_syntax_error_for_edit_find_mismatch() -> None:
    """
    Edit ValueError should produce edit_find_mismatch feedback.

    Args:
        None.

    Returns:
        None.
    """
    action = Action(name="edit_file", parameters={"path": "app.py"})

    syntax_error = build_action_exception_syntax_error(
        action, ValueError("find snippet missing")
    )

    assert syntax_error is not None
    assert syntax_error.error_type == "edit_find_mismatch"
    assert "read_file" in syntax_error.correction_hint


def test_build_action_exception_syntax_error_for_type_error() -> None:
    """
    TypeError should produce missing_param feedback.

    Args:
        None.

    Returns:
        None.
    """
    action = Action(name="run_command", parameters={})

    syntax_error = build_action_exception_syntax_error(
        action, TypeError("missing command")
    )

    assert syntax_error is not None
    assert syntax_error.error_type == "missing_param"
    assert "run_command" in syntax_error.correction_hint


def test_build_action_exception_syntax_error_ignores_runtime_error() -> None:
    """
    Generic runtime errors should not create syntax correction feedback.

    Args:
        None.

    Returns:
        None.
    """
    action = Action(name="run_command", parameters={})

    assert build_action_exception_syntax_error(action, RuntimeError("boom")) is None


def test_normalize_tool_result_extracts_error_body() -> None:
    """
    Pre-formatted Sym-Ops error strings should be normalized to (ERROR, body).
    """
    raw = "::status error\n::edit_file @app.py\n<<<\nReason: find_not_matched\n>>>"
    status, body = normalize_tool_result(raw)

    assert status == ToolStatus.ERROR
    assert body == "Reason: find_not_matched"


def test_normalize_tool_result_extracts_ok_body() -> None:
    """
    Pre-formatted Sym-Ops success strings should be normalized to (OK, body).
    """
    raw = "::status ok\n::generate_code @module.py\n<<<\nSuccess: 42 lines\n>>>"
    status, body = normalize_tool_result(raw)

    assert status == ToolStatus.OK
    assert body == "Success: 42 lines"


def test_normalize_tool_result_treats_cancelled_as_error() -> None:
    """
    Cancelled Sub-LLM results should be treated as errors for the LLM.
    """
    raw = "::status cancelled\n::generate_code @module.py\n<<<\nUser cancelled\n>>>"
    status, body = normalize_tool_result(raw)

    assert status == ToolStatus.ERROR
    assert body == "User cancelled"


def test_normalize_tool_result_passes_plain_results_unchanged() -> None:
    """
    Plain non-Sym-Ops results should keep the default status and raw content.
    """
    raw = "Successfully edited app.py"
    status, body = normalize_tool_result(raw)

    assert status == ToolStatus.OK
    assert body == raw


def test_normalize_tool_result_falls_back_when_no_content_block() -> None:
    """
    Pre-formatted status without a content block should strip the status line.
    """
    raw = "::status error\nReason: File not found: app.py"
    status, body = normalize_tool_result(raw)

    assert status == ToolStatus.ERROR
    assert body == "Reason: File not found: app.py"


def test_normalize_tool_result_handles_toolresult_dataclass() -> None:
    """
    Tools that return ToolResult directly (e.g. task_tool) should be normalized.
    """
    raw = ToolResult.error("generate_tasks", "plan", "No active plan.")
    status, body = normalize_tool_result(raw)

    assert status == ToolStatus.ERROR
    assert body == "No active plan."
