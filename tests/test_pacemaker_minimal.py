from companion.modules.pacemaker import DuckPacemaker
from companion.state.agent_state import Action, AgentState


def test_pacemaker_detects_repeated_action_stagnation() -> None:
    """
    Repeating the same action with the same parameters should trigger
    stagnation intervention.
    """
    pacemaker = DuckPacemaker(AgentState())
    action = Action(name="read_file", parameters={"path": "same.py"})

    for _ in range(4):
        pacemaker.update_vitals(action, "same result", is_error=False)

    reason = pacemaker.check_health()

    assert reason is not None
    assert reason.type == "STAGNATION"


def test_pacemaker_detects_error_cascade_after_three_errors() -> None:
    """Three consecutive errors should be classified as an error cascade."""
    state = AgentState()
    pacemaker = DuckPacemaker(state)

    for index in range(3):
        pacemaker.update_vitals(
            Action(name="run_command", parameters={"command": f"bad-{index}"}),
            f"error-{index}",
            is_error=True,
        )

    reason = pacemaker.check_health()

    assert reason is not None
    assert reason.type == "ERROR_CASCADE"


def test_pacemaker_max_loops_is_clamped_to_supported_range() -> None:
    """Dynamic loop calculation should stay inside the documented 3..35 range."""
    state = AgentState()
    state.vitals.confidence = 0.0
    state.vitals.safety = 0.0
    state.vitals.memory = 0.0
    state.vitals.focus = 0.0

    low = DuckPacemaker(state).calculate_max_loops()

    state.vitals.confidence = 1.0
    state.vitals.safety = 1.0
    state.vitals.memory = 1.0
    state.vitals.focus = 1.0
    high = DuckPacemaker(state).calculate_max_loops()

    assert 3 <= low <= 35
    assert 3 <= high <= 35
