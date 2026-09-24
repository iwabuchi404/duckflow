"""Tests that symbol tools resolve paths against the shared workspace root."""

import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from companion.tools.file_ops import file_ops
from companion.tools.results import ToolResult, ToolStatus
from companion.tools.symbols import find_symbol, list_symbols, replace_function


@pytest.mark.asyncio
async def test_list_symbols_uses_workspace_root(tmp_path: Path) -> None:
    """list_symbols must find files under file_ops.workspace_root."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "mod.py").write_text("def alpha() -> int:\n    return 1\n", encoding="utf-8")

    file_ops.set_workspace_root(str(tmp_path))
    try:
        result = await list_symbols("pkg/mod.py")
    finally:
        file_ops.set_workspace_root(".")

    assert "alpha" in result


@pytest.mark.asyncio
async def test_replace_function_uses_workspace_root(tmp_path: Path) -> None:
    """replace_function must edit files under file_ops.workspace_root."""
    target = tmp_path / "mod.py"
    target.write_text("def helo() -> str:\n    return 'hi'\n", encoding="utf-8")

    file_ops.set_workspace_root(str(tmp_path))
    try:
        result = await replace_function(
            "mod.py", "helo", "def helo() -> str:\n    return 'hello'\n"
        )
    finally:
        file_ops.set_workspace_root(".")

    assert not str(result).startswith("::status error")
    assert "hello" in target.read_text(encoding="utf-8")


def test_symbol_tools_do_not_expose_workspace_root() -> None:
    """Model-facing symbol tools must use only the shared workspace root."""
    for tool in (find_symbol, list_symbols, replace_function):
        assert "workspace_root" not in inspect.signature(tool).parameters


@pytest.mark.asyncio
async def test_list_symbols_rejects_parent_escape(tmp_path: Path) -> None:
    """list_symbols must not read a source file outside the workspace."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("def secret():\n    return 1\n", encoding="utf-8")
    previous_root = file_ops.workspace_root
    file_ops.set_workspace_root(str(workspace))
    try:
        result = await list_symbols("../outside.py")
    finally:
        file_ops.set_workspace_root(str(previous_root))

    assert isinstance(result, ToolResult)
    assert result.status == ToolStatus.ERROR
    assert "Outside workspace" in result.content


@pytest.mark.asyncio
async def test_replace_function_rejects_parent_escape(tmp_path: Path) -> None:
    """replace_function must not modify a source file outside the workspace."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.py"
    original = "def secret():\n    return 1\n"
    outside.write_text(original, encoding="utf-8")
    previous_root = file_ops.workspace_root
    file_ops.set_workspace_root(str(workspace))
    try:
        result = await replace_function(
            "../outside.py", "secret", "def secret():\n    return 2\n"
        )
    finally:
        file_ops.set_workspace_root(str(previous_root))

    assert isinstance(result, ToolResult)
    assert result.status == ToolStatus.ERROR
    assert outside.read_text(encoding="utf-8") == original
