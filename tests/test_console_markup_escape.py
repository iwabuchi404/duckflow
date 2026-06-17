"""
DuckUI の表示メソッドが、内部識別タグ（[TOOL_RESULT] など）を含む文字列を
表示してもクラッシュしないことを検証するテスト。

背景: Rich の console.print は markup=True がデフォルトで、文字列中の
`[...]` を全てスタイルタグとして解釈する。[TOOL_RESULT]/[/TOOL_RESULT]
エンベロープ（companion/tools/results.py）を含むエラーメッセージ等が
エスケープなしで渡ると、対応する開始タグが無いため
rich.errors.MarkupError が送出されクラッシュしていた。
"""

import os
import sys

sys.path.append(os.getcwd())

from companion.ui.console import DuckUI


DANGEROUS_CONTENT = "::status error\n[TOOL_RESULT]\nsomething\n[/TOOL_RESULT]"


def _make_ui() -> DuckUI:
    """テスト用に新規 DuckUI インスタンスを生成する。"""
    return DuckUI()


def test_print_error_does_not_raise_on_bracket_content() -> None:
    """print_error が角括弧タグを含む文字列でも例外を出さないことを確認する。"""
    ui = _make_ui()
    ui.print_error(DANGEROUS_CONTENT)


def test_print_warning_does_not_raise_on_bracket_content() -> None:
    """print_warning が角括弧タグを含む文字列でも例外を出さないことを確認する。"""
    ui = _make_ui()
    ui.print_warning(DANGEROUS_CONTENT)


def test_print_info_does_not_raise_on_bracket_content() -> None:
    """print_info が角括弧タグを含む文字列でも例外を出さないことを確認する。"""
    ui = _make_ui()
    ui.print_info(DANGEROUS_CONTENT)


def test_print_system_does_not_raise_on_bracket_content() -> None:
    """print_system が角括弧タグを含む文字列でも例外を出さないことを確認する。"""
    ui = _make_ui()
    ui.print_system(DANGEROUS_CONTENT)


def test_print_result_does_not_raise_on_bracket_content() -> None:
    """print_result が角括弧タグを含む文字列でも例外を出さないことを確認する。"""
    ui = _make_ui()
    ui.print_result(DANGEROUS_CONTENT, is_error=True)


def test_print_action_does_not_raise_on_bracket_content() -> None:
    """print_action がパラメータ値に角括弧タグを含んでも例外を出さないことを確認する。"""
    ui = _make_ui()
    ui.print_action("edit_file", {"path": "[TOOL_RESULT]foo[/TOOL_RESULT]"}, "thought [x]")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
