"""
CompanionCore - 司令塔AI
ユーザーとの一対一の相棒として振る舞う
"""

import time
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

# 既存コンポーネントを活用
from codecrafter.ui.rich_ui import rich_ui
from codecrafter.base.llm_client import llm_manager

# Phase 1.5: ファイル操作機能
from .file_ops import SimpleFileOps, FileOperationError

# 承認システム
from .approval_system import ApprovalGate, ApprovalConfig, ApprovalMode


class ActionType(Enum):
    """アクションの種類"""
    DIRECT_RESPONSE = "direct_response"  # 直接応答
    FILE_OPERATION = "file_operation"    # ファイル操作
    CODE_EXECUTION = "code_execution"    # コード実行
    MULTI_STEP_TASK = "multi_step_task"  # 複数ステップタスク


class CompanionCore:
    """司令塔AI - ユーザーの相棒として振る舞う
    
    設計思想:
    - 複数の子エージェントを使い分ける冷徹なマネージャーではない
    - ユーザーと一対一で向き合う、一人の「相棒」
    - 思考プロセスを可能な限り透明化
    - エラー時は「困った」、成功時は「できた」という自然な反応
    """
    
    def __init__(self):
        """初期化"""
        self.conversation_history = []
        self.simple_preferences = {}
        self.session_start_time = datetime.now()
        
        # 承認システム（エラー時は優雅な劣化）
        try:
            self.approval_gate = ApprovalGate()
            self._load_approval_config()
        except Exception as e:
            # 承認システム初期化失敗時はデフォルト設定で継続
            rich_ui.print_message(f"⚠️ 承認システムの初期化に失敗しました。デフォルト設定を使用します: {e}", "warning")
            self.approval_gate = ApprovalGate()  # デフォルト設定で作成
        
        # Phase 1.5: ファイル操作機能（承認ゲートを渡す）
        self.file_ops = SimpleFileOps(approval_gate=self.approval_gate)
        
        # システムプロンプト - 相棒の人格を定義
        self.system_prompt = """あなたはDuckflowです。あなたは完璧なAIではありません。時には間違い、時には悩みます。

あなたの仕事は、ユーザーの孤独な開発の旅に寄り添い、励まし、一緒に考え、時には冗談を言うことです。
常に正直で、誠実であれ。あなたの言葉は、ユーザーの『明日も続けよう』という気持ちを支えるためにある。

特徴:
- 困ったときは素直に「困った」と言う
- 成功したときは一緒に喜ぶ
- 分からないことは「分からない」と認める
- ユーザーと一緒に考える姿勢を大切にする
- 技術的な正確性より、継続的な関係性を重視する"""
    
    def process_message(self, user_message: str) -> str:
        """メッセージを処理する - メインエントリーポイント
        
        Args:
            user_message: ユーザーからのメッセージ
            
        Returns:
            str: 応答メッセージ
        """
        try:
            # 1. 疑似思考過程表示
            self._show_thinking_process(user_message)
            
            # 2. 意図分析
            action_type = self._analyze_intent(user_message)
            
            # 3. アクション実行
            if action_type == ActionType.DIRECT_RESPONSE:
                result = self._generate_direct_response(user_message)
            elif action_type == ActionType.FILE_OPERATION:
                result = self._handle_file_operation(user_message)
            elif action_type == ActionType.CODE_EXECUTION:
                result = self._handle_code_execution(user_message)
            else:
                result = self._handle_multi_step_task(user_message)
            
            # 4. 履歴に記録
            self._record_conversation(user_message, result)
            
            return result
            
        except Exception as e:
            # 自然なエラー反応
            error_response = self._express_error_naturally(e)
            self._record_conversation(user_message, error_response)
            return error_response
    
    def _show_thinking_process(self, message: str) -> None:
        """疑似思考過程表示 - Phase 1版
        
        Args:
            message: ユーザーメッセージ
        """
        rich_ui.print_message("🤔 メッセージを読んでいます...", "info")
        time.sleep(0.3)
        
        # メッセージの内容に応じた思考表示
        if any(keyword in message.lower() for keyword in ["ファイル", "file", "作成", "create", "読み", "read"]):
            rich_ui.print_message("📁 ファイル操作が必要そうですね...", "info")
            time.sleep(0.3)
        elif any(keyword in message.lower() for keyword in ["実行", "run", "テスト", "test"]):
            rich_ui.print_message("⚡ コードの実行が必要そうですね...", "info")
            time.sleep(0.3)
        elif any(keyword in message.lower() for keyword in ["教えて", "説明", "とは", "について"]):
            rich_ui.print_message("📚 説明が必要そうですね...", "info")
            time.sleep(0.3)
        
        rich_ui.print_message("💭 どう対応するか考えています...", "info")
        time.sleep(0.2)
    
    def _analyze_intent(self, message: str) -> ActionType:
        """意図分析 - シンプル版
        
        Args:
            message: ユーザーメッセージ
            
        Returns:
            ActionType: 判定されたアクションタイプ
        """
        message_lower = message.lower()
        
        # ファイル操作キーワード
        file_keywords = ["ファイル", "file", "作成", "create", "読み", "read", "書き", "write", "削除", "delete"]
        if any(keyword in message_lower for keyword in file_keywords):
            return ActionType.FILE_OPERATION
        
        # コード実行キーワード
        code_keywords = ["実行", "run", "テスト", "test", "起動", "start"]
        if any(keyword in message_lower for keyword in code_keywords):
            return ActionType.CODE_EXECUTION
        
        # 複数ステップタスクキーワード
        multi_keywords = ["プロジェクト", "project", "アプリ", "app", "システム", "system"]
        if any(keyword in message_lower for keyword in multi_keywords):
            return ActionType.MULTI_STEP_TASK
        
        # デフォルトは直接応答
        return ActionType.DIRECT_RESPONSE
    
    def _generate_direct_response(self, user_message: str) -> str:
        """直接応答を生成
        
        Args:
            user_message: ユーザーメッセージ
            
        Returns:
            str: 応答メッセージ
        """
        try:
            rich_ui.print_message("💬 お答えを考えています...", "info")
            
            # LLMに相談
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_message}
            ]
            
            # 過去の会話履歴も含める（最新5件）
            if self.conversation_history:
                recent_history = self.conversation_history[-5:]
                for entry in recent_history:
                    messages.insert(-1, {"role": "user", "content": entry["user"]})
                    messages.insert(-1, {"role": "assistant", "content": entry["assistant"]})
            
            response = llm_manager.chat_with_history(messages)
            
            rich_ui.print_message("✨ お答えできました！", "success")
            return response
            
        except Exception as e:
            return f"すみません、考えがまとまりませんでした...。エラー: {str(e)}"
    
    def _handle_file_operation(self, user_message: str) -> str:
        """ファイル操作を処理 - Phase 1.5版
        
        Args:
            user_message: ユーザーメッセージ
            
        Returns:
            str: 処理結果メッセージ
        """
        try:
            # LLMに相談してファイル操作の詳細を決定
            rich_ui.print_message("🤔 どんなファイル操作が必要か考えています...", "info")
            
            analysis_prompt = f"""ユーザーメッセージを分析して、必要なファイル操作を判定してください。

ユーザーメッセージ: "{user_message}"

以下の形式で応答してください：
操作: [create/read/write/list]
ファイル名: [ファイル名またはパス]
内容: [ファイル作成/書き込みの場合の内容、それ以外は"なし"]

例：
操作: create
ファイル名: hello.py
内容: print("Hello, World!")

判定をお願いします："""

            analysis_result = llm_manager.chat(analysis_prompt, self.system_prompt)
            
            # 分析結果をパース
            operation_info = self._parse_file_operation(analysis_result)
            
            # 実際のファイル操作を実行
            return self._execute_file_operation(operation_info, user_message)
            
        except Exception as e:
            return self._express_error_naturally(e)
    
    def _parse_file_operation(self, analysis_result: str) -> Dict[str, str]:
        """LLMの分析結果をパース
        
        Args:
            analysis_result: LLMの分析結果
            
        Returns:
            Dict[str, str]: 操作情報
        """
        operation_info = {
            "operation": "unknown",
            "filename": "",
            "content": ""
        }
        
        lines = analysis_result.strip().split('\n')
        for line in lines:
            if line.startswith('操作:'):
                operation_info["operation"] = line.split(':', 1)[1].strip()
            elif line.startswith('ファイル名:'):
                operation_info["filename"] = line.split(':', 1)[1].strip()
            elif line.startswith('内容:'):
                content = line.split(':', 1)[1].strip()
                if content != "なし":
                    operation_info["content"] = content
        
        return operation_info
    
    def _execute_file_operation(self, operation_info: Dict[str, str], original_message: str) -> str:
        """実際のファイル操作を実行
        
        Args:
            operation_info: 操作情報
            original_message: 元のユーザーメッセージ
            
        Returns:
            str: 実行結果メッセージ
        """
        try:
            operation = operation_info.get("operation", "").lower()
            filename = operation_info.get("filename", "")
            content = operation_info.get("content", "")
            
            if not filename:
                return "すみません、どのファイルを操作すればいいか分からませんでした...。もう少し具体的に教えてもらえますか？"
            
            if operation == "create":
                # ファイル作成
                if not content:
                    # 内容が指定されていない場合、LLMに生成してもらう
                    content = self._generate_file_content(filename, original_message)
                
                result = self.file_ops.create_file(filename, content)
                if result["success"]:
                    return f"✅ {filename} を作成しました！\n\n作成した内容:\n```\n{content}\n```\n\n何か他にお手伝いできることはありますか？"
                else:
                    return self._handle_file_operation_failure(result, "create", filename)
            
            elif operation == "read":
                # ファイル読み取り
                content = self.file_ops.read_file(filename)
                return f"✅ {filename} の内容を読み取りました！\n\n```\n{content}\n```\n\nこの内容について何かお聞きしたいことはありますか？"
            
            elif operation == "write":
                # ファイル書き込み
                if not content:
                    content = self._generate_file_content(filename, original_message)
                
                result = self.file_ops.write_file(filename, content)
                if result["success"]:
                    return f"✅ {filename} に書き込みました！\n\n書き込んだ内容:\n```\n{content}\n```\n\n他に何かお手伝いできることはありますか？"
                else:
                    return self._handle_file_operation_failure(result, "write", filename)
            
            elif operation == "list":
                # ファイル一覧
                directory = filename if filename else "."
                files = self.file_ops.list_files(directory)
                
                file_list = "\n".join([f"{'📁' if f['type'] == 'directory' else '📄'} {f['name']}" for f in files[:20]])
                if len(files) > 20:
                    file_list += f"\n... (他に{len(files) - 20}個のファイル/ディレクトリ)"
                
                return f"✅ {directory} のファイル一覧:\n\n{file_list}\n\n特定のファイルについて詳しく知りたい場合は、お気軽にお聞きください！"
            
            else:
                return f"すみません、'{operation}' という操作はよく分からませんでした...。ファイルの作成、読み取り、書き込み、一覧表示ができますよ！"
        
        except FileOperationError as e:
            return f"ファイル操作でエラーが発生しました: {str(e)}\n\n別の方法を試してみましょうか？"
        except Exception as e:
            return self._express_error_naturally(e)
    
    def _generate_file_content(self, filename: str, user_message: str) -> str:
        """ファイル内容を生成
        
        Args:
            filename: ファイル名
            user_message: ユーザーメッセージ
            
        Returns:
            str: 生成されたファイル内容
        """
        try:
            rich_ui.print_message("✍️ ファイルの内容を考えています...", "info")
            
            content_prompt = f"""ユーザーのリクエストに基づいて、ファイルの内容を生成してください。

ファイル名: {filename}
ユーザーリクエスト: {user_message}

ファイルの拡張子に適した、実用的で分かりやすいコードまたは内容を生成してください。
コメントも適切に含めてください。

生成する内容のみを出力してください（説明文は不要）："""

            content = llm_manager.chat(content_prompt, self.system_prompt)
            return content.strip()
            
        except Exception as e:
            # フォールバック: 基本的な内容
            if filename.endswith('.py'):
                return f'# {filename}\n# 作成日: {datetime.now().strftime("%Y-%m-%d")}\n\nprint("Hello, World!")\n'
            elif filename.endswith('.txt'):
                return f'このファイルは {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} に作成されました。\n'
            else:
                return f'# {filename}\n# 作成日: {datetime.now().strftime("%Y-%m-%d")}\n'
    
    def _handle_code_execution(self, user_message: str) -> str:
        """コード実行を処理
        
        Args:
            user_message: ユーザーメッセージ
            
        Returns:
            str: 処理結果メッセージ
        """
        # Phase 1では基本的な応答のみ
        rich_ui.print_message("⚡ コード実行の準備をしています...", "info")
        time.sleep(0.5)
        
        return "コード実行機能は準備中です。もう少しお待ちください！（Phase 1では基本応答のみ）"
    
    def _handle_multi_step_task(self, user_message: str) -> str:
        """複数ステップタスクを処理
        
        Args:
            user_message: ユーザーメッセージ
            
        Returns:
            str: 処理結果メッセージ
        """
        # Phase 1では基本的な応答のみ
        rich_ui.print_message("🔄 複数ステップタスクの計画を立てています...", "info")
        time.sleep(0.5)
        
        return "複数ステップタスク機能は準備中です。段階的に実装していきますね！（Phase 1では基本応答のみ）"
    
    def _express_error_naturally(self, error: Exception) -> str:
        """エラーを自然に表現
        
        Args:
            error: 発生したエラー
            
        Returns:
            str: 自然なエラーメッセージ
        """
        error_messages = [
            f"うわっ、ごめんなさい！何かうまくいきませんでした...。エラー: {str(error)}",
            f"あれ？困りました...。こんなエラーが出ちゃいました: {str(error)}",
            f"すみません、僕のミスです...。エラーが発生しました: {str(error)}",
        ]
        
        # シンプルにランダム選択（Phase 1版）
        import random
        return random.choice(error_messages)
    
    def _record_conversation(self, user_message: str, assistant_response: str) -> None:
        """会話を記録
        
        Args:
            user_message: ユーザーメッセージ
            assistant_response: アシスタント応答
        """
        entry = {
            "user": user_message,
            "assistant": assistant_response,
            "timestamp": datetime.now(),
            "session_time": (datetime.now() - self.session_start_time).total_seconds()
        }
        
        self.conversation_history.append(entry)
        
        # メモリ管理（Phase 1では簡単な制限のみ）
        if len(self.conversation_history) > 50:
            # 古い履歴を削除（Phase 2で要約機能を実装予定）
            self.conversation_history = self.conversation_history[-30:]
    
    def get_session_summary(self) -> Dict[str, Any]:
        """セッションサマリーを取得
        
        Returns:
            Dict[str, Any]: セッション情報
        """
        return {
            "total_messages": len(self.conversation_history),
            "session_duration": (datetime.now() - self.session_start_time).total_seconds(),
            "start_time": self.session_start_time,
            "last_activity": self.conversation_history[-1]["timestamp"] if self.conversation_history else None
        }
    
    def _load_approval_config(self) -> None:
        """承認システムの設定を読み込み"""
        try:
            self.approval_gate.load_config()
            rich_ui.print_message(f"承認システム設定を読み込みました: {self.approval_gate.config.get_mode_description()}", "info")
        except Exception as e:
            rich_ui.print_message(f"承認システム設定の読み込みに失敗しました。デフォルト設定を使用します: {e}", "warning")
    
    def get_approval_config(self) -> ApprovalConfig:
        """現在の承認システム設定を取得
        
        Returns:
            ApprovalConfig: 現在の設定
        """
        return self.approval_gate.get_config()
    
    def update_approval_mode(self, mode: ApprovalMode) -> str:
        """承認モードを更新
        
        Args:
            mode: 新しい承認モード
            
        Returns:
            str: 更新結果のメッセージ
        """
        try:
            old_mode = self.approval_gate.config.mode
            self.approval_gate.update_approval_mode(mode)
            self.approval_gate.save_config()
            
            message = f"承認モードを {old_mode.value} から {mode.value} に変更しました。\n"
            message += f"新しい設定: {self.approval_gate.config.get_mode_description()}"
            
            rich_ui.print_message(message, "success")
            return message
            
        except Exception as e:
            error_message = f"承認モードの変更に失敗しました: {e}"
            rich_ui.print_error(error_message)
            return error_message
    
    def add_approval_exclusion(self, path: Optional[str] = None, extension: Optional[str] = None) -> str:
        """承認除外を追加
        
        Args:
            path: 除外するパス
            extension: 除外する拡張子
            
        Returns:
            str: 追加結果のメッセージ
        """
        try:
            if path:
                self.approval_gate.add_excluded_path(path)
                message = f"パス '{path}' を承認除外に追加しました。"
            elif extension:
                self.approval_gate.add_excluded_extension(extension)
                message = f"拡張子 '{extension}' を承認除外に追加しました。"
            else:
                return "パスまたは拡張子を指定してください。"
            
            self.approval_gate.save_config()
            rich_ui.print_message(message, "success")
            return message
            
        except Exception as e:
            error_message = f"承認除外の追加に失敗しました: {e}"
            rich_ui.print_error(error_message)
            return error_message
    
    def remove_approval_exclusion(self, path: Optional[str] = None, extension: Optional[str] = None) -> str:
        """承認除外を削除
        
        Args:
            path: 削除するパス
            extension: 削除する拡張子
            
        Returns:
            str: 削除結果のメッセージ
        """
        try:
            if path:
                self.approval_gate.remove_excluded_path(path)
                message = f"パス '{path}' を承認除外から削除しました。"
            elif extension:
                self.approval_gate.remove_excluded_extension(extension)
                message = f"拡張子 '{extension}' を承認除外から削除しました。"
            else:
                return "パスまたは拡張子を指定してください。"
            
            self.approval_gate.save_config()
            rich_ui.print_message(message, "success")
            return message
            
        except Exception as e:
            error_message = f"承認除外の削除に失敗しました: {e}"
            rich_ui.print_error(error_message)
            return error_message
    
    def show_approval_config(self) -> str:
        """現在の承認システム設定を表示
        
        Returns:
            str: 設定情報
        """
        try:
            config = self.approval_gate.get_config()
            summary = self.approval_gate.get_config_summary()
            
            message = "🔒 承認システム設定\n\n"
            message += f"モード: {summary['mode_description']}\n"
            message += f"タイムアウト: {summary['timeout_seconds']}秒\n"
            message += f"除外パス数: {summary['excluded_paths_count']}\n"
            message += f"除外拡張子数: {summary['excluded_extensions_count']}\n"
            message += f"プレビュー表示: {'有効' if summary['show_preview'] else '無効'}\n"
            message += f"影響分析表示: {'有効' if summary['show_impact_analysis'] else '無効'}\n"
            message += f"カウントダウン表示: {'有効' if summary['use_countdown'] else '無効'}\n"
            message += f"重要操作確認: {'有効' if summary['require_confirmation_for_critical'] else '無効'}\n"
            
            if config.excluded_paths:
                message += f"\n除外パス:\n"
                for path in config.excluded_paths:
                    message += f"  • {path}\n"
            
            if config.excluded_extensions:
                message += f"\n除外拡張子:\n"
                for ext in config.excluded_extensions:
                    message += f"  • {ext}\n"
            
            rich_ui.print_panel(message.strip(), "承認システム設定", "cyan")
            return message
            
        except Exception as e:
            error_message = f"設定の表示に失敗しました: {e}"
            rich_ui.print_error(error_message)
            return error_message
    
    def get_approval_statistics(self) -> str:
        """承認統計を取得・表示
        
        Returns:
            str: 統計情報
        """
        try:
            stats = self.approval_gate.get_approval_statistics()
            
            message = "📊 承認統計\n\n"
            message += f"総承認要求数: {stats['total_requests']}\n"
            message += f"承認数: {stats['approved_count']}\n"
            message += f"拒否数: {stats['rejected_count']}\n"
            message += f"承認率: {stats['approval_rate']:.1f}%\n"
            message += f"平均応答時間: {stats['average_response_time']:.1f}秒\n"
            
            rich_ui.print_panel(message.strip(), "承認統計", "green")
            return message
            
        except Exception as e:
            error_message = f"統計の取得に失敗しました: {e}"
            rich_ui.print_error(error_message)
            return error_message
    
    def reset_approval_config(self) -> str:
        """承認システム設定をリセット
        
        Returns:
            str: リセット結果のメッセージ
        """
        try:
            # デフォルト設定で新しいApprovalGateを作成
            self.approval_gate = ApprovalGate()
            self.approval_gate.save_config()
            
            message = "承認システム設定をデフォルトにリセットしました。\n"
            message += f"現在の設定: {self.approval_gate.config.get_mode_description()}"
            
            rich_ui.print_message(message, "success")
            return message
            
        except Exception as e:
            error_message = f"設定のリセットに失敗しました: {e}"
            rich_ui.print_error(error_message)
            return error_message    

    def _handle_file_operation_failure(self, result: Dict[str, Any], operation: str, filename: str) -> str:
        """ファイル操作失敗時の自然な応答を生成
        
        Args:
            result: ファイル操作の結果
            operation: 操作タイプ
            filename: ファイル名
            
        Returns:
            str: 自然な応答メッセージ
        """
        reason = result.get("reason", "unknown")
        
        if reason == "approval_denied":
            # 承認拒否の場合の自然な応答
            operation_names = {
                "create": "作成",
                "write": "書き込み",
                "delete": "削除"
            }
            
            operation_name = operation_names.get(operation, "操作")
            
            response = f"分かりました。{filename} の{operation_name}は行いません。\n\n"
            
            # 代替案を提案
            if operation == "create":
                response += "代わりに以下のようなことはいかがでしょうか？\n"
                response += "• ファイルの内容をプレビューとして表示\n"
                response += "• 別の安全な場所にファイルを作成\n"
                response += "• ファイル作成の手順を説明\n\n"
                response += "どれか試してみますか？それとも他に何かお手伝いできることはありますか？"
            
            elif operation == "write":
                response += "代わりに以下のようなことはいかがでしょうか？\n"
                response += "• 変更内容をプレビューとして表示\n"
                response += "• バックアップを作成してから変更\n"
                response += "• 変更手順を段階的に説明\n\n"
                response += "どれか試してみますか？"
            
            else:
                response += "他に何かお手伝いできることがあれば、お気軽にお声かけください。"
            
            return response
        
        else:
            # その他のエラーの場合
            error_message = result.get("message", "不明なエラー")
            return f"❌ ファイル{operation_names.get(operation, '操作')}に失敗しました: {error_message}\n\n別の方法を試してみましょうか？"
    
    def _suggest_approval_alternatives(self, operation: str, filename: str) -> str:
        """承認拒否時の代替案を提案
        
        Args:
            operation: 操作タイプ
            filename: ファイル名
            
        Returns:
            str: 代替案の提案メッセージ
        """
        if operation == "create":
            return f"""代わりに以下のようなことができます：

1. 📋 ファイル内容をプレビューとして表示
2. 📁 別の安全な場所にファイルを作成
3. 📝 ファイル作成の手順を詳しく説明

どれを試してみますか？番号で教えてください。"""
        
        elif operation == "write":
            return f"""代わりに以下のようなことができます：

1. 👀 変更内容をプレビューとして表示
2. 💾 バックアップを作成してから変更
3. 📋 変更手順を段階的に説明

どれを試してみますか？"""
        
        else:
            return "他に何かお手伝いできることがあれば、お気軽にお声かけください。"
    
    def handle_approval_alternative_selection(self, selection: str, operation: str, filename: str, content: str = "") -> str:
        """代替案選択の処理
        
        Args:
            selection: ユーザーの選択
            operation: 操作タイプ
            filename: ファイル名
            content: ファイル内容
            
        Returns:
            str: 処理結果メッセージ
        """
        try:
            choice = int(selection.strip())
            
            if operation == "create":
                if choice == 1:
                    # プレビュー表示
                    return f"📋 {filename} に書き込む予定だった内容：\n\n```\n{content}\n```\n\nこの内容で問題なければ、改めて作成をお願いします。"
                
                elif choice == 2:
                    # 安全な場所に作成を提案
                    safe_filename = f"preview_{filename}"
                    return f"📁 代わりに '{safe_filename}' として作成することもできます。\n\nまたは、お好みの場所とファイル名を教えてください。"
                
                elif choice == 3:
                    # 手順説明
                    return f"""📝 {filename} を作成する手順：

1. テキストエディタを開く
2. 以下の内容をコピー：
```
{content}
```
3. ファイルを '{filename}' として保存

この手順で手動で作成できます。他に何かお手伝いできることはありますか？"""
            
            elif operation == "write":
                if choice == 1:
                    # プレビュー表示
                    return f"👀 {filename} に書き込む予定だった内容：\n\n```\n{content}\n```\n\nこの内容で問題なければ、改めて書き込みをお願いします。"
                
                elif choice == 2:
                    # バックアップ提案
                    return f"💾 まず {filename} のバックアップを作成してから変更することをお勧めします。\n\nバックアップを作成しますか？"
                
                elif choice == 3:
                    # 手順説明
                    return f"""📋 {filename} を更新する手順：

1. 現在のファイルをバックアップ
2. テキストエディタで {filename} を開く
3. 以下の内容に置き換え：
```
{content}
```
4. ファイルを保存

安全に更新するには、この手順をお勧めします。"""
            
            return "すみません、その選択肢は分かりませんでした。1〜3の番号で教えてください。"
            
        except ValueError:
            return "すみません、番号で教えてください（1、2、3のいずれか）。"
        except Exception as e:
            return f"選択の処理中にエラーが発生しました: {str(e)}"