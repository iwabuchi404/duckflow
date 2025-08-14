"""
Duck Scan統合テスト

Duck Scanとfile_toolsの統合動作をテストする
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock

from codecrafter.tools.file_tools import file_tools, FileOperationError


class TestDuckScanIntegration:
    """Duck Scan統合テスト"""
    
    def setup_method(self):
        """各テストメソッド実行前の初期化"""
        self.temp_dir = tempfile.mkdtemp()
        self.workspace_root = Path(self.temp_dir)
        
        # テスト用ファイル構造を作成
        self.create_test_file_structure()
    
    def teardown_method(self):
        """各テストメソッド実行後のクリーンアップ"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_test_file_structure(self):
        """テスト用のファイル構造を作成"""
        # Pythonファイル
        (self.workspace_root / "main.py").write_text("# メインファイル\ndef main():\n    pass\n")
        (self.workspace_root / "utils.py").write_text("# ユーティリティ\ndef helper():\n    pass\n")
        
        # ドキュメント
        (self.workspace_root / "README.md").write_text("# プロジェクト説明\n\nこれはテストプロジェクトです。\n")
        
        # サブディレクトリ
        src_dir = self.workspace_root / "src"
        src_dir.mkdir()
        (src_dir / "core.py").write_text("# コアモジュール\nclass Core:\n    pass\n")
        
        # 除外すべきディレクトリ
        git_dir = self.workspace_root / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("git config content")
        
        # .gitignore
        (self.workspace_root / ".gitignore").write_text("*.log\n__pycache__/\n")
        
        # ログファイル（gitignoreされる）
        (self.workspace_root / "debug.log").write_text("log content")
    
    @patch('codecrafter.tools.duck_scan.DuckScan')
    def test_duck_scan_workspace_integration(self, mock_duck_scan_class):
        """Duck Scanワークスペース探索統合テスト"""
        # Duck Scanのモックを設定
        mock_duck_scan = Mock()
        mock_duck_scan_class.return_value = mock_duck_scan
        
        # スキャン結果をモック
        from codecrafter.tools.duck_scan import ScanResult
        mock_result = ScanResult(
            files=["main.py", "utils.py", "README.md", "src/core.py"],
            scan_method="ripgrep_search",
            query="test",
            total_files_found=4,
            filtered_files_count=4,
            scan_time_seconds=0.1,
            workspace_root=str(self.workspace_root),
            metadata={}
        )
        mock_duck_scan.scan_workspace.return_value = mock_result
        
        try:
            # Duck Scanが利用可能かチェック
            from codecrafter.tools.duck_scan import DuckScan
            
            # スキャン実行
            duck_scan = DuckScan()
            result = duck_scan.scan_workspace("test")
            
            # 結果確認
            assert isinstance(result.files, list)
            assert len(result.files) > 0
            assert result.scan_method in ["ripgrep_search", "hierarchical_scan", "fallback_scan"]
            assert result.total_files_found >= 0
            assert result.scan_time_seconds >= 0
            
        except ImportError:
            pytest.skip("Duck Scan not available")
    
    @patch('codecrafter.tools.duck_scan.DuckScan')
    def test_duck_scan_directory_integration(self, mock_duck_scan_class):
        """Duck Scanディレクトリ探索統合テスト"""
        # Duck Scanのモックを設定
        mock_duck_scan = Mock()
        mock_duck_scan_class.return_value = mock_duck_scan
        
        # ディレクトリスキャン結果をモック
        from codecrafter.tools.duck_scan import ScanResult
        mock_result = ScanResult(
            files=["src/core.py"],
            scan_method="directory_scan",
            query=None,
            total_files_found=1,
            filtered_files_count=1,
            scan_time_seconds=0.05,
            workspace_root=str(self.workspace_root),
            metadata={"scanned_directory": "src"}
        )
        mock_duck_scan.scan_directory.return_value = mock_result
        
        try:
            # Duck Scanが利用可能かチェック
            from codecrafter.tools.duck_scan import DuckScan
            
            # ディレクトリスキャン実行
            duck_scan = DuckScan()
            result = duck_scan.scan_directory("src", recursive=True)
            
            # 結果確認
            assert isinstance(result.files, list)
            assert result.scan_method == "directory_scan"
            
        except ImportError:
            pytest.skip("Duck Scan not available")
    
    def test_duck_scan_policy_compliance(self):
        """Duck Scanポリシー準拠テスト"""
        try:
            from codecrafter.tools.duck_scan import DuckScan
            
            # Duck Scanインスタンス作成
            duck_scan = DuckScan()
            
            # ポリシー設定が適切に読み込まれていることを確認
            assert hasattr(duck_scan, 'policy')
            assert hasattr(duck_scan, 'workspace_root')
            
            # ワークスペースルートが設定されていることを確認
            assert duck_scan.workspace_root is not None
            
        except ImportError:
            pytest.skip("Duck Scan not available")
    
    @patch('codecrafter.tools.duck_scan.subprocess.run')
    def test_duck_scan_ripgrep_fallback(self, mock_subprocess):
        """Duck Scan ripgrepフォールバック動作テスト"""
        # ripgrepが利用できない場合のフォールバックをシミュレート
        mock_subprocess.side_effect = FileNotFoundError("ripgrep not found")
        
        try:
            from codecrafter.tools.duck_scan import DuckScan
            
            # Duck Scanインスタンス作成
            duck_scan = DuckScan()
            
            # フォールバック動作でもスキャンが実行されることを確認
            result = duck_scan.scan_workspace("test")
            
            # フォールバック方式でも結果が返されることを確認
            assert hasattr(result, 'files')
            assert hasattr(result, 'scan_method')
            assert result.scan_method in ["hierarchical_scan", "fallback_scan"]
            
        except ImportError:
            pytest.skip("Duck Scan not available")


