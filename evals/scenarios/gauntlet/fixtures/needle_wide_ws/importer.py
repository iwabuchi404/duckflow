"""CSV importer."""


def rows(text: str) -> list[str]:
    """Split into non-empty lines."""
    return [line for line in text.splitlines() if line.strip()]
