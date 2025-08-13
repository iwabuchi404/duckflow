"""
Duckflow v0.3.2-alpha - 5ノードアーキテクチャ実装版
LangGraphベースの評価ノード中心品質保証ループ
Duck Pacemaker統合AI安全システム搭載
"""
import os
import sys
import uuid
from datetime import datetime
from typing import Optional

from .base.config import config_manager
from .base.llm_client import llm_manager, LLMClientError
from .state.agent_state import AgentState, WorkspaceInfo
from .orchestration.five_node_orchestrator import FiveNodeOrchestrator
from .tools.file_tools import file_tools, FileOperationError
from .tools.rag_tools import rag_tools, RAGToolError
from .ui.rich_ui import rich_ui


class DuckflowAgentV2:
    """Duckflow エージェント - 5ノードアーキテクチャ実装（LangGraphベース）
    
    評価ノード中心の品質保証ループと決定論的応答生成を実現
    Duck Pacemaker統合による AI安全システム搭載
    """
    
    def __init__(self):
        """初期化"""
        self.config = config_manager.load_config()
        
        # ワークスペース情報の初期化（現在の絶対パスを使用）
        workspace = WorkspaceInfo(
            path=os.path.abspath("."),
            files=[],
            last_modified=datetime.now()
        )
        
        self.state = AgentState(
            session_id=str(uuid.uuid4()),
            workspace=workspace,
            debug_mode=config_manager.is_debug_mode()
        )
        
        self.orchestrator = FiveNodeOrchestrator(self.state)
        self.running = True
    
    def start(self) -> None:
        """エージェントを開始"""
        try:
            # ヘッダー表示
            rich_ui.print_header(
                "Duckflow v0.3.2-alpha (5-Node Architecture)",
                "AI-powered coding agent with 5-node LangGraph orchestration"
            )
            
            if self.state.debug_mode:
                rich_ui.print_warning("デバッグモードで実行中")
            
            rich_ui.print_message("[5-NODE] LangGraphベースの5ノードアーキテクチャ", "info")
            
            # メインループ
            self._main_loop()
            
        except KeyboardInterrupt:
            rich_ui.print_message("\n操作がキャンセルされました。", "warning")
        except Exception as e:
            rich_ui.print_error(f"予期しないエラーが発生しました: {e}")
            if self.state.debug_mode:
                import traceback
                rich_ui.print_error(traceback.format_exc())
        finally:
            self._show_session_summary()
            rich_ui.print_message("Duckflowを終了します。", "info")
    
    def _main_loop(self) -> None:
        """メインループ"""
        rich_ui.print_message("コマンドを入力してください。'help' でヘルプ、'quit' で終了。", "info")
        rich_ui.print_separator()
        
        while self.running:
            try:
                # ユーザー入力
                user_input = rich_ui.get_user_input("Duckflow").strip()
                
                if not user_input:
                    continue
                
                # コマンド処理
                self._process_command(user_input)
                
            except KeyboardInterrupt:
                if rich_ui.get_confirmation("終了しますか？"):
                    self.running = False
                else:
                    rich_ui.print_message("操作を続行します。", "info")
            except Exception as e:
                rich_ui.print_error(f"コマンド処理中にエラーが発生しました: {e}")
                if self.state.debug_mode:
                    import traceback
                    rich_ui.print_error(traceback.format_exc())
    
    def _process_command(self, command: str) -> None:
        """コマンドを処理"""
        parts = command.split()
        cmd = parts[0].lower()
        
        # 基本コマンド
        if cmd in ['quit', 'exit', 'q']:
            self.running = False
            return
        
        elif cmd in ['help', 'h']:
            self._show_help()
            return
        
        elif cmd == 'status':
            self._show_status()
            return
        
        elif cmd == 'config':
            self._show_config()
            return
        
        # ファイル操作コマンド（直接実行）
        elif cmd == 'ls' or cmd == 'list':
            path = parts[1] if len(parts) > 1 else "."
            self._list_files(path)
            return
        
        elif cmd == 'read':
            if len(parts) < 2:
                rich_ui.print_error("使用法: read <file_path>")
                return
            self._read_file(parts[1])
            return
        
        elif cmd == 'info':
            if len(parts) < 2:
                rich_ui.print_error("使用法: info <file_path>")
                return
            self._show_file_info(parts[1])
            return
        
        # 対話履歴コマンド
        elif cmd == 'history':
            count = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 10
            self._show_history(count)
            return
        
        # テスト実行コマンド
        elif cmd == 'test' or cmd == 'tests':
            verbose = '--verbose' in parts or '-v' in parts
            test_path = None
            for part in parts[1:]:
                if not part.startswith('-'):
                    test_path = part
                    break
            self._run_tests(test_path, verbose)
            return
        
        # グラフ実行状態表示
        elif cmd == 'graph':
            self._show_graph_status()
            return
        
        # RAG機能コマンド
        elif cmd == 'index':
            force_rebuild = '--force' in parts or '-f' in parts
            self._index_project(force_rebuild)
            return
        
        elif cmd == 'search':
            if len(parts) < 2:
                rich_ui.print_error("使用法: search <query> [--type=language] [--max=N]")
                return
            query = " ".join(parts[1:])
            
            # オプション解析
            max_results = 5
            file_type = None
            for part in parts[1:]:
                if part.startswith('--max='):
                    max_results = int(part.split('=')[1])
                    query = query.replace(part, '').strip()
                elif part.startswith('--type='):
                    file_type = part.split('=')[1]
                    query = query.replace(part, '').strip()
            
            self._search_code(query, max_results, file_type)
            return
        
        elif cmd == 'index-status':
            self._show_index_status()
            return
        
        # 作業ディレクトリ変更
        elif cmd == 'cd':
            if len(parts) < 2:
                rich_ui.print_message(f"現在のディレクトリ: {os.getcwd()}", "info")
                return
            new_path = parts[1]
            self._change_directory(new_path)
            return
        
        # 現在のディレクトリ表示
        elif cmd == 'pwd':
            rich_ui.print_message(f"現在のディレクトリ: {os.getcwd()}", "info")
            return
        
        # 記憶管理コマンド (ステップ2c)
        elif cmd == 'memory':
            self._show_memory_status()
            return
            
        elif cmd == 'summarize':
            self._create_memory_summary()
            return
        
        else:
            # 不明なコマンドはLangGraphオーケストレーションで処理
            self._handle_orchestrated_conversation(command)
    
    def _show_help(self) -> None:
        """ヘルプを表示"""
        help_text = """
[bold cyan]利用可能なコマンド:[/]

[yellow]基本操作:[/]
  help, h          - このヘルプを表示
  quit, exit, q    - Duckflowを終了
  status           - エージェントの状態を表示
  config           - 設定情報を表示
  history [count]  - 対話履歴を表示 (デフォルト: 10件)
  graph            - グラフ実行状態を表示

[yellow]RAG機能 (ステップ2b):[/]
  index [--force]  - プロジェクトをインデックス化 (--force: 強制再構築)
  search <query>   - コードを検索 (--type=言語 --max=件数)
  index-status     - インデックス状態を表示

[yellow]ファイル操作:[/]
  ls, list [path]  - ファイル一覧を表示 (デフォルト: 現在のディレクトリ)
  read <file>      - ファイルを読み取り表示
  info <file>      - ファイル情報を表示
  cd <path>        - 作業ディレクトリを変更
  pwd              - 現在のディレクトリを表示
  test, tests      - テストを実行 (オプション: -v, --verbose, [path])

[yellow]記憶管理 (ステップ2c):[/]
  memory           - 記憶状態を表示（対話履歴、要約状況）
  summarize        - 手動で対話履歴の要約を作成

[yellow]AI対話 (LangGraph):[/]
  上記以外の入力  - LangGraphオーケストレーションでAI対話を実行

[bold green]5ノードアーキテクチャ新機能:[/]
  ✨ 評価ノード中心の品質保証ループ
  ✨ 決定論的応答生成（TaskProfileテンプレート）
  ✨ Duck Pacemaker統合（AI安全システム）
  ✨ 高度な探索・分析エンジン

[dim]例: "example.pyファイルを作成して、Hello Worldを出力する関数を書いて"[/]
        """
        
        rich_ui.print_panel(help_text.strip(), "Help - 5-Node Architecture", "info")
    
    def _show_status(self) -> None:
        """エージェントの状態を表示"""
        status_info = f"""
[bold]セッション情報:[/]
  セッションID: {self.state.session_id}
  開始時刻: {self.state.created_at.strftime('%Y-%m-%d %H:%M:%S')}
  最終活動: {self.state.last_activity.strftime('%Y-%m-%d %H:%M:%S')}

[bold]対話情報:[/]
  メッセージ数: {len(self.state.conversation_history)}
  現在のタスク: {self.state.current_task or 'なし'}

[bold]5ノードLangGraph状態:[/]
  アーキテクチャ: 5ノード統合 (理解・計画 → 情報収集 → 安全実行 → 評価・継続 → 応答生成)
  現在のノード: {self.state.graph_state.current_node or 'なし'}
  実行パス: {' → '.join(self.state.graph_state.execution_path[-5:]) if self.state.graph_state.execution_path else 'なし'}
  ループ回数: {self.state.graph_state.loop_count}/{self.state.graph_state.max_loops}

[bold]ツール実行:[/]
  実行回数: {len(self.state.tool_executions)}
  エラー数: {self.state.error_count}
  リトライ回数: {self.state.retry_count}/{self.state.max_retries}

[bold]設定情報:[/]
  デバッグモード: {'有効' if self.state.debug_mode else '無効'}
  LLMプロバイダー: {self.config.llm.provider}
        """
        
        rich_ui.print_panel(status_info.strip(), "Status - 5-Node Architecture", "info")
    
    def _show_config(self) -> None:
        """設定情報を表示"""
        config_info = f"""
[bold]LLM設定:[/]
  プロバイダー: {self.config.llm.provider}

[bold]UI設定:[/]
  タイプ: {self.config.ui.type}

[bold]ファイル操作設定:[/]
  最大ファイルサイズ: {self.config.tools.file_operations.get('max_file_size_mb', 10)}MB
  バックアップ: {'有効' if self.config.tools.file_operations.get('backup_enabled', True) else '無効'}

[bold]セキュリティ設定:[/]
  ファイル書き込み承認: {'必要' if self.config.security.require_approval.get('file_write', True) else '不要'}

[bold]5ノードLangGraph設定:[/]
  アーキテクチャ: 評価ノード中心品質保証ループ
  最大ループ回数: {self.state.graph_state.max_loops}
  最大リトライ回数: {self.state.max_retries}
  Duck Pacemaker: 有効 (AI安全システム)
        """
        
        rich_ui.print_panel(config_info.strip(), "Configuration - 5-Node Architecture", "info")
    
    def _show_graph_status(self) -> None:
        """グラフ実行状態を表示"""
        graph_info = f"""
[bold]現在の実行状態:[/]
  現在のノード: {self.state.graph_state.current_node or 'なし'}
  次のノード候補: {', '.join(self.state.graph_state.next_nodes) if self.state.graph_state.next_nodes else 'なし'}

[bold]実行履歴 (最新10件):[/]
{chr(10).join([f"  {i+1}. {node}" for i, node in enumerate(self.state.graph_state.execution_path[-10:])]) if self.state.graph_state.execution_path else '  なし'}

[bold]パフォーマンス:[/]
  ループ回数: {self.state.graph_state.loop_count}/{self.state.graph_state.max_loops}
  エラー率: {(self.state.error_count / len(self.state.tool_executions) * 100):.1f}% ({self.state.error_count}/{len(self.state.tool_executions)})

[bold]最近のツール実行 (最新5件):[/]
{chr(10).join([f"  - {te.tool_name}: {'✅' if not te.error else '❌'} ({te.execution_time:.2f}s)" for te in self.state.tool_executions[-5:]]) if self.state.tool_executions else '  なし'}
        """
        
        rich_ui.print_panel(graph_info.strip(), "Graph Execution Status", "info")
    
    def _list_files(self, path: str) -> None:
        """ファイル一覧を表示"""
        try:
            files = file_tools.list_files(path)
            rich_ui.print_file_list(files, f"Files in {path}")
            
            # ワークスペース情報を更新
            if self.state.workspace:
                self.state.workspace.files = [f['name'] for f in files if f['type'] == 'file']
                self.state.workspace.last_modified = datetime.now()
        except FileOperationError as e:
            rich_ui.print_error(str(e))
    
    def _read_file(self, file_path: str) -> None:
        """ファイルを読み取り表示"""
        try:
            content = file_tools.read_file(file_path)
            
            # ファイル拡張子から言語を推測
            language = self._guess_language(file_path)
            
            rich_ui.print_file_content(file_path, content, language)
            rich_ui.print_success(f"ファイルを読み込みました: {file_path}")
            
            # ワークスペース情報を更新
            if self.state.workspace:
                self.state.workspace.current_file = file_path
                self.state.workspace.last_modified = datetime.now()
                
        except FileOperationError as e:
            rich_ui.print_error(str(e))
    
    def _show_file_info(self, file_path: str) -> None:
        """ファイル情報を表示"""
        try:
            info = file_tools.get_file_info(file_path)
            
            info_text = f"""
[bold]ファイル情報:[/]
  名前: {info['name']}
  パス: {info['path']}
  サイズ: {info['size']} bytes
  種類: {'ファイル' if info['is_file'] else 'ディレクトリ' if info['is_directory'] else '不明'}
  拡張子: {info['extension'] or 'なし'}
  更新日時: {info['modified']}
  作成日時: {info['created']}
  親ディレクトリ: {info['parent']}
            """
            
            rich_ui.print_panel(info_text.strip(), f"File Info: {info['name']}", "info")
            
        except FileOperationError as e:
            rich_ui.print_error(str(e))
    
    def _run_tests(self, test_path: Optional[str] = None, verbose: bool = False) -> None:
        """テストを実行"""
        try:
            rich_ui.print_message("テストを実行中...", "info")
            
            result = file_tools.run_tests(test_path, verbose)
            
            # テスト結果の表示
            if result["success"]:
                rich_ui.print_success(
                    f"テストが完了しました: {result['passed']}/{result['total_tests']} 成功 "
                    f"({result['duration']:.2f}秒)"
                )
            else:
                rich_ui.print_error(
                    f"テストに失敗しました: {result['passed']}/{result['total_tests']} 成功 "
                    f"({result['failed']} 失敗, {result['errors']} エラー, {result['duration']:.2f}秒)"
                )
            
            # 詳細情報の表示
            if result["total_tests"] > 0:
                summary = f"""
[bold]テスト結果サマリー:[/]
  実行数: {result['total_tests']}
  成功: [green]{result['passed']}[/]
  失敗: [red]{result['failed']}[/]
  エラー: [red]{result['errors']}[/]
  スキップ: [yellow]{result['skipped']}[/]
  実行時間: {result['duration']:.2f}秒
                """
                
                rich_ui.print_panel(summary.strip(), "Test Results", 
                                  "success" if result["success"] else "error")
            
            # 失敗したテストの詳細表示
            if result["failed_tests"]:
                rich_ui.print_message("\n失敗したテストの詳細:", "warning")
                for failed_test in result["failed_tests"]:
                    rich_ui.print_message(f"\n❌ {failed_test['name']}", "error")
                    if failed_test['error']:
                        # エラーメッセージの整形
                        error_lines = failed_test['error'].split('\n')
                        for line in error_lines[:10]:  # 最初の10行のみ表示
                            if line.strip():
                                rich_ui.print_message(f"   {line}", "muted")
                        if len(error_lines) > 10:
                            rich_ui.print_message("   ... (truncated)", "muted")
            
        except FileOperationError as e:
            rich_ui.print_error(f"テスト実行エラー: {e}")
    
    def _show_history(self, count: int) -> None:
        """対話履歴を表示"""
        messages = self.state.get_recent_messages(count)
        
        if not messages:
            rich_ui.print_message("対話履歴がありません。", "muted")
            return
        
        rich_ui.print_message(f"最新の{len(messages)}件の対話履歴:", "info")
        rich_ui.print_separator()
        
        for msg in messages:
            timestamp = msg.timestamp.strftime('%H:%M:%S')
            rich_ui.print_conversation_message(msg.role, msg.content, timestamp)
    
    def _show_session_summary(self) -> None:
        """セッション終了時のサマリーを表示"""
        summary = f"""
[bold cyan]セッションサマリー:[/]
  実行時間: {(datetime.now() - self.state.created_at).total_seconds():.1f}秒
  対話回数: {len(self.state.conversation_history)}
  ツール実行: {len(self.state.tool_executions)}回
  エラー: {self.state.error_count}回
  グラフループ: {self.state.graph_state.loop_count}回
        """
        
        rich_ui.print_panel(summary.strip(), "Session Summary", "success")
    
    def _guess_language(self, file_path: str) -> str:
        """ファイル拡張子から言語を推測"""
        extension_mapping = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'jsx',
            '.tsx': 'tsx',
            '.html': 'html',
            '.css': 'css',
            '.json': 'json',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.md': 'markdown',
            '.txt': 'text',
            '.sh': 'bash',
            '.bat': 'batch',
            '.sql': 'sql',
            '.xml': 'xml',
        }
        
        from pathlib import Path
        suffix = Path(file_path).suffix.lower()
        return extension_mapping.get(suffix, 'text')
    
    def _handle_orchestrated_conversation(self, user_message: str) -> None:
        """LangGraphオーケストレーションでAI対話を処理"""
        try:
            rich_ui.print_message("[ORCHESTRATION] LangGraphで処理中...", "info")
            
            # ユーザーメッセージを会話履歴に追加
            self.state.add_message("user", user_message)
            
            # グラフ状態をリセット（新しい対話のため）
            self.state.graph_state.loop_count = 0
            self.state.retry_count = 0
            self.state.last_error = None
            
            # オーケストレーションを実行
            self.orchestrator.run_conversation(user_message)
            
            # 状態を同期
            self.state = self.orchestrator.state
            
            # デバッグ: 対話履歴の確認
            assistant_messages = [msg for msg in self.state.conversation_history if msg.role == 'assistant']
            rich_ui.print_message(f"対話履歴: {len(self.state.conversation_history)}件、アシスタント応答: {len(assistant_messages)}件", "info")
            
            # 最新のアシスタント応答を表示
            self._display_latest_assistant_response()
            
            rich_ui.print_message("[ORCHESTRATION] 処理完了", "success")
            
        except Exception as e:
            error_msg = str(e)
            self.state.record_error(f"オーケストレーションエラー: {error_msg}")
            
            # 再帰制限エラーの場合は分かりやすいメッセージを表示
            if "recursion_limit" in error_msg.lower() or "recursion limit" in error_msg.lower():
                rich_ui.print_error("[ERROR] 処理が複雑になりすぎました。より簡単な質問に分けてお試しください。")
                rich_ui.print_message("ヒント: 'status' コマンドで現在の状態を確認できます", "info")
            else:
                rich_ui.print_error(f"[ERROR] 処理中にエラーが発生しました: {error_msg}")
            
            if self.state.debug_mode:
                import traceback
                rich_ui.print_error(traceback.format_exc())
    
    def _display_latest_assistant_response(self) -> None:
        """最新のアシスタント応答をUIに表示"""
        try:
            # 対話履歴から最新のアシスタントメッセージを取得
            if self.state.conversation_history:
                for message in reversed(self.state.conversation_history):
                    if message.role == 'assistant':
                        # アシスタントの応答を表示
                        rich_ui.print_conversation_message(
                            role=message.role,
                            content=message.content,
                            timestamp=message.timestamp.strftime('%H:%M:%S') if hasattr(message, 'timestamp') else None
                        )
                        return
            
            # アシスタントの応答が見つからない場合
            rich_ui.print_warning("アシスタントの応答が見つかりませんでした")
            
        except Exception as e:
            rich_ui.print_error(f"応答表示エラー: {e}")
            if self.state.debug_mode:
                import traceback
                rich_ui.print_error(traceback.format_exc())
    
    def _index_project(self, force_rebuild: bool = False) -> None:
        """プロジェクトをインデックス化"""
        try:
            rich_ui.print_message("🔍 プロジェクトのインデックス化を開始...", "info")
            
            result = rag_tools.index_project(force_rebuild=force_rebuild)
            
            if result.get("success"):
                stats = result.get("stats", {})
                rich_ui.print_success(f"✅ インデックス化完了 ({result.get('elapsed_time', 0):.2f}秒)")
                rich_ui.print_message(f"📊 {stats.get('unique_files', 0)} ファイル、{stats.get('total_chunks', 0)} チャンクを処理", "info")
            else:
                rich_ui.print_error(f"❌ インデックス化に失敗: {result.get('message', '不明なエラー')}")
        
        except RAGToolError as e:
            rich_ui.print_error(f"RAGツールエラー: {e}")
        except Exception as e:
            rich_ui.print_error(f"インデックス化エラー: {e}")
            if self.state.debug_mode:
                import traceback
                rich_ui.print_error(traceback.format_exc())
    
    def _search_code(self, query: str, max_results: int = 5, file_type: Optional[str] = None) -> None:
        """コードを検索"""
        try:
            rich_ui.print_message(f"🔍 検索中: '{query}'", "info")
            
            result = rag_tools.search_code(
                query=query,
                max_results=max_results,
                file_type=file_type
            )
            
            if result.get("success"):
                results = result.get("results", [])
                if results:
                    rich_ui.print_success(f"✅ {len(results)} 件の検索結果を発見")
                    
                    for i, search_result in enumerate(results, 1):
                        file_path = search_result.get("file_path", "unknown")
                        language = search_result.get("language", "unknown")
                        score = search_result.get("relevance_score", 0)
                        content = search_result.get("content", "")
                        
                        rich_ui.print_message(f"\n📄 {i}. {file_path} ({language}) [関連度: {score:.3f}]", "info")
                        
                        # コンテンツのプレビュー表示
                        preview = content[:300]
                        if len(content) > 300:
                            preview += "..."
                        rich_ui.print_message(f"   {preview}", "muted")
                else:
                    rich_ui.print_message("🔍 該当するコードが見つかりませんでした", "warning")
            else:
                rich_ui.print_error(f"❌ 検索に失敗: {result.get('message', '不明なエラー')}")
        
        except RAGToolError as e:
            rich_ui.print_error(f"RAGツールエラー: {e}")
        except Exception as e:
            rich_ui.print_error(f"コード検索エラー: {e}")
            if self.state.debug_mode:
                import traceback
                rich_ui.print_error(traceback.format_exc())
    
    def _show_index_status(self) -> None:
        """インデックス状態を表示"""
        try:
            status = rag_tools.get_index_status()
            
            if status.get("status") == "ready":
                index_info = f"""
[bold]RAGインデックス状態:[/]
  ステータス: [green]利用可能[/]
  ファイル数: {status.get('unique_files', 0)}
  チャンク数: {status.get('total_chunks', 0)}
  保存場所: {status.get('index_path', 'unknown')}

[bold]言語別分布:[/]"""
                
                languages = status.get('languages', {})
                for lang, count in sorted(languages.items()):
                    index_info += f"\n  {lang}: {count} チャンク"
                
                rich_ui.print_panel(index_info.strip(), "RAG Index Status", "info")
            
            elif status.get("status") == "not_initialized":
                rich_ui.print_panel(
                    "[bold red]RAGインデックスが初期化されていません[/]\n\n"
                    "使用方法:\n"
                    "  index          - プロジェクトをインデックス化\n"
                    "  index --force  - 強制再構築",
                    "RAG Index Status",
                    "warning"
                )
            
            else:
                rich_ui.print_panel(
                    f"[bold yellow]RAGインデックスエラー[/]\n\n"
                    f"エラー: {status.get('message', '不明なエラー')}",
                    "RAG Index Status",
                    "error"
                )
        
        except Exception as e:
            rich_ui.print_error(f"インデックス状態取得エラー: {e}")
            if self.state.debug_mode:
                import traceback
                rich_ui.print_error(traceback.format_exc())
    
    def _change_directory(self, new_path: str) -> None:
        """作業ディレクトリを変更"""
        try:
            # パスの正規化
            if new_path == "~":
                new_path = os.path.expanduser("~")
            elif new_path == "-":
                # 前のディレクトリに戻る機能（簡単な実装）
                if hasattr(self, '_previous_dir'):
                    new_path = self._previous_dir
                else:
                    rich_ui.print_warning("前のディレクトリが記録されていません")
                    return
            
            # 現在のディレクトリを記録
            self._previous_dir = os.getcwd()
            
            # 相対パスを絶対パスに変換
            new_path = os.path.abspath(os.path.expanduser(new_path))
            
            # ディレクトリの存在確認
            if not os.path.exists(new_path):
                rich_ui.print_error(f"ディレクトリが存在しません: {new_path}")
                return
            
            if not os.path.isdir(new_path):
                rich_ui.print_error(f"パスがディレクトリではありません: {new_path}")
                return
            
            # ディレクトリ変更実行
            os.chdir(new_path)
            rich_ui.print_success(f"作業ディレクトリを変更しました: {os.getcwd()}")
            
            # ワークスペース情報を更新
            if self.state.workspace:
                self.state.workspace.path = os.getcwd()
                self.state.workspace.last_modified = datetime.now()
            
        except PermissionError:
            rich_ui.print_error(f"ディレクトリへのアクセス権限がありません: {new_path}")
        except Exception as e:
            rich_ui.print_error(f"ディレクトリ変更に失敗しました: {e}")
    
    def _show_memory_status(self) -> None:
        """記憶管理の状態を表示"""
        try:
            memory_status = self.state.get_memory_status()
            
            rich_ui.print_panel(
                f"""**記憶管理状態 (ステップ2c)**

**対話統計:**
- 総メッセージ数: {memory_status.get('total_messages', 0)}
- 要約が必要: {'はい' if memory_status.get('needs_summary', False) else 'いいえ'}

**短期記憶 (最近の対話):**
- 現在の履歴長: {len(self.state.conversation_history)}メッセージ

**中期記憶 (要約):**
- 要約: {'あり' if self.state.history_summary else 'なし'}
- 要約作成日時: {self.state.summary_created_at.strftime('%Y-%m-%d %H:%M:%S') if self.state.summary_created_at else 'なし'}
- 元の対話数: {self.state.original_conversation_length}

**設定:**
- 要約トリガー: {memory_status.get('trigger_threshold', 'N/A')} トークン
- 保持ターン数: {memory_status.get('keep_recent_turns', 'N/A')}""",
                "記憶管理状態",
                "cyan"
            )
            
            if self.state.history_summary:
                rich_ui.print_panel(
                    self.state.history_summary[:500] + ("..." if len(self.state.history_summary) > 500 else ""),
                    "現在の要約 (抜粋)",
                    "blue"
                )
                
        except Exception as e:
            rich_ui.print_error(f"記憶状態取得エラー: {e}")
            if self.state.debug_mode:
                import traceback
                rich_ui.print_error(traceback.format_exc())
    
    def _create_memory_summary(self) -> None:
        """手動で記憶要約を作成"""
        try:
            if len(self.state.conversation_history) < 4:
                rich_ui.print_warning("要約するには対話が不十分です（最低4メッセージ必要）")
                return
            
            rich_ui.print_message("対話履歴の要約を作成中...", "info")
            
            if self.state.create_memory_summary():
                rich_ui.print_success("要約を作成し、対話履歴を整理しました")
                
                # 要約結果を表示
                if self.state.history_summary:
                    rich_ui.print_panel(
                        self.state.history_summary[:300] + ("..." if len(self.state.history_summary) > 300 else ""),
                        "作成された要約 (抜粋)",
                        "green"
                    )
            else:
                rich_ui.print_error("要約の作成に失敗しました")
                
        except Exception as e:
            rich_ui.print_error(f"記憶要約作成エラー: {e}")
            if self.state.debug_mode:
                import traceback
                rich_ui.print_error(traceback.format_exc())


def main() -> None:
    """メイン関数"""
    try:
        agent = DuckflowAgentV2()
        agent.start()
    except Exception as e:
        print(f"起動時にエラーが発生しました: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()