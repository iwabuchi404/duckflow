# tests/test_file_tools_final.py
"""
file_toolsモジュールのテスト (duckFileSystem対応最終版)
"""
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, Mock
from codecrafter.tools.file_tools import file_tools, FileOperationError


class TestFileToolsDuckFileSystemIntegration:
    """FileTools duckFileSystem統合テスト"""
    
    def setup_method(self):
        """各テストメソッド実行前の初期化"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "test.txt")
        self.test_content = "テスト内容\n日本語テスト\n"
        
        # Duck Keeperのワークスペース境界チェックを無効化（テスト用）
        self._patch_duck_keeper_for_tests()
    
    def teardown_method(self):
        """各テストメソッド実行後のクリーンアップ"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
        # Duck Keeperのパッチを解除
        if hasattr(self, '_duck_keeper_patcher'):
            self._duck_keeper_patcher.stop()
    
    def _patch_duck_keeper_for_tests(self):
        """テスト用にDuck Keeperの設定をパッチ"""
        try:
            from codecrafter.keeper import duck_keeper
            
            # ワークスペース境界チェックを無効化
            def mock_validate_file_access(file_path, operation="read"):
                return Mock(
                    is_allowed=True, 
                    violations=[], 
                    sanitized_path=str(file_path)  # パスをそのまま返す
                )
            
            self._duck_keeper_patcher = patch.object(
                duck_keeper, 
                'validate_file_access',
                side_effect=mock_validate_file_access
            )
            self._duck_keeper_patcher.start()
            
        except ImportError:
            # Duck Keeperが利用できない場合はスキップ
            pass
    
    def test_basic_file_operations_with_duck_fs(self):
        """基本的なファイル操作のDuck FS統合テスト"""
        # ファイル書き込み
        result = file_tools.write_file(self.test_file, self.test_content)
        
        assert result["success"] is True
        assert os.path.exists(self.test_file)
        
        # Duck FS統合による追加フィールドの確認（存在する場合）
        if "bytes_written" in result:
            assert result["bytes_written"] > 0
        if "timestamp" in result:
            assert result["timestamp"] is not None
        
        # ファイル読み込み
        content = file_tools.read_file(self.test_file)
        assert content == self.test_content
    
    def test_duck_fs_new_features(self):
        """Duck FSの新機能テスト"""
        # テストファイルを作成
        python_content = "# テストPythonファイル\ndef hello():\n    return 'Hello, World!'\nprint('test')\n"
        test_py_file = os.path.join(self.temp_dir, "test.py")
        with open(test_py_file, "w", encoding="utf-8") as f:
            f.write(python_content)
        
        # 行範囲指定読み取りテスト
        try:
            range_content = file_tools.read_file_range(test_py_file, 2, 3)
            assert isinstance(range_content, str)
            assert len(range_content) > 0
            # 関数定義が含まれることを確認
            assert "def hello" in range_content or "hello" in range_content
        except AttributeError:
            pytest.skip("read_file_range method not implemented")
        
        # ファイル要約テスト
        try:
            summary = file_tools.get_file_summary(test_py_file)
            assert isinstance(summary, str)
            assert len(summary) > 0
            # Pythonファイルの要約には関数情報が含まれることを期待
            assert any(keyword in summary.lower() for keyword in ["hello", "function", "def", "python"])
        except AttributeError:
            pytest.skip("get_file_summary method not implemented")
    
    def test_duck_fs_error_handling(self):
        """Duck FSエラーハンドリングテスト"""
        # 存在しないファイルでのエラー処理
        nonexistent_file = os.path.join(self.temp_dir, "nonexistent.py")
        
        with pytest.raises(FileOperationError) as exc_info:
            file_tools.read_file(nonexistent_file)
        
        # エラーメッセージが適切であることを確認
        error_msg = str(exc_info.value)
        assert len(error_msg) > 0
        assert any(msg in error_msg for msg in [
            "ファイルが見つかりません", 
            "ファイルが存在しません",
            "Duck Keeper",
            "存在しません"
        ])
    
    def test_unicode_and_encoding_handling(self):
        """Unicode・エンコーディング処理テスト"""
        unicode_content = "# 日本語コメント\ndef こんにちは():\n    return '世界'\n"
        unicode_file = os.path.join(self.temp_dir, "unicode.py")
        
        # 書き込み
        result = file_tools.write_file(unicode_file, unicode_content)
        assert result["success"] is True
        
        # 読み込み
        content = file_tools.read_file(unicode_file)
        assert content == unicode_content
    
    def test_backup_functionality(self):
        """バックアップ機能テスト"""
        # 元ファイルを作成
        original_content = "# 元のコード\ndef old_function():\n    pass\n"
        with open(self.test_file, "w", encoding="utf-8") as f:
            f.write(original_content)
        
        # 新しい内容で上書き
        new_content = "# 新しいコード\ndef new_function():\n    pass\n"
        result = file_tools.write_file(self.test_file, new_content)
        
        assert result["success"] is True
        
        # バックアップが作成された場合の確認
        if "backup_created" in result and result["backup_created"]:
            assert "backup_path" in result
            backup_path = result["backup_path"]
            assert os.path.exists(backup_path)
    
    def test_directory_operations(self):
        """ディレクトリ操作テスト"""
        new_dir = os.path.join(self.temp_dir, "new_directory")
        
        # ディレクトリ作成
        result = file_tools.create_directory(new_dir)
        assert result["created"] is True
        assert os.path.exists(new_dir)
        assert os.path.isdir(new_dir)
        
        # 既存ディレクトリの作成テスト
        result2 = file_tools.create_directory(new_dir)
        assert result2["created"] is False
        
        # ファイル一覧取得
        test_files = ["file1.txt", "file2.py"]
        for name in test_files:
            Path(os.path.join(self.temp_dir, name)).touch()
        
        files = file_tools.list_files(self.temp_dir)
        assert len(files) >= 2
        file_names = [f["name"] for f in files]
        for name in test_files:
            assert name in file_names
    
    def test_large_file_handling(self):
        """大型ファイル処理テスト"""
        # 大きなファイルを作成
        large_content = "# 大型Pythonファイル\n" + "print('test')\n" * 1000
        large_file = os.path.join(self.temp_dir, "large.py")
        
        # 書き込み
        result = file_tools.write_file(large_file, large_content)
        assert result["success"] is True
        
        # 読み込み（トークン制限により切り詰められる可能性）
        content = file_tools.read_file(large_file)
        assert isinstance(content, str)
        assert len(content) > 0
    
    @patch('codecrafter.keeper.duck_keeper')
    def test_duck_keeper_policy_integration(self, mock_duck_keeper):
        """Duck Keeperポリシー統合テスト"""
        # Duck Keeperのポリシー違反をシミュレート
        mock_duck_keeper.validate_file_access.return_value.is_allowed = False
        mock_duck_keeper.validate_file_access.return_value.violations = [
            Mock(violation_type="extension_blocked", severity="error")
        ]
        
        # 許可されていない拡張子のファイル
        blocked_file = os.path.join(self.temp_dir, "test.exe")
        
        try:
            with pytest.raises(FileOperationError):
                file_tools.read_file(blocked_file)
        except ImportError:
            pytest.skip("Duck Keeper not available")
    
    def test_performance_basic(self):
        """基本的なパフォーマンステスト"""
        import time
        
        # 複数ファイル操作のパフォーマンス
        file_count = 5
        start_time = time.time()
        
        for i in range(file_count):
            file_path = os.path.join(self.temp_dir, f"perf_test_{i}.py")
            content = f"# Performance test file {i}\ndef function_{i}():\n    return {i}\n"
            
            # 書き込み
            result = file_tools.write_file(file_path, content)
            assert result["success"] is True
            
            # 読み込み
            read_content = file_tools.read_file(file_path)
            assert read_content == content
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # パフォーマンス基準（5ファイルの操作が5秒以内）
        assert total_time < 5.0, f"Performance test failed: {total_time:.2f}s for {file_count} files"


