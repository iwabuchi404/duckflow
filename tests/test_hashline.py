"""
Hashline ファイル編集システムのテスト。

検証観点:
1. 同一内容の行（pass, 空行など）でもアンカーが区別できること
2. 編集後の行ズレでハッシュ不一致が検出されること
3. 連鎖編集（edit → 結果を見て再edit）がread_file不要で可能なこと
"""

import pytest
import tempfile
from pathlib import Path

from companion.tools.hashline import HashlineHelper
from companion.tools.file_ops import FileOps


class TestHashlineHelper:
    """HashlineHelper のユニットテスト。"""

    def test_generate_hash(self):
        """ハッシュ生成のテスト"""
        # 同じ内容の行は同じハッシュになる
        hash1 = HashlineHelper._compute_crc32_hash("def foo():")
        hash2 = HashlineHelper._compute_crc32_hash("def foo():")
        assert hash1 == hash2

        # 異なる内容の行は異なるハッシュになる
        hash3 = HashlineHelper._compute_crc32_hash("def bar():")
        assert hash1 != hash3

        # ハッシュは3文字の16進数
        assert len(hash1) == 3
        int(hash1, 16)  # 有効な16進数か

    def test_generate_hash_with_whitespace(self):
        """空白文字の扱いのテスト"""
        # leading/trailing whitespace を無視
        hash1 = HashlineHelper._compute_crc32_hash("    def foo():    ")
        hash2 = HashlineHelper._compute_crc32_hash("def foo():")
        assert hash1 == hash2

        # 中間の空白は保持
        hash3 = HashlineHelper._compute_crc32_hash("def foo(  ):")
        hash4 = HashlineHelper._compute_crc32_hash("def foo():")
        assert hash3 != hash4

    def test_format_with_hashlines(self):
        """hashline 形式への変換テスト（デフォルト: start_line=1）"""
        content = "def foo():\n    pass\ndef bar():"
        result = HashlineHelper.format_with_hashlines(content)

        lines = result.split('\n')
        assert len(lines) == 3

        # 1行目: "1:xxx|def foo():"
        assert lines[0].startswith("1:")
        assert "|def foo():" in lines[0]

        # 2行目: "2:xxx|    pass"
        assert lines[1].startswith("2:")
        assert "|    pass" in lines[1]

        # 3行目: "3:xxx|def bar():"
        assert lines[2].startswith("3:")
        assert "|def bar():" in lines[2]

    def test_format_with_hashlines_pagination(self):
        """ページネーション時に実際のファイル行番号が使われるテスト"""
        content = "def foo():\n    pass\ndef bar():"
        # start_line=301 でページネーション（ファイルの301行目以降を読んだ想定）
        result = HashlineHelper.format_with_hashlines(content, start_line=301)

        lines = result.split('\n')
        assert len(lines) == 3

        # 行番号が 301 から始まる
        assert lines[0].startswith("301:")
        assert "|def foo():" in lines[0]

        assert lines[1].startswith("302:")
        assert "|    pass" in lines[1]

        assert lines[2].startswith("303:")
        assert "|def bar():" in lines[2]

    def test_parse_anchor(self):
        """アンカー解析のテスト"""
        line_num, hash_val = HashlineHelper.parse_anchor("42:a3f")
        assert line_num == 42
        assert hash_val == "a3f"

        # 不正な形式
        with pytest.raises(ValueError):
            HashlineHelper.parse_anchor("invalid")

        with pytest.raises(ValueError):
            HashlineHelper.parse_anchor("42")

    def test_extract_content_block_success(self):
        """コンテンツ抽出成功のテスト"""
        file_lines = [
            "line 1",
            "line 2",
            "line 3",
            "line 4",
            "line 5",
        ]

        # アンカーを生成
        hash1 = HashlineHelper._compute_crc32_hash(file_lines[1])  # line 2
        hash3 = HashlineHelper._compute_crc32_hash(file_lines[3])  # line 4

        start_idx, end_idx, extracted = HashlineHelper.extract_content_block(
            file_lines, f"2:{hash1}", f"4:{hash3}"
        )

        assert start_idx == 1
        assert end_idx == 3
        assert len(extracted) == 3
        assert extracted == file_lines[1:4]

    def test_extract_content_block_hash_mismatch(self):
        """ハッシュ不一致のテスト"""
        file_lines = [
            "line 1",
            "line 2",
            "line 3",
        ]

        # ハッシュ不一致で例外が発生
        with pytest.raises(ValueError, match="Hash mismatch"):
            HashlineHelper.extract_content_block(
                file_lines, "2:fff", "3:fff"
            )

    def test_format_context_after_edit(self):
        """編集後コンテキストのテスト"""
        file_lines = [
            "line 1",
            "line 2",
            "line 3",
            "line 4",
            "line 5",
        ]

        context = HashlineHelper.format_context_after_edit(
            file_lines, edit_start_idx=1, edit_end_idx=3, context_lines=1
        )

        lines = context.split('\n')
        # 編集範囲(1-3)の前後1行を含む = 0:line0 から 4:line4 (5行)
        assert len(lines) == 5
        assert any("1:" in line and "line 1" in line for line in lines)
        assert any("4:" in line and "line 4" in line for line in lines)


