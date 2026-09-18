"""Notifications."""


def subject(order_id: int) -> str:
    """Email subject for an order."""
    return f"Order #{order_id} update"
