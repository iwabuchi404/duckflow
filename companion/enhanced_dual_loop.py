"""
EnhancedDualLoopSystem - Step 2: 既存システム統合版
AgentState、ConversationMemory、PromptCompilerとの完全統合
"""

import threading
import queue
import logging
import uuid
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime

from .enhanced_core import EnhancedCompanionCore
from .shared_context_manager import SharedContextManager
from .chat_loop import ChatLoop
from .task_loop import TaskLoop


class EnhancedChatLoop(ChatLoop):
    """拡張版ChatLoop - EnhancedCompanionCore対応"""
    
    def __init__(self, task_queue: queue.Queue, status_queue: queue.Queue, 
                 enhanced_companion: EnhancedCompanionCore, context_manager: SharedContextManager):
        """拡張版ChatLoopを初期化
        
        Args:
            task_queue: タスクキュー
            status_queue: 状態キュー
            enhanced_companion: 拡張版CompanionCore
            context_manager: 共有コンテキスト管理
        """
        # 親クラス初期化（enhanced_companionを渡す）
        super().__init__(task_queue, status_queue, enhanced_companion, context_manager)
        
        # 拡張機能
        self.enhanced_companion = enhanced_companion
        self.agent_state = enhanced_companion.get_agent_state()
        
        # ログ設定
        self.logger = logging.getLogger(__name__)
    
    async def _handle_user_input_unified(self, user_input: str):
        """拡張版統一意図理解による入力処理"""
        try:
            # 1. 拡張版統一意図理解を実行
            intent_result = await self.enhanced_companion.analyze_intent_only(user_input)
            
            # 2. AgentStateの更新をコンテキストに反映
            if self.context_manager:
                session_summary = self.enhanced_companion.get_session_summary()
                self.context_manager.update_context("agent_state_summary", session_summary)
            
            # 3. ActionTypeに基づく処理分岐
            action_type = intent_result["action_type"]
            
            if action_type.value == "direct_response":
                # ChatLoop内で直接処理
                await self._handle_enhanced_direct_response(intent_result)
            else:
                # TaskLoopに送信（拡張版意図理解結果も含む）
                await self._handle_enhanced_task_with_intent(intent_result)
                
        except Exception as e:
            self.logger.error(f"拡張版統一意図理解エラー: {e}")
            # フォールバック: 既存システム
            await super()._handle_user_input_unified(user_input)
    
    async def _handle_enhanced_direct_response(self, intent_result: Dict[str, Any]):
        """拡張版直接応答を処理"""
        try:
            # EnhancedCompanionCoreで拡張応答を生成
            response = await self.enhanced_companion.process_with_intent_result(intent_result)
            
            from codecrafter.ui.rich_ui import rich_ui
            rich_ui.print_conversation_message("Duckflow Enhanced", response)
            
            # 拡張コンテキスト更新
            if self.context_manager:
                from datetime import datetime
                self.context_manager.update_context("last_enhanced_response", {
                    "type": "enhanced_direct_response",
                    "content": response,
                    "session_id": intent_result.get("session_id"),
                    "timestamp": datetime.now()
                })
                
        except Exception as e:
            self.logger.error(f"拡張版直接応答処理エラー: {e}")
            # フォールバック
            await super()._handle_direct_response(intent_result)
    
    async def _handle_enhanced_task_with_intent(self, intent_result: Dict[str, Any]):
        """拡張版タスクを意図理解結果と共に送信"""
        try:
            # TaskLoopに拡張タスクを送信
            from datetime import datetime
            task_data = {
                "type": "enhanced_task_with_intent",
                "intent_result": intent_result,
                "agent_state_summary": self.enhanced_companion.get_session_summary(),
                "timestamp": datetime.now()
            }
            
            self.task_queue.put(task_data)
            
            from codecrafter.ui.rich_ui import rich_ui
            rich_ui.print_message("🚀 拡張タスクを開始しました", "success")
            rich_ui.print_message("AgentState統合により高度なコンテキスト管理を実行中...", "info")
            
            # 拡張コンテキスト更新
            if self.context_manager:
                self.context_manager.update_context("last_enhanced_task", {
                    "type": "enhanced_task_started",
                    "action_type": intent_result["action_type"].value,
                    "message": intent_result["message"],
                    "session_id": intent_result.get("session_id"),
                    "timestamp": datetime.now()
                })
                
        except Exception as e:
            self.logger.error(f"拡張版タスク送信エラー: {e}")
            # フォールバック
            await super()._handle_task_with_intent(intent_result)


