"""
Multi-stage result summarization pipeline (S3-1).

Applies a 4-stage compression to tool results:
  Stage 1: Threshold check — skip if short enough
  Stage 2: Mechanical summarization (tool-specific, no LLM)
  Stage 3: Re-threshold check — return if now short enough
  Stage 4: SubLLM summarization (default OFF) + ResultCache storage

The pipeline returns both the (possibly summarized) result for display/history
and the cache_id if the original was stored in ResultCache.
"""

from __future__ import annotations

import logging
from collections.abc import Coroutine
from typing import TYPE_CHECKING, Any, Protocol, cast

from companion.config.config_loader import config
from companion.tool_history_policy import compress_for_history

if TYPE_CHECKING:
    from companion.base.llm_client import LLMClient
    from companion.modules.result_cache import ResultCache

logger = logging.getLogger(__name__)


class _SubLLMManager(Protocol):
    """Sub-LLM summary interface accepted by the synchronous pipeline."""

    def summarize(self, text: str) -> Coroutine[Any, Any, str] | str:
        """Summarize text asynchronously or return an already-resolved string.

        Args:
            text: Mechanical summary to compress.

        Returns:
            Pending coroutine or completed summary text.
        """
        ...


class _SummarizationAgent(Protocol):
    """Agent surface required by the result summarization pipeline."""

    @property
    def llm(self) -> LLMClient:
        """Return the LLM client used for result metadata."""

    @property
    def result_cache(self) -> ResultCache:
        """Return the cache used for full tool results."""

    @property
    def sub_llm_manager(self) -> _SubLLMManager:
        """Return the optional Sub-LLM summarizer."""


# Tools that should never be summarized
_EXCLUDED_TOOLS = {"response", "note", "exit", "duck_call", "retrieve_result"}


def _get_threshold() -> int:
    """Return the configured character threshold for result summarization.

    Returns:
        Non-negative summarization threshold, or the default when unset.
    """
    return cast(int, config.get("summarizer.threshold_chars", 2000))


def _is_sub_llm_enabled() -> bool:
    """Return whether optional Sub-LLM result summarization is enabled.

    Returns:
        Configured summarization enablement flag.
    """
    return cast(bool, config.get("summarizer.sub_llm_enabled", False))


def summarize_result(
    action_name: str,
    result: str,
    agent: _SummarizationAgent,
) -> tuple[str, str | None]:
    """
    Apply the multi-stage summarization pipeline to a tool result.

    Args:
        action_name: Name of the tool that produced the result.
        result: Raw tool output string.
        agent: DuckAgent instance (for ResultCache and SubLLM access).

    Returns:
        Tuple of (summarized_result, cache_id).
        cache_id is non-None only when the original was stored in ResultCache.
    """
    # Skip excluded tools
    if action_name in _EXCLUDED_TOOLS:
        return result, None

    threshold = _get_threshold()

    # Stage 1: Threshold check
    if len(result) <= threshold:
        return result, None

    # Stage 2: Mechanical summarization
    strength = agent.llm.tier_profile.history_compression
    try:
        mechanical = compress_for_history(action_name, result, strength=strength)
    except Exception as e:
        logger.warning(f"Mechanical summarization failed for {action_name}: {e}")
        mechanical = result

    # Stage 3: Re-threshold check
    if len(mechanical) <= threshold:
        # Still cache the original if it was significantly compressed
        if len(mechanical) < len(result):
            cache_id = agent.result_cache.put(action_name, {}, result)
            hint = f"\n[Full data: ::retrieve_result cache_id={cache_id}]"
            return mechanical + hint, cache_id
        return mechanical, None

    # Stage 4: SubLLM summarization (default OFF)
    if _is_sub_llm_enabled():
        try:
            sub_llm = agent.sub_llm_manager
            summarization = sub_llm.summarize(mechanical)
            if isinstance(summarization, str):
                summarized = summarization
            else:
                summarization.close()
                summarized = ""
            if summarized and len(summarized) < len(mechanical):
                cache_id = agent.result_cache.put(action_name, {}, result)
                hint = f"\n[Full data: ::retrieve_result cache_id={cache_id}]"
                return summarized + hint, cache_id
        except Exception as e:
            logger.warning(f"SubLLM summarization failed for {action_name}: {e}")

    # Fallback: use mechanical summary + cache the original
    cache_id = agent.result_cache.put(action_name, {}, result)
    hint = f"\n[Full data: ::retrieve_result cache_id={cache_id}]"
    return mechanical + hint, cache_id
