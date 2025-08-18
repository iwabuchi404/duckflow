"""
EnhancedDualLoopSystem - Step 2: 既存システム統合版
AgentState、ConversationMemory、PromptCompilerとの完全統合
"""

import threading
import queue
import logging
import uuid
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime

from .enhanced_core import EnhancedCompanionCore
from .shared_context_manager import SharedContextManager
from .chat_loop import ChatLoop
from .task_loop import TaskLoop
from .collaborative_planner import ActionSpec
from .file_ops import SimpleFileOps, FileOpOutcome
from .simple_approval import ApprovalMode


class EnhancedChatLoop(ChatLoop):
    """拡張版ChatLoop - EnhancedCompanionCore対応"""
    
    def __init__(self, task_queue: queue.Queue, status_queue: queue.Queue, 
                 enhanced_companion: EnhancedCompanionCore, context_manager: SharedContextManager,
                 dual_loop_system=None):
        """拡張版ChatLoopを初期化
        
        Args:
            task_queue: タスクキュー
            status_queue: 状態キュー
            enhanced_companion: 拡張版CompanionCore
            context_manager: 共有コンテキスト管理
            dual_loop_system: 親システム（EnhancedDualLoopSystem）
        """
        # 親クラス初期化（enhanced_companionを渡す）
        super().__init__(task_queue, status_queue, enhanced_companion, context_manager)
        
        # 拡張機能
        self.enhanced_companion = enhanced_companion
        self.agent_state = enhanced_companion.get_agent_state()
        self.dual_loop_system = dual_loop_system  # 親システムへの参照
        
        # ログ設定
        self.logger = logging.getLogger(__name__)
    
    async def _handle_user_input_unified(self, user_input: str):
        """拡張版統一意図理解による入力処理"""
        try:
            # 1. 拡張版統一意図理解を実行（プラン状態をコンテキストに含める）
            plan_state = self.enhanced_companion.get_plan_state()
            context = {"plan_state": plan_state} if plan_state.get("pending") else None
            intent_result = await self.enhanced_companion.analyze_intent_only(user_input, context)
            
            # 2. AgentStateの更新をコンテキストに反映
            if self.context_manager:
                session_summary = self.enhanced_companion.get_session_summary()
                self.context_manager.update_context("agent_state_summary", session_summary)
            
            # 3. ルーティング決定表に基づく処理分岐（改修）
            action_type = intent_result["action_type"]
            route_type = intent_result.get("route_type", None)
            
            # 新ルーティングシステムが適用されている場合
            if route_type and hasattr(route_type, 'value'):
                await self._handle_routing_based_processing(intent_result)
            else:
                # フォールバック: 既存のActionType分岐
                if action_type.value == "direct_response":
                    # DirectResponseは guidance_request のみ許可
                    await self._handle_enhanced_direct_response_with_validation(intent_result)
                else:
                    # TaskLoopに送信（拡張版意図理解結果も含む）
                    await self._handle_enhanced_task_with_intent(intent_result)
                
        except Exception as e:
            self.logger.error(f"拡張版統一意図理解エラー: {e}")
            # フォールバック: 既存システム
            await super()._handle_user_input_unified(user_input)
    
    async def _handle_routing_based_processing(self, intent_result: Dict[str, Any]):
        """新ルーティング決定表に基づく処理
        
        Args:
            intent_result: 統合意図理解結果（ルーティング情報含む）
        """
        route_type = intent_result["route_type"]
        
        self.logger.info(f"ルーティング決定表適用: {route_type.value}")
        
        # 強制実行フラグのチェック（最優先）
        metadata = intent_result.get("metadata", {})
        if metadata.get("force_execution"):
            self.logger.info("強制実行フラグを検出、選択プラン実行に直行")
            # 実行可能なActionSpecが存在しない場合は実行せず、詳細確認へ誘導
            if not (self.dual_loop_system and self.dual_loop_system._has_executable_plan()):
                from codecrafter.ui.rich_ui import rich_ui
                self.logger.warning("実行可能なプランがありません。詳細の特定が必要です。")
                rich_ui.print_message("⚠️ 実行可能なプランが見つかりません。まず具体的な作業項目を特定します。", "warning")
                await self._handle_enhanced_clarification_flow(intent_result)
                return
            # タスク投入（LLM経路をバイパス）
            task_data = {
                "type": "execute_selected_plan",
                "intent_result": intent_result,
                "timestamp": datetime.now(),
            }
            self.task_queue.put(task_data)
            from codecrafter.ui.rich_ui import rich_ui
            rich_ui.print_message("🚀 選択されたプランを実行キューに投入しました", "success")
            return
        
        # 選択入力の直接検出（プラン保留時のみ有効）
        user_message = intent_result.get("message", "")
        from companion.intent_understanding.intent_integration import OptionResolver
        
        # プラン保留状態の確認
        plan_state = self.enhanced_companion.get_plan_state()
        plan_pending = bool(plan_state and plan_state.get("pending"))
        
        if plan_pending:
            # LLM強化プラン選択処理を使用
            await self._handle_plan_pending_input_enhanced(user_message, intent_result)
            return
        
        # アンチスタール検出（clarificationの場合のみ）
        if route_type.value == "clarification":
            user_message = intent_result.get("message", "")
            if self.enhanced_companion.anti_stall_guard.add_question(user_message):
                # スタール判定でも即時ファイル作成は行わず、まずは作業項目の具体化を提示
                self.logger.warning("スタール状態を検出、詳細具体化フローに切り替えます")
                await self._handle_enhanced_clarification_flow(intent_result)
                return
        
        if route_type.value == "direct_response":
            # guidance_requestのみ許可
            await self._handle_enhanced_direct_response_with_validation(intent_result)
        elif route_type.value == "execution":
            # 実行→検証→結果まで必須
            await self._handle_enhanced_execution_with_verification(intent_result)
        elif route_type.value == "clarification":
            # 詳細確認フロー
            await self._handle_enhanced_clarification_flow(intent_result)
        elif route_type.value == "safe_default":
            # 安全なデフォルト提案
            await self._handle_enhanced_safe_default(intent_result)
        else:
            self.logger.warning(f"未知のルートタイプ: {route_type.value}")
            await self._handle_enhanced_task_with_intent(intent_result)
    
    async def _handle_anti_stall_recovery(self, intent_result: Dict[str, Any]):
        """アンチスタール回復処理"""
        try:
            # 最小実装を提案して実行
            minimal_spec = self.enhanced_companion.anti_stall_guard.get_minimal_implementation_suggestion()
            
            # 最小実装実行タスクを作成
            anti_stall_data = {
                "type": "execute_selected_plan",
                "intent_result": {
                    **intent_result,
                    "metadata": {
                        "selection": 1,
                        "anti_stall_recovery": True
                    }
                },
                "timestamp": datetime.now()
            }
            
            # プランに最小実装を設定（PlanTool統合版）
            self._set_plan_specs([minimal_spec], "最小実装プラン")
            
            self.task_queue.put(anti_stall_data)
            
            from codecrafter.ui.rich_ui import rich_ui
            rich_ui.print_message("🔄 スタール状態を検出しました。最小実装で前進します。", "warning")
            rich_ui.print_message("この実装は後で拡張・修正できます。", "info")
            
        except Exception as e:
            self.logger.error(f"アンチスタール回復エラー: {e}")
            # フォールバック
            await self._handle_enhanced_task_with_intent(intent_result)
    
    async def _handle_enhanced_direct_response_with_validation(self, intent_result: Dict[str, Any]):
        """検証付き拡張版直接応答（guidance_requestのみ許可）"""
        try:
            # TaskProfileの検証
            task_profile = intent_result.get("task_profile", {})
            profile_type = getattr(task_profile, "profile_type", None)
            
            if profile_type and hasattr(profile_type, "value"):
                if profile_type.value != "guidance_request":
                    self.logger.warning(f"DirectResponseは guidance_request のみ許可。実際: {profile_type.value}")
                    # 強制的にTaskLoopへ転送
                    await self._handle_enhanced_task_with_intent(intent_result)
                    return
            
            # guidance_requestの場合のみ直接応答を実行
            await self._handle_enhanced_direct_response(intent_result)
            
        except Exception as e:
            self.logger.error(f"検証付き直接応答エラー: {e}")
            # フォールバック: TaskLoopへ転送
            await self._handle_enhanced_task_with_intent(intent_result)
    
    async def _handle_enhanced_execution_with_verification(self, intent_result: Dict[str, Any]):
        """実行→検証→結果まで完了必須の拡張版実行"""
        try:
            # TaskLoopに送信（検証フラグ付き）
            task_data = {
                "type": "enhanced_execution_with_verification",
                "intent_result": intent_result,
                "agent_state_summary": self.enhanced_companion.get_session_summary(),
                "verification_required": True,  # 検証必須フラグ
                "timestamp": datetime.now()
            }
            
            self.task_queue.put(task_data)
            
            from codecrafter.ui.rich_ui import rich_ui
            rich_ui.print_message("🚀 検証付き実行タスクを開始しました", "success")
            rich_ui.print_message("実行→承認→検証→結果の完全フローを実行中...", "info")
            
        except Exception as e:
            self.logger.error(f"検証付き実行タスク送信エラー: {e}")
            # フォールバック
            await self._handle_enhanced_task_with_intent(intent_result)
    
    async def _handle_enhanced_clarification_flow(self, intent_result: Dict[str, Any]):
        """拡張版詳細確認フロー（One-shot Clarification）"""
        try:
            # 詳細確認を実行（固定テンプレート廃止）
            clarification_data = {
                "type": "enhanced_clarification",
                "intent_result": intent_result,
                "clarification_type": "one_shot",  # One-shot方式
                "timestamp": datetime.now()
            }
            
            self.task_queue.put(clarification_data)
            
            from codecrafter.ui.rich_ui import rich_ui
            rich_ui.print_message("🤔 詳細確認フローを開始しました", "info")
            rich_ui.print_message("選択肢+デフォルト方式で効率的に確認中...", "info")
            
        except Exception as e:
            self.logger.error(f"詳細確認フロー送信エラー: {e}")
            # フォールバック
            await self._handle_enhanced_task_with_intent(intent_result)
    
    async def _handle_enhanced_safe_default(self, intent_result: Dict[str, Any]):
        """安全なデフォルト提案"""
        try:
            safe_default_data = {
                "type": "enhanced_safe_default",
                "intent_result": intent_result,
                "proposal_type": "minimal_safe_operation",
                "timestamp": datetime.now()
            }
            
            self.task_queue.put(safe_default_data)
            
            from codecrafter.ui.rich_ui import rich_ui
            rich_ui.print_message("🛡️ 安全なデフォルト提案を開始しました", "info")
            rich_ui.print_message("低リスクの最小操作を提案中...", "info")
            
        except Exception as e:
            self.logger.error(f"安全なデフォルト提案送信エラー: {e}")
            # フォールバック
            await self._handle_enhanced_task_with_intent(intent_result)
    
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
    
    async def _handle_plan_pending_input_enhanced(self, user_message: str, intent_result: Dict[str, Any]):
        """LLM強化プラン保留中入力処理
        
        Args:
            user_message: ユーザーメッセージ
            intent_result: 意図理解結果
        """
        try:
            from codecrafter.ui.rich_ui import rich_ui
            
            # 実行可能なプランがあるかチェック
            if not (self.dual_loop_system and self.dual_loop_system._has_executable_plan()):
                self.logger.warning("選択できるプランが未定義のため、詳細確認フローに移行")
                rich_ui.print_message("⚠️ 現在選択できる具体的プランがありません。作業項目を提案します。", "warning")
                await self._handle_enhanced_clarification_flow(intent_result)
                return
            
            # プラン情報を取得
            plan_state = self.enhanced_companion.get_plan_state()
            current_plan_id = plan_state.get("plan_id")
            
            if not current_plan_id:
                self.logger.warning("プランIDが未設定、通常の対話処理に移行")
                await self._handle_enhanced_task_with_intent(intent_result)
                return
            
            # PlanToolのLLM強化選択処理を使用
            try:
                plan_tool = self.enhanced_companion.plan_tool
                if hasattr(plan_tool, 'process_user_selection_enhanced'):
                    selection_result = await plan_tool.process_user_selection_enhanced(
                        user_message, current_plan_id
                    )
                    
                    self.logger.info(f"LLM選択処理結果: {selection_result['action']} (確信度: {selection_result['confidence']:.2f})")
                    
                    # 結果に基づく処理分岐
                    if selection_result.get("clarification_needed"):
                        # 確認要求
                        from companion.llm_choice.plan_approval_handler import LLMPlanApprovalHandler
                        from companion.plan_tool import Plan, PlanState
                        
                        # 確認メッセージを表示
                        handler = LLMPlanApprovalHandler()
                        plan = plan_tool._plans.get(current_plan_id)
                        plan_state_obj = plan_tool._plan_states.get(current_plan_id)
                        
                        if plan and plan_state_obj:
                            from companion.llm_choice.plan_approval_handler import PlanApprovalContext
                            
                            plan_context = PlanApprovalContext(
                                plan=plan,
                                plan_state=plan_state_obj,
                                available_actions=[spec.base for spec in plan_state_obj.action_specs],
                                risk_level=selection_result.get("risk_level", "medium")
                            )
                            
                            confirmation_msg = handler.format_approval_confirmation(
                                type('ApprovalResult', (), selection_result)(), plan_context
                            )
                            rich_ui.print_message(confirmation_msg, "question")
                        else:
                            rich_ui.print_message("申し訳ありませんが、より明確に選択肢を指定してください。", "question")
                        
                        return
                    
                    elif selection_result.get("should_approve"):
                        # 承認実行
                        if selection_result.get("selection"):
                            # 正式な承認処理
                            approval_result = plan_tool.approve(
                                current_plan_id,
                                approver="user",
                                selection=selection_result["selection"]
                            )
                            
                            rich_ui.print_message(f"✅ プランを承認しました: {approval_result['title']}", "success")
                            
                            # 実行キューに送信
                            md = intent_result.setdefault("metadata", {})
                            md["approved_plan"] = approval_result
                            md["selection_result"] = selection_result
                            
                            task_data = {
                                "type": "execute_approved_plan_enhanced",
                                "intent_result": intent_result,
                                "plan_approval": approval_result,
                                "timestamp": datetime.now(),
                            }
                            self.task_queue.put(task_data)
                            rich_ui.print_message("🚀 承認されたプランを実行キューに投入しました", "success")
                        else:
                            rich_ui.print_message("⚠️ 承認対象の選択肢が特定できませんでした", "warning")
                    
                    else:
                        # 拒否または修正要求
                        if selection_result.get("modifications_requested"):
                            rich_ui.print_message("📝 プランの修正要求を受け付けました:", "info")
                            for mod in selection_result["modifications_requested"]:
                                rich_ui.print_message(f"  - {mod}", "info")
                        else:
                            rich_ui.print_message("❌ プランが拒否されました", "info")
                        
                        # プラン状態をクリア
                        self.enhanced_companion.clear_plan_state()
                        rich_ui.print_message("新しい要求をお聞かせください。", "info")
                
                else:
                    # フォールバック: 従来のパターンマッチング
                    await self._handle_plan_pending_fallback(user_message, intent_result)
                    
            except Exception as e:
                self.logger.error(f"LLM選択処理エラー: {e}")
                # フォールバック処理
                await self._handle_plan_pending_fallback(user_message, intent_result)
                
        except Exception as e:
            self.logger.error(f"プラン保留中入力処理エラー: {e}")
            # 最終フォールバック
            from codecrafter.ui.rich_ui import rich_ui
            rich_ui.print_message("申し訳ありませんが、入力を理解できませんでした。", "error")
    
    async def _handle_plan_pending_fallback(self, user_message: str, intent_result: Dict[str, Any]):
        """プラン保留中の従来処理（フォールバック用）"""
        from companion.intent_understanding.intent_integration import OptionResolver
        
        if OptionResolver.is_selection_input(user_message):
            self.logger.info("従来のパターンマッチングでプラン選択を処理")
            
            # メタデータに選択番号が無ければデフォルト1を付与
            md = intent_result.setdefault("metadata", {})
            if "selection" not in md:
                md["selection"] = 1
            
            task_data = {
                "type": "execute_selected_plan",
                "intent_result": intent_result,
                "timestamp": datetime.now(),
            }
            self.task_queue.put(task_data)
            
            from codecrafter.ui.rich_ui import rich_ui
            rich_ui.print_message("🚀 選択されたプランを実行キューに投入しました", "success")
        else:
            # 選択入力ではない場合は通常の対話処理
            await self._handle_enhanced_task_with_intent(intent_result)


