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


class MemoryConfig(BaseModel):
    """記憶管理設定クラス (ステップ2c)"""
    
    short_term: Dict[str, Any] = Field(default_factory=dict, description="短期記憶設定")
    medium_term: Dict[str, Any] = Field(default_factory=dict, description="中期記憶設定")
    long_term: Dict[str, Any] = Field(default_factory=dict, description="長期記憶設定")


class ApprovalUIConfig(BaseModel):
    """承認UI設定クラス"""

    non_interactive: bool = Field(default=True, description="非対話UIの使用")
    auto_approve_low: bool = Field(default=True, description="低リスク自動承認")
    auto_approve_high: bool = Field(default=False, description="高リスク自動承認")
    auto_approve_all: bool = Field(default=False, description="全自動承認（非推奨）")


class ApprovalSettings(BaseModel):
    """承認システム設定クラス"""

    mode: str = Field(default="standard", description="承認モード strict|standard|trusted")
    timeout_seconds: int = Field(default=30, description="承認タイムアウト(秒)")
    show_preview: bool = Field(default=True, description="プレビュー表示")
    max_preview_length: int = Field(default=200, description="プレビュー最大長")
    ui: ApprovalUIConfig = Field(default_factory=ApprovalUIConfig, description="承認UI設定")


class SummaryLLMConfig(BaseModel):
    """要約用LLM設定クラス (ステップ2c)"""
    
    provider: str = Field(description="要約用LLMプロバイダー")
    openai: Dict[str, Any] = Field(default_factory=dict, description="OpenAI要約設定")
    anthropic: Dict[str, Any] = Field(default_factory=dict, description="Anthropic要約設定")
    groq: Dict[str, Any] = Field(default_factory=dict, description="Groq要約設定")
    openrouter: Dict[str, Any] = Field(default_factory=dict, description="OpenRouter要約設定")


class PromptSmithAIConfig(BaseModel):
    """PromptSmith AI役割設定クラス"""
    
    provider: str = Field(description="使用するLLMプロバイダー")
    model_settings: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="プロバイダー別モデル設定")


class PromptSmithEvaluationConfig(BaseModel):
    """PromptSmith評価設定クラス"""
    
    enabled: bool = Field(default=True, description="評価システム有効化")
    separate_ai_roles: bool = Field(default=True, description="役割別AI使用の有効化")
    timeout_seconds: int = Field(default=120, description="シナリオタイムアウト(秒)")
    max_retries: int = Field(default=3, description="失敗時の再試行回数")


class PromptSmithTargetAIConfig(BaseModel):
    """PromptSmith被評価AI設定クラス"""
    
    use_main_llm: bool = Field(default=True, description="メインLLM設定を使用するか")
    override_provider: Optional[str] = Field(default=None, description="プロバイダー上書き")
    override_model: Optional[str] = Field(default=None, description="モデル上書き")


class PromptSmithConfig(BaseModel):
    """PromptSmith設定クラス"""
    
    evaluation: PromptSmithEvaluationConfig = Field(default_factory=PromptSmithEvaluationConfig, description="評価設定")
    tester_ai: PromptSmithAIConfig = Field(default_factory=PromptSmithAIConfig, description="TesterAI設定")
    evaluator_ai: PromptSmithAIConfig = Field(default_factory=PromptSmithAIConfig, description="EvaluatorAI設定")
    optimizer_ai: PromptSmithAIConfig = Field(default_factory=PromptSmithAIConfig, description="OptimizerAI設定")
    conversation_analyzer: PromptSmithAIConfig = Field(default_factory=PromptSmithAIConfig, description="ConversationAnalyzer設定")
    target_ai: PromptSmithTargetAIConfig = Field(default_factory=PromptSmithTargetAIConfig, description="被評価AI設定")


class DuckKeeperScanSettings(BaseModel):
    """Duck Scan設定クラス"""
    
    use_ripgrep: bool = Field(default=True, description="ripgrep使用の有効化")
    max_search_results: int = Field(default=100, description="検索結果の最大数")
    max_scan_depth: int = Field(default=10, description="ディレクトリスキャンの最大深度")
    search_timeout: int = Field(default=30, description="キーワード検索のタイムアウト（秒）")


class DuckKeeperConfig(BaseModel):
    """Duck Keeper設定クラス"""
    
    allowed_extensions: List[str] = Field(default_factory=lambda: [".py", ".md", ".json", ".yaml", ".yml", ".txt", ".csv"], description="許可される拡張子")
    directory_blacklist: List[str] = Field(default_factory=lambda: [".git", ".idea", "node_modules", "__pycache__"], description="除外ディレクトリ")
    enforce_workspace_boundary: bool = Field(default=True, description="ワークスペース境界の強制")
    respect_gitignore: bool = Field(default=True, description=".gitignoreの尊重")
    max_file_read_tokens: int = Field(default=8000, description="ファイル読み取り最大トークン数")
    scan_settings: DuckKeeperScanSettings = Field(default_factory=DuckKeeperScanSettings, description="Duck Scan設定")


