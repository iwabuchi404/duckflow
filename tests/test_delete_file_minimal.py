from pathlib import Path

import pytest

from companion.tools.file_ops import FileOps


@pytest.fixture
def file_ops(tmp_path: Path) -> FileOps:
    """Return FileOps rooted at tmp_path."""
    return FileOps(str(tmp_path))


@pytest.mark.asyncio
async def test_delete_file_removes_existing_file(file_ops: FileOps, tmp_path: Path) -> None:
    """delete_file should remove a normal file."""
    target = tmp_path / "delete-me.txt"
    target.write_text("bye", encoding="utf-8")

    result = await file_ops.delete_file("delete-me.txt")

    assert result == "Deleted file: delete-me.txt"
    assert not target.exists()


@pytest.mark.asyncio
async def test_delete_file_reports_missing_file(file_ops: FileOps) -> None:
    """delete_file should raise FileNotFoundError for missing files."""
    with pytest.raises(FileNotFoundError):
        await file_ops.delete_file("missing.txt")


@pytest.mark.asyncio
async def test_delete_file_rejects_directories(file_ops: FileOps, tmp_path: Path) -> None:
    """delete_file should not remove directories."""
    (tmp_path / "directory").mkdir()

    with pytest.raises(IsADirectoryError):
        await file_ops.delete_file("directory")
