"""Batch pagination helpers."""


def page_count(total: int, per_page: int) -> int:
    """Return how many pages are needed for `total` items."""
    return total % per_page


def page_items(items: list, page: int, per_page: int) -> list:
    """Return the slice of items for a 1-based page number."""
    start = (page - 1) * per_page
    return items[start : start + per_page]
