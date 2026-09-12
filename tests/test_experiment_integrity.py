"""Tests for experiment-integrity fixes."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from companion.prompts.few_shot import get_effective_framing  # noqa: E402
from evals.runner import _load_yaml_no_duplicates  # noqa: E402


def test_duplicate_keys_rejected(tmp_path: Path) -> None:
    """Scenario files with duplicate keys fail fast."""
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "id: x\nverify_command: \"a\"\nverify_command: \"a\"\n", encoding="utf-8"
    )

    with pytest.raises(ValueError, match="Duplicate key"):
        _load_yaml_no_duplicates(bad)


def test_unique_keys_load(tmp_path: Path) -> None:
    """Normal files load unchanged."""
    good = tmp_path / "good.yaml"
    good.write_text("id: x\ntask: y\n", encoding="utf-8")

    assert _load_yaml_no_duplicates(good)["id"] == "x"


def test_effective_framing_defaults_to_framed(monkeypatch) -> None:
    """Builder and records share the framed default."""
    monkeypatch.delenv("DUCKFLOW_FEW_SHOT_FRAMING", raising=False)

    assert get_effective_framing() == "framed"


def test_effective_framing_respects_env(monkeypatch) -> None:
    """Explicit env values pass through; garbage falls back."""
    monkeypatch.setenv("DUCKFLOW_FEW_SHOT_FRAMING", "bare")
    assert get_effective_framing() == "bare"

    monkeypatch.setenv("DUCKFLOW_FEW_SHOT_FRAMING", "nonsense")
    assert get_effective_framing() == "framed"
