"""
4ノード統合アーキテクチャ - LangGraphベースのシンプル化されたオーケストレーション

既存の7ノード構成を4ノードに統合し、情報伝達ロスを防ぎつつ
応答性と理解しやすさを向上させる。
"""

import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union
from pathlib import Path

from langchain.schema import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain.tools import BaseTool
from langgraph.graph import StateGraph, END
from pydantic import BaseModel

from ..base.llm_client import llm_manager, LLMClientError
from ..state.agent_state import (
    AgentState,
    ConversationMessage,
    ToolExecution,
    GraphState,
    WorkspaceInfo,
    TaskStep,
)
from ..tools.file_tools import file_tools, FileOperationError
from ..tools.rag_tools import rag_tools, RAGToolError
from ..tools.shell_tools import shell_tools, ShellExecutionError, ShellSecurityError
from ..prompts.four_node_compiler import FourNodePromptCompiler
from ..prompts.four_node_context import (
    FourNodePromptContext, NodeType, NextAction, RiskLevel,
    ExecutionPlan, UnderstandingResult, GatheredInfo, ExecutionResult, EvaluationResult,
    FileContent, ProjectContext, RiskAssessment, ApprovalStatus, ToolResult,
    ExecutionError, ErrorAnalysis, TaskStep as FourNodeTaskStep, RetryContext
)
from ..ui.rich_ui import rich_ui
from .routing_engine import RoutingEngine
from .four_node_helpers import FourNodeHelpers
from ..services import llm_service, task_objective_manager, TaskObjective, SatisfactionEvaluation


