import pytest
import asyncio
from pathlib import Path
from companion.tools.file_ops import FileOps

@pytest.fixture
def file_ops(tmp_path):
    ops = FileOps()
    ops.workspace_root = tmp_path
    return ops

@pytest.mark.asyncio
async def test_extract_find_replace_fallback_single_line(file_ops):
    # Test v2.2 single-line fallback
    text = "find: old_code\nreplace: new_code\noccurrence: 2"
    res = file_ops._extract_find_replace_fallback(text)
    assert res == {'find': 'old_code', 'replace': 'new_code', 'occurrence': 2}

@pytest.mark.asyncio
async def test_extract_find_replace_fallback_mixed(file_ops):
    # Test mixed multi-line and single-line
    text = "find: |\n    multi\n    line\nreplace: single_line"
    res = file_ops._extract_find_replace_fallback(text)
    assert res == {'find': 'multi\nline', 'replace': 'single_line'}

@pytest.mark.asyncio
async def test_sanitize_content(file_ops):
    # Test sanitization guard (v2.2)
    leaked_content = """def my_func():
    :: response @ Hello
    print("Leak above")
    >>>
    return True
    <<<
    %%%
"""
    expected = """def my_func():
    print("Leak above")
    return True
"""
    # Note: currently my implementation skips lines starting with ::, >>>, <<<, %%%
    # The actual behavior depends on combined_pattern.match(line)
    sanitized = file_ops._sanitize_content(leaked_content)
    assert ":: response" not in sanitized
    assert ">>>" not in sanitized
    assert "<<<" not in sanitized
    assert "%%%" not in sanitized
    assert 'print("Leak above")' in sanitized

@pytest.mark.asyncio
async def test_write_file_sanitization(file_ops, tmp_path):
    # Test that write_file applies sanitization
    path = "test.py"
    content = ":: leak\nvalid_code = 123\n>>>"
    await file_ops.write_file(path, content)
    
    written = (tmp_path / path).read_text()
    assert written == "valid_code = 123"

@pytest.mark.asyncio
async def test_edit_file_sanitization(file_ops, tmp_path):
    # Test that edit_file applies sanitization to the final result
    path = "sample.py"
    (tmp_path / path).write_text("old_line = 1\n", encoding='utf-8')
    
    # Replacement contains a leak
    await file_ops.edit_file(
        path=path,
        find="old_line = 1",
        replace="new_line = 2\n:: leak_marker\n>>>"
    )
    
    written = (tmp_path / path).read_text()
    assert "new_line = 2" in written
    assert ":: leak_marker" not in written
    assert ">>>" not in written
