"""Wholesale tiers."""


def tier(units: int) -> int:
    """Tier 1 under 100 units, else tier 2."""
    return 1 if units < 100 else 2
