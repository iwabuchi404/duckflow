"""Tests for /config status command."""

import asyncio
import io
import pytest
from unittest.mock import MagicMock, patch
from rich.console import Console

from companion.modules.command_handler import CommandHandler


class FakeVitals:
    confidence = 0.8
    safety = 0.9
    memory = 0.7
    focus = 0.85


class FakeState:
    phase = MagicMock()
    phase.value = "executing"
    current_mode = MagicMock()
    current_mode.value = "planning"
    vitals = FakeVitals()
    turn_count = 5
    session_id = "20260622_120000_abcd"
    investigation_state = None

    def get_context_mode(self):
        return "planning"


class FakePacemaker:
    loop_count = 3
    max_loops = 20
    consecutive_errors = 0


class FakeLLM:
    model = "test-model-7b"
    provider = "groq"


class FakeAgent:
    state = FakeState()
    pacemaker = FakePacemaker()
    llm = FakeLLM()
    tools = {
        "response", "exit", "duck_call",
        "list_files", "find_symbol", "retrieve_result",
        "read_file", "edit_file", "write_file", "run_command",
        "replace_function",
    }


def _capture_panel_content(mock_console):
    """Extract rendered text from Panel objects passed to console.print."""
    buf = io.StringIO()
    real_console = Console(file=buf, width=200, force_terminal=False)
    for call in mock_console.print.call_args_list:
        panel = call.args[0]
        real_console.print(panel)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_config_status_runs_without_error():
    """_config_status should execute without raising."""
    handler = CommandHandler(FakeAgent())
    await handler._config_status()


@pytest.mark.asyncio
async def test_config_status_shows_mode_and_model():
    """_config_status should include mode and model in output."""
    handler = CommandHandler(FakeAgent())
    with patch("companion.modules.command_handler.ui") as mock_ui:
        mock_ui.console = MagicMock()
        await handler._config_status()
        texts = _capture_panel_content(mock_ui.console)
        assert "planning" in texts
        assert "test-model-7b" in texts


@pytest.mark.asyncio
async def test_config_status_shows_tools():
    """_config_status should show available tools for current mode."""
    handler = CommandHandler(FakeAgent())
    with patch("companion.modules.command_handler.ui") as mock_ui:
        mock_ui.console = MagicMock()
        await handler._config_status()
        texts = _capture_panel_content(mock_ui.console)
        assert "edit_file" in texts
        assert "read_file" in texts
        assert "replace_function" in texts


@pytest.mark.asyncio
async def test_config_status_shows_max_loops():
    """_config_status should show loop_count/max_loops."""
    handler = CommandHandler(FakeAgent())
    with patch("companion.modules.command_handler.ui") as mock_ui:
        mock_ui.console = MagicMock()
        await handler._config_status()
        texts = _capture_panel_content(mock_ui.console)
        assert "3/20" in texts


@pytest.mark.asyncio
async def test_config_status_shows_vitals():
    """_config_status should show vitals values."""
    handler = CommandHandler(FakeAgent())
    with patch("companion.modules.command_handler.ui") as mock_ui:
        mock_ui.console = MagicMock()
        await handler._config_status()
        texts = _capture_panel_content(mock_ui.console)
        assert "c=0.80" in texts
        assert "s=0.90" in texts


@pytest.mark.asyncio
async def test_config_help_includes_status():
    """Help text should mention /config status."""
    handler = CommandHandler(FakeAgent())
    with patch("companion.modules.command_handler.ui") as mock_ui:
        mock_ui.console = MagicMock()
        mock_ui.print_info = MagicMock()
        await handler.handle_config([])
        # The second handle_config prints usage via ui.print_info
        usage_text = str(mock_ui.print_info.call_args)
        assert "status" in usage_text.lower()
