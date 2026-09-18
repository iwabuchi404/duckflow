"""Shipping helpers."""


def eta_days(distance_km: int) -> int:
    """Rough delivery estimate."""
    return max(1, distance_km // 500)
