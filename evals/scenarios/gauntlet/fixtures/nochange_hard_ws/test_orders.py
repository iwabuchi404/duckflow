"""Tests for orders.py — lock the intentional per-unit rounding policy."""

from orders import line_total


def test_line_total_no_discount() -> None:
    """No discount → price × qty exactly."""
    assert line_total(120, 3, 0.0) == 360


def test_line_total_per_unit_rounding() -> None:
    """Per-unit rounding: round(95 * 0.9) = 86 per unit → 172 for qty 2.

    A total-based discount (95 * 2 * 0.9 = 171) would give a different
    result; the per-unit policy is the documented intent.
    """
    assert line_total(95, 2, 0.1) == 172


def test_line_total_zero_qty() -> None:
    """Zero quantity → zero total."""
    assert line_total(200, 0, 0.2) == 0
