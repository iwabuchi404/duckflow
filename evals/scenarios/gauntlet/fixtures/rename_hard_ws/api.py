"""Public search API."""

from store import fetch_records


def search(query: str) -> list[str]:
    """Search records via the storage backend."""
    return fetch_records(query)
