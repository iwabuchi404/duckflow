"""Tests for unified tool timeout in invoke_tool."""

import asyncio
import pytest

from companion.core_action_invocation import invoke_tool, filter_call_parameters
from companion.tools.results import ToolResult, ToolStatus


@pytest.mark.asyncio
async def test_invoke_tool_async_success():
    """Async tool should return result normally."""

    async def async_echo(msg: str) -> str:
        return f"echo: {msg}"

    result, dropped = await invoke_tool(async_echo, {"msg": "hello"})
    assert result == "echo: hello"
    assert dropped == set()


@pytest.mark.asyncio
async def test_invoke_tool_sync_success():
    """Sync tool should return result normally."""

    def sync_add(a: int, b: int) -> int:
        return a + b

    result, dropped = await invoke_tool(sync_add, {"a": 1, "b": 2})
    assert result == 3
    assert dropped == set()


@pytest.mark.asyncio
async def test_invoke_tool_drops_unexpected_params():
    """Parameters not in the function signature should be dropped."""

    async def async_one(x: int) -> int:
        return x * 2

    result, dropped = await invoke_tool(async_one, {"x": 5, "y": 10})
    assert result == 10
    assert dropped == {"y"}


@pytest.mark.asyncio
async def test_invoke_tool_timeout_returns_error():
    """Async tool exceeding timeout should return error string, not raise."""

    async def slow_tool() -> str:
        await asyncio.sleep(100)
        return "should never reach"

    # Temporarily set a very short timeout via config
    from companion.config.config_loader import config
    original = config._config.get("tool", {}).get("timeout")
    config._config.setdefault("tool", {})["timeout"] = 0.1

    try:
        result, dropped = await invoke_tool(slow_tool, {})
        assert isinstance(result, ToolResult)
        assert result.status == ToolStatus.ERROR
        assert "timed out" in result.content.lower()
        assert "0.1" in result.content
    finally:
        if original is not None:
            config._config["tool"]["timeout"] = original
        elif "timeout" in config._config.get("tool", {}):
            del config._config["tool"]["timeout"]


@pytest.mark.asyncio
async def test_invoke_tool_timeout_does_not_affect_sync():
    """Sync tools should not be affected by timeout (no asyncio.wait_for)."""

    def sync_fast() -> str:
        return "immediate"

    result, dropped = await invoke_tool(sync_fast, {})
    assert result == "immediate"


@pytest.mark.asyncio
async def test_invoke_tool_timeout_with_var_kw():
    """Tools with **kwargs should accept all parameters."""

    async def async_kwargs(**kw) -> dict:
        return kw

    result, dropped = await invoke_tool(async_kwargs, {"a": 1, "b": 2})
    assert result == {"a": 1, "b": 2}
    assert dropped == set()


def test_filter_call_parameters_basic():
    """filter_call_parameters should drop unknown params."""

    def sample(a: int, b: int) -> int:
        return a + b

    filtered, dropped = filter_call_parameters(sample, {"a": 1, "b": 2, "c": 3})
    assert filtered == {"a": 1, "b": 2}
    assert dropped == {"c"}


def test_filter_call_parameters_var_kw():
    """filter_call_parameters should pass all params if **kwargs present."""

    def sample(**kw) -> dict:
        return kw

    filtered, dropped = filter_call_parameters(sample, {"a": 1, "b": 2})
    assert filtered == {"a": 1, "b": 2}
    assert dropped == set()
