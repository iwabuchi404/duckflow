"""Monthly tax report."""

import calc


def report_tax(amounts: list[float], rate: float) -> float:
    """Sum tax across amounts."""
    return sum(calc.compute_tax(a, rate) for a in amounts)
