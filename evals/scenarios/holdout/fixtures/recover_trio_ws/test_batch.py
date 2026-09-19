from batch import page_count, page_items


def test_page_count_exact() -> None:
    assert page_count(10, 5) == 2


def test_page_count_remainder() -> None:
    """11 items at 5 per page needs a third page."""
    assert page_count(11, 5) == 3


def test_page_items_last_page() -> None:
    assert page_items(list(range(11)), 3, 5) == [10]
