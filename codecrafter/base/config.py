"""
設定管理モジュール
"""
import os
from pathlib import Path
from typing import Any, Dict, Optional, List
import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field


class ConfigurationError(Exception):
    """設定エラー"""
    pass


class LLMConfig(BaseModel):
    """LLM設定クラス"""
    
    provider: str = Field(description="LLMプロバイダー")
    openai: Dict[str, Any] = Field(default_factory=dict, description="OpenAI設定")
    anthropic: Dict[str, Any] = Field(default_factory=dict, description="Anthropic設定")
    google: Dict[str, Any] = Field(default_factory=dict, description="Google設定")
    groq: Dict[str, Any] = Field(default_factory=dict, description="Groq設定")
    openrouter: Dict[str, Any] = Field(default_factory=dict, description="OpenRouter設定")


class UIConfig(BaseModel):
    """UI設定クラス"""
    
    type: str = Field(default="rich", description="UIタイプ")
    rich: Dict[str, Any] = Field(default_factory=dict, description="Rich設定")
    textual: Dict[str, Any] = Field(default_factory=dict, description="Textual設定")


class ToolsConfig(BaseModel):
    """ツール設定クラス"""
    
    file_operations: Dict[str, Any] = Field(default_factory=dict, description="ファイル操作設定")
    shell: Dict[str, Any] = Field(default_factory=dict, description="シェル実行設定")


class SecurityConfig(BaseModel):
    """セキュリティ設定クラス"""
    
    require_approval: Dict[str, bool] = Field(default_factory=dict, description="承認が必要な操作")
    forbidden_patterns: list = Field(default_factory=list, description="禁止パターン")


class LoggingConfig(BaseModel):
    """ログ設定クラス"""
    
    level: str = Field(default="INFO", description="ログレベル")
    file: str = Field(default="logs/codecrafter.log", description="ログファイルパス")
    max_size_mb: int = Field(default=50, description="ログファイル最大サイズ(MB)")
    backup_count: int = Field(default=5, description="バックアップファイル数")
    conversation: Dict[str, Any] = Field(default_factory=dict, description="対話ログ設定")


class DevelopmentConfig(BaseModel):
    """開発設定クラス"""
    
    debug: bool = Field(default=False, description="デバッグモード")
    reload_on_change: bool = Field(default=False, description="変更時リロード")
    profiling: bool = Field(default=False, description="プロファイリング")


class Config(BaseModel):
    """メイン設定クラス"""
    
    llm: LLMConfig = Field(default_factory=LLMConfig, description="LLM設定")
    ui: UIConfig = Field(default_factory=UIConfig, description="UI設定")
    tools: ToolsConfig = Field(default_factory=ToolsConfig, description="ツール設定")
    security: SecurityConfig = Field(default_factory=SecurityConfig, description="セキュリティ設定")
    logging: LoggingConfig = Field(default_factory=LoggingConfig, description="ログ設定")
    development: DevelopmentConfig = Field(default_factory=DevelopmentConfig, description="開発設定")


