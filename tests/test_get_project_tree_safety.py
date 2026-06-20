import os
import sys
from pathlib import Path

import pytest

sys.path.append(os.getcwd())

from companion.tools.get_project_tree import get_project_tree


@pytest.mark.asyncio
async def test_get_project_tree_lists_workspace_files(tmp_path: Path) -> None:
    """
    get_project_tree should list normal files under the workspace root.

    Args:
        tmp_path: Temporary workspace path.

    Returns:
        None.
    """
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Test\n", encoding="utf-8")

    result = await get_project_tree(workspace_root=str(tmp_path), depth=2, respect_gitignore=False)

    assert "src/" in result
    assert "main.py" in result
    assert "README.md" in result


@pytest.mark.asyncio
async def test_get_project_tree_rejects_parent_escape(tmp_path: Path) -> None:
    """
    get_project_tree should reject relative paths escaping the workspace.

    Args:
        tmp_path: Temporary workspace path.

    Returns:
        None.
    """
    result = await get_project_tree(path="..", workspace_root=str(tmp_path), respect_gitignore=False)

    assert result.startswith("Error:")
    assert "Outside workspace" in result


@pytest.mark.asyncio
async def test_get_project_tree_rejects_absolute_escape(tmp_path: Path) -> None:
    """
    get_project_tree should reject absolute paths outside the workspace.

    Args:
        tmp_path: Temporary workspace path.

    Returns:
        None.
    """
    outside = tmp_path.parent

    result = await get_project_tree(path=str(outside), workspace_root=str(tmp_path), respect_gitignore=False)

    assert result.startswith("Error:")
    assert "Outside workspace" in result


@pytest.mark.asyncio
async def test_get_project_tree_skips_symlink_to_outside(tmp_path: Path) -> None:
    """
    get_project_tree should not follow symlinks that resolve outside the workspace.

    Args:
        tmp_path: Temporary workspace path.

    Returns:
        None.
    """
    outside = tmp_path.parent / "outside_target"
    outside.mkdir(exist_ok=True)
    (outside / "secret.txt").write_text("secret\n", encoding="utf-8")
    link = tmp_path / "outside_link"

    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Directory symlinks are not available in this environment")

    (tmp_path / "visible.txt").write_text("visible\n", encoding="utf-8")

    result = await get_project_tree(workspace_root=str(tmp_path), depth=2, respect_gitignore=False)

    assert "visible.txt" in result
    assert "outside_link" not in result
    assert "secret.txt" not in result


@pytest.mark.asyncio
async def test_get_project_tree_excludes_noise_directories(tmp_path: Path) -> None:
    """
    get_project_tree should exclude cache, dependency, and build artifact directories.

    Args:
        tmp_path: Temporary workspace path.

    Returns:
        None.
    """
    for dirname in ("__pycache__", "node_modules", "dist", "build", "sample.egg-info"):
        directory = tmp_path / dirname
        directory.mkdir()
        (directory / "noise.py").write_text("noise\n", encoding="utf-8")

    (tmp_path / "app.py").write_text("print('ok')\n", encoding="utf-8")

    result = await get_project_tree(workspace_root=str(tmp_path), depth=2, respect_gitignore=False)

    assert "app.py" in result
    assert "__pycache__" not in result
    assert "node_modules" not in result
    assert "sample.egg-info" not in result
    assert "noise.py" not in result


@pytest.mark.asyncio
async def test_get_project_tree_respects_false_string_for_gitignore(tmp_path: Path) -> None:
    """
    respect_gitignore='false' should be parsed as False, not truthy.

    Args:
        tmp_path: Temporary workspace path.

    Returns:
        None.
    """
    (tmp_path / "file.txt").write_text("content\n", encoding="utf-8")

    result = await get_project_tree(
        workspace_root=str(tmp_path),
        respect_gitignore="false",
    )

    assert "file.txt" in result