class DuckPacemakerDynamicLimits(BaseModel):
    """Duck Pacemaker動的制限設定クラス"""
    
    enabled: bool = Field(default=True, description="動的制限機能の有効化")
    min_loops: int = Field(default=3, description="最小ループ数")
    max_loops: int = Field(default=20, description="最大ループ数")


class DuckPacemakerTaskProfile(BaseModel):
    """Duck Pacemakerタスクプロファイル設定クラス"""
    
    base_loops: int = Field(description="ベースループ数")


class DuckPacemakerVitalsThreshold(BaseModel):
    """Duck Pacemakerバイタル閾値設定クラス"""
    
    low: float = Field(description="低下閾値")
    good: float = Field(description="良好閾値")


class DuckPacemakerVitalsThresholds(BaseModel):
    """Duck Pacemakerバイタル閾値設定クラス"""
    
    mood: DuckPacemakerVitalsThreshold = Field(description="プラン自信度閾値")
    focus: DuckPacemakerVitalsThreshold = Field(description="思考一貫性閾値")
    stamina: DuckPacemakerVitalsThreshold = Field(description="試行消耗度閾値")


class DuckPacemakerConfig(BaseModel):
    """Duck Pacemaker設定クラス"""
    
    dynamic_limits: DuckPacemakerDynamicLimits = Field(default_factory=DuckPacemakerDynamicLimits, description="動的制限設定")
    task_profiles: Dict[str, DuckPacemakerTaskProfile] = Field(default_factory=dict, description="タスクプロファイル別設定")
    vitals_thresholds: DuckPacemakerVitalsThresholds = Field(description="バイタル閾値設定")


