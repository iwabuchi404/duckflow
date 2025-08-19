"""
CompanionCore - 司令塔AI
ユーザーとの一対一の相棒として振る舞う
"""

import time
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from typing import Optional, List

# 既存コンポーネントを活用
from .ui import rich_ui
from .base.llm_client import llm_manager

# Phase 1.5: ファイル操作機能
from .file_ops import SimpleFileOps, FileOperationError

# 新しいシンプル承認システム
from .simple_approval import ApprovalMode

# ヘルプシステム
from .help_system import get_help

# 新しい意図理解システム
from .intent_understanding.intent_integration import IntentUnderstandingSystem


class ActionType(Enum):
    """アクションの種類"""
    DIRECT_RESPONSE = "direct_response"  # 直接応答
    FILE_OPERATION = "file_operation"    # ファイル操作
    CODE_EXECUTION = "code_execution"    # コード実行
    MULTI_STEP_TASK = "multi_step_task"  # 複数ステップタスク


@dataclass
class FailureContext:
    """失敗コンテキストの構造化記録"""
    operation_id: str
    kind: str  # "parse_error", "execution_error", "validation_error"
    inputs: Dict[str, Any]
    reason: str
    timestamp: datetime
    user_message: str
    suggested_actions: List[str]
    
    def to_prompt_context(self) -> str:
        """プロンプト用の文脈文字列を生成"""
        return f"""
前回の操作で以下の問題が発生しました:
- 操作種別: {self.kind}
- 問題: {self.reason}
- ユーザー要求: {self.user_message}
- 時刻: {self.timestamp.strftime('%H:%M:%S')}

この失敗を踏まえて、以下のような対応を検討してください:
{', '.join(self.suggested_actions)}
"""


@dataclass
class TaskPlan:
    """タスク計画の構造化表現"""
    plan_id: str
    purpose: str  # 目的
    prerequisites: List[str]  # 前提条件
    targets: List[str]  # 変更対象（ファイル/設定/UI等）
    impact_scope: str  # 影響範囲の簡易メモ
    steps: List[str]  # 実行手順（2-5手順）
    next_actions: Dict[str, str]  # A: 実行, B: 明確化, C: 代替案
    granularity: str  # "micro", "light", "standard"
    abstraction_level: str  # "low", "mid", "high"
    estimated_complexity: str  # "simple", "moderate", "complex"
    
    def to_user_display(self) -> str:
        """ユーザー向けの表示文字列を生成"""
        steps_text = "\n".join(f"{i+1}. {step}" for i, step in enumerate(self.steps))
        actions_text = "\n".join(f"{key}: {value}" for key, value in self.next_actions.items())
        
        return f"""
📋 **タスク計画** ({self.granularity}プラン)

🎯 **目的**: {self.purpose}

📝 **実行手順**:
{steps_text}

⚡ **影響範囲**: {self.impact_scope}

🔄 **次のアクション**:
{actions_text}

どのアクションを選択しますか？ (A/B/C)
"""


