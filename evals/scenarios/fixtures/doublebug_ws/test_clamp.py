from clamp import clamp


def test_clamp_inside_range() -> None:
    """範囲内はそのまま返るべき。"""
    assert clamp(5, 0, 10) == 5


def test_clamp_above_high() -> None:
    """上限超過は high を返すべき。"""
    assert clamp(15, 0, 10) == 10


def test_clamp_below_low() -> None:
    """下限未満は low を返すべき。"""
    assert clamp(-3, 0, 10) == 0