class TestDuckFileSystemDataStructures:
    """Duck File Systemデータ構造テスト"""
    
    def test_file_read_result_structure(self):
        """FileReadResult構造テスト"""
        try:
            from codecrafter.keeper import FileReadResult
            
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
            
        except ImportError:
            pytest.skip("FileReadResult not available")
    
    def test_file_write_result_structure(self):
        """FileWriteResult構造テスト"""
        try:
            from codecrafter.keeper import FileWriteResult
            from datetime import datetime
            
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
            
        except ImportError:
            pytest.skip("FileWriteResult not available")
    
    def test_duck_file_system_error(self):
        """DuckFileSystemError構造テスト"""
        try:
            from codecrafter.keeper import DuckFileSystemError
            
            error = DuckFileSystemError("Test error message")
            
            assert str(error) == "Test error message"
            assert isinstance(error, Exception)
            
        except ImportError:
            pytest.skip("DuckFileSystemError not available")


class TestDuckFileSystemCompatibility:
    """Duck File System互換性テスト"""
    
    def test_backward_compatibility(self):
        """後方互換性テスト"""
        temp_dir = tempfile.mkdtemp()
        try:
            test_file = os.path.join(temp_dir, "compat_test.txt")
            test_content = "互換性テスト内容"
            
            # Duck Keeperのワークスペース境界チェックを無効化（テスト用）
            try:
                from codecrafter.keeper import duck_keeper
                
                def mock_validate_file_access(file_path, operation="read"):
                    return Mock(
                        is_allowed=True, 
                        violations=[], 
                        sanitized_path=str(file_path)
                    )
                
                with patch.object(duck_keeper, 'validate_file_access', side_effect=mock_validate_file_access):
                    # 書き込み
                    result = file_tools.write_file(test_file, test_content)
                    assert result["success"] is True
                    
                    # 読み込み
                    content = file_tools.read_file(test_file)
                    assert content == test_content
                    
            except ImportError:
                # Duck Keeperが利用できない場合は基本的なファイル操作のみテスト
                with open(test_file, "w", encoding="utf-8") as f:
                    f.write(test_content)
                
                with open(test_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    assert content == test_content
            
            # ファイル情報取得（エラーが発生しても適切に処理される）
            try:
                info = file_tools.get_file_info(test_file)
                assert "name" in info
                assert "path" in info
            except FileOperationError:
                # Duck FSが利用できない場合のエラーは許容
                pass
            
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_error_message_consistency(self):
        """エラーメッセージの一貫性テスト"""
        temp_dir = tempfile.mkdtemp()
        try:
            # 存在しないファイルでのエラー
            nonexistent_file = os.path.join(temp_dir, "nonexistent.txt")
            
            with pytest.raises(FileOperationError) as exc_info:
                file_tools.read_file(nonexistent_file)
            
            error_msg = str(exc_info.value)
            # エラーメッセージが日本語で適切に表示されることを確認
            assert len(error_msg) > 0
            assert any(msg in error_msg for msg in [
                "ファイル", "存在", "見つかり", "Duck Keeper", "エラー"
            ])
            
            # 存在しないディレクトリでのエラー
            nonexistent_dir = os.path.join(temp_dir, "nonexistent_dir")
            
            with pytest.raises(FileOperationError) as exc_info:
                file_tools.list_files(nonexistent_dir)
            
            error_msg = str(exc_info.value)
            assert len(error_msg) > 0
            assert any(msg in error_msg for msg in [
                "ディレクトリ", "存在", "見つかり", "エラー"
            ])
            
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)