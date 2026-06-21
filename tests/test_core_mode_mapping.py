from companion.core import DuckAgent
from companion.core_tools import MODE_TOOL_MAPPING, get_tool_descriptions
from companion.prompts.templates import PLANNING_MODE_INSTRUCTIONS


class DummyLLM:
    """Minimal LLM stub for DuckAgent registration tests."""

    usage_stats = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "estimated_cost": 0.0,
    }


def test_planning_mode_exposes_edit_tools() -> None:
    """
    Planning mode should expose file mutation tools so the agent can apply
    fixes immediately after finish_investigation without an extra mode hop.

    Args:
        None.

    Returns:
        None.
    """
    edit_tools = {"edit_file", "write_file", "delete_lines", "delete_file"}

    assert edit_tools.issubset(DuckAgent.MODE_TOOL_MAPPING["planning"])


def test_task_mode_exposes_edit_tools() -> None:
    """
    Task mode should expose file mutation tools.

    Args:
        None.

    Returns:
        None.
    """
    edit_tools = {"edit_file", "write_file", "delete_lines", "delete_file"}

    assert edit_tools.issubset(DuckAgent.MODE_TOOL_MAPPING["task"])


def test_core_mode_mapping_reexports_core_tools_mapping() -> None:
    """
    DuckAgent should keep a backwards-compatible class-level mapping alias.

    Args:
        None.

    Returns:
        None.
    """
    assert DuckAgent.MODE_TOOL_MAPPING is MODE_TOOL_MAPPING


def test_get_tool_descriptions_filters_by_mode() -> None:
    """
    Tool descriptions should expose only universal and mode-specific tools.

    Args:
        None.

    Returns:
        None.
    """
    agent = DuckAgent(llm_client=DummyLLM())

    planning_descriptions = get_tool_descriptions(agent.tools, "planning")
    unknown_mode_descriptions = get_tool_descriptions(agent.tools, "unknown")

    assert "::read_file" in planning_descriptions
    assert "::edit_file" in planning_descriptions
    assert "::execute_tasks" not in planning_descriptions
    assert "::response" in unknown_mode_descriptions
    assert "::read_file" not in unknown_mode_descriptions


def test_planning_mode_instructions_document_edit_boundaries() -> None:
    """
    Planning mode prompt text should explain why edit tools are exposed and
    when the agent must proceed to Task Mode instead.

    Args:
        None.

    Returns:
        None.
    """
    assert (
        "File mutation tools are available only for narrow"
        in PLANNING_MODE_INSTRUCTIONS
    )
    assert "::finish_investigation" in PLANNING_MODE_INSTRUCTIONS
    assert "proceed to Task Mode" in PLANNING_MODE_INSTRUCTIONS


def test_registered_tools_exclude_retired_report_finish_actions() -> None:
    """
    Retired report/finish actions should not be exposed as callable tools.

    Args:
        None.

    Returns:
        None.
    """
    agent = DuckAgent(llm_client=DummyLLM())

    assert "report" not in agent.tools
    assert "finish" not in agent.tools
    assert hasattr(agent._actions, "action_note")
    assert not hasattr(agent, "action_note_")
    assert not hasattr(agent, "action_report")
    assert not hasattr(agent, "action_finish")


def test_status_remains_protocol_marker_noop_not_user_status_action() -> None:
    """
    ::status should stay a tool-result marker no-op, not a user status action.

    Args:
        None.

    Returns:
        None.
    """
    agent = DuckAgent(llm_client=DummyLLM())

    assert agent.tools["status"].__name__ == "_action_noop_symops_marker"
    assert not hasattr(agent, "action_status")
