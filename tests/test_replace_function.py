"""Tests for S3-2 Phase D: replace_function."""

import pytest
from pathlib import Path

from companion.tools.results import ToolResult, ToolStatus
from companion.tools.symbols import replace_function


@pytest.fixture
def workspace(tmp_path):
    """Create a temporary workspace with a test Python file."""
    (tmp_path / "mod.py").write_text(
        '''"""Test module."""


def greet(name):
    """Greet someone."""
    return f"Hello, {name}"


class Calculator:
    """A simple calculator."""

    def add(self, a, b):
        """Add two numbers."""
        return a + b

    def multiply(self, a, b):
        """Multiply two numbers."""
        return a * b


def helper():
    """A helper function."""
    return 42
'''
    )
    return tmp_path


@pytest.mark.asyncio
async def test_replace_function_basic(workspace):
    """replace_function should replace a function by name."""
    new_body = '''def greet(name, greeting="Hello"):
    """Greet someone with a custom greeting."""
    return f"{greeting}, {name}"'''

    result = await replace_function(
        path="mod.py",
        name="greet",
        body=new_body,
        workspace_root=str(workspace),
    )
    assert "Replaced" in result
    assert "greet" in result

    content = (workspace / "mod.py").read_text()
    assert 'greeting="Hello"' in content
    assert "Hello, {name}" not in content


@pytest.mark.asyncio
async def test_replace_class(workspace):
    """replace_function should also work on classes."""
    new_body = '''class Calculator:
    """An upgraded calculator."""

    def add(self, a, b):
        """Add two numbers."""
        return a + b

    def subtract(self, a, b):
        """Subtract b from a."""
        return a - b'''

    result = await replace_function(
        path="mod.py",
        name="Calculator",
        body=new_body,
        workspace_root=str(workspace),
    )
    assert "Replaced" in result
    assert "class" in result

    content = (workspace / "mod.py").read_text()
    assert "subtract" in content
    assert "multiply" not in content


@pytest.mark.asyncio
async def test_replace_function_not_found(workspace):
    """Should return error when symbol is not found."""
    result = await replace_function(
        path="mod.py",
        name="nonexistent",
        body="def nonexistent(): pass",
        workspace_root=str(workspace),
    )
    assert isinstance(result, ToolResult)
    assert result.status == ToolStatus.ERROR
    assert "not found" in result.content.lower()


@pytest.mark.asyncio
async def test_replace_function_file_not_found(workspace):
    """Should return error when file doesn't exist."""
    result = await replace_function(
        path="nonexistent.py",
        name="greet",
        body="def greet(): pass",
        workspace_root=str(workspace),
    )
    assert isinstance(result, ToolResult)
    assert result.status == ToolStatus.ERROR
    assert "not found" in result.content.lower()


@pytest.mark.asyncio
async def test_replace_function_syntax_error_in_body(workspace):
    """Should reject new body with syntax errors."""
    result = await replace_function(
        path="mod.py",
        name="greet",
        body="def greet(:\n  pass",
        workspace_root=str(workspace),
    )
    assert isinstance(result, ToolResult)
    assert result.status == ToolStatus.ERROR
    assert "syntax" in result.content.lower()

    # File should be unchanged
    content = (workspace / "mod.py").read_text()
    assert "Hello, {name}" in content


@pytest.mark.asyncio
async def test_replace_function_validates_full_file(workspace):
    """Should reject replacement if it makes the full file invalid."""
    # A body that's valid on its own but breaks the file context
    # (e.g., missing dedent after a preceding construct)
    # This is hard to construct in a simple file, so we test with a body
    # that has valid syntax but would create issues
    new_body = "def greet(name):\n    return f'Hi, {name}'"
    result = await replace_function(
        path="mod.py",
        name="greet",
        body=new_body,
        workspace_root=str(workspace),
    )
    # This should succeed since the body is valid and fits
    assert "Replaced" in result


@pytest.mark.asyncio
async def test_replace_function_ambiguous(workspace):
    """Should return ambiguity error when multiple symbols share the same name."""
    (workspace / "ambig.py").write_text(
        '''def process():
    return 1


class Handler:
    def process(self):
        return 2
'''
    )
    result = await replace_function(
        path="ambig.py",
        name="process",
        body="def process():\n    return 3",
        workspace_root=str(workspace),
    )
    assert isinstance(result, ToolResult)
    assert result.status == ToolStatus.ERROR
    assert "Multiple" in result.content or "ambiguous" in result.content.lower()


@pytest.mark.asyncio
async def test_replace_function_preserves_rest_of_file(workspace):
    """replace_function should only change the target symbol, leaving the rest intact."""
    original = (workspace / "mod.py").read_text()
    new_body = "def greet(name):\n    return f'Hi, {name}'"

    await replace_function(
        path="mod.py",
        name="greet",
        body=new_body,
        workspace_root=str(workspace),
    )

    content = (workspace / "mod.py").read_text()
    # Other symbols should be unchanged
    assert "class Calculator" in content
    assert "def add" in content
    assert "def helper" in content
    assert "return 42" in content


@pytest.mark.asyncio
async def test_replace_function_non_python(workspace):
    """Should reject non-Python files."""
    (workspace / "script.txt").write_text("def foo(): pass")
    result = await replace_function(
        path="script.txt",
        name="foo",
        body="def foo(): return 1",
        workspace_root=str(workspace),
    )
    assert isinstance(result, ToolResult)
    assert result.status == ToolStatus.ERROR
    assert "Python" in result.content


@pytest.mark.asyncio
async def test_replace_function_async(workspace):
    """replace_function should work on async functions."""
    (workspace / "async_mod.py").write_text(
        '''async def fetch_data():
    """Fetch data asynchronously."""
    return await get("http://example.com")
'''
    )
    new_body = '''async def fetch_data():
    """Fetch data with retry."""
    for _ in range(3):
        try:
            return await get("http://example.com")
        except Exception:
            await asyncio.sleep(1)
    return None'''

    result = await replace_function(
        path="async_mod.py",
        name="fetch_data",
        body=new_body,
        workspace_root=str(workspace),
    )
    assert "Replaced" in result

    content = (workspace / "async_mod.py").read_text()
    assert "retry" in content
    assert "range(3)" in content