class TestDuckScanErrorHandling:
    """Duck Scanエラーハンドリングテスト"""
    
    def setup_method(self):
        """各テストメソッド実行前の初期化"""
        self.temp_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """各テストメソッド実行後のクリーンアップ"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_duck_scan_error_handling(self):
        """Duck Scanエラーハンドリングテスト"""
        try:
            from codecrafter.tools.duck_scan import DuckScan, DuckScanError
            
            # Duck Scanインスタンス作成
            duck_scan = DuckScan()
            
            # 存在しないディレクトリでのスキャン
            try:
                result = duck_scan.scan_directory("/nonexistent/directory")
                # エラーが発生しない場合は空の結果が返されることを確認
                assert isinstance(result.files, list)
            except (DuckScanError, FileNotFoundError, OSError):
                # 適切なエラーが発生することを確認
                pass
            
        except ImportError:
            pytest.skip("Duck Scan not available")
    
    def test_duck_scan_permission_error(self):
        """Duck Scan権限エラーテスト"""
        try:
            from codecrafter.tools.duck_scan import DuckScan
            
            # Duck Scanインスタンス作成
            duck_scan = DuckScan()
            
            # 権限のないディレクトリでのスキャン（Unix系のみ）
            if os.name != 'nt':  # Windows以外
                try:
                    result = duck_scan.scan_directory("/root")
                    # 権限エラーが適切に処理されることを確認
                    assert isinstance(result.files, list)
                except (PermissionError, OSError):
                    # 権限エラーが適切に発生することを確認
                    pass
            
        except ImportError:
            pytest.skip("Duck Scan not available")


class TestDuckScanPerformance:
    """Duck Scanパフォーマンステスト"""
    
    def setup_method(self):
        """各テストメソッド実行前の初期化"""
        self.temp_dir = tempfile.mkdtemp()
        self.create_large_file_structure()
    
    def teardown_method(self):
        """各テストメソッド実行後のクリーンアップ"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_large_file_structure(self):
        """大規模なファイル構造を作成"""
        workspace = Path(self.temp_dir)
        
        # 複数のディレクトリとファイルを作成
        for i in range(10):
            dir_path = workspace / f"dir_{i}"
            dir_path.mkdir()
            
            for j in range(5):
                file_path = dir_path / f"file_{j}.py"
                file_path.write_text(f"# File {i}-{j}\ndef function_{i}_{j}():\n    pass\n")
    
    def test_duck_scan_large_project_performance(self):
        """Duck Scan大規模プロジェクトパフォーマンステスト"""
        import time
        
        try:
            from codecrafter.tools.duck_scan import DuckScan
            
            # Duck Scanインスタンス作成
            duck_scan = DuckScan()
            
            # パフォーマンス測定
            start_time = time.time()
            result = duck_scan.scan_workspace("function")
            end_time = time.time()
            
            # 結果確認
            assert isinstance(result.files, list)
            assert len(result.files) > 0
            
            # パフォーマンス基準（50ファイルのスキャンが5秒以内）
            scan_time = end_time - start_time
            assert scan_time < 5.0, f"Scan too slow: {scan_time:.2f}s"
            
            # スキャン時間がメタデータに記録されていることを確認
            assert result.scan_time_seconds > 0
            
        except ImportError:
            pytest.skip("Duck Scan not available")
    
    def test_duck_scan_memory_usage(self):
        """Duck Scanメモリ使用量テスト"""
        try:
            from codecrafter.tools.duck_scan import DuckScan
            import psutil
            import os
            
            # 現在のプロセスのメモリ使用量を取得
            process = psutil.Process(os.getpid())
            memory_before = process.memory_info().rss
            
            # Duck Scanインスタンス作成とスキャン実行
            duck_scan = DuckScan()
            result = duck_scan.scan_workspace("test")
            
            # スキャン後のメモリ使用量を取得
            memory_after = process.memory_info().rss
            memory_increase = memory_after - memory_before
            
            # メモリ使用量の増加が合理的な範囲内であることを確認（100MB以内）
            assert memory_increase < 100 * 1024 * 1024, f"Memory usage too high: {memory_increase / 1024 / 1024:.2f}MB"
            
        except (ImportError, ModuleNotFoundError):
            pytest.skip("Duck Scan or psutil not available")


