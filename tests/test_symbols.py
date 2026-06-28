"""Tests for S3-2: code navigation and context design.

Tests for:
- grep_files: case_sensitive, symbol headers, file grouping, truncation
- symbols.py: list_symbols, find_definition
"""

import asyncio
import tempfile
import pytest
from pathlib import Path

from companion.tools.file_ops import FileOps
from companion.tools.results import ToolResult, ToolStatus
from companion.tools.symbols import list_symbols, find_definition, _extract_symbols


@pytest.fixture
def workspace(tmp_path):
    """Create a temporary workspace with test Python files."""
    (tmp_path / "test_pkg").mkdir()
    (tmp_path / "test_pkg" / "__init__.py").write_text("")

    (tmp_path / "test_pkg" / "example.py").write_text(
        '''"""Example module for testing."""


def top_level_func(x: int) -> str:
    """A top-level function."""
    return str(x)


class MyClass:
    """A test class."""

    def method_a(self):
        """Method A."""
        return "a"

    def method_b(self, y):
        """Method B."""
        return y * 2


async def async_func():
    """An async function."""
    pass


def nested_func():
    """Outer function."""

    def inner():
        """Inner function."""
        return 42

    return inner()
''')

    (tmp_path / "test_pkg" / "other.py").write_text(
        '''"""Another module."""


def shared_name():
    """Shared name in other.py."""
    return "other"


def unique_func():
    """Only in other.py."""
    return 42
''')

    return tmp_path


@pytest.fixture
def file_ops(workspace):
    """Create FileOps instance with the test workspace."""
    return FileOps(workspace_root=workspace)


# --- grep_files: case_sensitive ---


@pytest.mark.asyncio
async def test_grep_case_sensitive_default(file_ops):
    """Default is case-sensitive - should not match different case."""
    result = await file_ops.grep_files("DEF", path="test_pkg", include="*.py")
    assert "No matches" in result


@pytest.mark.asyncio
async def test_grep_case_insensitive(file_ops):
    """case_sensitive=False should match regardless of case."""
    result = await file_ops.grep_files("def", path="test_pkg", include="*.py", case_sensitive=False)
    assert "match(es) found" in result
    assert "def top_level_func" in result


# --- grep_files: symbol headers ---


@pytest.mark.asyncio
async def test_grep_symbol_headers_shown(file_ops):
    """grep results should show enclosing symbol header for Python files."""
    result = await file_ops.grep_files("return", path="test_pkg/example.py")
    assert "[def top_level_func" in result or "[    def top_level_func" in result
    assert "[def method_a" in result or "[    def method_a" in result


@pytest.mark.asyncio
async def test_grep_file_grouping(file_ops):
    """grep results should be grouped by file with file headers."""
    result = await file_ops.grep_files("def", path="test_pkg", include="*.py")
    assert "example.py" in result
    assert "other.py" in result
    assert "---" in result  # file group headers


@pytest.mark.asyncio
async def test_grep_truncation_explicit(file_ops):
    """Truncation should be explicitly stated."""
    result = await file_ops.grep_files(".", path="test_pkg", include="*.py", max_results=2)
    assert "truncated" in result.lower()


@pytest.mark.asyncio
async def test_grep_no_matches(file_ops):
    """No matches should return a clear message."""
    result = await file_ops.grep_files("NONEXISTENT_PATTERN_XYZ", path="test_pkg")
    assert "No matches" in result


# --- symbols.py: list_symbols ---


@pytest.mark.asyncio
async def test_list_symbols_basic(workspace):
    """list_symbols should return all functions and classes."""
    result = await list_symbols("test_pkg/example.py", workspace_root=str(workspace))
    assert "top_level_func" in result
    assert "MyClass" in result
    assert "method_a" in result
    assert "async_func" in result


@pytest.mark.asyncio
async def test_list_symbols_line_ranges(workspace):
    """list_symbols should include line ranges."""
    result = await list_symbols("test_pkg/example.py", workspace_root=str(workspace))
    assert "lines" in result


@pytest.mark.asyncio
async def test_list_symbols_docstring(workspace):
    """list_symbols should include docstring first line."""
    result = await list_symbols("test_pkg/example.py", workspace_root=str(workspace))
    assert "A top-level function" in result


@pytest.mark.asyncio
async def test_list_symbols_nested(workspace):
    """list_symbols should show nested functions with qualified names."""
    result = await list_symbols("test_pkg/example.py", workspace_root=str(workspace))
    assert "nested_func.inner" in result


@pytest.mark.asyncio
async def test_list_symbols_non_python(workspace):
    """list_symbols should reject non-Python files."""
    (workspace / "test.txt").write_text("not python")
    result = await list_symbols("test.txt", workspace_root=str(workspace))
    assert isinstance(result, ToolResult)
    assert result.status == ToolStatus.ERROR
    assert "not a python file" in result.content.lower()


@pytest.mark.asyncio
async def test_list_symbols_not_found(workspace):
    """list_symbols should handle missing files."""
    result = await list_symbols("nonexistent.py", workspace_root=str(workspace))
    assert isinstance(result, ToolResult)
    assert result.status == ToolStatus.ERROR
    assert "not found" in result.content.lower()


# --- symbols.py: find_definition ---


@pytest.mark.asyncio
async def test_find_definition_single(workspace):
    """find_definition should find a unique symbol."""
    result = await find_definition("unique_func", scope="test_pkg", workspace_root=str(workspace))
    assert "other.py" in result
    assert "def unique_func" in result


@pytest.mark.asyncio
async def test_find_definition_multiple(workspace):
    """find_definition should list all matches for shared names."""
    result = await find_definition("shared_name", scope="test_pkg", workspace_root=str(workspace))
    assert "1 found" in result or "found" in result
    assert "other.py" in result


@pytest.mark.asyncio
async def test_find_definition_not_found(workspace):
    """find_definition should report when no definition is found."""
    result = await find_definition("NONEXISTENT_XYZ", scope="test_pkg", workspace_root=str(workspace))
    assert "No definition" in result


@pytest.mark.asyncio
async def test_find_definition_class_method(workspace):
    """find_definition should find class methods."""
    result = await find_definition("method_a", scope="test_pkg", workspace_root=str(workspace))
    assert "example.py" in result
    assert "method_a" in result


# --- _extract_symbols unit test ---


def test_extract_symbols_handles_syntax_error(tmp_path):
    """_extract_symbols should return empty list for files with syntax errors."""
    bad_file = tmp_path / "bad.py"
    bad_file.write_text("def broken(:\n  pass")
    result = _extract_symbols(bad_file, bad_file.read_text().splitlines())
    assert result == []
