"""Tests for pricing.py — order totals follow the per-unit rounding policy."""

from pricing import order_total


def test_order_total_single_item() -> None:
    """Single discounted line uses per-unit rounding."""
    assert order_total([{"price": 95, "qty": 2, "discount": 0.1}]) == 172


def test_order_total_no_discount() -> None:
    """Undiscounted lines sum exactly."""
    items = [
        {"price": 120, "qty": 2},
        {"price": 80, "qty": 1},
    ]
    assert order_total(items) == 320


def test_order_total_mixed_discounts() -> None:
    """Mixed discount rates aggregate per line."""
    items = [
        {"price": 200, "qty": 1, "discount": 0.25},  # 150
        {"price": 80, "qty": 3, "discount": 0.0},  # 240
    ]
    assert order_total(items) == 390
