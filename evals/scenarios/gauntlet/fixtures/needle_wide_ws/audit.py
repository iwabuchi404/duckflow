"""Audit trail."""


def record(action: str) -> str:
    """Format an audit line."""
    return f"[audit] {action}"
