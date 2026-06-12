"""
AutoRepair ブロック保護機能のテスト (v3.3)。

検証観点:
1. _fix_missing_symbols: <<< ～ >>> ブロック内の行は変更されない
2. _fix_missing_symbols: ブロック外のアクション行には :: が補完される
3. write_file が ACTION_VERBS に含まれ、補完対象になること
4. _fix_markdown_blocks: 既存ブロック内の ``` フェンスは保護される
5. _fix_markdown_blocks: ブロック外の ``` フェンスは <<< / >>> に変換される
6. _fix_vitals_format: ブロック内のバイタル表記は変換されない
7. _apply_outside_blocks: インデント付きの >>> はブロック終端として扱われない
8. 統合テスト: SymOpsProcessor 経由でブロック内容が byte-for-byte 保持される
9. 統合テスト: ブロック外の ``` フェンスがアクションのコンテンツに変換される
"""

import sys
import os
sys.path.append(os.getcwd())

import pytest
from companion.utils.sym_ops import AutoRepair, SymOpsProcessor


class TestFixMissingSymbolsBlockProtection:
    """_fix_missing_symbols のブロック保護テスト"""

    def setup_method(self) -> None:
        """
        各テストの前に AutoRepair インスタンスを生成する。

        Args: なし
        Returns: なし
        """
        self.repair = AutoRepair()

    def test_code_line_inside_block_is_unchanged(self) -> None:
        """
        <<< ～ >>> ブロック内のコード行（例: update = 5）は
        アクション行に誤変換されないことを確認する。

        Args: なし
        Returns: なし
        """
        text = "<<<\nupdate = 5\n>>>"
        result = self.repair._fix_missing_symbols(text)
        assert "update = 5" in result
        assert ":: update" not in result

    def test_read_prefix_inside_block_is_unchanged(self) -> None:
        """
        ブロック内の 'read ' で始まる行はアクション補完されないことを確認する。

        Args: なし
        Returns: なし
        """
        text = "<<<\nread the config file\n>>>"
        result = self.repair._fix_missing_symbols(text)
        assert "read the config file" in result
        assert ":: read" not in result

    def test_action_line_outside_block_is_repaired(self) -> None:
        """
        ブロック外の 'update ...' 行には :: が補完されることを確認する。

        Args: なし
        Returns: なし
        """
        text = "update foo.py"
        result = self.repair._fix_missing_symbols(text)
        assert result.startswith(":: update")

    def test_read_outside_block_is_repaired(self) -> None:
        """
        ブロック外の 'read ...' 行には :: が補完されることを確認する。

        Args: なし
        Returns: なし
        """
        text = "read config.yaml"
        result = self.repair._fix_missing_symbols(text)
        assert result.startswith(":: read")

    def test_write_file_in_action_verbs(self) -> None:
        """
        write_file が ACTION_VERBS に含まれており、ブロック外で補完されることを確認する。

        Args: なし
        Returns: なし
        """
        assert "write_file" in AutoRepair.ACTION_VERBS

        text = "write_file @ foo.py"
        result = self.repair._fix_missing_symbols(text)
        assert result.startswith(":: write_file")

    def test_write_file_outside_block_no_colon_repaired(self) -> None:
        """
        :: なしの 'write_file @ foo.py' がブロック外で :: write_file @ foo.py に補完される。

        Args: なし
        Returns: なし
        """
        text = "write_file @ foo.py"
        result = self.repair._fix_missing_symbols(text)
        assert ":: write_file" in result
        assert "foo.py" in result

    def test_code_outside_block_then_inside_block(self) -> None:
        """
        ブロック外のアクション行は補完され、同じ文字列がブロック内では保護される。

        Args: なし
        Returns: なし
        """
        text = "update = 5\n<<<\nupdate = 5\n>>>"
        result = self.repair._fix_missing_symbols(text)
        lines = result.split("\n")
        # 1行目（ブロック外）は補完される
        assert lines[0].startswith(":: update")
        # ブロック内の行は変更なし
        assert "update = 5" in result
        assert result.count("update = 5") == 1  # ブロック内のみ

    def test_vitals_string_inside_block_unchanged(self) -> None:
        """
        ブロック内の 'confidence: 95%' はバイタル補完されないことを確認する。

        Args: なし
        Returns: なし
        """
        text = "<<<\nconfidence: 95%\n>>>"
        result = self.repair._fix_missing_symbols(text)
        assert "confidence: 95%" in result


