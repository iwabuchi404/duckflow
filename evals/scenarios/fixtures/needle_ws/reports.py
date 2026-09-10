"""Reporting helpers (unrelated to the failing tests)."""


def summarize(values: list[float]) -> str:
    """Return a one-line summary."""
    return f"count={len(values)} total={sum(values)}"
