"""Sessions."""


def active(sessions: list[bool]) -> int:
    """Count active sessions."""
    return sum(1 for s in sessions if s)