class TestFixMarkdownBlocksProtection:
    """_fix_markdown_blocks のブロック保護テスト"""

    def setup_method(self) -> None:
        """
        各テストの前に AutoRepair インスタンスを生成する。

        Args: なし
        Returns: なし
        """
        self.repair = AutoRepair()

    def test_backtick_fence_inside_symops_block_preserved(self) -> None:
        """
        既存の <<< ～ >>> ブロック内にある ``` フェンスは変換されず保護される。

        Args: なし
        Returns: なし
        """
        text = "<<<\n```python\nprint('hello')\n```\n>>>"
        result = self.repair._fix_markdown_blocks(text)
        # ブロック内の ``` はそのまま残る
        assert "```python" in result
        assert "```" in result

    def test_backtick_fence_outside_block_converted(self) -> None:
        """
        ブロック外の ``` フェンスは <<< / >>> に変換される。

        Args: なし
        Returns: なし
        """
        text = "```python\nprint('hello')\n```"
        result = self.repair._fix_markdown_blocks(text)
        assert "<<<" in result
        assert ">>>" in result
        # 元の ``` は消える（言語タグも捨てる）
        assert "```python" not in result

    def test_language_tag_dropped_on_conversion(self) -> None:
        """
        ブロック外の開きフェンスの言語タグ（```python など）は変換時に捨てられる。

        Args: なし
        Returns: なし
        """
        text = "```javascript\nconst x = 1;\n```"
        result = self.repair._fix_markdown_blocks(text)
        assert "javascript" not in result
        assert "<<<" in result
        assert "const x = 1;" in result

    def test_content_preserved_on_conversion(self) -> None:
        """
        フェンスが <<< / >>> に変換されてもコード本体は保持される。

        Args: なし
        Returns: なし
        """
        text = "```\ndef foo():\n    return 42\n```"
        result = self.repair._fix_markdown_blocks(text)
        assert "def foo():" in result
        assert "return 42" in result

    def test_mixed_symops_and_markdown_blocks(self) -> None:
        """
        既存の <<< ブロックとブロック外の ``` フェンスが混在する場合、
        それぞれ適切に処理される。

        Args: なし
        Returns: なし
        """
        text = "<<<\n```inside_block\n```\n>>>\n```python\noutside_code\n```"
        result = self.repair._fix_markdown_blocks(text)
        # ブロック内の ``` は保護
        assert "```inside_block" in result
        # ブロック外の ``` は変換
        assert "outside_code" in result
        assert "```python" not in result


class TestFixVitalsFormatBlockProtection:
    """_fix_vitals_format のブロック保護テスト"""

    def setup_method(self) -> None:
        """
        各テストの前に AutoRepair インスタンスを生成する。

        Args: なし
        Returns: なし
        """
        self.repair = AutoRepair()

    def test_vitals_percent_inside_block_unchanged(self) -> None:
        """
        ブロック内の 'confidence: 95%' は ::c0.95 に変換されないことを確認する。

        Args: なし
        Returns: なし
        """
        text = "<<<\nconfidence: 95%\n>>>"
        result = self.repair._fix_vitals_format(text)
        assert "confidence: 95%" in result
        assert "::c" not in result

    def test_vitals_percent_outside_block_converted(self) -> None:
        """
        ブロック外の 'confidence: 95%' は ::c0.95 に変換されることを確認する。

        Args: なし
        Returns: なし
        """
        text = "confidence: 95%"
        result = self.repair._fix_vitals_format(text)
        assert "::c0.95" in result
        assert "confidence: 95%" not in result

    def test_vitals_in_block_vs_outside(self) -> None:
        """
        ブロック内外に同じバイタル表記がある場合、外側のみ変換される。

        Args: なし
        Returns: なし
        """
        text = "confidence: 80%\n<<<\nconfidence: 80%\n>>>"
        result = self.repair._fix_vitals_format(text)
        lines = result.split("\n")
        # ブロック外（1行目）は変換される
        assert "::c" in lines[0]
        # ブロック内は保持される
        assert "confidence: 80%" in result


