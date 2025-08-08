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

        # 危険性評価 → 人間承認 or 直接ツール実行
        workflow.add_conditional_edges(
            "危険性評価",
            self._requires_human_approval,
            {
                "require_approval": "人間承認",
                "direct_execution": "ツール実行",
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
            
            user_message = recent[-1].content
            
            # ファイル情報要求を検出して実行
            file_requests = self._detect_file_info_requests(user_message)
            file_context = self._gather_file_context(file_requests, state_obj)
            
            # RAG検索も実行
            rag_context = self._gather_rag_context(user_message, state_obj)
            
            # コンテキストを結合して保存
            if not hasattr(state_obj, 'collected_context'):
                state_obj.collected_context = {}
            state_obj.collected_context.update({
                'file_context': file_context,
                'rag_context': rag_context
            })
            
            # 既存の仕組みとの互換性のため
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
                
                # 安全性評価結果を状態に記録
                if not hasattr(state_obj, 'safety_assessment'):
                    state_obj.safety_assessment = {}
                
                state_obj.safety_assessment.update({
                    'risk_level': safety_analysis['risk_level'],
                    'detected_risks': safety_analysis['risks'],
                    'requires_approval': safety_analysis['requires_approval'],
                    'assessment_time': datetime.now()
                })
                
                if safety_analysis['requires_approval']:
                    rich_ui.print_warning(f"[SAFETY] 危険度: {safety_analysis['risk_level']} - 人間承認が必要です")
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
            
            # 今回は自動承認設定を確認
            if state_obj.auto_approve:
                rich_ui.print_success("[APPROVAL] 自動承認設定により承認されました")
                if not hasattr(state_obj, 'approval_result'):
                    state_obj.approval_result = 'approved'
            else:
                # 実際のUI実装では、ここでユーザー入力を待つ
                rich_ui.print_message("[APPROVAL] 承認待機中... (デモモードでは自動承認)", "info")
                if not hasattr(state_obj, 'approval_result'):
                    state_obj.approval_result = 'approved'  # デモ用
            
        except Exception as e:
            state_obj.record_error(f"人間承認エラー: {e}")
            rich_ui.print_error(f"[ERROR] 人間承認中にエラーが発生しました: {e}")
            if not hasattr(state_obj, 'approval_result'):
                state_obj.approval_result = 'rejected'
        
        return state_obj

    def _result_verification_node(self, state: Any) -> AgentState:
        """結果確認ノード：処理結果をまとめて表示"""
        state_obj = AgentState.parse_obj(state) if isinstance(state, dict) else state
        
        try:
            state_obj.update_graph_state(current_node="結果確認", add_to_path="結果確認")
            
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
        """コンテキスト収集が必要かどうかを判断（ステップ2d拡張）"""
        state_obj = AgentState.parse_obj(state) if isinstance(state, dict) else state
        
        # ループ制限チェック
        if state_obj.graph_state.loop_count >= state_obj.graph_state.max_loops:
            rich_ui.print_warning("ループ制限に達したため処理を終了します")
            return "complete"
        
        # 最新のAI応答を確認
        recent_messages = state_obj.get_recent_messages(1)
        if not recent_messages or recent_messages[-1].role != "assistant":
            return "complete"
        
        ai_response = recent_messages[-1].content
        
        # ツール実行指示がある場合は安全性評価へ
        if "FILE_OPERATION:" in ai_response:
            rich_ui.print_message("[ROUTING] ファイル操作指示を検出 → 安全性評価", "info")
            return "assess_safety"
        
        # RAGインデックスが利用可能で情報要求がある場合はコンテキスト収集
        try:
            status = rag_tools.get_index_status()
            if status.get("status") == "ready":
                # 情報を求めている質問かどうか判定
                info_keywords = ['どこ', 'なに', '何', 'どのように', 'どの', '教えて', '見せて', '確認', '検索']
                if any(keyword in ai_response.lower() for keyword in info_keywords):
                    rich_ui.print_message("[ROUTING] 情報要求を検出 → コンテキスト収集", "info")
                    return "collect_context"
        except Exception as e:
            rich_ui.print_message(f"[ROUTING] RAG状態確認エラー: {e}", "warning")
        
        # デフォルトは完了
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

    def _analyze_tool_error(self, tool_execution) -> Dict[str, Any]:
        """ツール実行エラーを分析"""
        error_msg = tool_execution.error or ""
        error_type = "UNKNOWN"
        error_category = "GENERAL"
        fixes = []
        can_retry = False
        
        try:
            # ファイル関連エラー
            if "FileNotFoundError" in error_msg or "No such file" in error_msg:
                error_type = "FILE_NOT_FOUND"
                error_category = "FILE_SYSTEM"
                fixes.append("ファイルパスを確認してください")
                fixes.append("ファイルが存在するかlist_filesで確認してください")
                can_retry = True
            
            elif "PermissionError" in error_msg or "Permission denied" in error_msg:
                error_type = "PERMISSION_DENIED"
                error_category = "FILE_SYSTEM"
                fixes.append("ファイルの書き込み権限を確認してください")
                fixes.append("管理者権限での実行を検討してください")
                can_retry = False
            
            elif "FileExistsError" in error_msg or "File exists" in error_msg:
                error_type = "FILE_EXISTS"
                error_category = "FILE_SYSTEM"
                fixes.append("既存ファイルを上書きするか確認してください")
                fixes.append("ファイル名を変更してください")
                can_retry = True
            
            # 構文エラー
            elif "SyntaxError" in error_msg:
                error_type = "SYNTAX_ERROR"
                error_category = "CODE"
                fixes.append("コードの構文を確認してください")
                fixes.append("インデントとブレースをチェックしてください")
                can_retry = True
            
            # インポートエラー
            elif "ModuleNotFoundError" in error_msg or "ImportError" in error_msg:
                error_type = "IMPORT_ERROR"
                error_category = "DEPENDENCY"
                fixes.append("必要なモジュールをインストールしてください")
                fixes.append("インポートパスを確認してください")
                can_retry = True
                
        except Exception as e:
            error_type = "ANALYSIS_ERROR"
            fixes.append(f"エラー分析中に問題が発生: {e}")
        
        return {
            'type': error_type,
            'category': error_category,
            'fixes': fixes,
            'can_retry': can_retry
        }

    # ------------- 従来のヘルパー関数 -------------
    def _detect_file_info_requests(self, user_message: str) -> Dict[str, Any]:
        """ユーザーメッセージからファイル情報要求を検出"""
        requests = {
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
        read_keywords = ['読んで', '読み込', 'read', '内容を', '中身を', '確認して']
        if any(k in msg_lower for k in read_keywords):
            import re
            # 簡単なファイル名検出
            file_patterns = re.findall(r'\b[\w\-_/\\\.]+\.[a-zA-Z]{1,5}\b', user_message)
            requests['read_files'].extend(file_patterns[:3])
        
        return requests
    
    def _gather_file_context(self, requests: Dict[str, Any], state: AgentState) -> Dict[str, Any]:
        """ファイルコンテキストを収集"""
        context = {
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
                    rich_ui.print_message(f"[READ] ファイルを読み込み中: {file_path}", "info")
                    content = file_tools.read_file(file_path)
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
        rag_results = getattr(state, "rag_context", None) if use_rag else None
        file_context = getattr(state, 'collected_context', {}).get('file_context', {})
        return prompt_compiler.compile_system_prompt(state, rag_results, file_context=file_context)

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
            if operation == "CREATE":
                result = file_tools.write_file(filename, content)
                state.add_tool_execution(
                    tool_name="write_file",
                    arguments={"filename": filename, "content_length": len(content)},
                    result=result,
                    execution_time=0,
                )
            elif operation == "EDIT":
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
                config={"recursion_limit": 10}  # さらに削減して10に
            )
            
            if isinstance(final_state, dict):
                self.state = AgentState.parse_obj(final_state)
            else:
                self.state = final_state
            rich_ui.print_message("[GRAPH] 処理が完了しました", "success")
        except Exception as e:
            self.state.record_error(f"会話実行エラー: {e}")
            rich_ui.print_error(f"[ERROR] 処理中にエラーが発生しました: {e}")
