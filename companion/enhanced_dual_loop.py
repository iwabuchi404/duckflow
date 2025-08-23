#!/usr/bin/env python3
"""
Enhanced Dual-Loop System v7 - 中央指令型タスク実行モデル

v7アーキテクチャに基づく新しいDual-Loop System
- 中央指令型のタスク実行
- 重複表示防止機能
- 適切な区切り表示
"""

import asyncio
import logging
import queue
import threading
import uuid
from typing import Optional, Dict, Any

# 既存のimport
try:
    from .state.agent_state import AgentState
    from .enhanced_core import EnhancedCompanionCoreV7
    from .enhanced.chat_loop import EnhancedChatLoopV7
    from .enhanced.task_loop import TaskLoopV7
    from .config.encoding_config import setup_encoding_once
except ImportError:
    # フォールバック用のダミークラス
    class AgentState: pass
    class EnhancedCompanionCoreV7: pass
    class EnhancedChatLoopV7: pass
    class TaskLoopV7: pass
    def setup_encoding_once(): pass

# v7アーキテクチャのコンポーネントをインポート
from .llm_call_manager import LLMCallManager
from .llm.llm_service import LLMService
from .llm.llm_client import LLMClient
from .intent_understanding.intent_analyzer_llm import IntentAnalyzerLLM
from .prompts.prompt_context_service import PromptContextService
from .ui import rich_ui

class EnhancedDualLoopSystem:
    """v7: 中央指令型タスク実行モデルに基づくDual-Loop System"""

    def __init__(self, session_id: Optional[str] = None):
        # システム起動時に文字コード環境を設定（一元化された設定を使用）
        setup_encoding_once()
        
        self.session_id = session_id or str(uuid.uuid4())
        self.logger = logging.getLogger(__name__)
        
        # スレッドセーフな通信のためのキュー
        self.task_queue = queue.Queue()
        self.status_queue = queue.Queue()
        
        # AgentStateを中央の状態管理として初期化
        self.agent_state = AgentState(session_id=self.session_id)

        # 🔥 新規: EnhancedCompanionCoreV7が必要とする属性を追加
        try:
            from .llm_call_manager import LLMCallManager
            self.llm_call_manager = LLMCallManager()
            self.logger.info("LLMCallManager が初期化されました")
        except ImportError:
            self.llm_call_manager = None
            self.logger.warning("LLMCallManager の初期化に失敗しました")
        
        try:
            from .llm.llm_service import LLMService
            from .llm.llm_client import LLMClient
            llm_client = LLMClient()
            self.llm_service = LLMService(llm_client)
            self.logger.info("LLMService が初期化されました")
        except ImportError:
            self.llm_service = None
            self.logger.warning("LLMService の初期化に失敗しました")
        
        try:
            from .intent_understanding.intent_analyzer_llm import IntentAnalyzerLLM
            self.intent_analyzer = IntentAnalyzerLLM()
            self.logger.info("IntentAnalyzer が初期化されました")
        except ImportError:
            self.intent_analyzer = None
            self.logger.warning("IntentAnalyzer の初期化に失敗しました")
        
        try:
            from .prompts.prompt_context_service import PromptContextService
            self.prompt_context_service = PromptContextService()
            self.logger.info("PromptContextService が初期化されました")
        except ImportError:
            self.prompt_context_service = None
            self.logger.warning("PromptContextService の初期化に失敗しました")

        # v7のコアとループを初期化
        self.enhanced_companion = EnhancedCompanionCoreV7(self) 
        
        self.chat_loop = EnhancedChatLoopV7(
            task_queue=self.task_queue, 
            status_queue=self.status_queue, 
            companion_core=self.enhanced_companion
        )
        self.task_loop = TaskLoopV7(
            task_queue=self.task_queue, 
            status_queue=self.status_queue, 
            agent_state=self.agent_state
        )
        
        self.task_thread: Optional[threading.Thread] = None
        self.running = False
        self.logger.info("EnhancedDualLoopSystem (v7) が初期化されました。")

    def start(self):
        if self.running:
            self.logger.warning("システムは既に実行中です。")
            return

        self.running = True
        rich_ui.print_message("🦆 Duckflow v7 アーキテクチャで起動中...", "success")
        rich_ui.print_message(f"📋 セッションID: {self.session_id}", "info")

        self.task_thread = threading.Thread(target=self.task_loop.run, daemon=True, name="TaskLoopV7")
        self.task_thread.start()
        
        try:
            # ChatLoopはメインスレッドで実行
            self.chat_loop.run()
        except KeyboardInterrupt:
            self.logger.info("ユーザーによるシャットダウン要求。")
        finally:
            self.stop()

    def stop(self):
        if not self.running:
            return
        self.logger.info("Stopping Dual-Loop System (v7)...")
        self.running = False
        self.chat_loop.stop()
        self.task_loop.stop()
        if self.task_thread and self.task_thread.is_alive():
            # TaskLoopスレッドに終了を通知するためにNoneをキューに入れる
            self.task_queue.put(None)
            self.task_thread.join(timeout=5.0)
        self.logger.info("System stopped.")

    def get_status(self):
        """システムの基本状態を返す"""
        return {
            "running": self.running,
            "session_id": self.session_id,
            "task_queue_size": self.task_queue.qsize(),
            "status_queue_size": self.status_queue.qsize(),
        }

    def get_agent_state(self) -> AgentState:
        """現在のAgentStateを返す"""
        return self.agent_state
