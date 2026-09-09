from calc import sum_up_to


def test_sum_up_to_five() -> None:
    """1+2+3+4+5 = 15 になるべき。"""
    assert sum_up_to(5) == 15


def test_sum_up_to_one() -> None:
    """n=1 のとき 1 になるべき。"""
    assert sum_up_to(1) == 1
