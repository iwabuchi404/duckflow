"""Retail helpers."""


def shelf_tag(name: str, price: float) -> str:
    """Price tag line."""
    return f"{name}: {price:.0f} yen"
