def is_email(value: str) -> bool:
    """Return True for plausible email addresses."""
    if "@" not in value:
        return False
    local, _, domain = value.partition("@")
    return bool(local) and "." in domain


def is_port(value: int) -> bool:
    """Return True for valid TCP port numbers."""
    return 0 < value < 65536
