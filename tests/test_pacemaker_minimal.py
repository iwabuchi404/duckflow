from companion.modules.pacemaker import DuckPacemaker
from companion.state.agent_state import Action, AgentState, MAX_HYPOTHESIS_ATTEMPTS


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


def test_pacemaker_detects_recent_error_rate_without_consecutive_errors() -> None:
    """Five errors in the recent ten actions should trigger an error cascade."""
    state = AgentState()
    pacemaker = DuckPacemaker(state)

    for index in range(10):
        pacemaker.update_vitals(
            Action(name="run_command", parameters={"command": f"cmd-{index}"}),
            f"result-{index}",
            is_error=index % 2 == 0,
        )

    reason = pacemaker.check_health()

    assert pacemaker.consecutive_errors == 0
    assert reason is not None
    assert reason.type == "ERROR_CASCADE"


def test_pacemaker_investigation_stuck_uses_shared_hypothesis_limit() -> None:
    """Investigation stuck intervention should wait for the documented limit."""
    state = AgentState()
    state.enter_investigation_mode()
    assert state.investigation_state is not None
    pacemaker = DuckPacemaker(state)

    state.investigation_state.hypothesis_attempts = MAX_HYPOTHESIS_ATTEMPTS - 1
    assert pacemaker.check_health() is None

    state.investigation_state.hypothesis_attempts = MAX_HYPOTHESIS_ATTEMPTS
    reason = pacemaker.check_health()

    assert reason is not None
    assert reason.type == "INVESTIGATION_STUCK"


def test_pacemaker_max_loops_is_clamped_to_supported_range() -> None:
    """Dynamic loop calculation should stay inside the documented 3..35 range.
    V-A2: max_loops no longer depends on declared vitals — only on execution_history."""
    state = AgentState()
    pacemaker = DuckPacemaker(state)

    # No execution history → neutral factor (1.0)
    loops = pacemaker.calculate_max_loops()
    assert 3 <= loops <= 35

    # With execution history showing high success rate → factor 1.2
    for i in range(10):
        pacemaker.update_vitals(
            Action(name="read_file", parameters={"path": f"file{i}.py"}),
            f"result-{i}",
            is_error=False,
        )
    loops_high = pacemaker.calculate_max_loops()
    assert 3 <= loops_high <= 35
    assert loops_high >= loops  # high success rate should not reduce loops
