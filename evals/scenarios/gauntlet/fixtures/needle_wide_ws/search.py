"""Search helpers."""


def normalize(query: str) -> str:
    """Lowercase and trim a query."""
    return query.strip().lower()
