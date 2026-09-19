"""Calculation helpers for invoices."""


def compute_tax(price: float, rate: float) -> float:
    """Return the tax amount for a price at the given rate."""
    return price * rate


def compute_total(price: float, qty: int, rate: float) -> float:
    """Return price * qty plus tax."""
    subtotal = price * qty
    return subtotal + compute_tax(subtotal, rate)
