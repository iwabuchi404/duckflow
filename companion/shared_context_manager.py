"""
SharedContextManager - ChatLoopとTaskLoop間の共有コンテキスト管理
Step 1: 最小変更での改善
"""

import threading
from typing import Any, Dict, Optional
from datetime import datetime


class SharedContextManager:
    """ChatLoopとTaskLoop間で共有するコンテキスト管理"""
    
    def __init__(self):
        """初期化"""
        self._context_lock = threading.Lock()
        self.current_context = {}
        self.last_updated = datetime.now()
    
    def update_context(self, key: str, value: Any) -> None:
        """コンテキストを更新（スレッドセーフ）
        
        Args:
            key: コンテキストキー
            value: 更新する値
        """
        with self._context_lock:
            self.current_context[key] = value
            self.last_updated = datetime.now()
    
    def get_context(self) -> Dict[str, Any]:
        """現在のコンテキストを取得
        
        Returns:
            コンテキストのコピー
        """
        with self._context_lock:
            return self.current_context.copy()
    
    def get_context_value(self, key: str, default: Any = None) -> Any:
        """特定のコンテキスト値を取得
        
        Args:
            key: コンテキストキー
            default: デフォルト値
            
        Returns:
            コンテキスト値
        """
        with self._context_lock:
            return self.current_context.get(key, default)
    
    def clear_context(self) -> None:
        """コンテキストをクリア"""
        with self._context_lock:
            self.current_context.clear()
            self.last_updated = datetime.now()
    
    def get_status(self) -> Dict[str, Any]:
        """コンテキスト管理の状態を取得
        
        Returns:
            状態情報
        """
        with self._context_lock:
            return {
                "context_keys": list(self.current_context.keys()),
                "last_updated": self.last_updated,
                "context_size": len(self.current_context)
            }