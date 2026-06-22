"""Tests for thought-only fallback and _extract_thoughts block-awareness."""

import pytest
from companion.utils.sym_ops import SymOpsProcessor, FuzzyParser
from companion.base.llm_client import LLMClient
from companion.state.agent_state import ActionList


def test_extract_thoughts_skips_block_content():
    """>> lines inside <<< >>> blocks should NOT be extracted as thoughts."""
    text = (
        ">> Outer thought\n"
        "::response\n"
        "<<<\n"
        ">> This is content, not a thought\n"
        "Some code here\n"
        ">>>\n"
        ">> Another real thought\n"
    )
    parser = FuzzyParser()
    thoughts = parser._extract_thoughts(text)
    assert "Outer thought" in thoughts
    assert "Another real thought" in thoughts
    assert "This is content, not a thought" not in thoughts


def test_extract_thoughts_no_blocks():
    """>> lines without blocks should all be extracted."""
    text = (
        ">> First thought\n"
        ">> Second thought\n"
        "::response @hello\n"
    )
    parser = FuzzyParser()
    thoughts = parser._extract_thoughts(text)
    assert len(thoughts) == 2
    assert "First thought" in thoughts
    assert "Second thought" in thoughts


def test_extract_thoughts_empty():
    """Empty text should produce no thoughts."""
    parser = FuzzyParser()
    assert parser._extract_thoughts("") == []


def test_extract_thoughts_multiple_blocks():
    """Multiple <<< >>> blocks should all be skipped."""
    text = (
        ">> Real thought 1\n"
        "::response\n"
        "<<<\n"
        ">> fake 1\n"
        ">>>\n"
        ">> Real thought 2\n"
        "::note\n"
        "<<<\n"
        ">> fake 2\n"
        ">>>\n"
    )
    parser = FuzzyParser()
    thoughts = parser._extract_thoughts(text)
    assert len(thoughts) == 2
    assert "Real thought 1" in thoughts
    assert "Real thought 2" in thoughts
    assert "fake 1" not in thoughts
    assert "fake 2" not in thoughts


def test_processor_thought_only_fallback():
    """Thought-only output without :: markers gets wrapped by PlainMarkdownConverter."""
    text = (
        ">> Analyzing the code\n"
        ">> Found an issue with the parser\n"
        ">> Need to fix the block detection\n"
    )
    processor = SymOpsProcessor()
    result = processor.process(text)
    # PlainMarkdownConverter wraps this into a response action
    assert len(result.actions) == 1
    assert result.actions[0].type == "response"
    # The >> lines should be in the response content, not in thoughts
    assert "Analyzing the code" in result.actions[0].content


def test_processor_thought_with_vitals_but_no_action():
    """Thoughts + vitals but no action should still produce 0 actions
    from the parser (the thought-only fallback in _parse_response handles this)."""
    text = (
        ">> Analyzing the code\n"
        "::c0.9 ::s1.0 ::m0.5 ::f0.9\n"
        ">> Found an issue\n"
        ">> Need to fix it\n"
    )
    processor = SymOpsProcessor()
    result = processor.process(text)
    # Has :: markers so PlainMarkdownConverter doesn't wrap it
    # But no ::action, so 0 actions
    assert len(result.actions) == 0
    assert len(result.thoughts) == 3


def test_processor_thought_with_action():
    """Normal thought + action should parse correctly."""
    text = (
        ">> I should read the file first\n"
        "::c0.9 ::s1.0 ::m0.5 ::f0.9\n"
        "::read_file @main.py\n"
    )
    processor = SymOpsProcessor()
    result = processor.process(text)
    assert len(result.thoughts) == 1
    assert len(result.actions) == 1
    assert result.actions[0].type == "read_file"


def test_thought_only_with_block_content_not_extracted():
    """Thoughts inside content blocks should not pollute the thought list."""
    text = (
        ">> Real thought\n"
        "::response\n"
        "<<<\n"
        "## Analysis\n"
        ">> This looks like a thought but is content\n"
        "More content\n"
        ">>>\n"
    )
    processor = SymOpsProcessor()
    result = processor.process(text)
    # Only the real thought should be extracted
    assert len(result.thoughts) == 1
    assert "Real thought" in result.thoughts[0]
    assert "This looks like a thought but is content" not in result.thoughts
