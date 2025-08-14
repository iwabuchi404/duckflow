"""
Five Node Orchestrator - 5ノードアーキテクチャ (LangGraphベース)

評価ノード中心の品質保証ループと決定論的応答生成を実現
全てのアクション結果は評価ノードに集約され、そこで次の行先が決定される
LangGraphによる堅牢なステートマシン実装
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

# シンプル動的Duck Pacemaker
from ..pacemaker import SimpleDynamicPacemaker, UserConsultation


class NodeType(Enum):
    """5ノードの種類"""
    PLANNING = "planning"
    INFORMATION_COLLECTION = "information_collection" 
    SAFE_EXECUTION = "safe_execution"
    EVALUATION_CONTINUATION = "evaluation_continuation"
    RESPONSE_GENERATION = "response_generation"


class FiveNodeOrchestrator:
    """5️⃣ノード・オーケストレーター (LangGraphベース)
    
    評価ノードを中心とした品質保証ループを実現
    全アクション結果は評価ノードに集約され、次の行動が決定される
    LangGraphによる堅牢なステートマシン実装
    """
    
    def __init__(self, state: AgentState):
        """5ノードオーケストレーターを初期化 (4ノード互換インターフェース)
        
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
        
        # シンプル動的Duck Pacemakerの初期化
        self.dynamic_pacemaker = SimpleDynamicPacemaker()
        self.user_consultation = UserConsultation()
        
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
        
    def run_conversation(self, user_message: str) -> None:
        """メイン対話実行メソッド (動的Duck Pacemaker統合版)
        
        Args:
            user_message: ユーザーメッセージ
        """
        try:
            start_time = datetime.now()
            self.session_start_time = start_time
            
            rich_ui.print_header("🦆 5-Node Dynamic Pacemaker Orchestration 開始")
            
            # タスクプロファイル分類
            classification_result = task_classifier.classify(user_message)
            self.current_task_profile = classification_result.profile_type
            
            # 動的制限設定
            pacemaker_result = self.dynamic_pacemaker.start_session(
                state=self.state,
                task_profile=self.current_task_profile
            )
            
            # 制限設定の表示（シンプル版）
            rich_ui.print_message(f"🦆 {self.current_task_profile.value}を実行中です...", "info")
            
            # ユーザーメッセージを状態に追加
            self.state.add_message("user", user_message)
            
            # LangGraph実行
            final_state = self.graph.invoke({
                "agent_state": self.state,
                "user_message": user_message,
                "current_node": "planning",
                "loop_count": 0,
                "execution_results": {},
                "task_profile": self.current_task_profile,
                "pacemaker_result": pacemaker_result,
                "final_response": None
            })
            
            # セッション終了処理
            execution_time = (datetime.now() - start_time).total_seconds()
            success = "error" not in final_state
            
            if hasattr(self, 'dynamic_pacemaker') and self.current_task_profile:
                self.dynamic_pacemaker.end_session(
                    state=self.state,
                    success=success,
                    loops_used=self.state.graph_state.loop_count
                )
            
            # 実行統計更新
            self._update_execution_stats(success, execution_time)
            
            # 最終状態を反映
            if "agent_state" in final_state:
                self.state = final_state["agent_state"]
            
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
    
    async def orchestrate(self, state_obj: AgentState, user_message: str) -> str:
        """5ノードメインオーケストレーション
        
        Args:
            state_obj: AgentState オブジェクト
            user_message: ユーザーメッセージ
            
        Returns:
            最終的なユーザー向け応答
        """
        try:
            rich_ui.print_header("🦆 5-Node Orchestration 開始")
            
            # セッションの初期化
            self._initialize_session(state_obj, user_message)
            
            # メインループ: 評価ノード中心の品質保証フロー
            current_node = NodeType.PLANNING
            understanding_result = None
            gathered_info = None
            execution_result = None
            task_profile_type = None
            
            while self.loop_count < self.max_loops:
                self.loop_count += 1
                rich_ui.print_message(f"[ループ {self.loop_count}] 現在のノード: {current_node.value}", "info")
                
                # D.U.C.K. Vitals 更新
                self._update_duck_vitals(state_obj, current_node)
                
                # ノード実行
                if current_node == NodeType.PLANNING:
                    understanding_result, task_profile_type = await self._execute_planning_node(
                        state_obj, user_message
                    )
                    next_node = NodeType.INFORMATION_COLLECTION
                    
                elif current_node == NodeType.INFORMATION_COLLECTION:
                    gathered_info = await self._execute_information_collection_node(
                        state_obj, understanding_result
                    )
                    next_node = NodeType.SAFE_EXECUTION
                    
                elif current_node == NodeType.SAFE_EXECUTION:
                    execution_result = await self._execute_safe_execution_node(
                        state_obj, understanding_result, gathered_info
                    )
                    next_node = NodeType.EVALUATION_CONTINUATION
                    
                elif current_node == NodeType.EVALUATION_CONTINUATION:
                    # 🎯 中央制御: 全結果を評価し、次の行先を決定
                    evaluation_result, next_node = await self._execute_evaluation_node(
                        state_obj, understanding_result, gathered_info, execution_result, task_profile_type
                    )
                    
                    # Duck Pacemaker による強制介入チェック
                    intervention = state_obj.needs_duck_intervention()
                    if intervention["required"]:
                        rich_ui.print_warning(f"🦆 Duck Pacemaker 介入: {intervention['reason']}")
                        if intervention["action"] == "HALT_AND_CONSULT":
                            # 強制的に人間相談モードへ
                            return self._generate_consultation_response(state_obj, intervention)
                        elif intervention["action"] == "REPLAN":
                            # 強制的に再計画へ
                            next_node = NodeType.PLANNING
                            rich_ui.print_message("🦆 再計画を強制実行", "warning")
                    
                elif current_node == NodeType.RESPONSE_GENERATION:
                    # The Scribe: 決定論的応答生成
                    final_response = await self._execute_response_generation_node(
                        state_obj, gathered_info, execution_result, task_profile_type
                    )
                    
                    # 生成品質の最終チェック（評価ノードに戻る）
                    next_node = NodeType.EVALUATION_CONTINUATION
                    state_obj.collected_context["final_response"] = final_response
                
                # ループ終了条件チェック
                if next_node == "END":
                    rich_ui.print_success("🎉 タスク完了")
                    break
                elif next_node == "DUCK_CALL":
                    return self._generate_duck_call_response(state_obj)
                
                # 次のノードへ移行
                self.current_node = current_node
                current_node = next_node
                
                # ノード実行履歴を記録
                self._record_node_execution(current_node, {
                    "understanding_result": understanding_result is not None,
                    "gathered_info": gathered_info is not None,
                    "execution_result": execution_result is not None,
                    "loop_count": self.loop_count
                })
            
            # 最大ループ到達時の処理
            if self.loop_count >= self.max_loops:
                rich_ui.print_error("⚠️ 最大ループ回数に到達")
                return self._generate_timeout_response(state_obj)
            
            # 最終応答の取得
            if "final_response" in state_obj.collected_context:
                return state_obj.collected_context["final_response"]
            else:
                # フォールバック: 緊急応答生成
                return await self._execute_response_generation_node(
                    state_obj, gathered_info, execution_result, task_profile_type or TaskProfileType.GENERAL_CHAT
                )
                
        except Exception as e:
            rich_ui.print_error(f"5ノードオーケストレーションエラー: {e}")
            return self._generate_error_response(str(e))
    
    def _build_langgraph(self) -> CompiledStateGraph:
        """LangGraphベースのステートマシンを構築
        
        Returns:
            CompiledStateGraph: コンパイル済みのLangGraph
        """
        # ステートスキーマ定義 (TypedDictを使用)
        from typing import TypedDict
        
        class FiveNodeState(TypedDict):
            agent_state: AgentState
            user_message: str
            current_node: str
            loop_count: int
            execution_results: dict
            final_response: Optional[str]
        
        workflow = StateGraph(FiveNodeState)
        
        # ノード定義
        workflow.add_node("planning", self._planning_node)
        workflow.add_node("information_collection", self._information_collection_node)
        workflow.add_node("safe_execution", self._safe_execution_node)
        workflow.add_node("evaluation_continuation", self._evaluation_continuation_node)
        workflow.add_node("response_generation", self._response_generation_node)
        
        # エントリーポイント
        workflow.set_entry_point("planning")
        
        # エッジ定義（条件分岐）
        workflow.add_conditional_edges(
            "planning",
            self._after_planning,
            {
                "information_collection": "information_collection",
                "safe_execution": "safe_execution",
                "response_generation": "response_generation",
                "end": END
            }
        )
        
        workflow.add_conditional_edges(
            "information_collection", 
            self._after_information_collection,
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
            self._after_evaluation_continuation,
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
            self._after_response_generation,
            {
                "evaluation_continuation": "evaluation_continuation",
                "end": END
            }
        )
        
        return workflow.compile()
    
    # === LangGraphノード実装 ===
    
    def _planning_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """1️⃣ 理解・計画ノード (The Architect) - LangGraph版"""
        try:
            rich_ui.print_step("[The Architect] 理解・計画フェーズ")
            
            agent_state = state["agent_state"]
            user_message = state["user_message"]
            
            # 軽量コンテキスト準備
            self.helpers.prepare_lightweight_context(agent_state)
            
            # 意図分析 (RoutingEngine)
            routing_decision = self.helpers.analyze_user_intent(agent_state)
            
            # TaskProfile分類
            classification_result = task_classifier.classify(user_message)
            task_profile_type = classification_result.profile_type
            
            rich_ui.print_message(f"TaskProfile: {task_profile_type.value} (信頼度: {classification_result.confidence:.2f})", "info")
            
            # 再試行コンテキスト判定
            is_retry = self.helpers.is_retry_context(agent_state)
            
            # Four Node Context 作成
            four_node_context = self._create_four_node_context(agent_state, routing_decision, task_profile_type)
            
            # 理解・計画プロンプト実行
            understanding_result = self.helpers.execute_understanding_prompt(
                agent_state, four_node_context, routing_decision, is_retry
            )
            
            # 【修正】The Pecking Order の構築・更新 (同期版)
            try:
                # 非同期関数を同期的に実行
                import asyncio
                loop = None
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # 既にイベントループが動作中の場合は、タスクを作成せずに警告のみ
                        rich_ui.print_warning("The Pecking Order: イベントループ動作中のためスキップ")
                    else:
                        loop.run_until_complete(self._build_or_update_pecking_order(
                            agent_state, understanding_result, is_retry, task_profile_type
                        ))
                except RuntimeError:
                    # イベントループが存在しない場合は新しく作成
                    asyncio.run(self._build_or_update_pecking_order(
                        agent_state, understanding_result, is_retry, task_profile_type
                    ))
            except Exception as pecking_error:
                rich_ui.print_warning(f"The Pecking Order 構築エラー: {pecking_error}")
            
            # バイタル更新
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
                "current_node": "planning"
            }
            
        except Exception as e:
            rich_ui.print_error(f"計画ノードエラー: {e}")
            agent_state.update_duck_vitals(had_error=True, is_progress=False)
            return {**state, "agent_state": agent_state, "error": str(e)}
    
    def _information_collection_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """2️⃣ 情報収集ノード (The Librarian) - LangGraph版"""
        try:
            rich_ui.print_step("[The Librarian] 情報収集フェーズ")
            
            agent_state = state["agent_state"]
            execution_results = state.get("execution_results", {})
            understanding_result = execution_results.get("understanding_result")
            
            if not understanding_result:
                rich_ui.print_warning("理解結果がありません - 最小限の情報収集を実行")
                return {**state, "current_node": "information_collection"}
            
            # Duck Scanを使用した探索（ターゲットファイル優先）
            routing_decision = execution_results.get("routing_decision", {})
            target_files = routing_decision.get("target_files", [])
            
            if target_files:
                # 特定ファイルが指定されている場合は、そのファイル名で検索
                primary_file = target_files[0]  # 最初のファイルを主要ターゲットとする
                scan_result = duck_scan.scan_workspace(primary_file)
                rich_ui.print_message(f"[INFO_COLLECTION] ターゲットファイル検索: {primary_file}", "info")
            else:
                # 一般的な検索
                user_message = state["user_message"]
                scan_result = duck_scan.scan_workspace(user_message)
                rich_ui.print_message(f"[INFO_COLLECTION] 一般検索: {user_message}", "info")
            
            rich_ui.print_message(f"Duck Scan結果: {len(scan_result.files)}ファイル発見", "info")
            
            # ファイル情報収集 (Duck FS使用 + FileContent変換)
            collected_files = {}
            
            # ターゲットファイルが見つかったかチェック
            target_found = False
            if target_files:
                for target_file in target_files:
                    for scanned_file in scan_result.files:
                        if target_file.lower() in scanned_file.lower():
                            target_found = True
                            break
                    if target_found:
                        break
            
            if target_files and not target_found:
                rich_ui.print_warning(f"[INFO_COLLECTION] ターゲットファイル '{target_files[0]}' が見つかりません")
                # 直接ファイル読み取りを試行
                for target_file in target_files:
                    try:
                        file_result = duck_fs.read(target_file)
                        from ..prompts.four_node_context import FileContent
                        file_content = FileContent(
                            path=file_result.path,
                            content=file_result.content,
                            encoding=file_result.encoding,
                            size=len(file_result.content),
                            last_modified=datetime.now(),
                            relevance_score=1.0  # ターゲットファイルは最高関連度
                        )
                        collected_files[target_file] = file_content
                        rich_ui.print_success(f"[INFO_COLLECTION] 直接読み取り成功: {target_file} ({len(file_result.content)}文字)")
                        target_found = True
                    except Exception as e:
                        rich_ui.print_warning(f"[INFO_COLLECTION] 直接読み取り失敗 {target_file}: {e}")
            
            # スキャン結果からファイルを読み取り（ターゲット優先）
            files_to_read = scan_result.files[:10] if not target_found else scan_result.files[:5]
            
            for file_path in files_to_read:
                try:
                    file_result = duck_fs.read(file_path)
                    
                    # Duck FSの結果をFileContentに変換
                    from ..prompts.four_node_context import FileContent
                    
                    # 関連度の計算（ターゲットファイルに近いほど高い）
                    relevance_score = 0.5
                    if target_files:
                        for target_file in target_files:
                            if target_file.lower() in file_path.lower():
                                relevance_score = 1.0
                                break
                    
                    file_content = FileContent(
                        path=file_result.path,
                        content=file_result.content,
                        encoding=file_result.encoding,
                        size=len(file_result.content),
                        last_modified=datetime.now(),
                        relevance_score=relevance_score
                    )
                    
                    collected_files[file_path] = file_content
                    rich_ui.print_message(f"[INFO_COLLECTION] 読み取り完了: {file_path} ({len(file_result.content)}文字, 関連度: {relevance_score:.1f})", "info")
                except Exception as e:
                    rich_ui.print_warning(f"ファイル読み取りエラー {file_path}: {e}")
            
            # RAG検索実行
            rag_results = self.helpers.perform_rag_search(understanding_result, agent_state)
            
            # プロジェクト文脈構築
            project_context = self.helpers.build_project_context(collected_files, agent_state)
            
            # GatheredInfo オブジェクト作成
            gathered_info = GatheredInfo(
                collected_files=collected_files,
                rag_results=rag_results or [],
                project_context=project_context,
                confidence_scores={},
                information_gaps=[],
                collection_strategy="duck_scan_integration"
            )
            
            # 状態への保存
            agent_state.collected_context["gathered_info"] = gathered_info
            execution_results["gathered_info"] = gathered_info
            
            # バイタル更新
            file_count = len(collected_files)
            agent_state.update_duck_vitals(
                is_progress=file_count > 0,
                context_size=sum(len(str(f.content)) for f in collected_files.values())
            )
            
            return {
                **state,
                "agent_state": agent_state,
                "execution_results": execution_results,
                "current_node": "information_collection"
            }
            
        except Exception as e:
            rich_ui.print_error(f"情報収集ノードエラー: {e}")
            agent_state.update_duck_vitals(had_error=True, is_progress=False)
            return {**state, "agent_state": agent_state, "error": str(e)}
    
    def _safe_execution_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """3️⃣ 安全実行ノード (The Operator) - LangGraph版"""
        try:
            rich_ui.print_step("[The Operator] 安全実行フェーズ")
            
            agent_state = state["agent_state"]
            execution_results = state.get("execution_results", {})
            understanding_result = execution_results.get("understanding_result")
            gathered_info = execution_results.get("gathered_info")
            
            if not understanding_result:
                rich_ui.print_warning("理解結果がありません - 実行をスキップ")
                return {**state, "current_node": "safe_execution"}
            
            # リスク評価
            risk_assessment = self.helpers.assess_execution_risks(
                understanding_result, gathered_info, agent_state
            )
            
            rich_ui.print_message(f"リスクレベル: {risk_assessment.overall_risk.value}", "info")
            
            # 承認プロセス (必要に応じて)
            approval_status = self.helpers.handle_approval_process(
                risk_assessment, understanding_result, agent_state
            )
            
            # 実行結果作成（現在は読み取り専用操作のみ）
            execution_result = ExecutionResult(
                success=True,
                error_message=None,
                execution_time=0.1,
                tool_results=[],
                risk_assessment=risk_assessment,
                approval_status=approval_status,
                errors=[]
            )
            
            # 状態への保存
            agent_state.collected_context["execution_result"] = execution_result
            execution_results["execution_result"] = execution_result
            
            # バイタル更新
            agent_state.update_duck_vitals(
                is_progress=execution_result.success,
                had_error=not execution_result.success
            )
            
            return {
                **state,
                "agent_state": agent_state,
                "execution_results": execution_results,
                "current_node": "safe_execution"
            }
            
        except Exception as e:
            rich_ui.print_error(f"安全実行ノードエラー: {e}")
            agent_state.update_duck_vitals(had_error=True, is_progress=False)
            return {**state, "agent_state": agent_state, "error": str(e)}
    
    def _evaluation_continuation_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """4️⃣ 評価・継続ノード (Quality Gate & Controller) - LangGraph版"""
        try:
            rich_ui.print_step("[Quality Gate & Controller] 評価・継続フェーズ")
            
            agent_state = state["agent_state"]
            execution_results = state.get("execution_results", {})
            understanding_result = execution_results.get("understanding_result")
            gathered_info = execution_results.get("gathered_info")
            execution_result = execution_results.get("execution_result")
            task_profile_type = execution_results.get("task_profile_type")
            
            # D.U.C.K. Vitals System の更新
            self._comprehensive_vitals_update(agent_state, understanding_result, gathered_info, execution_result)
            
            # 動的Duck Pacemaker実行中監視
            current_loop = state.get("loop_count", 0)
            if hasattr(self, 'dynamic_pacemaker'):
                update_result = self.dynamic_pacemaker.update_during_execution(
                    state=agent_state,
                    current_loop=current_loop
                )
                
                # 介入が必要な場合の処理
                if update_result.get("intervention_required"):
                    intervention_details = update_result.get("intervention_details", {})
                    
                    # ユーザー相談を実行
                    consultation_result = self.user_consultation.present_consultation(
                        state=agent_state,
                        intervention_details=intervention_details,
                        current_loop=current_loop
                    )
                    
                    # ユーザー選択を処理
                    choice_result = self.user_consultation.process_user_choice(
                        consultation_result, agent_state
                    )
                    
                    # 選択に基づく次のアクション決定
                    next_action = choice_result.get("next_action", "continue")
                    
                    # 状態更新
                    execution_results["consultation_result"] = consultation_result
                    execution_results["choice_result"] = choice_result
                    execution_results["next_action"] = next_action
                    
                    return {
                        **state,
                        "agent_state": agent_state,
                        "execution_results": execution_results,
                        "current_node": "evaluation_continuation"
                    }
            
            # 【修正】The Pecking Order 進捗更新 (同期版)
            try:
                # 非同期関数を同期的に実行
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # 既にイベントループが動作中の場合はスキップ
                        rich_ui.print_warning("The Pecking Order 進捗: イベントループ動作中のためスキップ")
                    else:
                        loop.run_until_complete(self._update_pecking_order_progress(agent_state, execution_result))
                except RuntimeError:
                    # イベントループが存在しない場合は新しく作成
                    asyncio.run(self._update_pecking_order_progress(agent_state, execution_result))
            except Exception as pecking_error:
                rich_ui.print_warning(f"The Pecking Order 進捗更新エラー: {pecking_error}")
            
            # 品質評価
            evaluation_result = self._perform_quality_evaluation(
                understanding_result, gathered_info, execution_result, task_profile_type
            )
            
            # 次のアクション決定
            next_action = self._determine_next_action_langgraph(
                agent_state, evaluation_result, understanding_result, gathered_info, execution_result
            )
            
            rich_ui.print_message(f"評価結果 -> 次のアクション: {next_action}", "info")
            
            # 状態更新
            execution_results["evaluation_result"] = evaluation_result
            execution_results["next_action"] = next_action
            
            return {
                **state,
                "agent_state": agent_state,
                "execution_results": execution_results,
                "current_node": "evaluation_continuation"
            }
            
        except Exception as e:
            rich_ui.print_error(f"評価ノードエラー: {e}")
            agent_state.update_duck_vitals(had_error=True, is_progress=False)
            return {**state, "agent_state": agent_state, "error": str(e)}
    
    def _response_generation_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """5️⃣ 応答生成ノード (The Scribe) - LangGraph版"""
        try:
            rich_ui.print_step("[The Scribe] 応答生成フェーズ")
            
            agent_state = state["agent_state"]
            execution_results = state.get("execution_results", {})
            gathered_info = execution_results.get("gathered_info")
            execution_result = execution_results.get("execution_result")
            task_profile_type = execution_results.get("task_profile_type", TaskProfileType.GENERAL_CHAT)
            
            # Response Generation Node を使用して決定論的応答生成
            response_result = response_generation_node.generate_response(
                agent_state, gathered_info, execution_result, task_profile_type
            )
            
            final_response = response_result.final_response
            
            # 応答をAgentStateに追加
            agent_state.add_message("assistant", final_response)
            
            rich_ui.print_success(f"The Scribe: {len(final_response)}文字の応答を生成")
            
            # バイタル更新
            agent_state.update_duck_vitals(
                confidence_score=0.9,  # 決定論的生成なので高信頼度
                is_progress=True
            )
            
            return {
                **state,
                "agent_state": agent_state,
                "final_response": final_response,
                "current_node": "response_generation"
            }
            
        except Exception as e:
            rich_ui.print_error(f"応答生成ノードエラー: {e}")
            agent_state.update_duck_vitals(had_error=True, is_progress=False)
            
            # フォールバック応答
            fallback_response = self._generate_error_response(str(e))
            agent_state.add_message("assistant", fallback_response)
            
            return {
                **state,
                "agent_state": agent_state,
                "final_response": fallback_response,
                "error": str(e)
            }
    
    # === ノード実行メソッド (非同期版 - 後方互換性) ===
    
    async def _execute_planning_node(
        self, 
        state_obj: AgentState, 
        user_message: str
    ) -> Tuple[Optional[UnderstandingResult], Optional[TaskProfileType]]:
        """1️⃣ 理解・計画ノード (The Architect) の実行"""
        try:
            rich_ui.print_step("[The Architect] 理解・計画フェーズ")
            
            # 軽量コンテキスト準備
            self.helpers.prepare_lightweight_context(state_obj)
            
            # 意図分析 (RoutingEngine)
            routing_decision = self.helpers.analyze_user_intent(state_obj)
            
            # TaskProfile分類
            classification_result = task_classifier.classify(user_message)
            task_profile_type = classification_result.profile_type
            
            rich_ui.print_message(f"TaskProfile: {task_profile_type.value} (信頼度: {classification_result.confidence:.2f})", "info")
            
            # 再試行コンテキスト判定
            is_retry = self.helpers.is_retry_context(state_obj)
            
            # Four Node Context 作成 (既存の仕組みを活用)
            four_node_context = self._create_four_node_context(state_obj, routing_decision, task_profile_type)
            
            # 理解・計画プロンプト実行
            understanding_result = self.helpers.execute_understanding_prompt(
                state_obj, four_node_context, routing_decision, is_retry
            )
            
            # 【追加】The Pecking Order の構築・更新
            await self._build_or_update_pecking_order(state_obj, understanding_result, is_retry, task_profile_type)
            
            # バイタル更新
            state_obj.update_duck_vitals(
                confidence_score=classification_result.confidence,
                is_progress=True
            )
            
            return understanding_result, task_profile_type
            
        except Exception as e:
            rich_ui.print_error(f"計画ノードエラー: {e}")
            state_obj.update_duck_vitals(had_error=True, is_progress=False)
            return None, None
    
    async def _execute_information_collection_node(
        self, 
        state_obj: AgentState, 
        understanding_result: Optional[UnderstandingResult]
    ) -> Optional[GatheredInfo]:
        """2️⃣ 情報収集ノード (The Librarian) の実行"""
        try:
            rich_ui.print_step("[The Librarian] 情報収集フェーズ")
            
            if not understanding_result:
                rich_ui.print_warning("理解結果がありません - 最小限の情報収集を実行")
                return None
            
            # 収集戦略の決定
            collection_strategy = self.helpers.determine_collection_strategy(understanding_result)
            rich_ui.print_message(f"収集戦略: {collection_strategy}", "info")
            
            # ファイル情報収集 (機械的処理)
            collected_files = self.helpers.collect_file_information(understanding_result, state_obj)
            
            # RAG検索実行
            rag_results = self.helpers.perform_rag_search(understanding_result, state_obj)
            
            # プロジェクト文脈構築
            project_context = self.helpers.build_project_context(collected_files, state_obj)
            
            # GatheredInfo オブジェクト作成
            gathered_info = GatheredInfo(
                collected_files=collected_files,
                rag_results=rag_results,
                project_context=project_context,
                collection_strategy=collection_strategy,
                collection_timestamp=datetime.now()
            )
            
            # 状態への保存
            state_obj.collected_context["gathered_info"] = gathered_info
            
            # バイタル更新
            file_count = len(collected_files) if collected_files else 0
            state_obj.update_duck_vitals(
                is_progress=file_count > 0,
                context_size=sum(len(str(f)) for f in collected_files.values()) if collected_files else 0
            )
            
            return gathered_info
            
        except Exception as e:
            rich_ui.print_error(f"情報収集ノードエラー: {e}")
            state_obj.update_duck_vitals(had_error=True, is_progress=False)
            return None
    
    async def _execute_safe_execution_node(
        self, 
        state_obj: AgentState, 
        understanding_result: Optional[UnderstandingResult],
        gathered_info: Optional[GatheredInfo]
    ) -> Optional[ExecutionResult]:
        """3️⃣ 安全実行ノード (The Operator) の実行"""
        try:
            rich_ui.print_step("[The Operator] 安全実行フェーズ")
            
            if not understanding_result:
                rich_ui.print_warning("理解結果がありません - 実行をスキップ")
                return None
            
            # リスク評価
            risk_assessment = self.helpers.assess_execution_risks(
                understanding_result, gathered_info, state_obj
            )
            
            rich_ui.print_message(f"リスクレベル: {risk_assessment.overall_risk.value}", "info")
            
            # 承認プロセス (必要に応じて)
            approval_status = self.helpers.handle_approval_process(
                risk_assessment, understanding_result, state_obj
            )
            
            if approval_status.requested and not approval_status.granted:
                rich_ui.print_warning("ユーザーが実行を拒否しました")
                return ExecutionResult(
                    success=False,
                    error_message="ユーザーによる実行拒否",
                    execution_time=0.0,
                    tool_results=[],
                    risk_assessment=risk_assessment,
                    approval_status=approval_status,
                    errors=[]
                )
            
            # 実際の実行は読み取り専用操作のみ (書き込み系は将来実装)
            execution_result = ExecutionResult(
                success=True,
                error_message=None,
                execution_time=0.1,
                tool_results=[],
                risk_assessment=risk_assessment,
                approval_status=approval_status,
                errors=[]
            )
            
            # 状態への保存
            state_obj.collected_context["execution_result"] = execution_result
            
            # バイタル更新
            state_obj.update_duck_vitals(
                is_progress=execution_result.success,
                had_error=not execution_result.success
            )
            
            return execution_result
            
        except Exception as e:
            rich_ui.print_error(f"安全実行ノードエラー: {e}")
            state_obj.update_duck_vitals(had_error=True, is_progress=False)
            return None
    
    async def _execute_evaluation_node(
        self, 
        state_obj: AgentState, 
        understanding_result: Optional[UnderstandingResult],
        gathered_info: Optional[GatheredInfo],
        execution_result: Optional[ExecutionResult],
        task_profile_type: Optional[TaskProfileType]
    ) -> Tuple[Optional[EvaluationResult], NodeType]:
        """4️⃣ 評価・継続ノード (Quality Gate & Controller) の実行"""
        try:
            rich_ui.print_step("[Quality Gate & Controller] 評価・継続フェーズ")
            
            # D.U.C.K. Vitals System の更新
            self._comprehensive_vitals_update(state_obj, understanding_result, gathered_info, execution_result)
            
            # 【追加】The Pecking Order 状態更新
            await self._update_pecking_order_progress(state_obj, execution_result)
            
            # LLMを使用した品質評価
            evaluation_result = await self._perform_llm_evaluation(
                state_obj, understanding_result, gathered_info, execution_result, task_profile_type
            )
            
            # 次のアクション決定ロジック
            next_node = self._determine_next_action(
                state_obj, evaluation_result, understanding_result, gathered_info, execution_result
            )
            
            rich_ui.print_message(f"評価結果 -> 次のアクション: {next_node}", "info")
            
            # バイタルベースの強制介入チェック (Duck Pacemaker)
            intervention = state_obj.needs_duck_intervention()
            if intervention["required"]:
                if intervention["priority"] == "CRITICAL":
                    return evaluation_result, "DUCK_CALL"
                elif intervention["priority"] == "HIGH":
                    return evaluation_result, NodeType.PLANNING  # 再計画強制
            
            return evaluation_result, next_node
            
        except Exception as e:
            rich_ui.print_error(f"評価ノードエラー: {e}")
            state_obj.update_duck_vitals(had_error=True, is_progress=False)
            return None, NodeType.RESPONSE_GENERATION  # エラー時はフォールバック
    
    async def _execute_response_generation_node(
        self, 
        state_obj: AgentState, 
        gathered_info: Optional[GatheredInfo],
        execution_result: Optional[ExecutionResult],
        task_profile_type: TaskProfileType
    ) -> str:
        """5️⃣ 応答生成ノード (The Scribe) の実行"""
        try:
            rich_ui.print_step("[The Scribe] 応答生成フェーズ")
            
            # Response Generation Node を使用して決定論的応答生成
            response_result = response_generation_node.generate_response(
                state_obj, gathered_info, execution_result, task_profile_type
            )
            
            rich_ui.print_success(f"The Scribe: {len(response_result.final_response)}文字の応答を生成")
            
            # バイタル更新
            state_obj.update_duck_vitals(
                confidence_score=0.9,  # 決定論的生成なので高信頼度
                is_progress=True
            )
            
            return response_result.final_response
            
        except Exception as e:
            rich_ui.print_error(f"応答生成ノードエラー: {e}")
            state_obj.update_duck_vitals(had_error=True, is_progress=False)
            return self._generate_error_response(str(e))
    
    # === LangGraph条件分岐メソッド ===
    
    def _after_planning(self, state: Dict[str, Any]) -> str:
        """理解・計画ノード後の分岐判定"""
        try:
            execution_results = state.get("execution_results", {})
            understanding_result = execution_results.get("understanding_result")
            routing_decision = execution_results.get("routing_decision", {})
            
            if not understanding_result:
                return "end"
            
            rich_ui.print_message(f"[PLANNING_BRANCH] 分岐判定開始", "info")
            
            # ファイル読み取りが必要かチェック（RoutingEngineの結果を使用）
            needs_file_read = routing_decision.get("needs_file_read", False)
            target_files = routing_decision.get("target_files", [])
            
            rich_ui.print_message(f"[PLANNING_BRANCH] needs_file_read: {needs_file_read}, target_files: {len(target_files)}", "info")
            
            if needs_file_read and target_files:
                rich_ui.print_message("[PLANNING_BRANCH] → 情報収集ノードへ", "info")
                return "information_collection"
            
            # 情報収集が必要かチェック（従来の方法）
            if hasattr(understanding_result, 'information_needs') and understanding_result.information_needs:
                rich_ui.print_message("[PLANNING_BRANCH] → 情報収集ノードへ（information_needs）", "info")
                return "information_collection"
            
            # 実行計画があるかチェック
            if understanding_result.execution_plan and understanding_result.execution_plan.required_tools:
                rich_ui.print_message("[PLANNING_BRANCH] → 安全実行ノードへ", "info")
                return "safe_execution"
            
            # デフォルトは応答生成
            rich_ui.print_message("[PLANNING_BRANCH] → 応答生成ノードへ（デフォルト）", "info")
            return "response_generation"
            
        except Exception as e:
            rich_ui.print_error(f"計画後分岐判定エラー: {e}")
            return "end"
    
    def _after_information_collection(self, state: Dict[str, Any]) -> str:
        """情報収集ノード後の分岐判定"""
        try:
            execution_results = state.get("execution_results", {})
            gathered_info = execution_results.get("gathered_info")
            understanding_result = execution_results.get("understanding_result")
            
            if not gathered_info:
                return "end"
            
            # 実行が必要かチェック
            if understanding_result and understanding_result.execution_plan:
                required_tools = understanding_result.execution_plan.required_tools
                if required_tools and any(tool not in ['read_file', 'list_files'] for tool in required_tools):
                    return "safe_execution"
            
            # 情報収集のみで完了の場合は評価へ
            return "evaluation_continuation"
            
        except Exception as e:
            rich_ui.print_error(f"情報収集後分岐判定エラー: {e}")
            return "end"
    
    def _after_evaluation_continuation(self, state: Dict[str, Any]) -> str:
        """評価・継続ノード後の分岐判定"""
        try:
            execution_results = state.get("execution_results", {})
            next_action = execution_results.get("next_action")
            loop_count = state.get("loop_count", 0)
            
            # ループ制限チェック
            if loop_count >= 10:
                rich_ui.print_warning("最大ループ回数に到達")
                return "response_generation"
            
            # 次のアクションに基づく分岐
            if next_action == "planning":
                return "planning"
            elif next_action == "information_collection":
                return "information_collection"
            elif next_action == "safe_execution":
                return "safe_execution"
            elif next_action == "response_generation":
                return "response_generation"
            else:
                return "end"
                
        except Exception as e:
            rich_ui.print_error(f"評価後分岐判定エラー: {e}")
            return "end"
    
    def _after_response_generation(self, state: Dict[str, Any]) -> str:
        """応答生成ノード後の分岐判定"""
        try:
            # 応答生成後は品質チェックのため評価ノードに戻る
            final_response = state.get("final_response")
            
            if final_response and len(final_response) > 100:
                # 十分な応答が生成された場合は終了
                return "end"
            else:
                # 不十分な場合は評価ノードで再検討
                return "evaluation_continuation"
                
        except Exception as e:
            rich_ui.print_error(f"応答生成後分岐判定エラー: {e}")
            return "end"
    
    # === ヘルパーメソッド ===
    
    def _initialize_session(self, state_obj: AgentState, user_message: str) -> None:
        """セッション初期化"""
        self.loop_count = 0
        self.current_node = None
        self.node_execution_history = []
        
        # メッセージを履歴に追加
        state_obj.add_message("user", user_message)
        
        # 初期コンテキストを設定
        if not hasattr(state_obj, 'collected_context'):
            state_obj.collected_context = {}
    
    def _create_four_node_context(
        self, 
        state_obj: AgentState, 
        routing_decision: Dict[str, Any], 
        task_profile_type: TaskProfileType
    ):
        """Four Node Context オブジェクトの作成 (既存システムとの互換性)"""
        from ..prompts.four_node_context import FourNodePromptContext, NodeType
        from pathlib import Path
        
        # 必須引数を指定してFourNodePromptContextを作成
        context = FourNodePromptContext(
            current_node=NodeType.UNDERSTANDING,
            execution_phase=1,
            workspace_path=Path.cwd()
        )
        
        # オプション属性を設定
        context.operation_type = routing_decision.get("operation_type", "chat")
        
        # 【修正】The Pecking Order情報を統合
        current_task = state_obj.get_current_task()
        if current_task:
            context.current_task = current_task.description
            # 階層的タスク情報をコンテキストに追加
            context.pecking_order_status = state_obj.get_pecking_order_status()
            context.task_hierarchy = state_obj.get_pecking_order_string()
        else:
            context.current_task = f"TaskProfile: {task_profile_type.value}"
        
        return context
    
    def _update_duck_vitals(self, state_obj: AgentState, current_node: NodeType) -> None:
        """ノード実行時のバイタル更新"""
        # 各ノードでの標準的なバイタル更新
        confidence_map = {
            NodeType.PLANNING: 0.8,
            NodeType.INFORMATION_COLLECTION: 0.9,
            NodeType.SAFE_EXECUTION: 0.7,
            NodeType.EVALUATION_CONTINUATION: 0.8,
            NodeType.RESPONSE_GENERATION: 0.9
        }
        
        confidence = confidence_map.get(current_node, 0.7)
        state_obj.update_duck_vitals(
            confidence_score=confidence,
            is_progress=True
        )
    
    def _comprehensive_vitals_update(
        self, 
        state_obj: AgentState, 
        understanding_result: Optional[UnderstandingResult],
        gathered_info: Optional[GatheredInfo],
        execution_result: Optional[ExecutionResult]
    ) -> None:
        """包括的なバイタル更新 (評価ノードで実行)"""
        # 成功率に基づく信頼度計算
        success_indicators = 0
        total_indicators = 3
        
        if understanding_result:
            success_indicators += 1
        if gathered_info and gathered_info.collected_files:
            success_indicators += 1
        if execution_result and execution_result.success:
            success_indicators += 1
        
        confidence_score = success_indicators / total_indicators
        
        # コンテキストサイズ計算
        context_size = 0
        if gathered_info and gathered_info.collected_files:
            for file_content in gathered_info.collected_files.values():
                if hasattr(file_content, 'content'):
                    context_size += len(file_content.content)
        
        # エラー有無チェック
        had_error = (execution_result and not execution_result.success) or confidence_score < 0.3
        
        # バイタル更新
        state_obj.update_duck_vitals(
            confidence_score=confidence_score,
            had_error=had_error,
            is_progress=success_indicators > 0,
            context_size=context_size
        )
    
    async def _perform_llm_evaluation(
        self, 
        state_obj: AgentState, 
        understanding_result: Optional[UnderstandingResult],
        gathered_info: Optional[GatheredInfo],
        execution_result: Optional[ExecutionResult],
        task_profile_type: Optional[TaskProfileType]
    ) -> Optional[EvaluationResult]:
        """LLMを使用した品質評価"""
        try:
            # 評価用プロンプト作成
            evaluation_prompt = self._build_evaluation_prompt(
                understanding_result, gathered_info, execution_result, task_profile_type
            )
            
            # LLM評価実行
            response = llm_manager.chat(evaluation_prompt)
            
            # 評価結果解析
            evaluation_result = self._parse_evaluation_response(response)
            
            return evaluation_result
            
        except Exception as e:
            rich_ui.print_warning(f"LLM評価エラー: {e}")
            return None
    
    def _build_evaluation_prompt(
        self, 
        understanding_result: Optional[UnderstandingResult],
        gathered_info: Optional[GatheredInfo],
        execution_result: Optional[ExecutionResult],
        task_profile_type: Optional[TaskProfileType]
    ) -> str:
        """評価用プロンプト構築"""
        prompt_parts = [
            "以下の情報を評価し、次のアクションを決定してください。",
            "",
            f"TaskProfile: {task_profile_type.value if task_profile_type else 'Unknown'}",
            "",
            "実行状況:",
        ]
        
        if understanding_result:
            prompt_parts.append(f"✅ 理解・計画: 完了 (信頼度: {understanding_result.confidence:.2f})")
        else:
            prompt_parts.append("❌ 理解・計画: 未完了")
        
        if gathered_info:
            file_count = len(gathered_info.collected_files) if gathered_info.collected_files else 0
            prompt_parts.append(f"✅ 情報収集: 完了 ({file_count}ファイル)")
        else:
            prompt_parts.append("❌ 情報収集: 未完了")
        
        if execution_result:
            status = "成功" if execution_result.success else "失敗"
            prompt_parts.append(f"{'✅' if execution_result.success else '❌'} 実行: {status}")
        else:
            prompt_parts.append("❌ 実行: 未実行")
        
        prompt_parts.extend([
            "",
            "次のアクションを選択してください:",
            "1. RESPONSE_GENERATION - 応答生成へ進む",
            "2. REPLAN - 再計画が必要",
            "3. COLLECT_MORE_INFO - 追加情報収集が必要", 
            "4. EXECUTE_ADDITIONAL - 追加実行が必要",
            "5. END - タスク完了",
            "",
            "選択理由と共に回答してください。"
        ])
        
        return "\n".join(prompt_parts)
    
    def _parse_evaluation_response(self, response: str) -> EvaluationResult:
        """評価レスポンスの解析"""
        # 簡易解析 (将来的にはより高度な解析を実装)
        next_action = NextAction.RESPONSE_GENERATION  # デフォルト
        
        response_lower = response.lower()
        if "replan" in response_lower or "再計画" in response_lower:
            next_action = NextAction.REPLAN
        elif "collect_more" in response_lower or "追加情報" in response_lower:
            next_action = NextAction.COLLECT_MORE_INFO
        elif "execute_additional" in response_lower or "追加実行" in response_lower:
            next_action = NextAction.EXECUTE_ADDITIONAL
        elif "end" in response_lower or "完了" in response_lower:
            next_action = NextAction.END
        
        return EvaluationResult(
            overall_quality_score=0.8,  # 簡易実装
            task_completion_status="in_progress",
            identified_issues=[],
            recommended_next_action=next_action,
            confidence_in_recommendation=0.8,
            reasoning=response[:200],  # 最初の200文字
            duck_vitals_assessment={"mood": 0.8, "focus": 0.7, "stamina": 0.8}
        )
    
    def _determine_next_action(
        self, 
        state_obj: AgentState, 
        evaluation_result: Optional[EvaluationResult],
        understanding_result: Optional[UnderstandingResult],
        gathered_info: Optional[GatheredInfo],
        execution_result: Optional[ExecutionResult]
    ) -> NodeType:
        """次のアクション決定"""
        # LLM評価結果がある場合はそれを優先
        if evaluation_result:
            action_map = {
                NextAction.RESPONSE_GENERATION: NodeType.RESPONSE_GENERATION,
                NextAction.REPLAN: NodeType.PLANNING,
                NextAction.COLLECT_MORE_INFO: NodeType.INFORMATION_COLLECTION,
                NextAction.EXECUTE_ADDITIONAL: NodeType.SAFE_EXECUTION,
                NextAction.END: "END"
            }
            
            next_action = action_map.get(evaluation_result.recommended_next_action, NodeType.RESPONSE_GENERATION)
            if next_action:
                return next_action
        
        # フォールバック: ルールベース決定
        if not understanding_result:
            return NodeType.PLANNING
        elif not gathered_info:
            return NodeType.INFORMATION_COLLECTION
        elif not execution_result:
            return NodeType.SAFE_EXECUTION
        else:
            return NodeType.RESPONSE_GENERATION
    
    def _record_node_execution(self, node_type: NodeType, metadata: Dict[str, Any]) -> None:
        """ノード実行履歴の記録"""
        self.node_execution_history.append({
            "node_type": node_type.value,
            "timestamp": datetime.now(),
            "metadata": metadata
        })
    
    def _generate_consultation_response(self, state_obj: AgentState, intervention: Dict[str, Any]) -> str:
        """Duck Pacemaker 相談応答生成"""
        vitals_display = state_obj.get_duck_status_display()
        
        return f"""# 🦆 Duck Pacemaker からの相談

{intervention['reason']}のため、一時停止しています。

## 現在の状態
{vitals_display}

## 推奨アクション
{intervention['action']}

## 対処方法
1. しばらく休憩を取ってください
2. タスクを小さく分割してみてください  
3. より具体的な指示を提供してください
4. 必要に応じて人間のサポートを求めてください

---
*Duck Pacemaker による自動介入*"""
    
    def _generate_duck_call_response(self, state_obj: AgentState) -> str:
        """Duck Call 応答生成"""
        return """# 🦆 Duck Call - 人間への相談

現在のタスクは複雑すぎるか、追加の判断が必要です。

## 状況
- 自動処理の限界に達しました
- 人間の判断が必要です

## 次のステップ
1. 現在の進捗を確認してください
2. 追加の指示やガイダンスを提供してください
3. タスクを分割することを検討してください

お手数ですが、追加のサポートをお願いします。

---
*Duck Call システムによる自動要請*"""
    
    def _generate_timeout_response(self, state_obj: AgentState) -> str:
        """タイムアウト応答生成"""
        return f"""# ⏰ 処理タイムアウト

最大ループ回数 ({self.max_loops}) に到達しました。

## 実行履歴
{len(self.node_execution_history)}個のノードを実行しました。

## 推奨事項
1. タスクをより小さく分割してください
2. より具体的な指示を提供してください
3. 必要に応じて段階的に進めてください

申し訳ございませんが、現在の形式ではタスクを完了できませんでした。

---
*5-Node Orchestrator による自動生成*"""
    
    def _perform_quality_evaluation(
        self,
        understanding_result: Optional[UnderstandingResult],
        gathered_info: Optional[GatheredInfo], 
        execution_result: Optional[ExecutionResult],
        task_profile_type: Optional[TaskProfileType]
    ) -> EvaluationResult:
        """品質評価の実行（簡易版）"""
        try:
            # 成功指標の計算
            success_indicators = 0
            total_indicators = 3
            
            if understanding_result:
                success_indicators += 1
            if gathered_info and gathered_info.collected_files:
                success_indicators += 1
            if execution_result and execution_result.success:
                success_indicators += 1
            
            quality_score = success_indicators / total_indicators
            
            # 次のアクション決定
            if quality_score >= 0.8:
                next_action = NextAction.RESPONSE_GENERATION
            elif quality_score >= 0.5:
                next_action = NextAction.CONTINUE
            else:
                next_action = NextAction.RETRY
            
            return EvaluationResult(
                overall_quality_score=quality_score,
                task_completion_status="completed" if quality_score >= 0.8 else "in_progress",
                identified_issues=[],
                recommended_next_action=next_action,
                confidence_in_recommendation=0.8,
                reasoning=f"品質スコア: {quality_score:.2f}",
                duck_vitals_assessment={"mood": 0.8, "focus": 0.7, "stamina": 0.8}
            )
            
        except Exception as e:
            rich_ui.print_warning(f"品質評価エラー: {e}")
            return EvaluationResult(
                overall_quality_score=0.5,
                task_completion_status="error",
                identified_issues=[str(e)],
                recommended_next_action=NextAction.RESPONSE_GENERATION,
                confidence_in_recommendation=0.3,
                reasoning=f"評価エラー: {str(e)}",
                duck_vitals_assessment={"mood": 0.5, "focus": 0.5, "stamina": 0.5}
            )
    
    def _determine_next_action_langgraph(
        self,
        state_obj: AgentState,
        evaluation_result: Optional[EvaluationResult],
        understanding_result: Optional[UnderstandingResult],
        gathered_info: Optional[GatheredInfo],
        execution_result: Optional[ExecutionResult]
    ) -> str:
        """LangGraph用の次のアクション決定"""
        if evaluation_result:
            action_map = {
                NextAction.RESPONSE_GENERATION: "response_generation",
                NextAction.REPLAN: "planning",
                NextAction.COLLECT_MORE_INFO: "information_collection",
                NextAction.EXECUTE_ADDITIONAL: "safe_execution",
                NextAction.END: "end",
                NextAction.CONTINUE: "response_generation"
            }
            
            return action_map.get(evaluation_result.recommended_next_action, "response_generation")
        
        # フォールバック: ルールベース決定
        if not understanding_result:
            return "planning"
        elif not gathered_info:
            return "information_collection"
        elif not execution_result:
            return "safe_execution"
        else:
            return "response_generation"
    
    def _update_execution_stats(self, success: bool, execution_time: float) -> None:
        """実行統計の更新"""
        self.execution_stats['total_runs'] += 1
        
        if success:
            self.execution_stats['successful_runs'] += 1
        else:
            self.execution_stats['failed_runs'] += 1
        
        # 平均実行時間の更新
        total_time = self.execution_stats['average_execution_time'] * (self.execution_stats['total_runs'] - 1)
        self.execution_stats['average_execution_time'] = (total_time + execution_time) / self.execution_stats['total_runs']
    
    def _generate_error_response(self, error_message: str) -> str:
        """エラー応答生成"""
        return f"""# ❌ システムエラー

処理中にエラーが発生しました。

## エラー詳細
{error_message}

## 対処方法
1. 要求を再度確認してください
2. より簡単な内容から開始してください
3. エラーが継続する場合は管理者にご連絡ください

申し訳ございませんが、現在のタスクを完了できませんでした。

---
*5-Node Orchestrator による自動生成*"""

    # ===== The Pecking Order 関連メソッド =====
    
    async def _build_or_update_pecking_order(
        self, 
        state_obj: AgentState, 
        understanding_result: Optional[UnderstandingResult], 
        is_continuation: bool,
        task_profile_type: TaskProfileType
    ) -> None:
        """The Pecking Order（階層的タスク管理）を構築または更新する
        
        Args:
            state_obj: AgentState
            understanding_result: UnderstandingResult
            is_continuation: 継続実行かどうか
            task_profile_type: TaskProfile分類結果
        """
        try:
            # 最新のユーザーメッセージを取得
            latest_user_message = self._get_latest_user_message(state_obj)
            if not latest_user_message:
                return
                
            # LLMService呼び出しでタスク構造を分析
            task_structure = await llm_service.analyze_task_hierarchy(
                user_request=latest_user_message,
                context=understanding_result.requirement_analysis if understanding_result else "",
                is_continuation=is_continuation,
                task_profile_type=task_profile_type.value  # TaskProfileを考慮
            )
            
            if not task_structure:
                rich_ui.print_warning("タスク構造の分析に失敗しました")
                return
            
            # 新規または既存タスクツリーの処理
            if not state_obj.task_tree or not is_continuation:
                # 新規タスクツリーの作成
                main_goal = task_structure.get('main_goal', latest_user_message[:100])
                root_description = task_structure.get('root_task', latest_user_message)
                
                root_task = state_obj.initialize_pecking_order(main_goal, root_description)
                rich_ui.print_step(f"🦆 The Pecking Order 初期化: {main_goal}")
                
                # TaskProfileに基づくサブタスク生成戦略
                max_subtasks = self._get_max_subtasks_for_profile(task_profile_type)
                sub_tasks = task_structure.get('sub_tasks', [])
                
                for i, sub_task_desc in enumerate(sub_tasks[:max_subtasks]):
                    sub_task = state_obj.add_sub_task(root_task.id, sub_task_desc, priority=i)
                    if sub_task:
                        # TaskProfileメタデータを追加
                        sub_task.metadata = sub_task.metadata or {}
                        sub_task.metadata['task_profile_type'] = task_profile_type.value
                        rich_ui.print_message(f"  └─ {sub_task_desc[:50]}...", "info")
                
            else:
                # 既存タスクツリーの更新
                if state_obj.task_tree:
                    # 現在のタスクを取得
                    current_task = state_obj.get_current_task()
                    if current_task:
                        rich_ui.print_step(f"🔄 現在のタスク: {current_task.description}")
                    
                    # 新しいサブタスクがあれば追加
                    new_sub_tasks = task_structure.get('additional_sub_tasks', [])
                    if new_sub_tasks and state_obj.task_tree:
                        for sub_task_desc in new_sub_tasks[:3]:  # 最大3個まで
                            sub_task = state_obj.add_sub_task(state_obj.task_tree.id, sub_task_desc)
                            if sub_task:
                                sub_task.metadata = sub_task.metadata or {}
                                sub_task.metadata['task_profile_type'] = task_profile_type.value
                                rich_ui.print_message(f"  ➕ 追加: {sub_task_desc[:50]}...", "info")
            
            # The Pecking Order の状態表示
            if state_obj.task_tree:
                status_summary = state_obj.get_pecking_order_status()
                completion_rate = status_summary.get('completion_rate', 0.0)
                total_tasks = status_summary.get('total_tasks', 0)
                
                rich_ui.print_message(f"📋 タスク階層: {total_tasks}個のタスク（完了率: {completion_rate:.1%}）", "info")
                
                # デバッグモードの場合は詳細表示
                if state_obj.debug_mode:
                    rich_ui.print_step("🐛 The Pecking Order 詳細:")
                    hierarchy_str = state_obj.get_pecking_order_string()
                    rich_ui.print_message(hierarchy_str, "debug")
            
        except Exception as e:
            rich_ui.print_error(f"The Pecking Order 構築エラー: {e}")
            # エラーが発生してもプロセスは続行
    
    def _get_max_subtasks_for_profile(self, task_profile_type: TaskProfileType) -> int:
        """TaskProfileに基づく最大サブタスク数を決定する"""
        profile_limits = {
            TaskProfileType.CREATION_REQUEST: 7,  # 作成系は多段階
            TaskProfileType.ANALYSIS_REQUEST: 5,  # 分析系は中程度
            TaskProfileType.MODIFICATION_REQUEST: 6,  # 修正系は中程度
            TaskProfileType.GENERAL_CHAT: 3,  # 一般会話は少なめ
            TaskProfileType.QUESTION_ANSWER: 4,  # Q&Aは中程度
        }
        return profile_limits.get(task_profile_type, 5)
    
    async def _update_current_task_status(
        self, 
        state_obj: AgentState, 
        status: 'TaskStatus', 
        result: Optional[str] = None, 
        error: Optional[str] = None
    ) -> None:
        """現在のタスクの状態を更新する
        
        Args:
            state_obj: AgentState
            status: 新しいタスク状態
            result: 実行結果（任意）
            error: エラーメッセージ（任意）
        """
        try:
            from ..state.pecking_order import TaskStatus
            
            current_task = state_obj.get_current_task()
            if not current_task:
                return
            
            old_status = current_task.status
            current_task.update_status(status, result, error)
            
            # 状態変更の通知
            status_symbols = {
                TaskStatus.PENDING: "⏳",
                TaskStatus.IN_PROGRESS: "🔄",
                TaskStatus.COMPLETED: "✅",
                TaskStatus.FAILED: "❌"
            }
            
            rich_ui.print_message(
                f"タスク状態更新: {status_symbols[old_status]} → {status_symbols[status]} {current_task.description[:50]}...",
                "info"
            )
            
            # 完了時は次のタスクに移行
            if status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                next_task = state_obj.start_next_task()
                if next_task:
                    rich_ui.print_message(f"次のタスク開始: {next_task.description[:50]}...", "info")
                else:
                    rich_ui.print_success("🎉 全てのタスクが完了しました！")
            
        except Exception as e:
            rich_ui.print_error(f"タスク状態更新エラー: {e}")
    
    async def _update_pecking_order_progress(
        self, 
        state_obj: AgentState, 
        execution_result: Optional[ExecutionResult]
    ) -> None:
        """The Pecking Order の進捗を更新する"""
        try:
            from ..state.pecking_order import TaskStatus
            
            current_task = state_obj.get_current_task()
            if not current_task:
                return
            
            # 実行結果に基づいてタスク状態を決定
            if execution_result:
                if execution_result.success:
                    # 成功時は完了状態に更新
                    await self._update_current_task_status(
                        state_obj, 
                        TaskStatus.COMPLETED, 
                        result=execution_result.summary if hasattr(execution_result, 'summary') else "実行完了"
                    )
                else:
                    # 失敗時は失敗状態に更新
                    await self._update_current_task_status(
                        state_obj, 
                        TaskStatus.FAILED, 
                        error=execution_result.error_message or "実行失敗"
                    )
            else:
                # 実行結果がない場合は進行中状態に更新
                await self._update_current_task_status(
                    state_obj, 
                    TaskStatus.IN_PROGRESS
                )
            
        except Exception as e:
            rich_ui.print_error(f"The Pecking Order 進捗更新エラー: {e}")
    
    def _get_latest_user_message(self, state_obj: AgentState) -> Optional[str]:
        """最新のユーザーメッセージを取得する"""
        try:
            messages = state_obj.get_messages()
            for message in reversed(messages):
                if message.role == "user":
                    return message.content
            return None
        except Exception:
            return None


# グローバルインスタンスは初期化時に作成
five_node_orchestrator = None

def create_five_node_orchestrator(prompt_compiler, routing_engine):
    """5ノードオーケストレーターのファクトリ関数"""
    global five_node_orchestrator
    five_node_orchestrator = FiveNodeOrchestrator(prompt_compiler, routing_engine)
    return five_node_orchestrator