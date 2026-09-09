"""Tests that run_command executes inside the configured workspace root."""

from pathlib import Path

import pytest

from companion.tools.file_ops import file_ops
from companion.tools.shell_tool import ShellTool


@pytest.mark.asyncio
async def test_run_command_uses_workspace_root(tmp_path: Path) -> None:
    """Commands must run with cwd = file_ops.workspace_root, not the process cwd."""
    file_ops.set_workspace_root(str(tmp_path))
    try:
        result = await ShellTool.run_command(
            f'"{__import__("sys").executable}" -c "import os; print(os.getcwd())"'
        )
    finally:
        file_ops.set_workspace_root(".")

    assert str(tmp_path) in result


@pytest.mark.asyncio
async def test_run_command_reports_nonzero_exit_code() -> None:
    """A failing command must surface its exit code in the result."""
    result = await ShellTool.run_command(
        f'"{__import__("sys").executable}" -c "import sys; sys.exit(5)"'
    )

    assert "exit_code: 5" in result


@pytest.mark.asyncio
async def test_run_command_success_has_zero_exit_code() -> None:
    """A succeeding command reports exit_code: 0."""
    result = await ShellTool.run_command("echo ok")

    assert "exit_code: 0" in result
