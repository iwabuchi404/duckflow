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

from .ui import rich_ui
from .core import CompanionCore
from .workspace_manager import WorkspaceManager


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
        
        # TaskLoop参照（後で設定される）
        self.task_loop = None
        
        # Step 3: 協調的計画の状態管理
        self.pending_plan_id: Optional[str] = None
        self.waiting_for_plan_approval = False
        
        # Step 3: エラー回復の状態管理
        self.pending_recovery_plan_id: Optional[str] = None
        self.waiting_for_recovery_decision = False
        
        # ワークスペース管理
        self.workspace_manager = WorkspaceManager()
        
        # ログ設定
        self.logger = logging.getLogger(__name__)
    
    def set_task_loop(self, task_loop):
        """TaskLoopの参照を設定
        
        Args:
            task_loop: TaskLoopインスタンス
        """
        self.task_loop = task_loop
    
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
                    
                    # Step 3: 協調的計画の承認待ちチェック
                    if self.waiting_for_plan_approval and self.pending_plan_id:
                        await self._handle_plan_feedback(user_input)
                        continue
                    
                    # Step 3: エラー回復の決定待ちチェック
                    if self.waiting_for_recovery_decision and self.pending_recovery_plan_id:
                        await self._handle_recovery_decision(user_input)
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
            rich_ui.print_conversation_message(response, "assistant")
            
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
            rich_ui.print_conversation_message(response, "assistant")
            
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
                
                # Step 3: 協調的計画の処理
                if self._handle_collaborative_planning_status(status):
                    continue
                
                # Step 3: エラー回復の処理
                if self._handle_error_recovery_status(status):
                    continue
                
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
        
        # Step 2: 一時停止・再開コマンド
        elif command in ['pause', '一時停止', 'ポーズ']:
            self._handle_pause_command()
            return True
        
        elif command in ['resume', '再開', '続行']:
            self._handle_resume_command()
            return True
        
        # Step 2: 階層タスク管理コマンド
        elif command in ['hierarchical', '階層', '階層タスク']:
            self._handle_hierarchical_status_command()
            return True
        
        elif command in ['toggle-hierarchical', '階層モード切替']:
            self._handle_toggle_hierarchical_command()
            return True
        
        # Step 3: 協調的計画コマンド
        elif command in ['plan', '計画', '計画表示']:
            self._handle_plan_status_command()
            return True
        
        elif command in ['toggle-planning', '計画モード切替']:
            self._handle_toggle_planning_command()
            return True
        
        # Step 3: エラー回復コマンド
        elif command in ['errors', 'エラー', 'エラーサマリー']:
            self._handle_error_summary_command()
            return True
        
        # ワークスペース管理コマンド
        elif command in ['pwd', '現在', '現在の場所']:
            self._handle_pwd_command()
            return True
        
        elif command.startswith('cd '):
            path = command[3:].strip()
            self._handle_cd_command(path)
            return True
        
        elif command in ['workspaces', 'ワークスペース', 'ワークスペース一覧']:
            self._handle_workspaces_command()
            return True
        
        elif command.startswith('bookmark '):
            args = command[9:].strip().split(' ', 1)
            name = args[0]
            description = args[1] if len(args) > 1 else None
            self._handle_bookmark_add_command(name, description)
            return True
        
        elif command in ['bookmarks', 'ブックマーク', 'ブックマーク一覧']:
            self._handle_bookmarks_command()
            return True
        
        elif command.startswith('goto '):
            bookmark_name = command[5:].strip()
            self._handle_goto_command(bookmark_name)
            return True
        
        elif command in ['back', '戻る']:
            self._handle_back_command()
            return True
        
        elif command.startswith('search '):
            query = command[7:].strip()
            self._handle_search_workspace_command(query)
            return True
        
        elif command.startswith('rm-bookmark '):
            bookmark_name = command[12:].strip()
            self._handle_remove_bookmark_command(bookmark_name)
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
- `pause` または `一時停止` - タスクを一時停止
- `resume` または `再開` - タスクを再開
- `hierarchical` または `階層` - 階層タスクの状態表示
- `toggle-hierarchical` - 階層タスクモードの切替
- `plan` または `計画` - 協調的計画の状態表示
- `toggle-planning` - 協調的計画モードの切替
- `errors` または `エラー` - エラーサマリーの表示

