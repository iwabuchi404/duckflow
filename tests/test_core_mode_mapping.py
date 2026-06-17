import os
import sys

sys.path.append(os.getcwd())

from companion.core import DuckAgent


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
