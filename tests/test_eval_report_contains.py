"""Tests for the report_contains check type in evals/runner.py.

This check closes the no-change-hard scoring hole: a run that left the
workspace untouched but never produced a report (e.g. asked a question
and the scripted run exited) must NOT pass. The check inspects the last
assistant prose message in the conversation history.
"""

from evals.runner import _last_report_text, _run_checks


def _history(*messages: tuple[str, str]) -> list[dict[str, str]]:
    """Build a minimal conversation history from (role, content) pairs."""
    return [{"role": role, "content": content} for role, content in messages]


def test_report_contains_passes_on_matching_report(tmp_path) -> None:
    """A real 'intentional rounding' report satisfies the check."""
    history = _history(
        ("user", "Investigate the discrepancy."),
        ("assistant", "::read_file @README.md"),
        (
            "assistant",
            "The 1-2 peso difference is intentional per-unit rounding "
            "documented in the README spec. No changes were made.",
        ),
    )
    results = _run_checks(
        [{"type": "report_contains", "texts": ["round", "丸め", "spec", "README"]}],
        tmp_path,
        history=history,
    )

    assert results[0]["passed"] is True


def test_report_contains_fails_when_run_ended_mid_question(tmp_path) -> None:
    """LFM's vacuous pass: asked a question, user exited → no report → fail."""
    history = _history(
        ("user", "Investigate the discrepancy."),
        ("assistant", "Could you tell me the correct path to orders.py?"),
        ("user", "exit"),
    )
    results = _run_checks(
        [{"type": "report_contains", "texts": ["round", "丸め", "spec", "README"]}],
        tmp_path,
        history=history,
    )

    assert results[0]["passed"] is False


def test_report_contains_fails_with_empty_history(tmp_path) -> None:
    """No history at all (crashed run) → fail, never a vacuous pass."""
    results = _run_checks(
        [{"type": "report_contains", "texts": ["round"]}],
        tmp_path,
        history=[],
    )

    assert results[0]["passed"] is False


def test_report_contains_fails_on_action_marker_only(tmp_path) -> None:
    """A bare '::response' marker without prose is not a report."""
    history = _history(
        ("user", "Investigate."),
        ("assistant", "::response"),
    )
    results = _run_checks(
        [{"type": "report_contains", "texts": ["round"]}],
        tmp_path,
        history=history,
    )

    assert results[0]["passed"] is False


def test_report_contains_single_text_key(tmp_path) -> None:
    """The shorthand `text:` key (single string) is also supported."""
    history = _history(("assistant", "Rounding is intentional."))
    results = _run_checks(
        [{"type": "report_contains", "text": "Rounding"}],
        tmp_path,
        history=history,
    )

    assert results[0]["passed"] is True


def test_last_report_text_picks_last_prose() -> None:
    """_last_report_text skips non-assistant and action-marker messages."""
    history = _history(
        ("assistant", "First report."),
        ("assistant", "::note @thinking"),
        ("assistant", "Final report here."),
        ("user", "exit"),
    )

    assert _last_report_text(history) == "Final report here."
