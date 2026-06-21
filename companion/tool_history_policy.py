"""
Tool result history injection policy.

Compresses tool results for LLM conversation history while preserving
the full content for UI display. This reduces context pressure during
long-running tasks without losing critical information.

Policy targets (Phase 1):
- grep_files: keep top 10 matches + file-level summary + re-search hint
- get_project_tree: keep top-level entries + counts, omit deep nesting
- run_command (success): keep head/tail 20 lines of stdout/stderr

Tools not listed here pass through unchanged (no compression).
"""

import logging
import re

logger = logging.getLogger(__name__)

# --- Thresholds ---
_GREP_MAX_EXCERPTS = 10
_PROJECT_TREE_MAX_LINES = 30
_RUN_CMD_HEAD_TAIL_LINES = 20
_RUN_CMD_COMPRESS_THRESHOLD = 60  # only compress if output exceeds this many lines


def compress_for_history(action_name: str, result: str) -> str:
    """Dispatch to a tool-specific compressor.

    If the compressed version is not shorter than the original, the
    original is returned unchanged.

    Args:
        action_name: Name of the tool that produced the result.
        result: Raw tool output string.

    Returns:
        Compressed string suitable for LLM history injection, or the
        original string if compression yields no benefit.
    """
    compressors = {
        "grep_files": _compress_grep,
        "get_project_tree": _compress_project_tree,
        "run_command": _compress_run_command,
    }

    compressor = compressors.get(action_name)
    if compressor is None:
        return result

    try:
        compressed = compressor(result)
    except Exception as e:
        logger.warning(f"History compression failed for {action_name}: {e}")
        return result

    if len(compressed) >= len(result):
        return result

    logger.info(
        f"History compression for {action_name}: "
        f"{len(result)} -> {len(compressed)} chars"
    )
    return compressed


# --- grep_files ---

def _compress_grep(result: str) -> str:
    """Compress grep_files output to top N matches + summary.

    Keeps:
    - File-level match counts
    - First N match excerpts (exact lines)
    - Total match count
    - Re-search hint

    Drops:
    - Matches beyond the first N
    """
    lines = result.split("\n")

    # Extract match lines (format: "path:line_num: content")
    match_pattern = re.compile(r"^(.+?):(\d+): (.*)$")
    matches = []
    summary_lines = []

    for line in lines:
        if match_pattern.match(line):
            matches.append(line)
        else:
            # Non-match lines (summaries, hints, "No matches", etc.)
            summary_lines.append(line)

    if not matches:
        return result  # no matches to compress

    # Group by file
    file_counts: dict[str, int] = {}
    for m in matches:
        match match_pattern.match(m):
            case m_obj:
                filepath = m_obj.group(1)
                file_counts[filepath] = file_counts.get(filepath, 0) + 1

    # Build compressed output
    parts: list[str] = []

    # File-level summary
    parts.append(f"Files with matches: {len(file_counts)}")
    for filepath, count in sorted(file_counts.items(), key=lambda x: -x[1]):
        parts.append(f"  {filepath}: {count} match(es)")

    # Top N excerpts
    parts.append(f"\nTop {_GREP_MAX_EXCERPTS} matches:")
    for m in matches[:_GREP_MAX_EXCERPTS]:
        parts.append(m)

    if len(matches) > _GREP_MAX_EXCERPTS:
        parts.append(f"  ... ({len(matches) - _GREP_MAX_EXCERPTS} more matches omitted)")

    # Preserve summary lines (match count, truncation notice, etc.)
    for s in summary_lines:
        if s.strip():
            parts.append(s)

    parts.append("\n[Hint: Re-run grep_files with a narrower pattern or path to see all matches.]")

    return "\n".join(parts)


# --- get_project_tree ---

def _compress_project_tree(result: str) -> str:
    """Compress project tree output to top-level + counts.

    Keeps:
    - Top-level entries (directories and files at depth 1)
    - Total entry count
    - Omission notice

    Drops:
    - Deep nesting (depth 2+)
    """
    lines = result.split("\n")

    if len(lines) <= _PROJECT_TREE_MAX_LINES:
        return result  # short enough already

    # Keep only top-level entries (no leading whitespace = depth 1)
    top_level: list[str] = []
    omitted = 0

    for line in lines:
        if not line.startswith("  ") and line.strip():
            top_level.append(line)
        else:
            omitted += 1

    parts: list[str] = [
        f"Top-level entries ({len(top_level)}):",
        *top_level,
        f"\n[Omitted {omitted} entries at deeper levels. "
        f"Use list_directory on a specific path to explore further.]",
    ]

    return "\n".join(parts)


# --- run_command (success only) ---

def _compress_run_command(result: str) -> str:
    """Compress successful run_command output to head/tail.

    Keeps:
    - First N lines of output
    - Last N lines of output
    - Omission notice with line count

    Only applies when output exceeds _RUN_CMD_COMPRESS_THRESHOLD lines.
    Error outputs (containing "Error:" prefix) are not compressed.
    """
    if result.startswith("Error:"):
        return result  # don't compress error output

    lines = result.split("\n")

    if len(lines) <= _RUN_CMD_COMPRESS_THRESHOLD:
        return result  # short enough

    head = lines[:_RUN_CMD_HEAD_TAIL_LINES]
    tail = lines[-_RUN_CMD_HEAD_TAIL_LINES:]
    omitted = len(lines) - _RUN_CMD_HEAD_TAIL_LINES * 2

    parts: list[str] = [
        *head,
        f"\n[... {omitted} lines omitted ...]\n",
        *tail,
    ]

    return "\n".join(parts)
