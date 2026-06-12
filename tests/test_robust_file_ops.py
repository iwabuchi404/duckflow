import pytest
import asyncio
from pathlib import Path
from companion.tools.file_ops import FileOps

@pytest.fixture
def file_ops(tmp_path):
    ops = FileOps()
    ops.workspace_root = tmp_path
    return ops

@pytest.mark.asyncio
async def test_extract_find_replace_fallback_single_line(file_ops):
    # Test v2.2 single-line fallback
    text = "find: old_code\nreplace: new_code\noccurrence: 2"
    res = file_ops._extract_find_replace_fallback(text)
    assert res == {'find': 'old_code', 'replace': 'new_code', 'occurrence': 2}

@pytest.mark.asyncio
async def test_extract_find_replace_fallback_mixed(file_ops):
    # Test mixed multi-line and single-line
    text = "find: |\n    multi\n    line\nreplace: single_line"
    res = file_ops._extract_find_replace_fallback(text)
    assert res == {'find': 'multi\nline', 'replace': 'single_line'}

@pytest.mark.asyncio
async def test_sanitize_content(file_ops):
    """
    v2.4 エッジトリムポリシーのテスト。

    先頭と末尾のプロトコル行・空行のみを除去し、
    本文中のすべての行は一切変更されないことを確認する。

    入力:
    - 先頭: vitals 行（::c0.9 ::s1.0）+ 区切り行（<<<）
    - 本文: 単独の >>> 行、インデント付き     >>> 行、
            mid-body の :: response @ hi 行（leakではない通常行として保持）
    - 末尾: 単独の >>> 行

    期待値:
    - 先頭・末尾のプロトコル行は除去される
    - 本文中の >>> 行（単独・インデント両方）はそのまま保持される
    - 本文中の :: response @ hi 行も保持される
    """
    input_text = (
        "::c0.9 ::s1.0\n"          # 先頭 vitals 行（エッジ）
        "<<<\n"                      # 先頭 block 区切り（エッジ）
        "def real_body():\n"         # 本文開始
        "    return True\n"
        ">>>\n"                      # 本文中の単独 >>> 行（保持すべき）
        "    >>>\n"                  # 本文中のインデント >>> 行（保持すべき）
        ":: response @ hi\n"         # 本文中の :: response 行（保持すべき）
        "    pass\n"
        ">>>"                        # 末尾 >>> 行（エッジ、除去すべき）
    )

    result = file_ops._sanitize_content(input_text)

    # 先頭プロトコル行が除去されていること
    assert not result.startswith("::c0.9"), "先頭の vitals 行が除去されていない"
    assert not result.startswith("<<<"), "先頭の <<< が除去されていない"

    # 本文の先頭行が保持されていること
    assert result.startswith("def real_body():")

    # 本文中の >>> 行（単独）が保持されていること
    lines = result.splitlines()
    assert ">>>" in lines, "本文中の単独 >>> 行が削除されている（エッジトリムの誤適用）"

    # 本文中のインデント付き >>> 行が保持されていること
    assert "    >>>" in lines, "本文中のインデント付き >>> 行が削除されている"

    # 本文中の :: response @ hi 行が保持されていること
    assert ":: response @ hi" in result, "本文中の :: response @ hi 行が削除されている"

    # 末尾の >>> が除去されていること（末尾エッジ）
    assert not result.endswith(">>>"), "末尾の >>> が除去されていない"

    # 本文の通常コード行が保持されていること
    assert "def real_body():" in result
    assert "    return True" in result
    assert "    pass" in result


@pytest.mark.asyncio
async def test_write_file_sanitization(file_ops, tmp_path):
    """
    write_file が先頭・末尾のプロトコル行を除去して書き込むことを確認する(v2.4)。

    ::response @done（先頭エッジ）と >>> （末尾エッジ）は除去され、
    本文の valid_code = 123 のみがファイルに書き込まれる。
    """
    path = "test.py"
    content = "::response @done\nvalid_code = 123\n>>>"
    await file_ops.write_file(path, content)

    written = (tmp_path / path).read_text()
    assert written == "valid_code = 123", (
        f"期待値 'valid_code = 123' と一致しない。実際の内容: {repr(written)}"
    )


@pytest.mark.asyncio
async def test_edit_file_sanitization(file_ops, tmp_path):
    """
    edit_file が replace テキスト末尾のプロトコル行を除去して書き込むことを確認する(v2.4)。

    replace に "new_line = 2\\n>>>" を渡した場合、
    ファイルには new_line = 2 のみが書き込まれ、末尾の >>> は除去される。
    edit_file のシグネチャ: await file_ops.edit_file(path=..., find=..., replace=...)
    """
    path = "sample.py"
    (tmp_path / path).write_text("old_line = 1", encoding='utf-8')

    await file_ops.edit_file(
        path=path,
        find="old_line = 1",
        replace="new_line = 2\n>>>"
    )

    written = (tmp_path / path).read_text()
    assert "new_line = 2" in written, "new_line = 2 がファイルに書き込まれていない"
    assert not written.rstrip().endswith(">>>"), (
        f"末尾の >>> が除去されていない。実際の内容: {repr(written)}"
    )
