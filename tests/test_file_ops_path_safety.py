from pathlib import Path

import pytest

from companion.tools.file_ops import FileOps


@pytest.fixture
def file_ops(tmp_path: Path) -> FileOps:
    """Return FileOps rooted at tmp_path."""
    return FileOps(str(tmp_path))


@pytest.mark.asyncio
async def test_read_file_rejects_parent_escape(file_ops: FileOps) -> None:
    """read_file should not allow paths outside the workspace."""
    with pytest.raises(PermissionError):
        await file_ops.read_file("../outside.txt")


@pytest.mark.asyncio
async def test_write_file_rejects_parent_escape(file_ops: FileOps) -> None:
    """write_file should not write outside the workspace."""
    with pytest.raises(PermissionError):
        await file_ops.write_file("../outside.txt", "nope")


@pytest.mark.asyncio
async def test_edit_file_rejects_parent_escape(file_ops: FileOps) -> None:
    """edit_file should not edit outside the workspace."""
    with pytest.raises(PermissionError):
        await file_ops.edit_file("../outside.txt", find="a", replace="b")


@pytest.mark.asyncio
async def test_delete_file_rejects_parent_escape(file_ops: FileOps) -> None:
    """delete_file should not delete outside the workspace."""
    with pytest.raises(PermissionError):
        await file_ops.delete_file("../outside.txt")


@pytest.mark.asyncio
async def test_write_file_allows_nested_workspace_paths(
    file_ops: FileOps, tmp_path: Path
) -> None:
    """A normal nested workspace path should still be writable."""
    result = await file_ops.write_file("src/app.py", "print('ok')\n")

    assert result == "Successfully wrote 11 bytes to src/app.py"
    assert (tmp_path / "src" / "app.py").read_text(encoding="utf-8") == "print('ok')"


@pytest.mark.asyncio
async def test_virtual_workspace_prefix_normalizes_to_relative(
    file_ops: FileOps, tmp_path: Path
) -> None:
    """'/workspace/x.py' (a common model hallucination) maps to 'x.py'.

    Reproduces the LFM ambiguous-gauntlet failure where
    '::write_file @/workspace/restock.json' was denied and the model
    wandered into filesystem-root searches instead of recovering.
    """
    result = await file_ops.write_file("/workspace/restock.json", "{}")

    assert "Successfully wrote" in result
    assert (tmp_path / "restock.json").read_text(encoding="utf-8") == "{}"


@pytest.mark.asyncio
async def test_absolute_path_inside_workspace_normalizes(
    file_ops: FileOps, tmp_path: Path
) -> None:
    """An absolute path that is genuinely inside the workspace → relative."""
    target = tmp_path / "orders.py"
    result = await file_ops.write_file(str(target), "x = 1")

    assert "Successfully wrote" in result
    assert target.read_text(encoding="utf-8") == "x = 1"


def test_posix_path_containing_workspace_name_normalizes(
    file_ops: FileOps, tmp_path: Path
) -> None:
    """POSIX-style path echoing pwd output → tail after the ws dir name.

    LFM ran `pwd`, got '/tmp/duckflow-evals/<run>/<ws_name>/', then wrote to
    that literal path — on Windows it resolves outside the workspace. The
    workspace dir name inside the path identifies the intended tail.
    """
    ws_name = tmp_path.name
    echo = f"/tmp/duckflow-evals/no-change-hard/{ws_name}/orders.py"

    assert file_ops._normalize_model_path(echo) == "orders.py"


@pytest.mark.asyncio
async def test_outside_workspace_error_is_actionable(file_ops: FileOps) -> None:
    """Denied paths must explain the relative-path contract, not just 'no'."""
    with pytest.raises(PermissionError) as exc_info:
        await file_ops.read_file("/etc/passwd")

    message = str(exc_info.value)
    assert "Outside workspace" in message
    assert "RELATIVE" in message
    assert "orders.py" in message  # concrete example of a valid path


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["../outside.txt", "..\\..\\outside.txt"])
async def test_traversal_still_rejected_after_normalization(
    file_ops: FileOps, path: str
) -> None:
    """Normalization must never widen access: traversal stays denied."""
    with pytest.raises(PermissionError):
        await file_ops.read_file(path)
