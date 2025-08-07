"""
Duckflow メインエントリーポイント
ステップ1: 最小限実装版
"""
import sys
import uuid
from datetime import datetime
from typing import Optional

from .base.config import config_manager
from .base.llm_client import llm_manager, LLMClientError
from .state.agent_state import AgentState
from .tools.file_tools import file_tools, FileOperationError
from .ui.rich_ui import rich_ui


class DuckflowAgent:
    """Duckflow エージェント - ステップ1実装"""
    
    def __init__(self):
        """初期化"""
        self.config = config_manager.load_config()
        self.state = AgentState(session_id=str(uuid.uuid4()))
        self.running = True
        
        # デバッグモードの確認
        self.debug_mode = config_manager.is_debug_mode()
    
    def start(self) -> None:
        """エージェントを開始"""
        try:
            # ヘッダー表示
            rich_ui.print_header(
                "Duckflow v0.1.0",
                "AI-powered coding agent for local development environments (Step 1)"
            )
            
            if self.debug_mode:
                rich_ui.print_warning("デバッグモードで実行中")
            
            # メインループ
            self._main_loop()
            
        except KeyboardInterrupt:
            rich_ui.print_message("\n操作がキャンセルされました。", "warning")
        except Exception as e:
            rich_ui.print_error(f"予期しないエラーが発生しました: {e}")
            if self.debug_mode:
                import traceback
                rich_ui.print_error(traceback.format_exc())
        finally:
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
                
                # 対話履歴に追加
                self.state.add_message("user", user_input)
                
                # コマンド処理
                self._process_command(user_input)
                
            except KeyboardInterrupt:
                if rich_ui.get_confirmation("終了しますか？"):
                    self.running = False
                else:
                    rich_ui.print_message("操作を続行します。", "info")
            except Exception as e:
                rich_ui.print_error(f"コマンド処理中にエラーが発生しました: {e}")
                if self.debug_mode:
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
        
        # ファイル操作コマンド
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
        
        elif cmd == 'write':
            if len(parts) < 2:
                rich_ui.print_error("使用法: write <file_path>")
                return
            self._write_file(parts[1])
            return
        
        elif cmd == 'info':
            if len(parts) < 2:
                rich_ui.print_error("使用法: info <file_path>")
                return
            self._show_file_info(parts[1])
            return
        
        elif cmd == 'mkdir':
            if len(parts) < 2:
                rich_ui.print_error("使用法: mkdir <directory_path>")
                return
            self._create_directory(parts[1])
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
        
        else:
            # 不明なコマンドはAIとの対話として処理
            self._handle_ai_conversation(command)
    
    def _show_help(self) -> None:
        """ヘルプを表示"""
        help_text = """
[bold cyan]利用可能なコマンド:[/]

[yellow]基本操作:[/]
  help, h          - このヘルプを表示
  quit, exit, q    - CodeCrafterを終了
  status           - エージェントの状態を表示
  config           - 設定情報を表示
  history [count]  - 対話履歴を表示 (デフォルト: 10件)
  test, tests      - テストを実行 (オプション: -v, --verbose, [path])

[yellow]ファイル操作:[/]
  ls, list [path]  - ファイル一覧を表示 (デフォルト: 現在のディレクトリ)
  read <file>      - ファイルを読み取り表示
  write <file>     - ファイルに書き込み (インタラクティブ)
  info <file>      - ファイル情報を表示
  mkdir <dir>      - ディレクトリを作成

[yellow]AI対話:[/]
  上記以外の入力  - AIとの対話でファイル編集を行います

[dim]例: "example.pyファイルを作成して、Hello Worldを出力する関数を書いて"[/]
        """
        
        rich_ui.print_panel(help_text.strip(), "Help", "info")
    
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

