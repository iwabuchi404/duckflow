"""Tests for consecutive action dedup and repetition truncation."""

from companion.utils.sym_ops import SymOpsProcessor, FuzzyParser


def test_dedup_consecutive_identical_actions():
    """strict_parse should collapse consecutive identical action lines."""
    text = "\n".join([
        ">> thought",
        "::read_file @companion/tools",
        "::read_file @companion/tools",
        "::read_file @companion/tools",
        "::read_file @companion/tools",
        "::read_file @companion/tools",
        "::response",
        "<<<",
        "done",
        ">>>",
    ])
    processor = SymOpsProcessor()
    result = processor.process(text)
    action_types = [a.type for a in result.actions]
    assert action_types == ["read_file", "response"]


def test_dedup_keeps_different_actions():
    """Non-consecutive or different actions should not be deduped."""
    text = "\n".join([
        "::read_file @a.py",
        "::read_file @b.py",
        "::read_file @a.py",
    ])
    processor = SymOpsProcessor()
    result = processor.process(text)
    assert len(result.actions) == 3


def test_truncate_repetition_collapses_repeated_lines():
    """_truncate_repetition should keep only threshold copies of repeated lines."""
    text = "\n".join(["::read_file @same.py"] * 20)
    truncated = SymOpsProcessor._truncate_repetition(text, threshold=3)
    lines = truncated.split("\n")
    # 3 copies of the line + empty line from \n prefix + system message
    assert len(lines) == 5
    assert "truncated" in lines[-1]


def test_truncate_repetition_preserves_normal_output():
    """Normal output without repetition should pass through unchanged."""
    text = ">> thought\n::read_file @a.py\n::response\n<<<\nhello\n>>>"
    truncated = SymOpsProcessor._truncate_repetition(text, threshold=5)
    assert truncated == text


def test_processor_truncates_then_dedups():
    """Full pipeline: repetition truncation + dedup should reduce 50 repeats to 1 action."""
    text = "\n".join(["::read_file @same.py"] * 50)
    processor = SymOpsProcessor()
    result = processor.process(text)
    assert len(result.actions) == 1
    assert result.actions[0].type == "read_file"
