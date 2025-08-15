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
        
        # 共有CompanionCoreまたは新規作成
        if shared_companion:
            self.companion = shared_companion
        else:
            from .core import CompanionCore
            self.companion = CompanionCore()
        
        # 共有コンテキスト管理
        self.context_manager = context_manager
        
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
            
            # 意図理解結果を再利用してタスクを実行
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
                    "result": result,
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
            
            # 少し待機（進捗表示のため）
            await asyncio.sleep(0.5)
            
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