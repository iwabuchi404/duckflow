"""
Callable invocation helpers for DuckAgent action execution.
"""

import asyncio
import inspect
import logging
from typing import Any, Callable

from companion.config.config_loader import config
from companion.tools.results import ToolResult

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
    func: Callable[..., Any],
    parameters: dict[str, Any],
    tool_name: str | None = None,
) -> tuple[Any, set[str]]:
    """
    Invoke a sync or async tool with filtered parameters and unified timeout.

    Async tools are wrapped with ``asyncio.wait_for`` using a configurable
    timeout (``tool.timeout`` in duckflow.yaml, default 120s). Sync tools
    are called directly (timeout not applicable).

    Args:
        func: Callable tool implementation.
        parameters: Raw action parameters emitted by the model.
        tool_name: Registered tool name (defaults to ``func.__name__``).

    Returns:
        A tuple of tool result and dropped parameter names.
    """
    call_params, dropped = filter_call_parameters(func, parameters)
    resolved_tool_name = tool_name or getattr(func, "__name__", str(func))
    target = call_params.get("path", call_params.get("command", "task"))

    sig = inspect.signature(func)
    valid = {
        name
        for name, param in sig.parameters.items()
        if param.kind != inspect.Parameter.VAR_KEYWORD
    }

    # Recover block-style parameters: when the model wrote "key: value" lines
    # directly in a <<<...>>> block, the parser maps the whole block to a
    # "content" parameter the tool does not accept. Re-parse the block text
    # scoped to this function's real parameter names and fill them in.
    # A remaining non-key body is assigned to "body" when the tool has one
    # (e.g. replace_function with inline name= + raw code block).
    if "content" in parameters and "content" not in valid:
        from companion.utils.sym_ops import extract_bare_key_params

        block = parameters["content"]
        if isinstance(block, str) and block.strip():
            recovered, remaining = extract_bare_key_params(block, valid_keys=valid)
            for key, value in recovered.items():
                if key not in call_params or not call_params[key]:
                    call_params[key] = value
            if (
                remaining.strip()
                and "body" in valid
                and not call_params.get("body")
            ):
                call_params["body"] = remaining
                recovered["body"] = remaining
            consumed = "content" if recovered else None
            dropped = dropped - set(recovered.keys())
            if consumed:
                dropped.discard("content")
            if recovered:
                logger.info(
                    f"Tool '{resolved_tool_name}': recovered params from "
                    f"content block: {sorted(recovered.keys())}"
                )

    # Check for missing required parameters
    for name, param in sig.parameters.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            continue
        if param.default is inspect.Parameter.empty:
            # Required parameter
            value = call_params.get(name)
            is_missing = value is None or (
                resolved_tool_name == "propose_plan" and value == ""
            )
            if is_missing:
                # Soft skip for propose_plan without goal — the LLM often
                # calls it repeatedly without content after a plan exists.
                # Return a non-error hint so the pacemaker doesn't escalate.
                if resolved_tool_name == "propose_plan":
                    return (
                        ToolResult.ok(
                            resolved_tool_name,
                            target,
                            "propose_plan was called without a goal. "
                            "If a plan already exists, continue with the next action or "
                            "::complete_step. If you need a new plan, "
                            "provide the plan content in a <<<...>>> block.",
                        ),
                        dropped,
                    )
                return (
                    ToolResult.error(
                        resolved_tool_name,
                        target,
                        (
                            f"Required parameter '{name}' is missing for tool "
                            f"'{resolved_tool_name}'. Provide the parameter in your action."
                        ),
                    ),
                    dropped,
                )

    if asyncio.iscoroutinefunction(func):
        timeout = config.get("tool.timeout", 120)
        try:
            result = await asyncio.wait_for(func(**call_params), timeout=timeout)
            return result, dropped
        except asyncio.TimeoutError:
            logger.warning(f"Tool '{resolved_tool_name}' timed out after {timeout}s")
            return (
                ToolResult.error(
                    resolved_tool_name,
                    target,
                    f"Tool timed out after {timeout}s",
                ),
                dropped,
            )
    return func(**call_params), dropped
