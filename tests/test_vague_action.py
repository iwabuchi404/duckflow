"""Tests for vague action-attempt routing (no fabricated termination)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from companion.utils.sym_ops import SymOpsProcessor, VAGUE_ACTION_WARNING  # noqa: E402


def test_thought_shaped_action_is_flagged_not_executed() -> None:
    """'>> read_file @x' must not become a terminating response."""
    result = SymOpsProcessor().process(">> read_file @test_app.py\n")

    assert VAGUE_ACTION_WARNING in result.warnings
    assert all(a.type != "response" for a in result.actions)


def test_genuine_prose_still_responds() -> None:
    """Plain prose without tool references keeps the response fallback."""
    result = SymOpsProcessor().process("The fix is complete, all done.\n")

    assert VAGUE_ACTION_WARNING not in result.warnings
    assert any(a.type == "response" for a in result.actions)


def test_explicit_action_unaffected() -> None:
    """Explicit ::action syntax is never flagged vague."""
    result = SymOpsProcessor().process("::read_file @calc.py\n")

    assert VAGUE_ACTION_WARNING not in result.warnings
    assert [a.type for a in result.actions] == ["read_file"]
