import pytest

from companion.core_action_invocation import filter_call_parameters
from companion.core_action_invocation import invoke_tool


def test_filter_call_parameters_drops_unaccepted_keys() -> None:
    """
    Parameters not accepted by the tool callable should be dropped.

    Args:
        None.

    Returns:
        None.
    """

    def tool(path: str, content: str) -> str:
        """Test callable with explicit parameters."""
        return f"{path}:{content}"

    filtered, dropped = filter_call_parameters(
        tool,
        {"path": "a.py", "content": "x", "unexpected": "y"},
    )

    assert filtered == {"path": "a.py", "content": "x"}
    assert dropped == {"unexpected"}


def test_filter_call_parameters_preserves_all_keys_for_kwargs() -> None:
    """
    Callables accepting **kwargs should receive all model parameters.

    Args:
        None.

    Returns:
        None.
    """

    def tool(**kwargs: str) -> dict[str, str]:
        """Test callable accepting arbitrary keyword arguments."""
        return kwargs

    filtered, dropped = filter_call_parameters(
        tool,
        {"path": "a.py", "extra": "ok"},
    )

    assert filtered == {"path": "a.py", "extra": "ok"}
    assert dropped == set()


async def _async_tool(path: str) -> str:
    """Async tool used by invoke_tool tests."""
    return f"async:{path}"


def _sync_tool(path: str) -> str:
    """Sync tool used by invoke_tool tests."""
    return f"sync:{path}"


@pytest.mark.asyncio
async def test_invoke_tool_calls_sync_tool_with_filtered_params() -> None:
    """
    invoke_tool should call sync tools and return dropped parameters.

    Args:
        None.

    Returns:
        None.
    """
    result, dropped = await invoke_tool(
        _sync_tool,
        {"path": "a.py", "extra": "drop"},
    )

    assert result == "sync:a.py"
    assert dropped == {"extra"}


@pytest.mark.asyncio
async def test_invoke_tool_calls_async_tool_with_filtered_params() -> None:
    """
    invoke_tool should await async tools and return dropped parameters.

    Args:
        None.

    Returns:
        None.
    """
    result, dropped = await invoke_tool(
        _async_tool,
        {"path": "a.py", "extra": "drop"},
    )

    assert result == "async:a.py"
    assert dropped == {"extra"}
