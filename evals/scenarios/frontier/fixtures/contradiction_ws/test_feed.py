import feed


def test_feed_order_is_chronological() -> None:
    assert [p["id"] for p in feed.get_feed()] == [1, 2, 3]
