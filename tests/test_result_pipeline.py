"""Tests for S3-1 Phase 3: multi-stage result pipeline."""

import pytest
from unittest.mock import MagicMock, patch

from companion.execution.result_pipeline import summarize_result


class FakeAgent:
    """Minimal agent with result_cache and sub_llm_manager."""
    def __init__(self):
        from companion.modules.result_cache import ResultCache
        self.result_cache = ResultCache(max_size=10)
        self.sub_llm_manager = MagicMock()


class TestSummarizeResult:
    def test_short_result_passthrough(self):
        """Results under threshold should pass through unchanged."""
        agent = FakeAgent()
        result, cache_id = summarize_result("read_file", "short content", agent)
        assert result == "short content"
        assert cache_id is None

    def test_excluded_tool_passthrough(self):
        """Excluded tools should never be summarized."""
        agent = FakeAgent()
        long_text = "x" * 5000
        result, cache_id = summarize_result("response", long_text, agent)
        assert result == long_text
        assert cache_id is None

    def test_long_result_mechanical_summary(self):
        """Long results should be mechanically summarized and cached."""
        agent = FakeAgent()
        # Create a long read_file result with structure (>2000 chars)
        lines = ["import os", ""]
        lines.extend([f"line{i}" for i in range(200)])
        lines.append("class MyClass:")
        lines.append("    pass")
        lines.append("def my_function():")
        lines.append("    pass")
        lines.extend([f"trailing{i}" for i in range(200)])
        content = "\n".join(lines)
        assert len(content) > 2000

        result, cache_id = summarize_result("read_file", content, agent)
        assert len(result) < len(content)
        assert cache_id is not None
        assert "retrieve_result" in result
        # Original should be in cache
        entry = agent.result_cache.get(cache_id)
        assert entry is not None
        assert entry.full_result == content

    def test_mechanical_under_threshold_caches(self):
        """If mechanical summary brings it under threshold, still cache original."""
        agent = FakeAgent()
        # grep_files with many matches in few files - compresses well
        lines = []
        for f in range(5):
            for m in range(50):
                lines.append(f"src/file{f}.py:{m+1}: match content line {m}")
        content = "\n".join(lines)
        assert len(content) > 2000

        result, cache_id = summarize_result("grep_files", content, agent)
        assert len(result) < len(content)
        assert cache_id is not None
        assert "retrieve_result" in result

    def test_generic_fallback_caches(self):
        """Unknown tools with long output should get generic compression + cache."""
        agent = FakeAgent()
        content = "\n".join(f"this is a longer line number {i} with extra text" for i in range(100))
        assert len(content) > 2000

        result, cache_id = summarize_result("unknown_tool", content, agent)
        assert len(result) < len(content)
        assert cache_id is not None

    def test_sub_llm_disabled_by_default(self):
        """SubLLM should not be called when disabled (default)."""
        agent = FakeAgent()
        content = "x" * 5000
        with patch("companion.execution.result_pipeline._is_sub_llm_enabled", return_value=False):
            result, cache_id = summarize_result("unknown_tool", content, agent)
            agent.sub_llm_manager.summarize.assert_not_called()

    def test_sub_llm_enabled_called(self):
        """When enabled, SubLLM should be called for results still over threshold."""
        agent = FakeAgent()
        # Create content that mechanical compression can't reduce enough
        content = "x" * 5000
        agent.sub_llm_manager.summarize = MagicMock(return_value="Summarized content")

        with patch("companion.execution.result_pipeline._is_sub_llm_enabled", return_value=True):
            result, cache_id = summarize_result("unknown_tool", content, agent)
            # SubLLM should have been called
            agent.sub_llm_manager.summarize.assert_called_once()
            assert "Summarized content" in result
            assert cache_id is not None

    def test_sub_llm_failure_falls_back_to_mechanical(self):
        """If SubLLM fails, should fall back to mechanical summary."""
        agent = FakeAgent()
        content = "x" * 5000
        agent.sub_llm_manager.summarize = MagicMock(side_effect=Exception("LLM error"))

        with patch("companion.execution.result_pipeline._is_sub_llm_enabled", return_value=True):
            result, cache_id = summarize_result("unknown_tool", content, agent)
            # Should still return a cached result
            assert cache_id is not None
            assert "retrieve_result" in result

    def test_retrieve_result_excluded(self):
        """retrieve_result itself should not be summarized."""
        agent = FakeAgent()
        long_text = "x" * 5000
        result, cache_id = summarize_result("retrieve_result", long_text, agent)
        assert result == long_text
        assert cache_id is None
