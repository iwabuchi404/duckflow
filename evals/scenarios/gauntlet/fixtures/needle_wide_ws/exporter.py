"""CSV exporter."""


def dump(rows: list[tuple[str, float]]) -> str:
    """Render rows as CSV text."""
    return "\n".join(f"{name},{value}" for name, value in rows)
