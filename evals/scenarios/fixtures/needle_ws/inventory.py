"""Inventory helpers (unrelated to the failing tests)."""


def stock_level(items: list[int]) -> int:
    """Return total stock."""
    return sum(items)


def restock(items: list[int], amount: int) -> list[int]:
    """Add amount to each item."""
    return [i + amount for i in items]
