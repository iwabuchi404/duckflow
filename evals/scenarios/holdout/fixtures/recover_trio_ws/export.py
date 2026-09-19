"""Plain-text export of report lines (needs `termcolor`; see requirements.txt)."""

from termcolor import colored


def render_lines(rows: list[tuple[str, float]]) -> str:
    """Render rows as 'name: amount' lines separated by newlines."""
    lines = [f"{name}: {colored(str(amount), 'green')}" for name, amount in rows]
    return "".join(lines)
