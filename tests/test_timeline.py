"""Tests for S3-11: Timeline tracker, EventLogger, and /timeline command."""

import json
import time
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from companion.modules.timeline import TimelineTracker, TimelineEntry
from companion.modules.event_logger import EventLogger
from companion.modules.command_handler import CommandHandler


# --- TimelineTracker tests ---

class TestTimelineTracker:
    def test_record_and_entries(self):
        tl = TimelineTracker(max_entries=10)
        tl.record("read_file", 100.0, 100.5, False, "file contents here")
        assert len(tl.entries) == 1
        e = tl.entries[0]
        assert e.action_name == "read_file"
        assert e.duration_ms == pytest.approx(500.0)
        assert e.is_error is False

    def test_max_entries_cap(self):
        tl = TimelineTracker(max_entries=3)
        for i in range(5):
            tl.record(f"action_{i}", 100.0, 100.1, False, "ok")
        assert len(tl.entries) == 3
        assert tl.entries[0].action_name == "action_2"
        assert tl.entries[2].action_name == "action_4"

    def test_error_count(self):
        tl = TimelineTracker()
        tl.record("ok_action", 1.0, 1.1, False, "success")
        tl.record("bad_action", 2.0, 2.1, True, "failed")
        assert tl.total_actions == 2
        assert tl.error_count == 1

    def test_avg_duration(self):
        tl = TimelineTracker()
        tl.record("a", 0.0, 0.1, False, "x")
        tl.record("b", 0.0, 0.2, False, "y")
        assert tl.avg_duration_ms == pytest.approx(150.0)

    def test_total_duration(self):
        tl = TimelineTracker()
        tl.record("a", 0.0, 0.1, False, "x")
        tl.record("b", 0.0, 0.3, False, "y")
        assert tl.total_duration_ms == pytest.approx(400.0)

    def test_clear(self):
        tl = TimelineTracker()
        tl.record("a", 0.0, 0.1, False, "x")
        tl.clear()
        assert len(tl.entries) == 0
        assert tl.total_actions == 0

    def test_empty_stats(self):
        tl = TimelineTracker()
        assert tl.avg_duration_ms == 0.0
        assert tl.total_duration_ms == 0.0
        assert tl.error_count == 0

    def test_result_summary_truncation(self):
        tl = TimelineTracker()
        long_text = "x" * 200
        tl.record("a", 0.0, 0.1, False, long_text)
        assert len(tl.entries[0].result_summary) == 123  # 120 + "..."


# --- EventLogger tests ---

class TestEventLogger:
    def test_log_writes_jsonl(self, tmp_path):
        log_file = tmp_path / "events.jsonl"
        el = EventLogger()
        el._log_path = log_file
        el._enabled = True

        el.log("test_event", {"key": "value", "num": 42})

        assert log_file.exists()
        lines = log_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        event = json.loads(lines[0])
        assert event["type"] == "test_event"
        assert event["key"] == "value"
        assert event["num"] == 42
        assert "ts" in event

    def test_log_action_start_end(self, tmp_path):
        log_file = tmp_path / "events.jsonl"
        el = EventLogger()
        el._log_path = log_file
        el._enabled = True

        el.log_action_start("read_file", {"path": "test.py"})
        el.log_action_end("read_file", 150.5, is_error=False, result_len=100)

        lines = log_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
        start_event = json.loads(lines[0])
        end_event = json.loads(lines[1])
        assert start_event["type"] == "action_start"
        assert start_event["action"] == "read_file"
        assert end_event["type"] == "action_end"
        assert end_event["duration_ms"] == 150.5
        assert end_event["is_error"] is False

    def test_disabled_does_not_write(self, tmp_path):
        log_file = tmp_path / "events.jsonl"
        el = EventLogger()
        el._log_path = log_file
        el._enabled = False

        el.log("test", {"k": "v"})
        assert not log_file.exists()

    def test_log_llm_response(self, tmp_path):
        log_file = tmp_path / "events.jsonl"
        el = EventLogger()
        el._log_path = log_file
        el._enabled = True

        el.log_llm_response("gpt-4o", 2500.0, input_tokens=500, output_tokens=200, retry_count=1)

        lines = log_file.read_text(encoding="utf-8").strip().split("\n")
        event = json.loads(lines[0])
        assert event["type"] == "llm_response"
        assert event["model"] == "gpt-4o"
        assert event["input_tokens"] == 500
        assert event["retry_count"] == 1


# --- /timeline command tests ---

class FakeVitalsT:
    confidence = 0.8
    safety = 0.9
    memory = 0.7
    focus = 0.85


class FakeStateT:
    phase = MagicMock()
    phase.value = "executing"
    current_mode = MagicMock()
    current_mode.value = "planning"
    vitals = FakeVitalsT()
    turn_count = 5
    session_id = "test"
    investigation_state = None
    conversation_history = []

    def get_context_mode(self):
        return "planning"


class FakePacemakerT:
    loop_count = 3
    max_loops = 20
    consecutive_errors = 0


class FakeLLMT:
    model = "test-model"
    provider = "groq"
    usage_stats = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cost_estimate": 0.0, "retry_count": 0, "retry_successes": 0}


class FakeAgentT:
    state = FakeStateT()
    pacemaker = FakePacemakerT()
    llm = FakeLLMT()
    tools = {"read_file", "edit_file"}
    timeline = TimelineTracker(max_entries=50)
    memory_manager = MagicMock()
    memory_manager.max_tokens = 10000
    memory_manager.estimate_history_tokens = MagicMock(return_value=80)


@pytest.mark.asyncio
async def test_timeline_empty():
    """handle_timeline with no entries should print info message."""
    handler = CommandHandler(FakeAgentT())
    with patch("companion.modules.command_handler.ui") as mock_ui:
        mock_ui.print_info = MagicMock()
        await handler.handle_timeline([])
        mock_ui.print_info.assert_called_once()


@pytest.mark.asyncio
async def test_timeline_with_entries():
    """handle_timeline with entries should render table."""
    agent = FakeAgentT()
    agent.timeline.record("read_file", 100.0, 100.5, False, "file contents")
    agent.timeline.record("edit_file", 200.0, 201.0, True, "error occurred")
    handler = CommandHandler(agent)
    with patch("companion.modules.command_handler.ui") as mock_ui:
        mock_ui.console = MagicMock()
        await handler.handle_timeline([])
        assert mock_ui.console.print.call_count >= 1


@pytest.mark.asyncio
async def test_tokens_includes_latency():
    """handle_tokens should include action latency stats when timeline has data."""
    import io
    from rich.console import Console
    agent = FakeAgentT()
    agent.timeline.record("read_file", 100.0, 100.5, False, "contents")
    handler = CommandHandler(agent)
    with patch("companion.modules.command_handler.ui") as mock_ui:
        mock_ui.console = MagicMock()
        handler._build_current_messages = MagicMock(return_value=[])
        await handler.handle_tokens([])
        # Render panels to text
        buf = io.StringIO()
        real_console = Console(file=buf, width=200, force_terminal=False)
        for call in mock_ui.console.print.call_args_list:
            real_console.print(call.args[0])
        text = buf.getvalue()
        assert "Action latency" in text
        assert "Avg action duration" in text
