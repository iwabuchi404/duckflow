import os
import sys

sys.path.append(os.getcwd())

from companion.core import DuckAgent


def test_planning_mode_does_not_expose_edit_tools() -> None:
    """
    Planning mode should not expose file mutation tools.

    Args:
        None.

    Returns:
        None.
    """
    edit_tools = {"edit_file", "write_file", "delete_lines", "delete_file"}

    assert DuckAgent.MODE_TOOL_MAPPING["planning"].isdisjoint(edit_tools)


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
