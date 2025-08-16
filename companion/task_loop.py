"""
Task Loop - 実行ループ
バックグラウンドでタスクを実行
"""

import queue
import time
import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from .core import CompanionCore
from .checkpoint_manager import CheckpointManager
from .hierarchical_task_manager import HierarchicalTaskManager, TaskStatus, TaskPriority
from .collaborative_planner import CollaborativePlanner, PlanStatus
from .error_recovery_system import ErrorRecoverySystem, ErrorSeverity
from .workspace_manager import WorkspaceManager


class TaskLoop:
    """実行ループ - バックグラウンドでタスクを実行"""
    
    def __init__(self, task_queue: queue.Queue, status_queue: queue.Queue, shared_companion=None, context_manager=None):
        """TaskLoopを初期化
        
        Args:
            task_queue: ChatLoopからタスクを受信するキュー
            status_queue: ChatLoopに状態を送信するキュー
            shared_companion: 共有のCompanionCoreインスタンス（オプション）
            context_manager: 共有コンテキスト管理（オプション）
        """
        self.task_queue = task_queue
        self.status_queue = status_queue
        self.running = False
        self.current_task: Optional[str] = None
        
        # Step 2: 一時停止・再開機能
        self.paused = False
        self.pause_requested = False
        self.resume_requested = False
        
        # 共有CompanionCoreまたは新規作成
        if shared_companion:
            self.companion = shared_companion
        else:
            from .core import CompanionCore
            self.companion = CompanionCore()
        
        # 共有コンテキスト管理
        self.context_manager = context_manager
        
        # Step 2: チェックポイント機能
        self.checkpoint_manager = CheckpointManager()
        self.current_task_id: Optional[str] = None
        
        # Step 2: 階層タスク管理
        self.hierarchical_manager = HierarchicalTaskManager()
        self.hierarchical_manager.set_task_executor(self._execute_sub_task)
        self.current_parent_task_id: Optional[str] = None
        self.enable_hierarchical_mode = True  # 階層タスク機能の有効/無効
        
        # Step 3: 協調的計画
        self.collaborative_planner = CollaborativePlanner()
        self.enable_collaborative_planning = True  # 協調的計画の有効/無効
        
        # Step 3: エラー回復システム
        self.error_recovery = ErrorRecoverySystem()
        self.pending_recovery_plan_id: Optional[str] = None
        self.waiting_for_recovery_decision = False
        
        # ワークスペース管理
        self.workspace_manager = WorkspaceManager()
        
        # ログ設定
        self.logger = logging.getLogger(__name__)
    
    def run(self):
        """メインの実行ループ"""
        self.running = True
        self.logger.info("TaskLoop を開始しました")
        
        while self.running:
            try:
                # 新しいタスクを取得（1秒でタイムアウト）
                try:
                    task_data = self.task_queue.get(timeout=1.0)
                    self._execute_task_unified(task_data)
                except queue.Empty:
                    # タスクがない場合は待機
                    continue
                
            except Exception as e:
                self.logger.error(f"TaskLoop エラー: {e}")
                self._send_status(f"❌ エラー: {str(e)}")
                self.current_task = None
    
    def _execute_task(self, task_description: str):
        """タスクを実行
        
        Args:
            task_description: タスクの説明
        """
        self.current_task = task_description
        self.logger.info(f"タスク実行開始: {task_description}")
        
        try:
            # 実行開始を通知
            self._send_status(f"🚀 実行開始: {task_description[:50]}...")
            
            # 既存のCompanionCoreを使用してタスクを実行
            self.logger.info(f"CompanionCoreでタスク処理開始: {task_description}")
            result = asyncio.run(self._process_task(task_description))
            self.logger.info(f"CompanionCoreからの結果: {len(result) if result else 0}文字")
            
            # 完了を通知
            if result:
                # 結果が長い場合は適切に切り詰める
                if len(result) > 200:
                    preview = result[:200] + "..."
                    self._send_status(f"✅ 完了: {preview}")
                    # 完全な結果も送信
                    self._send_status(f"📄 完全な結果:\n{result}")
                else:
                    self._send_status(f"✅ 完了: {result}")
            else:
                self._send_status("✅ タスクが完了しました（結果なし）")
            
            self.logger.info(f"タスク実行完了: {task_description}")
            
        except Exception as e:
            # エラーを通知
            error_msg = f"❌ エラー: {str(e)}"
            self._send_status(error_msg)
            self.logger.error(f"タスク実行エラー: {e}")
        
        finally:
            self.current_task = None
    
    def _execute_task_unified(self, task_data):
        """統一タスク実行（Step 1改善）
        
        Args:
            task_data: ChatLoopからのタスクデータ（意図理解結果含む）
        """
        try:
            # タスクデータの種類を判定
            if isinstance(task_data, dict) and task_data.get("type") == "task_with_intent":
                # 新形式: 意図理解結果付きタスク
                self._execute_task_with_intent(task_data)
            else:
                # 旧形式: 従来のタスク実行（後方互換性）
                self._execute_task(task_data)
                
        except Exception as e:
            self.logger.error(f"統一タスク実行エラー: {e}")
            self._send_status(f"❌ タスク実行エラー: {str(e)}")
            self.current_task = None
    
    def _execute_task_with_intent(self, task_data: dict):
        """意図理解結果を再利用したタスク実行
        
        Args:
            task_data: 意図理解結果を含むタスクデータ
        """
        intent_result = task_data["intent_result"]
        user_message = intent_result["message"]
        
        self.current_task = user_message
        self.logger.info(f"意図理解結果再利用タスク実行開始: {user_message}")
        
        try:
            # 実行開始を通知
            self._send_status(f"🚀 実行開始: {user_message[:50]}...")
            
            # Step 3: 協調的計画の判定と実行
            if self.enable_collaborative_planning:
                execution_result = self._execute_with_collaborative_planning(user_message, intent_result)
                if execution_result:
                    return  # 協調的計画で処理済み
            
            # Step 2: 階層タスク管理の判定
            if self.enable_hierarchical_mode and self._should_use_hierarchical_mode(user_message):
                self._execute_hierarchical_task(user_message, intent_result)
            else:
                # 通常の実行
                self.logger.info(f"CompanionCoreで意図理解結果再利用処理開始: {user_message}")
                result = asyncio.run(self._process_task_with_intent(intent_result))
                self.logger.info(f"CompanionCoreからの結果: {len(result) if result else 0}文字")
                
                # 完了を通知
                if result:
                    # 結果が長い場合は適切に切り詰める
                    if len(result) > 200:
                        preview = result[:200] + "..."
                        self._send_status(f"✅ 完了: {preview}")
                        # 完全な結果も送信
                        self._send_status(f"📄 完全な結果:\n{result}")
                    else:
                        self._send_status(f"✅ 完了: {result}")
                else:
                    self._send_status("✅ タスクが完了しました（結果なし）")
            
            # コンテキスト更新
            if self.context_manager:
                self.context_manager.update_context("last_task_result", {
                    "type": "task_completed",
                    "result": getattr(self, '_last_result', 'タスク完了'),
                    "action_type": intent_result["action_type"].value,
                    "timestamp": datetime.now()
                })
            
            self.logger.info(f"タスク実行完了: {user_message}")
            
        except Exception as e:
            # エラーを通知
            error_msg = f"❌ エラー: {str(e)}"
            self._send_status(error_msg)
            self.logger.error(f"タスク実行エラー: {e}")
            
            # コンテキスト更新
            if self.context_manager:
                self.context_manager.update_context("last_task_error", {
                    "type": "task_error",
                    "error": str(e),
                    "timestamp": datetime.now()
                })
        
        finally:
            self.current_task = None
            self.current_parent_task_id = None
    
    async def _process_task_with_intent(self, intent_result: dict) -> str:
        """意図理解結果を再利用してタスクを処理
        
        Args:
            intent_result: analyze_intent_onlyの結果
            
        Returns:
            str: 処理結果
        """
        try:
            # 進捗を報告
            self._send_status("🔍 意図理解結果を再利用中...")
            
            # Step 2: 一時停止チェック
            self._check_pause_resume()
            
            # 少し待機（進捗表示のため）
            await asyncio.sleep(0.5)
            
            # Step 2: 一時停止チェック
            self._check_pause_resume()
            
            # 既存のCompanionCoreで意図理解結果を再利用して処理
            self._send_status("⚙️ CompanionCoreで処理中...")
            result = await self.companion.process_with_intent_result(intent_result)
            
            # 結果の検証
            if not result or result.strip() == "":
                return "タスクは完了しましたが、結果が空でした。"
            
            return result
            
        except Exception as e:
            self.logger.error(f"意図理解結果再利用処理中にエラー: {e}")
            return f"タスク処理中にエラーが発生しました: {str(e)}"
    
    async def _process_task(self, task_description: str) -> str:
        """タスクを処理（既存のCompanionCoreを活用）
        
        Args:
            task_description: タスクの説明
            
        Returns:
            str: 処理結果
        """
        try:
            # 進捗を報告
            self._send_status("🔍 タスクを分析中...")
            
            # 少し待機（進捗表示のため）
            await asyncio.sleep(0.5)
            
            # 既存のCompanionCoreでタスクを処理
            self._send_status("⚙️ CompanionCoreで処理中...")
            result = await self.companion.process_message(task_description)
            
            # 結果の検証
            if not result or result.strip() == "":
                return "タスクは完了しましたが、結果が空でした。"
            
            return result
            
        except Exception as e:
            self.logger.error(f"タスク処理中にエラー: {e}")
            return f"タスク処理中にエラーが発生しました: {str(e)}"
    
    def _send_status(self, status: str):
        """ChatLoopに状態を送信
        
        Args:
            status: 状態メッセージ
        """
        try:
            self.status_queue.put(status)
            self.logger.info(f"状態送信: {status[:100]}...")
        except Exception as e:
            self.logger.error(f"状態送信エラー: {e}")
    
    def stop(self):
        """TaskLoopを停止"""
        self.running = False
        
        # 実行中のタスクがある場合は通知
        if self.current_task:
            self._send_status("⏹️ システム停止のため、タスクを中断しました")
        
        self.logger.info("TaskLoop を停止しました")
    
    def get_current_task(self) -> Optional[str]:
        """現在実行中のタスクを取得
        
        Returns:
            Optional[str]: 実行中のタスク（なければNone）
        """
        return self.current_task
    
    def is_busy(self) -> bool:
        """タスク実行中かどうか
        
        Returns:
            bool: 実行中の場合True
        """
        return self.current_task is not None
    
    # Step 2: 一時停止・再開機能
    def pause(self):
        """タスク実行を一時停止"""
        if self.current_task and not self.paused:
            self.pause_requested = True
            self._send_status("⏸️ タスクの一時停止を要求しました...")
            self.logger.info("タスクの一時停止を要求")
        elif self.paused:
            self._send_status("⏸️ タスクは既に一時停止中です")
        else:
            self._send_status("⏸️ 実行中のタスクがありません")
    
    def resume(self):
        """タスク実行を再開"""
        if self.paused:
            self.resume_requested = True
            self.paused = False
            self._send_status("▶️ タスクの再開を開始します...")
            self.logger.info("タスクの再開を要求")
        else:
            self._send_status("▶️ タスクは一時停止していません")
    
    def _check_pause_resume(self):
        """一時停止・再開のチェック（タスク実行中に定期的に呼び出す）"""
        if self.pause_requested and not self.paused:
            self.paused = True
            self.pause_requested = False
            self._send_status("⏸️ タスクを一時停止しました。再開するには 'resume' と入力してください")
            self.logger.info("タスクを一時停止")
            
        # 一時停止中は待機
        while self.paused and self.running:
            time.sleep(0.1)
            if self.resume_requested:
                self.resume_requested = False
                self._send_status("▶️ タスクを再開します")
                self.logger.info("タスクを再開")
                break
    
    def get_status(self) -> Dict[str, Any]:
        """Step 2: 詳細なステータス情報を取得"""
        status = {
            "running": self.running,
            "current_task": self.current_task,
            "paused": self.paused,
            "is_busy": self.is_busy(),
            "queue_size": self.task_queue.qsize() if hasattr(self.task_queue, 'qsize') else 0,
            "current_task_id": self.current_task_id,
            "checkpoint_count": len(self.checkpoint_manager.checkpoints) if self.checkpoint_manager else 0,
            "hierarchical_mode": self.enable_hierarchical_mode
        }
        
        # 階層タスク情報を追加
        if self.current_parent_task_id:
            task_summary = self.hierarchical_manager.get_task_status_summary(self.current_parent_task_id)
            status["hierarchical_task"] = task_summary
        
        return status
    
    # Step 2: チェックポイント機能メソッド
    def create_checkpoint(self, step_number: int, total_steps: int, 
                         state_data: Dict[str, Any]) -> Optional[str]:
        """現在のタスクのチェックポイントを作成
        
        Args:
            step_number: 現在のステップ番号
            total_steps: 総ステップ数
            state_data: 保存する状態データ
            
        Returns:
            Optional[str]: 作成されたチェックポイントID
        """
        if not self.current_task_id or not self.current_task:
            return None
        
        try:
            checkpoint_id = self.checkpoint_manager.create_checkpoint(
                task_id=self.current_task_id,
                task_description=self.current_task,
                step_number=step_number,
                total_steps=total_steps,
                state_data=state_data,
                context={
                    "paused": self.paused,
                    "created_during_execution": True
                }
            )
            
            self._send_status(f"💾 チェックポイント作成: ステップ {step_number}/{total_steps}")
            self.logger.info(f"チェックポイント作成: {checkpoint_id}")
            
            return checkpoint_id
            
        except Exception as e:
            self.logger.error(f"チェックポイント作成エラー: {e}")
            return None
    
    def restore_from_checkpoint(self, checkpoint_id: str) -> bool:
        """チェックポイントから復元
        
        Args:
            checkpoint_id: チェックポイントID
            
        Returns:
            bool: 復元に成功した場合True
        """
        try:
            checkpoint = self.checkpoint_manager.restore_checkpoint(checkpoint_id)
            if not checkpoint:
                self._send_status(f"❌ チェックポイント {checkpoint_id} が見つかりません")
                return False
            
            self.current_task = checkpoint.task_description
            self.current_task_id = checkpoint.task_id
            
            self._send_status(f"🔄 チェックポイントから復元: {checkpoint.task_description}")
            self._send_status(f"📊 進捗: {checkpoint.progress:.1%} ({checkpoint.step_number}/{checkpoint.total_steps})")
            
            self.logger.info(f"チェックポイントから復元: {checkpoint_id}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"チェックポイント復元エラー: {e}")
            self._send_status(f"❌ チェックポイント復元に失敗: {str(e)}")
            return False
    
    def list_checkpoints(self) -> None:
        """現在のタスクのチェックポイント一覧を表示"""
        if not self.current_task_id:
            self._send_status("📋 実行中のタスクがありません")
            return
        
        checkpoints = self.checkpoint_manager.list_checkpoints(self.current_task_id)
        
        if not checkpoints:
            self._send_status("📋 チェックポイントがありません")
            return
        
        self._send_status(f"📋 タスク '{self.current_task_id}' のチェックポイント:")
        for i, cp in enumerate(checkpoints[:5], 1):  # 最新5件のみ
            progress_bar = "█" * int(cp.progress * 10) + "░" * (10 - int(cp.progress * 10))
            self._send_status(f"  {i}. {cp.checkpoint_id[:12]}... ({cp.progress:.1%}) [{progress_bar}]")
            self._send_status(f"     ステップ {cp.step_number}/{cp.total_steps} - {cp.created_at.strftime('%H:%M:%S')}")
    
    def _start_new_task(self, task_description: str) -> None:
        """新しいタスクを開始し、タスクIDを生成"""
        import uuid
        self.current_task_id = str(uuid.uuid4())[:8]  # 短縮ID
        self.current_task = task_description
        
        # 初期チェックポイントを作成
        self.create_checkpoint(
            step_number=0,
            total_steps=1,  # デフォルト、後で更新可能
            state_data={
                "task_started": True,
                "task_description": task_description,
                "start_time": datetime.now().isoformat()
            }
        )
    
    def _should_use_hierarchical_mode(self, task_description: str) -> bool:
        """階層タスクモードを使用すべきか判定
        
        Args:
            task_description: タスクの説明
            
        Returns:
            bool: 階層モードを使用する場合True
        """
        # 複雑なタスクのキーワードをチェック
        hierarchical_keywords = [
            "プロジェクト", "実装", "システム", "開発", 
            "アプリケーション", "サイト", "機能", "モジュール",
            "複数", "まとめて", "一連", "ステップ", "段階"
        ]
        
        task_lower = task_description.lower()
        return any(keyword in task_lower for keyword in hierarchical_keywords)
    
    def _execute_hierarchical_task(self, task_description: str, intent_result: dict):
        """階層タスクを実行
        
        Args:
            task_description: タスクの説明
            intent_result: 意図理解結果
        """
        try:
            # 階層タスクを作成
            self._send_status("🌳 タスクを階層分割中...")
            parent_task_id = self.hierarchical_manager.decompose_task(task_description)
            
            if not parent_task_id:
                # 分割に失敗した場合は通常実行にフォールバック
                self._send_status("⚠️ タスク分割に失敗、通常実行に切り替えます")
                result = asyncio.run(self._process_task_with_intent(intent_result))
                self._last_result = result
                return
            
            self.current_parent_task_id = parent_task_id
            
            # 階層タスクを開始
            if not self.hierarchical_manager.start_parent_task(parent_task_id):
                self._send_status("❌ 階層タスクの開始に失敗")
                return
            
            # タスク状態を表示
            self._show_hierarchical_task_status(parent_task_id)
            
            # 子タスクを順次実行
            self._execute_sub_tasks(parent_task_id)
            
        except Exception as e:
            self.logger.error(f"階層タスク実行エラー: {e}")
            self._send_status(f"❌ 階層タスク実行エラー: {str(e)}")
    
    def _execute_sub_tasks(self, parent_task_id: str):
        """子タスクを順次実行
        
        Args:
            parent_task_id: 親タスクID
        """
        while True:
            # 一時停止チェック
            self._check_pause_resume()
            
            # 次の実行可能な子タスクを取得
            next_sub_task = self.hierarchical_manager.get_next_sub_task(parent_task_id)
            
            if not next_sub_task:
                # すべての子タスクが完了または実行可能なタスクがない
                parent_task = self.hierarchical_manager.parent_tasks.get(parent_task_id)
                if parent_task and parent_task.is_completed():
                    self._send_status("✅ すべての子タスクが完了しました")
                    self._last_result = "階層タスクが正常に完了しました"
                else:
                    self._send_status("⚠️ 依存関係のため実行可能なタスクがありません")
                    self._last_result = "階層タスクが異常終了しました"
                break
            
            # 子タスクを実行
            self._execute_single_sub_task(parent_task_id, next_sub_task)
            
            # タスク状態を更新表示
            self._show_hierarchical_task_progress(parent_task_id)
    
    def _execute_single_sub_task(self, parent_task_id: str, sub_task):
        """単一の子タスクを実行
        
        Args:
            parent_task_id: 親タスクID
            sub_task: 実行する子タスク
        """
        try:
            # 子タスク開始
            self._send_status(f"🔄 子タスク実行: {sub_task.name}")
            self.hierarchical_manager.update_sub_task_status(
                parent_task_id, sub_task.task_id, TaskStatus.RUNNING
            )
            
            # チェックポイント作成
            if self.current_task_id:
                try:
                    step_num = int(sub_task.task_id.split('_')[-1])
                except (ValueError, IndexError):
                    step_num = 1
                    
                self.create_checkpoint(
                    step_number=step_num,
                    total_steps=len(self.hierarchical_manager.parent_tasks[parent_task_id].sub_tasks),
                    state_data={
                        "sub_task_id": sub_task.task_id,
                        "sub_task_name": sub_task.name,
                        "parent_task_id": parent_task_id
                    }
                )
            
            # 子タスクを実行（エラー回復機能付き）
            result = self._execute_sub_task_with_recovery(sub_task, parent_task_id)
            
            # 結果を更新
            self.hierarchical_manager.update_sub_task_status(
                parent_task_id, sub_task.task_id, TaskStatus.COMPLETED,
                progress=1.0, result=result
            )
            
            self._send_status(f"✅ 子タスク完了: {sub_task.name}")
            
        except Exception as e:
            # Step 3: エラー回復システムによる処理
            if self._handle_task_error(e, sub_task.task_id, sub_task.name):
                return  # エラー回復待ち
            
            # エラー回復が失敗または利用不可の場合
            self.logger.error(f"子タスク実行エラー: {e}")
            self.hierarchical_manager.update_sub_task_status(
                parent_task_id, sub_task.task_id, TaskStatus.FAILED,
                error_message=str(e)
            )
            self._send_status(f"❌ 子タスク失敗: {sub_task.name} - {str(e)}")
    
    async def _execute_sub_task(self, task_description: str) -> str:
        """子タスクを実行するメソッド
        
        Args:
            task_description: 子タスクの説明
            
        Returns:
            str: 実行結果
        """
        try:
            # 一時停止チェック
            self._check_pause_resume()
            
            # CompanionCoreで子タスクを処理
            result = await self.companion.process_message(task_description)
            
            if not result or result.strip() == "":
                return f"子タスク '{task_description}' が完了しました。"
            
            return result
            
        except Exception as e:
            self.logger.error(f"子タスク処理エラー: {e}")
            raise e
    
    def _show_hierarchical_task_status(self, parent_task_id: str):
        """階層タスクの状態を表示
        
        Args:
            parent_task_id: 親タスクID
        """
        summary = self.hierarchical_manager.get_task_status_summary(parent_task_id)
        if "error" in summary:
            return
        
        parent_info = summary["parent_task"]
        self._send_status(f"🌳 階層タスク: {parent_info['name']}")
        self._send_status(f"📋 子タスク数: {parent_info['total_sub_tasks']}個")
        
        for i, sub_task in enumerate(summary["sub_tasks"], 1):
            status_icon = {
                "pending": "⏳",
                "running": "🔄",
                "completed": "✅",
                "failed": "❌",
                "paused": "⏸️"
            }.get(sub_task["status"], "❓")
            
            self._send_status(f"  {i}. {status_icon} {sub_task['name']} ({sub_task['status']})")
    
    def _show_hierarchical_task_progress(self, parent_task_id: str):
        """階層タスクの進捗を表示
        
        Args:
            parent_task_id: 親タスクID
        """
        summary = self.hierarchical_manager.get_task_status_summary(parent_task_id)
        if "error" in summary:
            return
        
        parent_info = summary["parent_task"]
        progress_bar = "█" * int(parent_info["progress"] * 10) + "░" * (10 - int(parent_info["progress"] * 10))
        
        self._send_status(f"📊 進捗: [{progress_bar}] {parent_info['progress']:.1%}")
    
    def get_hierarchical_task_info(self) -> Optional[Dict[str, Any]]:
        """現在の階層タスク情報を取得
        
        Returns:
            Optional[Dict[str, Any]]: 階層タスク情報
        """
        if not self.current_parent_task_id:
            return None
        
        return self.hierarchical_manager.get_task_status_summary(self.current_parent_task_id)
    
    def toggle_hierarchical_mode(self) -> bool:
        """階層タスクモードの有効/無効を切り替え
        
        Returns:
            bool: 新しいモード状態
        """
        self.enable_hierarchical_mode = not self.enable_hierarchical_mode
        self._send_status(f"🌳 階層タスクモード: {'ON' if self.enable_hierarchical_mode else 'OFF'}")
        return self.enable_hierarchical_mode
    
    def show_hierarchical_status(self):
        """現在の階層タスクの詳細状態を表示"""
        if not self.current_parent_task_id:
            self._send_status("🌳 現在実行中の階層タスクはありません")
            return
        
        self._show_hierarchical_task_status(self.current_parent_task_id)
        self._show_hierarchical_task_progress(self.current_parent_task_id)
    
    def _execute_with_collaborative_planning(self, task_description: str, intent_result: dict) -> bool:
        """協調的計画を使用してタスクを実行
        
        Args:
            task_description: タスクの説明
            intent_result: 意図理解結果
            
        Returns:
            bool: 協調的計画で処理した場合True
        """
        try:
            # タスクの複雑度を分析して計画が必要かチェック
            plan_id = self.collaborative_planner.analyze_and_create_plan(task_description)
            
            if not plan_id:
                # シンプルなタスクのため協調的計画は不要
                return False
            
            # 計画を提案
            self._send_status("📋 タスクを分析中...")
            plan_presentation = self.collaborative_planner.get_plan_presentation(plan_id)
            
            # ChatLoopに計画提示を送信（特別なメッセージ形式）
            self._send_status(f"PLAN_PROPOSAL:{plan_id}")
            self._send_status(plan_presentation)
            
            # ユーザーの応答を待機するため、ここでは保留
            # 実際の実行はユーザーの承認後に別途実行される
            self.logger.info(f"協調的計画を提案: {plan_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"協調的計画エラー: {e}")
            self._send_status(f"⚠️ 計画作成中にエラーが発生しました: {str(e)}")
            return False
    
    def execute_approved_plan(self, plan_id: str) -> bool:
        """承認された計画を実行
        
        Args:
            plan_id: 実行する計画ID
            
        Returns:
            bool: 実行開始に成功した場合True
        """
        try:
            # 計画を階層タスクに変換
            parent_task_id = self.collaborative_planner.convert_plan_to_hierarchical_tasks(plan_id)
            
            if not parent_task_id:
                self._send_status("❌ 計画の実行開始に失敗しました")
                return False
            
            self.current_parent_task_id = parent_task_id
            
            # 階層タスクを開始
            if not self.hierarchical_manager.start_parent_task(parent_task_id):
                self._send_status("❌ 階層タスクの開始に失敗")
                return False
            
            self._send_status("🚀 承認された計画の実行を開始します")
            
            # タスク状態を表示
            self._show_hierarchical_task_status(parent_task_id)
            
            # 子タスクを順次実行
            self._execute_sub_tasks(parent_task_id)
            
            return True
            
        except Exception as e:
            self.logger.error(f"承認済み計画実行エラー: {e}")
            self._send_status(f"❌ 計画実行中にエラーが発生しました: {str(e)}")
            return False
    
    def process_plan_feedback(self, plan_id: str, feedback: str) -> str:
        """計画に対するユーザーフィードバックを処理
        
        Args:
            plan_id: 計画ID
            feedback: ユーザーのフィードバック
            
        Returns:
            str: 処理結果メッセージ
        """
        try:
            success, message = self.collaborative_planner.process_user_feedback(plan_id, feedback)
            
            if success:
                plan = self.collaborative_planner.get_current_plan()
                if plan and plan.status == PlanStatus.APPROVED:
                    # 承認された場合は実行を開始
                    self.execute_approved_plan(plan_id)
                
                return message
            else:
                return f"❌ フィードバック処理に失敗しました: {message}"
                
        except Exception as e:
            self.logger.error(f"計画フィードバック処理エラー: {e}")
            return f"❌ フィードバック処理中にエラーが発生しました: {str(e)}"
    
    def toggle_collaborative_planning(self) -> bool:
        """協調的計画モードの有効/無効を切り替え
        
        Returns:
            bool: 新しいモード状態
        """
        self.enable_collaborative_planning = not self.enable_collaborative_planning
        self._send_status(f"📋 協調的計画モード: {'ON' if self.enable_collaborative_planning else 'OFF'}")
        return self.enable_collaborative_planning
    
    def show_current_plan(self):
        """現在の計画を表示"""
        plan = self.collaborative_planner.get_current_plan()
        if not plan:
            self._send_status("📋 現在進行中の計画はありません")
            return
        
        presentation = self.collaborative_planner.get_plan_presentation(plan.plan_id)
        self._send_status("📋 現在の計画:")
        self._send_status(presentation)
    
    def _execute_sub_task_with_recovery(self, sub_task, parent_task_id: str) -> str:
        """エラー回復機能付きで子タスクを実行
        
        Args:
            sub_task: 実行する子タスク
            parent_task_id: 親タスクID
            
        Returns:
            str: 実行結果
        """
        max_attempts = 3
        attempt = 1
        
        while attempt <= max_attempts:
            try:
                # 一時停止チェック
                self._check_pause_resume()
                
                # CompanionCoreで子タスクを処理
                result = asyncio.run(self._execute_sub_task(sub_task.description))
                
                if not result or result.strip() == "":
                    return f"子タスク '{sub_task.description}' が完了しました。"
                
                return result
                
            except Exception as e:
                self.logger.warning(f"子タスク実行試行 {attempt}/{max_attempts} 失敗: {e}")
                
                # エラー文脈を作成
                error_context = self.error_recovery.capture_error(
                    error=e,
                    task_id=sub_task.task_id,
                    step_name=sub_task.name,
                    context_data={
                        "parent_task_id": parent_task_id,
                        "attempt": attempt,
                        "max_attempts": max_attempts
                    }
                )
                
                # 自動回復を試行
                if attempt < max_attempts and self.error_recovery.should_auto_recover(error_context):
                    self._send_status(f"⚠️ エラーが発生しました。自動回復を試行します... (試行 {attempt}/{max_attempts})")
                    
                    # 回復計画を作成
                    recovery_plan = self.error_recovery.create_recovery_plan(error_context)
                    recommended_action = recovery_plan.get_recommended_action()
                    
                    if recommended_action and recommended_action.auto_executable:
                        # 自動回復を実行
                        success, message = self.error_recovery.execute_recovery_action(
                            recovery_plan.plan_id, 
                            recommended_action.action_id
                        )
                        
                        if success:
                            self._send_status(f"🔄 自動回復成功: {message}")
                            attempt += 1
                            continue
                    
                # 最後の試行または重大なエラーの場合
                if attempt >= max_attempts or error_context.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
                    # ユーザーに回復オプションを提示
                    self._present_recovery_options(error_context)
                    raise e
                
                attempt += 1
        
        # すべての試行が失敗した場合
        raise Exception(f"子タスク '{sub_task.name}' が {max_attempts} 回の試行後も失敗しました")
    
    def _handle_task_error(self, error: Exception, task_id: str, step_name: str) -> bool:
        """タスクエラーを処理
        
        Args:
            error: 発生したエラー
            task_id: タスクID
            step_name: ステップ名
            
        Returns:
            bool: エラー回復待ちの場合True
        """
        try:
            # エラー文脈を作成
            error_context = self.error_recovery.capture_error(
                error=error,
                task_id=task_id,
                step_name=step_name
            )
            
            # 重大なエラーまたは頻発するエラーの場合は即座にユーザーに提示
            if not self.error_recovery.should_auto_recover(error_context):
                self._present_recovery_options(error_context)
                return True
            
            # 軽微なエラーの場合は自動回復を試行
            recovery_plan = self.error_recovery.create_recovery_plan(error_context)
            recommended_action = recovery_plan.get_recommended_action()
            
            if recommended_action and recommended_action.auto_executable:
                success, message = self.error_recovery.execute_recovery_action(
                    recovery_plan.plan_id, 
                    recommended_action.action_id
                )
                
                if success:
                    self._send_status(f"🔄 自動回復完了: {message}")
                    return False  # 自動回復成功、処理続行
            
            # 自動回復失敗の場合はユーザーに提示
            self._present_recovery_options(error_context)
            return True
            
        except Exception as recovery_error:
            self.logger.error(f"エラー回復処理中にエラー: {recovery_error}")
            return False  # エラー回復自体が失敗、元のエラー処理を続行
    
    def _present_recovery_options(self, error_context):
        """回復オプションをユーザーに提示
        
        Args:
            error_context: エラー文脈情報
        """
        try:
            recovery_plan = self.error_recovery.create_recovery_plan(error_context)
            options = self.error_recovery.get_recovery_options(recovery_plan.plan_id)
            
            # ChatLoopに回復オプションを送信
            self.pending_recovery_plan_id = recovery_plan.plan_id
            self.waiting_for_recovery_decision = True
            
            self._send_status(f"ERROR_RECOVERY:{recovery_plan.plan_id}")
            self._send_status(options)
            
        except Exception as e:
            self.logger.error(f"回復オプション提示エラー: {e}")
            self._send_status(f"❌ エラー回復システムで問題が発生しました: {str(e)}")
    
    def process_recovery_decision(self, plan_id: str, decision: str) -> str:
        """ユーザーの回復決定を処理
        
        Args:
            plan_id: 回復計画ID
            decision: ユーザーの決定
            
        Returns:
            str: 処理結果メッセージ
        """
        try:
            decision_lower = decision.lower().strip()
            
            # 特別なコマンド処理
            if decision_lower == "auto":
                # 推奨アクションを自動実行
                plan = self.error_recovery.recovery_plans.get(plan_id)
                if plan:
                    recommended = plan.get_recommended_action()
                    if recommended:
                        success, message = self.error_recovery.execute_recovery_action(
                            plan_id, recommended.action_id
                        )
                        self.waiting_for_recovery_decision = False
                        self.pending_recovery_plan_id = None
                        return f"🤖 自動実行結果: {message}"
                
                return "❌ 推奨アクションが見つかりません"
            
            elif decision_lower == "abort":
                # タスクを中止
                self.waiting_for_recovery_decision = False
                self.pending_recovery_plan_id = None
                return "🛑 タスクを中止しました"
            
            elif decision_lower == "details":
                # エラーの詳細情報を表示
                plan = self.error_recovery.recovery_plans.get(plan_id)
                if plan:
                    error = plan.error_context
                    details = f"""
📊 **エラー詳細情報**

**基本情報:**
- エラーID: {error.error_id}
- 発生時刻: {error.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
- エラー種類: {error.error_type}
- 重要度: {error.severity.value.upper()}

**メッセージ:**
{error.error_message}

**文脈データ:**
{error.context_data}
"""
                    if error.stack_trace:
                        details += f"\n**スタックトレース:**\n```\n{error.stack_trace[:500]}...\n```"
                    
                    return details.strip()
                
                return "❌ エラー詳細が見つかりません"
            
            # 数字の選択肢処理
            elif decision_lower.isdigit():
                choice = int(decision_lower)
                plan = self.error_recovery.recovery_plans.get(plan_id)
                
                if plan and 1 <= choice <= len(plan.actions):
                    action = plan.actions[choice - 1]
                    success, message = self.error_recovery.execute_recovery_action(
                        plan_id, action.action_id
                    )
                    
                    if success:
                        self.waiting_for_recovery_decision = False
                        self.pending_recovery_plan_id = None
                    
                    return f"{'✅' if success else '❌'} 選択 {choice}: {message}"
                else:
                    return f"❌ 無効な選択肢です（1-{len(plan.actions) if plan else 0}の範囲で指定してください）"
            
            else:
                return "❌ 無効なコマンドです。'auto', 'abort', 'details', または数字を入力してください。"
                
        except Exception as e:
            self.logger.error(f"回復決定処理エラー: {e}")
            return f"❌ 回復決定処理中にエラーが発生しました: {str(e)}"
    
    def get_error_summary(self) -> str:
        """エラーサマリーを取得"""
        summary = self.error_recovery.get_error_summary()
        
        summary_text = f"""
📊 **エラーサマリー**

**統計:**
- 総エラー数: {summary['total_errors']}
- 直近1時間のエラー: {summary['recent_errors']}
- アクティブな回復計画: {summary['active_recovery_plans']}

**最近のエラー種類:**
"""
        
        for error_type, count in summary['error_types'].items():
            summary_text += f"- {error_type}: {count}回\n"
        
        summary_text += "\n**重要度別:**\n"
        for severity, count in summary['severities'].items():
            summary_text += f"- {severity.upper()}: {count}回\n"
        
        return summary_text.strip()
    
    # ワークスペース管理メソッド
    def update_workspace(self, new_workspace_path: str):
        """ワークスペースの更新を受信
        
        Args:
            new_workspace_path: 新しいワークスペースのパス
        """
        try:
            # 現在のCompanionCoreの作業ディレクトリを更新
            if hasattr(self.companion, 'set_working_directory'):
                self.companion.set_working_directory(new_workspace_path)
            
            # 階層タスク管理のワークスペースも更新
            if hasattr(self.hierarchical_manager, 'update_workspace'):
                self.hierarchical_manager.update_workspace(new_workspace_path)
            
            # チェックポイント管理の場所も更新
            if hasattr(self.checkpoint_manager, 'update_workspace'):
                self.checkpoint_manager.update_workspace(new_workspace_path)
            
            self.logger.info(f"TaskLoop: ワークスペースを更新しました: {new_workspace_path}")
            
        except Exception as e:
            self.logger.error(f"TaskLoop: ワークスペース更新エラー: {e}")
    
    def get_current_workspace(self) -> str:
        """現在のワークスペースパスを取得
        
        Returns:
            str: 現在のワークスペースパス
        """
        return self.workspace_manager.current_workspace
    
    def get_workspace_info(self) -> Dict[str, Any]:
        """ワークスペース情報を取得
        
        Returns:
            Dict[str, Any]: ワークスペース情報
        """
        try:
            current_info = self.workspace_manager.get_current_workspace()
            recent_workspaces = self.workspace_manager.list_recent_workspaces(5)
            bookmarks = self.workspace_manager.list_bookmarks()
            
            return {
                "current": current_info.to_dict(),
                "recent": [w.to_dict() for w in recent_workspaces],
                "bookmarks": [b.to_dict() for b in bookmarks]
            }
        except Exception as e:
            self.logger.error(f"ワークスペース情報取得エラー: {e}")
            return {
                "current": {"path": self.workspace_manager.current_workspace, "error": str(e)},
                "recent": [],
                "bookmarks": []
            }