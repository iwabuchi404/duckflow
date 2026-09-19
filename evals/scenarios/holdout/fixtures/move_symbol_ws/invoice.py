"""Invoice line helpers."""

from calc import compute_tax


def invoice_tax(price: float, qty: int, rate: float) -> float:
    """Tax for one invoice line."""
    return compute_tax(price * qty, rate)
