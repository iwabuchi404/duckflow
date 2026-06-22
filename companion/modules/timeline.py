"""
Timeline tracker for action execution observability (S3-11).

Records per-action timing data for the /timeline command.
"""

import time
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class TimelineEntry:
    """A single action execution record."""
    action_name: str
    start_ts: float
    end_ts: float
    duration_ms: float
    is_error: bool
    result_summary: str

    @property
    def timestamp_str(self) -> str:
        from datetime import datetime
        return datetime.fromtimestamp(self.start_ts).strftime("%H:%M:%S")


class TimelineTracker:
    """
    Collects action execution timing entries for /timeline display.

    Entries are kept in chronological order, capped at max_entries
    (oldest dropped first).
    """

    def __init__(self, max_entries: int = 50):
        self._entries: List[TimelineEntry] = []
        self._max_entries = max_entries

    def record(
        self,
        action_name: str,
        start_ts: float,
        end_ts: float,
        is_error: bool,
        result_summary: str,
    ) -> TimelineEntry:
        """Record a completed action and return the entry."""
        duration_ms = (end_ts - start_ts) * 1000
        summary = result_summary[:120] + "..." if len(result_summary) > 120 else result_summary
        entry = TimelineEntry(
            action_name=action_name,
            start_ts=start_ts,
            end_ts=end_ts,
            duration_ms=duration_ms,
            is_error=is_error,
            result_summary=summary,
        )
        self._entries.append(entry)
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries:]
        return entry

    @property
    def entries(self) -> List[TimelineEntry]:
        return list(self._entries)

    def clear(self) -> None:
        self._entries.clear()

    @property
    def total_actions(self) -> int:
        return len(self._entries)

    @property
    def error_count(self) -> int:
        return sum(1 for e in self._entries if e.is_error)

    @property
    def avg_duration_ms(self) -> float:
        if not self._entries:
            return 0.0
        return sum(e.duration_ms for e in self._entries) / len(self._entries)

    @property
    def total_duration_ms(self) -> float:
        return sum(e.duration_ms for e in self._entries)
