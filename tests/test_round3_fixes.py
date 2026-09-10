"""Tests for round-3 fixes: body recovery, strict verification tag."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from companion.core_action_invocation import invoke_tool  # noqa: E402
from evals.analysis import tag_verified_edit_success  # noqa: E402


@pytest.mark.asyncio
async def test_invoke_tool_maps_raw_code_block_to_body() -> None:
    """Normal form (inline name + raw code block) fills body."""

    async def fake_replace(path: str, name: str, body: str) -> str:
        """Fake replace_function contract."""
        assert path == "utils/helpers.py"
        assert name == "helo"
        return f"replaced ok ({len(body)} chars)"

    code = "def greet(name: str) -> str:\n    return f'Hello, {name}!'\n"
    result, dropped = await invoke_tool(
        fake_replace,
        {"path": "utils/helpers.py", "name": "helo", "content": code},
        tool_name="replace_function",
    )

    assert "replaced ok" in result
    assert "content" not in dropped
    assert "body" not in dropped


@pytest.mark.asyncio
async def test_invoke_tool_bare_keys_without_delimiters() -> None:
    """---less key lines fill params by signature."""

    async def fake_replace(path: str, name: str, body: str) -> str:
        """Fake replace_function contract."""
        return f"{path}|{name}|{len(body)}"

    block = "path: a.py\nname: old\nbody: |\n  def new(): ...\n"
    result, dropped = await invoke_tool(
        fake_replace, {"content": block}, tool_name="replace_function"
    )

    assert result == "a.py|old|15"
    assert dropped == set()


def test_verified_success_requires_exit_zero() -> None:
    """A post-edit run_command with exit 0 counts as verified success."""
    history = [
        {"role": "assistant", "content": ":: edit_file @calc.py"},
        {
            "role": "user",
            "content": "[TOOL_RESULT]\n::status ok\n::run_command @pytest\n"
            "<<<\n2 passed\nexit_code: 0\n>>>\n[/TOOL_RESULT]",
        },
    ]

    assert tag_verified_edit_success(history) is True


def test_verified_success_rejects_failing_check() -> None:
    """A post-edit run_command with nonzero exit does not count."""
    history = [
        {"role": "assistant", "content": ":: edit_file @calc.py"},
        {
            "role": "user",
            "content": "[TOOL_RESULT]\n::status ok\n::run_command @pytest\n"
            "<<<\n1 failed\nexit_code: 1\n>>>\n[/TOOL_RESULT]",
        },
    ]

    assert tag_verified_edit_success(history) is False


def test_verified_success_rejects_read_only() -> None:
    """Re-reading without a command run does not count as success."""
    history = [
        {"role": "assistant", "content": ":: edit_file @calc.py"},
        {"role": "assistant", "content": ":: read_file @calc.py"},
    ]

    assert tag_verified_edit_success(history) is False
