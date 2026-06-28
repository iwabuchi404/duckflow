"""
Callable invocation helpers for DuckAgent action execution.
"""

import asyncio
import inspect
import logging
from typing import Any, Callable

from companion.config.config_loader import config

logger = logging.getLogger(__name__)


def filter_call_parameters(
    func: Callable[..., Any], parameters: dict[str, Any]
) -> tuple[dict[str, Any], set[str]]:
    """
    Drop parameters that a callable does not accept.

    Args:
        func: Callable tool implementation.
        parameters: Raw action parameters emitted by the model.

    Returns:
        A tuple of filtered parameters and dropped parameter names.
    """
    sig = inspect.signature(func)
    has_var_kw = any(
        param.kind == inspect.Parameter.VAR_KEYWORD for param in sig.parameters.values()
    )
    if has_var_kw:
        return dict(parameters), set()

    valid = set(sig.parameters.keys())
    dropped = set(parameters.keys()) - valid
    filtered = {key: value for key, value in parameters.items() if key in valid}
    return filtered, dropped


async def invoke_tool(
    func: Callable[..., Any], parameters: dict[str, Any]
) -> tuple[Any, set[str]]:
    """
    Invoke a sync or async tool with filtered parameters and unified timeout.

    Async tools are wrapped with ``asyncio.wait_for`` using a configurable
    timeout (``tool.timeout`` in duckflow.yaml, default 120s). Sync tools
    are called directly (timeout not applicable).

    Args:
        func: Callable tool implementation.
        parameters: Raw action parameters emitted by the model.

    Returns:
        A tuple of tool result and dropped parameter names.
    """
    call_params, dropped = filter_call_parameters(func, parameters)

    # Check for missing required parameters
    sig = inspect.signature(func)
    for name, param in sig.parameters.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            continue
        if param.default is inspect.Parameter.empty:
            # Required parameter
            value = call_params.get(name)
            tool_name = getattr(func, "__name__", str(func))
            is_missing = value is None or (
                tool_name == "propose_plan" and value == ""
            )
            if is_missing:
                # Soft skip for propose_plan without goal — the LLM often
                # calls it repeatedly without content after a plan exists.
                # Return a non-error hint so the pacemaker doesn't escalate.
                if tool_name == "propose_plan":
                    missing_msg = (
                        f"::status skip\n"
                        f"propose_plan was called without a goal. "
                        f"If a plan already exists, continue with ::note or "
                        f"::mark_step_complete. If you need a new plan, "
                        f"provide the plan content in a <<<...>>> block."
                    )
                else:
                    missing_msg = (
                        f"::status error\n"
                        f"Reason: Required parameter '{name}' is missing for tool '{tool_name}'. "
                        f"Provide the parameter in your action."
                    )
                logger.warning(f"Tool '{tool_name}' missing required param '{name}'")
                return missing_msg, dropped

    if asyncio.iscoroutinefunction(func):
        timeout = config.get("tool.timeout", 120)
        try:
            result = await asyncio.wait_for(func(**call_params), timeout=timeout)
            return result, dropped
        except asyncio.TimeoutError:
            tool_name = getattr(func, "__name__", str(func))
            logger.warning(f"Tool '{tool_name}' timed out after {timeout}s")
            return f"::status error\nReason: Tool timed out after {timeout}s", dropped
    return func(**call_params), dropped
