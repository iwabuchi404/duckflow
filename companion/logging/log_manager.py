#!/usr/bin/env python3
"""
ログ管理 - ログの設定と管理

codecrafterから分離し、companion内で完結するように調整
"""

import os
import sys
import logging
import logging.handlers
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class LogConfig:
    """ログ設定データクラス"""
    # 基本設定
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format: str = "%Y-%m-%d %H:%M:%S"
    
    # ファイル出力設定
    file_enabled: bool = True
    file_path: str = "./logs/duckflow.log"
    file_max_size_mb: int = 10
    file_backup_count: int = 5
    
    # コンソール出力設定
    console_enabled: bool = True
    console_level: str = "INFO"
    
    # ログローテーション設定
    rotation_enabled: bool = True
    rotation_when: str = "midnight"
    rotation_interval: int = 1
    rotation_backup_count: int = 30
    
    # 特殊設定
    enable_debug_log: bool = False
    enable_performance_log: bool = False
    enable_security_log: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """設定を辞書形式で取得"""
        return {
            'level': self.level,
            'format': self.format,
            'date_format': self.date_format,
            'file_enabled': self.file_enabled,
            'file_path': self.file_path,
            'file_max_size_mb': self.file_max_size_mb,
            'file_backup_count': self.file_backup_count,
            'console_enabled': self.console_enabled,
            'console_level': self.console_level,
            'rotation_enabled': self.rotation_enabled,
            'rotation_when': self.rotation_when,
            'rotation_interval': self.rotation_interval,
            'rotation_backup_count': self.rotation_backup_count,
            'enable_debug_log': self.enable_debug_log,
            'enable_performance_log': self.enable_performance_log,
            'enable_security_log': self.enable_security_log
        }


