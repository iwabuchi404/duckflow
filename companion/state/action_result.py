"""
ActionResult data class for managing action execution results.

This module provides the ActionResult class for tracking and managing
the results of individual actions within ActionLists.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, Dict


@dataclass
class ActionResult:
    """
    アクション実行結果を格納するデータクラス
    
    Attributes:
        action_id: ActionList内での一意ID
        operation: 実行した操作 (例: "file_ops.read_file")
        result: 実際の実行結果
        timestamp: 実行時刻
        action_list_id: ActionList全体のID
        sequence_number: ActionList内での実行順序
        metadata: 追加のメタデータ
    """
    action_id: str
    operation: str
    result: Any
    timestamp: datetime
    action_list_id: str
    sequence_number: int
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """初期化後の処理"""
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換（AgentState保存用）"""
        return {
            'action_id': self.action_id,
            'operation': self.operation,
            'result': self.result,
            'timestamp': self.timestamp.isoformat(),
            'action_list_id': self.action_list_id,
            'sequence_number': self.sequence_number,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ActionResult':
        """辞書から復元"""
        return cls(
            action_id=data['action_id'],
            operation=data['operation'],
            result=data['result'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            action_list_id=data['action_list_id'],
            sequence_number=data['sequence_number'],
            metadata=data.get('metadata', {})
        )
    
    def get_result_summary(self, max_length: int = 100) -> str:
        """結果の要約を取得"""
        if isinstance(self.result, str):
            if len(self.result) <= max_length:
                return self.result
            return self.result[:max_length] + "..."
        else:
            result_str = str(self.result)
            if len(result_str) <= max_length:
                return result_str
            return result_str[:max_length] + "..."
    
    def is_error(self) -> bool:
        """エラー結果かどうかを判定"""
        if isinstance(self.result, dict):
            return 'error' in self.result
        return False
    
    def get_execution_info(self) -> str:
        """実行情報の文字列を生成"""
        result_summary = self.get_result_summary(50)
        error_status = " [ERROR]" if self.is_error() else ""
        return f"{self.action_id} ({self.operation}): {result_summary}{error_status}"