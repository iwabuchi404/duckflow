"""
Dual-Loop System - Step 1 Implementation
シンプルな対話継続システム

対話ループとタスク実行ループを分離し、
タスク実行中も対話を継続可能にする。
"""

import threading
import queue
import time
import logging
from typing import Optional

from .chat_loop import ChatLoop
from .task_loop import TaskLoop
from .state_machine import StateMachine


class DualLoopSystem:
    """シンプルなDual-Loop System
    
    ChatLoop: ユーザーとの対話を継続
    TaskLoop: バックグラウンドでタスク実行
    """
    
    def __init__(self):
        """システムを初期化"""
        # ループ間通信用のキュー
        self.task_queue = queue.Queue()      # ChatLoop → TaskLoop
        self.status_queue = queue.Queue()    # TaskLoop → ChatLoop
        
        # 状態管理（新しいChatLoopとの互換性のため）
        self.state_machine = StateMachine()
        
        # 共有のCompanionCoreインスタンス
        from .core import CompanionCore
        self.shared_companion = CompanionCore()
        
        # 共有コンテキスト管理（Step 1改善）
        from .shared_context_manager import SharedContextManager
        self.context_manager = SharedContextManager()
        
        # 各ループの初期化（共有インスタンスを渡す）
        self.chat_loop = ChatLoop(
            self.task_queue, 
            self.status_queue, 
            self.shared_companion,
            self
        )
        self.task_loop = TaskLoop(
            self.task_queue, 
            self.status_queue, 
            self.shared_companion,
            self
        )
        
        # スレッド管理
        self.task_thread: Optional[threading.Thread] = None
        self.running = False
        
        # ログ設定
        self.logger = logging.getLogger(__name__)
    
    def start(self):
        """システムを開始"""
        if self.running:
            self.logger.warning("システムは既に動作中です")
            return
        
        self.running = True
        
        # TaskLoopをバックグラウンドで開始
        self.task_thread = threading.Thread(
            target=self.task_loop.run,
            daemon=True,
            name="TaskLoop"
        )
        self.task_thread.start()
        
        self.logger.info("Dual-Loop System を開始しました")
        
        # ChatLoopをメインスレッドで実行
        try:
            self.chat_loop.run()
        except KeyboardInterrupt:
            self.logger.info("ユーザーによる終了要求")
        finally:
            self.stop()
    
    def stop(self):
        """システムを停止"""
        if not self.running:
            return
        
        self.logger.info("Dual-Loop System を停止中...")
        
        # 各ループに停止を通知
        self.running = False
        self.chat_loop.stop()
        self.task_loop.stop()
        
        # TaskLoopスレッドの終了を待機
        if self.task_thread and self.task_thread.is_alive():
            self.task_thread.join(timeout=5.0)
            if self.task_thread.is_alive():
                self.logger.warning("TaskLoopの停止がタイムアウトしました")
        
        self.logger.info("Dual-Loop System を停止しました")
    
    def get_status(self) -> dict:
        """システムの状態を取得"""
        return {
            "running": self.running,
            "chat_loop_active": self.chat_loop.running if hasattr(self.chat_loop, 'running') else False,
            "task_loop_active": self.task_loop.running if hasattr(self.task_loop, 'running') else False,
            "task_queue_size": self.task_queue.qsize(),
            "status_queue_size": self.status_queue.qsize(),
            "current_task": getattr(self.task_loop, 'current_task', None)
        }
    
    def is_task_running(self) -> bool:
        """タスクが実行中かどうか"""
        return hasattr(self.task_loop, 'current_task') and self.task_loop.current_task is not None


# デフォルトインスタンス（import-time initializationを避けるためコメントアウト）
# dual_loop_system = DualLoopSystem()