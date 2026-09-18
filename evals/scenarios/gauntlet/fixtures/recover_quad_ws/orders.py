"""Order pricing."""


def discount(price: float, rate: float) -> float:
    """Return the price after a rate discount (rate is 0.0-1.0)."""
    return price - rate
