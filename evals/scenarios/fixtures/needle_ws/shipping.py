"""Shipping helpers (unrelated to the failing tests)."""


def shipping_fee(weight: float) -> float:
    """Return the shipping fee for a weight in kg."""
    if weight <= 1.0:
        return 500.0
    return 500.0 + (weight - 1.0) * 200.0
