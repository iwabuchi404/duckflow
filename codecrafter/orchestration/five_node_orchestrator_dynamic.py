"""
Five Node Orchestrator with Dynamic Duck Pacemaker Integration
動的Duck Pacemaker統合版5ノードオーケストレーター
"""

import asyncio
from typing import Dict, Any, Optional, List, Tuple, Union
from datetime import datetime
from enum import Enum

# LangGraph imports
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph

from ..state.agent_state import AgentState
from ..services.task_classifier import TaskProfileType, task_classifier
from ..prompts.four_node_context import (
    UnderstandingResult, GatheredInfo, ExecutionResult, EvaluationResult, NextAction
)
from ..orchestration.four_node_helpers import FourNodeHelpers
from ..orchestration.response_generation_node import response_generation_node
from ..services.llm_service import llm_service
from ..ui.rich_ui import rich_ui
from ..base.llm_client import llm_manager
from ..tools.duck_scan import duck_scan
from ..keeper import duck_fs

# 動的Duck Pacemaker
from ..pacemaker import DynamicDuckPacemaker


class NodeType(Enum):
    """5ノードの種類"""
    PLANNING = "planning"
    INFORMATION_COLLECTION = "information_collection" 
    SAFE_EXECUTION = "safe_execution"
    EVALUATION_CONTINUATION = "evaluation_continuation"
    RESPONSE_GENERATION = "response_generation"