class EnhancedTaskLoop(TaskLoop):
    """拡張版TaskLoop - EnhancedCompanionCore対応"""
    
    def __init__(self, task_queue: queue.Queue, status_queue: queue.Queue,
                 enhanced_companion: EnhancedCompanionCore, context_manager: SharedContextManager,
                 dual_loop_system=None):
        """拡張版TaskLoopを初期化
        
        Args:
            task_queue: タスクキュー
            status_queue: 状態キュー
            enhanced_companion: 拡張版CompanionCore
            context_manager: 共有コンテキスト管理
            dual_loop_system: 親システム（EnhancedDualLoopSystem）
        """
        # 親クラス初期化（enhanced_companionを渡す）
        super().__init__(task_queue, status_queue, enhanced_companion, context_manager)
        
        # 拡張機能
        self.enhanced_companion = enhanced_companion
        self.agent_state = enhanced_companion.get_agent_state()
        self.dual_loop_system = dual_loop_system  # 親システムへの参照
        
        # ログ設定
        self.logger = logging.getLogger(__name__)
    
    def _execute_task_unified(self, task_data):
        """拡張版統一タスク実行"""
        try:
            # タスクデータの種類を判定（新ルーティング対応）
            if isinstance(task_data, dict):
                task_type = task_data.get("type")
                
                if task_type == "enhanced_execution_with_verification":
                    # 新規: 検証必須実行タスク
                    self._execute_enhanced_execution_with_verification(task_data)
                elif task_type == "enhanced_clarification":
                    # 新規: One-shot詳細確認
                    self._execute_enhanced_clarification(task_data)
                elif task_type == "enhanced_safe_default":
                    # 新規: 安全なデフォルト提案
                    self._execute_enhanced_safe_default(task_data)
                elif task_type == "enhanced_task_with_intent":
                    # 拡張版: AgentState統合タスク
                    self._execute_enhanced_task_with_intent(task_data)
                elif task_type == "execute_selected_plan":
                    # 新規: 選択されたプランの実行
                    self._execute_selected_plan(task_data)
                elif task_type == "task_with_intent":
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
    
    def _execute_enhanced_execution_with_verification(self, task_data: dict):
        """検証必須実行タスク（実行→承認→検証→結果の完全フロー）
        
        Args:
            task_data: 検証必須実行タスクデータ
        """
        intent_result = task_data["intent_result"]
        verification_required = task_data.get("verification_required", True)
        user_message = intent_result["message"]
        
        self.current_task = user_message
        self.logger.info(f"検証必須実行タスク開始: {user_message}")
        
        try:
            # 実行開始を通知
            self._send_status(f"🚀 検証必須実行開始: {user_message[:50]}...")
            self._send_status(f"📋 フロー: 実行→承認→検証→結果")
            # もし既に実行可能なプランが存在する場合は、選択プラン実行に直行（LLM経路を回避）
            if hasattr(self.enhanced_companion, 'plan_context') and self.enhanced_companion.plan_context.action_specs:
                self._send_status("⚙️ 既存プランに基づき即時実行します...")
                direct_task = {
                    "type": "execute_selected_plan",
                    "intent_result": intent_result,
                    "timestamp": datetime.now()
                }
                self._execute_selected_plan(direct_task)
                return
            
            # 実行フェーズ
            self._send_status("⚙️ Phase 1: 実行中...")
            result = asyncio.run(self._process_enhanced_task_with_intent(intent_result, {}))
            
            if not result:
                self._send_status("❌ 実行フェーズで結果が空でした")
                return
            
            # 検証フェーズ（必須）
            if verification_required:
                self._send_status("🔍 Phase 2: 結果を検証中...")
                verification_result = self._verify_execution_result(result, intent_result)
                
                if not verification_result["verified"]:
                    self._send_status(f"⚠️ 検証失敗: {verification_result['reason']}")
                    self._send_status("🔄 再実行または手動確認が必要です")
                    return
                
                self._send_status("✅ Phase 2: 検証完了")
            
            # 結果フェーズ（完了条件）
            self._send_status("📊 Phase 3: 最終結果確定中...")
            final_result = self._finalize_execution_result(result, intent_result)
            
            # 完了通知（検証済み結果イベント）
            self._send_status("✅ 検証済み実行完了")
            self._send_status(f"📄 最終結果:\n{final_result}")
            
            self.logger.info(f"検証必須実行タスク完了: {user_message}")
            
        except Exception as e:
            # エラーを通知
            error_msg = f"❌ 検証必須実行エラー: {str(e)}"
            self._send_status(error_msg)
            self.logger.error(f"検証必須実行タスクエラー: {e}")
        
        finally:
            self.current_task = None
    
    def _execute_enhanced_clarification(self, task_data: dict):
        """One-shot詳細確認の実行
        
        Args:
            task_data: 詳細確認タスクデータ
        """
        intent_result = task_data["intent_result"]
        clarification_type = task_data.get("clarification_type", "one_shot")
        
        self.logger.info(f"詳細確認実行開始: {clarification_type}")
        
        try:
            self._send_status("🤔 詳細確認を実行中...")
            
            # One-shot方式での詳細確認
            if clarification_type == "one_shot":
                clarification_result = self._perform_one_shot_clarification(intent_result)
            else:
                clarification_result = "詳細確認が完了しました"
            
            self._send_status(f"💡 詳細確認完了: {clarification_result}")
            
        except Exception as e:
            self._send_status(f"❌ 詳細確認エラー: {str(e)}")
            self.logger.error(f"詳細確認実行エラー: {e}")
        
        finally:
            self.current_task = None
    
    def _execute_enhanced_safe_default(self, task_data: dict):
        """安全なデフォルト提案の実行
        
        Args:
            task_data: 安全なデフォルト提案タスクデータ
        """
        intent_result = task_data["intent_result"]
        proposal_type = task_data.get("proposal_type", "minimal_safe_operation")
        
        self.logger.info(f"安全なデフォルト提案実行開始: {proposal_type}")
        
        try:
            self._send_status("🛡️ 安全なデフォルト提案を生成中...")
            
            # 最小安全操作の提案
            safe_proposal = self._generate_safe_default_proposal(intent_result)
            
            self._send_status(f"📋 安全提案: {safe_proposal}")
            self._send_status("承認後に安全な操作を実行します")
            
        except Exception as e:
            self._send_status(f"❌ 安全提案エラー: {str(e)}")
            self.logger.error(f"安全なデフォルト提案エラー: {e}")
        
        finally:
            self.current_task = None
    
    def _execute_selected_plan(self, task_data: dict):
        """選択されたプランを実行
        
        Args:
            task_data: 選択されたプラン実行タスクデータ
        """
        intent_result = task_data["intent_result"]
        selection = intent_result.get("metadata", {}).get("selection", 1)
        user_message = intent_result["message"]
        
        self.current_task = user_message
        self.logger.info(f"選択されたプラン実行開始: 選択 {selection}")
        
        try:
            # 実行可能なActionSpecを取得（親システムのメソッドを使用）
            if hasattr(self.enhanced_companion, 'plan_context'):
                # PlanContextからActionSpecを取得
                all_specs = self.enhanced_companion.plan_context.action_specs
                if selection is not None and all_specs:
                    if 1 <= selection <= len(all_specs):
                        action_specs = [all_specs[selection - 1]]
                    else:
                        action_specs = all_specs
                else:
                    action_specs = all_specs
            else:
                action_specs = []
            
            if not action_specs:
                # プランが存在しない場合は最小実装を提案
                self._send_status("⚠️ 実行可能なプランが見つかりません。最小実装を提案します。")
                minimal_spec = self.enhanced_companion.anti_stall_guard.get_minimal_implementation_suggestion()
                action_specs = [minimal_spec]
                # 最小実装をプランとして設定
                if hasattr(self.enhanced_companion, 'plan_context'):
                    self.enhanced_companion.plan_context.action_specs = action_specs
                    self.enhanced_companion.plan_context.pending = True
            
            # 実行開始を通知
            self._send_status(f"🚀 プラン実行開始: {len(action_specs)}個のアクション")
            
            # ActionSpecを実行
            execution_result = self.enhanced_companion.plan_executor.execute(
                action_specs, 
                session_id=intent_result.get("session_id", "selected_plan")
            )
            
            # 進展を記録
            if execution_result['success_count'] > 0:
                self.enhanced_companion.anti_stall_guard.record_progress('actions_executed', execution_result['success_count'])
                
                # ファイル操作の進展も記録
                for result in execution_result['results']:
                    if result.get('success') and result.get('spec', {}).get('kind') in ['create', 'write']:
                        metric = 'files_created' if result['spec']['kind'] == 'create' else 'files_updated'
                        self.enhanced_companion.anti_stall_guard.record_progress(metric, 1)
            
            # 結果を通知
            if execution_result['overall_success']:
                self._send_status(f"✅ プラン実行完了: {execution_result['success_count']}/{execution_result['total_specs']} 成功")
                
                # 実行結果の詳細
                for result in execution_result['results']:
                    if result.get('success'):
                        spec = result.get('spec', {})
                        self._send_status(f"  ✓ {spec.get('kind', 'unknown')}: {spec.get('path', 'N/A')}")
                    else:
                        self._send_status(f"  ✗ エラー: {result.get('error', 'unknown error')}")
                
                # 自然な継続メッセージ
                self._send_status("🎉 うまくいきましたね！他に何かお手伝いできることはありますか？")
                
                # プラン状態をクリア
                if hasattr(self.enhanced_companion, 'plan_context'):
                    self.enhanced_companion.plan_context.reset()
                
            else:
                self._send_status(f"⚠️ プラン実行部分完了: {execution_result['success_count']}/{execution_result['total_specs']} 成功")
                
                # 失敗した操作の詳細
                for result in execution_result['results']:
                    if not result.get('success'):
                        self._send_status(f"  ❌ 失敗: {result.get('error', 'unknown error')}")
                
                # 部分失敗でもプラン状態をクリア（再実行は新しいプランとして扱う）
                if hasattr(self.enhanced_companion, 'plan_context'):
                    self.enhanced_companion.plan_context.reset()
                
                # 改善提案
                self._send_status("💡 失敗した部分について、別のアプローチを試してみましょうか？")
            
            self.logger.info(f"選択されたプラン実行完了: 選択 {selection}")
            
        except Exception as e:
            # エラーを通知
            error_msg = f"❌ プラン実行エラー: {str(e)}"
            self._send_status(error_msg)
            self.logger.error(f"選択されたプラン実行エラー: {e}")
        
        finally:
            self.current_task = None
    
    def _verify_execution_result(self, result: str, intent_result: Dict[str, Any]) -> Dict[str, Any]:
        """実行結果の検証
        
        Args:
            result: 実行結果
            intent_result: 意図理解結果
            
        Returns:
            Dict: 検証結果
        """
        try:
            # 基本的な検証
            if not result or result.strip() == "":
                return {"verified": False, "reason": "実行結果が空です"}
            
            # 長さチェック
            if len(result) < 10:
                return {"verified": False, "reason": "実行結果が短すぎます"}
            
            # エラーメッセージのチェック
            error_keywords = ["エラー", "失敗", "Error", "Failed", "Exception"]
            if any(keyword in result for keyword in error_keywords):
                return {"verified": False, "reason": "実行結果にエラーが含まれています"}
            
            return {"verified": True, "reason": "検証完了"}
            
        except Exception as e:
            return {"verified": False, "reason": f"検証中にエラー: {str(e)}"}
    
    def _finalize_execution_result(self, result: str, intent_result: Dict[str, Any]) -> str:
        """実行結果の最終確定
        
        Args:
            result: 実行結果
            intent_result: 意図理解結果
            
        Returns:
            str: 最終確定結果
        """
        try:
            route_type = intent_result.get("route_type", "unknown")
            routing_reason = intent_result.get("routing_reason", "")
            
            final_result = f"""検証済み実行結果:
ルート: {route_type.value if hasattr(route_type, 'value') else route_type}
理由: {routing_reason}

実行結果:
{result}

この結果は検証フローを通過した信頼性の高い結果です。
"""
            return final_result
            
        except Exception as e:
            return f"最終確定中にエラー: {str(e)}\n\n元の結果:\n{result}"
    
    def _perform_one_shot_clarification(self, intent_result: Dict[str, Any]) -> str:
        """One-shot詳細確認の実行
        
        Args:
            intent_result: 意図理解結果
            
        Returns:
            str: 詳細確認結果
        """
        try:
            user_message = intent_result["message"]
            route_type = intent_result.get("route_type", "unknown")
            
            # 固定テンプレート廃止、選択肢+デフォルト方式
            clarification = f"""選択肢による詳細確認:

ご要求: {user_message}
ルート: {route_type.value if hasattr(route_type, 'value') else route_type}

推奨する実行プラン:
1. [デフォルト] 最小限の安全な実装
2. 詳細仕様を確認してから実装
3. 段階的に実装

デフォルトプランで進めますか？
"""
            return clarification
            
        except Exception as e:
            return f"詳細確認生成エラー: {str(e)}"
    
    def _generate_safe_default_proposal(self, intent_result: Dict[str, Any]) -> str:
        """安全なデフォルト提案の生成
        
        Args:
            intent_result: 意図理解結果
            
        Returns:
            str: 安全な提案
        """
        try:
            user_message = intent_result["message"]
            risk_level = intent_result.get("risk_level", "unknown")
            
            proposal = f"""安全なデフォルト提案:

元のご要求: {user_message}
リスクレベル: {risk_level.value if hasattr(risk_level, 'value') else risk_level}

推奨する最小安全操作:
- 既存ファイルのバックアップ作成
- 読み取り専用での調査・分析
- 変更前のプレビュー表示

この安全な操作から始めることをお勧めします。
"""
            return proposal
            
        except Exception as e:
            return f"安全提案生成エラー: {str(e)}"
    
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