class TestFileOpsWithHashline:
    """FileOps の hashline 対応の統合テスト。"""

    @pytest.fixture
    def file_ops(self):
        """一時ディレクトリを使用する FileOps インスタンス"""
        with tempfile.TemporaryDirectory() as tmpdir:
            ops = FileOps(workspace_root=tmpdir)
            yield ops

    def test_read_file_hashline_format(self, file_ops):
        """read_file が hashline 形式を返すテスト"""
        # テストファイル作成
        test_file = Path(file_ops.workspace_root) / "test.py"
        test_file.write_text("def foo():\n    pass\ndef bar():")

        # read_file 呼び出し
        import asyncio

        async def run_test():
            result = await file_ops.read_file("test.py")
            content = result["content"]

            # hashline 形式を確認
            lines = content.split('\n')
            assert len(lines) == 3
            assert lines[0].startswith("1:")
            assert lines[1].startswith("2:")
            assert lines[2].startswith("3:")

            # 行内容を確認
            assert "|def foo():" in lines[0]
            assert "|    pass" in lines[1]
            assert "|def bar():" in lines[2]

        asyncio.run(run_test())

    def test_edit_file_single_line(self, file_ops):
        """単一行編集のテスト"""
        # テストファイル作成
        test_file = Path(file_ops.workspace_root) / "test.py"
        test_file.write_text("def foo():\n    pass\ndef bar():")

        # 編集実行
        import asyncio

        async def run_test():
            # まず read_file でハッシュを取得
            read_result = await file_ops.read_file("test.py")
            read_lines = read_result["content"].split('\n')

            # 2行目のアンカーを取得 (line 2: "    pass")
            anchor_2 = read_lines[1].split('|')[0]  # "2:xxx"

            # edit_file 実行
            result = await file_ops.edit_file(
                "test.py",
                f"{anchor_2} {anchor_2}",  # 同じ行を編集
                "    # modified"
            )

            # 結果確認
            assert "Successfully edited test.py" in result
            assert "Updated Context" in result

            # ファイル内容確認
            content = test_file.read_text()
            assert "# modified" in content
            assert "pass" not in content

        asyncio.run(run_test())

    def test_edit_file_multiple_lines(self, file_ops):
        """複数行編集のテスト"""
        # テストファイル作成
        test_file = Path(file_ops.workspace_root) / "test.py"
        test_file.write_text("line 1\nline 2\nline 3\nline 4\nline 5")

        # 編集実行
        import asyncio

        async def run_test():
            # read_file でハッシュを取得
            read_result = await file_ops.read_file("test.py")
            read_lines = read_result["content"].split('\n')

            # 2-4行目のアンカーを取得
            anchor_2 = read_lines[1].split('|')[0]
            anchor_4 = read_lines[3].split('|')[0]

            # edit_file 実行
            result = await file_ops.edit_file(
                "test.py",
                f"{anchor_2} {anchor_4}",
                "modified line 1\nmodified line 2"
            )

            # ファイル内容確認
            content = test_file.read_text()
            assert content == "line 1\nmodified line 1\nmodified line 2\nline 5"

        asyncio.run(run_test())

    def test_edit_file_hash_mismatch(self, file_ops):
        """ハッシュ不一致でエラーになるテスト"""
        # テストファイル作成
        test_file = Path(file_ops.workspace_root) / "test.py"
        test_file.write_text("line 1\nline 2\nline 3")

        # 不正なハッシュで編集
        import asyncio

        async def run_test():
            # edit_file はハッシュ不一致を例外ではなく ::status error 文字列で返す
            result = await file_ops.edit_file(
                "test.py",
                "2:fff 3:fff",  # 不正なハッシュ
                "new content"
            )
            assert "::status error" in result
            assert "Hash mismatch" in result

        asyncio.run(run_test())

    def test_chained_edits(self, file_ops):
        """連鎖編集のテスト（read_file不要でeditを繰り返せる）"""
        # テストファイル作成
        test_file = Path(file_ops.workspace_root) / "test.py"
        test_file.write_text("def foo():\n    pass\n\ndef bar():\n    pass")

        import asyncio

        async def run_test():
            # 1回目の編集: read_file → edit
            read_result = await file_ops.read_file("test.py")
            read_lines = read_result["content"].split('\n')

            anchor_2 = read_lines[1].split('|')[0]  # "2:xxx"
            result1 = await file_ops.edit_file(
                "test.py",
                f"{anchor_2} {anchor_2}",
                "    # TODO: implement"
            )

            # 結果から新しいアンカーを取得（read_file不要）
            result_lines = result1.split('\n')
            # "Updated Context" セクションからアンカーを抽出
            context_start = result_lines.index("--- Updated Context (for reference in next edit) ---")
            # --- End of Context --- の直前まで
            try:
                context_end = result_lines.index("--- End of Context")
                context_lines = result_lines[context_start + 1:context_end]
            except ValueError:
                # End マーカーがない場合は最後まで
                context_lines = result_lines[context_start + 1:]

            # 2行目の新しいアンカーを取得
            new_anchor_2 = [line for line in context_lines if line.startswith("2:")][0].split('|')[0]

            # 2回目の編集: 新しいアンカーを使用
            result2 = await file_ops.edit_file(
                "test.py",
                f"{new_anchor_2} {new_anchor_2}",
                '    return "foo"'
            )

            # ファイル内容確認
            content = test_file.read_text()
            assert 'return "foo"' in content

        asyncio.run(run_test())


