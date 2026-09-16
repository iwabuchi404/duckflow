"""Item listing API (pre-pagination state)."""

ITEMS = ["a", "b", "c", "d", "e"]


def list_items() -> list[str]:
    """Return all items."""
    return list(ITEMS)
