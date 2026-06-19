"""
find_files / grep_files が __pycache__ や node_modules のようなノイズ
ディレクトリを再帰走査してしまうと、.pyc 等のバイナリファイルがテキスト検索
でヒットし、ユーザーが報告した「.pycノイズ」の原因になる。
従来はドット始まり（.git 等）のみを除外していたため、これらは素通りしていた。
"""

import os
import sys

sys.path.append(os.getcwd())

import asyncio
import pytest
from companion.tools.file_ops import FileOps


@pytest.fixture
def workspace(tmp_path):
    """ノイズディレクトリと通常ファイルを含むワークスペースを構築する。"""
    (tmp_path / "companion").mkdir()
    (tmp_path / "companion" / "main.py").write_text("print('hi')\n", encoding="utf-8")

    pycache = tmp_path / "companion" / "__pycache__"
    pycache.mkdir()
    (pycache / "main.cpython-311.pyc").write_bytes(b"\x00\x01\x02garbage TODO bytes")

    node_modules = tmp_path / "node_modules" / "some-pkg"
    node_modules.mkdir(parents=True)
    (node_modules / "index.py").write_text("# TODO noise\n", encoding="utf-8")

    egg_info = tmp_path / "sample.egg-info"
    egg_info.mkdir()
    (egg_info / "SOURCES.txt").write_text("TODO noise\n", encoding="utf-8")

    return FileOps(workspace_root=str(tmp_path))


class TestFindFilesExcludesNoiseDirs:
    """find_files がノイズディレクトリを除外することのテスト"""

    @pytest.mark.asyncio
    async def test_does_not_recurse_into_pycache(self, workspace: FileOps) -> None:
        """__pycache__ 内のファイルが結果に含まれないことを確認する。"""
        results = await workspace.find_files(pattern="*", path=".")
        assert not any("__pycache__" in r for r in results)

    @pytest.mark.asyncio
    async def test_does_not_recurse_into_node_modules(self, workspace: FileOps) -> None:
        """node_modules 内のファイルが結果に含まれないことを確認する。"""
        results = await workspace.find_files(pattern="*", path=".")
        assert not any("node_modules" in r for r in results)

    @pytest.mark.asyncio
    async def test_does_not_recurse_into_egg_info(self, workspace: FileOps) -> None:
        """*.egg-info 内のファイルが結果に含まれないことを確認する。"""
        results = await workspace.find_files(pattern="*", path=".")
        assert not any(".egg-info" in r for r in results)

    @pytest.mark.asyncio
    async def test_normal_files_still_found(self, workspace: FileOps) -> None:
        """通常ファイルは引き続き検出されることを確認する（リグレッション防止）。"""
        results = await workspace.find_files(pattern="*.py", path=".")
        assert any("main.py" in r for r in results)


class TestGrepFilesExcludesNoiseDirs:
    """grep_files がノイズディレクトリを除外することのテスト"""

    @pytest.mark.asyncio
    async def test_pyc_noise_not_matched_even_with_wildcard_include(self, workspace: FileOps) -> None:
        """include='*'（デフォルト）でも __pycache__ 内の .pyc がノイズとしてヒットしないことを確認する。"""
        result = await workspace.grep_files(pattern="TODO", path=".", include="*")
        assert "__pycache__" not in result

    @pytest.mark.asyncio
    async def test_node_modules_not_matched(self, workspace: FileOps) -> None:
        """node_modules 内のファイルがヒットしないことを確認する。"""
        result = await workspace.grep_files(pattern="TODO", path=".", include="*")
        assert "node_modules" not in result

    @pytest.mark.asyncio
    async def test_egg_info_not_matched(self, workspace: FileOps) -> None:
        """*.egg-info 内のファイルがヒットしないことを確認する。"""
        result = await workspace.grep_files(pattern="TODO", path=".", include="*")
        assert ".egg-info" not in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
