"""Tests for tool_history_policy compression functions."""

from companion.tool_history_policy import compress_for_history


# --- compress_for_history dispatcher ---


def test_unknown_tool_returns_original():
    result = compress_for_history("unknown_tool", "some output")
    assert result == "some output"


def test_short_result_returns_original():
    """Short results should not be compressed."""
    result = compress_for_history("grep_files", "No matches found")
    assert result == "No matches found"


# --- grep_files compression ---


def test_grep_compresses_large_output():
    """grep_files with many matches should be compressed to top N + summary."""
    lines = []
    for i in range(30):
        lines.append(f"src/file_{i % 3}.py:{i + 1}: match text {i}")
    lines.append("")
    lines.append("30 match(es) found.")
    raw = "\n".join(lines)

    compressed = compress_for_history("grep_files", raw)
    assert len(compressed) < len(raw)
    assert "Files with matches" in compressed
    assert "Top 10 matches" in compressed
    assert "more matches omitted" in compressed
    assert "Re-run grep_files" in compressed


def test_grep_preserves_no_matches_message():
    """grep_files with no matches should pass through unchanged."""
    raw = "No matches found for pattern 'foo' in '.' (include='*.py')"
    compressed = compress_for_history("grep_files", raw)
    assert compressed == raw


def test_grep_keeps_file_level_counts():
    """grep_files compression should include per-file match counts."""
    lines = []
    for i in range(25):
        file_idx = i % 3
        lines.append(f"src/file_{file_idx}.py:{i + 1}: foo")
    lines.append("")
    lines.append("25 match(es) found.")
    raw = "\n".join(lines)

    compressed = compress_for_history("grep_files", raw)
    assert "src/file_0.py:" in compressed
    assert "match(es)" in compressed


# --- get_project_tree compression ---


def test_project_tree_compresses_deep_nesting():
    """Large project tree should be compressed to top-level + counts."""
    lines = []
    for i in range(50):
        if i < 5:
            lines.append(f"dir_{i}/")
        else:
            lines.append(f"  file_{i}.py")
    raw = "\n".join(lines)

    compressed = compress_for_history("get_project_tree", raw)
    assert len(compressed) < len(raw)
    assert "Top-level entries" in compressed
    assert "Omitted" in compressed
    assert "list_directory" in compressed


def test_project_tree_short_passes_through():
    """Short project tree should not be compressed."""
    raw = "dir_a/\nfile_b.py\nfile_c.py"
    compressed = compress_for_history("get_project_tree", raw)
    assert compressed == raw


# --- run_command compression ---


def test_run_command_compresses_long_output():
    """Long successful command output should be compressed to head/tail."""
    lines = [f"line {i}" for i in range(100)]
    raw = "\n".join(lines)

    compressed = compress_for_history("run_command", raw)
    assert len(compressed) < len(raw)
    assert "lines omitted" in compressed
    assert "line 0" in compressed  # head
    assert "line 99" in compressed  # tail


def test_run_command_short_passes_through():
    """Short command output should not be compressed."""
    raw = "line 1\nline 2\nline 3"
    compressed = compress_for_history("run_command", raw)
    assert compressed == raw


def test_run_command_error_not_compressed():
    """Error output should not be compressed."""
    raw = "Error: Command failed\n" + "\n".join(f"line {i}" for i in range(100))
    compressed = compress_for_history("run_command", raw)
    assert compressed == raw


# --- build_tool_result_message with history_content ---


def test_build_tool_result_message_uses_history_content():
    """When history_content is provided, it should appear in the envelope."""
    from companion.core_action_results import build_tool_result_message
    from companion.state.agent_state import Action
    from companion.tools.results import is_tool_result_message

    action = Action(name="grep_files", parameters={"pattern": "foo", "path": "src"})
    raw = "line1\nline2\n" * 50
    history = "compressed content"

    msg = build_tool_result_message(action, raw, history_content=history)
    assert is_tool_result_message(msg)
    assert "compressed content" in msg
    assert "line1\nline2" not in msg


def test_build_tool_result_message_without_history_content():
    """Without history_content, raw content should be used (backward compat)."""
    from companion.core_action_results import build_tool_result_message
    from companion.state.agent_state import Action

    action = Action(name="read_file", parameters={"path": "test.py"})
    msg = build_tool_result_message(action, "raw content here")
    assert "raw content here" in msg