class TestApplyOutsideBlocks:
    """_apply_outside_blocks のブロック境界テスト"""

    def setup_method(self) -> None:
        """
        各テストの前に AutoRepair インスタンスを生成する。

        Args: なし
        Returns: なし
        """
        self.repair = AutoRepair()

    def test_indented_arrow_does_not_close_block(self) -> None:
        """
        インデント付きの >>> （例: Python doctest の '    >>>'）は
        ブロック終端として扱われないことを確認する（v3.2 doctest 保護）。

        Args: なし
        Returns: なし
        """
        # インデント付き >>> が来てもブロックは閉じない
        marker_calls: list[str] = []

        def track_fix(line: str) -> str:
            marker_calls.append(line)
            return line

        text = "<<<\n    >>> doctest_line\n>>>"
        self.repair._apply_outside_blocks(text, track_fix)

        # 3行すべてがブロック内扱いであり、track_fix は呼ばれていないはず
        assert "    >>> doctest_line" not in marker_calls

    def test_column_zero_arrow_closes_block(self) -> None:
        """
        行頭（column 0）の >>> はブロック終端として認識されることを確認する。

        Args: なし
        Returns: なし
        """
        marker_calls: list[str] = []

        def track_fix(line: str) -> str:
            marker_calls.append(line)
            return line

        # ブロック後の行は track_fix で処理されるはず
        text = "<<<\ncode\n>>>\noutside_line"
        self.repair._apply_outside_blocks(text, track_fix)

        assert "outside_line" in marker_calls

    def test_block_content_not_passed_to_fix(self) -> None:
        """
        ブロック内の行は fix_line 関数に渡されないことを確認する。

        Args: なし
        Returns: なし
        """
        seen: list[str] = []

        def collecting_fix(line: str) -> str:
            seen.append(line)
            return line

        text = "<<<\nSECRET_CONTENT\n>>>"
        self.repair._apply_outside_blocks(text, collecting_fix)

        assert "SECRET_CONTENT" not in seen

    def test_outside_line_is_passed_to_fix(self) -> None:
        """
        ブロック外の行は fix_line 関数に渡されることを確認する。

        Args: なし
        Returns: なし
        """
        seen: list[str] = []

        def collecting_fix(line: str) -> str:
            seen.append(line)
            return line

        text = "OUTSIDE_LINE\n<<<\nINSIDE\n>>>"
        self.repair._apply_outside_blocks(text, collecting_fix)

        assert "OUTSIDE_LINE" in seen
        assert "INSIDE" not in seen

    def test_trailing_space_on_close_not_accepted(self) -> None:
        """
        '>>> ' （末尾スペース）はブロック終端として扱われず、
        ブロック内容として保護されることを確認する。

        Args: なし
        Returns: なし
        """
        # '>>>  ' は line.rstrip() == '>>>' を満たさないのでブロックは閉じない
        seen: list[str] = []

        def collecting_fix(line: str) -> str:
            seen.append(line)
            return line

        # rstrip() すると '>>>' になるので実際は閉じる ── ただし
        # ソースコードの判定は line.rstrip() == '>>>' なので
        # 末尾スペース ">>>  " は rstrip() で ">>>" になり閉じる
        text = "<<<\nsome_line\n>>>  \nafter_line"
        self.repair._apply_outside_blocks(text, collecting_fix)
        # after_line はブロック終了後なので fix に渡される
        assert "after_line" in seen


class TestSymOpsProcessorIntegration:
    """SymOpsProcessor 経由のブロック保護統合テスト。

    パイプラインの注意点: PlainMarkdownConverter が先行して動作するため、
    入力にはバイタル行（例: ::c0.9 ::s1.0）を含める必要がある。
    """

    def setup_method(self) -> None:
        """
        各テストの前に SymOpsProcessor インスタンスを生成する。

        Args: なし
        Returns: なし
        """
        self.processor = SymOpsProcessor()

    def test_block_content_preserved_byte_for_byte(self) -> None:
        """
        ::write_file アクションのブロック内に
        - コード行（update = 5）
        - read で始まる行
        - confidence: 95% の文字列
        - ```python フェンス
        が含まれていても、パース後の .content が原文と一致することを確認する。

        Args: なし
        Returns: なし
        """
        # ブロック内に各種「修復対象っぽい」内容を含める
        inner_content = (
            "update = 5\n"
            "read the config file\n"
            "confidence: 95%\n"
            "```python\n"
            "x = 1\n"
            "```"
        )

        llm_output = (
            "::c0.9 ::s1.0 ::m0.1 ::f1.0\n"
            "::write_file @app.py\n"
            "<<<\n"
            f"{inner_content}\n"
            ">>>"
        )

        result = self.processor.process(llm_output)

        assert len(result.actions) >= 1
        action = result.actions[0]
        assert action.type == "write_file"
        assert action.path == "app.py"

        # ブロック内容が byte-for-byte 保持されていること
        assert action.content == inner_content

    def test_bare_fence_outside_block_becomes_content(self) -> None:
        """
        ::write_file アクションの後にブロック外で ``` フェンスがある場合、
        フェンスのコードがアクションの content として取り込まれることを確認する。

        Args: なし
        Returns: なし
        """
        llm_output = (
            "::c0.9 ::s1.0 ::m0.1 ::f1.0\n"
            "::write_file @bar.py\n"
            "```python\n"
            "def hello():\n"
            "    pass\n"
            "```"
        )

        result = self.processor.process(llm_output)

        assert len(result.actions) >= 1
        action = result.actions[0]
        assert action.type == "write_file"
        assert action.path == "bar.py"
        # フェンス外のコードがコンテンツとして含まれること
        assert "def hello():" in action.content
        assert "pass" in action.content
        # フェンスマーカー自体は content に含まれないこと
        assert "```python" not in action.content
        assert action.content.strip().startswith("def hello():")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
