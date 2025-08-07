"""
LangGraphベースのエージェントオーケストレーション
ステップ2b: RAG機能統合版 - プロジェクト理解能力搭載
"""
import time
from typing import Any, Dict, List, Optional
from datetime import datetime

from langchain.schema import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain.tools import BaseTool
from langgraph.graph import StateGraph, END
from pydantic import BaseModel

from ..base.llm_client import llm_manager, LLMClientError  
from ..state.agent_state import AgentState
from ..tools.file_tools import file_tools
from ..tools.rag_tools import rag_tools, RAGToolError
from ..prompts.prompt_compiler import prompt_compiler
from ..ui.rich_ui import rich_ui


class GraphOrchestrator:
    """LangGraphベースのエージェントオーケストレーション管理"""
    
    def __init__(self, state: AgentState):
        """初期化
        
        Args:
            state: エージェントの状態オブジェクト
        """
        self.state = state
        self.tools = self._initialize_tools()
        self.graph = self._create_graph()
    
    def _initialize_tools(self) -> Dict[str, Any]:
        """利用可能なツールを初期化
        
        Returns:
            ツール名と実行可能オブジェクトのマッピング
        """
        return {
            # ファイル操作ツール
            "list_files": file_tools.list_files,
            "read_file": file_tools.read_file,
            "write_file": file_tools.write_file,
            "get_file_info": file_tools.get_file_info,
            "create_directory": file_tools.create_directory,
            "run_tests": file_tools.run_tests,
            
            # RAGツール（ステップ2b）
            "index_project": rag_tools.index_project,
            "search_code": rag_tools.search_code,
            "get_index_status": rag_tools.get_index_status,
        }
    
    def _create_graph(self) -> StateGraph:
        """LangGraphのStateGraphを作成
        
        Returns:
            構築されたStateGraph
        """
        # グラフ構造を定義
        workflow = StateGraph(AgentState)
        
        # ノードを追加
        workflow.add_node("思考", self._thinking_node)
        workflow.add_node("コンテキスト収集", self._context_collection_node)  # 新規追加
        workflow.add_node("ツール実行", self._tool_execution_node)
        workflow.add_node("人間承認", self._human_approval_node)
        workflow.add_node("結果確認", self._result_verification_node)
        
        # エントリーポイントを設定
        workflow.set_entry_point("思考")
        
        # エッジ（フロー）を定義
        workflow.add_conditional_edges(
            "思考",
            self._should_collect_context,
            {
                "collect_context": "コンテキスト収集",
                "use_tools": "ツール実行", 
                "complete": END,
                "need_approval": "人間承認"
            }
        )
        
        workflow.add_conditional_edges(
            "コンテキスト収集",
            self._should_use_tools_after_context,
            {
                "use_tools": "ツール実行",
                "complete": END,
                "need_approval": "人間承認"
            }
        )
        
        workflow.add_edge("ツール実行", "結果確認")
        workflow.add_edge("人間承認", "ツール実行")
        workflow.add_conditional_edges(
            "結果確認",
            self._should_continue,
            {
                "continue": "思考",
                "complete": END,
                "retry": "思考"
            }
        )
        
        return workflow.compile()
    
    def _thinking_node(self, state: AgentState) -> AgentState:
        """思考ノード: AIが現在の状況を分析し、次のアクションを決定
        
        Args:
            state: 現在のエージェント状態
            
        Returns:
            更新された状態
        """
        try:
            state.update_graph_state(current_node="思考", add_to_path="思考")
            
            # システムプロンプトを生成（RAGコンテキストは考慮しない - 次のノードで収集）
            system_prompt = self._create_thinking_prompt(state, use_rag=False)
            
            # 最新のユーザーメッセージを取得
            recent_messages = state.get_recent_messages(1)
            if not recent_messages:
                raise ValueError("処理するメッセージがありません")
            
            user_message = recent_messages[-1].content
            
            # LLMで思考処理
            rich_ui.print_message("🤔 思考中...", "info")
            start_time = time.time()
            
            ai_response = llm_manager.chat(user_message, system_prompt)
            execution_time = time.time() - start_time
            
            # 応答を記録
            state.add_message("assistant", ai_response)
            state.add_tool_execution(
                tool_name="thinking", 
                arguments={"user_message": user_message[:100]},
                result=ai_response[:200],
                execution_time=execution_time
            )
            
            rich_ui.print_conversation_message("assistant", ai_response)
            
        except LLMClientError as e:
            state.record_error(f"LLM処理エラー: {e}")
            rich_ui.print_error(f"AI処理エラー: {e}")
        except Exception as e:
            state.record_error(f"思考ノードエラー: {e}")
            rich_ui.print_error(f"思考処理中にエラーが発生しました: {e}")
        
        return state
    
    def _tool_execution_node(self, state: AgentState) -> AgentState:
        """ツール実行ノード: 特定されたツールを実行
        
        Args:
            state: 現在のエージェント状態
            
        Returns:
            更新された状態
        """
        state.update_graph_state(current_node="ツール実行", add_to_path="ツール実行")
        
        # 最新のAIメッセージからツール実行指示を抽出
        recent_messages = state.get_recent_messages(1)
        if not recent_messages or recent_messages[-1].role != "assistant":
            return state
        
        ai_response = recent_messages[-1].content
        
        # ファイル操作の指示を解析して実行
        self._execute_file_operations(ai_response, state)
        
        return state
    
    def _human_approval_node(self, state: AgentState) -> AgentState:
        """人間承認ノード: 危険な操作の前に人間の承認を求める
        
        Args:
            state: 現在のエージェント状態
            
        Returns:
            更新された状態
        """
        state.update_graph_state(current_node="人間承認", add_to_path="人間承認")
        
        # TODO: 実装予定 - 現在はパススルー
        rich_ui.print_message("⚠️  人間承認が必要な操作です", "warning")
        
        return state
    
    def _result_verification_node(self, state: AgentState) -> AgentState:
        """結果確認ノード: ツール実行結果を確認し、次のアクションを決定
        
        Args:
            state: 現在のエージェント状態
            
        Returns:
            更新された状態
        """
        state.update_graph_state(current_node="結果確認", add_to_path="結果確認")
        
        # 最新のツール実行結果を確認
        if state.tool_executions:
            latest_execution = state.tool_executions[-1]
            if latest_execution.error:
                rich_ui.print_error(f"ツール実行でエラーが発生しました: {latest_execution.error}")
                if not state.increment_retry_count():
                    rich_ui.print_error("最大リトライ回数に達しました")
                    state.update_graph_state(next_nodes=["complete"])
                else:
                    state.update_graph_state(next_nodes=["retry"])
            else:
                rich_ui.print_success("ツール実行が成功しました")
                state.reset_retry_count()
                state.update_graph_state(next_nodes=["complete"])
        
        return state
    
    def _should_collect_context(self, state: AgentState) -> str:
        """コンテキスト収集の必要性を判定
        
        Args:
            state: 現在のエージェント状態
            
        Returns:
            次のノード名
        """
        # RAGインデックスが利用可能かチェック
        try:
            index_status = rag_tools.get_index_status()
            if index_status.get("status") == "ready":
                # インデックスが利用可能な場合はコンテキスト収集
                return "collect_context"
        except Exception:
            pass  # RAGが利用できない場合は通常フローへ
        
        # RAGが利用できない場合は直接ツール判定へ
        return self._should_use_tools(state)
    
    def _should_use_tools_after_context(self, state: AgentState) -> str:
        """コンテキスト収集後のツール使用判定
        
        Args:
            state: 現在のエージェント状態
            
        Returns:
            次のノード名
        """
        return self._should_use_tools(state)
    
    def _should_use_tools(self, state: AgentState) -> str:
        """ツール使用の必要性を判定
        
        Args:
            state: 現在のエージェント状態
            
        Returns:
            次のノード名
        """
        # 最新のAIメッセージをチェック
        recent_messages = state.get_recent_messages(1)
        if recent_messages and recent_messages[-1].role == "assistant":
            ai_response = recent_messages[-1].content
            
            # FILE_OPERATION指示があるかチェック
            if "FILE_OPERATION:" in ai_response:
                return "use_tools"
        
        return "complete"
    
    def _should_continue(self, state: AgentState) -> str:
        """処理継続の必要性を判定
        
        Args:
            state: 現在のエージェント状態
            
        Returns:
            次のノード名
        """
        # エラーがある場合の処理
        if state.last_error and state.retry_count < state.max_retries:
            return "retry"
        
        # アクティブなタスクステップがある場合は継続
        if state.get_active_task_steps():
            return "continue"
        
        # ループ回数制限チェック
        if not state.increment_loop_count():
            rich_ui.print_warning("最大ループ回数に達しました")
            return "complete"
        
        return "complete"
    
    def _context_collection_node(self, state: AgentState) -> AgentState:
        """コンテキスト収集ノード: RAG検索で関連コードを収集
        
        Args:
            state: 現在のエージェント状態
            
        Returns:
            更新された状態
        """
        try:
            state.update_graph_state(current_node="コンテキスト収集", add_to_path="コンテキスト収集")
            
            # 最新のユーザーメッセージを取得
            recent_messages = state.get_recent_messages(1)
            if not recent_messages:
                return state
            
            user_message = recent_messages[-1].content
            
            rich_ui.print_message("🔍 関連コードを検索中...", "info")
            start_time = time.time()
            
            # RAG検索実行
            search_result = rag_tools.search_code(
                query=user_message,
                max_results=5
            )
            
            execution_time = time.time() - start_time
            
            if search_result.get("success") and search_result.get("results"):
                # 検索結果を状態に記録
                state.add_tool_execution(
                    tool_name="search_code",
                    arguments={"query": user_message[:100]},
                    result=f"{len(search_result['results'])} 件の関連コードを発見",
                    execution_time=execution_time
                )
                
                # メタデータとして検索結果を保存
                if not hasattr(state, 'rag_context'):
                    state.rag_context = []
                state.rag_context = search_result['results']
                
                rich_ui.print_success(f"✅ {len(search_result['results'])} 件の関連コードを発見")
            else:
                # 検索結果なしまたはエラー
                state.add_tool_execution(
                    tool_name="search_code",
                    arguments={"query": user_message[:100]},
                    result="関連コードが見つかりませんでした",
                    execution_time=execution_time
                )
                
                if not hasattr(state, 'rag_context'):
                    state.rag_context = []
                
                rich_ui.print_message("🔍 関連するコードが見つかりませんでした", "warning")
            
        except RAGToolError as e:
            rich_ui.print_warning(f"RAG検索エラー: {e}")
            state.record_error(f"RAG検索エラー: {e}")
            
        except Exception as e:
            rich_ui.print_error(f"コンテキスト収集中にエラーが発生: {e}")
            state.record_error(f"コンテキスト収集エラー: {e}")
        
        return state

    def _create_thinking_prompt(self, state: AgentState, use_rag: bool = False) -> str:
        """思考ノード用のシステムプロンプトを生成
        
        Args:
            state: 現在のエージェント状態
            use_rag: RAG検索結果を使用するか
            
        Returns:
            生成されたプロンプト
        """
        # RAG検索結果を取得
        rag_results = getattr(state, 'rag_context', None) if use_rag else None
        
        # プロンプトコンパイラを使用
        return prompt_compiler.compile_system_prompt(state, rag_results)
    
    def _execute_file_operations(self, ai_response: str, state: AgentState) -> None:
        """AIの応答からファイル操作を解析・実行
        
        Args:
            ai_response: AIの応答テキスト
            state: エージェント状態（実行履歴記録用）
        """
        lines = ai_response.split('\n')
        
        current_operation = None
        current_filename = None
        current_content = []
        in_code_block = False
        
        for line in lines:
            # ファイル操作の指示をチェック
            if line.startswith('FILE_OPERATION:'):
                parts = line.split(':')
                if len(parts) >= 3:
                    current_operation = parts[1].upper()  # CREATE or EDIT
                    current_filename = parts[2]
                    current_content = []
                    continue
            
            # コードブロックの開始・終了をチェック
            if line.strip().startswith('```'):
                if in_code_block and current_operation and current_filename:
                    # コードブロック終了 - ファイル操作を実行
                    self._execute_single_file_operation(
                        current_operation, 
                        current_filename, 
                        '\n'.join(current_content),
                        state
                    )
                    current_operation = None
                    current_filename = None
                    current_content = []
                in_code_block = not in_code_block
                continue
            
            # コードブロック内の内容を収集
            if in_code_block and current_operation and current_filename:
                current_content.append(line)
    
    def _execute_single_file_operation(
        self, 
        operation: str, 
        filename: str, 
        content: str,
        state: AgentState
    ) -> None:
        """単一のファイル操作を実行
        
        Args:
            operation: 操作タイプ (CREATE/EDIT)
            filename: ファイル名
            content: ファイル内容
            state: エージェント状態
        """
        start_time = time.time()
        
        try:
            if operation == 'CREATE':
                rich_ui.print_message(f"📁 ファイルを作成中: {filename}", "info")
                
                # プレビュー表示
                preview = content[:200] + "..." if len(content) > 200 else content
                rich_ui.print_panel(f"```\n{preview}\n```", f"作成予定: {filename}", "warning")
                
                # 承認確認
                if not rich_ui.get_confirmation(f"ファイル '{filename}' を作成しますか？"):
                    rich_ui.print_message("ファイル作成をキャンセルしました。", "warning")
                    return
                
                # ファイル作成実行
                result = file_tools.write_file(filename, content)
                
                execution_time = time.time() - start_time
                state.add_tool_execution(
                    tool_name="write_file",
                    arguments={"filename": filename, "content_length": len(content)},
                    result=result,
                    execution_time=execution_time
                )
                
                rich_ui.print_success(f"ファイルを作成しました: {filename} ({result['size']} bytes)")
                
                if result['backup_created']:
                    rich_ui.print_message(f"既存ファイルのバックアップ: {result['backup_path']}", "info")
                
            elif operation == 'EDIT':
                rich_ui.print_message(f"✏️ ファイルを編集中: {filename}", "info")
                
                # 既存ファイルの確認
                try:
                    existing_content = file_tools.read_file(filename)
                    rich_ui.print_message(f"既存ファイルを編集します: {filename}", "info")
                except Exception:
                    rich_ui.print_message(f"新規ファイルとして作成します: {filename}", "info")
                
                # プレビュー表示
                preview = content[:200] + "..." if len(content) > 200 else content
                rich_ui.print_panel(f"```\n{preview}\n```", f"編集予定: {filename}", "warning")
                
                # 承認確認
                if not rich_ui.get_confirmation(f"ファイル '{filename}' を編集しますか？"):
                    rich_ui.print_message("ファイル編集をキャンセルしました。", "warning")
                    return
                
                # ファイル編集実行
                result = file_tools.write_file(filename, content)
                
                execution_time = time.time() - start_time
                state.add_tool_execution(
                    tool_name="write_file",
                    arguments={"filename": filename, "content_length": len(content)},
                    result=result,
                    execution_time=execution_time
                )
                
                rich_ui.print_success(f"ファイルを編集しました: {filename} ({result['size']} bytes)")
                
                if result['backup_created']:
                    rich_ui.print_message(f"バックアップを作成しました: {result['backup_path']}", "info")
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_message = f"ファイル操作に失敗しました: {e}"
            
            state.add_tool_execution(
                tool_name="write_file",
                arguments={"filename": filename},
                error=error_message,
                execution_time=execution_time
            )
            
            rich_ui.print_error(error_message)
    
    def run_conversation(self, user_input: str) -> None:
        """会話を実行
        
        Args:
            user_input: ユーザーからの入力
        """
        try:
            # ユーザーメッセージを状態に追加
            self.state.add_message("user", user_input)
            
            # グラフを実行
            rich_ui.print_message("🚀 処理を開始します...", "info")
            
            # グラフの実行
            final_state = self.graph.invoke(self.state)
            
            # 最終状態を更新
            self.state = final_state
            
            rich_ui.print_message("✅ 処理が完了しました", "success")
            
        except Exception as e:
            self.state.record_error(f"会話実行エラー: {e}")
            rich_ui.print_error(f"処理中にエラーが発生しました: {e}")