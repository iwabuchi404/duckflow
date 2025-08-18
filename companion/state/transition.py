"""
Transition control utilities for Phase 1

Implements:
- TransitionController: allowed transitions between Steps
- TransitionLimiter: max transitions per utterance (time-windowed)
"""
from datetime import datetime
from dataclasses import dataclass
from typing import Optional
from .agent_state import Step


class TransitionController:
    """Controls allowed transitions between Steps."""

    def __init__(self):
        self.allowed_transitions = {
            Step.PLANNING: [Step.EXECUTION, Step.REVIEW, Step.AWAITING_APPROVAL],
            Step.EXECUTION: [Step.REVIEW, Step.AWAITING_APPROVAL],
            Step.REVIEW: [Step.EXECUTION, Step.AWAITING_APPROVAL, "DONE"],
            Step.AWAITING_APPROVAL: [Step.EXECUTION, Step.PLANNING],
        }
        self.error_transitions = {
            Step.EXECUTION: Step.PLANNING,
            Step.REVIEW: Step.PLANNING,
        }

    def is_transition_allowed(self, from_step: Step, to_step) -> bool:
        if from_step not in self.allowed_transitions:
            return False
        return to_step in self.allowed_transitions[from_step]

    def get_error_recovery_step(self, current_step: Step) -> Step:
        return self.error_transitions.get(current_step, Step.PLANNING)


@dataclass
class TransitionLimiter:
    """Limits number of transitions per utterance within a time window."""

    max_transitions_per_utterance: int = 1
    reset_interval_seconds: int = 60
    last_transition_time: Optional[datetime] = None
    transition_count: int = 0

    def can_transition(self) -> bool:
        now = datetime.now()
        if self.last_transition_time is not None:
            if (now - self.last_transition_time).total_seconds() > self.reset_interval_seconds:
                self.transition_count = 0
        return self.transition_count < self.max_transitions_per_utterance

    def record_transition(self) -> None:
        self.transition_count += 1
        self.last_transition_time = datetime.now()

    def reset(self) -> None:
        """発話の先頭でカウンタをリセット"""
        self.transition_count = 0
        self.last_transition_time = None


