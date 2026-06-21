"""Tests for S3-8: reasoning model integration.

Tests that:
1. _extract_reasoning extracts reasoning from various message formats
2. reasoning_to_thought converts reasoning to >> Thought lines
3. strip_reasoning_tags returns extracted reasoning content
4. SymOpsProcessor injects imd reasoning as >> Thought
"""
from companion.utils.preprocessor import strip_reasoning_tags, reasoning_to_thought
from companion.utils.sym_ops import SymOpsProcessor


# --- _extract_reasoning ---


def _make_message(reasoning=None, reasoning_content=None, content="hello"):
    """Create a mock message object with optional reasoning fields."""
    class MockMessage:
        def __init__(self):
            self.content = content
            if reasoning is not None:
                self.reasoning = reasoning
            if reasoning_content is not None:
                self.reasoning_content = reasoning_content
            self.model_extra_fields = {}
            if reasoning is not None:
                self.model_extra_fields["reasoning"] = reasoning
            if reasoning_content is not None:
                self.model_extra_fields["reasoning_content"] = reasoning_content

    return MockMessage()


def test_extract_reasoning_direct_attr():
    from companion.base.llm_client import _extract_reasoning
    msg = _make_message(reasoning="thinking about the problem")
    assert _extract_reasoning(msg) == "thinking about the problem"


def test_extract_reasoning_content_attr():
    from companion.base.llm_client import _extract_reasoning
    msg = _make_message(reasoning_content="analyzing code structure")
    assert _extract_reasoning(msg) == "analyzing code structure"


def test_extract_reasoning_none():
    from companion.base.llm_client import _extract_reasoning
    msg = _make_message()
    assert _extract_reasoning(msg) is None


def test_extract_reasoning_empty_string():
    from companion.base.llm_client import _extract_reasoning
    msg = _make_message(reasoning="   ")
    assert _extract_reasoning(msg) is None


# --- reasoning_to_thought ---


def test_reasoning_to_thought_basic():
    result = reasoning_to_thought("line1\nline2\nline3")
    assert result == ">> line1\n>> line2\n>> line3"


def test_reasoning_to_thought_skips_empty_lines():
    result = reasoning_to_thought("line1\n\nline2")
    assert result == ">> line1\n>> line2"


def test_reasoning_to_thought_strips_whitespace():
    result = reasoning_to_thought("  line1  \n  line2  ")
    assert result == ">> line1\n>> line2"


# --- strip_reasoning_tags 3-tuple ---


def test_strip_returns_reasoning_content():
    text = "<think>my reasoning process</think>\n::response\n<<<\nhi\n>>>"
    stripped, was, reasoning = strip_reasoning_tags(text)
    assert was is True
    assert reasoning == "my reasoning process"
    assert "my reasoning process" not in stripped
    assert "hi" in stripped


def test_strip_returns_none_reasoning_when_no_blocks():
    text = "::response\n<<<\nhi\n>>>"
    stripped, was, reasoning = strip_reasoning_tags(text)
    assert was is False
    assert reasoning is None


def test_strip_returns_none_reasoning_for_orphan_tags():
    text = "::response\n<<<\nhi\n</think>\n>>>"
    stripped, was, reasoning = strip_reasoning_tags(text)
    assert was is True
    assert reasoning is None  # orphan tags have no content to extract


def test_strip_extracts_multiple_blocks():
    text = "<think>first thought</think>\nmiddle\n<think>second thought</think>\n::response"
    stripped, was, reasoning = strip_reasoning_tags(text)
    assert was is True
    assert reasoning is not None
    assert "first thought" in reasoning
    assert "second thought" in reasoning


# --- SymOpsProcessor integration ---


def test_processor_injects_imd_reasoning_as_thought():
    """imd block content should appear as >> Thought in parsed result."""
    raw = (
        "<think>I should respond with a greeting.</think>\n"
        "::c1.0\n"
        ">> Initial thought\n"
        "::response\n"
        "<<<\nHello!\n"
        ">>>"
    )
    result = SymOpsProcessor().process(raw)

    # The reasoning should appear as a thought
    all_thoughts = "\n".join(result.thoughts)
    assert "I should respond with a greeting" in all_thoughts

    # response content should not contain the reasoning
    response_contents = [a.content for a in result.actions if a.type == "response"]
    assert response_contents
    for content in response_contents:
        assert "I should respond with a greeting" not in content


def test_processor_still_strips_imd_from_response():
    """imd tags should not leak into response content (regression test)."""
    raw = (
        "<think>hidden reasoning</think>\n"
        "::response\n"
        "<<<\nVisible content\n"
        ">>>"
    )
    result = SymOpsProcessor().process(raw)

    response_contents = [a.content for a in result.actions if a.type == "response"]
    assert response_contents
    for content in response_contents:
        assert "<think>" not in content
        assert "</think>" not in content
        assert "hidden reasoning" not in content
