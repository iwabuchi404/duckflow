"""Tests for S3-1 Phase 2: extended tool_history_policy compressors."""

import pytest
from companion.tool_history_policy import (
    compress_for_history,
    _compress_read_file,
    _compress_list_symbols,
    _compress_generic,
)


class TestCompressReadFile:
    def test_short_file_passthrough(self):
        """Short files should not be compressed."""
        content = "\n".join(f"line{i}" for i in range(1, 30))
        result = _compress_read_file(content)
        assert result == content

    def test_long_file_compressed(self):
        """Long files should be compressed with structure + head."""
        lines = []
        lines.append("import os")
        lines.append("")
        for i in range(100):
            lines.append(f"line{i}")
        lines.append("class MyClass:")
        lines.append("    pass")
        lines.append("def my_function():")
        lines.append("    pass")
        for i in range(100):
            lines.append(f"trailing{i}")
        content = "\n".join(lines)

        result = _compress_read_file(content)
        assert len(result) < len(content)
        assert "File:" in result
        assert "lines" in result
        assert "Structure" in result
        assert "class MyClass" in result
        assert "def my_function" in result
        assert "omitted" in result

    def test_no_structure_still_compresses(self):
        """Files without class/def should still get head + line count."""
        content = "\n".join(f"data line {i}" for i in range(100))
        result = _compress_read_file(content)
        assert len(result) < len(content)
        assert "File:" in result
        assert "100 lines" in result
        assert "omitted" in result

    def test_python_class_and_def_extracted(self):
        """Python class and def headers should be extracted with line numbers."""
        lines = ["import os", "", "class Foo:", "    pass", "", "def bar():", "    pass"]
        lines.extend([f"# line {i}" for i in range(100)])
        content = "\n".join(lines)
        result = _compress_read_file(content)
        assert "L3: class Foo:" in result
        assert "L6: def bar():" in result

    def test_js_function_extracted(self):
        """JS/TS function/class headers should be extracted."""
        lines = ['import { x } from "y";', "", "export class MyComponent {", "  render() {}", "}", "", "function helper() {", "  return 1;", "}"]
        lines.extend([f"// line {i}" for i in range(100)])
        content = "\n".join(lines)
        result = _compress_read_file(content)
        assert "MyComponent" in result
        assert "helper" in result


class TestCompressListSymbols:
    def test_short_list_passthrough(self):
        """Short symbol lists should not be compressed."""
        content = "class Foo\ndef bar\ndef baz"
        result = _compress_list_symbols(content)
        assert result == content

    def test_long_list_compressed(self):
        """Long symbol lists should be compressed with type counts."""
        lines = []
        for i in range(50):
            lines.append(f"class Class{i}")
        for i in range(30):
            lines.append(f"def func{i}")
        content = "\n".join(lines)

        result = _compress_list_symbols(content)
        assert len(result) < len(content)
        assert "Symbols:" in result
        assert "80 total" in result
        assert "class:" in result
        assert "def:" in result
        assert "omitted" in result

    def test_type_counts_correct(self):
        """Type aggregation should count correctly."""
        lines = ["class A", "class B", "def x", "def y", "def z", "interface I"]
        lines.extend([f"def extra{i}" for i in range(20)])
        content = "\n".join(lines)
        result = _compress_list_symbols(content)
        assert "class:" in result
        assert "def:" in result


class TestCompressGeneric:
    def test_short_passthrough(self):
        """Short outputs should not be compressed."""
        content = "short output"
        result = _compress_generic(content)
        assert result == content

    def test_long_single_line_truncated(self):
        """Very long single line should be truncated by chars."""
        content = "x" * 5000
        result = _compress_generic(content)
        assert len(result) < len(content)
        assert "chars omitted" in result

    def test_long_multi_line_head_tail(self):
        """Long multi-line output should get head/tail."""
        lines = [f"line{i}" for i in range(100)]
        content = "\n".join(lines)
        result = _compress_generic(content)
        assert len(result) < len(content)
        assert "100 lines" in result
        assert "line0" in result
        assert "line99" in result
        assert "omitted" in result
        assert "line50" not in result  # middle should be omitted


class TestCompressForHistoryDispatch:
    def test_read_file_dispatched(self):
        """compress_for_history should dispatch read_file correctly."""
        lines = [f"line{i}" for i in range(100)]
        lines.insert(5, "class Foo:")
        content = "\n".join(lines)
        result = compress_for_history("read_file", content)
        assert len(result) < len(content)
        assert "class Foo" in result

    def test_list_symbols_dispatched(self):
        """compress_for_history should dispatch list_symbols correctly."""
        lines = [f"class C{i}" for i in range(50)]
        content = "\n".join(lines)
        result = compress_for_history("list_symbols", content)
        assert len(result) < len(content)
        assert "Symbols:" in result

    def test_unknown_tool_generic_fallback(self):
        """Unknown tools with long output should get generic compression."""
        content = "\n".join(f"this is a longer line number {i} with extra text" for i in range(100))
        result = compress_for_history("unknown_tool", content)
        assert len(result) < len(content)
        assert "lines" in result

    def test_unknown_tool_short_passthrough(self):
        """Unknown tools with short output should pass through."""
        result = compress_for_history("unknown_tool", "short")
        assert result == "short"
