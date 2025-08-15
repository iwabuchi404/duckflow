"""
Chat Loop - 対話ループ
ユーザーとの継続的な対話を管理
"""

import queue
import asyncio
import logging
import threading
import concurrent.futures
from typing import Optional, Dict, Any
from datetime import datetime

from codecrafter.ui.rich_ui import rich_ui
from .core import CompanionCore


class ChatLoop:
    """対話ループ - ユーザーとの継続的な対話を管理"""
    
    def __init__(self, task_queue: queue.Queue, status_queue: queue.Queue, shared_companion=None, context_manager=None):
        """ChatLoopを初期化
        
        Args:
            task_queue: タスクをTaskLoopに送信するキュー
            status_queue: TaskLoopからの状態を受信するキュー
            shared_companion: 共有のCompanionCoreインスタンス（オプション）
            context_manager: 共有コンテキスト管理（オプション）
        """
        self.task_queue = task_queue
        self.status_queue = status_queue
        self.running = False
        
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
        """メインの対話ループを実行"""
        self.running = True
        self.logger.info("ChatLoop を開始しました")
        
        # ウェルカムメッセージ
        rich_ui.print_message("🦆 Duckflow Dual-Loop System v1.0", "success")
        rich_ui.print_message("タスク実行中も対話を継続できます！", "info")
        
        # 非同期でメインループを実行
        asyncio.run(self._async_main_loop())
    
    async def _async_main_loop(self):
        """非同期メインループ"""
        import threading
        import time
        
        # 状態チェック用のタスクを開始
        status_task = asyncio.create_task(self._periodic_status_check())
        
        try:
            while self.running:
                try:
                    # ユーザー入力を取得（非ブロッキング）
                    user_input = await self._get_user_input_async()
                    
                    if not user_input:
                        continue
                    
                    # 特別なコマンドをチェック
                    if self._handle_special_commands(user_input):
                        continue
                    
                    # Step 1改善: 統一意図理解を実行
                    await self._handle_user_input_unified(user_input)
                    
                except KeyboardInterrupt:
                    self.logger.info("ChatLoop: ユーザーによる中断")
                    break
                except Exception as e:
                    self.logger.error(f"ChatLoop エラー: {e}")
                    rich_ui.print_error(f"エラーが発生しました: {e}")
        finally:
            status_task.cancel()
    
    async def _periodic_status_check(self):
        """定期的な状態チェック"""
        while self.running:
            try:
                self._check_task_status()
                await asyncio.sleep(0.1)  # 100ms間隔でチェック
            except Exception as e:
                self.logger.error(f"定期状態チェックエラー: {e}")
                await asyncio.sleep(1.0)
    
    async def _get_user_input_async(self):
        """非同期でユーザー入力を取得"""
        import concurrent.futures
        
        # 別スレッドでユーザー入力を取得
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(rich_ui.get_user_input, "あなた")
            
            # 入力を待機（定期的に状態をチェック）
            while not future.done():
                await asyncio.sleep(0.1)
            
            return future.result().strip()
    
    async def _handle_user_input_unified(self, user_input: str):
        """統一意図理解による入力処理（Step 1改善）"""
        try:
            # 1. 統一意図理解を実行（1回のみ）
            intent_result = await self.companion.analyze_intent_only(user_input)
            
            # 2. ActionTypeに基づく処理分岐
            action_type = intent_result["action_type"]
            
            if action_type.value == "direct_response":
                # ChatLoop内で直接処理
                await self._handle_direct_response(intent_result)
            else:
                # TaskLoopに送信（意図理解結果も含む）
                await self._handle_task_with_intent(intent_result)
                
        except Exception as e:
            self.logger.error(f"統一意図理解エラー: {e}")
            rich_ui.print_error(f"入力処理に失敗しました: {e}")
    
    async def _handle_direct_response(self, intent_result: Dict[str, Any]):
        """直接応答を処理"""
        try:
            # CompanionCoreで直接応答を生成
            response = await self.companion.process_with_intent_result(intent_result)
            rich_ui.print_conversation_message("Duckflow", response)
            
            # コンテキスト更新
            if self.context_manager:
                self.context_manager.update_context("last_response", {
                    "type": "direct_response",
                    "content": response,
                    "timestamp": datetime.now()
                })
                
        except Exception as e:
            self.logger.error(f"直接応答処理エラー: {e}")
            rich_ui.print_error(f"応答の生成に失敗しました: {e}")
    
    async def _handle_task_with_intent(self, intent_result: Dict[str, Any]):
        """タスクを意図理解結果と共に送信"""
        try:
            # TaskLoopにタスクを送信（意図理解結果も含む）
            task_data = {
                "type": "task_with_intent",
                "intent_result": intent_result,
                "timestamp": datetime.now()
            }
            
            self.task_queue.put(task_data)
            rich_ui.print_message("🚀 タスクを開始しました", "success")
            rich_ui.print_message("実行中も対話を続けられます。進捗は「状況」で確認できます。", "info")
            
            # コンテキスト更新
            if self.context_manager:
                self.context_manager.update_context("last_task", {
                    "type": "task_started",
                    "action_type": intent_result["action_type"].value,
                    "message": intent_result["message"],
                    "timestamp": datetime.now()
                })
                
        except Exception as e:
            self.logger.error(f"タスク送信エラー: {e}")
            rich_ui.print_error(f"タスクの開始に失敗しました: {e}")
    
    async def _handle_conversation_async(self, user_input: str):
        """非同期で通常の対話を処理（レガシー用）"""
        try:
            # 既存のCompanionCoreを使用（非同期対応）
            response = await self.companion.process_message(user_input)
            rich_ui.print_conversation_message("Duckflow", response)
            
        except Exception as e:
            self.logger.error(f"対話処理エラー: {e}")
            rich_ui.print_error(f"応答の生成に失敗しました: {e}")
    
    def _check_task_status(self):
        """TaskLoopからの状態更新をチェック"""
        try:
            status_count = 0
            while True:
                status = self.status_queue.get_nowait()
                self.logger.info(f"状態受信: {status[:100]}...")
                rich_ui.print_message(f"📋 タスク状況: {status}", "info")
                status_count += 1
                
                # 大量の状態更新を防ぐ
                if status_count > 10:
                    rich_ui.print_message("📋 （さらに状態更新があります...）", "muted")
                    break
                    
        except queue.Empty:
            pass  # 新しい状態がない場合は何もしない
    
    def _is_task_request(self, user_input: str) -> bool:
        """ユーザー入力がタスク要求かどうか判定"""
        # シンプルなキーワードベース判定
        task_keywords = [
            "ファイル", "file", "作成", "create", "読み", "read", 
            "書き", "write", "削除", "delete", "実行", "run",
            "分析", "analyze", "レビュー", "review", "確認", "check"
        ]
        
        user_lower = user_input.lower()
        return any(keyword in user_lower for keyword in task_keywords)
    
    def _handle_task_request(self, user_input: str):
        """タスク要求を処理"""
        try:
            # TaskLoopにタスクを送信
            self.task_queue.put(user_input)
            rich_ui.print_message("🚀 タスクを開始しました", "success")
            rich_ui.print_message("実行中も対話を続けられます。進捗は「状況」で確認できます。", "info")
            
        except Exception as e:
            self.logger.error(f"タスク送信エラー: {e}")
            rich_ui.print_error(f"タスクの開始に失敗しました: {e}")
    

    
    def _handle_special_commands(self, user_input: str) -> bool:
        """特別なコマンドを処理
        
        Returns:
            bool: 特別なコマンドを処理した場合True
        """
        command = user_input.lower().strip()
        
        if command in ['quit', 'exit', 'q', 'bye', '終了']:
            rich_ui.print_message("👋 お疲れさまでした！", "success")
            self.running = False
            return True
        
        elif command in ['status', '状況', '進捗']:
            self._show_task_status()
            return True
        
        elif command in ['help', 'h', 'ヘルプ']:
            self._show_help()
            return True
        
        return False
    
    def _show_task_status(self):
        """現在のタスク状況を表示"""
        try:
            # キューの状況を確認
            task_queue_size = self.task_queue.qsize()
            
            if task_queue_size > 0:
                rich_ui.print_message(f"📋 待機中のタスク: {task_queue_size}個", "info")
            else:
                rich_ui.print_message("📋 現在実行中のタスクはありません", "info")
            
            # 最新の状態を確認
            self._check_task_status()
            
        except Exception as e:
            rich_ui.print_error(f"状況確認エラー: {e}")
    
    def _show_help(self):
        """ヘルプを表示"""
        help_text = """
🦆 **Dual-Loop System ヘルプ**

**基本的な使い方:**
- 普通に話しかけてください（通常の対話）
- ファイル操作などのタスクも依頼できます

**特別なコマンド:**
- `status` または `状況` - タスクの進捗確認
- `help` - このヘルプを表示
- `quit` または `終了` - システム終了

**新機能:**
✨ タスク実行中も対話を継続できます
✨ 進捗をいつでも確認できます
✨ 複数のタスクを順次実行できます

何でもお気軽にお話しください！
        """
        
        rich_ui.print_panel(help_text.strip(), "Help", "blue")
    
    def stop(self):
        """ChatLoopを停止"""
        self.running = False
        self.logger.info("ChatLoop を停止しました")