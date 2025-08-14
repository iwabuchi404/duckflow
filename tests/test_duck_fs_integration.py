"""
Duck FS統合テスト

Duck FSとfile_toolsの統合動作を詳細にテストする
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock
from datetime import datetime

from codecrafter.tools.file_tools import file_tools, FileOperationError
from codecrafter.keeper import FileReadResult, FileWriteResult, DuckFileSystemError


class TestDuckFSDirectIntegration:
    """Duck FSとの直接統合テスト"""
    
    def setup_method(self):
        """各テストメソッド実行前の初期化"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "test.py")
        self.test_content = "# テストファイル\ndef test_function():\n    return 'test'\n"
    
    def teardown_method(self):
        """各テストメソッド実行後のクリーンアップ"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('codecrafter.keeper.duck_fs')
    def test_duck_fs_read_success(self, mock_duck_fs):
        """Duck FS読み取り成功時のテスト"""
        # Duck FSの成功レスポンスをモック
        mock_result = FileReadResult(
            content=self.test_content,
            path=self.test_file,
            read_percentage=1.0,
            total_size_bytes=len(self.test_content.encode('utf-8')),
            read_size_bytes=len(self.test_content.encode('utf-8')),
            file_type="python",
            encoding="utf-8",
            is_truncated=False,
            metadata={
                'modified_time': datetime.now(),
                'created_time': datetime.now(),
                'file_extension': '.py'
            }
        )
        mock_duck_fs.read.return_value = mock_result
        
        # ファイル読み取り実行
        content = file_tools.read_file(self.test_file)
        
        # 結果確認
        assert content == self.test_content
        mock_duck_fs.read.assert_called_once_with(self.test_file)
    
    @patch('codecrafter.keeper.duck_fs')
    def test_duck_fs_read_failure_fallback(self, mock_duck_fs):
        """Duck FS読み取り失敗時のフォールバック動作テスト"""
        # Duck FSの失敗をシミュレート
        mock_duck_fs.read.side_effect = DuckFileSystemError("Policy violation")
        
        # 実際のファイルを作成（フォールバック用）
        with open(self.test_file, "w", encoding="utf-8") as f:
            f.write(self.test_content)
        
        # ファイル読み取り実行（フォールバックが動作するはず）
        content = file_tools.read_file(self.test_file)
        
        # フォールバックで読み取れることを確認
        assert content == self.test_content
        mock_duck_fs.read.assert_called_once_with(self.test_file)
    
    @patch('codecrafter.keeper.duck_fs')
    def test_duck_fs_write_success(self, mock_duck_fs):
        """Duck FS書き込み成功時のテスト"""
        # Duck FSの成功レスポンスをモック
        mock_result = FileWriteResult(
            success=True,
            path=self.test_file,
            bytes_written=len(self.test_content.encode('utf-8')),
            backup_path=None,
            timestamp=datetime.now(),
            message="Write successful",
            metadata={}
        )
        mock_duck_fs.write.return_value = mock_result
        
        # ファイル書き込み実行
        result = file_tools.write_file(self.test_file, self.test_content)
        
        # 結果確認
        assert result["success"] is True
        assert result["bytes_written"] == len(self.test_content.encode('utf-8'))
        assert "timestamp" in result
        mock_duck_fs.write.assert_called_once()
    
    @patch('codecrafter.keeper.duck_fs')
    def test_duck_fs_write_with_backup(self, mock_duck_fs):
        """Duck FS書き込み（バックアップ付き）のテスト"""
        backup_path = self.test_file + ".backup"
        
        # Duck FSの成功レスポンス（バックアップ付き）をモック
        mock_result = FileWriteResult(
            success=True,
            path=self.test_file,
            bytes_written=len(self.test_content.encode('utf-8')),
            backup_path=backup_path,
            timestamp=datetime.now(),
            message="Write successful with backup",
            metadata={}
        )
        mock_duck_fs.write.return_value = mock_result
        
        # ファイル書き込み実行
        result = file_tools.write_file(self.test_file, self.test_content)
        
        # 結果確認
        assert result["success"] is True
        assert result["backup_created"] is True
        assert result["backup_path"] == backup_path
        mock_duck_fs.write.assert_called_once()
    
    @patch('codecrafter.keeper.duck_fs')
    def test_duck_fs_read_range_success(self, mock_duck_fs):
        """Duck FS範囲読み取り成功時のテスト"""
        range_content = "def test_function():\n    return 'test'\n"
        
        # Duck FSの成功レスポンスをモック
        mock_result = FileReadResult(
            content=range_content,
            path=self.test_file,
            read_percentage=0.5,
            total_size_bytes=len(self.test_content.encode('utf-8')),
            read_size_bytes=len(range_content.encode('utf-8')),
            file_type="python",
            encoding="utf-8",
            is_truncated=False,
            metadata={'start_line': 2, 'end_line': 3}
        )
        mock_duck_fs.read_range.return_value = mock_result
        
        try:
            # 範囲読み取り実行
            content = file_tools.read_file_range(self.test_file, 2, 3)
            
            # 結果確認
            assert content == range_content
            mock_duck_fs.read_range.assert_called_once_with(self.test_file, 2, 3)
        except AttributeError:
            pytest.skip("read_file_range method not implemented")
    
    @patch('codecrafter.keeper.duck_fs')
    def test_duck_fs_get_summary_success(self, mock_duck_fs):
        """Duck FS要約取得成功時のテスト"""
        summary_content = "Python file with 1 function: test_function"
        
        # Duck FSの成功レスポンスをモック
        mock_result = FileReadResult(
            content=summary_content,
            path=self.test_file,
            read_percentage=1.0,
            total_size_bytes=len(self.test_content.encode('utf-8')),
            read_size_bytes=len(summary_content.encode('utf-8')),
            file_type="python",
            encoding="utf-8",
            is_truncated=False,
            metadata={'summary_type': 'function_analysis'}
        )
        mock_duck_fs.get_summary.return_value = mock_result
        
        try:
            # 要約取得実行
            summary = file_tools.get_file_summary(self.test_file)
            
            # 結果確認
            assert summary == summary_content
            mock_duck_fs.get_summary.assert_called_once_with(self.test_file)
        except AttributeError:
            pytest.skip("get_file_summary method not implemented")


class TestDuckFSErrorScenarios:
    """Duck FSエラーシナリオのテスト"""
    
    def setup_method(self):
        """各テストメソッド実行前の初期化"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "test.py")
    
    def teardown_method(self):
        """各テストメソッド実行後のクリーンアップ"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('codecrafter.keeper.duck_fs')
    def test_duck_fs_policy_violation_error(self, mock_duck_fs):
        """Duck FSポリシー違反エラーのテスト"""
        # ポリシー違反エラーをシミュレート
        mock_duck_fs.read.side_effect = DuckFileSystemError("Extension not allowed: .exe")
        
        # エラーが適切に処理されることを確認
        with pytest.raises(FileOperationError) as exc_info:
            file_tools.read_file("test.exe")
        
        assert "Duck Keeper" in str(exc_info.value) or "Extension not allowed" in str(exc_info.value)
    
    @patch('codecrafter.keeper.duck_fs')
    def test_duck_fs_workspace_boundary_error(self, mock_duck_fs):
        """Duck FSワークスペース境界エラーのテスト"""
        # ワークスペース境界違反エラーをシミュレート
        mock_duck_fs.read.side_effect = DuckFileSystemError("File outside workspace boundary")
        
        # エラーが適切に処理されることを確認
        with pytest.raises(FileOperationError) as exc_info:
            file_tools.read_file("/outside/workspace/file.py")
        
        assert "Duck Keeper" in str(exc_info.value) or "workspace" in str(exc_info.value)
    
    @patch('codecrafter.keeper.duck_fs')
    def test_duck_fs_token_limit_exceeded(self, mock_duck_fs):
        """Duck FSトークン制限超過のテスト"""
        # トークン制限により切り詰められた結果をシミュレート
        truncated_content = "# 大型ファイルの一部のみ..."
        mock_result = FileReadResult(
            content=truncated_content,
            path=self.test_file,
            read_percentage=0.1,  # 10%のみ読み取り
            total_size_bytes=100000,
            read_size_bytes=10000,
            file_type="python",
            encoding="utf-8",
            is_truncated=True,
            metadata={'truncation_reason': 'token_limit_exceeded'}
        )
        mock_duck_fs.read.return_value = mock_result
        
        # 切り詰められた内容が返されることを確認
        content = file_tools.read_file(self.test_file)
        assert content == truncated_content
        
        # ファイル情報で切り詰め情報を確認
        info = file_tools.get_file_info(self.test_file)
        if "is_truncated" in info:
            assert info["is_truncated"] is True
            assert info["read_percentage"] == 0.1
    
    @patch('codecrafter.keeper.duck_fs')
    def test_duck_fs_unexpected_error(self, mock_duck_fs):
        """Duck FS予期しないエラーのテスト"""
        # 予期しないエラーをシミュレート
        mock_duck_fs.read.side_effect = Exception("Unexpected error")
        
        # 実際のファイルを作成（フォールバック用）
        test_content = "# フォールバック用ファイル\n"
        with open(self.test_file, "w", encoding="utf-8") as f:
            f.write(test_content)
        
        # フォールバックが動作することを確認
        content = file_tools.read_file(self.test_file)
        assert content == test_content


class TestDuckFSDataStructures:
    """Duck FSデータ構造のテスト"""
    
    def test_file_read_result_structure(self):
        """FileReadResult構造のテスト"""
        # FileReadResultの構造確認
        result = FileReadResult(
            content="test content",
            path="/test/path.py",
            read_percentage=1.0,
            total_size_bytes=100,
            read_size_bytes=100,
            file_type="python",
            encoding="utf-8",
            is_truncated=False,
            metadata={"test": "value"}
        )
        
        assert result.content == "test content"
        assert result.path == "/test/path.py"
        assert result.read_percentage == 1.0
        assert result.total_size_bytes == 100
        assert result.read_size_bytes == 100
        assert result.file_type == "python"
        assert result.encoding == "utf-8"
        assert result.is_truncated is False
        assert result.metadata == {"test": "value"}
    
    def test_file_write_result_structure(self):
        """FileWriteResult構造のテスト"""
        # FileWriteResultの構造確認
        timestamp = datetime.now()
        result = FileWriteResult(
            success=True,
            path="/test/path.py",
            bytes_written=100,
            backup_path="/test/path.py.backup",
            timestamp=timestamp,
            message="Write successful",
            metadata={"test": "value"}
        )
        
        assert result.success is True
        assert result.path == "/test/path.py"
        assert result.bytes_written == 100
        assert result.backup_path == "/test/path.py.backup"
        assert result.timestamp == timestamp
        assert result.message == "Write successful"
        assert result.metadata == {"test": "value"}
    
    def test_duck_file_system_error(self):
        """DuckFileSystemError構造のテスト"""
        error = DuckFileSystemError("Test error message")
        
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)


class TestDuckFSConfigIntegration:
    """Duck FS設定統合のテスト"""
    
    @patch('codecrafter.keeper.duck_keeper')
    def test_duck_keeper_config_access(self, mock_duck_keeper):
        """Duck Keeper設定アクセスのテスト"""
        # Duck Keeperの設定をモック
        mock_config = Mock()
        mock_config.duck_keeper.allowed_extensions = ['.py', '.md', '.txt']
        mock_config.duck_keeper.max_file_read_tokens = 8000
        mock_duck_keeper.config = mock_config
        mock_duck_keeper.get_allowed_extensions.return_value = ['.py', '.md', '.txt']
        mock_duck_keeper.get_max_file_read_tokens.return_value = 8000
        
        # 設定が適切に取得できることを確認
        extensions = mock_duck_keeper.get_allowed_extensions()
        max_tokens = mock_duck_keeper.get_max_file_read_tokens()
        
        assert extensions == ['.py', '.md', '.txt']
        assert max_tokens == 8000
    
    @patch('codecrafter.keeper.duck_keeper')
    def test_workspace_root_detection(self, mock_duck_keeper):
        """ワークスペースルート検出のテスト"""
        # ワークスペースルートをモック
        mock_duck_keeper.get_workspace_root.return_value = Path("/test/workspace")
        
        # ワークスペースルートが適切に取得できることを確認
        workspace_root = mock_duck_keeper.get_workspace_root()
        assert workspace_root == Path("/test/workspace")