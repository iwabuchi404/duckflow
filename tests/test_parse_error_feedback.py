from companion.base.llm_client import LLMClient
from companion.core_loop_helpers import record_parse_error_if_any
from companion.state.agent_state import ActionList, AgentState


def test_full_parse_failure_sets_parse_error_type() -> None:
    """
    When Sym-Ops parsing raises an unexpected exception, the fallback
    ActionList must record why, not just silently wrap the raw text as a
    response — otherwise the model never learns its output was unparseable.
    """
    client = LLMClient(api_key="dummy")

    # SymOpsProcessor.process() is expected to handle malformed text
    # gracefully in the common case; force the exception path directly to
    # verify the fallback branch's error reporting.
    from unittest.mock import patch

    with patch(
        "companion.base.llm_client.SymOpsProcessor.process",
        side_effect=RuntimeError("boom"),
    ):
        result = client._parse_response("::response @hi", ActionList)

    assert result.parse_error_type == "parse_failed"
    assert "boom" in result.parse_error_detail


def test_empty_response_sets_parse_error_type() -> None:
    """A response with no actions, no thoughts, and no reasoning must be
    flagged so the next turn's Correction Guide tells the model nothing
    usable was produced."""
    client = LLMClient(api_key="dummy")

    result = client._parse_response("   \n  ", ActionList)

    assert result.actions == []
    assert result.parse_error_type == "empty_actions"


def test_record_parse_error_if_any_appends_syntax_error() -> None:
    """record_parse_error_if_any should append a Correction Guide entry
    when parse_error_type is set, and do nothing otherwise."""
    state = AgentState()
    action_list = ActionList(
        reasoning="[FALLBACK]",
        actions=[],
        parse_error_type="parse_failed",
        parse_error_detail="raw garbage",
    )

    record_parse_error_if_any(state, action_list)

    assert len(state.last_syntax_errors) == 1
    assert state.last_syntax_errors[0].error_type == "parse_failed"
    assert state.last_syntax_errors[0].raw_snippet == "raw garbage"


def test_record_parse_error_if_any_is_noop_when_parse_succeeded() -> None:
    """A normal, successful ActionList must not add spurious syntax errors."""
    state = AgentState()
    action_list = ActionList(reasoning="ok", actions=[])

    record_parse_error_if_any(state, action_list)

    assert state.last_syntax_errors == []