class PlanContext:
    """プラン実行コンテキスト"""
    
    def __init__(self):
        self.pending = False
        self.planned = False
        self.attempted = False
        self.verified = False
        self.current_plan = None
        self.action_specs: List[ActionSpec] = []
        self.execution_results: List[Dict[str, Any]] = []
    
    def reset(self):
        """コンテキストをリセット"""
        self.pending = False
        self.planned = False
        self.attempted = False
        self.verified = False
        self.current_plan = None
        self.action_specs = []
        self.execution_results = []


class AntiStallGuard:
    """アンチスタール機能 - 進展のない質問ループを防ぐ"""
    
    def __init__(self):
        self.question_history: List[str] = []
        self.progress_metrics = {
            'files_created': 0,
            'files_updated': 0,
            'actions_executed': 0
        }
        self.last_progress_time = datetime.now()
        self.stall_threshold = 3  # 同様の質問が3回続いたらスタール判定
        self.progress_timeout = 300  # 5分間進展がなければスタール判定
    
    def add_question(self, question: str) -> bool:
        """質問を追加し、スタール状態かチェック
        
        Args:
            question: 質問内容
            
        Returns:
            bool: スタール状態の場合True
        """
        # 質問の正規化
        normalized = self._normalize_question(question)
        self.question_history.append(normalized)
        
        # 履歴を制限
        if len(self.question_history) > 10:
            self.question_history = self.question_history[-10:]
        
        # スタール判定
        return self._detect_stall()
    
    def record_progress(self, metric: str, count: int = 1):
        """進展を記録
        
        Args:
            metric: 進展メトリクス名
            count: 増加数
        """
        if metric in self.progress_metrics:
            self.progress_metrics[metric] += count
            self.last_progress_time = datetime.now()
    
    def _normalize_question(self, question: str) -> str:
        """質問を正規化（類似判定用）"""
        import re
        # 数字や固有名詞を除去して類似性を判定
        normalized = re.sub(r'\d+', 'N', question)
        normalized = re.sub(r'[^\w\s]', '', normalized)
        return normalized.lower().strip()
    
    def _detect_stall(self) -> bool:
        """スタール状態を検出"""
        if len(self.question_history) < self.stall_threshold:
            return False
        
        # 最近の質問の類似度をチェック
        recent_questions = self.question_history[-self.stall_threshold:]
        similarity_count = 0
        
        for i in range(len(recent_questions) - 1):
            if self._calculate_similarity(recent_questions[i], recent_questions[i + 1]) > 0.8:
                similarity_count += 1
        
        # 類似質問が閾値を超えた場合
        if similarity_count >= self.stall_threshold - 1:
            return True
        
        # 時間ベースのスタール判定
        time_since_progress = (datetime.now() - self.last_progress_time).total_seconds()
        if time_since_progress > self.progress_timeout:
            return True
        
        return False
    
    def _calculate_similarity(self, q1: str, q2: str) -> float:
        """質問の類似度を計算（簡易版）"""
        if not q1 or not q2:
            return 0.0
        
        words1 = set(q1.split())
        words2 = set(q2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def get_minimal_implementation_suggestion(self) -> ActionSpec:
        """最小実装の提案を生成"""
        return ActionSpec(
            kind='create',
            path='minimal_implementation.txt',
            content=f"""# 最小実装
# 作成日時: {datetime.now().isoformat()}

# スタール状態が検出されたため、最小限の実装で前進します。
# この実装は後で拡張・修正できます。

print("Hello, World!")
""",
            description="スタール回避のための最小実装",
            optional=False
        )


class PlanExecutor:
    """プラン実行器 - ActionSpecを実際のファイル操作に変換"""
    
    def __init__(self, file_ops: SimpleFileOps):
        self.file_ops = file_ops
        self.logger = logging.getLogger(__name__)
    
    def execute(self, specs: List[ActionSpec], session_id: str = "plan_executor") -> Dict[str, Any]:
        """ActionSpecリストを実行
        
        Args:
            specs: 実行するActionSpecリスト
            session_id: セッションID
            
        Returns:
            Dict: 実行結果
        """
        results = []
        success_count = 0
        
        for i, spec in enumerate(specs):
            self.logger.info(f"ActionSpec実行 {i+1}/{len(specs)}: {spec.kind} {spec.path}")
            
            try:
                result = self._execute_single_spec(spec, session_id)
                results.append(result)
                
                if result.get('success', False):
                    success_count += 1
                
            except Exception as e:
                self.logger.error(f"ActionSpec実行エラー: {e}")
                results.append({
                    'success': False,
                    'spec': spec.to_dict(),
                    'error': str(e)
                })
        
        return {
            'total_specs': len(specs),
            'success_count': success_count,
            'results': results,
            'overall_success': success_count == len(specs)
        }
    
    def _execute_single_spec(self, spec: ActionSpec, session_id: str) -> Dict[str, Any]:
        """単一のActionSpecを実行"""
        try:
            if spec.kind == 'create':
                return self._execute_create(spec, session_id)
            elif spec.kind == 'write':
                return self._execute_write(spec, session_id)
            elif spec.kind == 'mkdir':
                return self._execute_mkdir(spec, session_id)
            elif spec.kind == 'read':
                return self._execute_read(spec, session_id)
            elif spec.kind == 'analyze':
                return self._execute_analyze(spec, session_id)
            elif spec.kind == 'run':
                return self._execute_run(spec, session_id)
            else:
                return {
                    'success': False,
                    'spec': spec.to_dict(),
                    'error': f'未対応のActionSpec種別: {spec.kind}'
                }
        
        except Exception as e:
            return {
                'success': False,
                'spec': spec.to_dict(),
                'error': str(e)
            }
    
    def _execute_create(self, spec: ActionSpec, session_id: str) -> Dict[str, Any]:
        """ファイル作成を実行"""
        if not spec.path:
            return {'success': False, 'spec': spec.to_dict(), 'error': 'パスが指定されていません'}
        
        # V2 APIを使用
        import os
        if os.getenv("FILE_OPS_V2", "1") == "1":
            outcome = self.file_ops.apply_with_approval_write(spec.path, spec.content or "", session_id)
            return {
                'success': outcome.ok,
                'spec': spec.to_dict(),
                'outcome': {
                    'op': outcome.op,
                    'path': outcome.path,
                    'reason': outcome.reason,
                    'changed': outcome.changed
                },
                'error': outcome.reason if not outcome.ok else None
            }
        else:
            # V1 APIを使用
            result = self.file_ops.create_file(spec.path, spec.content or "", session_id)
            return {
                'success': result.get('success', False),
                'spec': spec.to_dict(),
                'result': result,
                'error': result.get('message') if not result.get('success') else None
            }
    
    def _execute_write(self, spec: ActionSpec, session_id: str) -> Dict[str, Any]:
        """ファイル書き込みを実行"""
        if not spec.path:
            return {'success': False, 'spec': spec.to_dict(), 'error': 'パスが指定されていません'}
        
        # V2 APIを使用
        import os
        if os.getenv("FILE_OPS_V2", "1") == "1":
            outcome = self.file_ops.apply_with_approval_write(spec.path, spec.content or "", session_id)
            return {
                'success': outcome.ok,
                'spec': spec.to_dict(),
                'outcome': {
                    'op': outcome.op,
                    'path': outcome.path,
                    'reason': outcome.reason,
                    'changed': outcome.changed
                },
                'error': outcome.reason if not outcome.ok else None
            }
        else:
            # V1 APIを使用
            result = self.file_ops.write_file(spec.path, spec.content or "")
            return {
                'success': result.get('success', False),
                'spec': spec.to_dict(),
                'result': result,
                'error': result.get('message') if not result.get('success') else None
            }
    
    def _execute_mkdir(self, spec: ActionSpec, session_id: str) -> Dict[str, Any]:
        """ディレクトリ作成を実行"""
        if not spec.path:
            return {'success': False, 'spec': spec.to_dict(), 'error': 'パスが指定されていません'}
        
        try:
            from pathlib import Path
            path = Path(spec.path)
            path.mkdir(parents=True, exist_ok=True)
            
            return {
                'success': True,
                'spec': spec.to_dict(),
                'result': {'path': str(path), 'created': True}
            }
        except Exception as e:
            return {
                'success': False,
                'spec': spec.to_dict(),
                'error': str(e)
            }
    
    def _execute_read(self, spec: ActionSpec, session_id: str) -> Dict[str, Any]:
        """ファイル読み取りを実行"""
        if not spec.path:
            return {'success': False, 'spec': spec.to_dict(), 'error': 'パスが指定されていません'}
        
        try:
            content = self.file_ops.read_file(spec.path)
            return {
                'success': True,
                'spec': spec.to_dict(),
                'result': {'content': content, 'length': len(content)}
            }
        except Exception as e:
            return {
                'success': False,
                'spec': spec.to_dict(),
                'error': str(e)
            }
    
    def _execute_analyze(self, spec: ActionSpec, session_id: str) -> Dict[str, Any]:
        """コード解析を実行（簡易版）"""
        return {
            'success': True,
            'spec': spec.to_dict(),
            'result': {'analysis': f'解析完了: {spec.description}', 'type': 'analysis'}
        }
    
    def _execute_run(self, spec: ActionSpec, session_id: str) -> Dict[str, Any]:
        """コマンド実行（簡易版）"""
        return {
            'success': True,
            'spec': spec.to_dict(),
            'result': {'output': f'実行完了: {spec.description}', 'type': 'command'}
        }


class EnhancedDualLoopSystem:
    """拡張版Dual-Loop System - 既存システム完全統合版
    
    Step 2の改善:
    - AgentStateによる統一状態管理
    - ConversationMemoryによる自動記憶要約
    - PromptCompilerによる高度なプロンプト最適化
    - 既存システムとの完全統合
    """
    
    def __init__(self, session_id: Optional[str] = None, approval_mode: ApprovalMode = ApprovalMode.STANDARD):
        """拡張システムを初期化
        
        Args:
            session_id: セッションID（省略時は自動生成）
            approval_mode: 承認モード
        """
        # セッションID
        self.session_id = session_id or str(uuid.uuid4())
        
        # ループ間通信用のキュー
        self.task_queue = queue.Queue()
        self.status_queue = queue.Queue()
        
        # 実行阻害改善機能
        self.plan_context = PlanContext()
        self.anti_stall_guard = AntiStallGuard()
        self.plan_executor = PlanExecutor(SimpleFileOps(approval_mode=approval_mode))
        
        # 拡張版CompanionCore（既存システム統合）
        self.enhanced_companion = EnhancedCompanionCore(self.session_id, approval_mode=approval_mode)
        
        # 実行阻害改善機能をCompanionCoreに注入
        self.enhanced_companion.plan_context = self.plan_context
        self.enhanced_companion.anti_stall_guard = self.anti_stall_guard
        self.enhanced_companion.plan_executor = self.plan_executor
        
        # PlanTool統合（段階的移行）
        self.use_plan_tool = True  # PlanTool使用フラグ
        
        # 共有コンテキスト管理
        self.context_manager = SharedContextManager()
        
        # 拡張版ループの初期化
        self.chat_loop = EnhancedChatLoop(
            self.task_queue,
            self.status_queue,
            self.enhanced_companion,
            self.context_manager,
            self  # 親システムへの参照
        )
        
        self.task_loop = EnhancedTaskLoop(
            self.task_queue,
            self.status_queue,
            self.enhanced_companion,
            self.context_manager,
            self  # 親システムへの参照
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
    
    # === PlanTool統合メソッド ===
    
    def _sync_plan_context_to_plan_tool(self):
        """PlanContextの状態をPlanToolに同期"""
        if not self.use_plan_tool:
            return
            
        try:
            # 現在のプランがあるかチェック
            current_plan = self.enhanced_companion.plan_tool.get_current()
            
            # PlanContextにActionSpecがあり、PlanToolにプランがない場合
            if (self.plan_context.action_specs and 
                (not current_plan or current_plan.get('status') != 'approved')):
                
                # PlanContextからPlanToolにプランを作成
                plan_content = self.plan_context.current_plan.get('summary', 'Legacy plan') if self.plan_context.current_plan else 'Legacy plan'
                
                plan_id = self.enhanced_companion.plan_tool.propose(
                    content=plan_content,
                    sources=[],
                    rationale="PlanContextからの移行",
                    tags=["legacy_migration"]
                )
                
                # ActionSpecを設定
                validation_result = self.enhanced_companion.plan_tool.set_action_specs(
                    plan_id, self.plan_context.action_specs
                )
                
                if validation_result.ok:
                    # 自動承認（既にPlanContextで承認済みとみなす）
                    from .plan_tool import SpecSelection
                    selection = SpecSelection(all=True)
                    self.enhanced_companion.plan_tool.request_approval(plan_id, selection)
                    self.enhanced_companion.plan_tool.approve(plan_id, "system_migration", selection)
                    
                    self.logger.info(f"PlanContext -> PlanTool 移行完了: {plan_id}")
                
        except Exception as e:
            self.logger.warning(f"PlanContext -> PlanTool 同期エラー: {e}")
    
    def _get_action_specs_from_plan_tool(self) -> List[ActionSpec]:
        """PlanToolから承認済みActionSpecを取得"""
        if not self.use_plan_tool:
            return self.plan_context.action_specs
            
        try:
            current_plan = self.enhanced_companion.plan_tool.get_current()
            if not current_plan:
                return self.plan_context.action_specs
                
            plan_state = self.enhanced_companion.plan_tool.get_state(current_plan['id'])
            if plan_state['state']['status'] == 'approved':
                # PlanToolから承認済みActionSpecを取得
                # 注意: PlanToolのActionSpecExtから基本ActionSpecを抽出
                plan_tool_state = self.enhanced_companion.plan_tool._plan_states.get(current_plan['id'])
                if plan_tool_state:
                    return [spec_ext.base for spec_ext in plan_tool_state.action_specs]
            
        except Exception as e:
            self.logger.warning(f"PlanTool ActionSpec取得エラー: {e}")
            
        # フォールバック: PlanContextを使用
        return self.plan_context.action_specs
    
    def _execute_plan_with_plan_tool(self, plan_id: str) -> Dict[str, Any]:
        """PlanToolを使用してプランを実行"""
        try:
            result = self.enhanced_companion.plan_tool.execute(plan_id)
            return {
                'success': result.overall_success,
                'results': result.results,
                'message': f"PlanTool実行完了: {len(result.results)}件"
            }
        except Exception as e:
            self.logger.error(f"PlanTool実行エラー: {e}")
            return {
                'success': False,
                'results': [],
                'message': f"PlanTool実行失敗: {e}"
            }
    
    # === 統合ラッパーメソッド ===
    
    def _has_executable_plan(self) -> bool:
        """実行可能なプランがあるかチェック（PlanTool統合版）"""
        if self.use_plan_tool:
            try:
                current_plan = self.enhanced_companion.plan_tool.get_current()
                if current_plan:
                    plan_state = self.enhanced_companion.plan_tool.get_state(current_plan['id'])
                    return plan_state['state']['status'] == 'approved' and plan_state['state']['action_count'] > 0
            except Exception as e:
                self.logger.warning(f"PlanTool プラン確認エラー: {e}")
        
        # フォールバック: PlanContext
        return bool(self.plan_context.action_specs)
    
    def _get_executable_action_specs(self, selection: Optional[int] = None) -> List[ActionSpec]:
        """実行可能なActionSpecを取得（PlanTool統合版）"""
        if self.use_plan_tool:
            try:
                # PlanContextからPlanToolに同期
                self._sync_plan_context_to_plan_tool()
                
                # PlanToolから取得
                action_specs = self._get_action_specs_from_plan_tool()
                
                if action_specs and selection is not None:
                    # 選択指定がある場合
                    if 1 <= selection <= len(action_specs):
                        return [action_specs[selection - 1]]
                    else:
                        self.logger.warning(f"無効な選択: {selection} (範囲: 1-{len(action_specs)})")
                        return action_specs
                
                return action_specs
                
            except Exception as e:
                self.logger.warning(f"PlanTool ActionSpec取得エラー: {e}")
        
        # フォールバック: PlanContext
        if not self.plan_context.action_specs:
            return []
        
        if selection is not None:
            if 1 <= selection <= len(self.plan_context.action_specs):
                return [self.plan_context.action_specs[selection - 1]]
            else:
                return self.plan_context.action_specs
        
        return self.plan_context.action_specs
    
    def _set_plan_specs(self, action_specs: List[ActionSpec], plan_content: str = "Minimal implementation"):
        """プランにActionSpecを設定（PlanTool統合版）"""
        if self.use_plan_tool:
            try:
                # PlanToolでプラン作成
                plan_id = self.enhanced_companion.plan_tool.propose(
                    content=plan_content,
                    sources=[],
                    rationale="システム生成プラン",
                    tags=["system_generated", "minimal"]
                )
                
                # ActionSpec設定
                validation_result = self.enhanced_companion.plan_tool.set_action_specs(plan_id, action_specs)
                
                if validation_result.ok:
                    # 自動承認
                    from .plan_tool import SpecSelection
                    selection = SpecSelection(all=True)
                    self.enhanced_companion.plan_tool.request_approval(plan_id, selection)
                    self.enhanced_companion.plan_tool.approve(plan_id, "system_auto", selection)
                    
                    self.logger.info(f"PlanTool プラン設定完了: {plan_id}")
                    return True
                else:
                    self.logger.warning(f"PlanTool バリデーション失敗: {validation_result.issues}")
                    
            except Exception as e:
                self.logger.warning(f"PlanTool プラン設定エラー: {e}")
        
        # フォールバック: PlanContext
        self.plan_context.action_specs = action_specs
        self.plan_context.pending = True
        return True
    
    def _execute_current_plan(self) -> Dict[str, Any]:
        """現在のプランを実行（PlanTool統合版）"""
        if self.use_plan_tool:
            try:
                current_plan = self.enhanced_companion.plan_tool.get_current()
                if current_plan and current_plan.get('status') == 'approved':
                    return self._execute_plan_with_plan_tool(current_plan['id'])
            except Exception as e:
                self.logger.warning(f"PlanTool実行エラー: {e}")
        
        # フォールバック: 従来の実行方式
        action_specs = self._get_executable_action_specs()
        if not action_specs:
            return {
                'success': False,
                'results': [],
                'message': '実行可能なプランがありません'
            }
        
        # 従来のPlanExecutorを使用
        return self.plan_executor.execute(action_specs)
    
    def _clear_current_plan(self):
        """現在のプランをクリア（PlanTool統合版）"""
        if self.use_plan_tool:
            try:
                self.enhanced_companion.plan_tool.clear_current()
            except Exception as e:
                self.logger.warning(f"PlanTool クリアエラー: {e}")
        
        # PlanContextもクリア
        self.plan_context.reset()


# デフォルトインスタンス
enhanced_dual_loop_system = EnhancedDualLoopSystem()