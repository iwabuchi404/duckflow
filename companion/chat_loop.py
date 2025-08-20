"""
Chat Loop - 対話ループ (Refactored)
ユーザーとの継続的な対話を管理し、コマンドを解釈し、タスクをディスパッチする。
"""

import queue
import asyncio
import logging
from typing import Optional, Dict, Any

from .ui import rich_ui
from .workspace_manager import WorkspaceManager

class ChatLoop:
    """対話ループ - ユーザー入力を処理し、コマンド実行またはタスク発行を行う"""
    
    def __init__(self, task_queue: queue.Queue, status_queue: queue.Queue, companion, dual_loop_system):
        self.task_queue = task_queue
        self.status_queue = status_queue
        self.companion = companion
        self.dual_loop_system = dual_loop_system
        self.workspace_manager = WorkspaceManager()
        self.running = False
        self.logger = logging.getLogger(__name__)

    def run(self):
        self.running = True
        self.logger.info("ChatLoop を開始しました")
        rich_ui.print_message("🦆 Duckflow v4.0 Final", "success")
        rich_ui.print_message("タスク実行中も対話を継続できます！ `help`でコマンド一覧を表示。", "info")
        asyncio.run(self._async_main_loop())

    async def _async_main_loop(self):
        """非同期メインループ"""
        try:
            while self.running:
                await self._check_status_queue()
                user_input = await self._get_user_input()
                if user_input is not None and user_input.strip():
                    if not await self._handle_command(user_input):
                        await self._dispatch_ai_task(user_input)
                elif user_input is None:
                    # ユーザー入力がNone（終了要求）の場合はループを終了
                    self.running = False
                await asyncio.sleep(0.1)
        except (KeyboardInterrupt, EOFError):
            self.logger.info("ユーザーによる終了要求")
            self.running = False
        finally:
            self.stop()

    async def _get_user_input(self) -> Optional[str]:
        """ユーザー入力を非同期で受け取る"""
        try:
            prompt = f"🦆 {self.workspace_manager.get_current_directory_name()}> "
            user_input = await asyncio.get_event_loop().run_in_executor(None, input, prompt)
            return user_input.strip() if user_input else None
        except (KeyboardInterrupt, EOFError) as e:
            self.logger.info(f"ユーザー入力終了: {type(e).__name__}")
            self.running = False
            return None
        except Exception as e:
            self.logger.error(f"ユーザー入力エラー: {e}")
            self.running = False
            return None

    async def _handle_command(self, user_input: str) -> bool:
        """内部コマンドを処理する。コマンドが処理された場合はTrueを返す。"""
        command = user_input.strip().lower()
        parts = command.split()
        if not parts:
            return False

        cmd = parts[0]

        if cmd in ['quit', 'exit', 'q']:
            self.running = False
            return True
        elif cmd == 'help':
            rich_ui.print_message("利用可能なコマンド: cd, ls, pwd, status, help, quit", "info")
            return True
        elif cmd == 'status':
            rich_ui.print_message(f"現在の状態: {self.dual_loop_system.state_machine.get_current_state()}", "info")
            return True
        elif cmd == 'pwd':
            rich_ui.print_message(self.workspace_manager.pwd(), "info")
            return True
        elif cmd == 'ls':
            path = parts[1] if len(parts) > 1 else "."
            rich_ui.print_message(self.workspace_manager.ls(path), "info")
            return True
        elif cmd == 'cd':
            if len(parts) < 2:
                rich_ui.print_message("cdコマンドには移動先のディレクトリが必要です。", "error")
            else:
                try:
                    result = self.workspace_manager.cd(parts[1])
                    rich_ui.print_message(f"移動しました: {result}", "success")
                except Exception as e:
                    rich_ui.print_message(f"ディレクトリ移動エラー: {e}", "error")
            return True
        
        return False # AIに処理を渡す

    async def _dispatch_ai_task(self, user_input: str):
        """AI処理タスクをキューに投入する"""
        try:
            self.logger.info(f"AIタスクをディスパッチ: {user_input}")
            # 正しい2ステップの呼び出し
            intent_result = await self.companion.analyze_intent_only(user_input)
            task_data = {
                "type": "process_intent",
                "intent_result": intent_result
            }
            self.task_queue.put(task_data)
            rich_ui.print_message("🤔 思考中...", "info")
        except Exception as e:
            self.logger.error(f"AIタスクのディスパッチ中にエラー: {e}", exc_info=True)
            rich_ui.print_message(f"❌ 意図理解の開始に失敗しました: {e}", "error")

    async def _check_status_queue(self):
        """TaskLoopからの状態更新を処理"""
        try:
            status_update = self.status_queue.get_nowait()
            rich_ui.print_message(f"進捗: {status_update.get('message', '')}", "info")
            self.task_queue.task_done()
        except queue.Empty:
            pass

    def stop(self):
        self.running = False
        self.logger.info("ChatLoop を停止しました")