class FourNodeOrchestrator:
    """
    4ノード統合アーキテクチャ - 情報伝達ロスを防ぐシンプルなオーケストレーター
    
    4つのノード構成:
    1. 理解・計画ノード (Understanding & Planning)
    2. 情報収集ノード (Information Gathering)  
    3. 安全実行ノード (Safe Execution)
    4. 評価・継続ノード (Evaluation & Continuation)
    """
    
    def __init__(self, state: AgentState):
        """
        4ノードオーケストレーターを初期化
        
        Args:
            state: 既存のAgentState（7ノード版からの移行対応）
        """
        self.state = state
        self.routing_engine = RoutingEngine()
        self.prompt_compiler = FourNodePromptCompiler()
        
        # ヘルパーメソッドの初期化
        self.helpers = FourNodeHelpers(self.prompt_compiler, self.routing_engine)
        
        # 4ノード用の状態管理
        self.four_node_context = self._create_four_node_context()
        
        # LLMService統合
        self.llm_service = llm_service
        self.task_objective: Optional[TaskObjective] = None
        
        # LangGraphの構築
        self.graph = self._build_graph()
    
    def _create_four_node_context(self) -> FourNodePromptContext:
        """
        既存のAgentStateから4ノード用のPromptContextを作成
        """
        # ワークスペースパスの取得
        workspace_path = Path.cwd()
        if self.state.workspace and hasattr(self.state.workspace, 'path'):
            workspace_path = Path(self.state.workspace.path)
        
        # タスクチェーンの変換
        task_chain = []
        if hasattr(self.state, 'conversation_history') and self.state.conversation_history:
            for msg in self.state.conversation_history[-3:]:  # 直近3件
                if msg.role == 'user':
                    task = FourNodeTaskStep(
                        step_id=f"task_{len(task_chain)}",
                        user_message=msg.content,
                        timestamp=msg.timestamp if hasattr(msg, 'timestamp') else datetime.now()
                    )
                    task_chain.append(task)
        
        # タスクチェーンが空の場合はダミータスクを追加
        if not task_chain:
            task_chain.append(FourNodeTaskStep(
                step_id="initial_task",
                user_message="初期タスク",
                timestamp=datetime.now()
            ))
        
        # 会話履歴の更新（最新10件を保持）
        recent_messages = []
        if hasattr(self.state, 'conversation_history') and self.state.conversation_history:
            recent_messages = self.state.conversation_history[-10:]
        
        return FourNodePromptContext(
            current_node=NodeType.UNDERSTANDING,
            execution_phase=1,
            workspace_path=workspace_path,
            task_chain=task_chain,
            recent_messages=recent_messages
        )
    
    def _update_context_with_conversation(self) -> None:
        """4ノードコンテキストの会話履歴を最新状態に更新"""
        if hasattr(self.state, 'conversation_history') and self.state.conversation_history:
            # 最新の会話履歴を反映
            self.four_node_context.recent_messages = self.state.conversation_history[-10:]
            
            # タスクチェーンも更新
            new_tasks = []
            for msg in self.state.conversation_history[-3:]:
                if msg.role == 'user':
                    task = FourNodeTaskStep(
                        step_id=f"task_{len(new_tasks)}",
                        user_message=msg.content,
                        timestamp=msg.timestamp if hasattr(msg, 'timestamp') else datetime.now()
                    )
                    new_tasks.append(task)
            
            if new_tasks:
                self.four_node_context.task_chain = new_tasks
    
    def _build_graph(self) -> StateGraph:
        """4ノード構成のグラフを構築"""
        workflow = StateGraph(AgentState)
        
        # 4ノード定義
        workflow.add_node("理解・計画", self._understanding_planning_node)
        workflow.add_node("情報収集", self._information_gathering_node)
        workflow.add_node("安全実行", self._safe_execution_node)
        workflow.add_node("評価・継続", self._evaluation_continuation_node)
        
        # エントリーポイント
        workflow.set_entry_point("理解・計画")
        
        # フロー定義（シンプル化された分岐）
        workflow.add_conditional_edges(
            "理解・計画",
            self._after_understanding_planning,
            {
                "gather_info": "情報収集",
                "execute_directly": "安全実行", 
                "complete": END,
            },
        )
        
        workflow.add_conditional_edges(
            "情報収集",
            self._after_information_gathering,
            {
                "execute": "安全実行",
                "plan_again": "理解・計画",
                "evaluate": "評価・継続",
                "complete": END,
            },
        )
        
        workflow.add_edge("安全実行", "評価・継続")
        
        workflow.add_conditional_edges(
            "評価・継続",
            self._after_evaluation_continuation,
            {
                "continue": "理解・計画",
                "retry": "理解・計画",
                "complete": END,
            },
        )
        
        return workflow.compile()
    
    # ===== 4ノードメソッド =====
    
    def _understanding_planning_node(self, state: Any) -> AgentState:
        """
        ノード1: 理解・計画ノード（継続コンテキスト対応）
        
        責務:
        - ユーザー要求の深い理解
        - 実行計画の立案（初回 or 継続）
        - 必要な情報の特定
        - リスク要因の予測
        - 継続実行時の学習した制約の考慮
        """
        state_obj = AgentState.parse_obj(state) if isinstance(state, dict) else state
        
        try:
            # ループ制限チェック
            if state_obj.graph_state.loop_count >= state_obj.graph_state.max_loops:
                rich_ui.print_warning("ループ制限に達したため、処理を終了します")
                state_obj.add_message("assistant", "処理が複雑になりすぎたため、ここで終了させていただきます。")
                return state_obj
            
            # ノード状態の更新
            state_obj.update_graph_state(current_node="理解・計画", add_to_path="理解・計画")
            self.four_node_context.current_node = NodeType.UNDERSTANDING
            
            # 継続コンテキストの検出
            continuation_context = self._extract_continuation_context(state_obj)
            is_continuation = continuation_context is not None
            
            # Phase 1: 調査タスクかどうかの判定
            is_investigation_task = self._detect_investigation_task(state_obj)
            
            if is_continuation:
                # === 継続計画立案 ===
                rich_ui.print_step("🔄 継続計画立案フェーズ開始")
                rich_ui.print_message(f"継続実行: {self.task_objective.iteration_count}回目の計画立案", "info")
                
                understanding_result = self._execute_continuation_planning(state_obj, continuation_context)
                
                # 学習した制約を反映
                if continuation_context.learned_limitations:
                    rich_ui.print_message(f"学習制約を適用: {len(continuation_context.learned_limitations)}件", "info")
                
            elif is_investigation_task and not state_obj.investigation_plan:
                # === 調査計画立案 ===
                rich_ui.print_step("[調査計画] 立案フェーズ開始")
                
                # TaskObjectiveの初期化（初回のみ）
                if not self.task_objective:
                    self._initialize_task_objective_from_state(state_obj)
                
                understanding_result = self._execute_investigation_planning(state_obj)
                
            elif is_investigation_task and state_obj.investigation_plan:
                # === 調査計画が既にある場合（継続実行等）===
                rich_ui.print_step("📋 既存調査計画を使用")
                rich_ui.print_message(f"調査対象: {len(state_obj.investigation_plan)}ファイル", "info")
                
                # TaskObjectiveの初期化（初回のみ）
                if not self.task_objective:
                    self._initialize_task_objective_from_state(state_obj)
                
                understanding_result = self._create_investigation_understanding_result(state_obj)
                
            else:
                # === 初回計画立案 ===
                rich_ui.print_step("🧠 初回理解・計画フェーズ開始")
                
                # TaskObjectiveの初期化（初回のみ）
                if not self.task_objective:
                    self._initialize_task_objective_from_state(state_obj)
                
                understanding_result = self._execute_initial_planning(state_obj)
            
            # 結果の保存
            self.four_node_context.understanding = understanding_result
            state_obj.collected_context = state_obj.collected_context or {}
            state_obj.collected_context['understanding_result'] = self._serialize_understanding_result(understanding_result)
            
            # 結果表示
            planning_type = "継続計画" if is_continuation else "初回計画"
            rich_ui.print_success(f"{planning_type}完了: {understanding_result.requirement_analysis[:100]}...")
            
            # LLMの応答をユーザーに表示
            if understanding_result.requirement_analysis and len(understanding_result.requirement_analysis) > 10:
                rich_ui.print_step("💭 AI分析結果")
                rich_ui.print_message(understanding_result.requirement_analysis, "info")
            
            return state_obj
            
        except Exception as e:
            rich_ui.print_error(f"理解・計画ノードでエラー: {e}")
            state_obj.record_error(f"理解・計画エラー: {str(e)}")
            return state_obj
    
    def _information_gathering_node(self, state: Any) -> AgentState:
        """
        ノード2: 情報収集ノード（Phase 2-2: 統合分析対応）
        
        責務:
        - 計画に基づいた情報収集
        - ファイル読み取り・RAG検索
        - 調査タスク時の統合分析実行
        - プロジェクト文脈の構築
        - 情報の信頼度評価
        """
        state_obj = AgentState.parse_obj(state) if isinstance(state, dict) else state
        
        try:
            # ノード状態の更新
            state_obj.update_graph_state(current_node="情報収集", add_to_path="情報収集")
            self.four_node_context.current_node = NodeType.GATHERING
            
            rich_ui.print_step("📚 情報収集フェーズ開始")
            
            # 理解結果の取得
            understanding_result = self.four_node_context.understanding
            if not understanding_result:
                rich_ui.print_warning("理解結果が不足しています。計画ノードに戻ります。")
                return state_obj
            
            # Phase 2-2: 調査計画が存在する場合は統合分析を実行
            if state_obj.investigation_plan:
                rich_ui.print_step("[調査タスク] 統合分析を実行")
                return self._execute_investigation_synthesis(state_obj, understanding_result)
            
            # 従来の情報収集フロー
            # 1. 情報収集戦略の決定
            collection_strategy = self.helpers.determine_collection_strategy(understanding_result)
            
            # 2. ファイル情報の収集
            collected_files = self.helpers.collect_file_information(understanding_result, state_obj)
            
            # 3. RAG検索の実行
            rag_results = self.helpers.perform_rag_search(understanding_result, state_obj)
            
            # 4. プロジェクト理解の構築
            project_context = self.helpers.build_project_context(collected_files, state_obj)
            
            # 5. 情報の品質評価
            confidence_scores = self._evaluate_information_quality(collected_files, rag_results)
            
            # 6. 結果の構築と保存
            gathered_info = GatheredInfo(
                collected_files=collected_files,
                rag_results=rag_results,
                project_context=project_context,
                confidence_scores=confidence_scores,
                information_gaps=self._identify_information_gaps(understanding_result, collected_files),
                collection_strategy=collection_strategy
            )
            
            self.four_node_context.gathered_info = gathered_info
            state_obj.collected_context = state_obj.collected_context or {}
            state_obj.collected_context['gathered_info'] = self._serialize_gathered_info(gathered_info)
            
            rich_ui.print_success(f"情報収集完了: {len(collected_files)}ファイル, {len(rag_results)}件のRAG結果")
            
            return state_obj
            
        except Exception as e:
            rich_ui.print_error(f"情報収集ノードでエラー: {e}")
            state_obj.record_error(f"情報収集エラー: {str(e)}")
            return state_obj
    
    def _safe_execution_node(self, state: Any) -> AgentState:
        """
        ノード3: 安全実行ノード
        
        責務:
        - リスク評価の実行
        - 人間承認の取得（必要時）
        - ツールの安全な実行
        - 実行結果の記録
        """
        state_obj = AgentState.parse_obj(state) if isinstance(state, dict) else state
        
        try:
            # ノード状態の更新
            state_obj.update_graph_state(current_node="安全実行", add_to_path="安全実行")
            self.four_node_context.current_node = NodeType.EXECUTION
            
            rich_ui.print_step("⚡ 安全実行フェーズ開始")
            
            # 前段階結果の確認
            understanding_result = self.four_node_context.understanding
            gathered_info = self.four_node_context.gathered_info
            
            if not understanding_result:
                raise ValueError("実行には理解結果が必要です")
            
            # 1. リスク評価の実行
            risk_assessment = self.helpers.assess_execution_risks(understanding_result, gathered_info, state_obj)
            
            # 2. 承認プロセス（必要時）
            approval_status = self.helpers.handle_approval_process(risk_assessment, understanding_result, state_obj)
            
            # 3. 承認が得られた場合のみ実行
            tool_results = []
            execution_errors = []
            
            if approval_status.granted:
                tool_results, execution_errors = self._execute_planned_tools(understanding_result, gathered_info, state_obj)
            else:
                rich_ui.print_warning("承認が得られなかったため、実行をスキップします")
            
            # 4. 結果の構築と保存
            execution_result = ExecutionResult(
                risk_assessment=risk_assessment,
                approval_status=approval_status,
                tool_results=tool_results,
                execution_errors=execution_errors,
                partial_success=len(tool_results) > 0 and len(execution_errors) > 0
            )
            
            self.four_node_context.execution_result = execution_result
            state_obj.collected_context = state_obj.collected_context or {}
            state_obj.collected_context['execution_result'] = self._serialize_execution_result(execution_result)
            
            if execution_errors:
                rich_ui.print_warning(f"実行完了（エラーあり）: {len(execution_errors)}件のエラー")
            else:
                rich_ui.print_success(f"実行完了: {len(tool_results)}個のツールが成功")
            
            return state_obj
            
        except Exception as e:
            rich_ui.print_error(f"安全実行ノードでエラー: {e}")
            state_obj.record_error(f"安全実行エラー: {str(e)}")
            return state_obj
    
    def _evaluation_continuation_node(self, state: Any) -> AgentState:
        """
        ノード4: 評価・継続ノード（Phase 2-3: 調査タスク対応）
        
        責務:
        - 実行結果または調査結果の評価・検証
        - エラーの分析と修正提案
        - 次のアクションの決定
        - タスク完了判定
        """
        state_obj = AgentState.parse_obj(state) if isinstance(state, dict) else state
        
        try:
            # ノード状態の更新
            state_obj.update_graph_state(current_node="評価・継続", add_to_path="評価・継続")
            self.four_node_context.current_node = NodeType.EVALUATION
            
            rich_ui.print_step("[評価・継続] フェーズ開始")
            
            # 前段階結果の確認
            understanding_result = self.four_node_context.understanding
            execution_result = self.four_node_context.execution_result
            gathered_info = self.four_node_context.gathered_info
            
            rich_ui.print_message(f"評価ノード状態: understanding={'あり' if understanding_result else 'なし'}, execution={'あり' if execution_result else 'なし'}, gathered={'あり' if gathered_info else 'なし'}", "info")
            
            # Phase 2-3: 調査タスクの場合は異なる評価ロジック
            if state_obj.investigation_plan and state_obj.project_summary:
                rich_ui.print_step("[調査結果] 評価を実行")
                return self._evaluate_investigation_results(state_obj, understanding_result, gathered_info)
            
            # 従来の実行結果評価
            if not (understanding_result and execution_result):
                raise ValueError("評価には理解・実行結果が必要です")
            
            # 1. LLMServiceによるユーザー要求満足度の評価
            if self.task_objective:
                # 蓄積された結果を更新
                self.task_objective.accumulated_results.update({
                    'execution_result': execution_result.model_dump() if hasattr(execution_result, 'model_dump') else str(execution_result),
                    'gathered_info': gathered_info.model_dump() if gathered_info and hasattr(gathered_info, 'model_dump') else str(gathered_info),
                    'understanding': understanding_result.model_dump() if hasattr(understanding_result, 'model_dump') else str(understanding_result)
                })
                
                # LLMServiceによる満足度評価
                satisfaction_evaluation = self.llm_service.evaluate_task_satisfaction(
                    self.task_objective.original_query,
                    self.task_objective.accumulated_results,
                    self.four_node_context.operation_type
                )
                
                # TaskObjectiveの更新
                self.task_objective.update_satisfaction(satisfaction_evaluation)
                
                rich_ui.print_message(f"[LLM評価] 満足度: {satisfaction_evaluation.overall_score:.2f}/1.0", "info")
                rich_ui.print_message(f"[LLM評価] 完了推奨: {'はい' if satisfaction_evaluation.completion_recommendation else 'いいえ'}", "info")
                
                # 従来の評価も実行（互換性のため）
                success_status, completion_percentage = self._evaluate_execution_results(understanding_result, execution_result)
                
                # LLMServiceの評価を優先
                success_status = satisfaction_evaluation.completion_recommendation
                completion_percentage = satisfaction_evaluation.overall_score * 100
                
            else:
                # フォールバック: 従来の評価方法
                success_status, completion_percentage = self._evaluate_execution_results(understanding_result, execution_result)
                rich_ui.print_warning("[評価] TaskObjectiveが未設定、従来評価を使用")
            
            # 2. 継続判定とアクション決定（LLMService統合版）
            if self.task_objective:
                # TaskObjectiveベースの判定
                if self.task_objective.is_completed():
                    rich_ui.print_success(f"✅ タスク完了 (満足度: {self.task_objective.current_satisfaction:.2f})")
                    next_action = NextAction.COMPLETE
                    error_analysis = None
                    
                elif self.task_objective.should_continue():
                    rich_ui.print_message(f"🔄 継続実行 (試行 {self.task_objective.iteration_count}/{self.task_objective.max_iterations})", "info")
                    
                    # 継続のための詳細分析
                    missing_info = self.llm_service.extract_missing_information(
                        self.task_objective.original_query,
                        self.task_objective.accumulated_results
                    )
                    
                    # 継続コンテキストの構築
                    continuation_context = self._build_continuation_context(self.task_objective, missing_info)
                    
                    # 次の試行のための準備
                    next_action = NextAction.CONTINUE
                    error_analysis = None
                    
                    # 継続コンテキストを状態に保存
                    state_obj.continuation_context = continuation_context
                    
                else:
                    # 最大試行回数に達した場合 - ユーザーエスカレーション実行
                    rich_ui.print_warning(f"⏰ 最大試行回数に達しました ({self.task_objective.iteration_count}回)")
                    
                    # ユーザーエスカレーションを実行
                    escalation_result = self._escalate_to_user_guidance(satisfaction_evaluation)
                    
                    # エスカレーション結果に基づく次のアクション
                    if escalation_result.get('action') == 'continue_with_guidance':
                        # ユーザーが追加指示を提供した場合
                        next_action = NextAction.CONTINUE
                        # 新しい指示でTaskObjectiveをリセット
                        additional_context = escalation_result.get('additional_context', '')
                        if additional_context:
                            self.task_objective.reset_for_retry(preserve_learning=True)
                            # 継続コンテキストに追加情報を反映
                            continuation_context = self.task_objective.get_continuation_context()
                            state_obj.continuation_context = continuation_context
                    elif escalation_result.get('action') == 'complete_partial':
                        # 部分結果での完了
                        next_action = NextAction.COMPLETE
                    else:
                        # デフォルト（キャンセル等）
                        next_action = NextAction.COMPLETE
                    
                    error_analysis = None
            
            else:
                # フォールバック: 従来のエラー分析・判定
                error_analysis = None
                if execution_result.execution_errors:
                    error_analysis = self._analyze_execution_errors(execution_result, understanding_result)
                    
                    # タスク失敗時のユーザー確認
                    should_continue = self._ask_user_about_failure(understanding_result, execution_result, error_analysis)
                    if not should_continue:
                        next_action = NextAction.COMPLETE
                    else:
                        next_action = self._determine_next_action(success_status, completion_percentage, error_analysis)
                else:
                    next_action = self._determine_next_action(success_status, completion_percentage, error_analysis)
            
            # 4. 継続計画の作成（必要時）
            continuation_plan = None
            if next_action in [NextAction.CONTINUE, NextAction.RETRY]:
                continuation_plan = self._create_continuation_plan(understanding_result, execution_result, error_analysis)
            
            # 5. ユーザー満足度の予測
            user_satisfaction_prediction = self._predict_user_satisfaction(understanding_result, execution_result, success_status)
            
            # 6. 結果の構築と保存
            evaluation_result = EvaluationResult(
                success_status=success_status,
                completion_percentage=completion_percentage,
                next_action=next_action,
                quality_assessment=self._assess_quality(understanding_result, execution_result),
                user_satisfaction_prediction=user_satisfaction_prediction,
                error_analysis=error_analysis,
                continuation_plan=continuation_plan
            )
            
            self.four_node_context.evaluation = evaluation_result
            state_obj.collected_context = state_obj.collected_context or {}
            state_obj.collected_context['evaluation_result'] = self._serialize_evaluation_result(evaluation_result)
            
            # 7. 最終的なユーザー応答の生成
            final_response = self._generate_final_response(evaluation_result, understanding_result, execution_result)
            
            # ファイル内容が収集されている場合は、それも含めて応答
            if (self.four_node_context.gathered_info and 
                self.four_node_context.gathered_info.collected_files):
                rich_ui.print_message(f"ファイル応答生成中: {len(self.four_node_context.gathered_info.collected_files)}件のファイル", "info")
                file_content_response = self._generate_file_content_response(
                    self.four_node_context.gathered_info.collected_files,
                    understanding_result
                )
                final_response = file_content_response + "\n\n" + final_response
                rich_ui.print_message("ファイル内容を含む応答を生成しました", "info")
            else:
                rich_ui.print_warning("収集されたファイル情報が見つかりません")
            
            state_obj.add_message("assistant", final_response)
            
            action_text = {
                NextAction.COMPLETE: "完了",
                NextAction.CONTINUE: "継続",
                NextAction.RETRY: "再試行",
                NextAction.ERROR: "エラー"
            }.get(next_action, "不明")
            
            rich_ui.print_success(f"評価完了: {action_text} (完了率: {completion_percentage:.1%})")
            
            return state_obj
            
        except Exception as e:
            rich_ui.print_error(f"評価・継続ノードでエラー: {e}")
            state_obj.record_error(f"評価・継続エラー: {str(e)}")
            return state_obj
    
    # ===== 条件分岐メソッド =====
    
    def _after_understanding_planning(self, state: Any) -> str:
        """理解・計画ノード後の分岐判定"""
        state_obj = AgentState.parse_obj(state) if isinstance(state, dict) else state
        
        try:
            understanding_result = self.four_node_context.understanding
            if not understanding_result:
                return "complete"
            
            # 読み取り専用操作かチェック
            is_read_only = all(tool in ['read_file', 'list_files', 'get_file_info'] 
                              for tool in understanding_result.execution_plan.required_tools)
            
            # 読み取り専用で対象ファイルがある場合は情報収集へ
            if is_read_only and understanding_result.execution_plan.expected_files:
                return "gather_info"
            
            # 情報収集が必要な場合
            if understanding_result.information_needs:
                return "gather_info"
            
            # 実行計画が単純で情報収集不要な場合
            if (understanding_result.execution_plan.estimated_complexity == "low" and 
                len(understanding_result.execution_plan.expected_files) == 0):
                return "execute_directly"
            
            # デフォルトは情報収集
            return "gather_info"
            
        except Exception as e:
            rich_ui.print_error(f"理解・計画後の分岐判定エラー: {e}")
            return "complete"
    
    def _after_information_gathering(self, state: Any) -> str:
        """情報収集ノード後の分岐判定"""
        state_obj = AgentState.parse_obj(state) if isinstance(state, dict) else state
        
        try:
            gathered_info = self.four_node_context.gathered_info
            understanding_result = self.four_node_context.understanding
            
            if not gathered_info:
                return "complete"
            
            # 読み取り専用操作の場合は実行をスキップして直接評価へ
            if understanding_result:
                is_read_only = all(tool in ['read_file', 'list_files', 'get_file_info'] 
                                  for tool in understanding_result.execution_plan.required_tools)
                if is_read_only:
                    rich_ui.print_message("読み取り専用操作のため実行フェーズをスキップし、評価ノードへ", "info")
                    # 実行結果を模擬的に作成
                    self._create_mock_execution_result_for_read_only(understanding_result, gathered_info)
                    return "evaluate"  # 評価ノードへ
            
            # 重大な情報ギャップがある場合は再計画
            if gathered_info.information_gaps and len(gathered_info.information_gaps) > 2:
                return "plan_again"
            
            # 通常は実行へ
            return "execute"
            
        except Exception as e:
            rich_ui.print_error(f"情報収集後の分岐判定エラー: {e}")
            return "complete"
    
    def _after_evaluation_continuation(self, state: Any) -> str:
        """評価・継続ノード後の分岐判定"""
        state_obj = AgentState.parse_obj(state) if isinstance(state, dict) else state
        
        try:
            evaluation_result = self.four_node_context.evaluation
            if not evaluation_result:
                return "complete"
            
            # 次のアクションに基づく分岐
            if evaluation_result.next_action == NextAction.COMPLETE:
                return "complete"
            elif evaluation_result.next_action == NextAction.CONTINUE:
                # 継続計画で4ノードコンテキストを更新
                if evaluation_result.continuation_plan:
                    self._prepare_continuation_context(evaluation_result.continuation_plan)
                return "continue"
            elif evaluation_result.next_action == NextAction.RETRY:
                # リトライコンテキストを準備
                self._prepare_retry_context(evaluation_result.error_analysis)
                return "retry"
            else:
                return "complete"
                
        except Exception as e:
            rich_ui.print_error(f"評価・継続後の分岐判定エラー: {e}")
            return "complete"
    
    # ===== 実行メソッド =====
    
    def run(self, user_message: str) -> AgentState:
        """
        4ノードオーケストレーターのメイン実行メソッド
        
        Args:
            user_message: ユーザーからのメッセージ
            
        Returns:
            更新されたAgentState
        """
        try:
            # ユーザーメッセージをStateに追加
            self.state.add_message("user", user_message)
            
            # 会話履歴に基づく4ノードコンテキストの更新
            self._update_context_with_conversation()
            
            # 現在のタスクを追加
            current_task = FourNodeTaskStep(
                step_id=f"task_{len(self.four_node_context.task_chain)}",
                user_message=user_message,
                timestamp=datetime.now()
            )
            self.four_node_context.task_chain.append(current_task)
            
            rich_ui.print_info("🚀 4ノードオーケストレーション開始（会話履歴更新済み）")
            
            # グラフの実行
            result = self.graph.invoke(self.state)
            
            rich_ui.print_info("✅ 4ノードオーケストレーション完了")
            
            return result
            
        except Exception as e:
            rich_ui.print_error(f"4ノードオーケストレーション実行エラー: {e}")
            self.state.record_error(f"オーケストレーションエラー: {str(e)}")
            return self.state
    
    # ===== 未実装メソッドの簡易実装 =====
    
    def _evaluate_information_quality(self, collected_files: Dict[str, FileContent], rag_results: List) -> Dict[str, float]:
        """情報の品質評価"""
        return {
            "file_coverage": len(collected_files) / max(1, len(collected_files)),
            "rag_relevance": len(rag_results) / max(1, 3)  # 最大3クエリを想定
        }
    
    def _identify_information_gaps(self, understanding_result: UnderstandingResult, collected_files: Dict[str, FileContent]) -> List[str]:
        """情報ギャップの特定"""
        gaps = []
        expected_files = set(understanding_result.execution_plan.expected_files)
        collected_file_paths = set(collected_files.keys())
        missing_files = expected_files - collected_file_paths
        return [f"ファイル不足: {f}" for f in missing_files]
    
    def _execute_planned_tools(self, understanding_result: UnderstandingResult, gathered_info: GatheredInfo, state_obj: AgentState) -> Tuple[List[ToolResult], List[ExecutionError]]:
        """計画されたツールの実行"""
        tool_results = []
        execution_errors = []
        
        try:
            for tool_name in understanding_result.execution_plan.required_tools:
                if tool_name == "read_file":
                    # 読み取り専用操作：実際にはgathered_infoで既に読み取り済み
                    rich_ui.print_message("ファイル読み取りは情報収集段階で完了済み", "info")
                    
                    # gathered_infoから読み取り結果を確認
                    if gathered_info and gathered_info.collected_files:
                        for file_path in understanding_result.execution_plan.expected_files:
                            if file_path in gathered_info.collected_files:
                                file_content = gathered_info.collected_files[file_path]
                                tool_results.append(ToolResult(
                                    tool_name="read_file",
                                    success=True,
                                    output=f"ファイル {file_path} を読み取り完了 ({file_content.size}文字)"
                                ))
                            else:
                                execution_errors.append(ExecutionError(
                                    error_type="FileNotFound",
                                    message=f"ファイル {file_path} が見つかりません",
                                    file_path=file_path
                                ))
                    else:
                        execution_errors.append(ExecutionError(
                            error_type="NoFilesCollected",
                            message="情報収集段階でファイルが収集されませんでした"
                        ))
                
                elif tool_name == "list_files":
                    # ファイル一覧取得
                    try:
                        files = file_tools.list_files(".")
                        tool_results.append(ToolResult(
                            tool_name="list_files",
                            success=True,
                            output=f"ファイル一覧を取得しました ({len(files)}件)"
                        ))
                    except Exception as e:
                        execution_errors.append(ExecutionError(
                            error_type="FileListError",
                            message=str(e)
                        ))
                
        except Exception as e:
            execution_errors.append(ExecutionError(
                error_type="ToolExecutionError",
                message=str(e)
            ))
        
        return tool_results, execution_errors
    
    def _evaluate_execution_results(self, understanding_result: UnderstandingResult, execution_result: ExecutionResult) -> Tuple[bool, float]:
        """実行結果の評価"""
        if execution_result.execution_errors:
            return False, 0.3
        elif execution_result.tool_results:
            return True, 1.0
        else:
            return False, 0.0
    
    def _analyze_execution_errors(self, execution_result: ExecutionResult, understanding_result: UnderstandingResult) -> ErrorAnalysis:
        """実行エラーの分析"""
        if not execution_result.execution_errors:
            return None
            
        first_error = execution_result.execution_errors[0]
        return ErrorAnalysis(
            root_cause=f"エラータイプ: {first_error.error_type}",
            suggested_fixes=[f"修正提案: {first_error.message}"],
            confidence=0.7,
            similar_patterns=[],
            prevention_measures=["事前チェックを強化"]
        )
    
    def _determine_next_action(self, success_status: bool, completion_percentage: float, error_analysis: Optional[ErrorAnalysis]) -> NextAction:
        """次のアクションの決定"""
        if success_status:
            return NextAction.COMPLETE
        elif error_analysis and completion_percentage > 0.5:
            return NextAction.RETRY
        elif completion_percentage > 0:
            return NextAction.CONTINUE
        else:
            return NextAction.ERROR
    
    def _create_continuation_plan(self, understanding_result: UnderstandingResult, execution_result: ExecutionResult, error_analysis: Optional[ErrorAnalysis]) -> Optional[ExecutionPlan]:
        """継続計画の作成"""
        if error_analysis:
            return ExecutionPlan(
                summary=f"修正版: {understanding_result.execution_plan.summary}",
                steps=error_analysis.suggested_fixes,
                required_tools=understanding_result.execution_plan.required_tools,
                expected_files=understanding_result.execution_plan.expected_files,
                estimated_complexity=understanding_result.execution_plan.estimated_complexity,
                success_criteria=understanding_result.execution_plan.success_criteria
            )
        return None
    
    def _predict_user_satisfaction(self, understanding_result: UnderstandingResult, execution_result: ExecutionResult, success_status: bool) -> float:
        """ユーザー満足度の予測"""
        if success_status:
            return 0.9
        elif execution_result.partial_success:
            return 0.6
        else:
            return 0.3
    
    def _ask_user_about_failure(self, understanding_result: UnderstandingResult, execution_result: ExecutionResult, error_analysis: ErrorAnalysis) -> bool:
        """
        タスク失敗時にユーザーに対応を確認
        
        Args:
            understanding_result: 理解結果
            execution_result: 実行結果
            error_analysis: エラー分析結果
            
        Returns:
            bool: 続行するかどうか（True=続行、False=中断）
        """
        try:
            # エラー詳細の表示
            rich_ui.print_warning("⚠️ タスクの実行に問題が発生しました")
            
            error_info = f"""
[bold red]エラー詳細:[/]
• 原因: {error_analysis.root_cause}
• 完了率: {execution_result.partial_success_percentage:.1f}%

[bold yellow]提案される修正方法:[/]"""
            
            for i, fix in enumerate(error_analysis.suggested_fixes, 1):
                error_info += f"\n  {i}. {fix}"
            
            rich_ui.print_panel(error_info.strip(), "タスク実行エラー", "error")
            
            # ユーザーに選択肢を提示
            options_info = """
[bold cyan]次の対応を選択してください:[/]

1. **再試行** - 修正方法を適用して再度実行
2. **別のアプローチ** - 計画を見直して別の方法で実行  
3. **手動で詳細確認** - より詳しい情報を提供してもらう
4. **タスク中断** - このタスクを終了する
"""
            
            rich_ui.print_panel(options_info.strip(), "対応選択", "info")
            
            # ユーザーの選択を取得
            while True:
                choice = rich_ui.get_user_input("選択 (1-4)").strip()
                
                if choice == "1":
                    rich_ui.print_message("修正方法を適用して再試行します。", "info")
                    return True
                elif choice == "2":
                    rich_ui.print_message("計画を見直して別のアプローチを試します。", "info")
                    return True
                elif choice == "3":
                    rich_ui.print_message("より詳しい情報提供をお願いします。", "info")
                    user_feedback = rich_ui.get_user_input("詳しい要求や補足情報を入力してください")
                    
                    # ユーザーフィードバックを理解結果に追加
                    if hasattr(understanding_result, 'user_feedback'):
                        understanding_result.user_feedback.append(user_feedback)
                    else:
                        understanding_result.user_feedback = [user_feedback]
                    
                    rich_ui.print_message("フィードバックを受け取りました。処理を続行します。", "info")
                    return True
                elif choice == "4":
                    rich_ui.print_message("タスクを中断します。", "warning")
                    return False
                else:
                    rich_ui.print_warning("1-4の数字を入力してください。")
            
        except Exception as e:
            rich_ui.print_error(f"ユーザー確認中にエラー: {e}")
            # エラーが発生した場合は安全側に倒して続行を選択
            return True
    
    def _build_continuation_context(self, task_objective: TaskObjective, missing_info) -> 'ContinuationContext':
        """継続コンテキストの構築"""
        from ..services import ContinuationContext, AttemptResult
        
        # 現在の試行結果を記録
        current_attempt = AttemptResult(
            attempt_number=task_objective.iteration_count,
            strategy="initial" if task_objective.iteration_count == 0 else "continuation",
            execution_plan=task_objective.accumulated_results.get('understanding', {}),
            results=task_objective.accumulated_results,
            satisfaction_score=task_objective.current_satisfaction,
            errors=[],
            lessons_learned=[]
        )
        
        # 収集済みファイル情報を抽出（スコープを広げる）
        gathered_files = []
        if 'gathered_info' in task_objective.accumulated_results:
            gathered_files = self._extract_gathered_files(task_objective.accumulated_results['gathered_info'])
        
        # 学んだ教訓の抽出
        if task_objective.current_satisfaction < 0.5:
            current_attempt.lessons_learned.append("現在の情報では要求を満たせない")
        
        if gathered_files:
            current_attempt.lessons_learned.append(f"読み取り済みファイル: {len(gathered_files)}件")
        
        # TaskObjectiveに試行結果を追加
        task_objective.add_attempt_result(current_attempt)
        
        # 継続コンテキストを生成
        context = task_objective.get_continuation_context()
        context.missing_info = missing_info
        
        # suggested_improvementsがリストであることを確認
        if not isinstance(context.suggested_improvements, list):
            context.suggested_improvements = []
        
        # unavailable_resourcesがリストであることを確認
        if not isinstance(context.unavailable_resources, list):
            context.unavailable_resources = []
        
        # 具体的な改善提案を追加
        context.suggested_improvements.extend([
            "より多くのファイルを探索する",
            "異なるファイルタイプ（テスト、ドキュメント）を確認する", 
            "ファイル名パターンを拡張する"
        ])
        
        # 読み取り済みファイルを回避対象に追加
        if gathered_files:
            context.unavailable_resources.extend([f"already_read: {f}" for f in gathered_files])
        
        rich_ui.print_message(f"[継続] 改善提案: {len(context.suggested_improvements)}件", "info")
        rich_ui.print_message(f"[継続] 回避対象: {len(context.unavailable_resources)}件", "info")
        
        return context
    
    def _extract_gathered_files(self, gathered_info) -> List[str]:
        """収集された情報からファイル一覧を抽出"""
        try:
            if isinstance(gathered_info, str):
                # 文字列の場合、ファイルパターンを検索
                import re
                file_pattern = r'[A-Za-z]:\\[^\\]+\\[^\\]+\.py'
                files = re.findall(file_pattern, gathered_info)
                return files[:10]  # 最大10件
            elif isinstance(gathered_info, dict):
                # 辞書の場合、ファイル関連キーを探索
                files = []
                for key, value in gathered_info.items():
                    if 'file' in key.lower() and isinstance(value, (list, str)):
                        if isinstance(value, list):
                            files.extend([str(v) for v in value[:5]])
                        else:
                            files.append(str(value))
                return files[:10]
            return []
        except Exception:
            return []
    
    def _assess_quality(self, understanding_result: UnderstandingResult, execution_result: ExecutionResult) -> str:
        """品質の評価"""
        if execution_result.execution_errors:
            return f"エラーあり: {len(execution_result.execution_errors)}件"
        else:
            return "良好"
    
    def _generate_final_response(self, evaluation_result: EvaluationResult, understanding_result: UnderstandingResult, execution_result: ExecutionResult) -> str:
        """最終的なユーザー応答の生成"""
        if evaluation_result.success_status:
            return f"タスクが正常に完了しました。{understanding_result.execution_plan.summary}"
        else:
            error_info = ""
            if execution_result.execution_errors:
                error_info = f" エラー: {execution_result.execution_errors[0].message}"
            return f"タスクの実行で問題が発生しました。{error_info}"
    
    def _generate_file_content_response(self, collected_files: Dict[str, Any], understanding_result: UnderstandingResult) -> str:
        """ファイル内容を基にした応答を生成"""
        try:
            rich_ui.print_message(f"ファイル応答生成開始: {len(collected_files) if collected_files else 0}件", "info")
            
            if not collected_files:
                rich_ui.print_warning("収集されたファイルが空です")
                return "ファイルの読み取りに失敗しました。"
            
            response_parts = []
            
            # ファイルごとに内容を整理
            for file_path, file_content in collected_files.items():
                response_parts.append(f"## {file_path} の内容\n")
                
                if hasattr(file_content, 'content'):
                    content = file_content.content
                    if content.startswith("[読み取りエラー"):
                        response_parts.append(f"❌ {content}")
                    else:
                        # design-doc.mdの場合は概要を生成
                        if file_path.endswith('design-doc.md'):
                            response_parts.append(self._summarize_design_doc(content))
                        else:
                            # 他のファイルは最初の部分を表示
                            preview = content[:1000]
                            if len(content) > 1000:
                                preview += "...\n\n*（以下省略）*"
                            response_parts.append(preview)
                else:
                    response_parts.append("内容を取得できませんでした。")
                
                response_parts.append("\n---\n")
            
            return "\n".join(response_parts)
            
        except Exception as e:
            return f"ファイル内容の処理中にエラーが発生しました: {e}"
    
    def _summarize_design_doc(self, content: str) -> str:
        """design-doc.mdの内容を要約"""
        try:
            # 重要なセクションを抽出
            lines = content.split('\n')
            summary_parts = []
            
            # プロジェクトタイトルを抽出
            for line in lines[:10]:
                if line.startswith('# ') or line.startswith('## '):
                    summary_parts.append(f"**{line.strip('#').strip()}**")
                    break
            
            # 概要や目的を抽出
            for i, line in enumerate(lines):
                if any(keyword in line.lower() for keyword in ['概要', '目的', 'overview', '現在の状況']):
                    # その後の数行を取得
                    for j in range(i, min(i + 10, len(lines))):
                        if lines[j].strip() and not lines[j].startswith('#'):
                            summary_parts.append(lines[j].strip())
                            if len(summary_parts) > 5:
                                break
                    break
            
            # 技術スタックを抽出
            for i, line in enumerate(lines):
                if any(keyword in line.lower() for keyword in ['技術', 'tech', 'stack', 'アーキテクチャ']):
                    for j in range(i, min(i + 5, len(lines))):
                        if lines[j].strip():
                            summary_parts.append(lines[j].strip())
                    break
            
            return '\n'.join(summary_parts) if summary_parts else content[:500] + "..."
            
        except Exception:
            return content[:500] + "..."
    
    # シリアライゼーションメソッド
    def _serialize_understanding_result(self, result: UnderstandingResult) -> Dict[str, Any]:
        return {"summary": result.requirement_analysis}
    
    def _serialize_gathered_info(self, info: GatheredInfo) -> Dict[str, Any]:
        return {"file_count": len(info.collected_files)}
    
    def _serialize_execution_result(self, result: ExecutionResult) -> Dict[str, Any]:
        return {"success": len(result.execution_errors) == 0}
    
    def _serialize_evaluation_result(self, result: EvaluationResult) -> Dict[str, Any]:
        return {"status": result.success_status, "action": result.next_action.value}
    
    def _prepare_continuation_context(self, plan: ExecutionPlan) -> None:
        """継続用のコンテキスト準備"""
        self.four_node_context.execution_phase += 1
        self.four_node_context.current_node = NodeType.UNDERSTANDING
    
    def _prepare_retry_context(self, error_analysis: ErrorAnalysis) -> None:
        """再試行用のコンテキスト準備"""
        if error_analysis:
            self.four_node_context.retry_context = RetryContext(
                retry_count=1,
                previous_errors=[],  # 簡略化
                failure_analysis=error_analysis
            )
        self.four_node_context.execution_phase += 1
        self.four_node_context.current_node = NodeType.UNDERSTANDING
    
    def _create_mock_execution_result_for_read_only(self, understanding_result: UnderstandingResult, gathered_info: GatheredInfo) -> None:
        """読み取り専用操作用の模擬実行結果を作成"""
        rich_ui.print_message("読み取り専用操作用の模擬実行結果を作成中", "info")
        
        # 低リスクの評価
        risk_assessment = RiskAssessment(
            overall_risk=RiskLevel.LOW,
            risk_factors=["ファイル読み取りのみ"],
            mitigation_measures=[],
            approval_required=False,
            reasoning="読み取り専用操作のため低リスク"
        )
        
        # 承認不要
        approval_status = ApprovalStatus(
            requested=False,
            granted=True,
            timestamp=datetime.now(),
            approval_message="読み取り専用のため自動承認"
        )
        
        # 成功したツール実行結果
        tool_results = []
        for file_path in understanding_result.execution_plan.expected_files:
            if file_path in gathered_info.collected_files:
                file_content = gathered_info.collected_files[file_path]
                tool_results.append(ToolResult(
                    tool_name="read_file",
                    success=True,
                    output=f"ファイル {file_path} を読み取り完了 ({file_content.size}文字)"
                ))
        
        # 模擬実行結果を設定
        execution_result = ExecutionResult(
            risk_assessment=risk_assessment,
            approval_status=approval_status,
            tool_results=tool_results,
            execution_errors=[],
            partial_success=False
        )
        
        self.four_node_context.execution_result = execution_result
        rich_ui.print_message(f"模擬実行結果を設定完了: {len(tool_results)}個のツール結果", "info")
    
    def run_conversation(self, user_input: str) -> None:
        """
        ユーザーとの対話を実行（main_v2からの互換性のため）
        
        注意: ユーザーメッセージは main_v2.py で既に追加済みのため、ここでは追加しない
        """
        from ..ui.rich_ui import rich_ui
        
        # TaskObjectiveを初期化（新しいタスクとして）
        self.task_objective = task_objective_manager.create_new_objective(user_input)
        rich_ui.print_message(f"[TASK] 新しいタスク目標を設定: {user_input[:50]}...", "info")
        
        try:
            rich_ui.print_message("[4NODE] 4ノード統合処理を開始...", "info")
            
            # 4ノードグラフを実行
            final_state = self.graph.invoke(self.state)
            
            # 状態を更新
            if isinstance(final_state, dict):
                from ..state.agent_state import AgentState
                self.state = AgentState.model_validate(final_state)
            else:
                self.state = final_state
                
            rich_ui.print_message("[4NODE] 4ノード統合処理が完了しました", "success")
            
        except Exception as e:
            self.state.record_error(f"4ノード実行エラー: {e}")
            rich_ui.print_error(f"[ERROR] 4ノード処理中にエラーが発生: {e}")
            import traceback
            if self.state.debug_mode:
                traceback.print_exc()
    
    # ===== Phase 2: 継続ループ機能 - 理解・計画ノード継続対応 =====
    
    def _extract_continuation_context(self, state_obj: AgentState) -> Optional['ContinuationContext']:
        """状態から継続コンテキストを抽出"""
        # 明示的な継続コンテキストがある場合
        if hasattr(state_obj, 'continuation_context') and state_obj.continuation_context:
            return state_obj.continuation_context
        
        # TaskObjectiveから継続判定
        if (self.task_objective and 
            self.task_objective.iteration_count > 0 and 
            not self.task_objective.is_completed()):
            return self.task_objective.get_continuation_context()
        
        return None
    
    def _execute_continuation_planning(self, state_obj: AgentState, continuation_context) -> UnderstandingResult:
        """継続実行のための計画立案"""
        
        # 過去の試行結果からAttemptResultを構築
        previous_attempts = []
        if self.task_objective and self.task_objective.attempt_history:
            previous_attempts = self.task_objective.attempt_history
        elif continuation_context.previous_attempts:
            previous_attempts = continuation_context.previous_attempts
        
        # 不足情報分析
        missing_info = self.llm_service.extract_missing_information(
            self.task_objective.original_query,
            self.task_objective.accumulated_results
        )
        
        # LLMServiceによる継続計画立案
        execution_plan = self.llm_service.plan_continuation_execution(
            user_request=self.task_objective.original_query,
            previous_attempts=[attempt.model_dump() if hasattr(attempt, 'model_dump') else str(attempt) 
                             for attempt in previous_attempts],
            missing_info=missing_info
        )
        
        # 継続実行時の新しいファイル探索戦略
        improved_files = self._generate_alternative_files_for_continuation(
            self.task_objective.original_query, 
            continuation_context
        )
        
        rich_ui.print_message(f"継続戦略: {execution_plan.get('strategy', '改良実行')}", "info")
        rich_ui.print_message(f"回避戦略: {len(continuation_context.failed_approaches)}件", "info")
        rich_ui.print_message(f"新しい探索ファイル: {len(improved_files)}件", "info")
        
        # 従来形式のUnderstandingResultに変換
        return UnderstandingResult(
            requirement_analysis=(
                f"継続実行 ({self.task_objective.iteration_count}回目): "
                + execution_plan.get('summary', '改良された実行計画')
            ),
            execution_plan=ExecutionPlan(
                summary=execution_plan.get('summary', '継続実行計画'),
                steps=execution_plan.get('steps', ['改良された手順で再実行']),
                required_tools=execution_plan.get('required_tools', ['read_file', 'list_files']),
                expected_files=improved_files,  # 新しいファイル探索戦略を使用
                estimated_complexity=execution_plan.get('estimated_complexity', 'medium'),
                success_criteria=execution_plan.get('success_criteria', 'LLM評価で満足度0.8以上')
            ),
            identified_risks=(missing_info.constraints if missing_info and hasattr(missing_info, 'constraints') else []),
            information_needs=(missing_info.missing_items if missing_info and hasattr(missing_info, 'missing_items') else []),
            confidence=0.8,
            complexity_assessment=execution_plan.get('estimated_complexity', 'medium'),
        )
    
    def _execute_initial_planning(self, state_obj: AgentState) -> UnderstandingResult:
        """初回実行のための計画立案"""
        
        # TaskObjectiveから要件抽出
        if self.task_objective:
            requirements = self.llm_service.extract_task_requirements(
                self.task_objective.original_query
            )
            self.task_objective.extracted_requirements = requirements
            
            rich_ui.print_message(f"抽出要件: {len(requirements)}件", "info")
        
        # 従来の理解・計画ロジックを実行
        self.helpers.prepare_lightweight_context(state_obj)
        routing_decision = self.helpers.analyze_user_intent(state_obj)
        is_retry = self.helpers.is_retry_context(state_obj)
        
        understanding_result = self.helpers.execute_understanding_prompt(
            state_obj, self.four_node_context, routing_decision, is_retry
        )
        
        return understanding_result
    
    def _initialize_task_objective_from_state(self, state_obj: AgentState) -> None:
        """状態からTaskObjectiveを初期化"""
        
        # 最新のユーザーメッセージを取得
        user_query = "タスク実行"  # デフォルト
        if state_obj.conversation_history:
            for msg in reversed(state_obj.conversation_history):
                if msg.role == "user":
                    user_query = msg.content
                    break
        
        # 新しいTaskObjectiveを作成
        self.task_objective = task_objective_manager.create_new_objective(user_query)
        rich_ui.print_message(f"[INIT] TaskObjective初期化: {user_query[:50]}...", "info")
    
    # ===== Phase 1: 知的探索・分析エンジン =====
    
    def _detect_investigation_task(self, state_obj: AgentState) -> bool:
        """調査・分析タスクかどうかを判定"""
        
        # 最新のユーザーメッセージを取得
        user_message = ""
        if state_obj.conversation_history:
            for msg in reversed(state_obj.conversation_history):
                if msg.role == "user":
                    user_message = msg.content.lower()
                    break
        
        # 調査・分析を示すキーワードパターン
        investigation_keywords = [
            'について教えて', 'を教えて', 'とは', 'について調べて', 'を調べて', 'を調査',
            'シナリオ', 'scenario', '使い方', '実行方法', '全体像', '概要', 
            'アーキテクチャ', 'architecture', '設計', 'design', '仕組み',
            '実際のコード', 'コードを確認', '実装を確認', '調査してください'
        ]
        
        # アクション・実行を示すキーワード（調査ではない）
        action_keywords = [
            'を作成', 'を修正', 'を削除', 'を変更', 'を実行', 'を追加',
            'リファクタリング', 'refactor', 'fix', '修正', 'update', '更新'
        ]
        
        # 調査キーワードが含まれ、かつアクションキーワードが含まれない場合は調査タスク
        has_investigation_keyword = any(keyword in user_message for keyword in investigation_keywords)
        has_action_keyword = any(keyword in user_message for keyword in action_keywords)
        
        is_investigation = has_investigation_keyword and not has_action_keyword
        
        if is_investigation:
            rich_ui.print_message(f"[調査判定] 調査タスクとして認識: '{user_message[:50]}...'", "info")
        
        return is_investigation
    
    def _execute_investigation_planning(self, state_obj: AgentState) -> UnderstandingResult:
        """調査計画の立案と実行"""
        
        # 1. 全ファイルリストを取得
        try:
            # globを使った直接的なファイル取得
            import glob
            import os
            from pathlib import Path
            
            # 相対パスでglob実行
            all_files = []
            search_patterns = [
                "**/*.py", "**/*.md", "**/*.yaml", "**/*.yml", "**/*.json", 
                "**/*.txt", "**/*.cfg", "**/*.ini", "**/README*", "**/PROGRESS*"
            ]
            
            # デバッグ：現在のディレクトリを確認
            cwd = os.getcwd()
            rich_ui.print_message(f"[調査計画] 作業ディレクトリ: {cwd}", "debug")
            
            for pattern in search_patterns:
                matches = glob.glob(pattern, recursive=True)
                rich_ui.print_message(f"[調査計画] パターン {pattern}: {len(matches)} マッチ", "debug")
                for match in matches:
                    # 絶対パスに変換せずに相対パスのまま保持
                    relative_path = str(Path(match).as_posix())
                    if relative_path not in all_files:
                        all_files.append(relative_path)
            
            rich_ui.print_message(f"[調査計画] プロジェクトファイル数: {len(all_files)}", "info")
            
            # デバッグ：最初の数ファイルを表示
            if all_files:
                rich_ui.print_message(f"[調査計画] サンプルファイル: {all_files[:3]}", "debug")
            
        except Exception as e:
            rich_ui.print_error(f"[調査計画] ファイルリスト取得エラー: {e}")
            import traceback
            rich_ui.print_error(f"[調査計画] エラー詳細: {traceback.format_exc()}")
            
            # さらなるフォールバック: os.walkを使用
            try:
                import os
                all_files = []
                for root, dirs, files in os.walk("."):
                    # 除外ディレクトリ
                    dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'node_modules']]
                    
                    for file in files:
                        if file.endswith(('.py', '.md', '.yaml', '.yml', '.json', '.txt')):
                            # 相対パスで保持
                            rel_path = os.path.relpath(os.path.join(root, file))
                            all_files.append(rel_path)
                            
                rich_ui.print_message(f"[調査計画] フォールバック取得: {len(all_files)}ファイル", "info")
            except Exception as e2:
                rich_ui.print_error(f"[調査計画] フォールバックもエラー: {e2}")
                all_files = []
        
        if not all_files:
            # フォールバック: 従来の理解・計画を実行
            return self._execute_initial_planning(state_obj)
        
        # 2. LLMServiceで優先順位付け
        user_query = self.task_objective.original_query if self.task_objective else "プロジェクト調査"
        
        try:
            prioritized_files = self.llm_service.prioritize_files_for_task(user_query, all_files)
            rich_ui.print_message(f"[調査計画] 優先ファイル: {len(prioritized_files)}件選択", "info")
            
            # 調査計画をAgentStateに保存
            state_obj.investigation_plan = prioritized_files
            
            # 選択されたファイルをログ表示
            if prioritized_files:
                rich_ui.print_message("以下のファイルを優先的に調査します:", "info")
                for i, file_path in enumerate(prioritized_files[:5], 1):  # 上位5ファイルを表示
                    rich_ui.print_message(f"  {i}. {file_path}", "info")
                if len(prioritized_files) > 5:
                    rich_ui.print_message(f"  ... 他{len(prioritized_files)-5}ファイル", "info")
            
        except Exception as e:
            rich_ui.print_error(f"[調査計画] ファイル優先順位付けエラー: {e}")
            # フォールバック: 重要そうなファイルを手動選択
            prioritized_files = self._fallback_important_files(all_files)
            state_obj.investigation_plan = prioritized_files
        
        # 3. 調査用のUnderstandingResultを作成
        return UnderstandingResult(
            requirement_analysis=f"調査計画立案完了: {user_query}",
            execution_plan=ExecutionPlan(
                summary="プロジェクト調査計画",
                steps=[
                    "優先順位付けされたファイルの読み取り",
                    "ファイル内容の統合分析", 
                    "プロジェクト全体理解の構築",
                    "ユーザー質問への包括的回答"
                ],
                required_tools=["read_file", "list_files"],
                expected_files=prioritized_files,
                estimated_complexity="medium",
                success_criteria="プロジェクト全体像の理解とユーザー質問への回答"
            ),
            identified_risks=[],  # 調査タスクはリスクが低い
            information_needs=["プロジェクト構造の理解", "主要コンポーネントの把握", "使用方法・シナリオの特定"],
            confidence=0.9,  # 調査計画は高信頼度（confidenceが正しいフィールド名）
            complexity_assessment="medium"
        )
    
    def _fallback_important_files(self, all_files: List[str]) -> List[str]:
        """LLM呼び出し失敗時の重要ファイル選択フォールバック"""
        import os
        
        # 重要度による簡単なファイルフィルタリング
        important_files = []
        
        # 優先度1: ドキュメント
        doc_files = [f for f in all_files if any(doc in os.path.basename(f).lower() 
                    for doc in ['readme', 'progress', 'design', 'doc'])]
        important_files.extend(doc_files[:3])
        
        # 優先度2: メインファイル
        main_files = [f for f in all_files if any(main in os.path.basename(f).lower() 
                     for main in ['main.py', '__init__.py', 'setup.py'])]
        important_files.extend(main_files[:3])
        
        # 優先度3: 設定ファイル
        config_files = [f for f in all_files if any(config in os.path.basename(f).lower() 
                       for config in ['config', 'setting']) and f.endswith(('.py', '.yaml', '.yml'))]
        important_files.extend(config_files[:2])
        
        # 重複除去
        return list(dict.fromkeys(important_files))[:10]
    
    def _create_investigation_understanding_result(self, state_obj: AgentState) -> UnderstandingResult:
        """調査計画が既にある場合のUnderstandingResult作成"""
        user_query = self.task_objective.original_query if self.task_objective else "プロジェクト調査"
        
        return UnderstandingResult(
            requirement_analysis=f"調査計画実行: {user_query}",
            execution_plan=ExecutionPlan(
                summary="既存調査計画に基づく実行",
                steps=[
                    "調査計画に基づくファイル読み取り",
                    "ファイル内容の統合分析",
                    "プロジェクト理解の構築",
                    "ユーザー質問への回答"
                ],
                required_tools=["read_file"],
                expected_files=state_obj.investigation_plan,
                estimated_complexity="medium",
                success_criteria="調査計画に基づく包括的理解"
            ),
            identified_risks=[],  # 調査タスクはリスクが低い
            information_needs=["プロジェクト構造", "主要機能", "使用例"],
            confidence=0.9,  # confidenceフィールドを使用
            complexity_assessment="medium"
        )
    
    def _generate_alternative_files_for_continuation(self, user_query: str, continuation_context) -> List[str]:
        """継続実行時の代替ファイル探索戦略"""
        
        # 読み取り済みファイルを抽出
        already_read_files = set()
        for attempt in continuation_context.previous_attempts:
            if hasattr(attempt, 'results') and attempt.results:
                gathered_info = attempt.results.get('gathered_info', {})
                if isinstance(gathered_info, dict) and 'collected_files' in gathered_info:
                    collected_files = gathered_info['collected_files']
                    if isinstance(collected_files, dict):
                        already_read_files.update(collected_files.keys())
        
        rich_ui.print_message(f"[継続探索] 読み取り済みファイル: {len(already_read_files)}件", "info")
        
        # 汎用的な代替ファイル探索
        alternative_files = self._find_general_alternative_files(user_query, already_read_files)
        
        rich_ui.print_message(f"[継続探索] 新しい候補ファイル: {len(alternative_files)}件", "info")
        return alternative_files[:10]  # 最大10ファイルに制限
    
    
    def _find_general_alternative_files(self, user_query: str, already_read_files: set) -> List[str]:
        """汎用的な代替ファイル探索"""
        # RoutingEngineを使用した再探索
        try:
            routing_decision = self.routing_engine.analyze_user_intent(
                user_query + " [継続実行での代替ファイル探索]"
            )
            
            # 推定ファイルから読み取り済みを除外
            alternative_files = []
            for file_path in routing_decision.target_files:
                if file_path not in already_read_files:
                    alternative_files.append(file_path)
            
            return alternative_files
            
        except Exception as e:
            rich_ui.print_warning(f"[継続探索] RoutingEngine使用失敗: {e}")
            return []
    
    def _escalate_to_user_guidance(self, satisfaction: 'SatisfactionEvaluation') -> Dict[str, Any]:
        """汎用ユーザーエスカレーション機能"""
        
        rich_ui.print_warning("⚠️ ユーザー指導が必要です")
        
        # 状況レポートの生成
        situation_report = self._generate_situation_report(satisfaction)
        rich_ui.print_panel(situation_report, "現在の状況", "warning")
        
        # 選択肢の提示
        options = self._generate_user_options(satisfaction)
        rich_ui.print_panel(options, "対応選択肢", "info")
        
        # ユーザー選択の取得
        while True:
            user_choice = rich_ui.get_user_input("選択 (1-5)").strip()
            
            if user_choice == "1":
                # より詳細な指示を要求
                additional_info = rich_ui.get_user_input("より詳しい要求をお聞かせください")
                rich_ui.print_message("追加指示を受け取りました", "info")
                return {
                    'action': 'continue_with_guidance',
                    'additional_context': additional_info,
                    'reason': 'user_provided_additional_instructions'
                }
                
            elif user_choice == "2":
                # 代替アプローチを試行
                rich_ui.print_message("代替アプローチで再試行します", "info")
                return {
                    'action': 'continue_with_guidance',
                    'additional_context': '代替アプローチでの再試行',
                    'reason': 'alternative_approach'
                }
                
            elif user_choice == "3":
                # 部分結果で満足
                rich_ui.print_message("現在の結果で完了とします", "info")
                return {
                    'action': 'complete_partial',
                    'reason': 'user_satisfied_with_partial'
                }
                
            elif user_choice == "4":
                # 専門的支援の提供
                technical_report = self._provide_technical_assistance(satisfaction)
                rich_ui.print_panel(technical_report, "技術詳細", "cyan")
                rich_ui.print_message("技術詳細を確認後、1-3を再選択してください", "info")
                continue  # 選択を続行
                
            elif user_choice == "5":
                # タスクキャンセル
                rich_ui.print_message("タスクをキャンセルします", "warning")
                return {
                    'action': 'cancel',
                    'reason': 'user_cancelled'
                }
                
            else:
                rich_ui.print_warning("1-5の数字を選択してください")
    
    def _generate_situation_report(self, satisfaction: 'SatisfactionEvaluation') -> str:
        """現在の状況レポート生成"""
        
        # TaskObjectiveが存在する場合の詳細レポート
        if self.task_objective:
            return f"""[bold yellow]タスク実行状況レポート[/]

[bold]元の要求:[/] {self.task_objective.original_query}
[bold]試行回数:[/] {self.task_objective.iteration_count}/{self.task_objective.max_iterations}
[bold]現在の満足度:[/] {satisfaction.overall_score:.2f}/1.0

[bold red]不足している要素:[/]
{chr(10).join([f"  • {aspect}" for aspect in satisfaction.missing_aspects])}

[bold green]収集済み情報:[/]
{chr(10).join([f"  • {key}: {str(value)[:100]}..." for key, value in self.task_objective.accumulated_results.items()])}

[bold blue]品質評価:[/]
{satisfaction.quality_assessment}"""
        
        # フォールバック: 基本レポート
        return f"""[bold yellow]タスク実行状況レポート[/]

[bold red]不足している要素:[/]
{chr(10).join([f"  • {aspect}" for aspect in satisfaction.missing_aspects])}

[bold blue]品質評価:[/]
{satisfaction.quality_assessment}"""
    
    def _generate_user_options(self, satisfaction: 'SatisfactionEvaluation') -> str:
        """ユーザー選択肢の生成"""
        
        return """[bold cyan]次の対応を選択してください:[/]

1. **詳細指示** - より具体的な要求を教えてください
2. **代替手法** - 別のアプローチで再試行します  
3. **部分完了** - 現在の結果で満足します
4. **技術支援** - 問題の詳細分析と解決策を提示します
5. **中断** - このタスクを終了します"""
    
    def _provide_technical_assistance(self, satisfaction: 'SatisfactionEvaluation') -> str:
        """技術的支援情報の提供"""
        
        technical_details = []
        
        # TaskObjective情報
        if self.task_objective:
            technical_details.extend([
                f"試行履歴: {len(self.task_objective.attempt_history)}回",
                f"蓄積データ: {len(self.task_objective.accumulated_results)}種類",
                f"学習制約: {len(self.task_objective.learned_constraints)}件"
            ])
        
        # 満足度詳細
        technical_details.extend([
            f"全体満足度: {satisfaction.overall_score:.3f}",
            f"不足側面: {len(satisfaction.missing_aspects)}件",
            f"完了推奨: {'はい' if satisfaction.completion_recommendation else 'いいえ'}"
        ])
        
        # 推奨改善策
        recommendations = [
            "要求をより具体的に表現する",
            "期待する結果の例を提供する", 
            "利用可能な情報源を明示する",
            "制約条件を明確にする"
        ]
        
        return f"""[bold green]技術詳細情報[/]

[bold]現在の状況:[/]
{chr(10).join([f"  • {detail}" for detail in technical_details])}

[bold]推奨改善策:[/]
{chr(10).join([f"  • {rec}" for rec in recommendations])}

[bold]不足している情報:[/]
{chr(10).join([f"  • {aspect}" for aspect in satisfaction.missing_aspects])}"""
    
    def _execute_investigation_synthesis(self, state_obj: AgentState, understanding_result: UnderstandingResult) -> AgentState:
        """
        Phase 2-2: 調査タスクの統合分析実行
        
        調査計画に基づいてファイルを読み込み、LLMServiceの統合分析機能を使用して
        包括的なプロジェクト理解を構築し、ユーザー質問に回答する
        """
        try:
            user_query = self.task_objective.original_query if self.task_objective else "プロジェクト調査"
            
            # 1. 調査対象ファイルの読み込み
            rich_ui.print_message(f"[統合分析] {len(state_obj.investigation_plan)}ファイルを読み込み中...", "info")
            
            files_with_content = {}
            read_errors = []
            
            for i, file_path in enumerate(state_obj.investigation_plan):
                try:
                    # file_toolsを使用してファイル内容を読み込み
                    from ..tools.file_tools import file_tools
                    content = file_tools.read_file(file_path)  # 直接文字列を返す
                    
                    # FileContentオブジェクトとして作成
                    file_content = FileContent(
                        path=file_path,
                        content=content,
                        encoding="utf-8",
                        size=len(content) if content else 0,
                        last_modified=datetime.now(),
                        relevance_score=0.9  # 調査対象ファイルは高関連度
                    )
                    files_with_content[file_path] = file_content
                    rich_ui.print_message(f"  OK {i+1}/{len(state_obj.investigation_plan)}: {file_path}", "debug")
                        
                except Exception as e:
                    read_errors.append(f"{file_path}: {str(e)}")
                    rich_ui.print_warning(f"  NG {file_path}: {str(e)}")
                    
                # 最大読み込み数制限（パフォーマンス考慮）
                if len(files_with_content) >= 15:
                    rich_ui.print_message(f"[統合分析] パフォーマンス考慮により{len(files_with_content)}ファイルで制限", "info")
                    break
            
            rich_ui.print_success(f"[統合分析] {len(files_with_content)}ファイルの読み込み完了")
            if read_errors:
                rich_ui.print_warning(f"[統合分析] {len(read_errors)}件のファイル読み込みエラー")
            
            # 2. LLMServiceの統合分析機能を実行
            if files_with_content:
                rich_ui.print_step("[統合分析] 実行中...")
                
                # FileContentオブジェクトから文字列内容を抽出
                files_content_str = {
                    path: file_content.content 
                    for path, file_content in files_with_content.items()
                }
                
                project_summary = self.llm_service.synthesize_insights_from_files(
                    user_query, files_content_str
                )
                
                # プロジェクト要約をAgentStateに保存
                state_obj.project_summary = project_summary
                
                # ユーザーに中間報告を表示
                rich_ui.print_panel(
                    project_summary,
                    "プロジェクト調査結果",
                    "cyan"
                )
                
                # 対話履歴にも追加
                state_obj.add_message("assistant", f"プロジェクト調査結果:\n\n{project_summary}")
                
            else:
                error_msg = "調査対象ファイルの読み込みに失敗しました"
                rich_ui.print_error(f"[統合分析] {error_msg}")
                state_obj.project_summary = error_msg
                state_obj.add_message("assistant", error_msg)
            
            # 3. GatheredInfoを構築（既存のインターフェース互換性のため）
            gathered_info = GatheredInfo(
                collected_files=files_with_content,
                rag_results=[],  # 調査タスクでは不使用
                project_context=ProjectContext(
                    project_type="investigation_analysis",
                    main_languages=["python"],  # プロジェクトの主要言語を推定
                    frameworks=[],  # フレームワーク情報は統合分析結果に含まれる
                    architecture_pattern="統合分析により生成",
                    key_directories=[],  # ディレクトリ分析は将来の拡張
                    recent_changes=[]  # 変更履歴は統合分析結果に含まれる
                ),
                confidence_scores={"investigation_synthesis": 0.9},
                information_gaps=read_errors,  # 読み込みエラーを情報ギャップとして記録
                collection_strategy="investigation_synthesis"
            )
            
            self.four_node_context.gathered_info = gathered_info
            state_obj.collected_context = state_obj.collected_context or {}
            state_obj.collected_context['gathered_info'] = self._serialize_gathered_info(gathered_info)
            
            return state_obj
            
        except Exception as e:
            rich_ui.print_error(f"[統合分析] 実行エラー: {e}")
            import traceback
            rich_ui.print_error(f"[統合分析] エラー詳細: {traceback.format_exc()}")
            
            state_obj.record_error(f"統合分析エラー: {str(e)}")
            state_obj.project_summary = f"統合分析中にエラーが発生しました: {str(e)}"
            
            return state_obj
    
    def _evaluate_investigation_results(self, state_obj: AgentState, understanding_result: UnderstandingResult, gathered_info: GatheredInfo) -> AgentState:
        """
        Phase 2-3: 調査結果の評価処理
        
        調査タスクの成果を評価し、次のアクション（完了/再計画）を決定する
        """
        try:
            user_query = self.task_objective.original_query if self.task_objective else "プロジェクト調査"
            
            # 1. 調査結果の品質評価
            rich_ui.print_message("[調査評価] 調査結果の品質を評価中...", "info")
            
            investigation_quality = self._assess_investigation_quality(
                user_query, 
                state_obj.project_summary,
                len(state_obj.investigation_plan),
                gathered_info
            )
            
            rich_ui.print_message(f"[調査評価] 品質スコア: {investigation_quality['quality_score']:.2f}/1.0", "info")
            rich_ui.print_message(f"[調査評価] 完全性: {investigation_quality['completeness']:.2f}/1.0", "info")
            
            # 2. 完了判定
            is_investigation_complete = (
                investigation_quality['quality_score'] >= 0.7 and
                investigation_quality['completeness'] >= 0.6 and
                len(state_obj.project_summary) > 200  # 最小限の情報量
            )
            
            if is_investigation_complete:
                # 調査完了
                rich_ui.print_success("✅ 調査タスク完了：包括的な理解を構築できました")
                
                # 結果を最終的に表示（要約版）
                self._display_investigation_summary(state_obj, investigation_quality)
                
                # 次のステップをユーザーに提案
                self._suggest_next_steps_after_investigation(user_query, state_obj)
                
                return state_obj
                
            else:
                # 再計画が必要
                rich_ui.print_warning("🔄 調査結果が不完全です。再計画を実行します")
                
                # 不足分析とREPLAN実行
                return self._execute_investigation_replan(state_obj, investigation_quality)
                
        except Exception as e:
            rich_ui.print_error(f"[調査評価] エラー: {e}")
            import traceback
            rich_ui.print_error(f"[調査評価] 詳細: {traceback.format_exc()}")
            
            state_obj.record_error(f"調査評価エラー: {str(e)}")
            return state_obj
    
    def _assess_investigation_quality(self, user_query: str, project_summary: str, files_read: int, gathered_info: GatheredInfo) -> Dict[str, float]:
        """調査結果の品質評価"""
        
        # 基本品質指標
        quality_score = 0.0
        completeness = 0.0
        
        # 1. プロジェクト要約の量と質
        if project_summary and len(project_summary) > 100:
            quality_score += 0.3
            if len(project_summary) > 500:
                quality_score += 0.2
            if len(project_summary) > 1000:
                quality_score += 0.1
        
        # 2. ファイル読み込み数
        if files_read > 0:
            completeness += 0.2
            if files_read >= 5:
                completeness += 0.2
            if files_read >= 10:
                completeness += 0.2
        
        # 3. ユーザー質問とのマッチング（簡易版）
        if project_summary:
            # キーワードマッチングによる関連度評価
            query_keywords = user_query.lower().split()
            summary_lower = project_summary.lower()
            
            matched_keywords = sum(1 for keyword in query_keywords if keyword in summary_lower)
            if len(query_keywords) > 0:
                keyword_relevance = matched_keywords / len(query_keywords)
                quality_score += keyword_relevance * 0.4
        
        # 4. エラー状況の考慮
        if gathered_info and gathered_info.information_gaps:
            # エラーがある場合は品質を下げる
            error_penalty = min(0.2, len(gathered_info.information_gaps) * 0.05)
            quality_score -= error_penalty
        
        # 5. 完全性評価
        completeness += min(0.4, files_read * 0.04)  # ファイル数に応じた完全性
        
        # スコア正規化
        quality_score = max(0.0, min(1.0, quality_score))
        completeness = max(0.0, min(1.0, completeness))
        
        return {
            'quality_score': quality_score,
            'completeness': completeness,
            'files_analyzed': files_read,
            'summary_length': len(project_summary) if project_summary else 0
        }
    
    def _display_investigation_summary(self, state_obj: AgentState, quality_metrics: Dict[str, float]):
        """調査完了時の要約表示"""
        
        summary_text = f"""調査タスク完了

📊 調査統計:
  • 分析ファイル数: {quality_metrics['files_analyzed']}
  • 要約文字数: {quality_metrics['summary_length']:,}
  • 品質スコア: {quality_metrics['quality_score']:.2f}/1.0
  • 完全性: {quality_metrics['completeness']:.2f}/1.0

※ 詳細な調査結果は上記のパネルをご参照ください。"""
        
        rich_ui.print_panel(summary_text, "調査完了サマリー", "green")
        
    def _suggest_next_steps_after_investigation(self, user_query: str, state_obj: AgentState):
        """調査完了後の次ステップ提案"""
        
        suggestions = []
        
        # ユーザー質問の性質に応じた提案  
        if 'test' in user_query.lower() or 'テスト' in user_query:
            suggestions.append("• テストの追加・改善を行う")
            suggestions.append("• テストカバレッジを向上させる")
            
        if 'scenario' in user_query.lower() or 'シナリオ' in user_query:
            suggestions.append("• 具体的なシナリオの実行テストを行う")
            suggestions.append("• シナリオに基づいたカスタム実装を作成する")
        
        # 汎用的な提案
        suggestions.extend([
            "• プロジェクトの特定機能を修正・改善する",
            "• 新機能の実装計画を立てる",
            "• ドキュメントの更新・充実化を行う"
        ])
        
        suggestions_text = "次に以下のようなタスクをお手伝いできます:\n\n" + "\n".join(suggestions)
        
        rich_ui.print_panel(suggestions_text, "次のステップ提案", "cyan")
    
    def _execute_investigation_replan(self, state_obj: AgentState, quality_metrics: Dict[str, float]) -> AgentState:
        """調査結果が不完全な場合の再計画実行"""
        
        rich_ui.print_message("[再計画] 調査結果の不足分析中...", "info")
        
        # 継続コンテキストの設定
        replan_reason = f"調査品質不足 (品質:{quality_metrics['quality_score']:.2f}, 完全性:{quality_metrics['completeness']:.2f})"
        
        # continuation_contextに再計画の理由を設定
        from ..services.task_objective import ContinuationContext
        continuation_context = ContinuationContext(
            identified_problems=[replan_reason],
            suggested_improvements=["追加ファイルの調査", "異なるファイル選択戦略", "より深い分析"],
            alternative_strategies=["階層的調査", "キーワードベース探索", "関連ファイル追跡"]
        )
        
        state_obj.continuation_context = continuation_context
        
        rich_ui.print_message("[再計画] 理解・計画ノードに戻り、追加調査を実行します", "info")
        
        return state_obj
