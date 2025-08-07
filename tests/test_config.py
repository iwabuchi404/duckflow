# tests/test_config.py
"""
config管理モジュールのテスト
"""
import pytest
import tempfile
import os
import yaml
from unittest.mock import patch
from codecrafter.base.config import ConfigManager, ConfigurationError


class TestConfigManager:
    """ConfigManagerクラスのテスト"""
    
    def setup_method(self):
        """各テストメソッド実行前の初期化"""
        self.config_manager = ConfigManager()
        self.temp_dir = tempfile.mkdtemp()
        
        # テスト用設定ファイル
        self.test_config = {
            "llm": {
                "provider": "openai",
                "openai": {
                    "model": "gpt-4",
                    "temperature": 0.2,
                    "max_tokens": 2000
                }
            },
            "ui": {
                "type": "rich"
            },
            "development": {
                "debug": True
            }
        }
    
    def teardown_method(self):
        """各テストメソッド実行後のクリーンアップ"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_test_config_file(self, config_data=None):
        """テスト用設定ファイルを作成"""
        if config_data is None:
            config_data = self.test_config
        
        config_file = os.path.join(self.temp_dir, "test_config.yaml")
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, allow_unicode=True)
        return config_file
    
    def test_load_config_from_file(self):
        """ファイルから設定を読み込むテスト"""
        config_file = self.create_test_config_file()
        
        with patch.object(self.config_manager, '_get_config_paths', return_value=[config_file]):
            config = self.config_manager.load_config()
        
        assert config.llm.provider == "openai"
        assert config.llm.openai.model == "gpt-4"
        assert config.llm.openai.temperature == 0.2
        assert config.ui.type == "rich"
        assert config.development.debug is True
    
    def test_load_config_file_not_found(self):
        """設定ファイルが見つからない場合のテスト"""
        nonexistent_file = os.path.join(self.temp_dir, "nonexistent.yaml")
        
        with patch.object(self.config_manager, '_get_config_paths', return_value=[nonexistent_file]):
            with pytest.raises(ConfigurationError) as exc_info:
                self.config_manager.load_config()
        
        assert "設定ファイルが見つかりません" in str(exc_info.value)
    
    def test_load_invalid_yaml_config(self):
        """不正なYAMLファイルの読み込みテスト"""
        config_file = os.path.join(self.temp_dir, "invalid.yaml")
        with open(config_file, "w", encoding="utf-8") as f:
            f.write("invalid: yaml: content: [\n")  # 不正なYAML
        
        with patch.object(self.config_manager, '_get_config_paths', return_value=[config_file]):
            with pytest.raises(ConfigurationError) as exc_info:
                self.config_manager.load_config()
        
        assert "YAML解析エラー" in str(exc_info.value)
    
    def test_load_config_with_missing_required_fields(self):
        """必須フィールドが欠けている設定のテスト"""
        incomplete_config = {
            "ui": {
                "type": "rich"
            }
            # llmセクションが欠けている
        }
        config_file = self.create_test_config_file(incomplete_config)
        
        with patch.object(self.config_manager, '_get_config_paths', return_value=[config_file]):
            with pytest.raises(ConfigurationError) as exc_info:
                self.config_manager.load_config()
        
        assert "必須設定が見つかりません" in str(exc_info.value)
    
    def test_is_debug_mode(self):
        """デバッグモード判定のテスト"""
        # デバッグモードが有効な設定
        debug_config = self.test_config.copy()
        debug_config["development"]["debug"] = True
        config_file = self.create_test_config_file(debug_config)
        
        with patch.object(self.config_manager, '_get_config_paths', return_value=[config_file]):
            self.config_manager.load_config()
            assert self.config_manager.is_debug_mode() is True
        
        # デバッグモードが無効な設定
        no_debug_config = self.test_config.copy()
        no_debug_config["development"]["debug"] = False
        config_file = self.create_test_config_file(no_debug_config)
        
        with patch.object(self.config_manager, '_get_config_paths', return_value=[config_file]):
            self.config_manager.load_config()
            assert self.config_manager.is_debug_mode() is False
    
    def test_environment_variable_override(self):
        """環境変数による設定上書きのテスト"""
        config_file = self.create_test_config_file()
        
        with patch.dict(os.environ, {'DUCKFLOW_DEBUG': 'true'}):
            with patch.object(self.config_manager, '_get_config_paths', return_value=[config_file]):
                assert self.config_manager.is_debug_mode() is True
        
        with patch.dict(os.environ, {'DUCKFLOW_DEBUG': 'false'}):
            with patch.object(self.config_manager, '_get_config_paths', return_value=[config_file]):
                assert self.config_manager.is_debug_mode() is False
    
    def test_multiple_config_files_priority(self):
        """複数設定ファイルの優先度テスト"""
        # 基本設定
        base_config = {
            "llm": {"provider": "openai"},
            "ui": {"type": "rich"},
            "development": {"debug": False}
        }
        base_file = self.create_test_config_file(base_config)
        
        # ユーザー設定（上書き）
        user_config = {
            "llm": {"provider": "anthropic"},
            "development": {"debug": True}
        }
        user_file = os.path.join(self.temp_dir, "user_config.yaml")
        with open(user_file, "w", encoding="utf-8") as f:
            yaml.dump(user_config, f)
        
        # 優先度: user_file > base_file
        with patch.object(self.config_manager, '_get_config_paths', return_value=[base_file, user_file]):
            config = self.config_manager.load_config()
        
        # user_configで上書きされた値
        assert config.llm.provider == "anthropic"
        assert config.development.debug is True
        
        # base_configから継承された値
        assert config.ui.type == "rich"
    
    def test_config_validation(self):
        """設定値の妥当性検証テスト"""
        # 無効なプロバイダー
        invalid_config = self.test_config.copy()
        invalid_config["llm"]["provider"] = "invalid_provider"
        config_file = self.create_test_config_file(invalid_config)
        
        with patch.object(self.config_manager, '_get_config_paths', return_value=[config_file]):
            with pytest.raises(ConfigurationError) as exc_info:
                self.config_manager.load_config()
        
        assert "サポートされていないLLMプロバイダー" in str(exc_info.value)
    
    def test_default_config_paths(self):
        """デフォルト設定ファイルパスのテスト"""
        paths = self.config_manager._get_config_paths()
        
        # 少なくとも1つの設定ファイルパスが返される
        assert len(paths) > 0
        
        # config/config.yamlが含まれている
        assert any("config.yaml" in path for path in paths)
    
    def test_nested_config_access(self):
        """ネストした設定項目へのアクセステスト"""
        config_file = self.create_test_config_file()
        
        with patch.object(self.config_manager, '_get_config_paths', return_value=[config_file]):
            config = self.config_manager.load_config()
        
        # ドット記法でのアクセス
        assert config.llm.openai.model == "gpt-4"
        assert config.llm.openai.temperature == 0.2
        assert config.llm.openai.max_tokens == 2000
    
    def test_config_with_japanese_content(self):
        """日本語を含む設定のテスト"""
        japanese_config = self.test_config.copy()
        japanese_config["ui"]["messages"] = {
            "welcome": "CodeCrafterへようこそ",
            "goodbye": "さようなら"
        }
        config_file = self.create_test_config_file(japanese_config)
        
        with patch.object(self.config_manager, '_get_config_paths', return_value=[config_file]):
            config = self.config_manager.load_config()
        
        assert config.ui.messages.welcome == "CodeCrafterへようこそ"
        assert config.ui.messages.goodbye == "さようなら"