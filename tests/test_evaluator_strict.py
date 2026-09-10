"""Tests for strict verification ordering and no_edit coverage."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals.analysis import tag_no_edit_applied, tag_verified_edit_success  # noqa: E402


def test_strict_ignores_success_before_last_edit() -> None:
    """A successful command before the last edit does not count."""
    history = [
        {"role": "assistant", "content": ":: run_command @pytest"},
        {
            "role": "user",
            "content": "[TOOL_RESULT]\n::run_command @pytest\n<<<\nok\nexit_code: 0\n>>>\n[/TOOL_RESULT]",
        },
        {"role": "assistant", "content": ":: edit_file @calc.py"},
        {
            "role": "user",
            "content": "[TOOL_RESULT]\n::status ok\n::edit_file @calc.py\n<<<\nedited\n>>>\n[/TOOL_RESULT]",
        },
    ]

    assert tag_verified_edit_success(history) is False


def test_strict_counts_success_after_last_edit_result() -> None:
    """A successful command after the last edit result counts."""
    history = [
        {"role": "assistant", "content": ":: edit_file @calc.py"},
        {
            "role": "user",
            "content": "[TOOL_RESULT]\n::status ok\n::edit_file @calc.py\n<<<\nedited\n>>>\n[/TOOL_RESULT]",
        },
        {"role": "assistant", "content": ":: run_command @pytest"},
        {
            "role": "user",
            "content": "[TOOL_RESULT]\n::run_command @pytest\n<<<\nok\nexit_code: 0\n>>>\n[/TOOL_RESULT]",
        },
    ]

    assert tag_verified_edit_success(history) is True


def test_no_edit_covers_replace_function() -> None:
    """replace_function counts as an edit action."""
    history = [{"role": "assistant", "content": ":: replace_function @a.py"}]

    assert tag_no_edit_applied(history) is False
