from orders import discount


def test_discount_ten_percent() -> None:
    """100円の10%引きは90円。"""
    assert discount(100.0, 0.1) == 90.0


def test_discount_zero() -> None:
    """0%引きはそのまま。"""
    assert discount(50.0, 0.0) == 50.0
