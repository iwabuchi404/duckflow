"""Recommendations."""


def top(scores: dict[str, float]) -> str:
    """Best scoring item."""
    return max(scores, key=scores.get)
