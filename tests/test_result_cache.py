"""Tests for S3-1 Phase 1: ResultCache, retrieve_result tool, /result command."""

import asyncio
import pytest
from unittest.mock import MagicMock, patch

from companion.modules.result_cache import ResultCache, ResultCacheEntry


# --- ResultCache tests ---

class TestResultCache:
    def test_put_and_get(self):
        cache = ResultCache(max_size=5)
        cid = cache.put("read_file", {"path": "test.py"}, "line1\nline2\nline3")
        assert cid == "r1"
        entry = cache.get(cid)
        assert entry is not None
        assert entry.tool_name == "read_file"
        assert entry.full_result == "line1\nline2\nline3"
        assert entry.size_chars == 17

    def test_sequential_ids(self):
        cache = ResultCache(max_size=5)
        id1 = cache.put("read_file", {}, "a")
        id2 = cache.put("grep_files", {}, "b")
        id3 = cache.put("run_command", {}, "c")
        assert id1 == "r1"
        assert id2 == "r2"
        assert id3 == "r3"

    def test_lru_eviction(self):
        cache = ResultCache(max_size=3)
        cache.put("a", {}, "1")
        cache.put("b", {}, "2")
        cache.put("c", {}, "3")
        assert cache.size == 3
        # Access r1 to make it recently used
        cache.get("r1")
        # Add r4, should evict r2 (least recently used)
        cache.put("d", {}, "4")
        assert cache.get("r1") is not None  # r1 still exists
        assert cache.get("r2") is None      # r2 evicted
        assert cache.get("r3") is not None  # r3 still exists
        assert cache.get("r4") is not None  # r4 exists

    def test_get_nonexistent_returns_none(self):
        cache = ResultCache(max_size=5)
        assert cache.get("r99") is None

    def test_expired_message(self):
        cache = ResultCache(max_size=5)
        msg = cache.expired_message("r5")
        assert "r5" in msg
        assert "expired" in msg

    def test_get_range(self):
        cache = ResultCache(max_size=5)
        text = "\n".join(f"line{i}" for i in range(1, 21))  # 20 lines
        cid = cache.put("read_file", {"path": "test.py"}, text)
        result = cache.get_range(cid, 5, 10)
        assert result is not None
        assert "line5" in result
        assert "line10" in result
        assert "line4" not in result
        assert "line11" not in result
        assert "Lines 5-10 of 20" in result

    def test_get_range_clamps(self):
        cache = ResultCache(max_size=5)
        text = "a\nb\nc"
        cid = cache.put("read_file", {}, text)
        result = cache.get_range(cid, 1, 100)
        assert result is not None
        assert "a" in result
        assert "b" in result
        assert "c" in result

    def test_get_range_invalid(self):
        cache = ResultCache(max_size=5)
        text = "a\nb\nc"
        cid = cache.put("read_file", {}, text)
        result = cache.get_range(cid, 10, 20)
        assert "Invalid" in result

    def test_clear(self):
        cache = ResultCache(max_size=5)
        cache.put("a", {}, "1")
        cache.put("b", {}, "2")
        cache.clear()
        assert cache.size == 0
        # Counter should reset
        cid = cache.put("a", {}, "1")
        assert cid == "r1"

    def test_entries_property(self):
        cache = ResultCache(max_size=5)
        cache.put("a", {}, "1")
        cache.put("b", {}, "2")
        entries = cache.entries
        assert len(entries) == 2
        assert "r1" in entries
        assert "r2" in entries

    def test_max_size_one(self):
        cache = ResultCache(max_size=1)
        cache.put("a", {}, "1")
        cache.put("b", {}, "2")
        assert cache.size == 1
        assert cache.get("r1") is None
        assert cache.get("r2") is not None


# --- retrieve_result tool tests ---

