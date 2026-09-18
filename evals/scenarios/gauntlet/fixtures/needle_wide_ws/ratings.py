"""Ratings."""


def average(stars: list[int]) -> float:
    """Mean rating."""
    return sum(stars) / len(stars)
