#!/usr/bin/env python3
"""
設定管理 - 設定ファイルの読み込みと管理

codecrafterから分離し、companion内で完結するように調整
"""

import os
import yaml
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass, field


@dataclass
class Config:
    """設定データクラス"""
    # 基本設定
    app_name: str = "DuckFlow Companion"
    version: str = "4.0.0"
    debug: bool = False
    
    # UI設定
    ui_language: str = "ja"
    ui_theme: str = "default"
    show_timestamps: bool = True
    
    # システム設定
    max_conversation_history: int = 100
    max_file_size_mb: int = 10
    timeout_seconds: int = 300
    
    # 承認システム設定
    approval_mode: str = "standard"
    auto_approval_threshold: str = "low"
    approval_timeout: int = 300
    
    # 承認設定（詳細）
    approval: Dict[str, Any] = field(default_factory=lambda: {
        'mode': 'standard',
        'timeout_seconds': 30,
        'show_preview': True,
        'max_preview_length': 200,
        'ui': {
            'non_interactive': False,
            'auto_approve_low': False,
            'auto_approve_high': False
        }
    })
    
    # ファイル操作設定
    work_directory: str = "./work"
    allowed_extensions: list = field(default_factory=lambda: ['.py', '.md', '.txt', '.json', '.yaml'])
    backup_enabled: bool = True
    
    # LLM設定
    llm_provider: str = "mock"
    llm_api_key: str = ""
    llm_model: str = "gpt-4"
    llm_temperature: float = 0.7
    llm_max_retries: int = 3
    llm_timeout_seconds: int = 30
    
    # ログ設定
    log_level: str = "INFO"
    log_file: str = "./logs/duckflow.log"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Phase 4: 健全性・統計ログ設定
    health_logging_enabled: bool = False
    health_logging_interval: int = 60  # 秒
    gate_auto_stats: bool = False
    
    # セキュリティ設定
    enable_sandbox: bool = True
    restrict_file_access: bool = True
    allowed_directories: list = field(default_factory=lambda: ["./work", "./temp"])
    
    def to_dict(self) -> Dict[str, Any]:
        """設定を辞書形式で取得"""
        return {
            'app_name': self.app_name,
            'version': self.version,
            'debug': self.debug,
            'ui_language': self.ui_language,
            'ui_theme': self.ui_theme,
            'show_timestamps': self.show_timestamps,
            'max_conversation_history': self.max_conversation_history,
            'max_file_size_mb': self.max_file_size_mb,
            'timeout_seconds': self.timeout_seconds,
            'approval_mode': self.approval_mode,
            'auto_approval_threshold': self.auto_approval_threshold,
            'approval_timeout': self.approval_timeout,
            'approval': self.approval,
            'work_directory': self.work_directory,
            'allowed_extensions': self.allowed_extensions,
            'backup_enabled': self.backup_enabled,
            'llm_provider': self.llm_provider,
            'llm_api_key': self.llm_api_key,
            'llm_model': self.llm_model,
            'llm_temperature': self.llm_temperature,
            'llm_max_retries': self.llm_max_retries,
            'llm_timeout_seconds': self.llm_timeout_seconds,
            'log_level': self.log_level,
            'log_file': self.log_file,
            'log_format': self.log_format,
            'health_logging_enabled': self.health_logging_enabled,
            'health_logging_interval': self.health_logging_interval,
            'gate_auto_stats': self.gate_auto_stats,
            'enable_sandbox': self.enable_sandbox,
            'restrict_file_access': self.restrict_file_access,
            'allowed_directories': self.allowed_directories
        }
    
    def update_from_dict(self, config_dict: Dict[str, Any]):
        """辞書から設定を更新"""
        for key, value in config_dict.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def validate(self) -> bool:
        """設定の妥当性を検証"""
        try:
            # 必須項目のチェック
            if not self.app_name or not self.version:
                return False
            
            # 数値項目の範囲チェック
            if self.max_conversation_history < 1:
                return False
            
            if self.max_file_size_mb < 1:
                return False
            
            if self.timeout_seconds < 1:
                return False
            
            if self.llm_temperature < 0.0 or self.llm_temperature > 2.0:
                return False
            
            # ディレクトリの存在チェック
            work_dir = Path(self.work_directory)
            if not work_dir.exists():
                work_dir.mkdir(parents=True, exist_ok=True)
            
            return True
            
        except Exception:
            return False