class Config(BaseModel):
    """メイン設定クラス"""
    
    llm: LLMConfig = Field(default_factory=LLMConfig, description="LLM設定")
    ui: UIConfig = Field(default_factory=UIConfig, description="UI設定")
    tools: ToolsConfig = Field(default_factory=ToolsConfig, description="ツール設定")
    security: SecurityConfig = Field(default_factory=SecurityConfig, description="セキュリティ設定")
    logging: LoggingConfig = Field(default_factory=LoggingConfig, description="ログ設定")
    development: DevelopmentConfig = Field(default_factory=DevelopmentConfig, description="開発設定")
    memory: MemoryConfig = Field(default_factory=MemoryConfig, description="記憶管理設定")
    summary_llm: SummaryLLMConfig = Field(default_factory=SummaryLLMConfig, description="要約用LLM設定")
    approval: ApprovalSettings = Field(default_factory=ApprovalSettings, description="承認システム設定")
    promptsmith: Optional[PromptSmithConfig] = Field(default=None, description="PromptSmith設定")
    duck_keeper: DuckKeeperConfig = Field(default_factory=DuckKeeperConfig, description="Duck Keeper設定")
    duck_pacemaker: Optional[DuckPacemakerConfig] = Field(default=None, description="Duck Pacemaker設定")
    # Phase 1 settings (optional, ignored if absent)
    phase1: Optional[Dict[str, Any]] = Field(default=None, description="Phase 1 設定")


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
    
    def get_promptsmith_config(self) -> Optional[PromptSmithConfig]:
        """PromptSmith設定を取得"""
        config = self.load_config()
        return config.promptsmith
    
    def get_promptsmith_ai_config(self, ai_role: str) -> Optional[Dict[str, Any]]:
        """
        PromptSmith特定AI役割の設定を取得
        
        Args:
            ai_role: AI役割名 ("tester_ai", "evaluator_ai", "optimizer_ai", "conversation_analyzer", "target_ai")
            
        Returns:
            AI設定辞書またはNone
        """
        promptsmith_config = self.get_promptsmith_config()
        if not promptsmith_config:
            return None
        
        if not promptsmith_config.evaluation.separate_ai_roles:
            # 役割別設定が無効の場合はメインLLM設定を返す
            return self.get_llm_config()
        
        ai_config_mapping = {
            "tester_ai": promptsmith_config.tester_ai,
            "evaluator_ai": promptsmith_config.evaluator_ai,
            "optimizer_ai": promptsmith_config.optimizer_ai,
            "conversation_analyzer": promptsmith_config.conversation_analyzer,
        }
        
        if ai_role == "target_ai":
            target_config = promptsmith_config.target_ai
            if target_config.use_main_llm:
                config = self.get_llm_config()
                # 上書き設定があれば適用
                if target_config.override_provider:
                    provider_config = getattr(self.load_config().llm, target_config.override_provider, {})
                    if isinstance(provider_config, dict):
                        config = provider_config.copy()
                if target_config.override_model and isinstance(config, dict):
                    config["model"] = target_config.override_model
                return config
            else:
                # メインLLMを使用しない場合の処理（将来拡張用）
                return None
        
        ai_config = ai_config_mapping.get(ai_role)
        if not ai_config:
            return None
        
        # プロバイダー別設定を取得
        provider = ai_config.provider
        model_settings = ai_config.model_settings.get(provider, {})
        
        return model_settings
    
    def get_promptsmith_provider(self, ai_role: str) -> Optional[str]:
        """
        PromptSmith特定AI役割のプロバイダーを取得
        
        Args:
            ai_role: AI役割名
            
        Returns:
            プロバイダー名またはNone
        """
        promptsmith_config = self.get_promptsmith_config()
        if not promptsmith_config:
            return None
        
        if not promptsmith_config.evaluation.separate_ai_roles:
            # 役割別設定が無効の場合はメインプロバイダーを返す
            return self.load_config().llm.provider
        
        if ai_role == "target_ai":
            target_config = promptsmith_config.target_ai
            if target_config.use_main_llm:
                return target_config.override_provider or self.load_config().llm.provider
            else:
                return None
        
        ai_config_mapping = {
            "tester_ai": promptsmith_config.tester_ai,
            "evaluator_ai": promptsmith_config.evaluator_ai,
            "optimizer_ai": promptsmith_config.optimizer_ai,
            "conversation_analyzer": promptsmith_config.conversation_analyzer,
        }
        
        ai_config = ai_config_mapping.get(ai_role)
        return ai_config.provider if ai_config else None
    
    def get_duck_pacemaker_config(self) -> Optional[DuckPacemakerConfig]:
        """Duck Pacemaker設定を取得
        
        Returns:
            Duck Pacemaker設定またはNone
        """
        config = self.load_config()
        return config.duck_pacemaker

    def get_approval_settings(self) -> ApprovalSettings:
        """承認システム設定を取得"""
        config = self.load_config()
        return config.approval
    
    def get_duck_pacemaker_dynamic_limits(self) -> Dict[str, Any]:
        """Duck Pacemaker動的制限設定を取得
        
        Returns:
            動的制限設定辞書
        """
        duck_config = self.get_duck_pacemaker_config()
        if duck_config and duck_config.dynamic_limits:
            return {
                "enabled": duck_config.dynamic_limits.enabled,
                "min_loops": duck_config.dynamic_limits.min_loops,
                "max_loops": duck_config.dynamic_limits.max_loops
            }
        
        # デフォルト値
        return {
            "enabled": True,
            "min_loops": 3,
            "max_loops": 20
        }
    
    def get_duck_pacemaker_task_profile(self, task_profile: str) -> Optional[int]:
        """特定タスクプロファイルのベースループ数を取得
        
        Args:
            task_profile: タスクプロファイル名
            
        Returns:
            ベースループ数またはNone
        """
        duck_config = self.get_duck_pacemaker_config()
        if duck_config and duck_config.task_profiles:
            profile_config = duck_config.task_profiles.get(task_profile)
            if profile_config:
                return profile_config.base_loops
        
        return None
    
    def get_duck_pacemaker_vitals_thresholds(self) -> Dict[str, Dict[str, float]]:
        """Duck Pacemakerバイタル閾値設定を取得
        
        Returns:
            バイタル閾値設定辞書
        """
        duck_config = self.get_duck_pacemaker_config()
        if duck_config and duck_config.vitals_thresholds:
            return {
                "mood": {
                    "low": duck_config.vitals_thresholds.mood.low,
                    "good": duck_config.vitals_thresholds.mood.good
                },
                "focus": {
                    "low": duck_config.vitals_thresholds.focus.low,
                    "good": duck_config.vitals_thresholds.focus.good
                },
                "stamina": {
                    "low": duck_config.vitals_thresholds.stamina.low,
                    "good": duck_config.vitals_thresholds.stamina.good
                }
            }
        
        # デフォルト値
        return {
            "mood": {"low": 0.4, "good": 0.8},
            "focus": {"low": 0.4, "good": 0.8},
            "stamina": {"low": 0.3, "good": 0.8}
        }


# グローバルな設定管理インスタンス
config_manager = ConfigManager()
