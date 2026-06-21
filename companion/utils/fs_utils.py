"""Shared filesystem utilities for directory traversal and file I/O.

Consolidates the directory-exclusion sets and helper predicates that were
duplicated across ``file_ops.py`` and ``get_project_tree.py``, as well as
the try-UTF-8-then-latin-1 file-reading pattern used in multiple places.
"""

from pathlib import Path

# Unified set of directory names to skip during file search / tree display.
# Covers dot-prefixed dirs (handled separately by ``is_hidden_entry``),
# build artefacts, caches, and dependency directories.
EXCLUDED_DIR_NAMES: frozenset[str] = frozenset(
    {
        # Python
        "__pycache__",
        # JavaScript / Node
        "node_modules",
        # Build artefacts
        "dist",
        "build",
        "out",
        "target",
        "bin",
        "obj",
        # Eggs
        "egg-info",
        # Virtual-environments (non-dot-prefixed)
        "venv",
        "vendor",
        "site-packages",
        # Framework-specific
        ".next",
        # VCS / IDE (also caught by ``is_hidden_entry``)
        ".git",
        ".svn",
        ".idea",
        ".vscode",
        # Environment files
        ".env",
        ".venv",
    }
)


def is_excluded_dir(name: str) -> bool:
    """Return whether a directory *name* should be skipped during traversal.

    Checks membership in ``EXCLUDED_DIR_NAMES`` and the ``*.egg-info``
    suffix convention.

    Args:
        name: Directory basename to check.

    Returns:
        ``True`` when the directory is a known noise / artefact directory.
    """
    return name in EXCLUDED_DIR_NAMES or name.endswith(".egg-info")


def is_hidden_entry(name: str) -> bool:
    """Return whether a file or directory *name* is hidden (dot-prefixed).

    Args:
        name: File or directory basename.

    Returns:
        ``True`` for names starting with ``"."``.
    """
    return name.startswith(".")


def should_skip_entry(name: str) -> bool:
    """Convenience predicate combining hidden-check and exclusion-check.

    Args:
        name: File or directory basename.

    Returns:
        ``True`` when the entry should be skipped during traversal.
    """
    return is_hidden_entry(name) or is_excluded_dir(name)


def read_text_with_fallback(path: Path) -> str:
    """Read a text file, falling back to latin-1 on ``UnicodeDecodeError``.

    Args:
        path: Resolved ``Path`` to read.

    Returns:
        File content as a string.
    """
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")
