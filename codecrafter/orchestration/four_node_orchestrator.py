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
        if hasattr(self.state, 'conversation_history'):
            for msg in self.state.conversation_history[-3:]:  # 直近3件
                if msg.role == 'user':
                    task = FourNodeTaskStep(
                        step_id=f"task_{len(task_chain)}",
                        user_message=msg.content,
                        timestamp=msg.timestamp if hasattr(msg, 'timestamp') else datetime.now()
                    )
                    task_chain.append(task)
        
        return FourNodePromptContext(
            current_node=NodeType.UNDERSTANDING,
            execution_phase=1,
            workspace_path=workspace_path,
            task_chain=task_chain,
            recent_messages=self.state.conversation_history[-5:] if hasattr(self.state, 'conversation_history') else []
        )
    
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
        ノード1: 理解・計画ノード
        
        責務:
        - ユーザー要求の深い理解
        - 実行計画の立案
        - 必要な情報の特定
        - リスク要因の予測
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
            
            rich_ui.print_step("🧠 理解・計画フェーズ開始")
            
            # 1. 軽量マニフェストの準備
            self.helpers.prepare_lightweight_context(state_obj)
            
            # 2. RoutingEngineによる意図分析
            routing_decision = self.helpers.analyze_user_intent(state_obj)
            
            # 3. 再試行判定（エラー回復時）
            is_retry = self.helpers.is_retry_context(state_obj)
            
            # 4. プロンプト生成と実行
            understanding_result = self.helpers.execute_understanding_prompt(state_obj, self.four_node_context, routing_decision, is_retry)
            
            # 5. 結果の保存
            self.four_node_context.understanding = understanding_result
            state_obj.collected_context = state_obj.collected_context or {}
            state_obj.collected_context['understanding_result'] = self._serialize_understanding_result(understanding_result)
            
            rich_ui.print_success(f"理解完了: {understanding_result.requirement_analysis[:100]}...")
            
            return state_obj
            
        except Exception as e:
            rich_ui.print_error(f"理解・計画ノードでエラー: {e}")
            state_obj.record_error("理解・計画エラー", str(e), "understanding_planning_node")
            return state_obj
    
    def _information_gathering_node(self, state: Any) -> AgentState:
        """
        ノード2: 情報収集ノード
        
        責務:
        - 計画に基づいた情報収集
        - ファイル読み取り・RAG検索
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
            state_obj.record_error("情報収集エラー", str(e), "information_gathering_node")
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
            state_obj.record_error("安全実行エラー", str(e), "safe_execution_node")
            return state_obj
    
    def _evaluation_continuation_node(self, state: Any) -> AgentState:
        """
        ノード4: 評価・継続ノード
        
        責務:
        - 実行結果の評価・検証
        - エラーの分析と修正提案
        - 次のアクションの決定
        - タスク完了判定
        """
        state_obj = AgentState.parse_obj(state) if isinstance(state, dict) else state
        
        try:
            # ノード状態の更新
            state_obj.update_graph_state(current_node="評価・継続", add_to_path="評価・継続")
            self.four_node_context.current_node = NodeType.EVALUATION
            
            rich_ui.print_step("🔍 評価・継続フェーズ開始")
            
            # 前段階結果の確認
            understanding_result = self.four_node_context.understanding
            execution_result = self.four_node_context.execution_result
            
            if not (understanding_result and execution_result):
                raise ValueError("評価には理解・実行結果が必要です")
            
            # 1. 実行結果の評価
            success_status, completion_percentage = self._evaluate_execution_results(understanding_result, execution_result)
            
            # 2. エラー分析（必要時）
            error_analysis = None
            if execution_result.execution_errors:
                error_analysis = self._analyze_execution_errors(execution_result, understanding_result)
            
            # 3. 次のアクションの決定
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
            state_obj.record_error("評価・継続エラー", str(e), "evaluation_continuation_node")
            return state_obj
    
    # ===== 条件分岐メソッド =====
    
    def _after_understanding_planning(self, state: Any) -> str:
        """理解・計画ノード後の分岐判定"""
        state_obj = AgentState.parse_obj(state) if isinstance(state, dict) else state
        
        try:
            understanding_result = self.four_node_context.understanding
            if not understanding_result:
                return "complete"
            
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
            if not gathered_info:
                return "complete"
            
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
            
            # 4ノードコンテキストの更新
            current_task = FourNodeTaskStep(
                step_id=f"task_{len(self.four_node_context.task_chain)}",
                user_message=user_message,
                timestamp=datetime.now()
            )
            self.four_node_context.task_chain.append(current_task)
            
            rich_ui.print_info("🚀 4ノードオーケストレーション開始")
            
            # グラフの実行
            result = self.graph.invoke(self.state)
            
            rich_ui.print_info("✅ 4ノードオーケストレーション完了")
            
            return result
            
        except Exception as e:
            rich_ui.print_error(f"4ノードオーケストレーション実行エラー: {e}")
            self.state.record_error("オーケストレーションエラー", str(e), "run")
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
                    # ファイル読み取りの実行例
                    for file_path in understanding_result.execution_plan.expected_files:
                        try:
                            content = file_tools.read_file(file_path)
                            tool_results.append(ToolResult(
                                tool_name="read_file",
                                success=True,
                                output=f"ファイル {file_path} を読み取りました"
                            ))
                        except Exception as e:
                            execution_errors.append(ExecutionError(
                                error_type="FileReadError",
                                message=str(e),
                                file_path=file_path
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
    
    def run_conversation(self, user_input: str) -> None:
        """
        ユーザーとの対話を実行（main_v2からの互換性のため）
        """
        from ..ui.rich_ui import rich_ui
        
        # ユーザーメッセージを追加
        self.state.add_message("user", user_input)
        
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