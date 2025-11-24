import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

class ConfigLoader:
    """
    Duckflow v4 Config Loader
    YAMLファイルから設定を読み込み、環境変数でオーバーライド可能にする。
    """
    _instance = None
    _config: Optional[Dict[str, Any]] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._config is None:
            self._load_config()
    
    def _load_config(self):
        """Load config from YAML file."""
        # Find duckflow.yaml in project root
        root_dir = Path(__file__).parent.parent.parent
        config_path = root_dir / "duckflow.yaml"
        
        if not config_path.exists():
            # Fallback to empty config, using defaults in get()
            self._config = {}
            return
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Warning: Failed to load config file: {e}")
            self._config = {}
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get config value by dot-separated key path.
        Example: get('llm.groq.model')
        
        Environment variables take precedence:
        - DUCKFLOW_LLM_GROQ_MODEL will override llm.groq.model
        """
        # Check environment variable first
        env_key = f"DUCKFLOW_{key_path.upper().replace('.', '_')}"
        env_value = os.getenv(env_key)
        if env_value is not None:
            return env_value
        
        # Navigate through config dict
        keys = key_path.split('.')
        value = self._config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value

# Global instance
config = ConfigLoader()
