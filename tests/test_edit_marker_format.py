"""
SEARCH/REPLACE マーカー形式の edit_file テスト。

対象: companion/tools/file_ops.py FileOps.edit_file（マーカー形式経路）
テスト識別子・説明は日本語、コード識別子は英語（CLAUDE.md §2 準拠）。
"""

import pytest
from pathlib import Path

from companion.tools.file_ops import FileOps


# ---------------------------------------------------------------------------
# フィクスチャ
# ---------------------------------------------------------------------------

@pytest.fixture
def file_ops(tmp_path: Path) -> FileOps:
    """
    テスト用 FileOps インスタンスを返す。

    Args:
        tmp_path: pytest が提供する一時ディレクトリ

    Returns:
        workspace_root が tmp_path に設定された FileOps インスタンス
    """
    ops = FileOps()
    ops.workspace_root = tmp_path
    return ops


# ---------------------------------------------------------------------------
# テスト 1: 基本的なマーカー編集（共通インデントのあるメソッド本体）
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_基本的なマーカー編集が成功する(file_ops: FileOps, tmp_path: Path) -> None:
    """
    クラス内メソッドに対してマーカー形式で編集が行えることを確認する。

    SEARCH にはインデント付きコードを渡し、REPLACE で返り値型ヒントと
    戻り値を変更する。成功時は結果が "Successfully edited" で始まることを確認する。

    Args:
        file_ops: workspace_root を tmp_path に向けた FileOps
        tmp_path: pytest 一時ディレクトリ

    Returns:
        なし
    """
    target = tmp_path / "sample.py"
    target.write_text("class C:\n    def foo(self):\n        return 1\n", encoding="utf-8")

    content = (
        "<<<<<<< SEARCH\n"
        "    def foo(self):\n"
        "        return 1\n"
        "=======\n"
        "    def foo(self) -> int:\n"
        "        return 2\n"
        ">>>>>>> REPLACE\n"
    )

    result = await file_ops.edit_file("sample.py", content=content)

    assert result.startswith("Successfully edited"), f"期待: 'Successfully edited' で始まる文字列\n実際: {result}"

    text = target.read_text(encoding="utf-8")
    assert "def foo(self) -> int:" in text, "返り値型ヒントが追加されていない"
    assert "return 2" in text, "戻り値が更新されていない"


# ---------------------------------------------------------------------------
# テスト 2: 寛容なマーカー形式（<<<<<<, =====, >>>>>> replace）
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_寛容なマーカー形式でも編集できる(file_ops: FileOps, tmp_path: Path) -> None:
    """
    マーカー長が 6 文字・5 文字でも編集が成功することを確認する。

    _SR_OPEN_RE は `<{4,}`、_SR_SEP_RE は `={4,}`、_SR_CLOSE_RE は `>{4,}` に
    マッチするため、7 文字未満でも動作するはずである。

    Args:
        file_ops: workspace_root を tmp_path に向けた FileOps
        tmp_path: pytest 一時ディレクトリ

    Returns:
        なし
    """
    target = tmp_path / "val.py"
    target.write_text("x = 1\n", encoding="utf-8")

    content = (
        "<<<<<< SEARCH\n"   # 6 文字の開始マーカー
        "x = 1\n"
        "=====\n"           # 5 文字の区切り
        "x = 99\n"
        ">>>>>> replace\n"  # 小文字ラベル
    )

    result = await file_ops.edit_file("val.py", content=content)

    assert result.startswith("Successfully edited"), f"寛容なマーカーで失敗: {result}"
    assert "x = 99" in target.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# テスト 3: 複数 SEARCH/REPLACE ブロックを一度に適用する
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_複数ブロックで複数箇所を一度に編集できる(file_ops: FileOps, tmp_path: Path) -> None:
    """
    2 つの SEARCH/REPLACE ブロックを含む content で 2 箇所が編集されることを確認する。

    Args:
        file_ops: workspace_root を tmp_path に向けた FileOps
        tmp_path: pytest 一時ディレクトリ

    Returns:
        なし
    """
    target = tmp_path / "multi.py"
    target.write_text("A = 1\nB = 2\n", encoding="utf-8")

    content = (
        "<<<<<<< SEARCH\n"
        "A = 1\n"
        "=======\n"
        "A = 10\n"
        ">>>>>>> REPLACE\n"
        "<<<<<<< SEARCH\n"
        "B = 2\n"
        "=======\n"
        "B = 20\n"
        ">>>>>>> REPLACE\n"
    )

    result = await file_ops.edit_file("multi.py", content=content)

    assert result.startswith("Successfully edited"), f"複数ブロック編集で失敗: {result}"
    text = target.read_text(encoding="utf-8")
    assert "A = 10" in text, "1 つ目のブロックが適用されていない"
    assert "B = 20" in text, "2 つ目のブロックが適用されていない"


# ---------------------------------------------------------------------------
# テスト 4: 対象ファイルに git コンフリクトマーカーがある場合は拒否する
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_コンフリクトファイルへのマーカー編集は拒否される(file_ops: FileOps, tmp_path: Path) -> None:
    """
    git コンフリクトマーカー（<<<<<<< HEAD ... ======= ... >>>>>>> main）を
    含むファイルに対してマーカー形式編集を試みると、エラーが返りファイルは
    変更されないことを確認する。

    Args:
        file_ops: workspace_root を tmp_path に向けた FileOps
        tmp_path: pytest 一時ディレクトリ

    Returns:
        なし
    """
    conflict_text = (
        "<<<<<<< HEAD\n"
        "x = 1\n"
        "=======\n"
        "x = 2\n"
        ">>>>>>> main\n"
    )
    target = tmp_path / "conflict.py"
    target.write_text(conflict_text, encoding="utf-8")

    content = (
        "<<<<<<< SEARCH\n"
        "x = 1\n"
        "=======\n"
        "x = 99\n"
        ">>>>>>> REPLACE\n"
    )

    result = await file_ops.edit_file("conflict.py", content=content)

    assert "conflict_markers_in_target" in result, (
        f"コンフリクトファイルへの編集がエラーにならなかった: {result}"
    )
    # ファイルは変更されていないこと
    assert target.read_text(encoding="utf-8") == conflict_text, (
        "コンフリクトファイルが書き換えられてしまった"
    )


