"""Tests for the no-progress stall gate.

Reproduces two observed GLM failure modes that produced no tool errors
and therefore escaped every existing counter:

- spec-build r2: propose_plan churned across turns with no real action
  until the run timed out (meta-action stall).
- no-change-hard r2: empty ::response turns spun until LOOP_EXHAUSTED
  because skipped responses never counted as "no progress".

The gate tracks consecutive bookkeeping actions (warn at
STALL_WARN_THRESHOLD, refuse at STALL_FUNNEL_THRESHOLD naming the three
exits) and feeds skipped-response turns into the existing no-progress
counter via turn_was_unproductive().
"""

from companion.core_loop_helpers import turn_was_unproductive
from companion.modules.pacemaker import (
    STALL_FUNNEL_THRESHOLD,
    STALL_WARN_THRESHOLD,
    DuckPacemaker,
)
from companion.state.agent_state import Action, ActionList, AgentState, SyntaxErrorInfo


def _pacemaker() -> DuckPacemaker:
    """Return a Pacemaker bound to a fresh AgentState."""
    return DuckPacemaker(AgentState())


def _plan() -> Action:
    """Return a propose_plan meta action (the GLM churn form)."""
    return Action(name="propose_plan", parameters={"goal": "restructure"})


def _read(path: str = "x.py") -> Action:
    """Return a real (non-meta) action."""
    return Action(name="read_file", parameters={"path": path})


def _response(message: str = "done") -> Action:
    """Return a turn-control action."""
    return Action(name="response", parameters={"message": message})


def _run(pacemaker: DuckPacemaker, action: Action) -> None:
    """Record a successful execution through the normal vitals path."""
    pacemaker.update_vitals(action, "ok", is_error=False)


def _action_list(*actions: Action) -> ActionList:
    """Return an ActionList wrapping the given actions."""
    return ActionList(reasoning="", actions=list(actions))


def _errors(*types: str) -> AgentState:
    """Return a state carrying the given syntax error types."""
    state = AgentState()
    for error_type in types:
        state.last_syntax_errors.append(
            SyntaxErrorInfo(error_type=error_type, raw_snippet="", correction_hint="")
        )
    return state


def test_meta_streak_counts_consecutive_meta_actions() -> None:
    """Consecutive bookkeeping actions accumulate the streak."""
    pacemaker = _pacemaker()
    for _ in range(3):
        _run(pacemaker, _plan())

    assert pacemaker.meta_streak == 3


def test_real_action_resets_meta_streak() -> None:
    """A read/edit/run between plans means legitimate re-planning."""
    pacemaker = _pacemaker()
    for _ in range(3):
        _run(pacemaker, _plan())
    _run(pacemaker, _read())

    assert pacemaker.meta_streak == 0


def test_control_action_preserves_meta_streak() -> None:
    """An interleaved ::response neither advances nor forgives churn."""
    pacemaker = _pacemaker()
    _run(pacemaker, _plan())
    _run(pacemaker, _plan())
    _run(pacemaker, _response("interim note"))
    _run(pacemaker, _plan())

    assert pacemaker.meta_streak == 3


def test_warn_fires_at_threshold() -> None:
    """The warn-level streak surfaces for Correction Guide injection."""
    pacemaker = _pacemaker()
    for _ in range(STALL_WARN_THRESHOLD - 1):
        _run(pacemaker, _plan())
    assert pacemaker.stall_escalation_count(_plan()) == 0

    _run(pacemaker, _plan())
    assert pacemaker.stall_escalation_count(_plan()) == STALL_WARN_THRESHOLD


def test_warn_ignores_non_meta_actions() -> None:
    """A real action never triggers the stall warning itself."""
    pacemaker = _pacemaker()
    for _ in range(STALL_WARN_THRESHOLD + 2):
        _run(pacemaker, _plan())

    assert pacemaker.stall_escalation_count(_read()) == 0


