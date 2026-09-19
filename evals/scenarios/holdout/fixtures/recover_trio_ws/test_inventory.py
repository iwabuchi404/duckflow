from inventory import add_item, count_items


def test_add_item_returns_new_items() -> None:
    """Two independent calls must not share state."""
    first = add_item("apple")
    second = add_item("banana")
    assert first == ["apple"]
    assert second == ["banana"]


def test_count_items() -> None:
    assert count_items(["a", "b"]) == 2
