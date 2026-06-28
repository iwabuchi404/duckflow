"""
Hashline helper and current FileOps integration tests.

HashlineHelper still supports hash anchors as a low-level utility, but
FileOps.read_file now returns line-number-only context and edit_file uses
SEARCH/REPLACE or find/replace snippets. These tests reflect the current
behavior instead of the removed anchor-edit workflow.
"""

from pathlib import Path

import pytest

from companion.tools.file_ops import FileOps
from companion.tools.hashline import HashlineHelper
from companion.tools.results import ToolResult, ToolStatus


class TestHashlineHelper:
    """HashlineHelper unit tests."""

    def test_generate_hash(self) -> None:
        """
        Hash generation should be stable and return 3 hex characters.

        Args:
            None.

        Returns:
            None.
        """
        hash1 = HashlineHelper._compute_crc32_hash("def foo():")
        hash2 = HashlineHelper._compute_crc32_hash("def foo():")
        hash3 = HashlineHelper._compute_crc32_hash("def bar():")

        assert hash1 == hash2
        assert hash1 != hash3
        assert len(hash1) == 3
        int(hash1, 16)

    def test_generate_hash_with_whitespace(self) -> None:
        """
        Hash generation should ignore leading/trailing whitespace.

        Args:
            None.

        Returns:
            None.
        """
        hash1 = HashlineHelper._compute_crc32_hash("    def foo():    ")
        hash2 = HashlineHelper._compute_crc32_hash("def foo():")
        hash3 = HashlineHelper._compute_crc32_hash("def foo(  ):")

        assert hash1 == hash2
        assert hash3 != hash2

    def test_format_with_hashlines(self) -> None:
        """
        format_with_hashlines should include hashes by default.

        Args:
            None.

        Returns:
            None.
        """
        content = "def foo():\n    pass\ndef bar():"
        result = HashlineHelper.format_with_hashlines(content)

        lines = result.split("\n")
        assert len(lines) == 3
        assert lines[0].startswith("1:")
        assert "|def foo():" in lines[0]
        assert lines[1].startswith("2:")
        assert "|    pass" in lines[1]
        assert lines[2].startswith("3:")
        assert "|def bar():" in lines[2]

    def test_format_with_hashlines_pagination(self) -> None:
        """
        format_with_hashlines should preserve the provided starting line number.

        Args:
            None.

        Returns:
            None.
        """
        content = "def foo():\n    pass\ndef bar():"
        result = HashlineHelper.format_with_hashlines(content, start_line=301)

        lines = result.split("\n")
        assert lines[0].startswith("301:")
        assert lines[1].startswith("302:")
        assert lines[2].startswith("303:")

    def test_parse_anchor(self) -> None:
        """
        parse_anchor should validate line:hash anchor format.

        Args:
            None.

        Returns:
            None.
        """
        line_num, hash_val = HashlineHelper.parse_anchor("42:a3f")
        assert line_num == 42
        assert hash_val == "a3f"

        with pytest.raises(ValueError):
            HashlineHelper.parse_anchor("invalid")

        with pytest.raises(ValueError):
            HashlineHelper.parse_anchor("42")

    def test_extract_content_block_success(self) -> None:
        """
        extract_content_block should verify hashes and return the selected range.

        Args:
            None.

        Returns:
            None.
        """
        file_lines = ["line 1", "line 2", "line 3", "line 4", "line 5"]
        hash1 = HashlineHelper._compute_crc32_hash(file_lines[1])
        hash3 = HashlineHelper._compute_crc32_hash(file_lines[3])

        start_idx, end_idx, extracted = HashlineHelper.extract_content_block(
            file_lines, f"2:{hash1}", f"4:{hash3}"
        )

        assert start_idx == 1
        assert end_idx == 3
        assert extracted == file_lines[1:4]

    def test_extract_content_block_hash_mismatch(self) -> None:
        """
        extract_content_block should reject stale or incorrect hashes.

        Args:
            None.

        Returns:
            None.
        """
        file_lines = ["line 1", "line 2", "line 3"]

        with pytest.raises(ValueError, match="Hash mismatch"):
            HashlineHelper.extract_content_block(file_lines, "2:fff", "3:fff")

    def test_format_context_after_edit_uses_line_numbers_without_hashes_by_default(
        self,
    ) -> None:
        """
        format_context_after_edit should return readable line-number context by default.

        Args:
            None.

        Returns:
            None.
        """
        file_lines = ["line 1", "line 2", "line 3", "line 4", "line 5"]

        context = HashlineHelper.format_context_after_edit(
            file_lines, edit_start_idx=1, edit_end_idx=3, context_lines=1
        )

        lines = context.split("\n")
        assert len(lines) == 5
        assert lines[0] == "1|line 1"
        assert lines[3] == "4|line 4"


@pytest.fixture
def file_ops(tmp_path: Path) -> FileOps:
    """
    Create a FileOps instance rooted at a temporary workspace.

    Args:
        tmp_path: Temporary workspace path.

    Returns:
        FileOps instance using tmp_path as the workspace root.
    """
    return FileOps(workspace_root=str(tmp_path))


