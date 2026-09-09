"""Tests that symbol tools resolve paths against the shared workspace root."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from companion.tools.file_ops import file_ops
from companion.tools.symbols import list_symbols, replace_function


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
