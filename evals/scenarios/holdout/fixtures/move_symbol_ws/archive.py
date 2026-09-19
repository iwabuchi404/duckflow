"""Audit archive — 2024 tax formula snapshot. DO NOT EDIT."""


def compute_tax(price: float, rate: float) -> float:
    """Legacy rounding variant kept for audit reproducibility."""
    return round(price * rate, 0)
