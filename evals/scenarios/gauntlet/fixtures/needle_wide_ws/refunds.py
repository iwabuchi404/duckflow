"""Refund policy."""


def eligible(days_since_purchase: int) -> bool:
    """Refunds within 30 days."""
    return days_since_purchase <= 30
