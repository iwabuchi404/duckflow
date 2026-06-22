"""
Tool result history injection policy.

Compresses tool results for LLM conversation history while preserving
the full content for UI display. This reduces context pressure during
long-running tasks without losing critical information.

Policy targets:
- grep_files: keep top 10 matches + file-level summary + re-search hint
- get_project_tree: keep top-level entries + counts, omit deep nesting
- run_command (success): keep head/tail 20 lines of stdout/stderr
- read_file: structure extraction (class/function headers) + head + line count
- list_symbols: symbol-type aggregation + top N entries
- generic: head/tail + line/char count

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
_READ_FILE_HEAD_LINES = 15
_READ_FILE_MAX_HEADERS = 20
_LIST_SYMBOLS_MAX_ENTRIES = 20
_GENERIC_HEAD_TAIL_LINES = 20
_GENERIC_COMPRESS_THRESHOLD = 60  # only compress if output exceeds this many lines


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
        "read_file": _compress_read_file,
        "list_symbols": _compress_list_symbols,
    }

    compressor = compressors.get(action_name)
    if compressor is None:
        # Generic fallback: head/tail compression for long outputs
        if len(result) > 2000:
            return _compress_generic(result)
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


# --- read_file ---

# Patterns for structure extraction (Python, JS/TS, and generic)
_STRUCT_PATTERNS = [
    re.compile(r"^(\s*(?:class|def|async def)\s+\w+.*)$", re.MULTILINE),  # Python
    re.compile(r"^(\s*(?:export\s+)?(?:class|function|interface|type|enum)\s+\w+.*)$", re.MULTILINE),  # JS/TS
    re.compile(r"^(\s*(?:pub(?:lic)?|priv(?:ate)?|fn|struct|impl|trait)\s+\w+.*)$", re.MULTILINE),  # Rust
]


def _compress_read_file(result: str) -> str:
    """Compress read_file output to structure headers + head + line count.

    Keeps:
    - Class/function/type definition headers (with line numbers if present)
    - First N lines of the file
    - Total line count and file size

    Drops:
    - Full file body (headers + head give enough context for navigation)
    """
    lines = result.split("\n")
    if len(lines) <= _GENERIC_COMPRESS_THRESHOLD:
        return result  # short enough

    # Extract structure headers
    headers: list[str] = []
    for i, line in enumerate(lines, 1):
        for pattern in _STRUCT_PATTERNS:
            if pattern.match(line):
                headers.append(f"L{i}: {line.strip()}")
                break
        if len(headers) >= _READ_FILE_MAX_HEADERS:
            break

    head = lines[:_READ_FILE_HEAD_LINES]

    parts: list[str] = [
        f"File: {len(lines)} lines, {len(result)} chars",
    ]

    if headers:
        parts.append(f"\nStructure ({len(headers)} definitions):")
        parts.extend(headers)
        if len(headers) >= _READ_FILE_MAX_HEADERS:
            parts.append("  ... (more definitions exist)")

    parts.append(f"\nFirst {_READ_FILE_HEAD_LINES} lines:")
    parts.extend(head)
    parts.append(f"\n[... {len(lines) - _READ_FILE_HEAD_LINES} lines omitted. "
                 f"Use retrieve_result with line range to access specific sections.]")

    return "\n".join(parts)


# --- list_symbols ---

def _compress_list_symbols(result: str) -> str:
    """Compress list_symbols output to type aggregation + top N entries.

    Keeps:
    - Symbol counts by type (class, function, method, etc.)
    - First N symbol entries
    - Total symbol count

    Drops:
    - Entries beyond the first N
    """
    lines = result.split("\n")
    if len(lines) <= _LIST_SYMBOLS_MAX_ENTRIES:
        return result  # short enough

    # Count symbol types (lines like "class MyClass" or "def my_func")
    type_counts: dict[str, int] = {}
    for line in lines:
        stripped = line.strip()
        if stripped:
            first_word = stripped.split()[0] if stripped.split() else ""
            if first_word in ("class", "def", "async", "function", "interface", "type", "enum", "struct", "impl", "trait", "pub", "priv", "fn"):
                type_counts[first_word] = type_counts.get(first_word, 0) + 1

    parts: list[str] = [
        f"Symbols: {len(lines)} total",
    ]

    if type_counts:
        parts.append("By type:")
        for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
            parts.append(f"  {t}: {c}")

    parts.append(f"\nFirst {_LIST_SYMBOLS_MAX_ENTRIES} entries:")
    parts.extend(lines[:_LIST_SYMBOLS_MAX_ENTRIES])
    parts.append(f"\n[... {len(lines) - _LIST_SYMBOLS_MAX_ENTRIES} more symbols omitted]")

    return "\n".join(parts)


# --- generic fallback ---

def _compress_generic(result: str) -> str:
    """Generic head/tail compression for any long output.

    Keeps:
    - First N lines
    - Last N lines
    - Total line/char count
    """
    lines = result.split("\n")
    if len(lines) <= _GENERIC_COMPRESS_THRESHOLD:
        # Single very long line? Truncate by chars.
        if len(result) > 2000:
            return result[:1000] + f"\n[... {len(result) - 2000} chars omitted ...]\n" + result[-1000:]
        return result

    head = lines[:_GENERIC_HEAD_TAIL_LINES]
    tail = lines[-_GENERIC_HEAD_TAIL_LINES:]
    omitted = len(lines) - _GENERIC_HEAD_TAIL_LINES * 2

    parts: list[str] = [
        f"[{len(lines)} lines, {len(result)} chars]",
        *head,
        f"\n[... {omitted} lines omitted ...]\n",
        *tail,
    ]

    return "\n".join(parts)