class LogManager:
    """ログ管理クラス"""
    
    def __init__(self, config: Optional[LogConfig] = None):
        self.config = config or LogConfig()
        self.loggers: Dict[str, logging.Logger] = {}
        self.handlers: Dict[str, logging.Handler] = {}
        
        # ログディレクトリの作成
        self._setup_log_directory()
        
        # 基本ロガーの設定
        self._setup_root_logger()
        
        # 特殊ロガーの設定
        self._setup_specialized_loggers()
        
        self.logger = self.get_logger(__name__)
        self.logger.info("LogManager初期化完了")
    
    def _setup_log_directory(self):
        """ログディレクトリを設定"""
        try:
            log_dir = Path(self.config.file_path).parent
            log_dir.mkdir(parents=True, exist_ok=True)
            
        except Exception as e:
            print(f"ログディレクトリ作成エラー: {e}", file=sys.stderr)
    
    def _setup_root_logger(self):
        """ルートロガーを設定"""
        try:
            # ルートロガーのレベルを設定
            logging.getLogger().setLevel(self._get_log_level(self.config.level))
            
            # 既存のハンドラーをクリア
            root_logger = logging.getLogger()
            for handler in root_logger.handlers[:]:
                root_logger.removeHandler(handler)
            
            # フォーマッターを作成
            formatter = logging.Formatter(
                self.config.format,
                datefmt=self.config.date_format
            )
            
            # コンソールハンドラー
            if self.config.console_enabled:
                console_handler = logging.StreamHandler(sys.stdout)
                console_handler.setLevel(self._get_log_level(self.config.console_level))
                console_handler.setFormatter(formatter)
                logging.getLogger().addHandler(console_handler)
                self.handlers['console'] = console_handler
            
            # ファイルハンドラー
            if self.config.file_enabled:
                file_handler = self._create_file_handler(formatter)
                if file_handler:
                    logging.getLogger().addHandler(file_handler)
                    self.handlers['file'] = file_handler
            
        except Exception as e:
            print(f"ルートロガー設定エラー: {e}", file=sys.stderr)
    
    def _create_file_handler(self, formatter: logging.Formatter) -> Optional[logging.Handler]:
        """ファイルハンドラーを作成"""
        try:
            if self.config.rotation_enabled:
                # ローテーションハンドラー
                handler = logging.handlers.TimedRotatingFileHandler(
                    filename=self.config.file_path,
                    when=self.config.rotation_when,
                    interval=self.config.rotation_interval,
                    backupCount=self.config.rotation_backup_count,
                    encoding='utf-8'
                )
            else:
                # 通常のファイルハンドラー
                handler = logging.FileHandler(
                    filename=self.config.file_path,
                    encoding='utf-8'
                )
            
            handler.setLevel(self._get_log_level(self.config.level))
            handler.setFormatter(formatter)
            
            return handler
            
        except Exception as e:
            print(f"ファイルハンドラー作成エラー: {e}", file=sys.stderr)
            return None
    
    def _setup_specialized_loggers(self):
        """特殊ロガーを設定"""
        try:
            # デバッグロガー
            if self.config.enable_debug_log:
                self._setup_debug_logger()
            
            # パフォーマンスロガー
            if self.config.enable_performance_log:
                self._setup_performance_logger()
            
            # セキュリティロガー
            if self.config.enable_security_log:
                self._setup_security_logger()
                
        except Exception as e:
            print(f"特殊ロガー設定エラー: {e}", file=sys.stderr)
    
    def _setup_debug_logger(self):
        """デバッグロガーを設定"""
        try:
            debug_logger = logging.getLogger('debug')
            debug_logger.setLevel(logging.DEBUG)
            
            # デバッグ専用ファイルハンドラー
            debug_file = Path(self.config.file_path).parent / "debug.log"
            debug_handler = logging.FileHandler(debug_file, encoding='utf-8')
            debug_handler.setLevel(logging.DEBUG)
            
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
                datefmt=self.config.date_format
            )
            debug_handler.setFormatter(formatter)
            
            debug_logger.addHandler(debug_handler)
            self.loggers['debug'] = debug_logger
            self.handlers['debug_file'] = debug_handler
            
        except Exception as e:
            print(f"デバッグロガー設定エラー: {e}", file=sys.stderr)
    
    def _setup_performance_logger(self):
        """パフォーマンスロガーを設定"""
        try:
            perf_logger = logging.getLogger('performance')
            perf_logger.setLevel(logging.INFO)
            
            # パフォーマンス専用ファイルハンドラー
            perf_file = Path(self.config.file_path).parent / "performance.log"
            perf_handler = logging.FileHandler(perf_file, encoding='utf-8')
            perf_handler.setLevel(logging.INFO)
            
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt=self.config.date_format
            )
            perf_handler.setFormatter(formatter)
            
            perf_logger.addHandler(perf_handler)
            self.loggers['performance'] = perf_logger
            self.handlers['perf_file'] = perf_handler
            
        except Exception as e:
            print(f"パフォーマンスロガー設定エラー: {e}", file=sys.stderr)
    
    def _setup_security_logger(self):
        """セキュリティロガーを設定"""
        try:
            security_logger = logging.getLogger('security')
            security_logger.setLevel(logging.WARNING)
            
            # セキュリティ専用ファイルハンドラー
            security_file = Path(self.config.file_path).parent / "security.log"
            security_handler = logging.FileHandler(security_file, encoding='utf-8')
            security_handler.setLevel(logging.WARNING)
            
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt=self.config.date_format
            )
            security_handler.setFormatter(formatter)
            
            security_logger.addHandler(security_handler)
            self.loggers['security'] = security_logger
            self.handlers['security_file'] = security_handler
            
        except Exception as e:
            print(f"セキュリティロガー設定エラー: {e}", file=sys.stderr)
    
    def _get_log_level(self, level_str: str) -> int:
        """ログレベル文字列を数値に変換"""
        level_map = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }
        return level_map.get(level_str.upper(), logging.INFO)
    
    def get_logger(self, name: str, level: Optional[str] = None) -> logging.Logger:
        """ロガーを取得または作成"""
        if name in self.loggers:
            logger = self.loggers[name]
        else:
            logger = logging.getLogger(name)
            self.loggers[name] = logger
        
        # レベルを設定
        if level:
            logger.setLevel(self._get_log_level(level))
        
        return logger
    
    def get_debug_logger(self) -> logging.Logger:
        """デバッグロガーを取得"""
        return self.loggers.get('debug', logging.getLogger('debug'))
    
    def get_performance_logger(self) -> logging.Logger:
        """パフォーマンスロガーを取得"""
        return self.loggers.get('performance', logging.getLogger('performance'))
    
    def get_security_logger(self) -> logging.Logger:
        """セキュリティロガーを取得"""
        return self.loggers.get('security', logging.getLogger('security'))
    
    def set_log_level(self, name: str, level: str):
        """ロガーのレベルを設定"""
        try:
            if name in self.loggers:
                self.loggers[name].setLevel(self._get_log_level(level))
            else:
                logging.getLogger(name).setLevel(self._get_log_level(level))
                
        except Exception as e:
            print(f"ログレベル設定エラー: {e}", file=sys.stderr)
    
    def add_file_handler(self, name: str, file_path: str, level: str = "INFO", 
                        formatter: Optional[logging.Formatter] = None) -> bool:
        """ファイルハンドラーを追加"""
        try:
            # ファイルディレクトリを作成
            log_file = Path(file_path)
            log_file.parent.mkdir(parents=True, exist_ok=True)
            
            # ハンドラーを作成
            handler = logging.FileHandler(file_path, encoding='utf-8')
            handler.setLevel(self._get_log_level(level))
            
            # フォーマッターを設定
            if formatter:
                handler.setFormatter(formatter)
            else:
                formatter = logging.Formatter(
                    self.config.format,
                    datefmt=self.config.date_format
                )
                handler.setFormatter(formatter)
            
            # ロガーに追加
            logger = logging.getLogger(name)
            logger.addHandler(handler)
            
            # ハンドラーを記録
            self.handlers[f"{name}_file"] = handler
            
            return True
            
        except Exception as e:
            print(f"ファイルハンドラー追加エラー: {e}", file=sys.stderr)
            return False
    
    def remove_handler(self, name: str) -> bool:
        """ハンドラーを削除"""
        try:
            if name in self.handlers:
                handler = self.handlers[name]
                
                # すべてのロガーからハンドラーを削除
                for logger in self.loggers.values():
                    if handler in logger.handlers:
                        logger.removeHandler(handler)
                
                # ルートロガーからも削除
                root_logger = logging.getLogger()
                if handler in root_logger.handlers:
                    root_logger.removeHandler(handler)
                
                # ハンドラーを閉じる
                handler.close()
                
                # 記録から削除
                del self.handlers[name]
                
                return True
            else:
                return False
                
        except Exception as e:
            print(f"ハンドラー削除エラー: {e}", file=sys.stderr)
            return False
    
    def log_performance(self, operation: str, duration: float, metadata: Optional[Dict[str, Any]] = None):
        """パフォーマンスログを記録"""
        try:
            perf_logger = self.get_performance_logger()
            
            message = f"Operation: {operation}, Duration: {duration:.3f}s"
            if metadata:
                message += f", Metadata: {metadata}"
            
            perf_logger.info(message)
            
        except Exception as e:
            print(f"パフォーマンスログ記録エラー: {e}", file=sys.stderr)
    
    def log_security(self, event: str, level: str = "WARNING", details: Optional[Dict[str, Any]] = None):
        """セキュリティログを記録"""
        try:
            security_logger = self.get_security_logger()
            
            message = f"Security Event: {event}"
            if details:
                message += f", Details: {details}"
            
            if level.upper() == "CRITICAL":
                security_logger.critical(message)
            elif level.upper() == "ERROR":
                security_logger.error(message)
            elif level.upper() == "WARNING":
                security_logger.warning(message)
            else:
                security_logger.info(message)
                
        except Exception as e:
            print(f"セキュリティログ記録エラー: {e}", file=sys.stderr)
    
    def get_log_statistics(self) -> Dict[str, Any]:
        """ログ統計を取得"""
        try:
            stats = {
                'total_loggers': len(self.loggers),
                'total_handlers': len(self.handlers),
                'log_files': [],
                'handler_types': {}
            }
            
            # ログファイルの情報
            for name, handler in self.handlers.items():
                if isinstance(handler, logging.FileHandler):
                    stats['log_files'].append({
                        'name': name,
                        'path': handler.baseFilename,
                        'level': logging.getLevelName(handler.level)
                    })
                
                # ハンドラータイプの統計
                handler_type = type(handler).__name__
                stats['handler_types'][handler_type] = stats['handler_types'].get(handler_type, 0) + 1
            
            return stats
            
        except Exception as e:
            return {'error': str(e)}
    
    def cleanup(self):
        """リソースのクリーンアップ"""
        try:
            # すべてのハンドラーを閉じる
            for handler in self.handlers.values():
                try:
                    handler.close()
                except Exception:
                    pass
            
            # ハンドラーとロガーをクリア
            self.handlers.clear()
            self.loggers.clear()
            
        except Exception as e:
            print(f"ログマネージャークリーンアップエラー: {e}", file=sys.stderr)
    
    def to_dict(self) -> Dict[str, Any]:
        """ログマネージャーの状態を辞書形式で取得"""
        return {
            'config': self.config.to_dict(),
            'loggers_count': len(self.loggers),
            'handlers_count': len(self.handlers),
            'statistics': self.get_log_statistics()
        }


# グローバルインスタンス
log_manager = LogManager()


# 便利な関数
def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """ロガーを取得"""
    return log_manager.get_logger(name, level)


def setup_logging(config: LogConfig):
    """ログ設定をセットアップ"""
    global log_manager
    log_manager = LogManager(config)


def log_performance(operation: str, duration: float, metadata: Optional[Dict[str, Any]] = None):
    """パフォーマンスログを記録"""
    log_manager.log_performance(operation, duration, metadata)


def log_security(event: str, level: str = "WARNING", details: Optional[Dict[str, Any]] = None):
    """セキュリティログを記録"""
    log_manager.log_security(event, level, details)


def get_log_statistics() -> Dict[str, Any]:
    """ログ統計を取得"""
    return log_manager.get_log_statistics()


def cleanup_logging():
    """ログシステムをクリーンアップ"""
    log_manager.cleanup()
