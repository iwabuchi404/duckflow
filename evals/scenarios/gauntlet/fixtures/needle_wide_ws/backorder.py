"""Backorders."""


def wait_weeks(stock: int) -> int:
    """Estimate restock wait."""
    return 0 if stock > 0 else 2
