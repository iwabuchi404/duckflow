"""Sales summary report (needs `tabulate`; see requirements.txt)."""

from tabulate import tabulate


def summary(orders: dict[str, float]) -> dict[str, float]:
    """Return per-product totals as a flat dict."""
    return {"summary": dict(orders)}


def table(orders: dict[str, float]) -> str:
    """Render per-product totals as a plain-text table."""
    rows = [(item, total) for item, total in sorted(summary(orders).items())]
    return tabulate(rows, headers=["item", "total"], tablefmt="plain")
