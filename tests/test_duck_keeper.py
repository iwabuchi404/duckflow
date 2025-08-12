"""
Duck Keeper Policy テストスイート

The Duck Keeperのアクセスポリシー管理システムの動作を検証
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch

from codecrafter.keeper.duck_policy import DuckKeeperPolicy, ValidationResult, PolicyViolation


class TestDuckKeeperPolicy:
    """DuckKeeperPolicyクラスのテスト"""
    
    def setup_method(self):
        """各テストメソッドの前に実行される設定"""
        # テスト用の一時ディレクトリを作成
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
        # テスト用設定をモック
        self.mock_config = {
            'duck_keeper': {
                'allowed_extensions': ['.py', '.md', '.txt'],
                'directory_blacklist': ['.git', 'node_modules', '__pycache__'],
                'enforce_workspace_boundary': True,
                'respect_gitignore': True,
                'max_file_read_tokens': 8000
            }
        }
    
    def _create_mock_config(self):
        """モック用のPydantic Configオブジェクトを作成"""
        from codecrafter.base.config import Config, DuckKeeperConfig, LLMConfig, SummaryLLMConfig
        
        duck_keeper_config = DuckKeeperConfig(**self.mock_config['duck_keeper'])
        llm_config = LLMConfig(provider="groq")  # 最低限必要なprovider設定
        summary_llm_config = SummaryLLMConfig(provider="groq")  # 要約LLM設定
        return Config(
            duck_keeper=duck_keeper_config, 
            llm=llm_config,
            summary_llm=summary_llm_config
        )
    
    def teardown_method(self):
        """各テストメソッドの後に実行されるクリーンアップ"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('codecrafter.keeper.duck_policy.config_manager.load_config')
    def test_initialization(self, mock_config_loader):
        """初期化処理のテスト"""
        mock_config_loader.return_value = self._create_mock_config()
        
        with patch.object(DuckKeeperPolicy, '_detect_workspace_root', return_value=self.temp_path):
            policy = DuckKeeperPolicy()
            
            assert policy.policy['allowed_extensions'] == self.mock_config['duck_keeper']['allowed_extensions']
            assert policy._workspace_root == self.temp_path
    
    @patch('codecrafter.keeper.duck_policy.config_manager.load_config')
    def test_workspace_boundary_validation_allowed(self, mock_config_loader):
        """ワークスペース境界内ファイルのアクセス許可テスト"""
        mock_config_loader.return_value = self._create_mock_config()
        
        # テスト用Pythonファイルを作成
        test_file = self.temp_path / "test.py"
        test_file.write_text("print('hello')")
        
        with patch.object(DuckKeeperPolicy, '_detect_workspace_root', return_value=self.temp_path):
            policy = DuckKeeperPolicy()
            result = policy.validate_file_access(str(test_file))
            
            assert result.is_allowed == True
            assert result.sanitized_path == str(test_file.resolve())
            assert len([v for v in result.violations if v.severity == "error"]) == 0
    
    @patch('codecrafter.keeper.duck_policy.config_manager.load_config')  
    def test_workspace_boundary_validation_denied(self, mock_config_loader):
        """ワークスペース境界外ファイルのアクセス拒否テスト"""
        mock_config_loader.return_value = self._create_mock_config()
        
        # ワークスペース外のファイルパス
        outside_file = Path("/tmp/outside.py")
        
        with patch.object(DuckKeeperPolicy, '_detect_workspace_root', return_value=self.temp_path):
            policy = DuckKeeperPolicy()
            result = policy.validate_file_access(str(outside_file))
            
            # ワークスペース境界違反があるはず
            boundary_violations = [v for v in result.violations 
                                 if v.violation_type == "workspace_boundary"]
            assert len(boundary_violations) > 0
            assert result.is_allowed == False
    
    @patch('codecrafter.keeper.duck_policy.config_manager.load_config')
    def test_extension_whitelist_allowed(self, mock_config_loader):
        """許可された拡張子のテスト"""
        mock_config_loader.return_value = self._create_mock_config()
        
        test_file = self.temp_path / "document.md"
        test_file.write_text("# テストドキュメント")
        
        with patch.object(DuckKeeperPolicy, '_detect_workspace_root', return_value=self.temp_path):
            policy = DuckKeeperPolicy()
            result = policy.validate_file_access(str(test_file))
            
            # 拡張子による拒否はないはず
            extension_violations = [v for v in result.violations 
                                  if v.violation_type == "extension_blocked"]
            assert len(extension_violations) == 0
    
    @patch('codecrafter.keeper.duck_policy.config_manager.load_config')
    def test_extension_whitelist_denied(self, mock_config_loader):
        """許可されていない拡張子のテスト"""
        mock_config_loader.return_value = self._create_mock_config()
        
        test_file = self.temp_path / "binary.exe"
        test_file.write_text("dummy binary")
        
        with patch.object(DuckKeeperPolicy, '_detect_workspace_root', return_value=self.temp_path):
            policy = DuckKeeperPolicy()
            result = policy.validate_file_access(str(test_file))
            
            # 拡張子による拒否があるはず
            extension_violations = [v for v in result.violations 
                                  if v.violation_type == "extension_blocked"]
            assert len(extension_violations) > 0
            assert result.is_allowed == False
    
    @patch('codecrafter.keeper.duck_policy.config_manager.load_config')
    def test_directory_blacklist_denied(self, mock_config_loader):
        """ブラックリストディレクトリの拒否テスト"""
        mock_config_loader.return_value = self._create_mock_config()
        
        # ブラックリストディレクトリにファイルを作成
        git_dir = self.temp_path / ".git"
        git_dir.mkdir()
        test_file = git_dir / "config"
        test_file.write_text("git config")
        
        with patch.object(DuckKeeperPolicy, '_detect_workspace_root', return_value=self.temp_path):
            policy = DuckKeeperPolicy()
            result = policy.validate_file_access(str(test_file))
            
            # ディレクトリブラックリスト違反があるはず
            directory_violations = [v for v in result.violations 
                                  if v.violation_type == "directory_blacklisted"]
            assert len(directory_violations) > 0
            assert result.is_allowed == False
    
    @patch('codecrafter.keeper.duck_policy.config_manager.load_config')
    def test_gitignore_patterns(self, mock_config_loader):
        """gitignoreパターンのテスト"""
        mock_config_loader.return_value = self._create_mock_config()
        
        # .gitignoreファイルを作成
        gitignore = self.temp_path / ".gitignore"
        gitignore.write_text("*.log\ntemp/")
        
        # gitignoreされるファイルを作成
        test_file = self.temp_path / "debug.log"
        test_file.write_text("log content")
        
        with patch.object(DuckKeeperPolicy, '_detect_workspace_root', return_value=self.temp_path):
            policy = DuckKeeperPolicy()
            result = policy.validate_file_access(str(test_file))
            
            # gitignore違反があるはず（警告レベル）
            gitignore_violations = [v for v in result.violations 
                                  if v.violation_type == "gitignored"]
            assert len(gitignore_violations) > 0
            assert gitignore_violations[0].severity == "warning"
            # 警告なのでアクセス自体は許可される
            assert result.is_allowed == True
    
    @patch('codecrafter.keeper.duck_policy.config_manager.load_config')
    def test_file_not_found_error(self, mock_config_loader):
        """存在しないファイルのエラーテスト"""
        mock_config_loader.return_value = self._create_mock_config()
        
        non_existent_file = self.temp_path / "not_exists.py"
        
        with patch.object(DuckKeeperPolicy, '_detect_workspace_root', return_value=self.temp_path):
            policy = DuckKeeperPolicy()
            result = policy.validate_file_access(str(non_existent_file), operation="read")
            
            # ファイル未発見エラーがあるはず
            not_found_violations = [v for v in result.violations 
                                  if v.violation_type == "file_not_found"]
            assert len(not_found_violations) > 0
            assert result.is_allowed == False
    
    @patch('codecrafter.keeper.duck_policy.config_manager.load_config')
    def test_bulk_validation(self, mock_config_loader):
        """一括検証のテスト"""
        mock_config_loader.return_value = self._create_mock_config()
        
        # テスト用ファイルを複数作成
        files = []
        for i in range(3):
            test_file = self.temp_path / f"test_{i}.py"
            test_file.write_text(f"# Test file {i}")
            files.append(str(test_file))
        
        with patch.object(DuckKeeperPolicy, '_detect_workspace_root', return_value=self.temp_path):
            policy = DuckKeeperPolicy()
            results = policy.is_safe_for_bulk_operations(files)
            
            assert len(results) == 3
            for file_path, result in results.items():
                assert isinstance(result, ValidationResult)
                assert result.is_allowed == True
    
    @patch('codecrafter.keeper.duck_policy.config_manager.load_config')
    def test_get_allowed_extensions(self, mock_config_loader):
        """許可拡張子取得のテスト"""
        mock_config_loader.return_value = self._create_mock_config()
        
        with patch.object(DuckKeeperPolicy, '_detect_workspace_root', return_value=self.temp_path):
            policy = DuckKeeperPolicy()
            extensions = policy.get_allowed_extensions()
            
            assert extensions == ['.py', '.md', '.txt']
    
    @patch('codecrafter.keeper.duck_policy.config_manager.load_config')
    def test_get_max_file_read_tokens(self, mock_config_loader):
        """最大読み取りトークン数取得のテスト"""
        mock_config_loader.return_value = self._create_mock_config()
        
        with patch.object(DuckKeeperPolicy, '_detect_workspace_root', return_value=self.temp_path):
            policy = DuckKeeperPolicy()
            max_tokens = policy.get_max_file_read_tokens()
            
            assert max_tokens == 8000
    
    @patch('codecrafter.keeper.duck_policy.config_manager.load_config')
    def test_get_workspace_root(self, mock_config_loader):
        """ワークスペースルート取得のテスト"""
        mock_config_loader.return_value = self._create_mock_config()
        
        with patch.object(DuckKeeperPolicy, '_detect_workspace_root', return_value=self.temp_path):
            policy = DuckKeeperPolicy()
            root = policy.get_workspace_root()
            
            assert root == self.temp_path


if __name__ == "__main__":
    pytest.main([__file__, "-v"])