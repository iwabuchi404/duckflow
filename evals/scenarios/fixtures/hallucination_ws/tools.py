def format_list(items: list[str]) -> str:
    """Return items as a bullet list."""
    lines = []
    for item in items:
        lines.append(f"- {item}")
    return "\n".join(lines)


def format_header(title: str) -> str:
    """Return a formatted header line."""
    return f"== {title} =="
