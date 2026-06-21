from companion.state.agent_state import AgentState


def test_investigation_prompt_context_uses_current_hypothesis_limit() -> None:
    """Investigation context should display the documented five-attempt limit."""
    state = AgentState()
    state.enter_investigation_mode()
    assert state.investigation_state is not None
    state.investigation_state.hypothesis_attempts = 3

    context = state.to_prompt_context()

    assert "hypothesis_attempts=3/5" in context
