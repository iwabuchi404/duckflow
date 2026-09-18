"""Warehouse slots."""


def slot(aisle: int, shelf: int) -> str:
    """Format a slot label."""
    return f"{aisle:02d}-{shelf:02d}"
