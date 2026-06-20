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
async def test_write_file_allows_nested_workspace_paths(file_ops: FileOps, tmp_path: Path) -> None:
    """A normal nested workspace path should still be writable."""
    result = await file_ops.write_file("src/app.py", "print('ok')\n")

    assert result == "Successfully wrote to src/app.py"
    assert (tmp_path / "src" / "app.py").read_text(encoding="utf-8") == "print('ok')"