class EnhancedTaskLoop(TaskLoop):
    """拡張版TaskLoop - EnhancedCompanionCore対応"""
    
    def __init__(self, task_queue: queue.Queue, status_queue: queue.Queue,
                 enhanced_companion: EnhancedCompanionCore, context_manager: SharedContextManager):
        """拡張版TaskLoopを初期化
        
        Args:
            task_queue: タスクキュー
            status_queue: 状態キュー
            enhanced_companion: 拡張版CompanionCore
            context_manager: 共有コンテキスト管理
        """
        # 親クラス初期化（enhanced_companionを渡す）
        super().__init__(task_queue, status_queue, enhanced_companion, context_manager)
        
        # 拡張機能
        self.enhanced_companion = enhanced_companion
        self.agent_state = enhanced_companion.get_agent_state()
        
        # ログ設定
        self.logger = logging.getLogger(__name__)
    
    def _execute_task_unified(self, task_data):
        """拡張版統一タスク実行"""
        try:
            # タスクデータの種類を判定
            if isinstance(task_data, dict):
                if task_data.get("type") == "enhanced_task_with_intent":
                    # 拡張版: AgentState統合タスク
                    self._execute_enhanced_task_with_intent(task_data)
                elif task_data.get("type") == "task_with_intent":
                    # 標準版: 意図理解結果付きタスク
                    super()._execute_task_with_intent(task_data)
                else:
                    # 旧形式: 従来のタスク実行
                    super()._execute_task(task_data)
            else:
                # 旧形式: 文字列タスク
                super()._execute_task(task_data)
                
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.logger.error(f"拡張版統一タスク実行エラー: {e}")
            self.logger.error(f"詳細なエラー情報: {error_details}")
            self._send_status(f"❌ 拡張タスク実行エラー: {str(e)}")
            self.current_task = None
    
    def _execute_enhanced_task_with_intent(self, task_data: dict):
        """拡張版意図理解結果を活用したタスク実行
        
        Args:
            task_data: 拡張版意図理解結果を含むタスクデータ
        """
        intent_result = task_data["intent_result"]
        agent_state_summary = task_data.get("agent_state_summary", {})
        user_message = intent_result["message"]
        
        self.current_task = user_message
        self.logger.info(f"拡張版タスク実行開始: {user_message}")
        
        try:
            # 実行開始を通知
            self._send_status(f"🚀 拡張実行開始: {user_message[:50]}...")
            self._send_status(f"🧠 AgentState統合コンテキスト活用中...")
            
            # 拡張版意図理解結果を再利用してタスクを実行
            self.logger.info(f"EnhancedCompanionCoreで拡張処理開始: {user_message}")
            
            result = asyncio.run(self._process_enhanced_task_with_intent(intent_result, agent_state_summary))
            
            self.logger.info(f"EnhancedCompanionCoreからの結果: {len(result) if result else 0}文字")
            
            # 完了を通知
            if result:
                # 結果が長い場合は適切に切り詰める
                if len(result) > 200:
                    preview = result[:200] + "..."
                    self._send_status(f"✅ 拡張完了: {preview}")
                    # 完全な結果も送信
                    self._send_status(f"📄 拡張結果:\n{result}")
                else:
                    self._send_status(f"✅ 拡張完了: {result}")
            else:
                self._send_status("✅ 拡張タスクが完了しました（結果なし）")
            
            # 拡張コンテキスト更新
            if self.context_manager:
                from datetime import datetime
                self.context_manager.update_context("last_enhanced_task_result", {
                    "type": "enhanced_task_completed",
                    "result": result,
                    "action_type": intent_result["action_type"].value,
                    "session_id": intent_result.get("session_id"),
                    "agent_state_summary": agent_state_summary,
                    "timestamp": datetime.now()
                })
            
            self.logger.info(f"拡張タスク実行完了: {user_message}")
            
        except Exception as e:
            # エラーを通知
            error_msg = f"❌ 拡張エラー: {str(e)}"
            self._send_status(error_msg)
            self.logger.error(f"拡張タスク実行エラー: {e}")
            
            # 拡張コンテキスト更新
            if self.context_manager:
                from datetime import datetime
                self.context_manager.update_context("last_enhanced_task_error", {
                    "type": "enhanced_task_error",
                    "error": str(e),
                    "session_id": intent_result.get("session_id"),
                    "timestamp": datetime.now()
                })
        
        finally:
            self.current_task = None
    
    async def _process_enhanced_task_with_intent(self, intent_result: dict, agent_state_summary: dict) -> str:
        """拡張版意図理解結果を活用してタスクを処理
        
        Args:
            intent_result: analyze_intent_onlyの結果
            agent_state_summary: AgentStateのサマリー
            
        Returns:
            str: 処理結果
        """
        try:
            # 進捗を報告
            self._send_status("🔍 拡張意図理解結果を活用中...")
            
            # AgentStateから正確な会話数を取得
            conversation_count = intent_result.get('conversation_count', 0)
            if conversation_count == 0 and hasattr(self.enhanced_companion, 'state'):
                conversation_count = len(self.enhanced_companion.state.conversation_history)
            
            self._send_status(f"📊 セッション情報: {conversation_count}メッセージ (AgentState統合)")
            
            # 少し待機（進捗表示のため）
            await asyncio.sleep(0.5)
            
            # EnhancedCompanionCoreで拡張処理
            self._send_status("⚙️ EnhancedCompanionCoreで高度な処理中...")
            result = await self.enhanced_companion.process_with_intent_result(intent_result)
            
            # 結果の検証
            if not result or result.strip() == "":
                return "拡張タスクは完了しましたが、結果が空でした。"
            
            return result
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.logger.error(f"拡張意図理解結果活用処理中にエラー: {e}")
            self.logger.error(f"詳細なエラー情報: {error_details}")
            return f"拡張タスク処理中にエラーが発生しました: {str(e)}"


