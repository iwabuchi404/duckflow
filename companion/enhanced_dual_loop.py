"""
EnhancedDualLoopSystem - Final Refactored Version

設計ドキュメント4.4節の要求に基づく状態同期システムを実装。
- 状態所有者の一元化
- ループからの参照による状態管理
- コールバックによる同期
"""

import threading
import queue
import logging
import uuid
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
import time

from .enhanced_core import EnhancedCompanionCore
from .shared_context_manager import SharedContextManager
from .chat_loop import ChatLoop
from .task_loop import TaskLoop
from .plan_tool import PlanTool
from .file_ops import SimpleFileOps
from .simple_approval import ApprovalMode
from .state.enums import Step, Status
from .state_machine import StateMachine
from .ui import rich_ui


class EnhancedDualLoopSystem:
    """Dual-Loop System with centralized state management."""

    def __init__(self, session_id: Optional[str] = None, approval_mode: ApprovalMode = ApprovalMode.STANDARD):
        self.session_id = session_id or str(uuid.uuid4())
        self.logger = logging.getLogger(__name__)
        
        self.task_queue = queue.Queue()
        self.status_queue = queue.Queue()
        
        # Centralized state and logic components
        self.state_machine = StateMachine()
        self.enhanced_companion = EnhancedCompanionCore(self.session_id, approval_mode)
        self.agent_state = self.enhanced_companion.get_agent_state()

        # Register a callback to sync StateMachine changes to AgentState
        self.state_machine.add_state_change_callback(self._sync_state_to_agent_state)
        # Initial sync to ensure consistency from the start
        self._sync_state_to_agent_state(self.state_machine.current_step, self.state_machine.current_status, "init")

        # Initialize loops with a reference to the parent system
        self.chat_loop = ChatLoop(self.task_queue, self.status_queue, self.enhanced_companion, self)
        self.task_loop = TaskLoop(self.task_queue, self.status_queue, self.enhanced_companion, self)
        
        self.task_thread: Optional[threading.Thread] = None
        self.running = False
        self.logger.info("EnhancedDualLoopSystem initialized successfully.")

    def _sync_state_to_agent_state(self, new_step: Step, new_status: Status, trigger: str):
        """Callback to sync the StateMachine's state to the central AgentState."""
        try:
            self.logger.debug(f"State Sync: {new_step.value}.{new_status.value} triggered by {trigger}")
            self.agent_state.step = new_step
            self.agent_state.status = new_status
        except Exception as e:
            self.logger.error(f"Error during state synchronization: {e}")

    def start(self):
        if self.running:
            self.logger.warning("System is already running.")
            return

        self.running = True
        rich_ui.print_message("🦆 Duckflow Companion v4.0 Final 起動中...", "success")
        rich_ui.print_message(f"📋 セッションID: {self.session_id}", "info")

        self.task_thread = threading.Thread(target=self.task_loop.run, daemon=True, name="TaskLoop")
        self.task_thread.start()
        self.logger.info("Dual-Loop System started.")

        try:
            self.chat_loop.run()
        except KeyboardInterrupt:
            self.logger.info("User requested shutdown.")
        finally:
            self.stop()

    def stop(self):
        if not self.running:
            return
        self.logger.info("Stopping Dual-Loop System...")
        self.running = False
        self.chat_loop.stop()
        self.task_loop.stop()
        if self.task_thread and self.task_thread.is_alive():
            self.task_thread.join(timeout=5.0)
        self.logger.info("System stopped.")

    def get_sync_health_report(self) -> Dict[str, Any]:
        """状態同期の健全性レポートを取得（設計ドキュメント4.4.2の監視要求）
        
        Returns:
            状態同期の健全性情報
        """
        try:
            # StateMachineの同期状況を取得
            sync_status = self.state_machine.get_sync_status() if hasattr(self.state_machine, 'get_sync_status') else {}
            
            # AgentStateとStateMachineの状態を比較
            state_machine_step = self.state_machine.current_step
            state_machine_status = self.state_machine.current_status
            agent_state_step = self.agent_state.step
            agent_state_status = self.agent_state.status
            
            # 同期の一貫性をチェック
            is_synced = (state_machine_step == agent_state_step and 
                        state_machine_status == agent_state_status)
            
            # 同期成功率を計算（基本的な実装）
            sync_success_rate = 100.0 if is_synced else 0.0
            
            # 推奨事項の生成
            recommendations = []
            if not is_synced:
                recommendations.append("状態の手動同期が必要です")
                recommendations.append("システムの再起動を検討してください")
            
            return {
                'sync_status': {
                    'is_synced': is_synced,
                    'sync_success_rate': sync_success_rate,
                    'state_machine_step': state_machine_step.value if state_machine_step else None,
                    'state_machine_status': state_machine_status.value if state_machine_status else None,
                    'agent_state_step': agent_state_step.value if agent_state_step else None,
                    'agent_state_status': agent_state_status.value if agent_state_status else None
                },
                'sync_details': sync_status,
                'recommendations': recommendations,
                'last_check': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"状態同期レポート生成エラー: {e}")
            return {
                'error': str(e),
                'sync_status': {'sync_success_rate': 0.0},
                'recommendations': ['システムエラーが発生しています'],
                'last_check': datetime.now().isoformat()
            }