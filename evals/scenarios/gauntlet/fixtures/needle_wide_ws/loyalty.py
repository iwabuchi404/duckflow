"""Loyalty points."""


def points(spent_yen: int) -> int:
    """One point per 100 yen."""
    return spent_yen // 100
