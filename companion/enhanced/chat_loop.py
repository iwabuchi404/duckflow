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
from enum import Enum

from companion.ui import rich_ui
from companion.workspace_manager import WorkspaceManager
from companion.state.enums import Step, Status


class StatusType(Enum):
    """ステータスタイプの定義（v3a: 型安全性向上）"""
    TASK_COMPLETED = "task_completed"
    TASK_ERROR = "task_error"
    STATE_UPDATED = "state_updated"
    UNKNOWN = "unknown"


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
        # デバッグ用にログレベルを調整
        self.logger.setLevel(logging.DEBUG)
        
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
            # ユーザー入力を別スレッドで開始
            input_task = asyncio.create_task(self._get_user_input_async())
            
            while self.running:
                # 状態監視を実行
                await self._check_status_queue()
                
                # ユーザー入力をチェック（非ブロッキング）
                if input_task.done():
                    user_input = input_task.result()
                    if user_input is not None and user_input.strip():
                        if not await self._handle_enhanced_command(user_input):
                            await self._dispatch_enhanced_ai_task(user_input)
                    elif user_input is None:
                        # 終了要求
                        self.running = False
                        break
                    
                    # 新しい入力タスクを作成
                    input_task = asyncio.create_task(self._get_user_input_async())
                
                # 短い間隔で状態監視を継続
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

    async def _get_user_input_async(self) -> Optional[str]:
        """非同期でユーザー入力を処理（v3a: 状態監視と並行実行）"""
        try:
            # 現在の状態を取得
            current_step = self.agent_state.step.value if self.agent_state.step else "UNKNOWN"
            current_status = self.agent_state.status.value if self.agent_state.status else "UNKNOWN"
            
            # プロンプトを表示
            prompt = f"🦆 [{current_step}.{current_status}] {self.workspace_manager.get_current_directory_name()}> "
            
            # 別スレッドでユーザー入力を待機
            user_input = await asyncio.get_event_loop().run_in_executor(None, input, prompt)
            self.logger.debug(f"ユーザー入力受信: {user_input[:50] if user_input else 'None'}...")
            return user_input.strip() if user_input else None
            
        except (KeyboardInterrupt, EOFError) as e:
            self.logger.info(f"ユーザー入力終了: {type(e).__name__}")
            return None
        except Exception as e:
            self.logger.error(f"非同期ユーザー入力エラー: {e}")
            return None

    async def _get_user_input_non_blocking(self) -> Optional[str]:
        """非ブロッキングでユーザー入力をチェック（v3a: 状態監視優先）"""
        try:
            # 現在の状態を取得
            current_step = self.agent_state.step.value if self.agent_state.step else "UNKNOWN"
            current_status = self.agent_state.status.value if self.agent_state.status else "UNKNOWN"
            
            # プロンプトを表示（状態監視を優先するため、短時間のみ表示）
            prompt = f"🦆 [{current_step}.{current_status}] {self.workspace_manager.get_current_directory_name()}> "
            
            # 非ブロッキングで入力チェック（タイムアウト付き）
            try:
                # より長いタイムアウトで入力チェック（1秒）
                user_input = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(None, input, prompt),
                    timeout=1.0
                )
                self.logger.debug(f"ユーザー入力受信: {user_input[:50] if user_input else 'None'}...")
                return user_input.strip() if user_input else None
                
            except asyncio.TimeoutError:
                # タイムアウト時は入力なしとして扱う
                return None
                
        except (KeyboardInterrupt, EOFError) as e:
            self.logger.info(f"ユーザー入力終了: {type(e).__name__}")
            return "QUIT"
        except Exception as e:
            self.logger.error(f"非ブロッキング入力エラー: {e}")
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
            # デバッグ用ログを追加（頻度を下げる）
            if self.agent_state:
                # ログの頻度を下げる（10回に1回のみ出力）
                if hasattr(self, '_log_counter'):
                    self._log_counter += 1
                else:
                    self._log_counter = 0
                
                if self._log_counter % 10 == 0:
                    self.logger.debug(f"AgentState監視中: last_task_result={self.agent_state.last_task_result is not None}")
                    if self.agent_state.last_task_result:
                        self.logger.debug(f"タスク結果検出: {self.agent_state.last_task_result}")
                        self.logger.debug(f"結果の型: {type(self.agent_state.last_task_result)}")
                        self.logger.debug(f"結果のキー: {list(self.agent_state.last_task_result.keys()) if isinstance(self.agent_state.last_task_result, dict) else 'N/A'}")
            else:
                self.logger.warning("AgentStateがNoneです")
            
            # AgentStateから直接タスク結果を監視
            if self.agent_state and self.agent_state.last_task_result:
                result = self.agent_state.last_task_result
                message_type = result.get('type', StatusType.UNKNOWN.value)
                message = result.get('message', '')
                
                self.logger.info(f"タスク結果を表示: type={message_type}, message={message[:100]}...")
                
                if message_type == StatusType.TASK_COMPLETED.value:
                    rich_ui.print_message(f"✅ 完了: {message}", "success")
                elif message_type == StatusType.TASK_ERROR.value:
                    rich_ui.print_message(f"❌ エラー: {message}", "error")
                else:
                    rich_ui.print_message(f"📊 進捗: {message}", "info")
                
                # 結果をクリアして再表示を防ぐ
                self.agent_state.clear_task_result()
                self.logger.info("タスク結果をクリアしました")
            
            # 状態更新の通知も処理
            try:
                status_update = self.status_queue.get_nowait()
                message_type = status_update.get('type', StatusType.UNKNOWN.value)
                message = status_update.get('message', '')
                
                if message_type == StatusType.STATE_UPDATED.value:
                    rich_ui.print_message(f"📊 状態更新: {message}", "info")
                else:
                    rich_ui.print_message(f"📊 通知: {message}", "info")
                    
                # 修正: status_queueから取得したのでstatus_queueでtask_done()を呼ぶ
                self.status_queue.task_done()
                
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
