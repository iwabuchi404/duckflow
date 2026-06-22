from companion.base.llm_client import LLMClient
from companion.state.agent_state import ActionList


def _parse_actions(text: str) -> ActionList:
    """Parse Sym-Ops text through the main-agent ActionList path."""
    return LLMClient(api_key="dummy")._parse_response(text, ActionList)


def test_run_command_content_maps_to_command_parameter() -> None:
    """run_command should map the content block to the command parameter."""
    result = _parse_actions(
        ">> run a command\n" "::run_command\n" "<<<\n" "echo hello\n" ">>>"
    )

    action = result.actions[0]
    assert action.name == "run_command"
    assert action.parameters["command"] == "echo hello"


def test_message_actions_map_content_to_message_parameter() -> None:
    """note/response/duck_call should use message, not path/content."""
    result = _parse_actions(
        ">> send messages\n"
        "::note\n"
        "<<<\nprogress\n>>>\n"
        "::response\n"
        "<<<\ndone\n>>>\n"
        "::duck_call\n"
        "<<<\nneed input\n>>>"
    )

    assert result.actions[0].parameters == {"message": "progress"}
    assert result.actions[1].parameters == {"message": "done"}
    assert result.actions[2].parameters == {"message": "need input"}


def test_propose_plan_content_maps_to_goal_parameter() -> None:
    """propose_plan should map its content block to goal."""
    result = _parse_actions(
        ">> plan\n"
        "::propose_plan\n"
        "<<<\n"
        "## Step 1: Build\n"
        "Do the work.\n"
        ">>>"
    )

    action = result.actions[0]
    assert action.name == "propose_plan"
    assert action.parameters["goal"].startswith("## Step 1: Build")


def test_mark_task_complete_target_maps_to_task_index() -> None:
    """mark_task_complete @N should become task_index=N."""
    result = _parse_actions(">> complete task\n::mark_task_complete @2\n::c0.9 ::s1.0")

    action = result.actions[0]
    assert action.name == "mark_task_complete"
    assert action.parameters["task_index"] == 2


def test_archive_search_target_maps_to_query_parameter() -> None:
    """search_archives should map @target to query."""
    result = _parse_actions(
        ">> search memory\n"
        "::search_archives @parser failure\n"
    )

    assert result.actions[0].parameters == {"query": "parser failure"}


def test_retired_report_and_finish_actions_have_no_special_parameter_mapping() -> None:
    """
    Retired report/finish actions should not be treated like response-style
    callable tools by the Sym-Ops to ActionList conversion layer.
    """
    result = _parse_actions(">> retired actions\n::report @summary\n::finish @done")

    assert result.actions[0].name == "report"
    assert result.actions[0].parameters == {"path": "summary"}
    assert result.actions[1].name == "finish"
    assert result.actions[1].parameters == {"path": "done"}
