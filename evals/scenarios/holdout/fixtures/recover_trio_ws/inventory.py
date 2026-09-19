"""Inventory accumulation helpers."""


def add_item(item: str, items: list = []) -> list:
    """Append item and return the updated list."""
    items.append(item)
    return items


def count_items(items: list) -> int:
    """Return the number of items."""
    return len(items)
