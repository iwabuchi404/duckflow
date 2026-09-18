"""Cache keys."""


def key(*parts: str) -> str:
    """Join cache key parts."""
    return ":".join(parts)
