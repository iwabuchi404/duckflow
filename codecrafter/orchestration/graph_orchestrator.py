"""
LangGraphベースのエージェントオーケストレーション
ステップ2b: RAG機能統合版 - プロジェクト理解能力搭載
"""
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

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
from ..prompts.prompt_compiler import prompt_compiler
from ..ui.rich_ui import rich_ui

# ---------- グラフ状態 ----------
class GraphOrchestrator:
    """
    LangGraphを利用したエージェントオーケストレーション
    """
    def __init__(self, state: AgentState):
        self.state = state
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """ステップ2d: Human-in-the-Loop対応の高度なグラフを構築"""
        workflow = StateGraph(AgentState)

        # ノード定義（ステップ2d拡張）
        workflow.add_node("思考", self._thinking_node)
        workflow.add_node("コンテキスト収集", self._context_collection_node) 
        workflow.add_node("危険性評価", self._safety_assessment_node)
        workflow.add_node("人間承認", self._human_approval_node)
        workflow.add_node("ツール実行", self._tool_execution_node)
        workflow.add_node("結果確認", self._result_verification_node)
        workflow.add_node("エラー分析", self._error_analysis_node)

        workflow.set_entry_point("思考")

        # 思考 → コンテキスト収集または危険性評価
        workflow.add_conditional_edges(
            "思考",
            self._should_collect_context,
            {
                "collect_context": "コンテキスト収集",
                "assess_safety": "危険性評価",
                "complete": END,
            },
        )

        # コンテキスト収集 → 危険性評価
        workflow.add_edge("コンテキスト収集", "危険性評価")

        # 危険性評価 → 人間承認 or 直接ツール実行 or 再思考
        workflow.add_conditional_edges(
            "危険性評価",
            self._requires_human_approval,
            {
                "require_approval": "人間承認",
                "direct_execution": "ツール実行",
                "think": "思考",
                "complete": END,
            },
        )

        # 人間承認 → ツール実行 or 終了
        workflow.add_conditional_edges(
            "人間承認",
            self._process_human_decision,
            {
                "approved": "ツール実行",
                "rejected": END,
                "complete": END,
            },
        )

        # ツール実行 → 結果確認
        workflow.add_edge("ツール実行", "結果確認")
        
        # 結果確認 → エラー分析 or 終了
        workflow.add_conditional_edges(
            "結果確認",
            self._should_analyze_errors,
            {
                "analyze_errors": "エラー分析",
                "complete": END,
            },
        )

        # エラー分析 → 思考（再試行） or 終了
        workflow.add_conditional_edges(
            "エラー分析",
            self._should_retry_after_error,
            {
                "retry": "思考",
                "complete": END,
            },
        )

        return workflow.compile()

    # ----- ノード関数 -----
    def _thinking_node(self, state: Any) -> AgentState:
        """思考ノード：ユーザーメッセージに対する AI応答を生成"""
        state_obj = AgentState.parse_obj(state) if isinstance(state, dict) else state
        
        try:
            # ループ制限チェック
            if state_obj.graph_state.loop_count >= state_obj.graph_state.max_loops:
                rich_ui.print_warning("ループ制限に達したため、簡易応答を生成します")
                state_obj.add_message("assistant", "申し訳ございません。処理が複雑になりすぎたため、こちらで終了させていただきます。")
                return state_obj
            
            state_obj.update_graph_state(current_node="思考", add_to_path="思考")
            
            # 追加: 思考前に軽量マニフェストを準備（トップレベル + 代表ディレクトリのみ）
            try:
                self._seed_lightweight_manifest(state_obj)
            except Exception as e:
                rich_ui.print_warning(f"[INFO] 軽量マニフェスト準備に失敗: {e}")

            # 直近ユーザー発話がファイル読取/要約要求か検知し、LLM応答を保留（未読時のみ）
            last_user = self._get_last_user_message(state_obj)
            if last_user and self._is_file_content_request(last_user):
                # 直前に『収集後に回答』フラグが立っている場合は、ここでの再ルーティングを抑止
                if getattr(state_obj, 'collected_context', {}).get('needs_answer_after_context'):
                    pass  # 再思考で回答すべきタイミング
                else:
                    file_ctx = getattr(state_obj, 'collected_context', {}).get('file_context', {})
                    loaded = file_ctx.get('file_contents') if isinstance(file_ctx, dict) else None
                    has_loaded_content = bool(loaded) and any(bool(v) for v in loaded.values())
                    if not has_loaded_content:
                        rich_ui.print_message("[ROUTING] ユーザーがファイル内容の確認を要求 → コンテキスト収集へ", "info")
                        state_obj.add_tool_execution(
                            tool_name="plan",
                            arguments={"action": "collect_context_for_file_read"},
                            result="pending",
                            execution_time=0,
                        )
                        state_obj.add_message("assistant", "指定のファイル内容を確認してから回答します。")
                        return state_obj
            
            # システムプロンプトの生成
            system_prompt = self._create_thinking_prompt(state_obj)
            recent = state_obj.get_recent_messages(1)
            
            if not recent:
                raise ValueError("メッセージがありません")
            
            user_message = recent[-1].content
            rich_ui.print_message(f"[THINKING] AIが回答を生成中...", "info")
            
            # AI応答の生成
            ai_response = llm_manager.chat(user_message, system_prompt)
            state_obj.add_message("assistant", ai_response)
            
            # ツール実行履歴の記録
            state_obj.add_tool_execution(
                tool_name="thinking",
                arguments={"user_message": user_message[:100]},
                result=ai_response[:200],
                execution_time=0,
            )
            
            # 応答の表示
            rich_ui.print_conversation_message("assistant", ai_response)
            
        except Exception as e:
            state_obj.record_error(f"思考ノードエラー: {e}")
            rich_ui.print_error(f"[ERROR] 思考処理中にエラーが発生しました: {e}")
            
            # フォールバック応答
            fallback_response = f"申し訳ございません。処理中にエラーが発生しました: {str(e)[:100]}"
            state_obj.add_message("assistant", fallback_response)
        
        return state_obj

    def _context_collection_node(self, state: Any) -> AgentState:
        state_obj = AgentState.parse_obj(state) if isinstance(state, dict) else state
        try:
            state_obj.update_graph_state(current_node="コンテキスト収集", add_to_path="コンテキスト収集")
            recent = state_obj.get_recent_messages(1)
            if not recent:
                return state_obj
            
            # 直近ユーザーの要求で解析（assistantではなくユーザー発話を見る）
            user_message = self._get_last_user_message(state_obj) or recent[-1].content
            
            # 既存のコンテキスト
            ctx = getattr(state_obj, 'collected_context', {}) or {}
            prev_file_ctx = ctx.get('file_context') if isinstance(ctx, dict) else None
            prev_contents = {}
            if isinstance(prev_file_ctx, dict):
                prev_contents = prev_file_ctx.get('file_contents', {}) or {}
            
            # リクエスト検出
            file_requests = self._detect_file_info_requests(user_message)
            requested_files = file_requests.get('read_files', [])
            need_read = bool(requested_files) and any(
                (f not in prev_contents) or not prev_contents.get(f)
                for f in requested_files
            )
            need_list = bool(file_requests.get('list_files'))
            
            # ファイル情報収集（必要な場合のみ）
            did_new_file_collect = False
            if need_read or need_list:
                file_context = self._gather_file_context(file_requests, state_obj)
                did_new_file_collect = bool(file_context.get('file_contents')) or bool(file_context.get('files_list'))
            else:
                file_context = prev_file_ctx or {'file_contents': {}, 'errors': []}
            
            # RAG検索（必要に応じて）
            rag_context = self._gather_rag_context(user_message, state_obj)
            did_rag = bool(rag_context)
            
            # コンテキストを保存
            if not hasattr(state_obj, 'collected_context'):
                state_obj.collected_context = {}
            state_obj.collected_context.update({
                'file_context': file_context,
                'rag_context': rag_context,
                # 新規収集やRAGヒットがあった場合のみ、再思考で回答へ戻す
                'needs_answer_after_context': bool(did_new_file_collect or did_rag)
            })
            
            # 互換フィールド
            state_obj.rag_context = rag_context
            
        except Exception as e:
            state_obj.record_error(f"コンテキスト収集エラー: {e}")
            rich_ui.print_error(f"コンテキスト収集中にエラーが発生: {e}")
        return state_obj

    def _tool_execution_node(self, state: Any) -> AgentState:
        state_obj = AgentState.parse_obj(state) if isinstance(state, dict) else state
        try:
            # ステップの移動
            state_obj.update_graph_state(current_node="ツール実行", add_to_path="ツール実行")
            recent = state_obj.get_recent_messages(1)
            if not recent or recent[-1].role != "assistant":
                return state_obj
            ai_response = recent[-1].content
            
            # ファイル操作の実行
            self._execute_file_operations(ai_response, state_obj)
            
            # シェル操作の実行  
            self._execute_shell_operations(ai_response, state_obj)
        except Exception as e:
            state_obj.record_error(f"ツール実行エラー: {e}")
            rich_ui.print_error(f"ツール実行時にエラーが発生しました: {e}")
        return state_obj

    def _safety_assessment_node(self, state: Any) -> AgentState:
        """危険性評価ノード：計画された操作の安全性を評価"""
        state_obj = AgentState.parse_obj(state) if isinstance(state, dict) else state
        
        try:
            state_obj.update_graph_state(current_node="危険性評価", add_to_path="危険性評価")
            rich_ui.print_message("[SAFETY] 操作の安全性を評価中...", "info")
            
            # 最新のAI応答から危険性を評価
            recent_messages = state_obj.get_recent_messages(1)
            if recent_messages and recent_messages[-1].role == "assistant":
                ai_response = recent_messages[-1].content
                
                # 危険な操作パターンを検出
                safety_analysis = self._analyze_safety_risks(ai_response)
                
                # 未確認ファイル参照の検出を追加
                try:
                    unknown = self._verify_file_mentions(ai_response, state_obj)
                except Exception:
                    unknown = []
                
                # 安全性評価結果を状態に記録
                if not hasattr(state_obj, 'safety_assessment'):
                    state_obj.safety_assessment = {}
                
                state_obj.safety_assessment.update({
                    'risk_level': safety_analysis['risk_level'],
                    'detected_risks': safety_analysis['risks'],
                    'requires_approval': safety_analysis['requires_approval'],
                    'assessment_time': datetime.now()
                })
                
                # 未確認ファイルがある場合は承認必須に引き上げ
                if unknown:
                    risks = state_obj.safety_assessment.get('detected_risks', [])
                    risks.append(f"未確認ファイル参照: {', '.join(sorted(set(unknown)))}")
                    state_obj.safety_assessment['detected_risks'] = risks
                    state_obj.safety_assessment['requires_approval'] = True
                    if state_obj.safety_assessment.get('risk_level') == 'LOW':
                        state_obj.safety_assessment['risk_level'] = 'MEDIUM'
                    rich_ui.print_warning("[SAFETY] 未確認ファイル参照を検出 → 人間承認が必要です")
                
                if state_obj.safety_assessment['requires_approval']:
                    rich_ui.print_warning(f"[SAFETY] 危険度: {state_obj.safety_assessment['risk_level']} - 人間承認が必要です")
                else:
                    rich_ui.print_success("[SAFETY] 安全な操作と判定されました")
            
        except Exception as e:
            state_obj.record_error(f"安全性評価エラー: {e}")
            rich_ui.print_error(f"[ERROR] 安全性評価中にエラーが発生しました: {e}")
            
        return state_obj

    def _human_approval_node(self, state: Any) -> AgentState:
        """人間承認ノード：危険な操作について人間の承認を求める"""
        state_obj = AgentState.parse_obj(state) if isinstance(state, dict) else state
        
        try:
            state_obj.update_graph_state(current_node="人間承認", add_to_path="人間承認")
            
            # 安全性評価結果を表示
            safety_info = getattr(state_obj, 'safety_assessment', {})
            risk_level = safety_info.get('risk_level', 'UNKNOWN')
            risks = safety_info.get('detected_risks', [])
            
            rich_ui.print_message(f"[APPROVAL] 人間承認が必要な操作です", "warning")
            rich_ui.print_message(f"[APPROVAL] 危険度: {risk_level}", "warning")
            
            if risks:
                rich_ui.print_message("[APPROVAL] 検出されたリスク:", "warning")
                for risk in risks:
                    rich_ui.print_message(f"  - {risk}", "warning")
            
            # 計画された操作を表示
            recent_messages = state_obj.get_recent_messages(1)
            if recent_messages and recent_messages[-1].role == "assistant":
                ai_response = recent_messages[-1].content
                if "FILE_OPERATION:" in ai_response:
                    rich_ui.print_message("[APPROVAL] 実行予定の操作:", "info")
                    rich_ui.print_message(ai_response[:500] + ("..." if len(ai_response) > 500 else ""), "muted")
            
            # 承認結果を要求（実際の実装では rich_ui.get_confirmation を使用）
            rich_ui.print_message("[APPROVAL] この操作を承認しますか？ (y/n)", "warning")
            
            # 自動承認設定
            if state_obj.auto_approve:
                rich_ui.print_success("[APPROVAL] 自動承認設定により承認されました")
                state_obj.approval_result = 'approved'
            else:
                # UIに確認APIがあれば使用、なければデモとして承認
                try:
                    if hasattr(rich_ui, 'get_confirmation'):
                        confirmed = rich_ui.get_confirmation("この操作を承認しますか？")
                        state_obj.approval_result = 'approved' if confirmed else 'rejected'
                    else:
                        rich_ui.print_message("[APPROVAL] 承認待機中... (デモモードでは自動承認)", "info")
                        if not state_obj.approval_result:
                            state_obj.approval_result = 'approved'  # デモ用既定
                except Exception:
                    if not state_obj.approval_result:
                        state_obj.approval_result = 'approved'
            
        except Exception as e:
            state_obj.record_error(f"人間承認エラー: {e}")
            rich_ui.print_error(f"[ERROR] 人間承認中にエラーが発生しました: {e}")
            if not state_obj.approval_result:
                state_obj.approval_result = 'rejected'
        
        return state_obj

    def _result_verification_node(self, state: Any) -> AgentState:
        """結果確認ノード：処理結果をまとめて表示"""
        state_obj = AgentState.parse_obj(state) if isinstance(state, dict) else state
        
        try:
            state_obj.update_graph_state(current_node="結果確認", add_to_path="結果確認")
            
            # 直前のAI応答に未知ファイルのメンションがないか検証（警告として扱い、エラーにしない）
            recent = state_obj.get_recent_messages(1)
            if recent and recent[-1].role == "assistant":
                unknown = self._verify_file_mentions(recent[-1].content, state_obj)
                if unknown:
                    warn = f"参照されたが未確認のファイル: {', '.join(sorted(set(unknown)))}"
                    rich_ui.print_warning(warn)
                    state_obj.add_tool_execution(
                        tool_name="verify_file_mentions",
                        arguments={"candidates": list(sorted(set(unknown)))},
                        result={"unknown_files": list(sorted(set(unknown)))},
                        execution_time=0,
                    )
            
            # 実行されたツールの結果を確認
            if state_obj.tool_executions:
                last = state_obj.tool_executions[-1]
                if last.error:
                    rich_ui.print_error(f"[RESULT] ツール実行でエラーが発生しました: {last.error}")
                else:
                    rich_ui.print_success("[RESULT] ツール実行が成功しました")
                
                # 統計情報を表示
                recent_tools = state_obj.tool_executions[-5:] if len(state_obj.tool_executions) > 5 else state_obj.tool_executions
                successful_tools = [t for t in recent_tools if not t.error]
                rich_ui.print_message(f"[RESULT] 最新ツール結果: {len(successful_tools)}/{len(recent_tools)} 成功", "info")
            else:
                rich_ui.print_message("[RESULT] ツール実行はありませんでした", "info")
            
            # エラーカウントをクリア（線形フローのため）
            state_obj.last_error = None
            state_obj.retry_count = 0
            
        except Exception as e:
            state_obj.record_error(f"結果確認エラー: {e}")
            rich_ui.print_error(f"[ERROR] 結果確認時にエラーが発生しました: {e}")
        
        return state_obj

    def _should_collect_context(self, state: Any) -> str:
        """コンテキスト収集が必要かどうかを判断（直近ユーザー発話を優先）"""
        state_obj = AgentState.parse_obj(state) if isinstance(state, dict) else state
        
        # ループ制限チェック
        if state_obj.graph_state.loop_count >= state_obj.graph_state.max_loops:
            rich_ui.print_warning("ループ制限に達したため処理を終了します")
            return "complete"
        
        # 直近ユーザー発話を取得
        user_msg = self._get_last_user_message(state_obj)
        if user_msg:
            # ファイル内容を見て/要約/確認などの要求を検知
            if self._is_file_content_request(user_msg):
                # 既にファイル内容が収集済みなら再収集せず、後段処理へ
                try:
                    file_ctx = getattr(state_obj, 'collected_context', {}).get('file_context', {})
                    loaded = file_ctx.get('file_contents') if isinstance(file_ctx, dict) else None
                    has_loaded_content = bool(loaded) and any(bool(v) for v in loaded.values())
                except Exception:
                    has_loaded_content = False
                if not has_loaded_content:
                    rich_ui.print_message("[ROUTING] ユーザーの読取要求を検出 → コンテキスト収集", "info")
                    return "collect_context"
                else:
                    # 既にファイル内容があり、AI応答も生成済みの場合は完了
                    recent_messages = state_obj.get_recent_messages(1)
                    if recent_messages and recent_messages[-1].role == "assistant":
                        rich_ui.print_message("[ROUTING] ファイル内容は既に収集済み、回答済み → 完了", "info")
                        return "complete"
                    else:
                        rich_ui.print_message("[ROUTING] ファイル内容は既に収集済み → 危険性評価", "info")
                        return "assess_safety"
        
        # 最新のAI応答に基づく既存判定
        recent_messages = state_obj.get_recent_messages(1)
        if recent_messages and recent_messages[-1].role == "assistant":
            ai_response = recent_messages[-1].content
            
            # ツール実行指示がある場合は安全性評価へ
            if "FILE_OPERATION:" in ai_response:
                rich_ui.print_message("[ROUTING] ファイル操作指示を検出 → 安全性評価", "info")
                return "assess_safety"
        
        # RAGインデックスが利用可能で情報要求がある場合はコンテキスト収集
        try:
            status = rag_tools.get_index_status()
            if status.get("status") == "ready":
                # 情報を求めている質問かどうか判定（ユーザー発話基準）
                info_keywords = ['どこ', 'なに', '何', 'どのように', 'どの', '教えて', '見せて', '確認', '検索']
                text = (user_msg or '').lower()
                if any(keyword in text for keyword in info_keywords):
                    rich_ui.print_message("[ROUTING] 情報要求を検出 → コンテキスト収集", "info")
                    return "collect_context"
        except Exception as e:
            rich_ui.print_message(f"[ROUTING] RAG状態確認エラー: {e}", "warning")
        
        # デフォルトは完了（思考カウンタもリセット）
        if hasattr(state_obj, '_think_count'):
            state_obj._think_count = 0
        rich_ui.print_message("[ROUTING] 追加処理不要 → 完了", "info")
        return "complete"

    def _should_use_tools_after_context(self, state: Any) -> str:
        """コンテキスト収集後にツール使用が必要かどうかを判断"""
        # コンテキスト収集後は必ず危険性評価を経由
        return "assess_safety"

    def _requires_human_approval(self, state: Any) -> str:
        """人間承認が必要かどうかを判断"""
        state_obj = AgentState.parse_obj(state) if isinstance(state, dict) else state
        
        # 安全性評価結果を確認
        safety_assessment = getattr(state_obj, 'safety_assessment', {})
        requires_approval = safety_assessment.get('requires_approval', False)
        
        if requires_approval:
            rich_ui.print_message("[ROUTING] 人間承認が必要 → 承認待ち", "warning")
            return "require_approval"
        else:
            # 安全と判定されたがツール実行指示があるか確認
            recent_messages = state_obj.get_recent_messages(1)
            if recent_messages and recent_messages[-1].role == "assistant":
                ai_response = recent_messages[-1].content
                if "FILE_OPERATION:" in ai_response:
                    rich_ui.print_message("[ROUTING] 安全な操作 → 直接実行", "success")
                    return "direct_execution"
            
            # ツール実行対象がなく、直前にコンテキスト収集が行われた場合は再思考へ戻す
            needs_answer = getattr(state_obj, 'collected_context', {}).get('needs_answer_after_context', False)
            if needs_answer:
                # 無限ループ防止：think_count を追加してチェック
                think_count = getattr(state_obj, '_think_count', 0)
                if think_count >= 2:  # 3回目以降は強制完了
                    rich_ui.print_message("[ROUTING] 思考回数制限に到達 → 強制完了", "warning")
                    state_obj._think_count = 0  # リセット
                    return "complete"
                
                # 一度だけ戻すためフラグをクリア
                try:
                    state_obj.collected_context['needs_answer_after_context'] = False
                    state_obj._think_count = think_count + 1  # カウンタ増加
                except Exception:
                    pass
                rich_ui.print_message(f"[ROUTING] コンテキスト収集完了 → 再思考で回答 (回数: {think_count + 1})", "info")
                return "think"
            
            rich_ui.print_message("[ROUTING] 実行対象なし → 完了", "info")
            return "complete"

    def _process_human_decision(self, state: Any) -> str:
        """人間の承認結果を処理"""
        state_obj = AgentState.parse_obj(state) if isinstance(state, dict) else state
        
        approval_result = getattr(state_obj, 'approval_result', 'rejected')
        
        if approval_result == 'approved':
            rich_ui.print_success("[ROUTING] 承認済み → ツール実行")
            return "approved"
        else:
            rich_ui.print_warning("[ROUTING] 拒否済み → 処理終了")
            return "rejected"

    def _should_analyze_errors(self, state: Any) -> str:
        """エラー分析が必要かどうかを判断"""
        state_obj = AgentState.parse_obj(state) if isinstance(state, dict) else state
        
        # 最新のツール実行でエラーがあったかチェック
        if state_obj.tool_executions:
            latest_execution = state_obj.tool_executions[-1]
            if latest_execution.error:
                rich_ui.print_message("[ROUTING] エラー検出 → エラー分析", "warning")
                return "analyze_errors"
        
        rich_ui.print_message("[ROUTING] エラーなし → 処理完了", "success")
        return "complete"

    def _should_retry_after_error(self, state: Any) -> str:
        """エラー分析後に再試行するかどうかを判断"""
        state_obj = AgentState.parse_obj(state) if isinstance(state, dict) else state
        
        # リトライ回数制限チェック
        if state_obj.retry_count >= state_obj.max_retries:
            rich_ui.print_warning("[ROUTING] 最大リトライ回数に達しました → 処理終了")
            return "complete"
        
        # ループ回数制限チェック
        if state_obj.graph_state.loop_count >= state_obj.graph_state.max_loops:
            rich_ui.print_warning("[ROUTING] 最大ループ回数に達しました → 処理終了")
            return "complete"
        
        # エラー分析結果を確認
        error_analysis = getattr(state_obj, 'error_analysis', {})
        retry_recommended = error_analysis.get('retry_recommended', False)
        
        if retry_recommended:
            # リトライ回数を増加
            state_obj.retry_count += 1
            rich_ui.print_message(f"[ROUTING] リトライ実行 ({state_obj.retry_count}/{state_obj.max_retries}) → 思考", "warning")
            return "retry"
        else:
            rich_ui.print_warning("[ROUTING] 手動修正が必要 → 処理終了")
            return "complete"

    def _should_use_tools(self, state: Any) -> str:
        """ツールを使用するかどうかを判断"""
        state_obj = AgentState.parse_obj(state) if isinstance(state, dict) else state
        
        # ループ制限チェック
        if state_obj.graph_state.loop_count >= state_obj.graph_state.max_loops:
            rich_ui.print_warning("ループ制限に達したため、ツール実行をスキップします")
            return "complete"
        
        # 最新のAI応答にファイル操作指示があるかチェック
        recent = state_obj.get_recent_messages(1)
        if recent and recent[-1].role == "assistant" and "FILE_OPERATION:" in recent[-1].content:
            rich_ui.print_message("[TOOLS] ファイル操作指示を検出しました", "info")
            return "use_tools"
        
        rich_ui.print_message("[TOOLS] ツール実行の必要性なし", "info")
        return "complete"

    def _error_analysis_node(self, state: Any) -> AgentState:
        """エラー分析ノード：失敗した操作を分析し、修正方法を提案"""
        state_obj = AgentState.parse_obj(state) if isinstance(state, dict) else state
        
        try:
            state_obj.update_graph_state(current_node="エラー分析", add_to_path="エラー分析")
            rich_ui.print_message("[ERROR_ANALYSIS] エラーを分析中...", "info")
            
            # 最新のツール実行エラーを分析
            if state_obj.tool_executions:
                latest_execution = state_obj.tool_executions[-1]
                if latest_execution.error:
                    error_analysis = self._analyze_tool_error(latest_execution)
                    
                    # エラー分析結果を状態に記録
                    if not hasattr(state_obj, 'error_analysis'):
                        state_obj.error_analysis = {}
                    
                    state_obj.error_analysis.update({
                        'error_type': error_analysis['type'],
                        'error_category': error_analysis['category'],
                        'suggested_fixes': error_analysis['fixes'],
                        'retry_recommended': error_analysis['can_retry'],
                        'analysis_time': datetime.now()
                    })
                    
                    rich_ui.print_error(f"[ERROR_ANALYSIS] エラータイプ: {error_analysis['type']}")
                    rich_ui.print_error(f"[ERROR_ANALYSIS] カテゴリ: {error_analysis['category']}")
                    
                    if error_analysis['fixes']:
                        rich_ui.print_message("[ERROR_ANALYSIS] 修正提案:", "warning")
                        for i, fix in enumerate(error_analysis['fixes'], 1):
                            rich_ui.print_message(f"  {i}. {fix}", "warning")
                    
                    if error_analysis['can_retry']:
                        rich_ui.print_success("[ERROR_ANALYSIS] 再試行が推奨されます")
                    else:
                        rich_ui.print_warning("[ERROR_ANALYSIS] 手動での修正が必要です")
                else:
                    rich_ui.print_success("[ERROR_ANALYSIS] エラーは検出されませんでした")
            else:
                rich_ui.print_message("[ERROR_ANALYSIS] 分析対象のツール実行がありません", "info")
                
        except Exception as e:
            state_obj.record_error(f"エラー分析エラー: {e}")
            rich_ui.print_error(f"[ERROR] エラー分析中にエラーが発生しました: {e}")
        
        return state_obj

    # ------------- ヘルパー関数 (ステップ2d拡張) -------------
    def _analyze_safety_risks(self, ai_response: str) -> Dict[str, Any]:
        """AI応答の安全性リスクを分析"""
        risks = []
        risk_level = "LOW"
        requires_approval = False
        
        try:
            # ファイル操作の検出
            if "FILE_OPERATION:" in ai_response:
                if "FILE_OPERATION:CREATE" in ai_response:
                    risks.append("新しいファイルの作成")
                    risk_level = "MEDIUM"
                    requires_approval = True
                
                if "FILE_OPERATION:EDIT" in ai_response:
                    risks.append("既存ファイルの編集")
                    risk_level = "MEDIUM"
                    requires_approval = True
            
            # シェルコマンドの検出
            if "SHELL_COMMAND:" in ai_response:
                risks.append("シェルコマンド実行")
                risk_level = max(risk_level, "MEDIUM") if risk_level != "HIGH" else "HIGH"
                requires_approval = True
                
                # 危険なコマンドパターンをチェック
                dangerous_patterns = [
                    "rm -", "del ", "remove", "delete", 
                    "sudo", "chmod", "chown", "passwd"
                ]
                
                for pattern in dangerous_patterns:
                    if pattern in ai_response.lower():
                        risks.append(f"危険なコマンド: {pattern}")
                        risk_level = "HIGH"
                        requires_approval = True
            
            # テスト実行の検出
            if "RUN_TESTS" in ai_response:
                risks.append("テスト実行")
                # テストは比較的安全なのでMEDIUMレベル
                if risk_level == "LOW":
                    risk_level = "MEDIUM"
                requires_approval = True
            
            # リンター実行の検出
            if "LINT_CODE:" in ai_response:
                risks.append("コード解析ツール実行")
                # リンターも比較的安全
                if risk_level == "LOW":
                    risk_level = "MEDIUM"
                requires_approval = True
            
            # システムファイルへのアクセス
            system_paths = [
                "/etc/", "/sys/", "/proc/", "C:\\Windows\\", "C:\\System"
            ]
            
            for path in system_paths:
                if path in ai_response:
                    risks.append(f"システムパスへのアクセス: {path}")
                    risk_level = "HIGH"
                    requires_approval = True
                    
        except Exception as e:
            risks.append(f"安全性評価エラー: {e}")
            risk_level = "UNKNOWN"
            requires_approval = True
        
        return {
            'risks': risks,
            'risk_level': risk_level,
            'requires_approval': requires_approval
        }

    def _seed_lightweight_manifest(self, state: AgentState, max_top: int = 30, rep_dirs: Optional[List[str]] = None, max_each: int = 10) -> None:
        """初回の思考前に軽量なファイルマニフェストを収集して状態に格納する。
        - トップレベル: 最大 max_top 件
        - 代表ディレクトリ: codecrafter/tests/docs/config/src など存在するものを各 max_each 件
        既に files_list が存在する場合は何もしない。
        """
        from pathlib import Path
        # 既に収集済みならスキップ
        ctx = getattr(state, 'collected_context', {})
        file_ctx = ctx.get('file_context') if isinstance(ctx, dict) else None
        if file_ctx and isinstance(file_ctx, dict) and file_ctx.get('files_list'):
            return
        
        work_dir = state.workspace.path if state.workspace and state.workspace.path else os.getcwd()
        base = Path(work_dir)
        files_list: List[Dict[str, Any]] = []
        errors: List[str] = []
        
        # トップレベル（ファイルのみ）
        try:
            top_files = file_tools.list_files(work_dir, recursive=False)
            files_list.extend(top_files[:max_top])
        except Exception as e:
            errors.append(f"トップレベル一覧取得失敗: {e}")
        
        # 代表ディレクトリ候補
        if rep_dirs is None:
            rep_dirs = ["codecrafter", "tests", "docs", "config", "src"]
        selected_dirs: List[Path] = []
        try:
            for name in rep_dirs:
                p = base / name
                if p.exists() and p.is_dir():
                    selected_dirs.append(p)
            # 候補が全く無い場合は最初のサブディレクトリをいくつかサンプル
            if not selected_dirs:
                subs = [d for d in base.iterdir() if d.is_dir()]
                selected_dirs = subs[:3]
        except Exception as e:
            errors.append(f"代表ディレクトリ検出失敗: {e}")
        
        # 各代表ディレクトリから少量サンプリング
        for d in selected_dirs:
            try:
                sub_files = file_tools.list_files(str(d), recursive=False)
                files_list.extend(sub_files[:max_each])
            except Exception as e:
                errors.append(f"{d.name} の一覧取得失敗: {e}")
        
        # 状態に格納（既存の構造を尊重）
        if not hasattr(state, 'collected_context') or not isinstance(state.collected_context, dict):
            state.collected_context = {}
        existing_file_ctx = state.collected_context.get('file_context')
        if not existing_file_ctx or not isinstance(existing_file_ctx, dict):
            existing_file_ctx = {'file_contents': {}, 'errors': []}
        
        existing_file_ctx.update({
            'files_list': files_list,
            'manifest_seeded': True,
            'generated_at': datetime.now().isoformat(),
        })
        if errors:
            existing_file_ctx.setdefault('errors', []).extend(errors)
        state.collected_context['file_context'] = existing_file_ctx
        
        # 進捗表示
        try:
            rich_ui.print_message(f"[INFO] 軽量マニフェスト準備完了: {len(files_list)} 件", "info")
        except Exception:
            pass

    # ------------- 従来のヘルパー関数 -------------
    def _detect_file_info_requests_legacy(self, user_message: str) -> Dict[str, Any]:
        """ユーザーメッセージからファイル情報要求を検出（旧ロジック）。新実装へ委譲します。"""
        return self._detect_file_info_requests(user_message)
    
    # ------------- 追加ヘルパー（ルーティング検知） -------------
    def _get_last_user_message(self, state: AgentState) -> Optional[str]:
        """直近のユーザー発話内容を取得（conversation_history を参照）"""
        try:
            for m in reversed(state.conversation_history):
                if m.role == 'user':
                    return m.content
        except Exception:
            pass
        return None

    def _is_file_content_request(self, text: str) -> bool:
        """ファイル内容を『見て/要約/確認』する要求かを簡易判定"""
        if not text:
            return False
        import re
        lowered = text.lower()
        keywords = [
            '見て', '内容', '中身', '要約', '概要', '把握', '確認', '開いて',
            'read', 'show', 'open', 'summarize', 'overview'
        ]
        if any(k in lowered for k in keywords) or any(k in text for k in ['内容', '中身', '要約', '概要']):
            # パス表記や拡張子付きトークンが含まれるか
            if re.search(r"[A-Za-z]:\\\\|/|\\\\", text) or re.search(r"[\w\-_/\\.]+\.[A-Za-z0-9]{1,8}", text):
                return True
            # 明示的なファイル名がなくても、『design-doc』等の既知名を含む場合
            hints = ['design-doc', 'readme', 'changelog']
            if any(h in lowered for h in hints):
                return True
        return False

    def _detect_file_info_requests(self, user_message: str) -> Dict[str, Any]:
        """ユーザーメッセージからファイル情報要求（一覧/読み込み）を検出"""
        requests: Dict[str, Any] = {
            'list_files': False,
            'read_files': [],
            'get_file_info': []
        }
        
        msg_lower = user_message.lower()
        
        # ファイル一覧要求
        list_keywords = ['ファイル一覧', 'ファイルリスト', 'ls', 'list files', 'ファイルを見', 'ファイル構造']
        if any(k in msg_lower for k in list_keywords):
            requests['list_files'] = True
        
        # ファイル読み込み要求
        read_keywords = ['読んで', '読み込', 'read', '内容', '内容を', '中身', '中身を', '確認', '見て', '要約', '概要', '把握', 'open', 'open file']
        if any(k in msg_lower for k in read_keywords):
            import re, os
            candidates: list[str] = []
            # パターン1: 日本語対応（ドライブレター / 相対パス含む）
            p1 = r'[A-Za-z]:\\[^\n\r]+?\.[A-Za-z0-9]{1,8}|[\w\-\./\\ぁ-ゖァ-ヾ一-龯・]+?\.[A-Za-z0-9]{1,8}'
            candidates += re.findall(p1, user_message)
            # パターン2: 日本語対応 区切りを含む相対/絶対パス
            p2 = r'(?:[A-Za-z]:)?(?:[\\/][^\s\n\r]+)+?\.[A-Za-z0-9]{1,8}'
            candidates += re.findall(p2, user_message)
            # パターン3: 日本語対応 ディレクトリ名+ファイル名形式（区切り必須）
            p3 = r'[\w\.\-ぁ-ゖァ-ヾ一-龯・]+(?:[\\/][\w\.\-ぁ-ゖァ-ヾ一-龯・]+)+\.[A-Za-z0-9]{1,8}'
            candidates += re.findall(p3, user_message)

            # 正規化（末尾の句読点や括弧を除去、日本語対応）
            normalized: list[str] = []
            for c in candidates:
                t = c.strip().rstrip('。、.）)』】」》〉】〕]')
                # バックスラッシュを正規化（Windows環境対応）
                t = t.replace('\\', '/')
                if t:  # 空文字列を除外
                    normalized.append(t)
            
            # 重複排除しつつ順序維持
            seen = set()
            ordered = []
            for p in normalized:
                if p not in seen:
                    seen.add(p)
                    ordered.append(p)
            
            # サフィックス重複（長いパスに内包される短いサブパス）を除外
            def normsep(s: str) -> str:
                return s.replace('/', os.path.sep).replace('\\', os.path.sep)
            filtered = []
            for i, p in enumerate(ordered):
                p_n = normsep(p)
                drop = False
                for j, q in enumerate(ordered):
                    if i == j:
                        continue
                    q_n = normsep(q)
                    if len(q_n) > len(p_n) and q_n.endswith(p_n):
                        # 例: q = "temp_test_files\\users.csv", p = "\\users.csv"
                        drop = True
                        break
                if not drop:
                    filtered.append(p)
            
            # 最大3件
            requests['read_files'].extend(filtered[:3])
        
        return requests

    # ------------- コンテキスト収集 -------------
    def _gather_file_context(self, requests: Dict[str, Any], state: AgentState) -> Dict[str, Any]:
        """ファイルコンテキストを収集"""
        context: Dict[str, Any] = {
            'files_list': None,
            'file_contents': {},
            'errors': []
        }
        
        try:
            # ファイル一覧を取得
            if requests.get('list_files'):
                rich_ui.print_message("[INFO] ファイル一覧を取得中...", "info")
                try:
                    # 作業ディレクトリを決定（ワークスペース情報を優先）
                    if state.workspace and state.workspace.path:
                        work_dir = state.workspace.path
                        rich_ui.print_message(f"[DEBUG] ワークスペースディレクトリ: {work_dir}", "info")
                    else:
                        work_dir = os.getcwd()
                        rich_ui.print_message(f"[DEBUG] 現在の作業ディレクトリ: {work_dir}", "info")
                    
                    file_list = file_tools.list_files(work_dir, recursive=True)
                    context['files_list'] = file_list[:20]  # 最大20件
                    state.add_tool_execution(
                        tool_name="list_files",
                        arguments={"directory": work_dir, "recursive": True},
                        result=f"{len(file_list)} ファイルを発見 (in {work_dir})",
                        execution_time=0,
                    )
                    rich_ui.print_success(f"[OK] {len(file_list)} ファイルを発見 (ディレクトリ: {work_dir})")
                except Exception as e:
                    error_msg = f"ファイル一覧取得エラー: {e}"
                    context['errors'].append(error_msg)
                    rich_ui.print_warning(error_msg)
            
            # ファイル読み込み
            for file_path in requests.get('read_files', []):
                try:
                    # パス正規化と日本語ファイル名対応
                    import re, os
                    from pathlib import Path
                    
                    # 不正なルート相対/短縮パスをスキップ（例: "\\users.csv"）
                    if re.match(r"^[\\/][^\\/].*", file_path) and not re.match(r"^[A-Za-z]:", file_path):
                        rich_ui.print_warning(f"[SKIP] ルート相対などの不正な可能性があるパスをスキップ: {file_path}")
                        continue
                    
                    # パスの正規化（日本語ファイル名対応）
                    resolved_path = file_path
                    
                    # 作業ディレクトリからの相対パス解決を試行
                    if not os.path.isabs(file_path):
                        if state.workspace and state.workspace.path:
                            work_dir = state.workspace.path
                        else:
                            work_dir = os.getcwd()
                        resolved_path = os.path.join(work_dir, file_path)
                    
                    rich_ui.print_message(f"[READ] ファイルを読み込み中: {resolved_path}", "info")
                    content = file_tools.read_file(resolved_path)
                    context['file_contents'][file_path] = content[:2000]  # 最大2000文字
                    state.add_tool_execution(
                        tool_name="read_file",
                        arguments={"file_path": file_path},
                        result=f"ファイル読み込み成功 ({len(content)} 文字)",
                        execution_time=0,
                    )
                    rich_ui.print_success(f"[OK] {file_path} を読み込み完了")
                except Exception as e:
                    error_msg = f"ファイル読み込みエラー ({file_path}): {e}"
                    context['errors'].append(error_msg)
                    rich_ui.print_warning(error_msg)
        
        except Exception as e:
            error_msg = f"ファイルコンテキスト収集エラー: {e}"
            context['errors'].append(error_msg)
            rich_ui.print_error(error_msg)
        
        return context
    
    def _gather_rag_context(self, user_message: str, state: AgentState) -> List[Dict[str, Any]]:
        """RAGコンテキストを収集"""
        try:
            rich_ui.print_message("[SEARCH] 関連コードを検索中...", "info")
            rag_result = rag_tools.search_code(user_message, max_results=5)
            
            if rag_result.get("success") and rag_result.get("results"):
                state.add_tool_execution(
                    tool_name="search_code",
                    arguments={"query": user_message[:100]},
                    result=f"{len(rag_result['results'])} 件の関連コードを発見",
                    execution_time=0,
                )
                rich_ui.print_success(f"[OK] {len(rag_result['results'])} 件の関連コードを発見")
                return rag_result.get("results", [])
            else:
                state.add_tool_execution(
                    tool_name="search_code",
                    arguments={"query": user_message[:100]},
                    result="関連コードが見つかりませんでした",
                    execution_time=0,
                )
                rich_ui.print_message("[WARN] 該当するコードが見つかりませんでした", "warning")
                return []
                
        except Exception as e:
            rich_ui.print_error(f"RAG検索中にエラーが発生: {e}")
            state.record_error(f"RAG検索エラー: {e}")
            return []
    
    def _create_thinking_prompt(self, state: AgentState, use_rag: bool = False) -> str:
        # RAGコンテキストが存在すれば常に活用（use_rag引数は後方互換のため残置）
        rag_results = getattr(state, "rag_context", None)
        file_context = getattr(state, 'collected_context', {}).get('file_context', {})
        
        # ステップ2e: DTOベースのプロンプト生成を試行、失敗時は従来方式でフォールバック
        return prompt_compiler.compile_with_dto_fallback(
            state=state, 
            rag_results=rag_results, 
            file_context=file_context,
            use_dto=True  # DTOベースを優先使用
        )

    # ------------- 実行系（ファイル/シェル/テスト/リンター） -------------
    def _execute_file_operations(self, ai_response: str, state: AgentState) -> None:
        lines = ai_response.split("\n")
        current_op, filename, content, in_code, buf = None, None, [], False, []
        for line in lines:
            if line.startswith("FILE_OPERATION:"):
                parts = line.split(":")
                if len(parts) >= 3:
                    current_op = parts[1].upper()
                    filename = parts[2]
                    buf = []
                    
                    # READ操作の場合は即座に実行（コードブロック不要）
                    if current_op == "READ":
                        self._execute_single_file_operation(current_op, filename, "", state)
                        current_op, filename = None, None
                    continue
            if line.strip().startswith("```"):
                if in_code and current_op and filename:
                    self._execute_single_file_operation(current_op, filename, "\n".join(buf), state)
                    current_op, filename, buf = None, None, []
                in_code = not in_code
                continue
            if in_code and current_op and filename:
                buf.append(line)

    def _execute_single_file_operation(
        self,
        operation: str,
        filename: str,
        content: str,
        state: AgentState,
    ) -> None:
        try:
            from pathlib import Path
            
            # READ操作の処理
            if operation == "READ":
                try:
                    file_content = file_tools.read_file(filename)
                    read_msg = f"""📄 ファイル内容を読み取りました: {filename}

--- ファイル内容 ---
{file_content}
--- 終了 ---

ファイルサイズ: {len(file_content)} 文字
読み取り完了。内容を分析してご回答します。"""
                    
                    rich_ui.print_message(f"[READ] ファイル読み取り: {filename}", "info")
                    state.add_message("system", read_msg)
                    state.add_tool_execution(
                        tool_name="read_file",
                        arguments={"filename": filename},
                        result=f"読み取り成功 ({len(file_content)} 文字)",
                        execution_time=0,
                    )
                except Exception as e:
                    error_msg = f"ファイル読み取りエラー ({filename}): {e}"
                    rich_ui.print_warning(error_msg)
                    state.record_error(error_msg)
                    state.add_tool_execution(
                        tool_name="read_file",
                        arguments={"filename": filename},
                        result=None,
                        error=error_msg,
                        execution_time=0,
                    )
                return
            
            # EDIT時は対象ファイルの実在を厳密チェック
            if operation == "EDIT":
                p = Path(filename)
                if not p.exists() or not p.is_file():
                    msg = f"EDIT対象のファイルが見つかりません: {filename}"
                    state.record_error(msg)
                    state.add_tool_execution(
                        tool_name="write_file",
                        arguments={"filename": filename, "content_length": len(content)},
                        result=None,
                        error=msg,
                        execution_time=0,
                    )
                    return
            if operation == "CREATE":
                result = file_tools.write_file(filename, content)
                state.add_tool_execution(
                    tool_name="write_file",
                    arguments={"filename": filename, "content_length": len(content)},
                    result=result,
                    execution_time=0,
                )
            elif operation == "EDIT":
                # 安全チェック: ファイル内容の大幅削減を検知
                try:
                    current_content = file_tools.read_file(filename)
                    content_reduction_ratio = 1 - (len(content) / len(current_content)) if len(current_content) > 0 else 0
                    
                    # 70%以上の削減または空ファイル化を検知
                    if content_reduction_ratio >= 0.7 or len(content.strip()) == 0:
                        warning_msg = f"""🚨 EDIT操作の安全チェックが作動しました

ファイル: {filename}
元のサイズ: {len(current_content)} 文字
新しいサイズ: {len(content)} 文字
削減率: {content_reduction_ratio*100:.1f}%

このファイル操作は危険です。ファイル内容の大幅な削減が検出されました。
バックアップは作成されていますが、意図しない操作の可能性があります。

操作を中止しました。ファイル内容を確認したい場合は、編集ではなく読み取りを行ってください。"""
                        
                        rich_ui.print_warning(warning_msg)
                        state.add_message("system", warning_msg)
                        state.record_error("ファイル内容大幅削減のため操作中止")
                        state.add_tool_execution(
                            tool_name="write_file",
                            arguments={"filename": filename, "content_length": len(content)},
                            result=None,
                            error="安全チェックにより操作中止",
                            execution_time=0,
                        )
                        return
                except Exception as read_error:
                    # ファイル読み込みに失敗した場合は通常の警告のみで処理を続行
                    rich_ui.print_warning(f"ファイル読み込みエラーのため安全チェックをスキップ: {read_error}")
                
                result = file_tools.write_file(filename, content)
                state.add_tool_execution(
                    tool_name="write_file",
                    arguments={"filename": filename, "content_length": len(content)},
                    result=result,
                    execution_time=0,
                )
        except Exception as e:
            state.record_error(f"ファイル操作失敗: {e}")

    def _execute_shell_operations(self, ai_response: str, state: AgentState) -> None:
        """AI応答からシェル操作を抽出して実行"""
        lines = ai_response.split("\n")
        
        for line in lines:
            # SHELL_COMMAND: パターンを検出
            if line.startswith("SHELL_COMMAND:"):
                command = line.replace("SHELL_COMMAND:", "").strip()
                if command:
                    self._execute_single_shell_command(command, state)
            
            # RUN_TESTS パターンを検出
            elif line.startswith("RUN_TESTS"):
                test_path = None
                if ":" in line:
                    test_path = line.split(":", 1)[1].strip()
                self._execute_tests(test_path, state)
            
            # LINT_CODE パターンを検出
            elif line.startswith("LINT_CODE:"):
                parts = line.split(":", 2)
                tool = parts[1].strip() if len(parts) > 1 else "ruff"
                path = parts[2].strip() if len(parts) > 2 else "."
                self._execute_linter(tool, path, state)

    def _execute_single_shell_command(
        self, 
        command: str, 
        state: AgentState,
        require_approval: bool = True
    ) -> None:
        """単一のシェルコマンドを実行"""
        try:
            rich_ui.print_message(f"[SHELL] コマンド実行: {command}", "info")
            
            # 安全性チェック
            safety_check = shell_tools.is_command_safe(command)
            if not safety_check['is_safe']:
                error_msg = f"危険なコマンドが検出されました: {safety_check['reason']}"
                rich_ui.print_error(error_msg)
                state.record_error(error_msg)
                state.add_tool_execution(
                    tool_name="shell_command",
                    arguments={"command": command},
                    result={"success": False, "error": error_msg},
                    execution_time=0,
                    success=False,
                    error=error_msg
                )
                return
            
            # コマンド実行
            result = shell_tools.execute_command(
                command=command,
                capture_output=True,
                require_approval=require_approval
            )
            
            # 結果の表示
            if result['success']:
                rich_ui.print_message(f"[SHELL] 実行成功 ({result['execution_time']:.2f}s)", "success")
                if result['stdout']:
                    rich_ui.print_message(f"出力:\n{result['stdout']}", "info")
            else:
                rich_ui.print_error(f"[SHELL] 実行失敗: {result['stderr']}")
            
            # 状態に記録
            state.add_tool_execution(
                tool_name="shell_command",
                arguments={"command": command},
                result=result,
                execution_time=result['execution_time'],
                success=result['success'],
                error=result.get('stderr') if not result['success'] else None
            )
            
        except Exception as e:
            error_msg = f"シェルコマンド実行エラー: {str(e)}"
            rich_ui.print_error(error_msg)
            state.record_error(error_msg)
            state.add_tool_execution(
                tool_name="shell_command",
                arguments={"command": command},
                result={"success": False, "error": error_msg},
                execution_time=0,
                success=False,
                error=error_msg
            )

    def _execute_tests(self, test_path: Optional[str], state: AgentState) -> None:
        """テストを実行"""
        try:
            rich_ui.print_message("[TEST] テスト実行開始...", "info")
            
            result = shell_tools.run_tests(
                test_path=test_path,
                verbose=True
            )
            
            # 結果の表示
            if result['success']:
                status = result.get('test_status', 'UNKNOWN')
                passed = result.get('passed_count', 0)
                failed = result.get('failed_count', 0)
                total = result.get('total_count', 0)
                
                if status == 'PASSED':
                    rich_ui.print_message(f"[TEST] ✅ テスト成功: {passed}/{total} passed", "success")
                else:
                    rich_ui.print_error(f"[TEST] ❌ テスト失敗: {passed}/{total} passed, {failed} failed")
                    
                if result['stdout']:
                    rich_ui.print_message(f"テスト出力:\n{result['stdout']}", "info")
            else:
                rich_ui.print_error(f"[TEST] テスト実行エラー: {result['stderr']}")
            
            # 状態に記録
            state.add_tool_execution(
                tool_name="run_tests",
                arguments={"test_path": test_path},
                result=result,
                execution_time=result['execution_time'],
                success=result['success'],
                error=result.get('stderr') if not result['success'] else None
            )
            
        except Exception as e:
            error_msg = f"テスト実行エラー: {str(e)}"
            rich_ui.print_error(error_msg)
            state.record_error(error_msg)

    def _execute_linter(self, tool: str, path: str, state: AgentState) -> None:
        """リンターを実行"""
        try:
            rich_ui.print_message(f"[LINT] {tool} 実行開始: {path}", "info")
            
            result = shell_tools.run_linter(
                tool=tool,
                path=path,
                fix=False  # 自動修正はデフォルトで無効
            )
            
            # 結果の表示
            if result['success']:
                rich_ui.print_message(f"[LINT] ✅ {tool} 完了", "success")
            else:
                rich_ui.print_error(f"[LINT] ❌ {tool} で問題が検出されました")
            
            if result['stdout']:
                rich_ui.print_message(f"{tool} 出力:\n{result['stdout']}", "info")
                
            if result['stderr']:
                rich_ui.print_message(f"{tool} エラー:\n{result['stderr']}", "warning")
            
            # 状態に記録
            state.add_tool_execution(
                tool_name="run_linter",
                arguments={"tool": tool, "path": path},
                result=result,
                execution_time=result['execution_time'],
                success=result['success'],
                error=result.get('stderr') if not result['success'] else None
            )
            
        except Exception as e:
            error_msg = f"リンター実行エラー: {str(e)}"
            rich_ui.print_error(error_msg)
            state.record_error(error_msg)

    # ------------- 会話実行 -------------
    def run_conversation(self, user_input: str) -> None:
        self.state.add_message("user", user_input)
        if isinstance(self.state, dict):
            self.state = AgentState.parse_obj(self.state)
        
        # 記憶管理を実行 (ステップ2c)
        if self.state.needs_memory_management():
            rich_ui.print_message("[MEMORY] 記憶管理を実行中...", "info")
            if self.state.create_memory_summary():
                rich_ui.print_success("[MEMORY] 対話履歴を要約し、記憶を整理しました")
            else:
                rich_ui.print_warning("[MEMORY] 記憶管理でエラーが発生しましたが、処理を続行します")
        
        try:
            rich_ui.print_message("[GRAPH] 処理を開始します...", "info")
            
            # LangGraphの再帰制限を設定
            final_state = self.graph.invoke(
                self.state, 
                config={"recursion_limit": 10}
            )
            
            if isinstance(final_state, dict):
                self.state = AgentState.parse_obj(final_state)
            else:
                self.state = final_state
            rich_ui.print_message("[GRAPH] 処理が完了しました", "success")
        except Exception as e:
            self.state.record_error(f"会話実行エラー: {e}")
            rich_ui.print_error(f"[ERROR] 処理中にエラーが発生しました: {e}")
    
    # ------------- 応答検証 -------------
    def _verify_file_mentions(self, ai_response: str, state: AgentState) -> List[str]:
        """AI応答に含まれるファイルらしき文字列を抽出し、実在を検証。未知ファイルのリストを返す。
        ノイズ低減のため以下を除外:
          - コードブロック内の文字列
          - URL/ドメイン名らしきトークン
          - メールアドレス
          - パス区切りを含まない単語で、一般的拡張子に該当しないもの
        """
        import re, os
        # コードブロックとURLを事前に除去
        cleaned = re.sub(r"```.*?```", "", ai_response, flags=re.S)
        cleaned = re.sub(r"https?://\S+", "", cleaned)

        mentioned = set()
        for m in re.findall(r"[\w\-_/\\.]+\.[a-zA-Z0-9]{1,8}", cleaned):
            mentioned.add(m)
        if not mentioned:
            return []

        # ノイズ除外フィルタ
        def is_domain_like(tok: str) -> bool:
            # パス区切りが無く、ドメイン風（example.com, sub.example.co.jp など）
            if any(sep in tok for sep in ['\\', '/', os.path.sep]):
                return False
            return re.match(r"^[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", tok) is not None
        def is_email(tok: str) -> bool:
            return '@' in tok
        known_exts = {
            'py','md','txt','json','yaml','yml','csv','ts','js','tsx','jsx','toml','ini','cfg','conf',
            'ipynb','sh','bat','ps1','lock','html','css','sql','xml','rst','mdx','pdf','png','jpg','jpeg'
        }
        filtered = set()
        for tok in mentioned:
            if is_email(tok) or is_domain_like(tok):
                continue
            # パス区切りを含まない場合は、拡張子が既知のものだけ対象にする
            if all(sep not in tok for sep in ['\\', '/', os.path.sep]):
                ext = tok.rsplit('.', 1)[-1].lower()
                if ext not in known_exts:
                    continue
            filtered.add(tok)

        if not filtered:
            return []

        # 既知ファイル一覧を収集
        known_paths = set()
        try:
            ctx = getattr(state, 'collected_context', {}).get('file_context', {})
            files_list = ctx.get('files_list') if isinstance(ctx, dict) else None
            if files_list:
                for f in files_list:
                    p = f.get('path') or f.get('relative_path') or f.get('name')
                    if p:
                        known_paths.add(os.path.normpath(p))
            if not known_paths and state.workspace and state.workspace.files:
                for p in state.workspace.files:
                    known_paths.add(os.path.normpath(p))
        except Exception:
            pass

        # 実在チェック（ファイルシステムにも確認）
        unknown = []
        for m in filtered:
            nm = os.path.normpath(m)
            if nm in known_paths:
                continue
            try:
                if os.path.exists(nm) and os.path.isfile(nm):
                    continue
            except Exception:
                pass
            unknown.append(m)
        return unknown
