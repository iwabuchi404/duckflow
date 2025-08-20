"""
Task Loop - 実行ループ (Refactored)
バックグラウンドでタスクを実行し、状態を更新する。
"""

import queue
import time
import asyncio
import logging
from typing import Optional, Dict, Any

from .state.enums import Step, Status

class TaskLoop:
    """実行ループ - バックグラウンドでタスクを実行し、状態を更新する"""

    def __init__(self, task_queue: queue.Queue, status_queue: queue.Queue, companion, dual_loop_system):
        self.task_queue = task_queue
        self.status_queue = status_queue
        self.companion = companion
        self.dual_loop_system = dual_loop_system
        self.running = False
        self.logger = logging.getLogger(__name__)

    def run(self):
        self.running = True
        self.logger.info("TaskLoop を開始しました")
        while self.running:
            try:
                task_data = self.task_queue.get(timeout=1) # タイムアウト付きで待機
                self._execute_task(task_data)
            except queue.Empty:
                continue # タイムアウト時はループを継続
            except Exception as e:
                self.logger.error(f"TaskLoopで予期せぬエラー: {e}", exc_info=True)
                self._send_status({'type': 'error', 'message': str(e)})

    def _execute_task(self, task_data: Dict[str, Any]):
        """タスクデータを解釈して実行"""
        task_type = task_data.get('type')
        self.logger.info(f"タスク受信: {task_type}")

        if task_type == 'process_intent':
            intent_result = task_data.get('intent_result')
            if intent_result:
                # 非同期メソッドをTaskLoopのスレッドで安全に実行
                try:
                    result = asyncio.run(self.companion.process_with_intent_result(intent_result))
                    self._send_status({'type': 'task_completed', 'message': result})
                except Exception as e:
                    self.logger.error(f"process_with_intent_resultの実行中にエラー: {e}", exc_info=True)
                    self._send_status({'type': 'task_error', 'message': str(e)})
            else:
                self.logger.warning("intent_resultが含まれていないタスクをスキップしました。")
        else:
            self.logger.warning(f"不明なタスクタイプをスキップしました: {task_type}")
        
        self.task_queue.task_done()

    def _send_status(self, status_data: Dict[str, Any]):
        """状態更新をChatLoopに通知"""
        try:
            self.status_queue.put(status_data)
        except Exception as e:
            self.logger.error(f"状態キューへの通知エラー: {e}")

    def stop(self):
        self.running = False
        self.logger.info("TaskLoop を停止しました")