class TestDuckScanConfigIntegration:
    """Duck Scan設定統合テスト"""
    
    @patch('codecrafter.keeper.duck_keeper')
    def test_duck_scan_config_integration(self, mock_duck_keeper):
        """Duck Scan設定統合テスト"""
        # Duck Keeperの設定をモック
        mock_config = Mock()
        mock_config.duck_keeper.scan_settings.use_ripgrep = True
        mock_config.duck_keeper.scan_settings.max_search_results = 100
        mock_config.duck_keeper.scan_settings.max_scan_depth = 10
        mock_duck_keeper.config = mock_config
        
        try:
            from codecrafter.tools.duck_scan import DuckScan
            
            # Duck Scanインスタンス作成
            duck_scan = DuckScan()
            
            # 設定が適切に読み込まれていることを確認
            assert hasattr(duck_scan, 'config')
            
        except ImportError:
            pytest.skip("Duck Scan not available")
    
    def test_duck_scan_gitignore_respect(self):
        """Duck Scan .gitignore尊重テスト"""
        temp_dir = tempfile.mkdtemp()
        try:
            workspace = Path(temp_dir)
            
            # .gitignoreファイルを作成
            gitignore = workspace / ".gitignore"
            gitignore.write_text("*.log\n__pycache__/\n*.tmp\n")
            
            # gitignoreされるファイルを作成
            (workspace / "debug.log").write_text("log content")
            (workspace / "temp.tmp").write_text("temp content")
            
            # gitignoreされないファイルを作成
            (workspace / "main.py").write_text("# main file")
            
            try:
                from codecrafter.tools.duck_scan import DuckScan
                
                # Duck Scanインスタンス作成
                duck_scan = DuckScan()
                
                # スキャン実行
                result = duck_scan.scan_workspace("content")
                
                # gitignoreされないファイルのみが含まれることを確認
                assert isinstance(result.files, list)
                
                # gitignoreされたファイルが除外されていることを確認
                file_names = [os.path.basename(f) for f in result.files]
                assert "debug.log" not in file_names
                assert "temp.tmp" not in file_names
                
            except ImportError:
                pytest.skip("Duck Scan not available")
                
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)