class TestRetrieveResultTool:
    @pytest.mark.asyncio
    async def test_retrieve_full(self):
        from companion.tools.retrieve_result_tool import make_retrieve_result_tool

        agent = MagicMock()
        agent.result_cache = ResultCache(max_size=5)
        cid = agent.result_cache.put("read_file", {"path": "test.py"}, "full content here")

        tool = make_retrieve_result_tool(agent)
        result = await tool(cache_id=cid)
        assert result == "full content here"

    @pytest.mark.asyncio
    async def test_retrieve_expired(self):
        from companion.tools.retrieve_result_tool import make_retrieve_result_tool

        agent = MagicMock()
        agent.result_cache = ResultCache(max_size=5)

        tool = make_retrieve_result_tool(agent)
        result = await tool(cache_id="r99")
        assert "expired" in result
        assert "r99" in result

    @pytest.mark.asyncio
    async def test_retrieve_with_lines(self):
        from companion.tools.retrieve_result_tool import make_retrieve_result_tool

        agent = MagicMock()
        agent.result_cache = ResultCache(max_size=5)
        text = "\n".join(f"line{i}" for i in range(1, 21))
        cid = agent.result_cache.put("read_file", {}, text)

        tool = make_retrieve_result_tool(agent)
        result = await tool(cache_id=cid, lines="5-10")
        assert "line5" in result
        assert "line10" in result
        assert "line4" not in result

    @pytest.mark.asyncio
    async def test_retrieve_invalid_lines_format(self):
        from companion.tools.retrieve_result_tool import make_retrieve_result_tool

        agent = MagicMock()
        agent.result_cache = ResultCache(max_size=5)
        cid = agent.result_cache.put("read_file", {}, "content")

        tool = make_retrieve_result_tool(agent)
        result = await tool(cache_id=cid, lines="abc")
        assert "Invalid" in result


# --- /result command tests ---

class FakeAgentR:
    result_cache = ResultCache(max_size=5)


@pytest.mark.asyncio
async def test_result_command_empty():
    """handle_result with no args and empty cache should print info."""
    from companion.modules.command_handler import CommandHandler

    agent = FakeAgentR()
    agent.result_cache.clear()
    handler = CommandHandler(agent)
    with patch("companion.modules.command_handler.ui") as mock_ui:
        mock_ui.print_info = MagicMock()
        await handler.handle_result([])
        mock_ui.print_info.assert_called_once()


@pytest.mark.asyncio
async def test_result_command_list():
    """handle_result with no args and non-empty cache should show table."""
    from companion.modules.command_handler import CommandHandler

    agent = FakeAgentR()
    agent.result_cache.clear()
    agent.result_cache.put("read_file", {"path": "test.py"}, "content")
    handler = CommandHandler(agent)
    with patch("companion.modules.command_handler.ui") as mock_ui:
        mock_ui.console = MagicMock()
        await handler.handle_result([])
        assert mock_ui.console.print.call_count >= 1


@pytest.mark.asyncio
async def test_result_command_full():
    """handle_result with id should show full result."""
    from companion.modules.command_handler import CommandHandler

    agent = FakeAgentR()
    agent.result_cache.clear()
    cid = agent.result_cache.put("read_file", {"path": "test.py"}, "full content")
    handler = CommandHandler(agent)
    with patch("companion.modules.command_handler.ui") as mock_ui:
        mock_ui.print_result = MagicMock()
        await handler.handle_result([cid])
        mock_ui.print_result.assert_called_once_with("full content")


@pytest.mark.asyncio
async def test_result_command_line_range():
    """handle_result with id and line range should show range."""
    from companion.modules.command_handler import CommandHandler

    agent = FakeAgentR()
    agent.result_cache.clear()
    text = "\n".join(f"line{i}" for i in range(1, 21))
    cid = agent.result_cache.put("read_file", {}, text)
    handler = CommandHandler(agent)
    with patch("companion.modules.command_handler.ui") as mock_ui:
        mock_ui.print_result = MagicMock()
        await handler.handle_result([cid, "5-10"])
        result = mock_ui.print_result.call_args.args[0]
        assert "line5" in result
        assert "line10" in result


@pytest.mark.asyncio
async def test_result_command_expired():
    """handle_result with expired id should print error."""
    from companion.modules.command_handler import CommandHandler

    agent = FakeAgentR()
    agent.result_cache.clear()
    handler = CommandHandler(agent)
    with patch("companion.modules.command_handler.ui") as mock_ui:
        mock_ui.print_error = MagicMock()
        await handler.handle_result(["r99"])
        mock_ui.print_error.assert_called_once()
        assert "expired" in mock_ui.print_error.call_args.args[0]