[bold]設定情報:[/]
  デバッグモード: {'有効' if self.debug_mode else '無効'}
  LLMプロバイダー: {self.config.llm.provider}
        """
        
        rich_ui.print_panel(status_info.strip(), "Status", "info")
    
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
        """
        
        rich_ui.print_panel(config_info.strip(), "Configuration", "info")
    
    def _list_files(self, path: str) -> None:
        """ファイル一覧を表示"""
        try:
            files = file_tools.list_files(path)
            rich_ui.print_file_list(files, f"Files in {path}")
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
            
        except FileOperationError as e:
            rich_ui.print_error(str(e))
    
    def _write_file(self, file_path: str) -> None:
        """ファイルに書き込み"""
        try:
            # セキュリティチェック
            if self.config.security.require_approval.get('file_write', True):
                if not rich_ui.get_confirmation(f"ファイル '{file_path}' に書き込みますか？"):
                    rich_ui.print_message("操作がキャンセルされました。", "warning")
                    return
            
            rich_ui.print_message("ファイル内容を入力してください。（Ctrl+D または空行で終了）", "info")
            
            lines = []
            try:
                while True:
                    line = input()
                    if not line:  # 空行で終了
                        break
                    lines.append(line)
            except EOFError:
                pass  # Ctrl+D で終了
            
            content = '\n'.join(lines)
            
            if not content.strip():
                rich_ui.print_warning("内容が空のため、書き込みをキャンセルしました。")
                return
            
            result = file_tools.write_file(file_path, content)
            rich_ui.print_success(f"ファイルに書き込みました: {file_path} ({result['size']} bytes)")
            
            if result['backup_created']:
                rich_ui.print_message(f"バックアップを作成しました: {result['backup_path']}", "info")
            
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
    
    def _create_directory(self, directory_path: str) -> None:
        """ディレクトリを作成"""
        try:
            # セキュリティチェック
            if self.config.security.require_approval.get('directory_creation', True):
                if not rich_ui.get_confirmation(f"ディレクトリ '{directory_path}' を作成しますか？"):
                    rich_ui.print_message("操作がキャンセルされました。", "warning")
                    return
            
            result = file_tools.create_directory(directory_path)
            
            if result['created']:
                rich_ui.print_success(f"ディレクトリを作成しました: {directory_path}")
            else:
                rich_ui.print_message(result['message'], "info")
            
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
            
            # 標準エラー出力がある場合は表示
            if result.get("stderr") and result["stderr"].strip():
                rich_ui.print_message("\nエラー出力:", "warning")
                rich_ui.print_message(result["stderr"], "muted")
            
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
    
    def _handle_ai_conversation(self, user_message: str) -> None:
        """AIとの対話を処理してファイル編集を実行"""
        try:
            rich_ui.print_message(f"AI ({llm_manager.get_provider_name()}) に送信中...", "info")
            
            # システムプロンプトを作成
            system_prompt = self._create_system_prompt()
            
            # AIからの応答を取得
            ai_response = llm_manager.chat(user_message, system_prompt)
            
            # 応答を対話履歴に追加
            self.state.add_message("assistant", ai_response)
            
            # AIの応答を表示
            rich_ui.print_conversation_message("assistant", ai_response)
            
            # AIの応答からファイル操作の指示を解析して実行
            self._execute_ai_instructions(ai_response, user_message)
            
        except LLMClientError as e:
            rich_ui.print_error(f"AI処理エラー: {e}")
        except Exception as e:
            rich_ui.print_error(f"対話処理中にエラーが発生しました: {e}")
            if self.debug_mode:
                import traceback
                rich_ui.print_error(traceback.format_exc())
    
    def _create_system_prompt(self) -> str:
        """システムプロンプトを作成"""
        return """あなたはDuckflowのファイル編集アシスタントです。

役割:
- ユーザーの指示に従ってファイルの作成・編集を支援する
- 具体的で実用的なコードを提供する
- ファイル操作の必要性を判断し、適切な指示を提供する

制約:
- 単一ファイルの編集に集中する
- セキュリティリスクのあるコードは避ける
- 実用的で動作するコードを提供する

応答フォーマット:
1. ユーザーの要求を理解したことを確認
2. 実行する内容を説明
3. 必要に応じてファイル作成・編集の具体的な内容を提示

ファイル操作が必要な場合は、以下の形式で指示してください:
FILE_OPERATION:CREATE:filename.py
```python
# ここにファイル内容
```
FILE_OPERATION:EDIT:filename.py
```python
# ここに編集後のファイル内容
```"""
    
    def _execute_ai_instructions(self, ai_response: str, user_message: str) -> None:
        """AIの指示を解析してファイル操作を実行"""
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
                    self._execute_file_operation(current_operation, current_filename, '\n'.join(current_content))
                    current_operation = None
                    current_filename = None
                    current_content = []
                in_code_block = not in_code_block
                continue
            
            # コードブロック内の内容を収集
            if in_code_block and current_operation and current_filename:
                current_content.append(line)
    
    def _execute_file_operation(self, operation: str, filename: str, content: str) -> None:
        """ファイル操作を実行"""
        try:
            if operation == 'CREATE':
                # セキュリティチェック
                if self.config.security.require_approval.get('file_write', True):
                    preview = content[:200] + "..." if len(content) > 200 else content
                    rich_ui.print_panel(f"```\n{preview}\n```", f"ファイル作成プレビュー: {filename}", "warning")
                    
                    if not rich_ui.get_confirmation(f"ファイル '{filename}' を作成しますか？"):
                        rich_ui.print_message("ファイル作成をキャンセルしました。", "warning")
                        return
                
                # ファイル作成
                result = file_tools.write_file(filename, content)
                rich_ui.print_success(f"ファイルを作成しました: {filename} ({result['size']} bytes)")
                
                if result['backup_created']:
                    rich_ui.print_message(f"既存ファイルのバックアップ: {result['backup_path']}", "info")
            
            elif operation == 'EDIT':
                # 既存ファイルの確認
                try:
                    existing_content = file_tools.read_file(filename)
                    rich_ui.print_message(f"既存ファイルを編集します: {filename}", "info")
                except FileOperationError:
                    rich_ui.print_message(f"新規ファイルとして作成します: {filename}", "info")
                
                # セキュリティチェック
                if self.config.security.require_approval.get('file_write', True):
                    preview = content[:200] + "..." if len(content) > 200 else content
                    rich_ui.print_panel(f"```\n{preview}\n```", f"ファイル編集プレビュー: {filename}", "warning")
                    
                    if not rich_ui.get_confirmation(f"ファイル '{filename}' を編集しますか？"):
                        rich_ui.print_message("ファイル編集をキャンセルしました。", "warning")
                        return
                
                # ファイル編集
                result = file_tools.write_file(filename, content)
                rich_ui.print_success(f"ファイルを編集しました: {filename} ({result['size']} bytes)")
                
                if result['backup_created']:
                    rich_ui.print_message(f"バックアップを作成しました: {result['backup_path']}", "info")
            
        except FileOperationError as e:
            rich_ui.print_error(f"ファイル操作に失敗しました: {e}")


def main() -> None:
    """メイン関数"""
    try:
        agent = DuckflowAgent()
        agent.start()
    except Exception as e:
        print(f"起動時にエラーが発生しました: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()