class ConfigManager:
    """設定管理クラス"""
    
    def __init__(self, config_dir: str = "./config"):
        self.logger = logging.getLogger(__name__)
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # 設定ファイルのパス
        self.config_file = self.config_dir / "config.yaml"
        self.backup_file = self.config_dir / "config.backup.yaml"
        
        # デフォルト設定
        self.default_config = Config()
        
        # 現在の設定
        self.current_config = Config()
        
        # 設定の読み込み
        self._load_config()
        
        self.logger.info("ConfigManager初期化完了")
    
    def _load_config(self):
        """設定ファイルを読み込み"""
        try:
            if self.config_file.exists():
                # メイン設定ファイルを読み込み
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f)
                
                if config_data:
                    self.current_config.update_from_dict(config_data)
                    self.logger.info(f"設定ファイル読み込み完了: {self.config_file}")
                else:
                    self.logger.warning("設定ファイルが空です。デフォルト設定を使用")
                    self.current_config = Config()
            else:
                # 設定ファイルが存在しない場合、デフォルト設定で作成
                self.logger.info("設定ファイルが存在しません。デフォルト設定で作成")
                self._create_default_config()
                
        except Exception as e:
            self.logger.error(f"設定ファイル読み込みエラー: {e}")
            self.logger.info("デフォルト設定を使用")
            self.current_config = Config()
    
    def _create_default_config(self):
        """デフォルト設定ファイルを作成"""
        try:
            # 現在の設定を保存
            self.save_config()
            self.logger.info(f"デフォルト設定ファイルを作成: {self.config_file}")
            
        except Exception as e:
            self.logger.error(f"デフォルト設定ファイル作成エラー: {e}")
    
    def save_config(self, backup: bool = True):
        """設定をファイルに保存"""
        try:
            # バックアップを作成
            if backup and self.config_file.exists():
                import shutil
                shutil.copy2(self.config_file, self.backup_file)
                self.logger.debug(f"設定ファイルをバックアップ: {self.backup_file}")
            
            # 設定を保存
            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.dump(self.current_config.to_dict(), f, default_flow_style=False, 
                          allow_unicode=True, indent=2)
            
            self.logger.info(f"設定ファイルを保存: {self.config_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"設定ファイル保存エラー: {e}")
            return False
    
    def load_config(self) -> Config:
        """設定を読み込み"""
        return self.current_config
    
    def get_config(self) -> Config:
        """現在の設定を取得"""
        return self.current_config
    
    def update_config(self, updates: Dict[str, Any], save: bool = True) -> bool:
        """設定を更新"""
        try:
            # 設定を更新
            self.current_config.update_from_dict(updates)
            
            # 妥当性チェック
            if not self.current_config.validate():
                self.logger.error("設定の妥当性チェックに失敗")
                return False
            
            # ファイルに保存
            if save:
                self.save_config()
            
            self.logger.info("設定を更新しました")
            return True
            
        except Exception as e:
            self.logger.error(f"設定更新エラー: {e}")
            return False
    
    def reset_to_defaults(self) -> bool:
        """設定をデフォルトにリセット"""
        try:
            self.current_config = Config()
            self.save_config()
            self.logger.info("設定をデフォルトにリセットしました")
            return True
            
        except Exception as e:
            self.logger.error(f"設定リセットエラー: {e}")
            return False
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """特定の設定値を取得"""
        try:
            return getattr(self.current_config, key, default)
        except AttributeError:
            return default
    
    def set_setting(self, key: str, value: Any, save: bool = True) -> bool:
        """特定の設定値を設定"""
        try:
            if hasattr(self.current_config, key):
                setattr(self.current_config, key, value)
                
                if save:
                    self.save_config()
                
                self.logger.info(f"設定を更新: {key} = {value}")
                return True
            else:
                self.logger.warning(f"設定キーが存在しません: {key}")
                return False
                
        except Exception as e:
            self.logger.error(f"設定値設定エラー: {e}")
            return False
    
    def export_config(self, format: str = "yaml") -> str:
        """設定をエクスポート"""
        try:
            if format.lower() == "json":
                return json.dumps(self.current_config.to_dict(), indent=2, ensure_ascii=False)
            else:
                return yaml.dump(self.current_config.to_dict(), default_flow_style=False, 
                               allow_unicode=True, indent=2)
                
        except Exception as e:
            self.logger.error(f"設定エクスポートエラー: {e}")
            return ""
    
    def import_config(self, config_data: str, format: str = "yaml") -> bool:
        """設定をインポート"""
        try:
            if format.lower() == "json":
                data = json.loads(config_data)
            else:
                data = yaml.safe_load(config_data)
            
            if data and isinstance(data, dict):
                self.current_config.update_from_dict(data)
                
                if self.current_config.validate():
                    self.save_config()
                    self.logger.info("設定をインポートしました")
                    return True
                else:
                    self.logger.error("インポートされた設定の妥当性チェックに失敗")
                    return False
            else:
                self.logger.error("インポートされた設定データが無効です")
                return False
                
        except Exception as e:
            self.logger.error(f"設定インポートエラー: {e}")
            return False
    
    def validate_config(self) -> Dict[str, Any]:
        """設定の妥当性を検証"""
        validation_result = {
            'valid': False,
            'errors': [],
            'warnings': [],
            'recommendations': []
        }
        
        try:
            # 基本検証
            if not self.current_config.app_name:
                validation_result['errors'].append("アプリ名が設定されていません")
            
            if not self.current_config.version:
                validation_result['errors'].append("バージョンが設定されていません")
            
            # 数値検証
            if self.current_config.max_conversation_history < 10:
                validation_result['warnings'].append("会話履歴の最大数が少なすぎます（推奨: 50以上）")
            
            if self.current_config.max_file_size_mb > 100:
                validation_result['warnings'].append("ファイルサイズ制限が大きすぎます（推奨: 50MB以下）")
            
            # ディレクトリ検証
            work_dir = Path(self.current_config.work_directory)
            if not work_dir.exists():
                validation_result['warnings'].append("作業ディレクトリが存在しません")
            
            # セキュリティ検証
            if not self.current_config.restrict_file_access:
                validation_result['warnings'].append("ファイルアクセス制限が無効です")
            
            # エラーがない場合は有効
            validation_result['valid'] = len(validation_result['errors']) == 0
            
            # 推奨事項
            if validation_result['valid']:
                validation_result['recommendations'].append("設定は正常です")
            
            return validation_result
            
        except Exception as e:
            validation_result['errors'].append(f"検証処理エラー: {e}")
            return validation_result
    
    def get_config_summary(self) -> Dict[str, Any]:
        """設定のサマリーを取得"""
        return {
            'config_file': str(self.config_file),
            'backup_file': str(self.backup_file),
            'config_valid': self.current_config.validate(),
            'settings_count': len(self.current_config.to_dict()),
            'last_modified': self.config_file.stat().st_mtime if self.config_file.exists() else None
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """設定マネージャーの状態を辞書形式で取得"""
        return {
            'config_dir': str(self.config_dir),
            'config_file': str(self.config_file),
            'backup_file': str(self.backup_file),
            'current_config': self.current_config.to_dict(),
            'config_summary': self.get_config_summary(),
            'validation': self.validate_config()
        }


# グローバルインスタンス
config_manager = ConfigManager()


# 便利な関数
def load_config() -> Config:
    """設定を読み込み"""
    return config_manager.load_config()


def get_config() -> Config:
    """現在の設定を取得"""
    return config_manager.get_config()


def update_config(updates: Dict[str, Any], save: bool = True) -> bool:
    """設定を更新"""
    return config_manager.update_config(updates, save)


def get_setting(key: str, default: Any = None) -> Any:
    """特定の設定値を取得"""
    return config_manager.get_setting(key, default)


def set_setting(key: str, value: Any, save: bool = True) -> bool:
    """特定の設定値を設定"""
    return config_manager.set_setting(key, value, save)


def reset_config() -> bool:
    """設定をデフォルトにリセット"""
    return config_manager.reset_to_defaults()


def validate_config() -> Dict[str, Any]:
    """設定の妥当性を検証"""
    return config_manager.validate_config()


def export_config(format: str = "yaml") -> str:
    """設定をエクスポート"""
    return config_manager.export_config(format)


def import_config(config_data: str, format: str = "yaml") -> bool:
    """設定をインポート"""
    return config_manager.import_config(config_data, format)
