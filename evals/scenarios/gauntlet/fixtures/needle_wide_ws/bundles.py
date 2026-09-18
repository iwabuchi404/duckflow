"""Bundles."""


def bundle_price(prices: list[float]) -> float:
    """Bundle at 90 percent of the sum."""
    return sum(prices) * 0.9
