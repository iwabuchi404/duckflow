"""
retrieve_result tool — LLM-facing tool to fetch cached full results (S3-1).

When a tool result has been summarized, the LLM can use this tool to
retrieve the original full data from ResultCache, optionally with a
line range for pin-point access.
"""

import logging
import re
from collections.abc import Awaitable, Callable
from typing import Protocol

logger = logging.getLogger(__name__)


class _ResultCacheEntry(Protocol):
    """Subset of a cached result entry used by the retrieval tool."""

    full_result: str


class _ResultCache(Protocol):
    """Result cache operations required by the retrieval tool."""

    def get(self, cache_id: str) -> _ResultCacheEntry | None:
        """Return a cache entry when it still exists.

        Args:
            cache_id: Identifier assigned by ResultCache.put.

        Returns:
            Cached entry, or None when the identifier is unavailable.
        """
        ...

    def get_range(self, cache_id: str, start: int, end: int) -> str | None:
        """Return a one-indexed inclusive line range when available.

        Args:
            cache_id: Identifier assigned by ResultCache.put.
            start: First line to return.
            end: Last line to return.

        Returns:
            Selected text, or None when the cache entry is unavailable.
        """
        ...

    def expired_message(self, cache_id: str) -> str:
        """Return a message describing an unavailable cache entry.

        Args:
            cache_id: Missing cache identifier.

        Returns:
            User-facing expiration message.
        """
        ...


class _AgentWithResultCache(Protocol):
    """Agent surface required to bind the result retrieval tool."""

    result_cache: _ResultCache


def make_retrieve_result_tool(
    agent: _AgentWithResultCache,
) -> Callable[..., Awaitable[str]]:
    """
    Create a retrieve_result tool function bound to the agent's ResultCache.

    Returns a callable with a proper docstring and signature for
    Sym-Ops tool registration.
    """

    async def retrieve_result(
        cache_id: str,
        lines: str | None = None,
    ) -> str:
        """
        Retrieve the full (unsummarized) result of a previously executed tool.

        Use this when a summarized result lacks the detail you need.
        Optionally specify a line range to avoid retrieving the entire output.

        Args:
            cache_id: Cache entry ID (e.g. "r3").
            lines: Optional line range in "start-end" format (e.g. "120-180").
                   1-indexed, inclusive. If omitted, returns the full result.
        """
        cache = agent.result_cache
        entry = cache.get(cache_id)

        if entry is None:
            msg = cache.expired_message(cache_id)
            logger.info(f"retrieve_result: {msg}")
            return msg

        if lines:
            match = re.match(r"^(\d+)-(\d+)$", lines.strip())
            if match:
                start = int(match.group(1))
                end = int(match.group(2))
                result = cache.get_range(cache_id, start, end)
                if result is None:
                    return cache.expired_message(cache_id)
                return result
            else:
                return f"Invalid lines format: '{lines}'. Use 'start-end' (e.g. '120-180')."

        return entry.full_result

    return retrieve_result