class TestFileOpsCurrentBehavior:
    """FileOps integration tests for the current edit/delete API."""

    @pytest.mark.asyncio
    async def test_read_file_returns_line_number_context(
        self, file_ops: FileOps, tmp_path: Path
    ) -> None:
        """
        read_file should return line-number-only context for readability.

        Args:
            file_ops: FileOps fixture.
            tmp_path: Temporary workspace path.

        Returns:
            None.
        """
        target = tmp_path / "test.py"
        target.write_text("def foo():\n    pass\ndef bar():", encoding="utf-8")

        result = await file_ops.read_file("test.py")
        lines = result["content"].split("\n")

        assert lines == ["1|def foo():", "2|    pass", "3|def bar():"]
        assert result["showing_lines"] == "1-3"
        assert result["has_more"] is False

    @pytest.mark.asyncio
    async def test_edit_file_single_line_marker_format(
        self, file_ops: FileOps, tmp_path: Path
    ) -> None:
        """
        edit_file should update a single line with SEARCH/REPLACE markers.

        Args:
            file_ops: FileOps fixture.
            tmp_path: Temporary workspace path.

        Returns:
            None.
        """
        target = tmp_path / "test.py"
        target.write_text("def foo():\n    pass\ndef bar():", encoding="utf-8")

        content = (
            "<<<<<<< SEARCH\n"
            "    pass\n"
            "=======\n"
            "    # modified\n"
            ">>>>>>> REPLACE\n"
        )
        result = await file_ops.edit_file("test.py", content=content)

        assert result.startswith("Successfully edited test.py")
        assert "--- Updated Context ---" in result
        assert (
            target.read_text(encoding="utf-8")
            == "def foo():\n    # modified\ndef bar():"
        )

    @pytest.mark.asyncio
    async def test_edit_file_multiple_lines_marker_format(
        self, file_ops: FileOps, tmp_path: Path
    ) -> None:
        """
        edit_file should replace a multi-line SEARCH block.

        Args:
            file_ops: FileOps fixture.
            tmp_path: Temporary workspace path.

        Returns:
            None.
        """
        target = tmp_path / "test.py"
        target.write_text("line 1\nline 2\nline 3\nline 4\nline 5", encoding="utf-8")

        content = (
            "<<<<<<< SEARCH\n"
            "line 2\n"
            "line 3\n"
            "line 4\n"
            "=======\n"
            "modified line 1\n"
            "modified line 2\n"
            ">>>>>>> REPLACE\n"
        )
        result = await file_ops.edit_file("test.py", content=content)

        assert result.startswith("Successfully edited test.py")
        assert target.read_text(encoding="utf-8") == (
            "line 1\nmodified line 1\nmodified line 2\nline 5"
        )

    @pytest.mark.asyncio
    async def test_edit_file_stale_or_incorrect_search_reports_find_not_matched(
        self, file_ops: FileOps, tmp_path: Path
    ) -> None:
        """
        edit_file should report find_not_matched when the SEARCH text is stale.

        Args:
            file_ops: FileOps fixture.
            tmp_path: Temporary workspace path.

        Returns:
            None.
        """
        target = tmp_path / "test.py"
        target.write_text("line 1\nline 2\nline 3", encoding="utf-8")

        content = (
            "<<<<<<< SEARCH\n"
            "line 2 changed elsewhere\n"
            "=======\n"
            "new content\n"
            ">>>>>>> REPLACE\n"
        )
        result = await file_ops.edit_file("test.py", content=content)

        assert isinstance(result, ToolResult)
        assert result.status == ToolStatus.ERROR
        assert "find_not_matched" in result.content
        assert target.read_text(encoding="utf-8") == "line 1\nline 2\nline 3"

    @pytest.mark.asyncio
    async def test_chained_edits_use_updated_context_without_hash_anchors(
        self, file_ops: FileOps, tmp_path: Path
    ) -> None:
        """
        edit_file should return updated context usable for the next exact SEARCH.

        Args:
            file_ops: FileOps fixture.
            tmp_path: Temporary workspace path.

        Returns:
            None.
        """
        target = tmp_path / "test.py"
        target.write_text(
            "def foo():\n    pass\n\ndef bar():\n    pass", encoding="utf-8"
        )

        result1 = await file_ops.edit_file(
            "test.py",
            content=(
                "<<<<<<< SEARCH\n"
                "    pass\n"
                "=======\n"
                "    # TODO: implement\n"
                ">>>>>>> REPLACE\n"
            ),
        )

        assert "--- Updated Context ---" in result1
        assert "2|    # TODO: implement" in result1

        result2 = await file_ops.edit_file(
            "test.py",
            content=(
                "<<<<<<< SEARCH\n"
                "    # TODO: implement\n"
                "=======\n"
                '    return "foo"\n'
                ">>>>>>> REPLACE\n"
            ),
        )

        assert result2.startswith("Successfully edited test.py")
        assert 'return "foo"' in target.read_text(encoding="utf-8")


