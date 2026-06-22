"""
ResultCache — in-memory LRU cache for full tool results (S3-1).

Stores original (unsummarized) tool results so the LLM or user can
retrieve them via `retrieve_result` or `/result` after summarization.
"""

import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple


@dataclass
class ResultCacheEntry:
    """A single cached tool result."""
    cache_id: str
    tool_name: str
    params: Dict[str, Any]
    full_result: str
    timestamp: float
    size_chars: int


class ResultCache:
    """
    LRU cache for full tool results.

    Entries are identified by sequential IDs (r1, r2, ...).
    When the cache is full, the oldest entry is evicted.
    Expired lookups return a descriptive error message.
    """

    def __init__(self, max_size: int = 10):
        self._entries: OrderedDict[str, ResultCacheEntry] = OrderedDict()
        self._max_size = max_size
        self._counter = 0

    def put(
        self,
        tool_name: str,
        params: Dict[str, Any],
        full_result: str,
    ) -> str:
        """Store a result and return its cache ID."""
        self._counter += 1
        cache_id = f"r{self._counter}"
        entry = ResultCacheEntry(
            cache_id=cache_id,
            tool_name=tool_name,
            params=params,
            full_result=full_result,
            timestamp=time.time(),
            size_chars=len(full_result),
        )
        self._entries[cache_id] = entry
        self._entries.move_to_end(cache_id)

        while len(self._entries) > self._max_size:
            self._entries.popitem(last=False)

        return cache_id

    def get(self, cache_id: str) -> Optional[ResultCacheEntry]:
        """Retrieve an entry by ID. Returns None if not found (expired)."""
        entry = self._entries.get(cache_id)
        if entry is None:
            return None
        self._entries.move_to_end(cache_id)
        return entry

    def get_range(
        self, cache_id: str, start: int, end: int
    ) -> Optional[str]:
        """Retrieve a line range from a cached entry.

        Args:
            cache_id: Cache entry ID.
            start: 1-indexed start line (inclusive).
            end: 1-indexed end line (inclusive).

        Returns:
            The specified line range as a string, or None if entry not found.
        """
        entry = self.get(cache_id)
        if entry is None:
            return None
        lines = entry.full_result.split("\n")
        # Clamp to valid range
        start = max(1, start)
        end = min(len(lines), end)
        if start > end:
            return f"Invalid line range: {start}-{end} (file has {len(lines)} lines)"
        selected = lines[start - 1 : end]
        header = f"[Lines {start}-{end} of {len(lines)}]\n"
        return header + "\n".join(selected)

    @property
    def size(self) -> int:
        return len(self._entries)

    @property
    def entries(self) -> Dict[str, ResultCacheEntry]:
        return dict(self._entries)

    def clear(self) -> None:
        self._entries.clear()
        self._counter = 0

    def expired_message(self, cache_id: str) -> str:
        """Return a user-friendly expired message."""
        return (
            f"Cache entry {cache_id} has expired. "
            "Re-run the original tool to get fresh data."
        )
