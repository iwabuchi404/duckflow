"""
Tool result history injection policy.

Compresses tool results for LLM conversation history while preserving
the full content for UI display. This reduces context pressure during
long-running tasks without losing critical information.

Policy targets:
- grep_files: keep top 10 matches + file-level summary + re-search hint
- list_files: keep top-level entries + counts, omit deep nesting (tree-view mode)
- run_command (success): keep head/tail 20 lines of stdout/stderr
- find_symbol: symbol-type aggregation + top N entries
- generic: head/tail + line/char count

Tools not listed here pass through unchanged (no compression).
"""

import logging
import re
from typing import Dict

logger = logging.getLogger(__name__)

# --- Thresholds ---
# tier 別の圧縮強度プロファイル（docs/agent_surface_redesign_design.md §5.2
# 「履歴圧縮の強度」）。"standard" は従来値のまま維持し、"strong"（low tier
# 向け）はより多く切り詰める。tier を知るのは呼び出し側（result_pipeline.py
# が TierProfile.history_compression を渡す）だけで、このモジュール自体は
# tier を知らず、プロファイル名から辞書を引くだけ。
_COMPRESSION_PROFILES: Dict[str, Dict[str, int]] = {
    "standard": {
        "grep_max_excerpts": 10,
        "project_tree_max_lines": 30,
        "run_cmd_head_tail_lines": 20,
        "run_cmd_compress_threshold": 60,
        "list_symbols_max_entries": 20,
        "generic_head_tail_lines": 20,
        "generic_compress_threshold": 60,
    },
    "strong": {
        "grep_max_excerpts": 5,
        "project_tree_max_lines": 20,
        "run_cmd_head_tail_lines": 10,
        "run_cmd_compress_threshold": 40,
        "list_symbols_max_entries": 12,
        "generic_head_tail_lines": 10,
        "generic_compress_threshold": 40,
    },
}
_DEFAULT_PROFILE = "standard"


def compress_for_history(
    action_name: str, result: str, strength: str = _DEFAULT_PROFILE
) -> str:
    """Dispatch to a tool-specific compressor.

    If the compressed version is not shorter than the original, the
    original is returned unchanged.

    Args:
        action_name: Name of the tool that produced the result.
        result: Raw tool output string.
        strength: Compression profile name ("standard" or "strong"). Callers
            pass ``TierProfile.history_compression`` to ration history size
            by model strength (docs/agent_surface_redesign_design.md §5.2).
            Unknown values fall back to "standard".

    Returns:
        Compressed string suitable for LLM history injection, or the
        original string if compression yields no benefit.
    """
    profile = _COMPRESSION_PROFILES.get(strength, _COMPRESSION_PROFILES[_DEFAULT_PROFILE])

    compressors = {
        "grep_files": _compress_grep,
        "list_files": _compress_project_tree,
        "run_command": _compress_run_command,
        "find_symbol": _compress_list_symbols,
    }

    compressor = compressors.get(action_name)
    if compressor is None:
        # Generic fallback: head/tail compression for long outputs
        if len(result) > 2000:
            return _compress_generic(result, profile)
        return result

    try:
        compressed = compressor(result, profile)
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

def _compress_grep(result: str, profile: Dict[str, int]) -> str:
    """Compress grep_files output to top N matches + summary.

    Keeps:
    - File-level match counts
    - First N match excerpts (exact lines)
    - Total match count
    - Re-search hint

    Drops:
    - Matches beyond the first N
    """
    max_excerpts = profile["grep_max_excerpts"]
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
    parts.append(f"\nTop {max_excerpts} matches:")
    for m in matches[:max_excerpts]:
        parts.append(m)

    if len(matches) > max_excerpts:
        parts.append(f"  ... ({len(matches) - max_excerpts} more matches omitted)")

    # Preserve summary lines (match count, truncation notice, etc.)
    for s in summary_lines:
        if s.strip():
            parts.append(s)

    parts.append("\n[Hint: Re-run grep_files with a narrower pattern or path to see all matches.]")

    return "\n".join(parts)


# --- get_project_tree ---

def _compress_project_tree(result: str, profile: Dict[str, int]) -> str:
    """Compress project tree output to top-level + counts.

    Keeps:
    - Top-level entries (directories and files at depth 1)
    - Total entry count
    - Omission notice

    Drops:
    - Deep nesting (depth 2+)
    """
    lines = result.split("\n")

    if len(lines) <= profile["project_tree_max_lines"]:
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
        f"Use list_files on a specific path to explore further.]",
    ]

    return "\n".join(parts)


# --- run_command (success only) ---

def _compress_run_command(result: str, profile: Dict[str, int]) -> str:
    """Compress successful run_command output to head/tail.

    Keeps:
    - First N lines of output
    - Last N lines of output
    - Omission notice with line count

    Only applies when output exceeds the profile's compress threshold.
    Error outputs (containing "Error:" prefix) are not compressed.
    """
    if result.startswith("Error:"):
        return result  # don't compress error output

    head_tail_lines = profile["run_cmd_head_tail_lines"]
    lines = result.split("\n")

    if len(lines) <= profile["run_cmd_compress_threshold"]:
        return result  # short enough

    head = lines[:head_tail_lines]
    tail = lines[-head_tail_lines:]
    omitted = len(lines) - head_tail_lines * 2

    parts: list[str] = [
        *head,
        f"\n[... {omitted} lines omitted ...]\n",
        *tail,
    ]

    return "\n".join(parts)


# --- list_symbols ---

def _compress_list_symbols(result: str, profile: Dict[str, int]) -> str:
    """Compress list_symbols output to type aggregation + top N entries.

    Keeps:
    - Symbol counts by type (class, function, method, etc.)
    - First N symbol entries
    - Total symbol count

    Drops:
    - Entries beyond the first N
    """
    max_entries = profile["list_symbols_max_entries"]
    lines = result.split("\n")
    if len(lines) <= max_entries:
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

    parts.append(f"\nFirst {max_entries} entries:")
    parts.extend(lines[:max_entries])
    parts.append(f"\n[... {len(lines) - max_entries} more symbols omitted]")

    return "\n".join(parts)


# --- generic fallback ---

def _compress_generic(result: str, profile: Dict[str, int]) -> str:
    """Generic head/tail compression for any long output.

    Keeps:
    - First N lines
    - Last N lines
    - Total line/char count
    """
    head_tail_lines = profile["generic_head_tail_lines"]
    lines = result.split("\n")
    if len(lines) <= profile["generic_compress_threshold"]:
        # Single very long line? Truncate by chars.
        if len(result) > 2000:
            return result[:1000] + f"\n[... {len(result) - 2000} chars omitted ...]\n" + result[-1000:]
        return result

    head = lines[:head_tail_lines]
    tail = lines[-head_tail_lines:]
    omitted = len(lines) - head_tail_lines * 2

    parts: list[str] = [
        f"[{len(lines)} lines, {len(result)} chars]",
        *head,
        f"\n[... {omitted} lines omitted ...]\n",
        *tail,
    ]

    return "\n".join(parts)
