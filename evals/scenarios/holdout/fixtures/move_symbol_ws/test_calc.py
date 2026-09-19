from tax import compute_tax


def test_compute_tax_basic() -> None:
    assert compute_tax(100.0, 0.1) == 10.0


def test_compute_tax_zero() -> None:
    assert compute_tax(0.0, 0.1) == 0.0
