from shipping import fee


def test_fee_boundary() -> None:
    """10kgちょうどは500円の tier に入る。"""
    assert fee(10) == 500


def test_fee_light_and_heavy() -> None:
    """軽量は500円、超過は800円。"""
    assert fee(2) == 500
    assert fee(11) == 800
