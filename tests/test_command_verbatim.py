"""Tests for shell command verbatim handling (issue #5).

run_command targets must pass through the parser untouched: shell
redirection (>, >>, 2>&1), pipes and chaining (&&, ||) are part of the
command body, not Sym-Ops dependency syntax.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from companion.utils.sym_ops import SymOpsProcessor  # noqa: E402
from companion.tools.shell_tool import ShellTool  # noqa: E402


def test_run_command_keeps_redirection_verbatim() -> None:
    """Redirection and chaining survive parsing for run_command."""
    result = SymOpsProcessor().process(
        "::run_command @python -m pytest test_calc.py -v 2>&1 || true\n"
    )

    assert len(result.actions) == 1
    action = result.actions[0]
    assert action.type == "run_command"
    assert action.path == "python -m pytest test_calc.py -v 2>&1 || true"
    assert action.depends_on is None


def test_run_command_keeps_pipe_and_append() -> None:
    """Pipes and append-redirection survive parsing for run_command."""
    result = SymOpsProcessor().process(
        "::run_command @pytest -q 2>> errors.log | head -20\n"
    )

    action = result.actions[0]
    assert action.path == "pytest -q 2>> errors.log | head -20"
    assert action.depends_on is None


def test_other_actions_still_split_dependencies() -> None:
    """Non-shell actions keep the legacy '>' dependency split."""
    result = SymOpsProcessor().process("::note @topic > followup\n")

    action = result.actions[0]
    assert action.path == "topic"
    assert action.depends_on == "followup"


@pytest.mark.asyncio
async def test_run_command_failure_has_header_marker() -> None:
    """Nonzero exits carry a visible header marker plus the trailer."""
    result = await ShellTool.run_command(
        f'"{sys.executable}" -c "import sys; sys.exit(5)"'
    )

    assert "[command exited with code 5]" in result
    assert "exit_code: 5" in result


@pytest.mark.asyncio
async def test_run_command_success_has_no_marker() -> None:
    """Zero exits carry no failure marker."""
    result = await ShellTool.run_command("echo ok")

    assert "exited with code" not in result
    assert "exit_code: 0" in result
