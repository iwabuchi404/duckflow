"""Shipping fees."""


def fee(weight: float) -> int:
    """Weight tiers: up to 10kg costs 500, anything heavier costs 800."""
    if weight < 10:
        return 500
    return 800
