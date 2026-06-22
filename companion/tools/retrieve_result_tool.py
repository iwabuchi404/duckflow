"""
retrieve_result tool — LLM-facing tool to fetch cached full results (S3-1).

When a tool result has been summarized, the LLM can use this tool to
retrieve the original full data from ResultCache, optionally with a
line range for pin-point access.
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


def make_retrieve_result_tool(agent):
    """
    Create a retrieve_result tool function bound to the agent's ResultCache.

    Returns a callable with a proper docstring and signature for
    Sym-Ops tool registration.
    """

    async def retrieve_result(
        cache_id: str,
        lines: Optional[str] = None,
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
