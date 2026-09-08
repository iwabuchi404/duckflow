"""Sym-Ops protocol boundary and compatibility regression tests."""

import math

import pytest

from companion.base.llm_client import LLMClient
from companion.core_loop_helpers import update_vitals_from_response
from companion.state.agent_state import ActionList, AgentState
from companion.utils.parser import DuckflowParser
from companion.utils.sym_ops import FuzzyParser, ParseError, SymOpsProcessor


def _parse_action_list(text: str) -> ActionList:
    """Parse text through the production main-agent mapping path.

    Args:
        text: Raw Sym-Ops response.

    Returns:
        Parsed internal action list.
    """
    return LLMClient(api_key="dummy")._parse_response(text, ActionList)


def test_インラインターゲットをツールの主引数へ変換する() -> None:
    """`@` should map to each tool's primary parameter.

    Returns:
        None.
    """
    result = _parse_action_list("::response @Hello\n::investigate @why it fails")

    assert result.actions[0].parameters == {"message": "Hello"}
    assert result.actions[1].parameters == {"reason": "why it fails"}


def test_空白入りパスと引用パラメータを保持する() -> None:
    """Paths and quoted parameter values containing spaces should survive.

    Returns:
        None.
    """
    parsed = SymOpsProcessor().process(
        '::grep_files @docs/My Project pattern="foo bar" include="*.py"'
    )

    action = parsed.actions[0]
    assert action.path == "docs/My Project"
    assert action.params == {"pattern": "foo bar", "include": "*.py"}


def test_旧パーサーAPIを現行パイプラインへ委譲する() -> None:
    """The compatibility parser should preserve canonical target semantics.

    Returns:
        None.
    """
    result = DuckflowParser().parse("::response @Hello")

    assert result.parse_errors == []
    assert result.actions[0].type == "response"
    assert result.actions[0].target == "Hello"


def test_vitalsは小数精度を保持し範囲外を拒否する() -> None:
    """Vitals should allow arbitrary decimals but reject values outside 0-1.

    Returns:
        None.
    """
    parsed = SymOpsProcessor().process(
        "::c0.88 ::s1.5 ::m-0.1 ::f0.95\n::response @done"
    )

    assert parsed.vitals == {"confidence": 0.88, "focus": 0.95}
    assert any(
        "safety" in warning and "out-of-range" in warning for warning in parsed.warnings
    )
    assert any(
        "memory" in warning and "out-of-range" in warning for warning in parsed.warnings
    )


def test_状態更新でも不正なvitalsを拒否する() -> None:
    """State updates should ignore invalid values from non-parser callers.

    Returns:
        None.
    """
    state = AgentState()
    state.vitals.safety = 0.7
    state.vitals.memory = 0.6
    action_list = ActionList(
        reasoning="test",
        actions=[],
        vitals={
            "confidence": 0.5,
            "safety": 1.5,
            "memory": math.nan,
        },
    )

    update_vitals_from_response(state, action_list)

    assert state.vitals.confidence == 0.5
    assert state.vitals.safety == 0.7
    assert state.vitals.memory == 0.6


def test_単独終端行をエスケープして本文へ復元する() -> None:
    """Escaped terminators should round-trip without closing the block.

    Returns:
        None.
    """
    parsed = SymOpsProcessor().process(
        "::write_file @sample.txt\n<<<\n\\>>>\n\\\\>>>\n>>>"
    )

    assert parsed.actions[0].content == ">>>\n\\>>>"


def test_本文中の開始マーカーを破壊しない() -> None:
    """A literal `<<<` line inside content should not reset its buffer.

    Returns:
        None.
    """
    parsed = SymOpsProcessor().process(
        "::write_file @sample.txt\n<<<\nbefore\n<<<\nafter\n>>>"
    )

    assert parsed.actions[0].content == "before\n<<<\nafter"


def test_strict構造エラーを具体化してfuzzyへ退避する() -> None:
    """Structural failures should be actionable and still recover actions.

    Returns:
        None.
    """
    with pytest.raises(ParseError, match="line 1.*expected"):
        FuzzyParser().strict_parse(">>>")

    parsed = SymOpsProcessor().process("::response @ok\n>>>")

    assert parsed.actions[0].type == "response"
    assert parsed.actions[0].path == "ok"
    assert any(
        "Strict parse failed" in warning and "line 2" in warning
        for warning in parsed.warnings
    )


def test_回復不能な構造エラーをCorrection_Guideへ渡す() -> None:
    """Unrecoverable syntax errors should retain expected and actual forms.

    Returns:
        None.
    """
    result = _parse_action_list(":: @bad")

    assert result.actions == []
    assert result.parse_error_type == "parse_failed"
    assert "expected" in result.parse_error_detail
    assert "actual" in result.parse_error_detail
    assert ":: @bad" in result.parse_error_detail
