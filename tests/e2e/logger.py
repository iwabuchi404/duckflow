"""
ConversationLogger - 対話ログの記録と管理
"""

import json
import uuid
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path


class ConversationLogger:
    """対話ログの記録と管理"""
    
    def __init__(self, scenario_name: str):
        """初期化
        
        Args:
            scenario_name: シナリオ名
        """
        self.scenario_name = scenario_name
        self.log = {
            "session_id": str(uuid.uuid4()),
            "scenario_name": scenario_name,
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "exchanges": [],
            "system_states": [],
            "files_created": [],
            "completion_status": "running",  # running, completed, failed, timeout
            "test_config": {},
            "error_messages": []
        }
        
        # ログの設定
        self.logger = logging.getLogger(__name__)
        
    def log_exchange(self, user_input: str, duckflow_response: str, 
                    system_state: Optional[Dict] = None):
        """1回の対話をログに記録
        
        Args:
            user_input: ユーザーの入力
            duckflow_response: Duckflowの応答
            system_state: システムの内部状態
        """
        exchange = {
            "exchange_id": len(self.log["exchanges"]) + 1,
            "timestamp": datetime.now().isoformat(),
            "user": user_input,
            "duckflow": duckflow_response,
            "user_length": len(user_input),
            "duckflow_length": len(duckflow_response),
            "system_state": system_state or {}
        }
        
        self.log["exchanges"].append(exchange)
        self.logger.info(f"Logged exchange {exchange['exchange_id']}: {user_input[:50]}...")
    
    def log_file_operation(self, operation: str, file_path: str, content: str = ""):
        """ファイル操作をログに記録
        
        Args:
            operation: 操作の種類 (create, read, write, delete)
            file_path: ファイルパス
            content: ファイルの内容（最初の500文字のみ記録）
        """
        file_op = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "file_path": file_path,
            "content_preview": content[:500] + ("..." if len(content) > 500 else ""),
            "content_length": len(content)
        }
        
        self.log["files_created"].append(file_op)
        self.logger.info(f"Logged file operation: {operation} {file_path}")
    
    def log_system_state(self, state_name: str, state_data: Dict):
        """システム状態をログに記録
        
        Args:
            state_name: 状態の名前
            state_data: 状態データ
        """
        state_entry = {
            "timestamp": datetime.now().isoformat(),
            "state_name": state_name,
            "state_data": state_data
        }
        
        self.log["system_states"].append(state_entry)
        self.logger.debug(f"Logged system state: {state_name}")
    
    def log_error(self, error_message: str, error_type: str = "general"):
        """エラーをログに記録
        
        Args:
            error_message: エラーメッセージ
            error_type: エラーの種類
        """
        error_entry = {
            "timestamp": datetime.now().isoformat(),
            "error_type": error_type,
            "error_message": error_message
        }
        
        self.log["error_messages"].append(error_entry)
        self.logger.error(f"Logged error: {error_type} - {error_message}")
    
    def set_completion_status(self, status: str, reason: str = ""):
        """完了ステータスを設定
        
        Args:
            status: 完了ステータス (completed, failed, timeout)
            reason: 完了理由
        """
        self.log["completion_status"] = status
        self.log["end_time"] = datetime.now().isoformat()
        
        if reason:
            self.log["completion_reason"] = reason
        
        # 統計情報の計算
        self.log["statistics"] = self._calculate_statistics()
        
        self.logger.info(f"Test completed with status: {status}")
    
    def _calculate_statistics(self) -> Dict:
        """統計情報を計算
        
        Returns:
            統計情報
        """
        exchanges = self.log["exchanges"]
        
        if not exchanges:
            return {}
        
        # 基本統計
        total_exchanges = len(exchanges)
        total_user_chars = sum(ex["user_length"] for ex in exchanges)
        total_duckflow_chars = sum(ex["duckflow_length"] for ex in exchanges)
        
        # 時間統計
        start_time = datetime.fromisoformat(self.log["start_time"])
        end_time = datetime.fromisoformat(self.log["end_time"])
        duration_seconds = (end_time - start_time).total_seconds()
        
        return {
            "total_exchanges": total_exchanges,
            "total_user_characters": total_user_chars,
            "total_duckflow_characters": total_duckflow_chars,
            "average_user_length": total_user_chars / total_exchanges if total_exchanges > 0 else 0,
            "average_duckflow_length": total_duckflow_chars / total_exchanges if total_exchanges > 0 else 0,
            "duration_seconds": duration_seconds,
            "exchanges_per_minute": (total_exchanges / duration_seconds * 60) if duration_seconds > 0 else 0,
            "total_files_created": len(self.log["files_created"]),
            "total_errors": len(self.log["error_messages"])
        }
    
    def save_log(self, results_dir: str = "tests/results/daily") -> str:
        """ログをファイルに保存
        
        Args:
            results_dir: 保存先ディレクトリ
            
        Returns:
            保存されたファイルパス
        """
        # 保存先ディレクトリの作成
        save_dir = Path(results_dir)
        save_dir.mkdir(parents=True, exist_ok=True)
        
        # ファイル名の生成
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_scenario_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in self.scenario_name)
        filename = f"e2e_test_{safe_scenario_name}_{timestamp}.json"
        filepath = save_dir / filename
        
        # ログの保存
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.log, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"Log saved to: {filepath}")
            return str(filepath)
            
        except Exception as e:
            self.logger.error(f"Failed to save log: {e}")
            raise
    
    def get_log_summary(self) -> Dict:
        """ログの要約を取得
        
        Returns:
            ログの要約
        """
        summary = {
            "session_id": self.log["session_id"],
            "scenario_name": self.log["scenario_name"],
            "completion_status": self.log["completion_status"],
            "total_exchanges": len(self.log["exchanges"]),
            "total_files": len(self.log["files_created"]),
            "total_errors": len(self.log["error_messages"])
        }
        
        if "statistics" in self.log:
            summary.update(self.log["statistics"])
        
        return summary
    
    def get_conversation_text(self) -> str:
        """対話テキストを取得（評価用）
        
        Returns:
            対話テキストの文字列
        """
        lines = []
        
        for exchange in self.log["exchanges"]:
            lines.append(f"ユーザー: {exchange['user']}")
            lines.append(f"Duckflow: {exchange['duckflow']}")
            lines.append("")  # 空行
        
        return "\n".join(lines)