class ConfigManager:
    """設定管理クラス"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        設定管理クラスの初期化
        
        Args:
            config_path: 設定ファイルのパス
        """
        self.config_path = Path(config_path) if config_path else self._find_config_file()
        self.config: Optional[Config] = None
        self.env_loaded = False
    
    def _find_config_file(self) -> Path:
        """設定ファイルを検索"""
        # 現在のディレクトリから順番に上位ディレクトリを検索
        current_path = Path.cwd()
        
        for path in [current_path] + list(current_path.parents):
            config_file = path / "config" / "config.yaml"
            if config_file.exists():
                return config_file
        
        # デフォルトパス
        return Path("config/config.yaml")
    
    def load_env(self) -> None:
        """環境変数を読み込み"""
        if not self.env_loaded:
            # .envファイルを検索して読み込み
            env_file = self.config_path.parent.parent / ".env"
            if env_file.exists():
                load_dotenv(env_file)
            else:
                # カレントディレクトリの.envを試す
                load_dotenv()
            self.env_loaded = True
    
    def load_config(self) -> Config:
        """設定ファイルを読み込み"""
        if self.config is not None:
            return self.config
        
        # 環境変数を読み込み
        self.load_env()
        
        # 設定ファイルパスのリストを取得
        config_paths = self._get_config_paths()
        config_data = {}
        found_config = False
        
        # 複数の設定ファイルを順番に読み込み（後のファイルが前のファイルを上書き）
        for config_path in config_paths:
            if Path(config_path).exists():
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        file_config = yaml.safe_load(f) or {}
                        config_data = self._merge_configs(config_data, file_config)
                        found_config = True
                except yaml.YAMLError as e:
                    raise ConfigurationError(f"YAML解析エラー: {config_path} - {e}")
                except Exception as e:
                    raise ConfigurationError(f"設定ファイルの読み込みエラー: {config_path} - {e}")
        
        if not found_config:
            raise ConfigurationError(f"設定ファイルが見つかりません: {config_paths}")
        
        # 必須設定項目の確認
        if 'llm' not in config_data:
            raise ConfigurationError("必須設定が見つかりません: llm")
        
        # 設定の妥当性検証
        self._validate_config(config_data)
        
        # 環境変数での上書き
        self._apply_env_overrides(config_data)
        
        # 設定オブジェクトを作成
        try:
            self.config = Config(**config_data)
        except Exception as e:
            raise ConfigurationError(f"設定オブジェクトの作成に失敗しました: {e}")
        
        return self.config
    
    def _get_config_paths(self) -> List[str]:
        """設定ファイルのパス一覧を取得（優先度順）"""
        if self.config_path != Path("config/config.yaml"):
            # 明示的に指定されたパスを使用
            return [str(self.config_path)]
        
        # デフォルトの検索パス
        current_dir = Path.cwd()
        paths = []
        
        # プロジェクトの設定ファイル
        paths.append(str(current_dir / "config" / "config.yaml"))
        
        # ユーザー設定ファイル（存在すれば上書き用）
        user_config = current_dir / "config" / "user.yaml"
        if user_config.exists():
            paths.append(str(user_config))
        
        return paths
    
    def _merge_configs(self, base: dict, override: dict) -> dict:
        """設定をマージする"""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _validate_config(self, config_data: dict) -> None:
        """設定の妥当性を検証する"""
        # LLMプロバイダーの確認
        if 'llm' in config_data and 'provider' in config_data['llm']:
            provider = config_data['llm']['provider']
            valid_providers = ['openai', 'anthropic', 'google', 'groq', 'openrouter']
            if provider not in valid_providers:
                raise ConfigurationError(f"サポートされていないLLMプロバイダー: {provider}. 利用可能: {valid_providers}")
    
    def _apply_env_overrides(self, config_data: Dict[str, Any]) -> None:
        """環境変数による設定の上書き"""
        # デバッグモードの上書き
        if os.getenv('DUCKFLOW_DEBUG'):
            if 'development' not in config_data:
                config_data['development'] = {}
            config_data['development']['debug'] = os.getenv('DUCKFLOW_DEBUG', 'false').lower() == 'true'
        
        # LLMプロバイダーの上書き
        if os.getenv('DUCKFLOW_LLM_PROVIDER'):
            if 'llm' not in config_data:
                config_data['llm'] = {}
            config_data['llm']['provider'] = os.getenv('DUCKFLOW_LLM_PROVIDER')
    
    def get_api_key(self, provider: str) -> Optional[str]:
        """プロバイダーのAPIキーを取得"""
        self.load_env()
        
        key_mapping = {
            'openai': 'OPENAI_API_KEY',
            'anthropic': 'ANTHROPIC_API_KEY',
            'google': 'GOOGLE_AI_API_KEY',
            'groq': 'GROQ_API_KEY',
            'openrouter': 'OPENROUTER_API_KEY',
        }
        
        env_key = key_mapping.get(provider.lower())
        if env_key:
            return os.getenv(env_key)
        return None
    
    def get_llm_config(self) -> Dict[str, Any]:
        """LLM設定を取得"""
        config = self.load_config()
        provider = config.llm.provider
        
        # プロバイダー別の設定を取得
        provider_config = getattr(config.llm, provider, {})
        if isinstance(provider_config, dict):
            return provider_config
        return {}
    
    def is_debug_mode(self) -> bool:
        """デバッグモードかどうかを確認"""
        config = self.load_config()
        return config.development.debug
    
    def get_log_config(self) -> Dict[str, Any]:
        """ログ設定を取得"""
        config = self.load_config()
        return {
            'level': config.logging.level,
            'file': config.logging.file,
            'max_size_mb': config.logging.max_size_mb,
            'backup_count': config.logging.backup_count,
            'conversation': config.logging.conversation,
        }


# グローバルな設定管理インスタンス
config_manager = ConfigManager()