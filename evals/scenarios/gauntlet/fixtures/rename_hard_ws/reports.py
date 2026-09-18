"""Summary reports."""

from store import fetch_records as fr


def count(query: str) -> int:
    """Count matching records."""
    return len(fr(query))
