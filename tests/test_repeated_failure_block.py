"""Tests for repeated-identical-failure detection and escalation.

Reproduces the GLM rename-hard failure: the model resent an empty-body
edit_file six times across turns despite correct Correction Guide hints,
burning ~140k tokens. The fix tracks failure signatures that survive
interleaved successes (unlike consecutive_errors), escalates the guide
at the 3rd repeat, hard-blocks verbatim contract-error repeats from the
4th attempt, and feeds ERROR_CASCADE at 5.
"""

from companion.modules.pacemaker import (
    REPEAT_BLOCK_THRESHOLD,
    REPEAT_CASCADE_THRESHOLD,
    DuckPacemaker,
    _is_contract_error,
)
from companion.state.agent_state import Action, AgentState

EMPTY_EDIT_ERROR = (
    "Action 'edit_file' failed: Reason: No find/replace details found "
    "in content block. Fix: Send the edit body with SEARCH/REPLACE markers."
)
MISMATCH_ERROR = (
    "Action 'edit_file' failed: find_not_matched — the SEARCH block did "
    "not match any content in the file."
)
PYTEST_ERROR = "Action 'run_command' failed: exit code 1\nFAILED tests/"


def _pacemaker() -> DuckPacemaker:
    """Return a Pacemaker bound to a fresh AgentState."""
    return DuckPacemaker(AgentState())


def _edit(path: str = "service.py") -> Action:
    """Return an empty-body edit_file action (the GLM failure form)."""
    return Action(name="edit_file", parameters={"path": path})


def _fail(pacemaker: DuckPacemaker, action: Action, error: str) -> None:
    """Record an error result through the normal vitals path."""
    pacemaker.update_vitals(action, error, is_error=True)


def _succeed(pacemaker: DuckPacemaker, action: Action) -> None:
    """Record a successful result through the normal vitals path."""
    pacemaker.update_vitals(action, "ok", is_error=False)


def test_signature_counts_identical_calls() -> None:
    """Three identical failing calls are counted under one signature."""
    pacemaker = _pacemaker()
    action = _edit()

    for _ in range(3):
        _fail(pacemaker, action, EMPTY_EDIT_ERROR)

    assert pacemaker.repeated_call_count(action) == 3


def test_different_params_do_not_group() -> None:
    """Calls with different arguments are legitimate iteration, not repeats."""
    pacemaker = _pacemaker()
    _fail(pacemaker, _edit("a.py"), EMPTY_EDIT_ERROR)
    _fail(pacemaker, _edit("b.py"), EMPTY_EDIT_ERROR)

    assert pacemaker.repeated_call_count(_edit("a.py")) == 1
    assert pacemaker.repeated_call_count(_edit("b.py")) == 1
    # ...but the tool+kind level still catches "same error, different args"
    assert pacemaker.repeated_kind_count(_edit("c.py")) == 2


def test_interleaved_success_preserves_signature_count() -> None:
    """A successful read_file must NOT reset the edit_file failure count.

    This is the gap in consecutive_errors: any success resets it, so
    failures separated by successful reads were invisible.
    """
    pacemaker = _pacemaker()
    action = _edit()
    read = Action(name="read_file", parameters={"path": "x.py"})

    for _ in range(3):
        _fail(pacemaker, action, EMPTY_EDIT_ERROR)
        _succeed(pacemaker, read)

    assert pacemaker.consecutive_errors == 0  # reset by the success
    assert pacemaker.repeated_call_count(action) == 3  # but signature kept


def test_success_of_same_tool_resets_its_counters() -> None:
    """A successful edit_file forgives prior edit_file failures."""
    pacemaker = _pacemaker()
    action = _edit()

    for _ in range(3):
        _fail(pacemaker, action, EMPTY_EDIT_ERROR)
    _succeed(pacemaker, _edit())

    assert pacemaker.repeated_call_count(action) == 0
    assert pacemaker.repeated_kind_count(action) == 0


def test_repeat_block_refuses_verbatim_contract_error() -> None:
    """The 4th identical contract-error call is refused pre-execution."""
    pacemaker = _pacemaker()
    action = _edit()

    for _ in range(REPEAT_BLOCK_THRESHOLD):
        _fail(pacemaker, action, EMPTY_EDIT_ERROR)

    refusal = pacemaker.check_repeat_block(action)

    assert refusal is not None
    assert "BLOCKED" in refusal
    assert "edit_file" in refusal
    assert "SEARCH" in refusal  # concrete recovery instruction


def test_repeat_block_never_blocks_state_dependent_errors() -> None:
    """find_mismatch / pytest failures must never be hard-blocked.

    The workspace may have changed between attempts — rerunning pytest
    after a fix is legitimate and expected to succeed eventually.
    """
    pacemaker = _pacemaker()
    edit = _edit()
    pytest_call = Action(name="run_command", parameters={"command": "pytest"})

    for _ in range(REPEAT_BLOCK_THRESHOLD + 1):
        _fail(pacemaker, edit, MISMATCH_ERROR)
        _fail(pacemaker, pytest_call, PYTEST_ERROR)

    assert pacemaker.check_repeat_block(edit) is None
    assert pacemaker.check_repeat_block(pytest_call) is None


