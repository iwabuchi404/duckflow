"""Small helpers (unrelated to the rename)."""


def slug(text: str) -> str:
    """Return a URL-safe slug."""
    return text.strip().lower().replace(" ", "-")
