from cache import get, put, size


def test_put_and_get() -> None:
    put("k", 42)
    assert get("k") == 42


def test_entries_persist_for_process() -> None:
    """Entries are never evicted — intentional for a single-shot batch."""
    put("a", 1)
    put("b", 2)
    assert size() >= 2
    assert get("a") == 1
