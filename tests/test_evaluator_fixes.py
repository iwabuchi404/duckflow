"""Tests for evaluator fixes: ordering, repetition semantics, experiment meta."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals.analysis import tag_repeated_command, tag_verified_edit_success  # noqa: E402
from evals.runner import _collect_experiment_meta  # noqa: E402


def _history(*assistant_contents: str) -> list[dict]:
    """Build a conversation history from assistant action summaries."""
    return [{"role": "assistant", "content": c} for c in assistant_contents]


def test_repeated_command_ignores_rerun_after_edit() -> None:
    """A re-run separated by an edit is a verify loop, not degeneration."""
    history = _history(
        ":: run_command @pytest test_calc.py -v",
        ":: edit_file @calc.py",
        ":: run_command @pytest test_calc.py -v",
    )

    assert tag_repeated_command(history) is False


def test_repeated_command_flags_back_to_back_repeat() -> None:
    """The same command twice with nothing between is flagged."""
    history = _history(
        ":: run_command @pytest calc.py -v",
        ":: run_command @pytest calc.py -v",
    )

    assert tag_repeated_command(history) is True


def test_repeated_command_flags_repeat_after_read_only() -> None:
    """A repeat separated only by reads (no edit) is still flagged."""
    history = _history(
        ":: run_command @pytest calc.py -v",
        ":: read_file @calc.py",
        ":: run_command @pytest calc.py -v",
    )

    assert tag_repeated_command(history) is True


def test_verified_success_multi_action_ordering() -> None:
    """With batched actions, success after the edit turn still counts."""
    history = _history(
        ":: read_file @calc.py\n:: run_command @pytest",
        ":: edit_file @calc.py\n:: run_command @pytest test_calc.py -v",
    ) + [
        {
            "role": "user",
            "content": "[TOOL_RESULT]\n::run_command @pytest test_calc.py\n"
            "<<<\n2 passed\nexit_code: 0\n>>>\n[/TOOL_RESULT]",
        }
    ]

    assert tag_verified_edit_success(history) is True


def test_experiment_meta_records_conditions() -> None:
    """Experiment metadata captures commit, framing and scenario hash."""
    scenario = {"id": "demo", "task": "do it", "_path": "somewhere"}

    meta = _collect_experiment_meta(scenario)

    assert meta["scenario_id"] == "demo"
    assert len(meta["scenario_sha"]) == 12
    assert meta["few_shot_framing"] in ("bare", "framed", "minimal")
    assert "git_commit" in meta
    assert "llm_settings" in meta