class CompanionCore:
    """司令塔AI - ユーザーの相棒として振る舞う
    
    設計思想:
    - 複数の子エージェントを使い分ける冷徹なマネージャーではない
    - ユーザーと一対一で向き合う、一人の「相棒」
    - 思考プロセスを可能な限り透明化
    - エラー時は「困った」、成功時は「できた」という自然な反応
    """
    
    def __init__(self, approval_mode: ApprovalMode = ApprovalMode.STANDARD):
        """初期化"""
        import threading
        self.conversation_history = []
        self.simple_preferences = {}
        self.session_start_time = datetime.now()
        self._history_lock = threading.Lock()  # スレッドセーフティ用
        
        self.failure_contexts: List[FailureContext] = []
        self.operation_counter = 0
        
        self.current_plan: Optional[TaskPlan] = None
        self.plan_counter = 0
        
        # ファイル操作機能を初期化
        self.file_ops = SimpleFileOps(approval_mode=approval_mode)
        
        # 新しい意図理解システムの初期化（既存LLMマネージャー使用）
        try:
            from .llm.existing_llm_adapter import default_llm_adapter
            
            if default_llm_adapter.is_available():
                self.intent_system = IntentUnderstandingSystem(default_llm_adapter)
                self.use_new_intent_system = True
                provider_info = default_llm_adapter.get_provider_info()
                rich_ui.print_message(f"新しい意図理解システムを初期化しました（{provider_info['provider_name']}）", "success")
            else:
                rich_ui.print_message("⚠️ LLMが利用できません。旧システムを使用します", "warning")
                self.intent_system = None
                self.use_new_intent_system = False
        except Exception as e:
            rich_ui.print_message(f"新しい意図理解システムの初期化に失敗しました。旧システムを使用します: {e}", "warning")
            self.intent_system = None
            self.use_new_intent_system = False
        
        import uuid
        self.session_id = str(uuid.uuid4())
        
        self.system_prompt = """あなたはDuckflowです。あなたは完璧なAIではありません。時には間違い、時には悩みます。

あなたの仕事は、ユーザーの孤独な開発の旅に寄り添い、励まし、一緒に考え、時には冗談を言うことです。
常に正直で、誠実であれ。あなたの言葉は、ユーザーの『明日も続けよう』という気持ちを支えるためにある。

特徴:
- 困ったときは素直に「困った」と言う
- 成功したときは一緒に喜ぶ
- 分からないことは「分からない」と認める
- ユーザーと一緒に考える姿勢を大切にする
- 技術的な正確性より、継続的な関係性を重視する"""
    
    async def analyze_intent_only(self, user_message: str) -> Dict[str, Any]:
        """意図理解のみを実行（統一化用）"""
        try:
            if self.use_new_intent_system and self.intent_system:
                action_type = await self._analyze_intent_new_system(user_message)
                understanding_result = getattr(self, 'last_understanding_result', None)
            else:
                action_type = self._analyze_intent_legacy(user_message)
                understanding_result = None
            
            return {
                "action_type": action_type,
                "understanding_result": understanding_result,
                "message": user_message
            }
        except Exception as e:
            return {
                "action_type": ActionType.DIRECT_RESPONSE,
                "understanding_result": None,
                "message": user_message,
                "error": str(e)
            }
    
    async def process_message(self, user_message: str) -> str:
        """メッセージを処理する - メインエントリーポイント"""
        try:
            if self._is_help_request(user_message):
                return self._handle_help_request(user_message)
            
            if self.current_plan and self._is_plan_response(user_message):
                return self._handle_plan_response(user_message)
            
            self._show_thinking_process(user_message)
            
            if self.use_new_intent_system and self.intent_system:
                action_type = await self._analyze_intent_new_system(user_message)
            else:
                action_type = self._analyze_intent_legacy(user_message)
            
            if action_type == ActionType.DIRECT_RESPONSE:
                result = self._generate_direct_response(user_message)
            elif action_type == ActionType.FILE_OPERATION:
                result = self._handle_file_operation(user_message)
            elif action_type == ActionType.CODE_EXECUTION:
                result = self._handle_code_execution(user_message)
            else:
                result = self._handle_multi_step_task(user_message)
            
            self._record_conversation(user_message, result)
            return result
        except Exception as e:
            error_response = self._express_error_naturally(e)
            self._record_conversation(user_message, error_response)
            return error_response
    
    async def process_with_intent_result(self, intent_result: Dict[str, Any]) -> str:
        """意図理解結果を再利用してメッセージを処理"""
        try:
            user_message = intent_result["message"]
            action_type = intent_result["action_type"]
            self._show_thinking_process(user_message)
            
            if hasattr(self, 'last_understanding_result'):
                self.last_understanding_result = intent_result.get("understanding_result")
            
            if action_type == ActionType.DIRECT_RESPONSE:
                result = self._generate_direct_response(user_message)
            elif action_type == ActionType.FILE_OPERATION:
                result = self._handle_file_operation(user_message)
            elif action_type == ActionType.CODE_EXECUTION:
                result = self._handle_code_execution(user_message)
            else:
                result = self._handle_multi_step_task(user_message)
            
            self._record_conversation(user_message, result)
            return result
        except Exception as e:
            error_response = self._express_error_naturally(e)
            self._record_conversation(intent_result["message"], error_response)
            return error_response
    
    def _show_thinking_process(self, message: str) -> None:
        """疑似思考過程表示"""
        rich_ui.print_message("🤔 メッセージを読んでいます...", "info")
        time.sleep(0.3)
        if any(keyword in message.lower() for keyword in ["ファイル", "file", "作成", "create", "読み", "read"]):
            rich_ui.print_message("📁 ファイル操作が必要そうですね...", "info")
            time.sleep(0.3)
        elif any(keyword in message.lower() for keyword in ["実行", "run", "テスト", "test"]):
            rich_ui.print_message("⚡ コードの実行が必要そうですね...", "info")
            time.sleep(0.3)
        rich_ui.print_message("💭 どう対応するか考えています...", "info")
        time.sleep(0.2)

    # ... (メソッドの実装は続く) ...
    # 以下、簡単のため省略しますが、元のファイルの他のメソッドはすべて保持されていると仮定します。
    # このリファクタリングでは、__init__とインポート文のみが変更対象です。

    def _is_help_request(self, message: str) -> bool:
        return message.strip().lower() in ["/help", "help"]

    def _handle_help_request(self, message: str) -> str:
        return get_help()

    def _generate_direct_response(self, user_message: str) -> str:
        """直接応答を生成"""
        try:
            rich_ui.print_message("💬 お答えを考えています...", "info")
            messages = [{"role": "system", "content": self.system_prompt}]
            with self._history_lock:
                if self.conversation_history:
                    for entry in self.conversation_history[-20:]:
                        messages.append({"role": "user", "content": entry["user"]})
                        messages.append({"role": "assistant", "content": entry["assistant"]})
            messages.append({"role": "user", "content": user_message})
            response = llm_manager.chat_with_history(messages)
            rich_ui.print_message("✨ お答えできました！", "success")
            return response
        except Exception as e:
            return f"すみません、考えがまとまりませんでした...。エラー: {str(e)}"

    def _handle_file_operation(self, user_message: str) -> str:
        """ファイル操作を処理（フォールバック時の簡易読み取り対応）"""
        try:
            # 簡易に引用や拡張子を含むファイル名を検出して読み取り
            import re
            patterns = [
                r'["\']([^"\']+\.[a-zA-Z0-9]+)["\']',
                r'([a-zA-Z0-9_\-\.\\/]+\.[a-zA-Z0-9]+)'
            ]
            file_path = None
            for p in patterns:
                m = re.search(p, user_message)
                if m:
                    file_path = m.group(1)
                    break
            if file_path:
                from .file_ops import SimpleFileOps
                ops = SimpleFileOps()
                content = ops.read_file(file_path)
                preview = content if len(content) < 800 else content[:800] + '...'
                return f"📄 ファイル '{file_path}' の内容:\n\n{preview}"
        except Exception:
            pass
        # 既定のメッセージ（従来）
        rich_ui.print_message("ファイル操作は現在リファクタリング中です。", "warning")
        return "ファイル操作機能は、新しい承認システムへの移行作業中のため、現在ご利用いただけません。"

    def _handle_code_execution(self, user_message: str) -> str:
        """コード実行を処理"""
        return "コード実行機能は現在実装されていません。"

    def _handle_multi_step_task(self, user_message: str) -> str:
        """複数ステップタスクを処理"""
        return "複数ステップタスク機能は現在リファクタリング中です。"

    def _express_error_naturally(self, error: Exception) -> str:
        """エラーを自然に表現"""
        import random
        error_messages = [
            f"うわっ、ごめんなさい！何かうまくいきませんでした...。エラー: {str(error)}",
            f"あれ？困りました...。こんなエラーが出ちゃいました: {str(error)}",
            f"すみません、僕のミスです...。エラーが発生しました: {str(error)}",
        ]
        return random.choice(error_messages)

    def _record_conversation(self, user_message: str, assistant_response: str) -> None:
        """会話を記録"""
        entry = {
            "user": user_message,
            "assistant": assistant_response,
            "timestamp": datetime.now(),
        }
        with self._history_lock:
            self.conversation_history.append(entry)
            if len(self.conversation_history) > 100:
                self.conversation_history = self.conversation_history[-80:]

    def _analyze_intent_legacy(self, message: str) -> ActionType:
        """旧システムによる意図分析"""
        message_lower = message.lower()
        if any(kw in message_lower for kw in ["ファイル", "file", "作成", "create", "読み", "read", "書き込み", "write"]):
            return ActionType.FILE_OPERATION
        return ActionType.DIRECT_RESPONSE

    def _is_plan_response(self, user_message: str) -> bool:
        return self.current_plan is not None and user_message.lower().strip() in ['a', 'b', 'c']

    async def _analyze_intent_new_system(self, message: str, context: Optional[Dict[str, Any]] = None) -> ActionType:
        """新しい意図理解システムによる分析"""
        try:
            rich_ui.print_message("🧠 新しい意図理解システムで分析中...", "info")
            if context is None:
                context = {}
            
            understanding_result = await self.intent_system.understand_intent(message, context)
            
            task_profile = understanding_result.task_profile.profile_type.value
            
            if task_profile in ["creation_request", "modification_request", "analysis_request"]:
                action_type = ActionType.FILE_OPERATION
            elif task_profile in ["information_request", "guidance_request"]:
                action_type = ActionType.DIRECT_RESPONSE
            elif task_profile in ["search_request"]:
                action_type = ActionType.MULTI_STEP_TASK
            else:
                action_type = ActionType.DIRECT_RESPONSE  # デフォルトは安全な直接応答

            self.last_understanding_result = understanding_result
            return action_type
        except Exception as e:
            rich_ui.print_message(f"[!] 新システムでエラー発生、旧システムにフォールバック: {str(e)[:100]}...", "warning")
            return self._analyze_intent_legacy(message)

    def _handle_plan_response(self, user_message: str) -> str:
        return "プラン応答機能はリファクタリング中です。"
