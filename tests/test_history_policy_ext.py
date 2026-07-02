"""Tests for S3-1 Phase 2: extended tool_history_policy compressors."""

import pytest
from companion.tool_history_policy import (
    compress_for_history,
    _compress_list_symbols,
    _compress_generic,
    _COMPRESSION_PROFILES,
)

_STANDARD = _COMPRESSION_PROFILES["standard"]


class TestCompressListSymbols:
    def test_short_list_passthrough(self):
        """Short symbol lists should not be compressed."""
        content = "class Foo\ndef bar\ndef baz"
        result = _compress_list_symbols(content, _STANDARD)
        assert result == content

    def test_long_list_compressed(self):
        """Long symbol lists should be compressed with type counts."""
        lines = []
        for i in range(50):
            lines.append(f"class Class{i}")
        for i in range(30):
            lines.append(f"def func{i}")
        content = "\n".join(lines)

        result = _compress_list_symbols(content, _STANDARD)
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
        result = _compress_list_symbols(content, _STANDARD)
        assert "class:" in result
        assert "def:" in result


class TestCompressGeneric:
    def test_short_passthrough(self):
        """Short outputs should not be compressed."""
        content = "short output"
        result = _compress_generic(content, _STANDARD)
        assert result == content

    def test_long_single_line_truncated(self):
        """Very long single line should be truncated by chars."""
        content = "x" * 5000
        result = _compress_generic(content, _STANDARD)
        assert len(result) < len(content)
        assert "chars omitted" in result

    def test_long_multi_line_head_tail(self):
        """Long multi-line output should get head/tail."""
        lines = [f"line{i}" for i in range(100)]
        content = "\n".join(lines)
        result = _compress_generic(content, _STANDARD)
        assert len(result) < len(content)
        assert "100 lines" in result
        assert "line0" in result
        assert "line99" in result
        assert "omitted" in result
        assert "line50" not in result  # middle should be omitted


class TestCompressForHistoryDispatch:
    def test_read_file_generic_fallback(self):
        """read_file should use generic fallback (no tool-specific compressor)."""
        content = "\n".join(f"this is a longer line number {i} with extra text" for i in range(100))
        result = compress_for_history("read_file", content)
        # Should use generic fallback, not a read_file-specific compressor
        assert len(result) < len(content)
        assert "lines" in result
        assert "Structure" not in result  # no structure extraction

    def test_find_symbol_dispatched(self):
        """compress_for_history should dispatch find_symbol correctly."""
        lines = [f"class C{i}" for i in range(50)]
        content = "\n".join(lines)
        result = compress_for_history("find_symbol", content)
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
