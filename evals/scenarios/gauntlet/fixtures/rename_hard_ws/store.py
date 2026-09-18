"""Record storage backend."""


def fetch_records(query: str) -> list[str]:
    """Return records matching the query."""
    return [f"{query}-{i}" for i in range(3)]
