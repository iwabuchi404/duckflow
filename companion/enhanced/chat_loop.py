# companion/enhanced/chat_loop.py (v7)
"""
Duckflow v7アーキテクチャに基づくChatLoop。
ユーザー入力を受け付け、Coreに処理を依頼し、TaskLoopからの非同期報告を待つ。
"""
import queue
import asyncio
import logging
from typing import Optional

from companion.ui import rich_ui
from companion.workspace_manager import WorkspaceManager
from companion.state.agent_state import AgentState
from companion.enhanced_core import EnhancedCompanionCoreV7

class EnhancedChatLoopV7:
    def __init__(self, task_queue: queue.Queue, status_queue: queue.Queue, 
                 companion_core: EnhancedCompanionCoreV7):
        self.task_queue = task_queue
        self.status_queue = status_queue
        self.companion_core = companion_core
        self.agent_state = companion_core.agent_state
        self.workspace_manager = WorkspaceManager()
        self.running = False
        self.logger = logging.getLogger(__name__)
        
        # 初期化時にworkspace情報を同期
        self._update_agent_state_workspace()

    def run(self):
        """対話ループを開始する"""
        self.running = True
        self.logger.info("ChatLoop (v7) を開始しました")
        rich_ui.print_message("v7アーキテクチャで起動しました。何でもお話しください。", "success")
        
        try:
            asyncio.run(self._async_main_loop())
        except (KeyboardInterrupt, EOFError):
            self.logger.info("ユーザーによるシャットダウン要求。")
        finally:
            self.stop()

    async def _async_main_loop(self):
        """ユーザー入力とステータス監視を並行して処理する非同期メインループ"""
        input_task = asyncio.create_task(self._get_user_input_async())
        status_task = asyncio.create_task(self._monitor_status_queue())

        while self.running:
            done, pending = await asyncio.wait(
                [input_task, status_task],
                return_when=asyncio.FIRST_COMPLETED
            )

            if input_task in done:
                user_input = input_task.result()
                if user_input is None: # EOF (Ctrl+D) or quit command
                    self.running = False
                    break
                
                if user_input.strip():
                    # 内部コマンドを処理し、処理された場合はAIには渡さない
                    if self._handle_internal_commands(user_input):
                        pass # コマンド処理完了
                    else:
                        # 内部コマンドでなければ、Coreに処理を依頼
                        asyncio.create_task(self._process_input_and_respond(user_input))

                # 次のユーザー入力を待機するタスクを再作成
                input_task = asyncio.create_task(self._get_user_input_async())

            if status_task in done:
                # ステータス監視タスクは常に再起動
                status_task = asyncio.create_task(self._monitor_status_queue())
        
        # ループ終了時に残っているタスクをキャンセル
        input_task.cancel()
        status_task.cancel()

    async def _process_input_and_respond(self, user_input: str):
        """ユーザー入力をCoreに渡して、最終的な応答を表示する"""
        rich_ui.print_message("🤔 思考中...", "info")
        final_response = await self.companion_core.process_user_input(user_input)
        rich_ui.print_message(final_response, "assistant")

    async def _get_user_input_async(self) -> Optional[str]:
        """ユーザーからの入力を非同期で待機する"""
        while self.running:
            try:
                active_plan = self.agent_state.active_plan_id or "NO_PLAN"
                prompt = f"🦆 [{active_plan}]> "
                user_input = await asyncio.get_event_loop().run_in_executor(None, input, prompt)
                
                if user_input.lower().strip() in ['quit', 'exit', 'q']:
                    return None

                return user_input.strip()
            except (KeyboardInterrupt, EOFError):
                return None
        return None

    def _handle_internal_commands(self, user_input: str) -> bool:
        """内部コマンドを処理する。コマンドが処理された場合はTrueを返す。"""
        command = user_input.strip()
        parts = command.split()
        if not parts:
            return False
        
        cmd = parts[0].lower()

        if cmd == 'pwd':
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
                    target_dir = " ".join(parts[1:])
                    result = self.workspace_manager.cd(target_dir)
                    rich_ui.print_message(f"移動しました: {result}", "success")
                    
                    # AgentState.workspaceを更新
                    self._update_agent_state_workspace()
                    
                except Exception as e:
                    rich_ui.print_message(f"ディレクトリ移動エラー: {e}", "error")
            return True

        return False

    async def _process_input_and_respond(self, user_input: str):
        """ユーザー入力をCoreに渡して、最終的な応答を表示する"""
        rich_ui.print_message("🤔 思考中...", "info")
        final_response = await self.companion_core.process_user_input(user_input)
        rich_ui.print_message(final_response, "assistant")

    async def _get_user_input_async(self) -> Optional[str]:
        """ユーザーからの入力を非同期で待機する"""
        while self.running:
            try:
                active_plan = self.agent_state.active_plan_id or "NO_PLAN"
                prompt = f"🦆 [{active_plan}]> "
                user_input = await asyncio.get_event_loop().run_in_executor(None, input, prompt)
                
                if user_input.lower().strip() in ['quit', 'exit', 'q']:
                    return None

                return user_input.strip()
            except (KeyboardInterrupt, EOFError):
                return None
        return None

    async def _monitor_status_queue(self):
        """TaskLoopからの非同期報告を監視し、表示する"""
        while self.running:
            try:
                status_update = self.status_queue.get_nowait()
                self.logger.info(f"TaskLoopからの報告を受信: {status_update}")
                
                if status_update.get("type") == "task_list_completed":
                    summary = status_update.get("summary", {})
                    status = summary.get("status", "不明")
                    message = summary.get("message", "詳細不明のタスクが完了しました。")
                    details = summary.get("details", "")
                    
                    panel_color = "green" if status == "成功" else "red"
                    rich_ui.print_panel(f"{message}\n--- 詳細 ---\n{details}", f"非同期タスク完了: {status}", panel_color)
                
                elif status_update.get("type") == "loop_error":
                    error_msg = status_update.get("error", "不明なエラー")
                    rich_ui.print_error(f"TaskLoopでエラーが発生しました: {error_msg}")

                self.status_queue.task_done()
            except queue.Empty:
                # キューが空の場合はスリープしてCPU負荷を下げる
                await asyncio.sleep(0.2)
            except Exception as e:
                self.logger.error(f"ステータス監視中にエラー: {e}", exc_info=True)
                await asyncio.sleep(1)

    def _update_agent_state_workspace(self):
        """workspace_managerの現在状態をAgentState.workspaceに反映"""
        try:
            from companion.state.agent_state import WorkspaceInfo as AgentWorkspaceInfo
            from datetime import datetime
            import os
            
            current_dir = self.workspace_manager.pwd()
            
            # ワークスペース情報を作成/更新
            workspace_info = AgentWorkspaceInfo(
                path=current_dir,
                files=[],  # 初期化時は空、必要に応じて後で更新
                current_file=None,
                last_modified=datetime.now()
            )
            
            # ファイル一覧を取得（エラー処理付き）
            try:
                files = os.listdir(current_dir)
                workspace_info.files = [f for f in files if os.path.isfile(os.path.join(current_dir, f))]
            except (OSError, PermissionError):
                # アクセス権限がない場合は空リストのまま
                pass
            
            # AgentStateに反映
            self.agent_state.workspace = workspace_info
            
            self.logger.debug(f"AgentState.workspaceを更新: {current_dir}")
            
        except Exception as e:
            self.logger.warning(f"workspace情報の更新エラー: {e}")
            # エラーは無視して継続

    def stop(self):
        """チャットループを停止する"""
        self.running = False
        self.logger.info("ChatLoop (v7) を停止しました")