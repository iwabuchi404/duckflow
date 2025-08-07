# tests/conftest.py
"""
pytest設定とフィクスチャ定義
"""
import pytest
import tempfile
import shutil
import os
from pathlib import Path
from unittest.mock import Mock, patch


@pytest.fixture
def temp_dir():
    """一時ディレクトリのフィクスチャ"""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def test_file_path(temp_dir):
    """テストファイルパスのフィクスチャ"""
    return os.path.join(temp_dir, "test_file.txt")


@pytest.fixture
def mock_llm_client():
    """モックLLMクライアントのフィクスチャ"""
    mock_client = Mock()
    mock_client.chat.return_value = "テスト応答"
    mock_client.get_provider_name.return_value = "test_provider"
    return mock_client


@pytest.fixture
def sample_config_data():
    """サンプル設定データのフィクスチャ"""
    return {
        "llm": {
            "provider": "openai",
            "openai": {
                "model": "gpt-4",
                "temperature": 0.1,
                "max_tokens": 4096
            },
            "anthropic": {
                "model": "claude-3-5-sonnet-20241022",
                "temperature": 0.1,
                "max_tokens": 4096
            }
        },
        "ui": {
            "type": "rich",
            "rich": {
                "theme": "monokai",
                "highlight": True
            }
        },
        "tools": {
            "file_operations": {
                "max_file_size_mb": 10,
                "backup_enabled": True
            }
        },
        "security": {
            "require_approval": {
                "file_write": True,
                "directory_creation": True
            }
        },
        "development": {
            "debug": False
        }
    }


@pytest.fixture
def mock_config_manager(sample_config_data):
    """モック設定マネージャーのフィクスチャ"""
    from codecrafter.base.config import ConfigManager
    
    with patch.object(ConfigManager, 'load_config') as mock_load:
        # 設定データをNamespaceオブジェクトに変換
        from types import SimpleNamespace
        
        def dict_to_namespace(d):
            if isinstance(d, dict):
                return SimpleNamespace(**{k: dict_to_namespace(v) for k, v in d.items()})
            return d
        
        config_obj = dict_to_namespace(sample_config_data)
        mock_load.return_value = config_obj
        
        manager = ConfigManager()
        manager.load_config()
        yield manager


@pytest.fixture(autouse=True)
def setup_test_environment():
    """テスト環境の自動セットアップ"""
    # テスト時に環境変数をクリア
    test_env_vars = [
        'DUCKFLOW_DEBUG',
        'OPENAI_API_KEY',
        'ANTHROPIC_API_KEY',
    ]
    
    original_env = {}
    for var in test_env_vars:
        if var in os.environ:
            original_env[var] = os.environ[var]
            del os.environ[var]
    
    yield
    
    # 環境変数を復元
    for var, value in original_env.items():
        os.environ[var] = value


@pytest.fixture
def captured_output():
    """出力キャプチャのフィクスチャ"""
    from io import StringIO
    import sys
    
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    
    stdout_capture = StringIO()
    stderr_capture = StringIO()
    
    sys.stdout = stdout_capture
    sys.stderr = stderr_capture
    
    yield {
        'stdout': stdout_capture,
        'stderr': stderr_capture
    }
    
    sys.stdout = old_stdout
    sys.stderr = old_stderr


# テスト設定
def pytest_configure(config):
    """pytest設定"""
    # カスタムマーカーの登録
    config.addinivalue_line(
        "markers", 
        "integration: mark test as integration test (requires external dependencies)"
    )
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow running test"
    )


# テスト収集の設定
def pytest_collection_modifyitems(config, items):
    """テスト項目の修正"""
    for item in items:
        # 統合テストの自動マーキング
        if "test_integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)
        
        # 時間のかかるテストの自動マーキング
        if any(keyword in item.name.lower() for keyword in ["large", "performance", "stress"]):
            item.add_marker(pytest.mark.slow)