"""Coupon codes."""


def is_valid(code: str) -> bool:
    """Codes are 8 uppercase alphanumerics."""
    return len(code) == 8 and code.isalnum() and code.isupper()