class FiveNodeOrchestratorDynamic:
    """5️⃣ノード・オーケストレーター (動的Duck Pacemaker統合版)
    
    動的ループ制限機能を持つ評価ノード中心の品質保証ループを実現
    """
    
    def __init__(self, state: AgentState):
        """5ノードオーケストレーターを初期化 (動的制御版)
        
        Args:
            state: AgentState インスタンス
        """
        self.state = state
        
        # 依存コンポーネントの初期化
        from ..orchestration.routing_engine import RoutingEngine
        from ..prompts.four_node_compiler import FourNodePromptCompiler
        
        self.routing_engine = RoutingEngine()
        self.prompt_compiler = FourNodePromptCompiler()
        self.helpers = FourNodeHelpers(self.prompt_compiler, self.routing_engine)
        
        # 動的Duck Pacemaker初期化
        self.dynamic_pacemaker = DynamicDuckPacemaker()
        
        # LangGraphの構築
        self.graph = self._build_langgraph()
        
        # 実行統計
        self.execution_stats = {
            'total_runs': 0,
            'successful_runs': 0,
            'failed_runs': 0,
            'average_execution_time': 0.0
        }
        
        # 動的制御用の状態
        self.current_task_profile: Optional[TaskProfileType] = None
        self.session_start_time: Optional[datetime] = None
        
        rich_ui.print_message("🦆 動的Duck Pacemaker統合版5ノードオーケストレーター初期化完了", "info")
        
    def run_conversation(self, user_message: str) -> None:
        """メイン対話実行メソッド (動的制御版)
        
        Args:
            user_message: ユーザーメッセージ
        """
        try:
            start_time = datetime.now()
            self.session_start_time = start_time
            
            rich_ui.print_header("🦆 5-Node Dynamic Orchestration 開始")
            
            # タスクプロファイル分類
            classification_result = task_classifier.classify(user_message)
            self.current_task_profile = classification_result.profile_type
            
            # 動的制限設定
            pacemaker_result = self.dynamic_pacemaker.start_session(
                state=self.state,
                task_profile=self.current_task_profile
            )
            
            rich_ui.print_message(
                f"[DYNAMIC_CONTROL] 動的制限設定: {pacemaker_result['max_loops']}回 "
                f"(ティア: {pacemaker_result['calculation_result']['tier']})",
                "info"
            )
            
            # ユーザーメッセージを状態に追加
            self.state.add_message("user", user_message)
            
            # LangGraph実行
            final_state = self.graph.invoke({
                "agent_state": self.state,
                "user_message": user_message,
                "current_node": "planning",
                "loop_count": 0,
                "execution_results": {},
                "final_response": None,
                "task_profile": self.current_task_profile,
                "pacemaker_result": pacemaker_result
            })
            
            # セッション終了処理
            execution_time = (datetime.now() - start_time).total_seconds()
            success = "error" not in final_state
            
            self.dynamic_pacemaker.end_session(
                state=self.state,
                success=success
            )
            
            # 実行統計更新
            self._update_execution_stats(success, execution_time)
            
            # 最終状態を反映
            if "agent_state" in final_state:
                self.state = final_state["agent_state"]
            
            # パフォーマンス要約表示
            self._display_performance_summary()
            
            rich_ui.print_success(f"🎉 動的5ノードオーケストレーション完了 ({execution_time:.2f}秒)")
            
        except Exception as e:
            rich_ui.print_error(f"動的5ノードオーケストレーションエラー: {e}")
            
            # エラー時もセッション終了処理
            if hasattr(self, 'dynamic_pacemaker') and self.current_task_profile:
                self.dynamic_pacemaker.end_session(
                    state=self.state,
                    success=False
                )
            
            self._update_execution_stats(False, 0.0)
            
            # エラー応答を追加
            error_response = self._generate_error_response(str(e))
            self.state.add_message("assistant", error_response)
    
    def _build_langgraph(self) -> CompiledStateGraph:
        """LangGraphベースのステートマシンを構築 (動的制御版)"""
        from typing import TypedDict
        
        class FiveNodeDynamicState(TypedDict):
            agent_state: AgentState
            user_message: str
            current_node: str
            loop_count: int
            execution_results: dict
            final_response: Optional[str]
            task_profile: TaskProfileType
            pacemaker_result: dict
        
        workflow = StateGraph(FiveNodeDynamicState)
        
        # ノード定義
        workflow.add_node("planning", self._planning_node_dynamic)
        workflow.add_node("information_collection", self._information_collection_node_dynamic)
        workflow.add_node("safe_execution", self._safe_execution_node_dynamic)
        workflow.add_node("evaluation_continuation", self._evaluation_continuation_node_dynamic)
        workflow.add_node("response_generation", self._response_generation_node_dynamic)
        
        # エントリーポイント
        workflow.set_entry_point("planning")
        
        # エッジ定義（動的制御対応）
        workflow.add_conditional_edges(
            "planning",
            self._after_planning_dynamic,
            {
                "information_collection": "information_collection",
                "safe_execution": "safe_execution",
                "response_generation": "response_generation",
                "end": END
            }
        )
        
        workflow.add_conditional_edges(
            "information_collection", 
            self._after_information_collection_dynamic,
            {
                "safe_execution": "safe_execution",
                "evaluation_continuation": "evaluation_continuation",
                "planning": "planning",
                "end": END
            }
        )
        
        workflow.add_edge("safe_execution", "evaluation_continuation")
        
        workflow.add_conditional_edges(
            "evaluation_continuation",
            self._after_evaluation_continuation_dynamic,
            {
                "planning": "planning",
                "information_collection": "information_collection", 
                "safe_execution": "safe_execution",
                "response_generation": "response_generation",
                "end": END
            }
        )
        
        workflow.add_conditional_edges(
            "response_generation",
            self._after_response_generation_dynamic,
            {
                "evaluation_continuation": "evaluation_continuation",
                "end": END
            }
        )
        
        return workflow.compile()
    
    # === 動的制御対応ノード実装 ===
    
    def _planning_node_dynamic(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """1️⃣ 理解・計画ノード (動的制御版)"""
        try:
            rich_ui.print_step("[The Architect] 理解・計画フェーズ (動的制御)")
            
            agent_state = state["agent_state"]
            user_message = state["user_message"]
            loop_count = state.get("loop_count", 0)
            
            # 動的制御更新
            if loop_count > 0:
                update_result = self.dynamic_pacemaker.update_during_execution(
                    state=agent_state,
                    current_loop=loop_count
                )
                
                if update_result["intervention_required"]:
                    rich_ui.print_warning(f"[DYNAMIC_CONTROL] 介入が必要: {update_result}")
            
            # 既存の計画ロジック実行
            self.helpers.prepare_lightweight_context(agent_state)
            routing_decision = self.helpers.analyze_user_intent(agent_state)
            
            task_profile_type = state.get("task_profile", TaskProfileType.GENERAL_CHAT)
            
            is_retry = self.helpers.is_retry_context(agent_state)
            four_node_context = self._create_four_node_context(agent_state, routing_decision, task_profile_type)
            
            understanding_result = self.helpers.execute_understanding_prompt(
                agent_state, four_node_context, routing_decision, is_retry
            )
            
            # バイタル更新
            classification_result = task_classifier.classify(user_message)
            agent_state.update_duck_vitals(
                confidence_score=classification_result.confidence,
                is_progress=True
            )
            
            # 実行結果を状態に保存
            execution_results = state.get("execution_results", {})
            execution_results["understanding_result"] = understanding_result
            execution_results["task_profile_type"] = task_profile_type
            execution_results["routing_decision"] = routing_decision
            
            return {
                **state,
                "agent_state": agent_state,
                "execution_results": execution_results,
                "current_node": "planning",
                "loop_count": loop_count + 1
            }
            
        except Exception as e:
            rich_ui.print_error(f"動的計画ノードエラー: {e}")
            agent_state.update_duck_vitals(had_error=True, is_progress=False)
            return {**state, "agent_state": agent_state, "error": str(e)}
    
    def _evaluation_continuation_node_dynamic(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """4️⃣ 評価・継続ノード (動的制御版)"""
        try:
            rich_ui.print_step("[Quality Gate & Controller] 評価・継続フェーズ (動的制御)")
            
            agent_state = state["agent_state"]
            loop_count = state.get("loop_count", 0)
            execution_results = state.get("execution_results", {})
            
            # 動的制御チェック
            update_result = self.dynamic_pacemaker.update_during_execution(
                state=agent_state,
                current_loop=loop_count
            )
            
            # 推奨アクションの処理
            if update_result.get("recommendation") == "EARLY_COMPLETION_POSSIBLE":
                rich_ui.print_message("[DYNAMIC_CONTROL] 早期完了を推奨", "info")
                execution_results["next_action"] = "response_generation"
            elif update_result.get("recommendation") == "EXTENSION_POSSIBLE":
                rich_ui.print_message("[DYNAMIC_CONTROL] 制限延長が可能", "info")
                # 必要に応じて制限を動的に延長
                if agent_state.graph_state.max_loops < 20:
                    agent_state.graph_state.max_loops += 2
                    rich_ui.print_message(f"[DYNAMIC_CONTROL] 制限を{agent_state.graph_state.max_loops}回に延長", "info")
            
            # 既存の評価ロジック
            understanding_result = execution_results.get("understanding_result")
            gathered_info = execution_results.get("gathered_info")
            execution_result = execution_results.get("execution_result")
            task_profile_type = execution_results.get("task_profile_type")
            
            # バイタル更新
            self._comprehensive_vitals_update(agent_state, understanding_result, gathered_info, execution_result)
            
            # 品質評価
            evaluation_result = self._perform_quality_evaluation(
                understanding_result, gathered_info, execution_result, task_profile_type
            )
            
            # 次のアクション決定（動的制御考慮）
            next_action = self._determine_next_action_dynamic(
                agent_state, evaluation_result, understanding_result, 
                gathered_info, execution_result, update_result
            )
            
            rich_ui.print_message(f"[DYNAMIC_CONTROL] 評価結果 -> 次のアクション: {next_action}", "info")
            
            execution_results["evaluation_result"] = evaluation_result
            execution_results["next_action"] = next_action
            execution_results["dynamic_update"] = update_result
            
            return {
                **state,
                "agent_state": agent_state,
                "execution_results": execution_results,
                "current_node": "evaluation_continuation"
            }
            
        except Exception as e:
            rich_ui.print_error(f"動的評価ノードエラー: {e}")
            agent_state.update_duck_vitals(had_error=True, is_progress=False)
            return {**state, "agent_state": agent_state, "error": str(e)}
    
    # === 動的制御対応の分岐ロジック ===
    
    def _after_evaluation_continuation_dynamic(self, state: Dict[str, Any]) -> str:
        """評価ノード後の分岐決定 (動的制御版)"""
        execution_results = state.get("execution_results", {})
        next_action = execution_results.get("next_action")
        loop_count = state.get("loop_count", 0)
        agent_state = state["agent_state"]
        
        # 動的制限チェック
        if loop_count >= agent_state.graph_state.max_loops:
            rich_ui.print_warning(f"[DYNAMIC_CONTROL] 動的制限に到達 ({loop_count}/{agent_state.graph_state.max_loops})")
            return "response_generation"
        
        # Duck Pacemaker介入チェック
        intervention = agent_state.needs_duck_intervention()
        if intervention["required"]:
            if intervention["priority"] == "CRITICAL":
                rich_ui.print_warning(f"[DUCK_PACEMAKER] 緊急介入: {intervention['reason']}")
                return "end"
            elif intervention["priority"] == "HIGH":
                rich_ui.print_warning(f"[DUCK_PACEMAKER] 高優先度介入: {intervention['reason']}")
                return "planning"  # 再計画強制
        
        # 通常の分岐ロジック
        if next_action == "response_generation":
            return "response_generation"
        elif next_action == "planning":
            return "planning"
        elif next_action == "information_collection":
            return "information_collection"
        elif next_action == "safe_execution":
            return "safe_execution"
        else:
            return "end"
    
    def _determine_next_action_dynamic(
        self,
        agent_state: AgentState,
        evaluation_result: Any,
        understanding_result: Any,
        gathered_info: Any,
        execution_result: Any,
        dynamic_update: Dict[str, Any]
    ) -> str:
        """次のアクションを決定 (動的制御考慮)"""
        
        # 動的制御の推奨を優先
        if dynamic_update.get("recommendation") == "EARLY_COMPLETION_POSSIBLE":
            return "response_generation"
        
        # 介入が必要な場合
        if dynamic_update.get("intervention_required"):
            return "response_generation"  # 安全のため早期終了
        
        # 既存のロジックを使用
        return self._determine_next_action_langgraph(
            agent_state, evaluation_result, understanding_result, gathered_info, execution_result
        )
    
    # === ユーティリティメソッド ===
    
    def _display_performance_summary(self):
        """パフォーマンス要約を表示"""
        try:
            summary = self.dynamic_pacemaker.get_performance_summary()
            
            if summary["overall_stats"]["total_sessions"] > 0:
                rich_ui.print_message(
                    f"[PERFORMANCE_SUMMARY]\n"
                    f"  総セッション数: {summary['overall_stats']['total_sessions']}\n"
                    f"  全体成功率: {summary['overall_stats']['overall_success_rate']:.2%}\n"
                    f"  平均効率: {summary['overall_stats']['avg_efficiency']:.2%}",
                    "info"
                )
        except Exception as e:
            rich_ui.print_warning(f"パフォーマンス要約表示エラー: {e}")
    
    def _update_execution_stats(self, success: bool, execution_time: float):
        """実行統計を更新"""
        self.execution_stats['total_runs'] += 1
        if success:
            self.execution_stats['successful_runs'] += 1
        else:
            self.execution_stats['failed_runs'] += 1
        
        # 移動平均で実行時間を更新
        alpha = 0.1
        self.execution_stats['average_execution_time'] = (
            (1 - alpha) * self.execution_stats['average_execution_time'] + 
            alpha * execution_time
        )
    
    def _generate_error_response(self, error_message: str) -> str:
        """エラー応答を生成"""
        return f"""申し訳ございません。処理中にエラーが発生しました。

エラー詳細: {error_message}

動的Duck Pacemakerが安全のため処理を停止しました。
別の方法でお手伝いできることがあれば、お知らせください。"""
    
    # === 既存メソッドの継承/参照 ===
    # 以下のメソッドは元のFiveNodeOrchestratorから継承または参照
    
    def _create_four_node_context(self, agent_state, routing_decision, task_profile_type):
        """Four Node Context作成 (元の実装を使用)"""
        # 元のFiveNodeOrchestratorの実装を参照
        pass
    
    def _comprehensive_vitals_update(self, agent_state, understanding_result, gathered_info, execution_result):
        """包括的バイタル更新 (元の実装を使用)"""
        # 元のFiveNodeOrchestratorの実装を参照
        pass
    
    def _perform_quality_evaluation(self, understanding_result, gathered_info, execution_result, task_profile_type):
        """品質評価実行 (元の実装を使用)"""
        # 元のFiveNodeOrchestratorの実装を参照
        pass
    
    def _determine_next_action_langgraph(self, agent_state, evaluation_result, understanding_result, gathered_info, execution_result):
        """次のアクション決定 (元の実装を使用)"""
        # 元のFiveNodeOrchestratorの実装を参照
        pass
    
    # 他の必要なノード実装メソッドも同様に継承/参照