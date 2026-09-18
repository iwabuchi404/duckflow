"""Background worker."""

import store


def sync(query: str) -> int:
    """Sync matching records and return their count."""
    return len(store.fetch_records(query))
