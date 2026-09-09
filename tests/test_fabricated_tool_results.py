"""Tests for fabricated tool-result stripping (Sym-Ops hardening)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from companion.utils.sym_ops import SymOpsProcessor  # noqa: E402


def test_strip_removes_envelope_and_status_lines() -> None:
    """Fabricated [TOOL_RESULT] blocks and ::status lines are removed."""
    raw = (
        "::read_file @calc.py\n"
        "[TOOL_RESULT]\n::status ok\n<<<\ncontent here\n>>>\n[/TOOL_RESULT]\n"
        ">> thinking about the result\n"
        "::status ok\n"
        "::response @done\n<<<\nall good\n>>>\n"
    )

    cleaned, removed = SymOpsProcessor._strip_fabricated_tool_results(raw)

    assert removed == 2
    assert "[TOOL_RESULT]" not in cleaned
    assert "::status" not in cleaned
    assert "::read_file @calc.py" in cleaned
    assert "content here" not in cleaned
    assert "::response @done" in cleaned


def test_strip_noop_for_clean_output() -> None:
    """Clean output passes through unchanged with zero removals."""
    raw = ">> thinking\n::run_command @pytest test_calc.py -v\n"

    cleaned, removed = SymOpsProcessor._strip_fabricated_tool_results(raw)

    assert removed == 0
    assert cleaned == raw


def test_process_parses_output_with_fabricated_results() -> None:
    """A transcript-continuing response still yields only real actions."""
    processor = SymOpsProcessor()
    raw = (
        ">> read the file\n"
        "::read_file @calc.py\n"
        "[TOOL_RESULT]\n::status ok\n<<<\n1|def f():\n>>>\n[/TOOL_RESULT]\n"
        ">> the file looks fine\n"
        "::status ok\n"
        "::response @done\n<<<\nfinished\n>>>\n"
    )

    result = processor.process(raw)

    names = [a.type for a in result.actions]
    assert "status" not in names
    assert "read_file" in names
    assert "response" in names
