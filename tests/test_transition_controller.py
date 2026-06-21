"""
Tests for companion/state/transition.py (TransitionLimiter)
and companion/state/enums.py (Step, Status)

Note: TransitionController from transition.py cannot be instantiated because
it references Step.PLANNING etc., but agent_state.Step is a Pydantic BaseModel
(not an Enum). The Step Enum lives in enums.py. transition_controller.py has a
broken import (Status not in agent_state). We test what is functional.
"""

from datetime import datetime, timedelta

from companion.state.enums import Status, Step
from companion.state.transition import TransitionLimiter

# ============================================================
# Enum tests (companion/state/enums.py)
# ============================================================


class TestStepEnum:
    def test_all_expected_values_exist(self) -> None:
        expected = {
            "IDLE",
            "THINKING",
            "PLANNING",
            "EXECUTION",
            "REVIEW",
            "AWAITING_APPROVAL",
            "AWAITING_USER_INPUT",
            "COMPLETED",
            "ERROR",
        }
        actual = {s.value for s in Step}
        assert expected == actual

    def test_step_value_roundtrip(self) -> None:
        assert Step("PLANNING") == Step.PLANNING


class TestStatusEnum:
    def test_all_expected_values_exist(self) -> None:
        expected = {
            "PENDING",
            "IN_PROGRESS",
            "SUCCESS",
            "ERROR",
            "CANCELLED",
            "REQUIRES_USER_INPUT",
        }
        actual = {s.value for s in Status}
        assert expected == actual

    def test_status_value_roundtrip(self) -> None:
        assert Status("SUCCESS") == Status.SUCCESS


# ============================================================
# TransitionLimiter (companion/state/transition.py)
# ============================================================


class TestTransitionLimiter:
    def test_first_transition_allowed(self) -> None:
        lim = TransitionLimiter()
        assert lim.can_transition()

    def test_second_transition_blocked(self) -> None:
        lim = TransitionLimiter()
        lim.record_transition()
        assert not lim.can_transition()

    def test_reset_allows_again(self) -> None:
        lim = TransitionLimiter()
        lim.record_transition()
        lim.reset()
        assert lim.can_transition()
        assert lim.transition_count == 0
        assert lim.last_transition_time is None

    def test_time_window_reset(self) -> None:
        lim = TransitionLimiter(reset_interval_seconds=0)
        lim.record_transition()
        lim.last_transition_time = datetime.now() - timedelta(seconds=1)
        assert lim.can_transition()

    def test_custom_max_transitions(self) -> None:
        lim = TransitionLimiter(max_transitions_per_utterance=3)
        lim.record_transition()
        lim.record_transition()
        assert lim.can_transition()
        lim.record_transition()
        assert not lim.can_transition()

    def test_record_sets_timestamp(self) -> None:
        lim = TransitionLimiter()
        assert lim.last_transition_time is None
        lim.record_transition()
        assert lim.last_transition_time is not None
        assert lim.transition_count == 1
