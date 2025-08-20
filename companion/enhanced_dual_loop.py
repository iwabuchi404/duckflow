"""
EnhancedDualLoopSystem - Final Refactored Version
"""

import threading
import queue
import logging
import uuid
from typing import Optional

from .enhanced_core import EnhancedCompanionCore
from .enhanced.chat_loop import EnhancedChatLoop
from .enhanced.task_loop import EnhancedTaskLoop
from .simple_approval import ApprovalMode
from .ui import rich_ui


class EnhancedDualLoopSystem:
    """Dual-Loop System with centralized state management."""

    def __init__(self, session_id: Optional[str] = None, approval_mode: ApprovalMode = ApprovalMode.STANDARD):
        self.session_id = session_id or str(uuid.uuid4())
        self.logger = logging.getLogger(__name__)
        
        # Queues for thread-safe communication
        self.task_queue = queue.Queue()
        self.status_queue = queue.Queue()
        
        # Centralized state and logic components
        self.enhanced_companion = EnhancedCompanionCore(self.session_id, approval_mode)
        self.agent_state = self.enhanced_companion.get_agent_state()

        # Initialize Enhanced v2.0 loops with a reference to the parent system
        self.chat_loop = EnhancedChatLoop(self.task_queue, self.status_queue, self.enhanced_companion, self)
        self.task_loop = EnhancedTaskLoop(self.task_queue, self.status_queue, self.enhanced_companion, self)
        
        self.task_thread: Optional[threading.Thread] = None
        self.running = False

    def get_current_state(self) -> str:
        """AgentState ベースの現在状態を返す。"""
        try:
            step = self.agent_state.step.value if self.agent_state and self.agent_state.step else None
            status = self.agent_state.status.value if self.agent_state and self.agent_state.status else None
            if step and status:
                return f"{step}.{status}"
            return "UNKNOWN"
        except Exception:
            return "UNKNOWN"

    def start(self):
        if self.running:
            self.logger.warning("System is already running.")
            return

        self.running = True
        rich_ui.print_message("🦆 Duckflow Enhanced v2.0 起動中...", "success")
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