class EnhancedDualLoopSystem:
    """拡張版Dual-Loop System - 既存システム完全統合版
    
    Step 2の改善:
    - AgentStateによる統一状態管理
    - ConversationMemoryによる自動記憶要約
    - PromptCompilerによる高度なプロンプト最適化
    - 既存システムとの完全統合
    """
    
    def __init__(self, session_id: Optional[str] = None):
        """拡張システムを初期化
        
        Args:
            session_id: セッションID（省略時は自動生成）
        """
        # セッションID
        self.session_id = session_id or str(uuid.uuid4())
        
        # ループ間通信用のキュー
        self.task_queue = queue.Queue()
        self.status_queue = queue.Queue()
        
        # 拡張版CompanionCore（既存システム統合）
        self.enhanced_companion = EnhancedCompanionCore(self.session_id)
        
        # 共有コンテキスト管理
        self.context_manager = SharedContextManager()
        
        # 拡張版ループの初期化
        self.chat_loop = EnhancedChatLoop(
            self.task_queue,
            self.status_queue,
            self.enhanced_companion,
            self.context_manager
        )
        
        self.task_loop = EnhancedTaskLoop(
            self.task_queue,
            self.status_queue,
            self.enhanced_companion,
            self.context_manager
        )
        
        # スレッド管理
        self.task_thread: Optional[threading.Thread] = None
        self.running = False
        
        # ログ設定
        self.logger = logging.getLogger(__name__)
    
    def start(self):
        """拡張システムを開始"""
        if self.running:
            self.logger.warning("拡張システムは既に動作中です")
            return
        
        self.running = True
        
        # 開始メッセージ
        from codecrafter.ui.rich_ui import rich_ui
        rich_ui.print_message("🦆 Enhanced Dual-Loop System v2.0 起動中...", "success")
        rich_ui.print_message(f"📋 セッションID: {self.session_id}", "info")
        rich_ui.print_message("🧠 AgentState統合 | 💾 ConversationMemory | 🎯 PromptCompiler", "info")
        
        # TaskLoopをバックグラウンドで開始
        self.task_thread = threading.Thread(
            target=self.task_loop.run,
            daemon=True,
            name="EnhancedTaskLoop"
        )
        self.task_thread.start()
        
        self.logger.info("Enhanced Dual-Loop System を開始しました")
        
        # ChatLoopをメインスレッドで実行
        try:
            self.chat_loop.run()
        except KeyboardInterrupt:
            self.logger.info("ユーザーによる終了要求")
        finally:
            self.stop()
    
    def stop(self):
        """拡張システムを停止"""
        if not self.running:
            return
        
        self.logger.info("Enhanced Dual-Loop System を停止中...")
        
        # 各ループに停止を通知
        self.running = False
        self.chat_loop.stop()
        self.task_loop.stop()
        
        # TaskLoopスレッドの終了を待機
        if self.task_thread and self.task_thread.is_alive():
            self.task_thread.join(timeout=5.0)
            if self.task_thread.is_alive():
                self.logger.warning("EnhancedTaskLoopの停止がタイムアウトしました")
        
        self.logger.info("Enhanced Dual-Loop System を停止しました")
    
    def get_status(self) -> Dict[str, Any]:
        """拡張システムの状態を取得"""
        base_status = {
            "running": self.running,
            "session_id": self.session_id,
            "enhanced_mode": self.enhanced_companion.use_enhanced_mode,
            "chat_loop_active": self.chat_loop.running if hasattr(self.chat_loop, 'running') else False,
            "task_loop_active": self.task_loop.running if hasattr(self.task_loop, 'running') else False,
            "task_queue_size": self.task_queue.qsize(),
            "status_queue_size": self.status_queue.qsize(),
            "current_task": getattr(self.task_loop, 'current_task', None)
        }
        
        # AgentStateの情報を追加
        try:
            agent_summary = self.enhanced_companion.get_session_summary()
            base_status["agent_state"] = agent_summary
        except Exception as e:
            base_status["agent_state_error"] = str(e)
        
        # コンテキスト管理の情報を追加
        try:
            context_status = self.context_manager.get_status()
            base_status["context_manager"] = context_status
        except Exception as e:
            base_status["context_manager_error"] = str(e)
        
        return base_status
    
    def get_agent_state(self):
        """AgentStateを取得"""
        return self.enhanced_companion.get_agent_state()
    
    def toggle_enhanced_mode(self, enabled: bool = None) -> bool:
        """拡張モードの切り替え"""
        return self.enhanced_companion.toggle_enhanced_mode(enabled)


# デフォルトインスタンス
enhanced_dual_loop_system = EnhancedDualLoopSystem()