# ---------------------------------------------------------------------------
# テスト 5: 区切り（=======）のない SEARCH ブロックは marker_parse_failed を返す
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_区切りのないブロックはパース失敗エラーになる(file_ops: FileOps, tmp_path: Path) -> None:
    """
    `=======` セパレータを持たない SEARCH ブロックを渡した場合、
    marker_parse_failed エラーが返りファイルは変更されないことを確認する。

    Args:
        file_ops: workspace_root を tmp_path に向けた FileOps
        tmp_path: pytest 一時ディレクトリ

    Returns:
        なし
    """
    original = "val = 42\n"
    target = tmp_path / "nosep.py"
    target.write_text(original, encoding="utf-8")

    # セパレータなし — SEARCH だけで REPLACE なし
    content = (
        "<<<<<<< SEARCH\n"
        "val = 42\n"
        ">>>>>>> REPLACE\n"  # ======= がないので区切りとして認識されない
    )

    result = await file_ops.edit_file("nosep.py", content=content)

    assert "marker_parse_failed" in result, (
        f"区切りなしブロックがエラーにならなかった: {result}"
    )
    assert target.read_text(encoding="utf-8") == original, (
        "区切りなしブロックでファイルが変更されてしまった"
    )


# ---------------------------------------------------------------------------
# テスト 6: _has_git_conflict_markers の単体テスト
#           （marker_leak_in_replace を確実にトリガーするのが困難なため、
#             内部メソッドを直接テストしてサニティチェックのロジックを検証する）
# ---------------------------------------------------------------------------

def test_has_git_conflict_markers_は正しく判定する(file_ops: FileOps) -> None:
    """
    _has_git_conflict_markers が git コンフリクトマーカーの有無を
    正しく判定することを確認する。

    note: marker_leak_in_replace は、パース結果の REPLACE 部分に
    _has_git_conflict_markers が True を返す内容か、先頭が '<<<<<<<' / '>>>>>>>'
    で始まる内容が含まれるときに発火する。このメソッドを直接テストすることで
    サニティチェック経路のロジックを検証する。

    Args:
        file_ops: FileOps インスタンス（workspace_root は未使用）

    Returns:
        なし
    """
    # コンフリクトあり: <<<<<<< HEAD と ======= が両方存在
    conflict = "<<<<<<< HEAD\nfoo\n=======\nbar\n>>>>>>> main\n"
    assert FileOps._has_git_conflict_markers(conflict) is True, (
        "コンフリクトマーカー付きテキストで True にならなかった"
    )

    # コンフリクトなし: <<<<<<< のみで ======= がない
    no_sep = "<<<<<<< HEAD\nfoo\n>>>>>>> main\n"
    assert FileOps._has_git_conflict_markers(no_sep) is False, (
        "======= がないテキストで True になってしまった"
    )

    # コンフリクトなし: 通常コード
    normal = "x = 1\ny = 2\n"
    assert FileOps._has_git_conflict_markers(normal) is False, (
        "通常コードで True になってしまった"
    )


# ---------------------------------------------------------------------------
# テスト 7: 後方互換性 — レガシー find:/replace: 形式も引き続き動作する
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_レガシー形式でも編集できる(file_ops: FileOps, tmp_path: Path) -> None:
    """
    SEARCH/REPLACE マーカーを含まない find:/replace: 形式での編集が
    引き続き動作することを確認する（後方互換性テスト）。

    Args:
        file_ops: workspace_root を tmp_path に向けた FileOps
        tmp_path: pytest 一時ディレクトリ

    Returns:
        なし
    """
    target = tmp_path / "legacy.py"
    target.write_text("val = 1\n", encoding="utf-8")

    content = "find: |\n    val = 1\nreplace: |\n    val = 2\n"

    result = await file_ops.edit_file("legacy.py", content=content)

    assert result.startswith("Successfully edited"), f"レガシー形式で失敗: {result}"
    assert "val = 2" in target.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# テスト 8: SEARCH テキストがファイルに存在しない場合は find_not_matched エラー
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_存在しないテキストのSEARCHはfind_not_matchedエラーになる(
    file_ops: FileOps, tmp_path: Path
) -> None:
    """
    ファイルに存在しないテキストを SEARCH ブロックに書いた場合、
    find_not_matched エラーが返ることを確認する。

    Args:
        file_ops: workspace_root を tmp_path に向けた FileOps
        tmp_path: pytest 一時ディレクトリ

    Returns:
        なし
    """
    target = tmp_path / "notfound.py"
    target.write_text("hello = 'world'\n", encoding="utf-8")

    content = (
        "<<<<<<< SEARCH\n"
        "this_line_does_not_exist_in_file = True\n"
        "=======\n"
        "replaced = True\n"
        ">>>>>>> REPLACE\n"
    )

    result = await file_ops.edit_file("notfound.py", content=content)

    assert "find_not_matched" in result, (
        f"存在しないテキストの SEARCH でエラーにならなかった: {result}"
    )
