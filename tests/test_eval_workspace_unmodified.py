"""Tests for the workspace_unmodified check type in evals/runner.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals.runner import _run_checks  # noqa: E402


def _make_fixture_and_workspace(tmp_path: Path) -> tuple[Path, Path]:
    """Create an identical fixture and workspace pair.

    Args:
        tmp_path: pytest tmp dir.

    Returns:
        (fixture, workspace) paths with identical contents.
    """
    fixture = tmp_path / "fixture"
    workspace = tmp_path / "ws"
    for root in (fixture, workspace):
        (root / "sub").mkdir(parents=True)
        (root / "a.py").write_text("print('a')\n", encoding="utf-8")
        (root / "sub" / "b.py").write_text("print('b')\n", encoding="utf-8")
    return fixture, workspace


def _check() -> dict:
    """Return the workspace_unmodified check dict."""
    return {"type": "workspace_unmodified"}


def test_workspace_unmodified_passes_on_identical_trees(tmp_path: Path) -> None:
    """Identical trees pass the check."""
    fixture, workspace = _make_fixture_and_workspace(tmp_path)
    results = _run_checks([_check()], workspace, fixture=fixture)
    assert results[0]["passed"] is True


def test_workspace_unmodified_fails_on_edit(tmp_path: Path) -> None:
    """A modified file fails the check."""
    fixture, workspace = _make_fixture_and_workspace(tmp_path)
    (workspace / "a.py").write_text("print('edited')\n", encoding="utf-8")
    results = _run_checks([_check()], workspace, fixture=fixture)
    assert results[0]["passed"] is False


def test_workspace_unmodified_fails_on_new_file(tmp_path: Path) -> None:
    """A newly created file fails the check."""
    fixture, workspace = _make_fixture_and_workspace(tmp_path)
    (workspace / "new.py").write_text("print('new')\n", encoding="utf-8")
    results = _run_checks([_check()], workspace, fixture=fixture)
    assert results[0]["passed"] is False


def test_workspace_unmodified_fails_on_deleted_file(tmp_path: Path) -> None:
    """A deleted file fails the check."""
    fixture, workspace = _make_fixture_and_workspace(tmp_path)
    (workspace / "a.py").unlink()
    results = _run_checks([_check()], workspace, fixture=fixture)
    assert results[0]["passed"] is False


def test_workspace_unmodified_ignores_generated_noise(tmp_path: Path) -> None:
    """__pycache__/.pytest_cache/*.pyc in the workspace are ignored."""
    fixture, workspace = _make_fixture_and_workspace(tmp_path)
    (workspace / "__pycache__").mkdir()
    (workspace / "__pycache__" / "a.cpython-312.pyc").write_bytes(b"pk")
    (workspace / ".pytest_cache").mkdir()
    (workspace / ".pytest_cache" / "v").write_text("cache", encoding="utf-8")
    (workspace / "a.pyc").write_bytes(b"pk")
    results = _run_checks([_check()], workspace, fixture=fixture)
    assert results[0]["passed"] is True


def test_workspace_unmodified_fails_without_fixture(tmp_path: Path) -> None:
    """No fixture → cannot verify unmodified → fail safe."""
    _, workspace = _make_fixture_and_workspace(tmp_path)
    results = _run_checks([_check()], workspace, fixture=None)
    assert results[0]["passed"] is False