def test_funnel_blocks_meta_at_threshold() -> None:
    """Once past the funnel level, further meta actions are refused."""
    pacemaker = _pacemaker()
    for _ in range(STALL_FUNNEL_THRESHOLD):
        _run(pacemaker, _plan())

    refusal = pacemaker.check_stall_block(_plan())

    assert refusal is not None
    assert "BLOCKED" in refusal
    # The refusal must name all three exits.
    assert "response" in refusal
    assert "duck_call" in refusal


def test_funnel_allows_meta_below_threshold() -> None:
    """Below the funnel level meta actions still execute — warn only."""
    pacemaker = _pacemaker()
    for _ in range(STALL_FUNNEL_THRESHOLD - 1):
        _run(pacemaker, _plan())

    assert pacemaker.check_stall_block(_plan()) is None


def test_funnel_never_blocks_real_actions() -> None:
    """Reads, edits, and commands are always allowed — they are the exit."""
    pacemaker = _pacemaker()
    for _ in range(STALL_FUNNEL_THRESHOLD + 3):
        _run(pacemaker, _plan())

    assert pacemaker.check_stall_block(_read()) is None
    edit = Action(name="edit_file", parameters={"path": "x.py"})
    run = Action(name="run_command", parameters={"command": "pytest"})
    assert pacemaker.check_stall_block(edit) is None
    assert pacemaker.check_stall_block(run) is None


def test_blocked_meta_keeps_streak_alive() -> None:
    """Refused meta actions record as errors and keep the streak growing,
    so repeated attempts stay blocked and feed the cascade."""
    pacemaker = _pacemaker()
    for _ in range(STALL_FUNNEL_THRESHOLD):
        _run(pacemaker, _plan())

    refusal = pacemaker.check_stall_block(_plan())
    assert refusal is not None
    pacemaker.update_vitals(_plan(), refusal, is_error=True)

    assert pacemaker.meta_streak == STALL_FUNNEL_THRESHOLD + 1
    assert pacemaker.check_stall_block(_plan()) is not None


def test_meta_streak_covers_all_meta_actions() -> None:
    """Notes and task bookkeeping count as meta, not just propose_plan."""
    pacemaker = _pacemaker()
    for name in ("note", "mark_step_complete", "generate_tasks"):
        _run(pacemaker, Action(name=name, parameters={}))

    assert pacemaker.meta_streak == 3


def test_reset_clears_meta_streak() -> None:
    """Session reset must clear the stall-gate state."""
    pacemaker = _pacemaker()
    for _ in range(3):
        _run(pacemaker, _plan())

    pacemaker.reset()

    assert pacemaker.meta_streak == 0


def test_turn_unproductive_when_only_empty_response() -> None:
    """A turn ending on a skipped empty response produced nothing."""
    action_list = _action_list(_response(""))
    state = _errors("empty_response")

    assert turn_was_unproductive(action_list, state) is True


def test_turn_unproductive_for_premature_and_auto_response() -> None:
    """Premature announcements and auto-generated responses count too."""
    for error_type in ("premature_response", "auto_response"):
        action_list = _action_list(_response("修正します"))
        state = _errors(error_type)
        assert turn_was_unproductive(action_list, state) is True


def test_turn_productive_when_real_action_present() -> None:
    """A skipped response after real work is not churn — work happened."""
    action_list = _action_list(_read(), _response(""))
    state = _errors("empty_response")

    assert turn_was_unproductive(action_list, state) is False


def test_turn_productive_without_skipped_response() -> None:
    """Ordinary mid-work turns carry no skipped-response errors."""
    action_list = _action_list(_read())
    state = _errors()

    assert turn_was_unproductive(action_list, state) is False


def test_turn_unproductive_meta_plus_empty_response() -> None:
    """A plan followed by an empty response is still an unproductive turn."""
    action_list = _action_list(_plan(), _response(""))
    state = _errors("empty_response")

    assert turn_was_unproductive(action_list, state) is True
