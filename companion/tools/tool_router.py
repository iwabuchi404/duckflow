"""
ToolRouter - Phase 3: 基本的なツール統合
DuckFlowのツールルーティングシステムを実装する
"""

import os
import logging
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from datetime import datetime

from ..file_ops import SimpleFileOps


class ToolRouter:
    """基本的なツール統合とルーティング"""
    
    def __init__(self, work_dir: str = "./work"):
        self.logger = logging.getLogger(__name__)
        self.work_dir = Path(work_dir)
        self.file_ops = SimpleFileOps()
        
        # サポートされている操作
        self.supported_operations = {
            "file": ["read", "write", "create", "delete", "list", "exists"],
            "system": ["info", "status", "health"],
            "conversation": ["history", "summary", "export"]
        }
        
        # 操作履歴
        self.operation_history = []
        self.max_history = 20
        
        # 安全性設定
        self.safety_config = {
            "max_file_size": 10 * 1024 * 1024,  # 10MB
            "allowed_extensions": [".txt", ".md", ".py", ".json", ".yaml", ".csv"],
            "blocked_extensions": [".exe", ".bat", ".sh", ".ps1", ".dll", ".so"],
            "require_approval_for": ["delete", "system_command"]
        }
    
    def route_operation(self, operation: str, **kwargs) -> Dict[str, Any]:
        """操作をルーティング"""
        try:
            self.logger.info(f"操作ルーティング開始: {operation}")
            
            # 操作の分類
            operation_type = self._classify_operation(operation)
            
            # 安全性チェック
            safety_check = self._check_operation_safety(operation, operation_type, **kwargs)
            if not safety_check['safe']:
                return {
                    'success': False,
                    'error': f"安全性チェック失敗: {safety_check['reason']}",
                    'requires_approval': safety_check['requires_approval']
                }
            
            # 操作の実行
            result = self._execute_operation(operation, operation_type, **kwargs)
            
            # 履歴に記録
            self._record_operation(operation, operation_type, kwargs, result)
            
            self.logger.info(f"操作ルーティング完了: {operation} - {result.get('success', False)}")
            return result
            
        except Exception as e:
            self.logger.error(f"操作ルーティングエラー: {e}")
            return {
                'success': False,
                'error': str(e),
                'operation': operation
            }
    
    def _classify_operation(self, operation: str) -> str:
        """操作を分類"""
        if operation in self.supported_operations["file"]:
            return "file"
        elif operation in self.supported_operations["system"]:
            return "system"
        elif operation in self.supported_operations["conversation"]:
            return "conversation"
        else:
            return "unknown"
    
    def _check_operation_safety(self, operation: str, operation_type: str, **kwargs) -> Dict[str, Any]:
        """操作の安全性をチェック"""
        safety_result = {
            'safe': True,
            'reason': '',
            'requires_approval': False
        }
        
        # ファイル操作の安全性チェック
        if operation_type == "file":
            file_safety = self._check_file_operation_safety(operation, **kwargs)
            if not file_safety['safe']:
                safety_result.update(file_safety)
                return safety_result
        
        # 承認が必要な操作のチェック
        if operation in self.safety_config["require_approval_for"]:
            safety_result['requires_approval'] = True
            # 承認が完了しているかチェック
            if not kwargs.get('approved', False):
                safety_result['safe'] = False
                safety_result['reason'] = f"操作 '{operation}' には承認が必要です"
                return safety_result
        
        return safety_result
    
    def _check_file_operation_safety(self, operation: str, **kwargs) -> Dict[str, Any]:
        """ファイル操作の安全性をチェック"""
        safety_result = {
            'safe': True,
            'reason': '',
            'requires_approval': False
        }
        
        file_path = kwargs.get('file_path', '')
        if not file_path:
            return safety_result
        
        # 作業ディレクトリ内かチェック
        try:
            file_path_obj = Path(file_path)
            work_dir_obj = Path(self.work_dir).resolve()
            
            if not file_path_obj.resolve().is_relative_to(work_dir_obj):
                safety_result['safe'] = False
                safety_result['reason'] = f"作業ディレクトリ外のファイル: {file_path}"
                return safety_result
        except Exception:
            safety_result['safe'] = False
            safety_result['reason'] = f"無効なファイルパス: {file_path}"
            return safety_result
        
        # 拡張子チェック
        if operation in ["write", "create"]:
            file_ext = file_path_obj.suffix.lower()
            if file_ext in self.safety_config["blocked_extensions"]:
                safety_result['safe'] = False
                safety_result['reason'] = f"ブロックされた拡張子: {file_ext}"
                return safety_result
            
            if file_ext not in self.safety_config["allowed_extensions"]:
                safety_result['requires_approval'] = True
        
        # ファイルサイズチェック
        if operation == "write":
            content = kwargs.get('content', '')
            if len(content) > self.safety_config["max_file_size"]:
                safety_result['safe'] = False
                safety_result['reason'] = f"ファイルサイズが大きすぎます: {len(content)} bytes"
                return safety_result
        
        return safety_result
    
    def _execute_operation(self, operation: str, operation_type: str, **kwargs) -> Dict[str, Any]:
        """操作を実行"""
        try:
            if operation_type == "file":
                return self._execute_file_operation(operation, **kwargs)
            elif operation_type == "system":
                return self._execute_system_operation(operation, **kwargs)
            elif operation_type == "conversation":
                return self._execute_conversation_operation(operation, **kwargs)
            else:
                return {
                    'success': False,
                    'error': f"サポートされていない操作: {operation}"
                }
        except Exception as e:
            return {
                'success': False,
                'error': f"操作実行エラー: {str(e)}"
            }
    
    def _execute_file_operation(self, operation: str, **kwargs) -> Dict[str, Any]:
        """ファイル操作を実行"""
        file_path = kwargs.get('file_path', '')
        
        try:
            if operation == "read":
                content = self.file_ops.read_file(file_path)
                return {
                    'success': True,
                    'content': content,
                    'file_path': file_path,
                    'operation': operation
                }
            
            elif operation == "write":
                content = kwargs.get('content', '')
                result = self.file_ops.write_file(file_path, content)
                return {
                    'success': result,
                    'file_path': file_path,
                    'operation': operation,
                    'content_length': len(content)
                }
            
            elif operation == "create":
                content = kwargs.get('content', '')
                result = self.file_ops.write_file(file_path, content)
                return {
                    'success': result,
                    'file_path': file_path,
                    'operation': operation,
                    'content_length': len(content)
                }
            
            elif operation == "delete":
                result = self.file_ops.delete_file(file_path)
                return {
                    'success': result,
                    'file_path': file_path,
                    'operation': operation
                }
            
            elif operation == "list":
                directory = kwargs.get('directory', self.work_dir)
                files = self.file_ops.list_files(directory)
                return {
                    'success': True,
                    'files': files,
                    'directory': str(directory),
                    'operation': operation
                }
            
            elif operation == "exists":
                exists = self.file_ops.file_exists(file_path)
                return {
                    'success': True,
                    'exists': exists,
                    'file_path': file_path,
                    'operation': operation
                }
            
            else:
                return {
                    'success': False,
                    'error': f"サポートされていないファイル操作: {operation}"
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f"ファイル操作エラー: {str(e)}",
                'operation': operation,
                'file_path': file_path
            }
    
    def _execute_system_operation(self, operation: str, **kwargs) -> Dict[str, Any]:
        """システム操作を実行"""
        try:
            if operation == "info":
                return {
                    'success': True,
                    'system_info': {
                        'work_directory': str(self.work_dir),
                        'python_version': self._get_python_version(),
                        'platform': self._get_platform_info(),
                        'timestamp': datetime.now().isoformat()
                    },
                    'operation': operation
                }
            
            elif operation == "status":
                return {
                    'success': True,
                    'status': {
                        'tool_router': 'active',
                        'file_ops': 'active',
                        'work_dir_exists': self.work_dir.exists(),
                        'operation_count': len(self.operation_history)
                    },
                    'operation': operation
                }
            
            elif operation == "health":
                return {
                    'success': True,
                    'health': {
                        'status': 'healthy',
                        'checks': {
                            'work_directory': self.work_dir.exists(),
                            'file_operations': True,
                            'safety_config': True
                        },
                        'timestamp': datetime.now().isoformat()
                    },
                    'operation': operation
                }
            
            else:
                return {
                    'success': False,
                    'error': f"サポートされていないシステム操作: {operation}"
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f"システム操作エラー: {str(e)}",
                'operation': operation
            }
    
    def _execute_conversation_operation(self, operation: str, **kwargs) -> Dict[str, Any]:
        """会話関連の操作を実行"""
        try:
            if operation == "history":
                return {
                    'success': True,
                    'history': self.operation_history[-10:],  # 最新10件
                    'operation': operation
                }
            
            elif operation == "summary":
                summary = self._generate_operation_summary()
                return {
                    'success': True,
                    'summary': summary,
                    'operation': operation
                }
            
            elif operation == "export":
                export_data = self._export_operation_data()
                return {
                    'success': True,
                    'export_data': export_data,
                    'operation': operation
                }
            
            else:
                return {
                    'success': False,
                    'error': f"サポートされていない会話操作: {operation}"
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f"会話操作エラー: {str(e)}",
                'operation': operation
            }
    
    def _record_operation(self, operation: str, operation_type: str, 
                         kwargs: Dict[str, Any], result: Dict[str, Any]):
        """操作を履歴に記録"""
        record = {
            'timestamp': datetime.now().isoformat(),
            'operation': operation,
            'type': operation_type,
            'parameters': kwargs,
            'result': {
                'success': result.get('success', False),
                'error': result.get('error', '')
            }
        }
        
        self.operation_history.append(record)
        
        # 最大履歴数を制限
        if len(self.operation_history) > self.max_history:
            self.operation_history = self.operation_history[-self.max_history:]
    
    def _generate_operation_summary(self) -> Dict[str, Any]:
        """操作履歴のサマリーを生成"""
        if not self.operation_history:
            return {'message': '操作履歴がありません'}
        
        total_operations = len(self.operation_history)
        successful_operations = sum(1 for op in self.operation_history if op['result']['success'])
        success_rate = successful_operations / total_operations if total_operations > 0 else 0
        
        operation_types = {}
        for op in self.operation_history:
            op_type = op['type']
            operation_types[op_type] = operation_types.get(op_type, 0) + 1
        
        return {
            'total_operations': total_operations,
            'successful_operations': successful_operations,
            'success_rate': success_rate,
            'operation_types': operation_types,
            'last_operation': self.operation_history[-1]['operation'] if self.operation_history else None
        }
    
    def _export_operation_data(self) -> Dict[str, Any]:
        """操作データをエクスポート"""
        return {
            'export_timestamp': datetime.now().isoformat(),
            'work_directory': str(self.work_dir),
            'safety_config': self.safety_config,
            'supported_operations': self.supported_operations,
            'operation_history': self.operation_history,
            'usage_statistics': self.get_usage_statistics()
        }
    
    def _get_python_version(self) -> str:
        """Pythonバージョンを取得"""
        import sys
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    
    def _get_platform_info(self) -> str:
        """プラットフォーム情報を取得"""
        import platform
        return platform.platform()
    
    def get_supported_operations(self) -> Dict[str, List[str]]:
        """サポートされている操作を取得"""
        return self.supported_operations.copy()
    
    def get_safety_config(self) -> Dict[str, Any]:
        """安全性設定を取得"""
        return self.safety_config.copy()
    
    def get_usage_statistics(self) -> Dict[str, Any]:
        """使用統計を取得"""
        summary = self._generate_operation_summary()
        return {
            'total_operations': len(self.operation_history),
            'operation_types': summary.get('operation_types', {}),
            'last_operation_time': self.operation_history[-1]['timestamp'] if self.operation_history else None
        }
    
    def update_safety_config(self, **kwargs):
        """安全性設定を更新"""
        for key, value in kwargs.items():
            if key in self.safety_config:
                self.safety_config[key] = value
                self.logger.info(f"安全性設定を更新: {key} = {value}")
    
    def clear_history(self):
        """操作履歴をクリア"""
        self.operation_history.clear()
        self.logger.info("操作履歴をクリアしました")
    
    def to_dict(self) -> Dict[str, Any]:
        """設定を辞書形式で取得"""
        return {
            'work_directory': str(self.work_dir),
            'supported_operations': self.supported_operations,
            'safety_config': self.safety_config,
            'usage_statistics': self.get_usage_statistics(),
            'operation_history_count': len(self.operation_history)
        }
