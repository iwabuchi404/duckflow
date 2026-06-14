"""
AutoRepair._fix_unclosed_blocks の単体テスト。

バグ修正の検証:
- v3.2 以前は text.count('<<<') による部分文字列カウントだったため、
  <<<<<<< SEARCH のような 7 文字マーカーを誤計上していた。
- v3.3 からは行単位判定: strip() == '<<<' (open) / rstrip() == '>>>' (close)。

テスト識別子・説明は日本語、コード識別子は英語（CLAUDE.md §2 準拠）。
"""

import pytest
from companion.utils.sym_ops import AutoRepair


@pytest.fixture
def repair() -> AutoRepair:
    """
    テスト用 AutoRepair インスタンスを返す。

    Args:
        なし

    Returns:
        AutoRepair インスタンス
    """
    return AutoRepair()


# ---------------------------------------------------------------------------
# テスト 1: 正常に閉じられたブロックは変更されない
# ---------------------------------------------------------------------------

def test_正常に閉じたブロックは変更されない(repair: AutoRepair) -> None:
    """
    open_count == close_count の場合、EOF に '>>>' が追加されないことを確認する。

    Args:
        repair: AutoRepair インスタンス

    Returns:
        なし
    """
    text = "<<< \nsome content\n>>>"
    result = repair._fix_unclosed_blocks(text)
    assert result == text, (
        f"正常なブロックが変更されてしまった\n入力: {repr(text)}\n出力: {repr(result)}"
    )


# ---------------------------------------------------------------------------
# テスト 2: 閉じられていない <<< ブロックに >>> が追加される
# ---------------------------------------------------------------------------

def test_未閉鎖ブロックに終端区切りが追加される(repair: AutoRepair) -> None:
    """
    <<< があって >>> がない場合、EOF に '>>>' が 1 行追加されることを確認する。

    Args:
        repair: AutoRepair インスタンス

    Returns:
        なし
    """
    text = "<<<\nsome content"
    result = repair._fix_unclosed_blocks(text)
    assert result.rstrip('\n').endswith(">>>"), (
        f"未閉鎖ブロックに >>> が追加されなかった\n出力: {repr(result)}"
    )
    # 追加した >>> の行数は不足分だけ（open=1, close=0 → 1 行追加）
    added_lines = result.splitlines()
    close_lines = [l for l in added_lines if l.rstrip() == ">>>"]
    assert len(close_lines) == 1, (
        f">>> が 1 行追加されるはずが {len(close_lines)} 行になった"
    )


# ---------------------------------------------------------------------------
# テスト 3: 回帰テスト — 7 文字マーカー (<<<<<<< SEARCH / >>>>>>> REPLACE) を
#             含むテキストに余分な >>> が追加されない
# ---------------------------------------------------------------------------

def test_7文字マーカーを含むテキストに余分な終端が追加されない(repair: AutoRepair) -> None:
    """
    <<<<<<< SEARCH / >>>>>>> REPLACE のような 7 文字マーカーは、
    行単位判定では '<<<' / '>>>' とマッチしないため open/close としてカウントされない。
    したがって未閉鎖とみなされず、余分な '>>>' が追加されないことを確認する。

    これは v3.2 以前のバグ（部分文字列カウントで誤計上）の回帰テストである。

    Args:
        repair: AutoRepair インスタンス

    Returns:
        なし
    """
    text = (
        "<<<<<<< SEARCH\n"
        "x = 1\n"
        "=======\n"
        "x = 2\n"
        ">>>>>>> REPLACE\n"
    )
    result = repair._fix_unclosed_blocks(text)
    # 入力と出力が完全に同一であること（>>> が追加されない）
    assert result == text, (
        f"7文字マーカーのテキストが変更されてしまった\n入力: {repr(text)}\n出力: {repr(result)}"
    )


# ---------------------------------------------------------------------------
# テスト 4: インデント付き >>> はブロック終端としてカウントされない
# ---------------------------------------------------------------------------

def test_インデント付き終端行はクローズとしてカウントされない(repair: AutoRepair) -> None:
    """
    インデントされた '    >>>' はブロック終端の '>>>' (rstrip() == '>>>') と
    一致しないため close_count に加算されない。

    ケース:
    - <<< が 1 行（open_count=1）
    - インデント付き '    >>>' が 1 行（close_count=0）
    → 未閉鎖とみなされ EOF に '>>>' が 1 行追加される。

    Args:
        repair: AutoRepair インスタンス

    Returns:
        なし
    """
    text = "<<<\n    >>> (doctest line)\nsome other content"
    result = repair._fix_unclosed_blocks(text)
    # 未閉鎖なので >>> が追加されるべき
    assert result.rstrip('\n').endswith(">>>"), (
        f"インデント >>> しかないブロックが閉じ済みと判定されてしまった\n出力: {repr(result)}"
    )

    # 正しく列 0 の >>> で閉じたケースは追加されない
    text_closed = "<<<\nsome content\n>>>"
    result_closed = repair._fix_unclosed_blocks(text_closed)
    assert result_closed == text_closed, (
        f"列 0 の >>> で閉じたブロックが変更された\n出力: {repr(result_closed)}"
    )
