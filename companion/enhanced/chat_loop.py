"""
Enhanced ChatLoop - Enhanced v2.0専用版

v4.0 Final版の機能を移植し、AgentStateを直接参照する設計。
状態管理はAgentStateに統一し、StateMachineへの依存を完全に排除。
"""

import queue
import asyncio
import logging
from typing import Optional, Dict, Any
from pathlib import Path

from companion.ui import rich_ui
from companion.workspace_manager import WorkspaceManager
from companion.state.enums import Step, Status


class EnhancedChatLoop:
    """Enhanced v2.0専用ChatLoop - AgentState直接参照版"""
    
    def __init__(self, task_queue: queue.Queue, status_queue: queue.Queue, 
                 enhanced_companion, dual_loop_system):
        self.task_queue = task_queue
        self.status_queue = status_queue
        self.enhanced_companion = enhanced_companion
        self.dual_loop_system = dual_loop_system
        
        # parent_system参照を追加（v3a）
        self.parent_system = dual_loop_system
        
        # AgentStateを直接参照（StateMachine不要）
        self.agent_state = dual_loop_system.agent_state
        
        # WorkspaceManager統合（v4.0 Final版から移植）
        self.workspace_manager = WorkspaceManager()
        
        self.running = False
        self.logger = logging.getLogger(__name__)
        
        self.logger.info("EnhancedChatLoop initialized with AgentState direct reference")

    def run(self):
        """Enhanced v2.0専用の対話ループ開始"""
        self.running = True
        self.logger.info("EnhancedChatLoop を開始しました")
        
        # Enhanced v2.0専用の起動メッセージ
        rich_ui.print_message("🦆 Duckflow Enhanced v2.0", "success")
        rich_ui.print_message("状態管理統一版 - AgentState一本化", "info")
        rich_ui.print_message("タスク実行中も対話を継続できます！ `help`でコマンド一覧を表示。", "info")
        
        asyncio.run(self._async_main_loop())

    async def _async_main_loop(self):
        """非同期メインループ（Enhanced v2.0版）"""
        try:
            while self.running:
                await self._check_status_queue()
                user_input = await self._get_user_input()
                
                if user_input is not None and user_input.strip():
                    if not await self._handle_enhanced_command(user_input):
                        await self._dispatch_enhanced_ai_task(user_input)
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
        """ユーザー入力を非同期で受け取る（Enhanced v2.0版）"""
        try:
            # AgentStateから現在の状態を取得してプロンプトに表示
            current_step = self.agent_state.step.value if self.agent_state.step else "UNKNOWN"
            current_status = self.agent_state.status.value if self.agent_state.status else "UNKNOWN"
            
            prompt = f"🦆 [{current_step}.{current_status}] {self.workspace_manager.get_current_directory_name()}> "
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

    async def _handle_enhanced_command(self, user_input: str) -> bool:
        """Enhanced v2.0専用の内部コマンド処理"""
        command = user_input.strip().lower()
        parts = command.split()
        if not parts:
            return False

        cmd = parts[0]

        if cmd in ['quit', 'exit', 'q']:
            self.running = False
            return True
            
        elif cmd == 'help':
            self._show_enhanced_help()
            return True
            
        elif cmd == 'status':
            # AgentStateベースの状態表示
            self._show_enhanced_status()
            return True
            
        elif cmd == 'state':
            # 詳細な状態情報表示（Enhanced v2.0専用）
            self._show_detailed_state()
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
        
        return False  # AIに処理を渡す

    def _show_enhanced_help(self):
        """Enhanced v2.0専用のヘルプ表示"""
        help_text = """
🦆 Enhanced v2.0 利用可能なコマンド:

基本コマンド:
  cd <dir>     - ディレクトリ移動
  ls [path]    - ファイル一覧表示
  pwd          - 現在のディレクトリ表示
  help         - このヘルプを表示
  quit/exit/q  - 終了

状態管理コマンド:
  status       - 現在の状態表示
  state        - 詳細な状態情報表示

AI処理:
  その他の入力 - AIによる処理
        """
        rich_ui.print_message(help_text, "info")

    def _show_enhanced_status(self):
        """Enhanced v2.0専用の状態表示"""
        try:
            # AgentStateから状態を取得
            step = self.agent_state.step.value if self.agent_state.step else "UNKNOWN"
            status = self.agent_state.status.value if self.agent_state.status else "UNKNOWN"
            goal = self.agent_state.goal or "未設定"
            
            status_text = f"""
📊 Enhanced v2.0 現在の状態:
  ステップ: {step}
  ステータス: {status}
  目標: {goal}
  セッションID: {self.dual_loop_system.session_id}
            """
            rich_ui.print_message(status_text, "info")
            
        except Exception as e:
            rich_ui.print_message(f"状態取得エラー: {e}", "error")

    def _show_detailed_state(self):
        """詳細な状態情報表示（Enhanced v2.0専用）"""
        try:
            # 固定5項目の表示
            state_info = self.agent_state.get_context_summary()
            
            detailed_text = f"""
🔍 Enhanced v2.0 詳細状態:

固定5項目:
  目標: {state_info.get('goal', '未設定')}
  なぜ今やるのか: {state_info.get('why_now', '未設定')}
  制約: {', '.join(state_info.get('constraints', []))}
  直近の計画: {', '.join(state_info.get('plan_brief', []))}
  未解決の問い: {', '.join(state_info.get('open_questions', []))}

状態情報:
  ステップ: {state_info.get('current_step', 'UNKNOWN')}
  ステータス: {state_info.get('current_status', 'UNKNOWN')}
  最後の変更: {state_info.get('last_delta', 'なし')}
  会話数: {state_info.get('conversation_count', 0)}件
  セッション開始: {state_info.get('created_at', 'UNKNOWN')}

バイタル:
  気分: {state_info.get('vitals', {}).get('mood', 'UNKNOWN')}
  集中力: {state_info.get('vitals', {}).get('focus', 'UNKNOWN')}
  体力: {state_info.get('vitals', {}).get('stamina', 'UNKNOWN')}
            """
            rich_ui.print_message(detailed_text, "info")
            
        except Exception as e:
            rich_ui.print_message(f"詳細状態取得エラー: {e}", "error")

    async def _dispatch_enhanced_ai_task(self, user_input: str):
        """Enhanced v2.0専用のAI処理タスクディスパッチ"""
        try:
            self.logger.info(f"Enhanced AIタスクをディスパッチ: {user_input}")
            
            # Enhanced v2.0専用の2ステップ呼び出し
            intent_result = await self.enhanced_companion.analyze_intent_only(user_input)
            
            task_data = {
                "type": "process_enhanced_intent",
                "intent_result": intent_result,
                "user_input": user_input
            }
            
            self.task_queue.put(task_data)
            rich_ui.print_message("🤔 Enhanced思考中...", "info")
            
        except Exception as e:
            self.logger.error(f"Enhanced AIタスクのディスパッチ中にエラー: {e}", exc_info=True)
            rich_ui.print_message(f"❌ Enhanced意図理解の開始に失敗しました: {e}", "error")

    async def _check_status_queue(self):
        """EnhancedTaskLoopからの状態更新を処理（v3a）"""
        try:
            # AgentStateから直接タスク結果を監視
            if self.agent_state and self.agent_state.last_task_result:
                result = self.agent_state.last_task_result
                message_type = result.get('type', 'unknown')
                message = result.get('message', '')
                
                if message_type == 'task_completed':
                    rich_ui.print_message(f"✅ 完了: {message}", "success")
                elif message_type == 'task_error':
                    rich_ui.print_message(f"❌ エラー: {message}", "error")
                else:
                    rich_ui.print_message(f"📊 進捗: {message}", "info")
                
                # 結果をクリアして再表示を防ぐ
                self.agent_state.clear_task_result()
            
            # 状態更新の通知も処理
            try:
                status_update = self.status_queue.get_nowait()
                message_type = status_update.get('type', 'unknown')
                message = status_update.get('message', '')
                
                if message_type == 'state_updated':
                    rich_ui.print_message(f"📊 状態更新: {message}", "info")
                else:
                    rich_ui.print_message(f"📊 通知: {message}", "info")
                    
                self.task_queue.task_done()
                
            except queue.Empty:
                pass
            
        except Exception as e:
            self.logger.error(f"状態監視エラー: {e}")
        
        # 定期的な呼び出しのための遅延
        await asyncio.sleep(0.1)

    def stop(self):
        """Enhanced v2.0専用の停止処理"""
        self.running = False
        self.logger.info("EnhancedChatLoop を停止しました")
