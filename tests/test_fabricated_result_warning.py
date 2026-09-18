"""Tests for fabricated tool-result warnings (Correction Guide routing)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from companion.core_loop_helpers import _PARSE_ERROR_HINTS  # noqa: E402
from companion.prompts.builder import PromptBuilder  # noqa: E402
from companion.utils.sym_ops import (  # noqa: E402
    FABRICATED_RESULT_WARNING,
    SymOpsProcessor,
)


def test_fabricated_envelope_is_stripped_and_flagged() -> None:
    """Model-authored [TOOL_RESULT] must not survive parsing."""
    raw = (
        "::read_file @calc.py\n"
        "[TOOL_RESULT]\n::status ok\ncontent here\n[/TOOL_RESULT]\n"
    )
    result = SymOpsProcessor().process(raw)

    assert FABRICATED_RESULT_WARNING in result.warnings
    assert "[TOOL_RESULT]" not in str(result.actions)


def test_fabricated_status_line_is_flagged() -> None:
    """Bare model-authored ::status lines are flagged too."""
    result = SymOpsProcessor().process("::status ok\n::read_file @calc.py\n")

    assert FABRICATED_RESULT_WARNING in result.warnings
    assert [a.type for a in result.actions] == ["read_file"]


def test_genuine_output_unflagged() -> None:
    """Normal actions carry no fabrication warning."""
    result = SymOpsProcessor().process("::read_file @calc.py\n")

    assert FABRICATED_RESULT_WARNING not in result.warnings


def test_correction_guide_covers_fabricated_result() -> None:
    """Hint map and few-shot examples must know the new error type."""
    assert "fabricated_tool_result" in _PARSE_ERROR_HINTS
    assert "fabricated_tool_result" in PromptBuilder._CORRECTION_EXAMPLES