**ワークスペース管理:**
- `pwd` または `現在` - 現在の作業フォルダを表示
- `cd <パス>` - 作業フォルダを変更
- `workspaces` または `ワークスペース` - ワークスペース一覧を表示
- `bookmark <名前> [説明]` - 現在の場所をブックマーク
- `bookmarks` または `ブックマーク` - ブックマーク一覧を表示
- `goto <ブックマーク名>` - ブックマークに移動
- `back` または `戻る` - 前のワークスペースに戻る
- `search <クエリ>` - ワークスペースを検索
- `rm-bookmark <名前>` - ブックマークを削除

**新機能:**
✨ タスク実行中も対話を継続できます
✨ 進捗をいつでも確認できます
✨ 複数のタスクを順次実行できます
✨ 複雑なタスクを階層分割して実行できます
✨ タスクの一時停止・再開が可能です
✨ 協調的計画でタスクを事前に相談できます
✨ 実行計画の承認・修正・却下が可能です
✨ エラー発生時の自動回復と手動対応選択
✨ エラー履歴とパターン分析による予防
✨ 作業フォルダの切り替えと履歴管理
✨ ブックマーク機能でよく使う場所を管理

何でもお気軽にお話しください！
        """
        
        rich_ui.print_panel(help_text.strip(), "Help", "blue")
    
    def stop(self):
        """ChatLoopを停止"""
        self.running = False
        self.logger.info("ChatLoop を停止しました")
    
    # Step 2: 一時停止・再開コマンドハンドラー
    def _handle_pause_command(self):
        """一時停止コマンドを処理"""
        if self.task_loop and hasattr(self.task_loop, 'pause'):
            self.task_loop.pause()
        else:
            rich_ui.print_message("⚠️ タスク実行システムが利用できません", "warning")
    
    def _handle_resume_command(self):
        """再開コマンドを処理"""
        if self.task_loop and hasattr(self.task_loop, 'resume'):
            self.task_loop.resume()
        else:
            rich_ui.print_message("⚠️ タスク実行システムが利用できません", "warning")
    
    def _handle_hierarchical_status_command(self):
        """階層タスク状態表示コマンドを処理"""
        if self.task_loop and hasattr(self.task_loop, 'show_hierarchical_status'):
            self.task_loop.show_hierarchical_status()
        else:
            rich_ui.print_message("⚠️ 階層タスク機能が利用できません", "warning")
    
    def _handle_toggle_hierarchical_command(self):
        """階層タスクモード切替コマンドを処理"""
        if self.task_loop and hasattr(self.task_loop, 'toggle_hierarchical_mode'):
            new_mode = self.task_loop.toggle_hierarchical_mode()
            status = "有効" if new_mode else "無効"
            rich_ui.print_message(f"🌳 階層タスクモードが{status}になりました", "success")
        else:
            rich_ui.print_message("⚠️ 階層タスク機能が利用できません", "warning")
    
    def _handle_collaborative_planning_status(self, status: str) -> bool:
        """協調的計画の状態メッセージを処理
        
        Args:
            status: TaskLoopからのステータスメッセージ
            
        Returns:
            bool: 協調的計画メッセージを処理した場合True
        """
        if status.startswith("PLAN_PROPOSAL:"):
            # 計画提案の開始
            plan_id = status.split(":", 1)[1]
            self.pending_plan_id = plan_id
            self.waiting_for_plan_approval = True
            rich_ui.print_message("📋 実行計画が提案されました", "info")
            return True
        
        elif self.waiting_for_plan_approval:
            # 計画提案の詳細表示
            rich_ui.print_panel(status, "実行計画の提案", "blue")
            return True
        
        return False
    
    async def _handle_plan_feedback(self, feedback: str):
        """計画に対するフィードバックを処理
        
        Args:
            feedback: ユーザーのフィードバック
        """
        try:
            if self.task_loop and hasattr(self.task_loop, 'process_plan_feedback'):
                response = self.task_loop.process_plan_feedback(self.pending_plan_id, feedback)
                rich_ui.print_message(response, "info")
                
                # フィードバック処理後は承認待ち状態を解除
                if any(word in feedback.lower() for word in ['承認', 'approve', '拒否', 'reject']):
                    self.waiting_for_plan_approval = False
                    self.pending_plan_id = None
            else:
                rich_ui.print_message("⚠️ 計画フィードバック機能が利用できません", "warning")
                
        except Exception as e:
            self.logger.error(f"計画フィードバック処理エラー: {e}")
            rich_ui.print_error(f"フィードバック処理に失敗しました: {e}")
    
    def _handle_plan_status_command(self):
        """計画状態表示コマンドを処理"""
        if self.task_loop and hasattr(self.task_loop, 'show_current_plan'):
            self.task_loop.show_current_plan()
        else:
            rich_ui.print_message("⚠️ 協調的計画機能が利用できません", "warning")
    
    def _handle_toggle_planning_command(self):
        """協調的計画モード切替コマンドを処理"""
        if self.task_loop and hasattr(self.task_loop, 'toggle_collaborative_planning'):
            new_mode = self.task_loop.toggle_collaborative_planning()
            status = "有効" if new_mode else "無効"
            rich_ui.print_message(f"📋 協調的計画モードが{status}になりました", "success")
        else:
            rich_ui.print_message("⚠️ 協調的計画機能が利用できません", "warning")
    
    def _handle_error_recovery_status(self, status: str) -> bool:
        """エラー回復の状態メッセージを処理
        
        Args:
            status: TaskLoopからのステータスメッセージ
            
        Returns:
            bool: エラー回復メッセージを処理した場合True
        """
        if status.startswith("ERROR_RECOVERY:"):
            # エラー回復の開始
            plan_id = status.split(":", 1)[1]
            self.pending_recovery_plan_id = plan_id
            self.waiting_for_recovery_decision = True
            rich_ui.print_message("🚨 エラーが発生しました。回復オプションを確認中...", "warning")
            return True
        
        elif self.waiting_for_recovery_decision:
            # エラー回復オプションの詳細表示
            rich_ui.print_panel(status, "エラー回復オプション", "red")
            return True
        
        return False
    
    async def _handle_recovery_decision(self, decision: str):
        """エラー回復決定を処理
        
        Args:
            decision: ユーザーの決定
        """
        try:
            if self.task_loop and hasattr(self.task_loop, 'process_recovery_decision'):
                response = self.task_loop.process_recovery_decision(
                    self.pending_recovery_plan_id, decision
                )
                rich_ui.print_message(response, "info")
                
                # 回復決定処理後は状態を更新
                if any(word in decision.lower() for word in ['auto', 'abort'] + [str(i) for i in range(1, 10)]):
                    self.waiting_for_recovery_decision = False
                    self.pending_recovery_plan_id = None
            else:
                rich_ui.print_message("⚠️ エラー回復機能が利用できません", "warning")
                
        except Exception as e:
            self.logger.error(f"エラー回復決定処理エラー: {e}")
            rich_ui.print_error(f"回復決定処理に失敗しました: {e}")
    
    def _handle_error_summary_command(self):
        """エラーサマリー表示コマンドを処理"""
        if self.task_loop and hasattr(self.task_loop, 'get_error_summary'):
            summary = self.task_loop.get_error_summary()
            rich_ui.print_panel(summary, "エラーサマリー", "yellow")
        else:
            rich_ui.print_message("⚠️ エラー回復機能が利用できません", "warning")
    
    # ワークスペース管理コマンドハンドラー
    def _handle_pwd_command(self):
        """現在のワークスペース表示コマンドを処理"""
        try:
            info_display = self.workspace_manager.get_workspace_info_display()
            rich_ui.print_panel(info_display, "現在のワークスペース", "green")
        except Exception as e:
            rich_ui.print_error(f"ワークスペース情報の取得に失敗しました: {e}")
    
    def _handle_cd_command(self, path: str):
        """作業フォルダ変更コマンドを処理"""
        try:
            # パスの候補を提案
            if not path:
                rich_ui.print_message("❌ パスを指定してください", "error")
                return
            
            success, message = self.workspace_manager.change_workspace(path)
            
            if success:
                rich_ui.print_message(message, "success")
                # TaskLoopにも通知
                if self.task_loop and hasattr(self.task_loop, 'update_workspace'):
                    self.task_loop.update_workspace(self.workspace_manager.current_workspace)
            else:
                rich_ui.print_message(message, "error")
                
                # 候補を提案
                suggestions = self.workspace_manager.suggest_similar_paths(path)
                if suggestions:
                    rich_ui.print_message("💡 候補:", "info")
                    for suggestion in suggestions[:5]:
                        rich_ui.print_message(f"  📁 {suggestion}", "muted")
                        
        except Exception as e:
            rich_ui.print_error(f"フォルダ変更に失敗しました: {e}")
    
    def _handle_workspaces_command(self):
        """ワークスペース一覧表示コマンドを処理"""
        try:
            list_display = self.workspace_manager.get_workspace_list_display()
            rich_ui.print_panel(list_display, "ワークスペース一覧", "blue")
        except Exception as e:
            rich_ui.print_error(f"ワークスペース一覧の取得に失敗しました: {e}")
    
    def _handle_bookmark_add_command(self, name: str, description: Optional[str] = None):
        """ブックマーク追加コマンドを処理"""
        try:
            success, message = self.workspace_manager.add_bookmark(name, description=description)
            
            if success:
                rich_ui.print_message(message, "success")
            else:
                rich_ui.print_message(message, "error")
                
        except Exception as e:
            rich_ui.print_error(f"ブックマーク追加に失敗しました: {e}")
    
    def _handle_bookmarks_command(self):
        """ブックマーク一覧表示コマンドを処理"""
        try:
            bookmarks = self.workspace_manager.list_bookmarks()
            
            if not bookmarks:
                rich_ui.print_message("📌 ブックマークはありません", "info")
                return
            
            display = "📌 **ブックマーク一覧**\n\n"
            for bookmark in bookmarks:
                project_info = f" ({bookmark.project_type})" if bookmark.project_type else ""
                display += f"• **{bookmark.name}**{project_info}\n"
                display += f"  📁 {bookmark.path}\n"
                if bookmark.description:
                    display += f"  💬 {bookmark.description}\n"
                display += f"  🕐 {bookmark.last_accessed.strftime('%m-%d %H:%M')}\n\n"
            
            rich_ui.print_panel(display.strip(), "ブックマーク", "magenta")
        except Exception as e:
            rich_ui.print_error(f"ブックマーク一覧の取得に失敗しました: {e}")
    
    def _handle_goto_command(self, bookmark_name: str):
        """ブックマーク移動コマンドを処理"""
        try:
            success, message = self.workspace_manager.change_to_bookmark(bookmark_name)
            
            if success:
                rich_ui.print_message(message, "success")
                # TaskLoopにも通知
                if self.task_loop and hasattr(self.task_loop, 'update_workspace'):
                    self.task_loop.update_workspace(self.workspace_manager.current_workspace)
            else:
                rich_ui.print_message(message, "error")
                
                # 似た名前のブックマークを提案
                bookmarks = self.workspace_manager.list_bookmarks()
                similar = [b.name for b in bookmarks if bookmark_name.lower() in b.name.lower()]
                if similar:
                    rich_ui.print_message("💡 似た名前のブックマーク:", "info")
                    for name in similar[:3]:
                        rich_ui.print_message(f"  📌 {name}", "muted")
                        
        except Exception as e:
            rich_ui.print_error(f"ブックマーク移動に失敗しました: {e}")
    
    def _handle_back_command(self):
        """前のワークスペースに戻るコマンドを処理"""
        try:
            success, message = self.workspace_manager.go_back()
            
            if success:
                rich_ui.print_message(message, "success")
                # TaskLoopにも通知
                if self.task_loop and hasattr(self.task_loop, 'update_workspace'):
                    self.task_loop.update_workspace(self.workspace_manager.current_workspace)
            else:
                rich_ui.print_message(message, "error")
                
        except Exception as e:
            rich_ui.print_error(f"ワークスペースの復帰に失敗しました: {e}")
    
    def _handle_search_workspace_command(self, query: str):
        """ワークスペース検索コマンドを処理"""
        try:
            results = self.workspace_manager.search_workspaces(query)
            
            if not results:
                rich_ui.print_message(f"🔍 '{query}' にマッチするワークスペースが見つかりません", "info")
                return
            
            display = f"🔍 **検索結果: '{query}'**\n\n"
            for workspace in results[:10]:  # 最大10件表示
                project_info = f" ({workspace.project_type})" if workspace.project_type else ""
                bookmark_mark = "📌" if workspace.is_bookmark else "📁"
                display += f"{bookmark_mark} **{workspace.name}**{project_info}\n"
                display += f"  📁 {workspace.path}\n"
                if workspace.description:
                    display += f"  💬 {workspace.description}\n"
                display += f"  🕐 {workspace.last_accessed.strftime('%m-%d %H:%M')}\n\n"
            
            rich_ui.print_panel(display.strip(), "検索結果", "cyan")
        except Exception as e:
            rich_ui.print_error(f"ワークスペース検索に失敗しました: {e}")
    
    def _handle_remove_bookmark_command(self, bookmark_name: str):
        """ブックマーク削除コマンドを処理"""
        try:
            success, message = self.workspace_manager.remove_bookmark(bookmark_name)
            
            if success:
                rich_ui.print_message(message, "success")
            else:
                rich_ui.print_message(message, "error")
                
        except Exception as e:
            rich_ui.print_error(f"ブックマーク削除に失敗しました: {e}")