class TestDeleteLines:
    """FileOps.delete_lines のテスト。"""

    @pytest.fixture
    def file_ops(self):
        """一時ディレクトリを使用する FileOps インスタンス"""
        with tempfile.TemporaryDirectory() as tmpdir:
            ops = FileOps(workspace_root=tmpdir)
            yield ops

    def _make_content(self, anchors: str) -> str:
        """YAML フロントマター形式のコンテンツブロックを生成"""
        return f'---\nanchors: "{anchors}"\n---'

    def test_delete_single_line(self, file_ops):
        """単一行削除のテスト"""
        test_file = Path(file_ops.workspace_root) / "test.py"
        test_file.write_text("line 1\nline 2\nline 3\nline 4\nline 5")

        import asyncio

        async def run_test():
            # read_file でハッシュを取得
            read_result = await file_ops.read_file("test.py")
            read_lines = read_result["content"].split('\n')

            # 3行目のアンカーを取得
            anchor_3 = read_lines[2].split('|')[0]

            # 3行目を削除
            result = await file_ops.delete_lines(
                "test.py", self._make_content(f"{anchor_3} {anchor_3}")
            )

            assert "Successfully deleted 1 line(s)" in result
            assert "Updated Context" in result

            # ファイル内容確認
            content = test_file.read_text()
            assert content == "line 1\nline 2\nline 4\nline 5"

        asyncio.run(run_test())

    def test_delete_multiple_lines(self, file_ops):
        """複数行削除のテスト"""
        test_file = Path(file_ops.workspace_root) / "test.py"
        test_file.write_text("line 1\nline 2\nline 3\nline 4\nline 5")

        import asyncio

        async def run_test():
            read_result = await file_ops.read_file("test.py")
            read_lines = read_result["content"].split('\n')

            # 2-4行目のアンカーを取得
            anchor_2 = read_lines[1].split('|')[0]
            anchor_4 = read_lines[3].split('|')[0]

            result = await file_ops.delete_lines(
                "test.py", self._make_content(f"{anchor_2} {anchor_4}")
            )

            assert "Successfully deleted 3 line(s)" in result

            content = test_file.read_text()
            assert content == "line 1\nline 5"

        asyncio.run(run_test())

    def test_delete_lines_hash_mismatch(self, file_ops):
        """ハッシュ不一致でエラーになるテスト"""
        test_file = Path(file_ops.workspace_root) / "test.py"
        test_file.write_text("line 1\nline 2\nline 3")

        import asyncio

        async def run_test():
            result = await file_ops.delete_lines(
                "test.py", self._make_content("2:fff 3:fff")
            )
            assert "::status error" in result
            assert "Hash mismatch" in result

        asyncio.run(run_test())

    def test_delete_lines_invalid_anchors(self, file_ops):
        """フロントマターなしでエラーになるテスト"""
        test_file = Path(file_ops.workspace_root) / "test.py"
        test_file.write_text("line 1\nline 2")

        import asyncio

        async def run_test():
            # フロントマターなし
            result = await file_ops.delete_lines("test.py", "no frontmatter here")
            assert "::status error" in result
            assert "anchors" in result

        asyncio.run(run_test())

    def test_delete_lines_file_not_found(self, file_ops):
        """存在しないファイルでエラーになるテスト"""
        import asyncio

        async def run_test():
            result = await file_ops.delete_lines(
                "nonexistent.py", self._make_content("1:abc 2:def")
            )
            assert "::status error" in result
            assert "File not found" in result

        asyncio.run(run_test())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
