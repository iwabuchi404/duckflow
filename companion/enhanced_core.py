"""
EnhancedCompanionCore - Step 2: 既存システム統合版
AgentState、ConversationMemory、PromptCompilerとの統合
"""

import asyncio
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime

# 既存システムとの統合
from codecrafter.state.agent_state import AgentState
from codecrafter.memory.conversation_memory import conversation_memory
from codecrafter.prompts.prompt_compiler import prompt_compiler
from codecrafter.prompts.context_builder import PromptContextBuilder
from codecrafter.base.llm_client import llm_manager
from codecrafter.ui.rich_ui import rich_ui

# 既存のCompanionCore機能
from .core import CompanionCore, ActionType
from .shared_context_manager import SharedContextManager


class EnhancedCompanionCore:
    """既存システム統合版CompanionCore
    
    Step 2の改善:
    - AgentStateによる統一状態管理
    - ConversationMemoryによる自動記憶要約
    - PromptCompilerによる高度なプロンプト最適化
    - PromptContextBuilderによる構造化コンテキスト管理
    """
    
    def __init__(self, session_id: Optional[str] = None):
        """初期化
        
        Args:
            session_id: セッションID（省略時は自動生成）
        """
        # AgentStateを初期化
        self.state = AgentState(
            session_id=session_id or str(uuid.uuid4())
        )
        
        # 既存システムとの統合
        self.memory_manager = conversation_memory
        self.prompt_compiler = prompt_compiler
        self.context_builder = PromptContextBuilder()
        
        # 既存のCompanionCoreも保持（フォールバック用）
        self.legacy_companion = CompanionCore()
        
        # 統合モードフラグ
        self.use_enhanced_mode = True
        
        # ログ設定
        import logging
        self.logger = logging.getLogger(__name__)
    
    async def analyze_intent_only(self, user_message: str) -> Dict[str, Any]:
        """統合版意図理解（AgentState活用）
        
        Args:
            user_message: ユーザーからのメッセージ
            
        Returns:
            Dict: 意図理解結果
        """
        try:
            if self.use_enhanced_mode:
                return await self._analyze_intent_enhanced(user_message)
            else:
                # フォールバック: 既存システム使用
                return await self.legacy_companion.analyze_intent_only(user_message)
                
        except Exception as e:
            self.logger.error(f"統合版意図理解エラー: {e}")
            # フォールバック
            return await self.legacy_companion.analyze_intent_only(user_message)
    
    async def _analyze_intent_enhanced(self, user_message: str) -> Dict[str, Any]:
        """拡張版意図理解（既存システム活用）
        
        Args:
            user_message: ユーザーメッセージ
            
        Returns:
            Dict: 意図理解結果
        """
        # AgentStateに記録（同期問題を解決）
        self.state.add_message("user", user_message)
        
        # 記憶管理（自動要約）
        if self.state.needs_memory_management():
            success = self.state.create_memory_summary()
            if success:
                rich_ui.print_message("🧠 会話履歴を要約しました", "info")
        
        # 既存CompanionCoreの会話履歴も同期
        self._sync_conversation_history()
        
        # 既存の意図理解システムを活用
        if hasattr(self.legacy_companion, 'use_new_intent_system') and self.legacy_companion.use_new_intent_system:
            action_type = await self.legacy_companion._analyze_intent_new_system(user_message)
            understanding_result = getattr(self.legacy_companion, 'last_understanding_result', None)
        else:
            action_type = self.legacy_companion._analyze_intent_legacy(user_message)
            understanding_result = None
        
        return {
            "action_type": action_type,
            "understanding_result": understanding_result,
            "message": user_message,
            "enhanced_mode": True,
            "session_id": self.state.session_id,
            "conversation_count": len(self.state.conversation_history)  # 同期確認用
        }
    
    async def process_with_intent_result(self, intent_result: Dict[str, Any]) -> str:
        """統合版意図理解結果処理
        
        Args:
            intent_result: analyze_intent_onlyの結果
            
        Returns:
            str: 応答メッセージ
        """
        try:
            if self.use_enhanced_mode and intent_result.get("enhanced_mode"):
                return await self._process_with_enhanced_context(intent_result)
            else:
                # フォールバック: 既存システム使用
                return await self.legacy_companion.process_with_intent_result(intent_result)
                
        except Exception as e:
            self.logger.error(f"統合版処理エラー: {e}")
            # フォールバック
            return await self.legacy_companion.process_with_intent_result(intent_result)
    
    async def _process_with_enhanced_context(self, intent_result: Dict[str, Any]) -> str:
        """拡張コンテキストでの処理
        
        Args:
            intent_result: 意図理解結果
            
        Returns:
            str: 処理結果
        """
        user_message = intent_result["message"]
        action_type = intent_result["action_type"]
        
        # 思考過程表示
        self.legacy_companion._show_thinking_process(user_message)
        
        # 高度なコンテキスト構築
        context = await self._build_enhanced_context(action_type)
        
        # システムプロンプトをコンパイル
        system_prompt = self.prompt_compiler.compile_system_prompt_dto(context)
        
        # アクション実行（既存ロジック活用）
        if action_type == ActionType.DIRECT_RESPONSE:
            result = await self._generate_enhanced_response(user_message, system_prompt)
        elif action_type == ActionType.FILE_OPERATION:
            result = await self._handle_enhanced_file_operation(user_message, system_prompt)
        elif action_type == ActionType.CODE_EXECUTION:
            result = self.legacy_companion._handle_code_execution(user_message)
        else:
            result = self.legacy_companion._handle_multi_step_task(user_message)
        
        # AgentStateに応答を記録
        self._sync_from_legacy_to_agent_state(user_message, result)
        
        return result
    
    async def _build_enhanced_context(self, action_type: ActionType) -> Any:
        """拡張コンテキストを構築
        
        Args:
            action_type: アクションタイプ
            
        Returns:
            PromptContext: 構築されたコンテキスト
        """
        # テンプレート選択
        template_name = "system_base"
        if action_type == ActionType.FILE_OPERATION:
            template_name = "system_rag_enhanced"
        
        # ファイルコンテキスト収集（簡易版）
        file_context = await self._collect_file_context()
        
        # RAG検索（将来の拡張用）
        rag_results = None  # 現在は未実装
        
        # PromptContextを構築
        context = self.context_builder.from_agent_state(
            state=self.state,
            template_name=template_name,
            rag_results=rag_results,
            file_context_dict=file_context
        ).with_token_budget(8000).build()
        
        return context
    
    async def _collect_file_context(self) -> Dict[str, Any]:
        """ファイルコンテキストを収集（簡易版）
        
        Returns:
            Dict: ファイルコンテキスト
        """
        # 現在は基本的な情報のみ
        # 将来的にはfile_toolsとの統合を予定
        return {
            "files_list": [],
            "file_contents": {},
            "read_request_targets": []
        }
    
    async def _generate_enhanced_response(self, user_message: str, system_prompt: str) -> str:
        """拡張版直接応答生成（Chatと同じ内容を使用）
        
        Args:
            user_message: ユーザーメッセージ
            system_prompt: システムプロンプト
            
        Returns:
            str: 応答メッセージ
        """
        try:
            rich_ui.print_message("💬 拡張コンテキストで応答を生成中...", "info")
            
            # Chatと同じ方式: システムプロンプト + 会話履歴 + 現在のメッセージ
            messages = [{"role": "system", "content": system_prompt}]

            # AgentStateの会話履歴を使用（最新20件）
            if self.state.conversation_history:
                recent_history = self.state.conversation_history[-20:]
                for msg in recent_history:
                    if msg.role in ["user", "assistant"]:
                        messages.append({"role": msg.role, "content": msg.content})
            
            # 現在のユーザーメッセージを最後に追加
            messages.append({"role": "user", "content": user_message})
            
            # LLM実行
            response = llm_manager.chat_with_history(messages)
            
            rich_ui.print_message("✨ 拡張応答を生成しました！", "success")
            return response
            
        except Exception as e:
            self.logger.error(f"拡張応答生成エラー: {e}")
            # フォールバック: 既存システム
            return self.legacy_companion._generate_direct_response(user_message)
    
    async def _handle_enhanced_file_operation(self, user_message: str, system_prompt: str) -> str:
        """拡張版ファイル操作処理（シンプル版）
        
        Args:
            user_message: ユーザーメッセージ
            system_prompt: システムプロンプト
            
        Returns:
            str: 処理結果
        """
        try:
            rich_ui.print_message("📁 ファイル操作タスクとして処理中...", "info")
            
            # シンプルなアプローチ: 既存のファイル操作ロジックを活用
            # ただし、AgentStateの会話履歴を同期してから実行
            self._sync_conversation_history()
            return self.legacy_companion._handle_file_operation(user_message)
            
        except Exception as e:
            self.logger.error(f"拡張ファイル操作エラー: {e}")
            # フォールバック
            return self.legacy_companion._handle_file_operation(user_message)
    
    def get_agent_state(self) -> AgentState:
        """AgentStateを取得
        
        Returns:
            AgentState: 現在の状態
        """
        return self.state
    
    def get_session_summary(self) -> Dict[str, Any]:
        """セッションサマリーを取得
        
        Returns:
            Dict: セッション情報
        """
        base_summary = self.state.get_context_summary()
        
        # 記憶管理情報を追加
        memory_status = self.state.get_memory_status()
        
        return {
            **base_summary,
            "memory_status": memory_status,
            "enhanced_mode": self.use_enhanced_mode,
            "session_id": self.state.session_id
        }
    
    def toggle_enhanced_mode(self, enabled: bool = None) -> bool:
        """拡張モードの切り替え
        
        Args:
            enabled: 有効にするかどうか（Noneの場合はトグル）
            
        Returns:
            bool: 現在の拡張モード状態
        """
        if enabled is None:
            self.use_enhanced_mode = not self.use_enhanced_mode
        else:
            self.use_enhanced_mode = enabled
        
        mode_str = "有効" if self.use_enhanced_mode else "無効"
        rich_ui.print_message(f"🔧 拡張モード: {mode_str}", "info")
        
        return self.use_enhanced_mode
    
    def _sync_conversation_history(self):
        """AgentStateとlegacy CompanionCoreの会話履歴を同期
        
        AgentStateの会話履歴をlegacy CompanionCoreに反映させる
        """
        try:
            # AgentStateの会話履歴をlegacy形式に変換
            legacy_history = []
            
            for msg in self.state.conversation_history:
                if msg.role == "user":
                    # ユーザーメッセージの場合、次のアシスタントメッセージとペアにする
                    user_content = msg.content
                    assistant_content = ""
                    
                    # 対応するアシスタントメッセージを探す
                    msg_index = self.state.conversation_history.index(msg)
                    if msg_index + 1 < len(self.state.conversation_history):
                        next_msg = self.state.conversation_history[msg_index + 1]
                        if next_msg.role == "assistant":
                            assistant_content = next_msg.content
                    
                    # legacy形式のエントリを作成
                    if assistant_content:  # ペアが揃っている場合のみ追加
                        legacy_entry = {
                            "user": user_content,
                            "assistant": assistant_content,
                            "timestamp": msg.timestamp,
                            "session_time": (msg.timestamp - self.state.created_at).total_seconds()
                        }
                        legacy_history.append(legacy_entry)
            
            # legacy CompanionCoreの履歴を更新
            with self.legacy_companion._history_lock:
                self.legacy_companion.conversation_history = legacy_history
            
            self.logger.info(f"会話履歴を同期しました: AgentState({len(self.state.conversation_history)}) → Legacy({len(legacy_history)})")
            
        except Exception as e:
            self.logger.error(f"会話履歴同期エラー: {e}")
    
    def _sync_from_legacy_to_agent_state(self, user_message: str, assistant_response: str):
        """legacy CompanionCoreからAgentStateに会話を同期
        
        Args:
            user_message: ユーザーメッセージ
            assistant_response: アシスタント応答
        """
        try:
            # AgentStateに応答を記録（ユーザーメッセージは既に記録済み）
            self.state.add_message("assistant", assistant_response)
            
            self.logger.info(f"AgentStateに応答を記録: {len(assistant_response)}文字")
            
        except Exception as e:
            self.logger.error(f"AgentState同期エラー: {e}")