def test_repeat_block_does_not_fire_below_threshold() -> None:
    """Two identical failures are still within normal retry budget."""
    pacemaker = _pacemaker()
    action = _edit()

    for _ in range(REPEAT_BLOCK_THRESHOLD - 1):
        _fail(pacemaker, action, EMPTY_EDIT_ERROR)

    assert pacemaker.check_repeat_block(action) is None


def test_escalation_count_triggers_at_warn_threshold() -> None:
    """The 3rd identical failure escalates the Correction Guide."""
    pacemaker = _pacemaker()
    action = _edit()

    _fail(pacemaker, action, EMPTY_EDIT_ERROR)
    _fail(pacemaker, action, EMPTY_EDIT_ERROR)
    assert pacemaker.repeat_escalation_count(action) == 0

    _fail(pacemaker, action, EMPTY_EDIT_ERROR)
    assert pacemaker.repeat_escalation_count(action) == 3


def test_cascade_fires_on_repeated_signature_with_interleaved_success() -> None:
    """ERROR_CASCADE catches same-signature repeats despite successes.

    consecutive_errors resets on each success, so the generic check
    never fires — the signature-based check must.
    """
    pacemaker = _pacemaker()
    action = _edit()
    read = Action(name="read_file", parameters={"path": "x.py"})

    for _ in range(REPEAT_CASCADE_THRESHOLD):
        _fail(pacemaker, action, EMPTY_EDIT_ERROR)
        _succeed(pacemaker, read)

    assert pacemaker.consecutive_errors == 0
    assert pacemaker._detect_error_cascade() is True


def test_cascade_quiet_for_varied_failures() -> None:
    """Distinct failure kinds don't accumulate into a false cascade.

    Successes are interleaved so the generic consecutive_errors and
    error-rate checks stay quiet — this isolates the signature check.
    """
    pacemaker = _pacemaker()
    read = Action(name="read_file", parameters={"path": "x.py"})
    read2 = Action(name="read_file", parameters={"path": "y.py"})
    for i in range(REPEAT_CASCADE_THRESHOLD):
        _fail(
            pacemaker,
            _edit(f"file{i}.py"),
            f"Action 'edit_file' failed: Reason: different problem {i}",
        )
        _succeed(pacemaker, read)
        _succeed(pacemaker, read2)

    assert pacemaker._max_repeated_failures() == 1
    assert pacemaker._detect_error_cascade() is False


def test_reset_clears_signature_counters() -> None:
    """Session reset must clear repeat-failure state."""
    pacemaker = _pacemaker()
    for _ in range(3):
        _fail(pacemaker, _edit(), EMPTY_EDIT_ERROR)

    pacemaker.reset()

    assert pacemaker.repeated_call_count(_edit()) == 0
    assert pacemaker._max_repeated_failures() == 0


def test_contract_error_classification() -> None:
    """Contract markers classify correctly; state-dependent ones don't."""
    assert _is_contract_error("no find/replace details found")
    assert _is_contract_error("access denied to /etc/passwd")
    assert _is_contract_error("outside workspace")
    assert not _is_contract_error("find_not_matched")
    assert not _is_contract_error("exit code 1")


def test_defect_block_catches_rotating_target() -> None:
    """Empty-body edits to *different* files still get blocked.

    Reproduces GLM rename-hard r1: store.py/api.py succeeded, then the
    model resent the same malformed empty body to cli.py, worker.py,
    reports.py — rotating targets defeats verbatim signatures, so the
    shared form defect (no edit body) is what must be matched.
    """
    pacemaker = _pacemaker()
    for path in ("cli.py", "worker.py", "reports.py"):
        _fail(pacemaker, _edit(path), EMPTY_EDIT_ERROR)

    # A 4th empty-body edit to yet another filename is doomed — refuse it.
    refusal = pacemaker.check_repeat_block(_edit("new_target.py"))

    assert refusal is not None
    assert "BLOCKED" in refusal


def test_defect_block_allows_call_with_real_body() -> None:
    """A properly-formed edit is the intended escape hatch — never blocked."""
    pacemaker = _pacemaker()
    for path in ("cli.py", "worker.py", "reports.py"):
        _fail(pacemaker, _edit(path), EMPTY_EDIT_ERROR)

    marker_edit = Action(
        name="edit_file",
        parameters={
            "path": "new_target.py",
            "content": "<<<<<<< SEARCH\nold\n=======\nnew\n>>>>>>> REPLACE",
        },
    )
    legacy_edit = Action(
        name="edit_file",
        parameters={"path": "new_target.py", "find": "old", "replace": "new"},
    )

    assert pacemaker.check_repeat_block(marker_edit) is None
    assert pacemaker.check_repeat_block(legacy_edit) is None


def test_defect_block_scoped_to_inspectable_defects() -> None:
    """Contract kinds without a call-visible defect stay verbatim-only.

    'outside workspace' can be fixed by changing the path param — a new
    call with a different path is legitimate and must not be refused.
    """
    pacemaker = _pacemaker()
    path_error = "Action 'read_file' failed: Reason: path outside workspace"
    for _ in range(REPEAT_BLOCK_THRESHOLD):
        _fail(
            pacemaker,
            Action(name="read_file", parameters={"path": "/etc/x"}),
            path_error,
        )

    # A read of a different path is not the same defect — allowed.
    new_call = Action(name="read_file", parameters={"path": "ok.py"})
    assert pacemaker.check_repeat_block(new_call) is None