class TestDeleteLinesCurrentBehavior:
    """FileOps.delete_lines tests for the current find snippet API."""

    @pytest.mark.asyncio
    async def test_delete_single_line(self, file_ops: FileOps, tmp_path: Path) -> None:
        """
        delete_lines should remove a single matching line.

        Args:
            file_ops: FileOps fixture.
            tmp_path: Temporary workspace path.

        Returns:
            None.
        """
        target = tmp_path / "test.py"
        target.write_text("line 1\nline 2\nline 3\nline 4\nline 5", encoding="utf-8")

        result = await file_ops.delete_lines("test.py", find="line 3")

        assert "Successfully deleted 1 line(s)" in result
        assert "--- Updated Context ---" in result
        assert target.read_text(encoding="utf-8") == "line 1\nline 2\nline 4\nline 5"

    @pytest.mark.asyncio
    async def test_delete_multiple_lines(
        self, file_ops: FileOps, tmp_path: Path
    ) -> None:
        """
        delete_lines should remove a multi-line matching snippet.

        Args:
            file_ops: FileOps fixture.
            tmp_path: Temporary workspace path.

        Returns:
            None.
        """
        target = tmp_path / "test.py"
        target.write_text("line 1\nline 2\nline 3\nline 4\nline 5", encoding="utf-8")

        result = await file_ops.delete_lines(
            "test.py",
            content="find: |\n  line 2\n  line 3\n  line 4\n",
        )

        assert "Successfully deleted 3 line(s)" in result
        assert target.read_text(encoding="utf-8") == "line 1\nline 5"

    @pytest.mark.asyncio
    async def test_delete_lines_accepts_search_replace_marker_format(
        self, file_ops: FileOps, tmp_path: Path
    ) -> None:
        """
        delete_lines should accept the same marker style as edit_file when
        the REPLACE section is empty.

        Args:
            file_ops: FileOps fixture.
            tmp_path: Temporary workspace path.

        Returns:
            None.
        """
        target = tmp_path / "test.py"
        target.write_text("keep 1\ndelete 1\ndelete 2\nkeep 2", encoding="utf-8")

        result = await file_ops.delete_lines(
            "test.py",
            content=(
                "<<<<<<< SEARCH\n"
                "delete 1\n"
                "delete 2\n"
                "=======\n"
                ">>>>>>> REPLACE"
            ),
        )

        assert "Successfully deleted 2 line(s)" in result
        assert target.read_text(encoding="utf-8") == "keep 1\nkeep 2"

    @pytest.mark.asyncio
    async def test_delete_lines_rejects_non_empty_replace_marker(
        self, file_ops: FileOps, tmp_path: Path
    ) -> None:
        """
        delete_lines should reject SEARCH/REPLACE markers that attempt a
        replacement rather than a deletion.

        Args:
            file_ops: FileOps fixture.
            tmp_path: Temporary workspace path.

        Returns:
            None.
        """
        target = tmp_path / "test.py"
        target.write_text("keep 1\ndelete me\nkeep 2", encoding="utf-8")

        result = await file_ops.delete_lines(
            "test.py",
            content=(
                "<<<<<<< SEARCH\n"
                "delete me\n"
                "=======\n"
                "replace me\n"
                ">>>>>>> REPLACE"
            ),
        )

        assert isinstance(result, ToolResult)
        assert result.status == ToolStatus.ERROR
        assert "delete_lines_replace_not_empty" in result.content
        assert target.read_text(encoding="utf-8") == "keep 1\ndelete me\nkeep 2"

    @pytest.mark.asyncio
    async def test_delete_lines_stale_or_incorrect_find_reports_error(
        self, file_ops: FileOps, tmp_path: Path
    ) -> None:
        """
        delete_lines should report find_not_matched for stale snippets.

        Args:
            file_ops: FileOps fixture.
            tmp_path: Temporary workspace path.

        Returns:
            None.
        """
        target = tmp_path / "test.py"
        target.write_text("line 1\nline 2\nline 3", encoding="utf-8")

        result = await file_ops.delete_lines("test.py", find="line 2 changed")

        assert isinstance(result, ToolResult)
        assert result.status == ToolStatus.ERROR
        assert "find_not_matched" in result.content

    @pytest.mark.asyncio
    async def test_delete_lines_missing_find_reports_error(
        self, file_ops: FileOps, tmp_path: Path
    ) -> None:
        """
        delete_lines should require a find snippet.

        Args:
            file_ops: FileOps fixture.
            tmp_path: Temporary workspace path.

        Returns:
            None.
        """
        target = tmp_path / "test.py"
        target.write_text("line 1\nline 2", encoding="utf-8")

        result = await file_ops.delete_lines("test.py", content="no frontmatter here")

        assert isinstance(result, ToolResult)
        assert result.status == ToolStatus.ERROR
        assert "No 'find' snippet" in result.content

    @pytest.mark.asyncio
    async def test_delete_lines_file_not_found(self, file_ops: FileOps) -> None:
        """
        delete_lines should report missing files.

        Args:
            file_ops: FileOps fixture.

        Returns:
            None.
        """
        result = await file_ops.delete_lines("nonexistent.py", find="line")

        assert isinstance(result, ToolResult)
        assert result.status == ToolStatus.ERROR
        assert "File not found" in result.content
