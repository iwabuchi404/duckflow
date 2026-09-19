"""Weekly stats report."""

from stats import summarize


def weekly_report(sales: list[float]) -> str:
    """Render a one-line summary of weekly sales."""
    s = summarize(sales)
    if not s:
        return "no data"
    return f"n={s['count']} total={s['total']} mean={s['mean']}"
