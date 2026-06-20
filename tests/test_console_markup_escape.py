"""
DuckUI の表示メソッドが、内部識別タグ（[TOOL_RESULT] など）を含む文字列を
表示してもクラッシュしないことを検証するテスト。

背景: Rich の console.print は markup=True がデフォルトで、文字列中の
`[...]` を全てスタイルタグとして解釈する。[TOOL_RESULT]/[/TOOL_RESULT]
エンベロープ（companion/tools/results.py）を含むエラーメッセージ等が
エスケープなしで渡ると、対応する開始タグが無いため
rich.errors.MarkupError が送出されクラッシュしていた。
"""

from companion.ui.console import DuckUI


DANGEROUS_CONTENT = "::status error\n[TOOL_RESULT]\nsomething\n[/TOOL_RESULT]"
SURROGATE_CONTENT = "invalid unicode: \udcff\n[TOOL_RESULT]\nvalue\n[/TOOL_RESULT]"


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
    ui.print_action(
        "edit_file", {"path": "[TOOL_RESULT]foo[/TOOL_RESULT]"}, "thought [x]"
    )


def test_print_methods_do_not_raise_on_lone_surrogates() -> None:
    """主要な表示メソッドが単独サロゲートを含む文字列でも例外を出さないことを確認する。"""
    ui = _make_ui()

    ui.print_error(SURROGATE_CONTENT)
    ui.print_warning(SURROGATE_CONTENT)
    ui.print_info(SURROGATE_CONTENT)
    ui.print_system(SURROGATE_CONTENT)
    ui.print_user(SURROGATE_CONTENT)
    ui.print_thinking(SURROGATE_CONTENT)
    ui.print_success(SURROGATE_CONTENT)
    ui.print_result(SURROGATE_CONTENT, is_error=True)
    ui.print_conversation_message(SURROGATE_CONTENT, speaker="assistant")
    ui.print_action("edit_file", {"path": SURROGATE_CONTENT}, SURROGATE_CONTENT)


def test_print_code_and_markdown_do_not_raise_on_lone_surrogates() -> None:
    """Markdown/Syntax renderable も単独サロゲートで例外を出さないことを確認する。"""
    ui = _make_ui()

    ui.print_markdown(f"# Heading\n\n{SURROGATE_CONTENT}")
    ui.print_code(f"value = {SURROGATE_CONTENT!r}", language="python")


def test_update_status_sanitizes_lone_surrogates() -> None:
    """Live ステータス表示に渡る文字列から単独サロゲートが除去されることを確認する。"""
    ui = _make_ui()

    ui.update_status(SURROGATE_CONTENT)

    assert "\udcff" not in ui.status_text
    ui._make_status_line()
