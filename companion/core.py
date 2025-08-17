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
from codecrafter.ui.rich_ui import rich_ui
from codecrafter.base.llm_client import llm_manager

# Phase 1.5: ファイル操作機能
from .file_ops import SimpleFileOps, FileOperationError

# 承認システム
from .approval_system import ApprovalGate, ApprovalConfig, ApprovalMode

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
    
    def __init__(self):
        """初期化"""
        import threading
        self.conversation_history = []
        self.simple_preferences = {}
        self.session_start_time = datetime.now()
        self._history_lock = threading.Lock()  # スレッドセーフティ用
        
        # A-2: 失敗認知ループ用の状態管理
        self.failure_contexts: List[FailureContext] = []
        self.operation_counter = 0
        
        # B-1: 動的計画フェーズ用の状態管理
        self.current_plan: Optional[TaskPlan] = None
        self.plan_counter = 0
        
        # 承認システム（エラー時は優雅な劣化）
        try:
            from .approval_ui import UserApprovalUI
            
            self.approval_gate = ApprovalGate()
            self._load_approval_config()
            
            # UserApprovalUIを承認ゲートに接続
            self.approval_ui = UserApprovalUI(timeout_seconds=30)
            self.approval_gate.set_approval_ui(self.approval_ui)
            rich_ui.print_message("✅ 承認システムとUIを接続しました", "success")
            
        except Exception as e:
            # 承認システム初期化失敗時はデフォルト設定で継続
            rich_ui.print_message(f"⚠️ 承認システムの初期化に失敗しました。デフォルト設定を使用します: {e}", "warning")
            self.approval_gate = ApprovalGate()  # デフォルト設定で作成
        
        # Phase 1.5: ファイル操作機能（承認ゲートを渡す）
        self.file_ops = SimpleFileOps(approval_gate=self.approval_gate)
        
        # 新しい意図理解システムの初期化（既存LLMマネージャー使用）
        try:
            from .llm.existing_llm_adapter import default_llm_adapter
            
            # 既存のLLMマネージャーが利用可能かチェック
            if default_llm_adapter.is_available():
                self.intent_system = IntentUnderstandingSystem(default_llm_adapter)
                self.use_new_intent_system = True
                provider_info = default_llm_adapter.get_provider_info()
                rich_ui.print_message(f"✨ 新しい意図理解システムを初期化しました（{provider_info['provider_name']}）", "success")
            else:
                # LLMが利用できない場合は旧システムを使用
                rich_ui.print_message("⚠️ LLMが利用できません。旧システムを使用します", "warning")
                self.intent_system = None
                self.use_new_intent_system = False
        except Exception as e:
            # 新システム初期化失敗時は旧システムを使用
            rich_ui.print_message(f"⚠️ 新しい意図理解システムの初期化に失敗しました。旧システムを使用します: {e}", "warning")
            self.intent_system = None
            self.use_new_intent_system = False
        
        # セッション管理
        import uuid
        self.session_id = str(uuid.uuid4())
        
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
    
    async def analyze_intent_only(self, user_message: str) -> Dict[str, Any]:
        """意図理解のみを実行（統一化用）
        
        Args:
            user_message: ユーザーからのメッセージ
            
        Returns:
            Dict: 意図理解結果
        """
        try:
            # 意図分析（新システム or 旧システム）
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
            # エラー時はDIRECT_RESPONSEにフォールバック
            return {
                "action_type": ActionType.DIRECT_RESPONSE,
                "understanding_result": None,
                "message": user_message,
                "error": str(e)
            }
    
    async def process_message(self, user_message: str) -> str:
        """メッセージを処理する - メインエントリーポイント
        
        Args:
            user_message: ユーザーからのメッセージ
            
        Returns:
            str: 応答メッセージ
        """
        try:
            # 0. ヘルプコマンドの処理
            if self._is_help_request(user_message):
                return self._handle_help_request(user_message)
            
            # B-2: 既存計画への応答処理
            if self.current_plan and self._is_plan_response(user_message):
                return self._handle_plan_response(user_message)
            
            # 1. 疑似思考過程表示
            self._show_thinking_process(user_message)
            
            # 2. 意図分析（新システム or 旧システム）
            if self.use_new_intent_system and self.intent_system:
                action_type = await self._analyze_intent_new_system(user_message)
            else:
                action_type = self._analyze_intent_legacy(user_message)
            
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
    
    async def process_with_intent_result(self, intent_result: Dict[str, Any]) -> str:
        """意図理解結果を再利用してメッセージを処理
        
        Args:
            intent_result: analyze_intent_onlyの結果
            
        Returns:
            str: 応答メッセージ
        """
        try:
            user_message = intent_result["message"]
            action_type = intent_result["action_type"]
            
            # 1. 疑似思考過程表示
            self._show_thinking_process(user_message)
            
            # 2. 意図理解結果を再利用
            if hasattr(self, 'last_understanding_result'):
                self.last_understanding_result = intent_result.get("understanding_result")
            
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
            self._record_conversation(intent_result["message"], error_response)
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
    
    async def _analyze_intent_new_system(self, message: str, external_context: Optional[Dict[str, Any]] = None) -> ActionType:
        """新しい意図理解システムによる分析
        
        Args:
            message: ユーザーメッセージ
            
        Returns:
            ActionType: 判定されたアクションタイプ
        """
        try:
            rich_ui.print_message("🧠 新しい意図理解システムで分析中...", "info")
            
            # コンテキストの準備（外部コンテキストをマージ）
            context = {
                "recent_messages": self.conversation_history[-3:] if self.conversation_history else [],
                "project_info": "Duckflow companion system",
                "session_duration": (datetime.now() - self.session_start_time).total_seconds()
            }
            
            # 外部コンテキスト（プラン状態など）をマージ
            if external_context:
                context.update(external_context)
            
            # 統合意図理解の実行
            understanding_result = await self.intent_system.understand_intent(message, context)
            
            # TaskProfileからActionTypeへの変換
            task_profile = understanding_result.task_profile.profile_type.value
            detected_targets = understanding_result.intent_analysis.detected_targets
            
            # ファイル関連の検出ロジックを強化
            has_file_reference = any([
                # ファイル名パターンの検出
                any(target.endswith(('.md', '.py', '.txt', '.json', '.yaml', '.yml', '.js', '.ts', '.html', '.css')) 
                    for target in detected_targets),
                # メッセージ内のファイル参照
                any(keyword in message.lower() for keyword in [
                    'ファイル', 'file', '.md', '.py', '.txt', '.json',
                    '確認', '参照', '読み', 'read', '見る', '内容'
                ])
            ])
            
            # A-1: 抽象度/具体度による処理選択
            abstraction_level, concreteness_score = self._analyze_abstraction_concreteness(message, detected_targets)
            
            # デバッグ情報
            rich_ui.print_message(f"🎯 抽象度: {abstraction_level}, 具体度: {concreteness_score:.2f}", "muted")
            
            # ルーティング保守化: 抽象度/具体度に基づく判定
            if task_profile in ["creation_request", "modification_request"]:
                # 抽象的なcreation_requestは質問/計画フェーズへ
                if concreteness_score < 0.5:
                    rich_ui.print_message("📋 抽象的な要求のため、詳細確認が必要です", "info")
                    action_type = ActionType.MULTI_STEP_TASK
                else:
                    action_type = ActionType.FILE_OPERATION
            elif task_profile == "information_request" and has_file_reference:
                # 情報要求でもファイル参照がある場合はファイル操作
                action_type = ActionType.FILE_OPERATION
            elif task_profile == "analysis_request":
                action_type = ActionType.MULTI_STEP_TASK
            elif task_profile == "search_request":
                action_type = ActionType.MULTI_STEP_TASK
            elif task_profile in ["information_request", "guidance_request"]:
                action_type = ActionType.DIRECT_RESPONSE
            else:
                action_type = ActionType.DIRECT_RESPONSE
            
            # デバッグ情報の表示
            rich_ui.print_message(f"🎯 TaskProfile: {task_profile}", "muted")
            rich_ui.print_message(f"🎯 信頼度: {understanding_result.overall_confidence:.1%}", "muted")
            rich_ui.print_message(f"🎯 ActionType: {action_type.value}", "muted")
            
            # 理解結果を保存（後で使用可能）
            self.last_understanding_result = understanding_result
            
            return action_type
            
        except Exception as e:
            rich_ui.print_message(f"⚠️ 新システムでエラー発生、旧システムにフォールバック: {str(e)[:100]}...", "warning")
            # 新システムを無効化
            self.use_new_intent_system = False
            return self._analyze_intent_legacy(message)
    
    def _analyze_abstraction_concreteness(self, message: str, detected_targets: list) -> tuple:
        """メッセージの抽象度と具体度を判定
        
        Args:
            message: ユーザーメッセージ
            detected_targets: 検出されたターゲット
            
        Returns:
            tuple: (abstraction_level: str, concreteness_score: float)
        """
        message_lower = message.lower()
        
        # 具体度スコア計算（0.0-1.0）
        concreteness_indicators = 0
        total_indicators = 0
        
        # ファイル名の明確さ
        total_indicators += 1
        if detected_targets and any('.' in target for target in detected_targets):
            concreteness_indicators += 0.8  # 拡張子のあるファイル名
        elif detected_targets:
            concreteness_indicators += 0.4  # ファイル名はあるが曖昧
        
        # 操作の明確さ
        total_indicators += 1
        concrete_operations = ['作成', '作って', 'create', '書き込み', 'write', '読み取り', 'read', '削除', 'delete']
        if any(op in message_lower for op in concrete_operations):
            concreteness_indicators += 0.7
        
        # 内容の具体性
        total_indicators += 1
        if any(keyword in message_lower for keyword in ['内容', 'content', 'コード', 'code', 'テキスト', 'text']):
            concreteness_indicators += 0.6
        
        # 場所の明確さ
        total_indicators += 1
        if any(keyword in message_lower for keyword in ['ディレクトリ', 'directory', 'フォルダ', 'folder', 'パス', 'path']):
            concreteness_indicators += 0.5
        
        # 抽象的キーワード（減点）
        abstract_keywords = ['実装', 'implement', '始め', 'start', '開発', 'develop', '作業', 'work', 'システム', 'system']
        abstract_penalty = sum(0.2 for keyword in abstract_keywords if keyword in message_lower)
        
        concreteness_score = max(0.0, min(1.0, concreteness_indicators / total_indicators - abstract_penalty))
        
        # 抽象度レベル決定
        if concreteness_score >= 0.7:
            abstraction_level = "low"
        elif concreteness_score >= 0.4:
            abstraction_level = "mid"
        else:
            abstraction_level = "high"
        
        return abstraction_level, concreteness_score
    
    def _record_failure(self, kind: str, reason: str, inputs: Dict[str, Any], 
                       user_message: str, suggested_actions: List[str] = None) -> FailureContext:
        """失敗を構造化記録
        
        Args:
            kind: 失敗の種類
            reason: 失敗理由
            inputs: 入力データ
            user_message: ユーザーメッセージ
            suggested_actions: 提案される対応策
            
        Returns:
            FailureContext: 記録された失敗コンテキスト
        """
        self.operation_counter += 1
        operation_id = f"op_{self.operation_counter}_{datetime.now().strftime('%H%M%S')}"
        
        if suggested_actions is None:
            suggested_actions = [
                "より具体的な指示を提供",
                "ファイル名や内容を明確化",
                "別のアプローチを検討"
            ]
        
        failure_context = FailureContext(
            operation_id=operation_id,
            kind=kind,
            inputs=inputs,
            reason=reason,
            timestamp=datetime.now(),
            user_message=user_message,
            suggested_actions=suggested_actions
        )
        
        # 最新5件のみ保持
        self.failure_contexts.append(failure_context)
        if len(self.failure_contexts) > 5:
            self.failure_contexts = self.failure_contexts[-5:]
        
        rich_ui.print_message(f"🔍 失敗を記録しました: {operation_id} ({kind})", "muted")
        return failure_context
    
    def _get_failure_context_for_prompt(self) -> str:
        """プロンプト用の失敗コンテキストを取得"""
        if not self.failure_contexts:
            return ""
        
        # 最新の失敗コンテキストのみを使用
        latest_failure = self.failure_contexts[-1]
        return latest_failure.to_prompt_context()
    
    def _parse_file_operation_json(self, analysis_result: str, user_message: str) -> Optional[Dict[str, Any]]:
        """JSONスキーマによる厳格なパース
        
        Args:
            analysis_result: LLMの分析結果
            user_message: ユーザーメッセージ
            
        Returns:
            Optional[Dict[str, Any]]: パース結果（失敗時はNone）
        """
        import json
        import re
        
        try:
            # JSONブロックを抽出
            json_match = re.search(r'\{[^{}]*\}', analysis_result)
            if not json_match:
                rich_ui.print_message("❌ JSON形式が見つかりません", "error")
                return None
            
            json_str = json_match.group()
            operation_data = json.loads(json_str)
            
            # 必須フィールドの検証
            required_fields = ['operation', 'filename']
            for field in required_fields:
                if field not in operation_data or not operation_data[field]:
                    rich_ui.print_message(f"❌ 必須フィールド '{field}' が不足", "error")
                    return None
            
            # 操作タイプの検証
            valid_operations = ['create', 'read', 'write', 'list']
            if operation_data['operation'] not in valid_operations:
                rich_ui.print_message(f"❌ 無効な操作: {operation_data['operation']}", "error")
                return None
            
            # デフォルト値の設定
            operation_data.setdefault('content', '')
            operation_data.setdefault('is_directory', False)
            operation_data.setdefault('justification', '操作の実行')
            
            rich_ui.print_message("✅ JSON解析に成功しました", "success")
            return operation_data
            
        except json.JSONDecodeError as e:
            rich_ui.print_message(f"❌ JSON解析エラー: {e}", "error")
            return None
        except Exception as e:
            rich_ui.print_message(f"❌ 予期しないパースエラー: {e}", "error")
            return None
    
    def _handle_parse_failure(self, analysis_result: str, user_message: str) -> str:
        """パース失敗時の失敗認知ループ処理
        
        Args:
            analysis_result: 失敗したLLM応答
            user_message: ユーザーメッセージ
            
        Returns:
            str: 失敗対応メッセージ
        """
        # 失敗を記録
        failure_context = self._record_failure(
            kind="parse_error",
            reason="LLM出力がJSONスキーマに準拠していません",
            inputs={"llm_response": analysis_result[:200], "user_message": user_message},
            user_message=user_message,
            suggested_actions=[
                "より具体的なファイル名を指定",
                "操作内容を明確化",
                "ステップを分けて実行"
            ]
        )
        
        # 明確化質問を生成
        clarification_questions = self._generate_clarification_questions(user_message)
        
        response = f"""申し訳ありません。ファイル操作の詳細を正しく理解できませんでした。

🔍 **問題**: {failure_context.reason}

以下の点を明確にしていただけますか？

{clarification_questions}

より具体的な指示をいただければ、適切にファイル操作を実行できます。"""
        
        return response
    
    def _generate_clarification_questions(self, user_message: str) -> str:
        """明確化質問を生成（最大2問）
        
        Args:
            user_message: ユーザーメッセージ
            
        Returns:
            str: 質問リスト
        """
        questions = []
        message_lower = user_message.lower()
        
        # ファイル名が不明確な場合
        if not any(ext in message_lower for ext in ['.py', '.txt', '.md', '.json', '.js', '.html', '.css']):
            questions.append("📁 **ファイル名**: どのようなファイル名にしますか？（拡張子も含めて）")
        
        # 操作が不明確な場合
        if not any(op in message_lower for op in ['作成', '作って', '書き込み', '読み取り', '削除']):
            questions.append("⚡ **操作内容**: 具体的に何をしたいですか？（作成/読み取り/編集/削除）")
        
        # 内容が不明確な場合（作成・書き込み時）
        if any(word in message_lower for word in ['作成', '作って', '書き込み']) and 'ディレクトリ' not in message_lower:
            if len(questions) < 2:
                questions.append("📝 **内容**: ファイルにはどのような内容を書き込みますか？")
        
        # 最大2問に制限
        questions = questions[:2]
        
        if not questions:
            questions = ["📋 **詳細**: もう少し具体的に教えていただけますか？"]
        
        return "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
    
    def _get_minimal_context(self) -> str:
        """汎用コンテキストの最小収集（C-2: 失敗認知統合版）
        
        Returns:
            str: 最小限のコンテキスト情報
        """
        context_parts = []
        
        # 直近の対話履歴（最大3件）
        with self._history_lock:
            if self.conversation_history:
                recent_messages = self.conversation_history[-3:]
                if recent_messages:
                    context_parts.append("直近の対話:")
                    for entry in recent_messages:
                        context_parts.append(f"- ユーザー: {entry['user'][:50]}{'...' if len(entry['user']) > 50 else ''}")
                        context_parts.append(f"- 応答: {entry['assistant'][:50]}{'...' if len(entry['assistant']) > 50 else ''}")
        
        # C-2: 失敗認知プロンプト - 最近の失敗ログを含める
        failure_context = self._get_failure_context()
        if failure_context:
            context_parts.append("\n" + failure_context)
        
        # セッション情報
        session_duration = (datetime.now() - self.session_start_time).total_seconds()
        if session_duration > 60:
            context_parts.append(f"セッション継続時間: {session_duration/60:.1f}分")
        
        # 失敗履歴数（学習パターン用）
        if self.failure_contexts:
            context_parts.append(f"今セッションでの解決済み課題: {len(self.failure_contexts)}件")
        
        return "\n".join(context_parts) if context_parts else "新しいセッション"
    
    def _get_failure_context(self) -> str:
        """C-2: 失敗認知プロンプト用の文脈を生成
        
        Returns:
            str: 失敗からの学習文脈
        """
        failure_parts = []
        
        # Phase A: FailureContext からの失敗情報
        if self.failure_contexts:
            recent_failures = self.failure_contexts[-2:]  # 最新2件
            if recent_failures:
                failure_parts.append("🔍 **前回の問題と学習**:")
                for failure in recent_failures:
                    failure_parts.append(f"- {failure.to_prompt_context()}")
        
        # C-1: 構造化操作ログからの失敗情報
        if hasattr(self.file_ops, 'get_recent_failures'):
            operation_failures = self.file_ops.get_recent_failures(limit=2)
            if operation_failures:
                failure_parts.append("🔧 **最近の操作失敗**:")
                for op_failure in operation_failures:
                    failure_summary = op_failure.to_failure_summary()
                    if failure_summary:
                        failure_parts.append(f"- {failure_summary}")
        
        return "\n".join(failure_parts) if failure_parts else ""
    
    def _generate_failure_aware_prompt(self, user_message: str, base_prompt: str) -> str:
        """C-2: 失敗を踏まえたプロンプトを生成
        
        Args:
            user_message: ユーザーメッセージ
            base_prompt: ベースプロンプト
            
        Returns:
            str: 失敗認知を含む強化プロンプト
        """
        failure_context = self._get_failure_context()
        
        if not failure_context:
            return base_prompt
        
        # 失敗を踏まえた次の一手を促すプロンプト拡張
        enhanced_prompt = f"""{base_prompt}

{failure_context}

**重要**: 上記の失敗・問題を踏まえて、以下を検討してください：
1. 同じ失敗を避けるためのアプローチ
2. 代替手段や異なる手順の提案
3. より詳細な情報が必要な場合は質問
4. 実行前の確認や準備が必要な場合は明示

失敗から学んで、より良い解決策を提供してください。"""

        return enhanced_prompt
    
    def _handle_operation_with_retry(self, operation_func, operation_name: str, 
                                    max_retries: int = 1, **kwargs) -> Any:
        """C-3: 操作をリトライ方針に従って実行
        
        Args:
            operation_func: 実行する操作関数
            operation_name: 操作名（ログ用）
            max_retries: 最大リトライ回数（デフォルト1回）
            **kwargs: 操作関数に渡す引数
            
        Returns:
            Any: 操作結果
            
        Raises:
            Exception: 最大リトライ後も失敗した場合
        """
        last_error = None
        
        for attempt in range(max_retries + 1):  # 初回 + リトライ
            try:
                if attempt > 0:
                    rich_ui.print_message(f"🔄 {operation_name} をリトライ中... ({attempt}/{max_retries})", "warning")
                    
                    # リトライ前に失敗コンテキストを作成
                    if last_error:
                        failure_context = FailureContext(
                            operation_id=f"retry_{self.operation_counter}_{attempt}",
                            kind="retry_attempt",
                            inputs=kwargs,
                            reason=str(last_error),
                            timestamp=datetime.now(),
                            user_message=kwargs.get('user_message', ''),
                            suggested_actions=[
                                "パラメータを調整して再試行",
                                "代替手段を検討",
                                "より詳細な情報を提供"
                            ]
                        )
                        self.failure_contexts.append(failure_context)
                
                # 操作実行
                result = operation_func(**kwargs)
                
                if attempt > 0:
                    rich_ui.print_message(f"✅ {operation_name} がリトライで成功しました！", "success")
                
                return result
                
            except Exception as e:
                last_error = e
                
                if attempt < max_retries:
                    rich_ui.print_message(f"⚠️ {operation_name} が失敗しました: {str(e)}", "warning")
                    rich_ui.print_message(f"🔄 自動リトライします... (残り{max_retries - attempt}回)", "info")
                else:
                    rich_ui.print_message(f"❌ {operation_name} が最大リトライ後も失敗しました: {str(e)}", "error")
                    
                    # 最終失敗のコンテキストを作成
                    failure_context = FailureContext(
                        operation_id=f"final_failure_{self.operation_counter}",
                        kind="max_retries_exceeded",
                        inputs=kwargs,
                        reason=f"最大リトライ回数({max_retries})後も失敗: {str(e)}",
                        timestamp=datetime.now(),
                        user_message=kwargs.get('user_message', ''),
                        suggested_actions=[
                            "手動で詳細を確認",
                            "別のアプローチを検討",
                            "システム管理者に連絡"
                        ]
                    )
                    self.failure_contexts.append(failure_context)
                    
                    raise e
        
        # この行には到達しないはずだが、安全のため
        raise Exception(f"{operation_name} の実行に失敗しました")
    
    def _should_retry_error(self, error: Exception) -> bool:
        """C-3: エラーがリトライ対象かどうかを判定
        
        Args:
            error: 発生したエラー
            
        Returns:
            bool: リトライすべき場合True
        """
        # リトライ対象のエラータイプ
        retryable_errors = [
            "timeout",
            "connection",
            "network",
            "temporary",
            "rate_limit",
            "429",  # Too Many Requests
            "503",  # Service Unavailable
            "502",  # Bad Gateway
        ]
        
        error_str = str(error).lower()
        return any(keyword in error_str for keyword in retryable_errors)
    
    def _wait_before_retry(self, attempt: int, base_delay: float = 1.0) -> None:
        """C-3: リトライ前の待機（指数バックオフ）
        
        Args:
            attempt: 試行回数
            base_delay: ベース遅延時間（秒）
        """
        import time
        import random
        
        # 指数バックオフ + ジッター
        delay = base_delay * (2 ** (attempt - 1)) + random.uniform(0, 1)
        max_delay = 10.0  # 最大10秒
        
        actual_delay = min(delay, max_delay)
        
        rich_ui.print_message(f"⏱️ {actual_delay:.1f}秒待機してからリトライします...", "info")
        time.sleep(actual_delay)
    
    def _create_micro_plan(self, user_message: str, abstraction_level: str, concreteness_score: float) -> TaskPlan:
        """マイクロプラン（1-2手順）を作成
        
        Args:
            user_message: ユーザーメッセージ
            abstraction_level: 抽象度
            concreteness_score: 具体度スコア
            
        Returns:
            TaskPlan: マイクロプラン
        """
        self.plan_counter += 1
        plan_id = f"micro_{self.plan_counter}_{datetime.now().strftime('%H%M%S')}"
        
        # 簡単なルールベース計画生成
        if "ファイル" in user_message.lower() and "作成" in user_message.lower():
            purpose = "ファイル作成タスクの実行"
            steps = [
                "ファイル内容を決定",
                "ファイルを作成"
            ]
            targets = ["新規ファイル"]
            impact_scope = "ローカルファイルシステム"
        elif "実装" in user_message.lower():
            purpose = "実装タスクの開始"
            steps = [
                "実装対象を明確化",
                "基本構造を作成"
            ]
            targets = ["ソースコード"]
            impact_scope = "プロジェクト構造"
        else:
            purpose = "ユーザー要求の実行"
            steps = [
                "要求内容を分析",
                "適切な手順で実行"
            ]
            targets = ["要求された対象"]
            impact_scope = "限定的"
        
        return TaskPlan(
            plan_id=plan_id,
            purpose=purpose,
            prerequisites=["なし"],
            targets=targets,
            impact_scope=impact_scope,
            steps=steps,
            next_actions={
                "A": "実行 - このプランで進める",
                "B": "明確化 - より詳しい情報を提供",
                "C": "代替案 - 別のアプローチを検討"
            },
            granularity="micro",
            abstraction_level=abstraction_level,
            estimated_complexity="simple"
        )
    
    def _create_light_plan(self, user_message: str, abstraction_level: str, concreteness_score: float) -> TaskPlan:
        """軽量計画（2-5手順）を作成
        
        Args:
            user_message: ユーザーメッセージ
            abstraction_level: 抽象度
            concreteness_score: 具体度スコア
            
        Returns:
            TaskPlan: 軽量計画
        """
        self.plan_counter += 1
        plan_id = f"light_{self.plan_counter}_{datetime.now().strftime('%H%M%S')}"
        
        # LLMベースの計画生成
        try:
            planning_prompt = f"""
ユーザー要求を分析して、2-5手順の軽量タスク計画を作成してください。

ユーザー要求: "{user_message}"
抽象度: {abstraction_level}
具体度スコア: {concreteness_score:.2f}

以下のJSON形式で応答してください：
{{
    "purpose": "目的の簡潔な説明",
    "prerequisites": ["前提条件1", "前提条件2"],
    "targets": ["変更対象1", "変更対象2"],
    "impact_scope": "影響範囲の説明",
    "steps": ["手順1", "手順2", "手順3", "手順4", "手順5"],
    "estimated_complexity": "simple|moderate|complex"
}}

要件:
- stepsは2-5個の実行可能な手順
- prerequisitesは実際に必要な前提条件のみ
- targetsは具体的な変更対象
- impact_scopeは簡潔に
"""
            
            # C-3: リトライ機能を使ってLLM呼び出し
            def llm_call_wrapper(**kwargs):
                return llm_manager.chat(kwargs['prompt'], kwargs['system_prompt'])
            
            result = self._handle_operation_with_retry(
                llm_call_wrapper,
                "LLM計画生成",
                max_retries=1,
                prompt=planning_prompt,
                system_prompt=self.system_prompt,
                user_message=user_message
            )
            
            # JSONパース
            import json
            import re
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                plan_data = json.loads(json_match.group())
                
                return TaskPlan(
                    plan_id=plan_id,
                    purpose=plan_data.get("purpose", "ユーザー要求の実行"),
                    prerequisites=plan_data.get("prerequisites", ["なし"]),
                    targets=plan_data.get("targets", ["要求された対象"]),
                    impact_scope=plan_data.get("impact_scope", "プロジェクト内"),
                    steps=plan_data.get("steps", ["要求を分析", "計画を実行"]),
                    next_actions={
                        "A": "実行 - この計画で進める",
                        "B": "明確化 - より詳しい情報を提供", 
                        "C": "代替案 - 別のアプローチを検討"
                    },
                    granularity="light",
                    abstraction_level=abstraction_level,
                    estimated_complexity=plan_data.get("estimated_complexity", "moderate")
                )
        
        except Exception as e:
            rich_ui.print_message(f"⚠️ LLMベース計画生成に失敗、フォールバック使用: {e}", "warning")
        
        # フォールバック: ルールベース計画
        return self._create_micro_plan(user_message, abstraction_level, concreteness_score)
    
    def _handle_clarification_needed(self, user_message: str, abstraction_level: str, concreteness_score: float) -> str:
        """B-2: 明確化が必要な場合の処理
        
        Args:
            user_message: ユーザーメッセージ
            abstraction_level: 抽象度
            concreteness_score: 具体度スコア
            
        Returns:
            str: 明確化質問
        """
        questions = self._generate_clarification_questions(user_message)
        
        # 固定テンプレート廃止: 選択肢+デフォルト方式
        plan_response = f"""💭 **実行プランの選択**

ご要求: {user_message}
抽象度: {abstraction_level} (具体度: {concreteness_score:.2f})

推奨する進め方:
1. [推奨] 最小限の安全な実装から始める
2. 詳細を確認してから慎重に実装
3. 段階的に複数回に分けて実装

{questions}

デフォルト（推奨プラン）で進めますか？"""
        
        # プラン状態を設定（実行阻害改善）
        if hasattr(self, 'set_plan_state'):
            self.set_plan_state(plan_response, "clarification_plan")
        
        return plan_response
    
    def _is_plan_response(self, user_message: str) -> bool:
        """計画への応答かどうかを判定"""
        message_lower = user_message.lower().strip()
        
        # 選択肢の応答
        if message_lower in ['a', 'b', 'c']:
            return True
        
        # 明示的な選択
        plan_keywords = [
            '実行', '進める', 'やって', 'お願い', 
            '明確化', '詳細', '教えて', '質問',
            '代替', '別の', '他の', 'やめる'
        ]
        
        return any(keyword in message_lower for keyword in plan_keywords)
    
    def _handle_plan_response(self, user_message: str) -> str:
        """B-2: 計画への応答を処理
        
        Args:
            user_message: ユーザーメッセージ
            
        Returns:
            str: 処理結果メッセージ
        """
        if not self.current_plan:
            return "現在有効な計画がありません。新しい要求をお聞かせください。"
        
        message_lower = user_message.lower().strip()
        
        # A: 実行
        if message_lower in ['a', '実行', '進める', 'やって', 'お願い', 'はい'] or \
           any(word in message_lower for word in ['実行', '進める', 'やって']):
            return self._execute_plan()
        
        # B: 明確化
        elif message_lower in ['b', '明確化', '詳細', '教えて'] or \
             any(word in message_lower for word in ['明確化', '詳細', '教えて', '質問']):
            return self._request_plan_clarification()
        
        # C: 代替案
        elif message_lower in ['c', '代替', '別の', '他の'] or \
             any(word in message_lower for word in ['代替', '別の', '他の', 'やめる']):
            return self._suggest_alternatives()
        
        # その他の応答（追加情報として扱う）
        else:
            return self._update_plan_with_additional_info(user_message)
    
    def _execute_plan(self) -> str:
        """B-3: 計画の実行（承認システム統合版）"""
        if not self.current_plan:
            return "実行する計画がありません。"
        
        rich_ui.print_message(f"🚀 計画を実行中: {self.current_plan.plan_id}", "info")
        rich_ui.print_message(f"📋 目的: {self.current_plan.purpose}", "info")
        
        # 実行前の最終確認（重要リスクの場合）
        if self.current_plan.estimated_complexity in ["complex"] or \
           any(keyword in step.lower() for step in self.current_plan.steps 
               for keyword in ['削除', 'delete', 'システム', 'system']):
            
            try:
                from .approval_system import OperationType, RiskLevel
                
                # 計画全体の承認要求
                approval_response = self.approval_gate.request_approval(
                    operation_type="execute_plan",
                    params={
                        'target': self.current_plan.plan_id,
                        'plan_purpose': self.current_plan.purpose,
                        'steps': self.current_plan.steps,
                        'complexity': self.current_plan.estimated_complexity,
                        'impact_scope': self.current_plan.impact_scope
                    },
                    session_id=self.session_id
                )
                
                if not approval_response.approved:
                    self.current_plan = None
                    return f"🚫 計画の実行が拒否されました: {approval_response.reason}"
                    
            except Exception as e:
                rich_ui.print_message(f"⚠️ 承認システムエラー: {e}", "warning")
        
        # ステップごとの実行
        results = []
        failed_steps = []
        
        for i, step in enumerate(self.current_plan.steps, 1):
            rich_ui.print_message(f"📋 ステップ {i}/{len(self.current_plan.steps)}: {step}", "info")
            
            try:
                # 各ステップを実際のファイル操作に変換
                step_result = self._execute_plan_step(step, i)
                results.append(f"ステップ {i}: {step_result}")
                
                # エラーが含まれている場合は記録
                if "❌" in step_result or "🚫" in step_result:
                    failed_steps.append(i)
                    
            except Exception as e:
                error_result = f"❌ ステップ {i}: 予期しないエラー - {str(e)}"
                results.append(error_result)
                failed_steps.append(i)
                rich_ui.print_message(f"⚠️ ステップ {i} でエラーが発生: {e}", "warning")
        
        # 実行結果のサマリー
        total_steps = len(self.current_plan.steps)
        successful_steps = total_steps - len(failed_steps)
        
        if failed_steps:
            plan_summary = f"⚠️ 計画 '{self.current_plan.purpose}' を部分的に完了しました\n\n"
            plan_summary += f"📊 実行結果: {successful_steps}/{total_steps} ステップ成功\n"
            plan_summary += f"❌ 失敗ステップ: {', '.join(map(str, failed_steps))}\n\n"
        else:
            plan_summary = f"✅ 計画 '{self.current_plan.purpose}' を完全に完了しました！\n\n"
            plan_summary += f"📊 実行結果: {successful_steps}/{total_steps} ステップ全て成功\n\n"
        
        plan_summary += "\n".join(results)
        plan_summary += f"\n\n🎯 影響範囲: {self.current_plan.impact_scope}"
        
        # 失敗がある場合は次のアクションを提案
        if failed_steps:
            plan_summary += "\n\n💡 **次のアクション**:"
            plan_summary += "\n- 失敗したステップを個別に再実行"
            plan_summary += "\n- 別のアプローチを検討"
            plan_summary += "\n- より詳細な計画を作成"
        
        # 計画をクリア
        completed_plan_id = self.current_plan.plan_id
        self.current_plan = None
        
        # 実行ログを記録
        rich_ui.print_message(f"📝 計画 {completed_plan_id} の実行を完了しました", "success")
        
        return plan_summary
    
    def _execute_plan_step(self, step: str, step_number: int) -> str:
        """計画ステップの実行（承認システム統合版）
        
        Args:
            step: 実行するステップ
            step_number: ステップ番号
            
        Returns:
            str: ステップ実行結果
        """
        step_lower = step.lower()
        
        # ファイル関連のステップ - 承認システムを経由
        if any(keyword in step_lower for keyword in ['ファイル', 'file', '作成', 'create']):
            try:
                # ステップをファイル操作要求として解釈
                if "作成" in step_lower:
                    # ファイル作成の承認要求
                    filename = f"plan_step_{step_number}.txt" 
                    content = f"# ステップ {step_number}: {step}\n実行時刻: {datetime.now()}\n"
                    
                    # 承認システムを経由したファイル操作
                    from .approval_system import OperationType
                    
                    # 承認要求
                    approval_response = self.approval_gate.request_approval(
                        operation_type=OperationType.CREATE_FILE,
                        params={
                            'target': filename,
                            'content': content,
                            'operation_context': f'計画実行: {self.current_plan.plan_id if self.current_plan else "unknown"}'
                        },
                        session_id=self.session_id
                    )
                    
                    if approval_response.approved:
                        # 承認された場合のみファイル操作実行
                        result = self.file_ops.create_file(filename, content)
                        if result["success"]:
                            return f"✅ {step} - ファイル {filename} を作成（承認済み）"
                        else:
                            return f"❌ {step} - 失敗: {result.get('message', 'unknown error')}"
                    else:
                        # 承認拒否の場合
                        return f"🚫 {step} - ユーザーにより拒否されました: {approval_response.reason}"
                        
                elif "読み取り" in step_lower or "確認" in step_lower:
                    # 読み取り操作（低リスク）
                    return f"✅ {step} - 確認完了"
                else:
                    return f"✅ {step} - 準備完了"
            
            except Exception as e:
                return f"❌ {step} - エラー: {str(e)}"
        
        # コード実行関連のステップ - 承認システムを経由
        elif any(keyword in step_lower for keyword in ['実行', 'execute', 'run', 'テスト']):
            try:
                from .approval_system import OperationType
                
                # 実行の承認要求
                approval_response = self.approval_gate.request_approval(
                    operation_type=OperationType.EXECUTE_PYTHON,
                    params={
                        'target': step,
                        'command': f'計画ステップ実行: {step}',
                        'operation_context': f'計画実行: {self.current_plan.plan_id if self.current_plan else "unknown"}'
                    },
                    session_id=self.session_id
                )
                
                if approval_response.approved:
                    return f"✅ {step} - 実行準備完了（承認済み）"
                else:
                    return f"🚫 {step} - 実行が拒否されました: {approval_response.reason}"
                    
            except Exception as e:
                return f"❌ {step} - エラー: {str(e)}"
        
        # その他のステップ（情報収集、分析等） - 承認不要
        else:
            return f"✅ {step} - 完了"
    
    def _request_plan_clarification(self) -> str:
        """計画の明確化要求"""
        if not self.current_plan:
            return "明確化する計画がありません。"
        
        # より詳細な質問を生成
        clarification_prompt = f"""
現在の計画について、ユーザーがより詳しい情報を求めています。

計画: {self.current_plan.purpose}
手順: {', '.join(self.current_plan.steps)}

以下の点について明確化質問を1-2個生成してください：
1. 具体的な実装方法
2. 技術的な詳細
3. リスクや注意点
4. 代替アプローチ

簡潔で実用的な質問にしてください。"""
        
        try:
            clarification = llm_manager.chat(clarification_prompt, self.system_prompt)
            
            return f"""📋 **計画の詳細について**

{clarification}

これらの点について教えていただけますか？計画をより具体的にできます。"""
        
        except Exception as e:
            return f"""📋 **計画の詳細について**

以下の点を明確にしていただけますか？

1. どの部分をより詳しく説明が必要ですか？
2. 技術的な制約や要求はありますか？
3. 期待する結果のイメージを教えてください

これらの情報があれば、計画をより具体的にできます。"""
    
    def _suggest_alternatives(self) -> str:
        """代替案の提案"""
        if not self.current_plan:
            return "代替案を提案する計画がありません。"
        
        alternatives = [
            "🔄 **段階的アプローチ**: 計画を更に小さなステップに分割",
            "🛡️ **安全重視アプローチ**: より慎重で保守的な方法", 
            "⚡ **シンプルアプローチ**: 最小限の変更で目的を達成",
            "🧪 **試行アプローチ**: 小規模なテストから開始"
        ]
        
        alternative_text = "\n".join(alternatives)
        
        # 計画をクリア
        self.current_plan = None
        
        return f"""🤔 **代替案のご提案**

現在の計画の代わりに、以下のようなアプローチはいかがでしょうか？

{alternative_text}

どのアプローチがお好みですか？または、全く違ったアプローチをご希望でしたら教えてください。"""
    
    def _update_plan_with_additional_info(self, additional_info: str) -> str:
        """追加情報で計画を更新"""
        if not self.current_plan:
            return "更新する計画がありません。"
        
        # 追加情報をAgentStateに記録（将来の実装で活用）
        return f"""📝 **追加情報を受け取りました**

「{additional_info}」

この情報を考慮して計画を調整できます。以下から選択してください：

A: 調整した計画で実行
B: さらに詳細を確認
C: 代替案を検討

どちらを希望されますか？"""
    
    def _analyze_intent_legacy(self, message: str) -> ActionType:
        """旧システムによる意図分析（保守的判定版）
        
        Args:
            message: ユーザーメッセージ
            
        Returns:
            ActionType: 判定されたアクションタイプ
        """
        message_lower = message.lower()
        
        # 🔍 DEBUG: 意図分析のログ
        rich_ui.print_message("🔍 [DEBUG] 保守的意図分析:", "info")
        rich_ui.print_message(f"入力メッセージ: '{message}'", "muted")
        
        # ファイル操作キーワード（明確なもののみ）
        file_keywords = ["ファイル作成", "ファイル削除", "ファイル編集", "create file", "delete file", "edit file", ".py作成", ".md作成"]
        matched_file_keywords = [kw for kw in file_keywords if kw in message_lower]
        if matched_file_keywords:
            rich_ui.print_message(f"✅ ファイル操作キーワード検出: {matched_file_keywords}", "muted")
            return ActionType.FILE_OPERATION
        
        # コード実行キーワード（明確なもののみ）
        code_keywords = ["コード実行", "プログラム実行", "run code", "execute", "python実行"]
        matched_code_keywords = [kw for kw in code_keywords if kw in message_lower]
        if matched_code_keywords:
            rich_ui.print_message(f"✅ コード実行キーワード検出: {matched_code_keywords}", "muted")
            return ActionType.CODE_EXECUTION
        
        # 複数ステップタスクキーワード（非常に限定的）
        # 「分析して」「調査して」「レビューして」のような明確な分析要求のみ
        multi_keywords = ["分析して", "調査して", "レビューして", "検討して", "評価して", "問題点", "課題", "改善点"]
        matched_multi_keywords = [kw for kw in multi_keywords if kw in message_lower]
        if matched_multi_keywords and len(message) > 20:  # 短すぎるメッセージは除外
            rich_ui.print_message(f"✅ 複数ステップタスクキーワード検出: {matched_multi_keywords}", "muted")
            return ActionType.MULTI_STEP_TASK
        
        # デフォルトは直接応答（大部分のケース）
        rich_ui.print_message("💭 直接応答として判定", "muted")
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
            messages = [{"role": "system", "content": self.system_prompt}]

            # 過去の会話履歴も含める（最新20件）- スレッドセーフ
            with self._history_lock:
                if self.conversation_history:
                    recent_history = self.conversation_history[-20:]
                    for entry in recent_history:
                        messages.append({"role": "user", "content": entry["user"]})
                        messages.append({"role": "assistant", "content": entry["assistant"]})
            
            # 現在のユーザーメッセージを最後に追加
            messages.append({"role": "user", "content": user_message})
            
            response = llm_manager.chat_with_history(messages)
            
            rich_ui.print_message("✨ お答えできました！", "success")
            return response
            
        except Exception as e:
            return f"すみません、考えがまとまりませんでした...。エラー: {str(e)}"
    
    def _handle_file_operation(self, user_message: str) -> str:
        """ファイル操作を処理 - A-2: 失敗認知ループ統合版
        
        Args:
            user_message: ユーザーメッセージ
            
        Returns:
            str: 処理結果メッセージ
        """
        try:
            # A-2: 失敗コンテキストを含むプロンプト生成
            failure_context = self._get_failure_context_for_prompt()
            
            # A-4: 汎用コンテキストの最小収集
            minimal_context = self._get_minimal_context()
            
            base_prompt = f"""ユーザーメッセージを分析して、必要なファイル操作を判定してください。

{failure_context}

{minimal_context}

ユーザーメッセージ: "{user_message}" 

以下の厳格なJSONスキーマで応答してください：
{{"operation":"create|read|write|list","filename":"<path>","content":"<string|optional>","is_directory":false,"justification":"<why>"}}

**重要な注意事項:**
- 必ずJSON形式で応答してください
- ディレクトリ作成の場合: operation="create", is_directory=true, content=""
- ファイル作成の場合: operation="create", is_directory=false, content="実際の内容"
- justificationには操作の理由を簡潔に記載

例1（ファイル作成）：
{{"operation":"create","filename":"hello.py","content":"print('Hello, World!')","is_directory":false,"justification":"Python Hello Worldプログラムの作成"}}

例2（ディレクトリ作成）：
{{"operation":"create","filename":"temp_test_files","content":"","is_directory":true,"justification":"作業用ディレクトリの作成"}}"""

            # LLMに相談してファイル操作の詳細を決定
            rich_ui.print_message("🤔 どんなファイル操作が必要か考えています...", "info")
            
            analysis_result = llm_manager.chat(base_prompt, self.system_prompt)
            
            # 🔍 DEBUG: LLMレスポンスをログ出力
            rich_ui.print_message("🔍 [DEBUG] LLM分析結果:", "info")
            rich_ui.print_message(f"--- LLM Response Start ---", "muted")
            rich_ui.print_message(analysis_result, "muted")
            rich_ui.print_message(f"--- LLM Response End ---", "muted")
            
            # A-3: JSONスキーマによる堅牢なパース
            operation_info = self._parse_file_operation_json(analysis_result, user_message)
            
            # パースに失敗した場合は失敗認知ループに移行
            if operation_info is None:
                return self._handle_parse_failure(analysis_result, user_message)
            
            # 🔍 DEBUG: パース結果をログ出力
            rich_ui.print_message("🔍 [DEBUG] パース結果:", "info")
            rich_ui.print_message(f"Operation: '{operation_info.get('operation', 'None')}'", "muted")
            rich_ui.print_message(f"Filename: '{operation_info.get('filename', 'None')}'", "muted")
            rich_ui.print_message(f"Content: '{operation_info.get('content', 'None')}'", "muted")
            
            # 実際のファイル操作を実行
            return self._execute_file_operation(operation_info, user_message)
            
        except Exception as e:
            # 🔍 DEBUG: 例外の詳細ログ
            rich_ui.print_message("🚨 [DEBUG] ファイル操作処理で例外が発生:", "error")
            rich_ui.print_message(f"例外タイプ: {type(e).__name__}", "muted")
            rich_ui.print_message(f"例外メッセージ: {str(e)}", "muted")
            import traceback
            rich_ui.print_message(f"スタックトレース:", "muted")
            rich_ui.print_message(traceback.format_exc(), "muted")
            return self._express_error_naturally(e)
    
    def _parse_file_operation(self, analysis_result: str) -> Dict[str, str]:
        """LLMの分析結果をパース（ディレクトリ対応版）
        
        Args:
            analysis_result: LLMの分析結果
            
        Returns:
            Dict[str, str]: 操作情報
        """
        operation_info = {
            "operation": "unknown",
            "filename": "",
            "content": "",
            "is_directory": False
        }
        
        lines = analysis_result.strip().split('\n')
        
        # 🔍 DEBUG: パース処理の詳細ログ
        rich_ui.print_message("🔍 [DEBUG] パース処理開始:", "info")
        rich_ui.print_message(f"総行数: {len(lines)}", "muted")
        
        for i, line in enumerate(lines):
            rich_ui.print_message(f"行{i+1}: '{line}'", "muted")
            
            if line.startswith('操作:'):
                operation_info["operation"] = line.split(':', 1)[1].strip()
                rich_ui.print_message(f"✅ 操作を検出: '{operation_info['operation']}'", "muted")
            elif line.startswith('ファイル名:') or line.startswith('ディレクトリ名:'):
                filename = line.split(':', 1)[1].strip()
                operation_info["filename"] = filename
                
                # ディレクトリかどうかの判定
                if (filename.endswith('/') or 
                    'フォルダ' in filename or 
                    'ディレクトリ' in filename or
                    line.startswith('ディレクトリ名:')):
                    operation_info["is_directory"] = True
                    # 末尾のスラッシュを除去
                    if filename.endswith('/'):
                        operation_info["filename"] = filename.rstrip('/')
                    rich_ui.print_message(f"✅ ディレクトリを検出: '{operation_info['filename']}'", "muted")
                else:
                    rich_ui.print_message(f"✅ ファイル名を検出: '{operation_info['filename']}'", "muted")
                    
            elif line.startswith('内容:'):
                content = line.split(':', 1)[1].strip()
                if content != "なし":
                    operation_info["content"] = content
                    rich_ui.print_message(f"✅ 内容を検出: '{content[:50]}{'...' if len(content) > 50 else ''}'", "muted")
                else:
                    rich_ui.print_message(f"💭 内容は「なし」", "muted")
            else:
                rich_ui.print_message(f"⚠️ 未認識行: '{line}'", "muted")
        
        rich_ui.print_message("🔍 [DEBUG] パース処理完了", "info")
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
                # ディレクトリかファイルかを判定
                if operation_info.get("is_directory", False):
                    # ディレクトリ作成
                    rich_ui.print_message("📁 ディレクトリを作成しています...", "info")
                    result = self.file_ops.create_directory(filename)
                    if result["success"]:
                        return f"✅ ディレクトリ '{filename}' を作成しました！\n\nパス: {result.get('path', filename)}\n\n実装を始める準備が整いました。何か他にお手伝いできることはありますか？"
                    else:
                        return self._handle_file_operation_failure(result, "create_directory", filename)
                else:
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
        """コード実行を処理（シンプル版）
        
        Args:
            user_message: ユーザーメッセージ
            
        Returns:
            str: 処理結果メッセージ
        """
        try:
            rich_ui.print_message("⚡ コード実行タスクとして処理中...", "info")
            
            # シンプルなアプローチ: 通常のチャットベースでコード実行用最適化
            return self._generate_enhanced_response(user_message, task_type="code_execution")
            
        except Exception as e:
            return f"コード実行処理中にエラーが発生しました: {str(e)}"
    
    def _handle_multi_step_task(self, user_message: str) -> str:
        """B-1: 動的グラニュラリティの計画フェーズ
        
        Args:
            user_message: ユーザーメッセージ
            
        Returns:
            str: 処理結果メッセージ
        """
        try:
            rich_ui.print_message("📋 タスク計画を作成中...", "info")
            
            # 抽象度/具体度に基づく計画作成
            abstraction_level, concreteness_score = self._analyze_abstraction_concreteness(user_message, [])
            
            # 動的グラニュラリティ決定
            if abstraction_level == "low" and concreteness_score >= 0.7:
                # マイクロプラン（1-2手順）
                plan = self._create_micro_plan(user_message, abstraction_level, concreteness_score)
            elif abstraction_level == "mid" or (abstraction_level == "high" and concreteness_score >= 0.3):
                # 軽量計画（2-5手順）
                plan = self._create_light_plan(user_message, abstraction_level, concreteness_score)
            else:
                # 明確化が必要（質問フェーズへ）
                return self._handle_clarification_needed(user_message, abstraction_level, concreteness_score)
            
            # 計画を保存
            self.current_plan = plan
            
            # ユーザーに計画を提示
            return plan.to_user_display()
            
        except Exception as e:
            rich_ui.print_message(f"❌ 計画作成処理でエラー: {e}", "error")
            # フォールバックとして従来の処理
            return self._generate_enhanced_response(user_message, task_type="multi_step")
    
    def _generate_enhanced_response(self, user_message: str, task_type: str = "direct") -> str:
        """タスクタイプに応じた最適化された応答を生成
        
        Args:
            user_message: ユーザーメッセージ
            task_type: タスクタイプ (direct, file_operation, multi_step, code_execution)
            
        Returns:
            str: 応答メッセージ
        """
        try:
            rich_ui.print_message("💬 最適化された応答を生成中...", "info")
            
            # タスクタイプ別の最適化文を準備
            optimization_hints = {
                "direct": "",
                "file_operation": "\n\n**ファイル操作に関する注意**: 具体的なファイル名やパスを明確にし、操作の詳細を説明してください。",
                "multi_step": "\n\n**複数ステップタスクとして**: この要求を段階的に分析し、包括的で構造化された回答を提供してください。",
                "code_execution": "\n\n**コード実行に関して**: 実行可能なコードと、その説明を含めて回答してください。"
            }
            
            # 基本のシステムプロンプトに最適化文を追加
            enhanced_system_prompt = self.system_prompt + optimization_hints.get(task_type, "")
            
            # LLMに相談（通常のチャットと同じ方式）
            messages = [{"role": "system", "content": enhanced_system_prompt}]

            # 過去の会話履歴も含める（最新20件）- スレッドセーフ
            with self._history_lock:
                if self.conversation_history:
                    recent_history = self.conversation_history[-20:]
                    for entry in recent_history:
                        messages.append({"role": "user", "content": entry["user"]})
                        messages.append({"role": "assistant", "content": entry["assistant"]})
            
            # 現在のユーザーメッセージを最後に追加
            messages.append({"role": "user", "content": user_message})
            
            response = llm_manager.chat_with_history(messages)
            
            rich_ui.print_message("✨ 最適化された応答を生成しました！", "success")
            return response
            
        except Exception as e:
            return f"すみません、考えがまとまりませんでした...。エラー: {str(e)}"
    
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
        
        # スレッドセーフな履歴更新
        with self._history_lock:
            self.conversation_history.append(entry)
            
            # メモリ管理（改善版: 100件保存、80件に削減）
            if len(self.conversation_history) > 100:
                # 古い履歴を削除（100件を超えたら80件に削減）
                self.conversation_history = self.conversation_history[-80:]
    
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
    
    def _is_help_request(self, message: str) -> bool:
        """ヘルプ要求かどうかを判定"""
        help_keywords = [
            'help', 'ヘルプ', '助けて', 'たすけて', 'わからない', '分からない',
            '使い方', 'つかいかた', 'どうやって', 'どうすれば', '教えて', 'おしえて'
        ]
        
        message_lower = message.lower().strip()
        
        # 直接的なヘルプコマンド
        if message_lower in help_keywords:
            return True
        
        # "help <topic>" 形式
        if message_lower.startswith(('help ', 'ヘルプ ')):
            return True
        
        # 質問形式のヘルプ要求
        help_patterns = [
            '使い方を教えて', 'つかいかたを教えて', 'どうやって使う', 'どうすればいい',
            'わからない', '分からない', 'どうしたら', 'どうやったら'
        ]
        
        return any(pattern in message_lower for pattern in help_patterns)
    
    def _handle_help_request(self, message: str) -> str:
        """ヘルプ要求を処理"""
        try:
            # ヘルプクエリを抽出
            query = None
            message_lower = message.lower().strip()
            
            if message_lower.startswith(('help ', 'ヘルプ ')):
                parts = message.split(' ', 1)
                if len(parts) > 1:
                    query = parts[1].strip()
            elif message_lower not in ['help', 'ヘルプ', '助けて', 'たすけて']:
                # 質問形式の場合、キーワードを抽出
                keywords = ['承認', '設定', 'ファイル', 'コマンド', 'モード']
                for keyword in keywords:
                    if keyword in message:
                        query = keyword
                        break
            
            # ヘルプシステムから情報を取得
            help_content = get_help(query)
            
            # 相棒らしい前置きを追加
            if query:
                prefix = f"🤔 「{query}」についてですね！お答えします：\n\n"
            else:
                prefix = "🤖 Duckflow Companionのヘルプシステムです！\n\n"
            
            return prefix + help_content
            
        except Exception as e:
            return f"""
🤔 すみません、ヘルプシステムで問題が発生しました。

基本的な使い方：
- `help` - メインヘルプを表示
- `help 承認` - 承認システムについて
- `help コマンド` - 利用可能なコマンド

何か具体的にお困りのことがあれば、自然な言葉で質問してください！

エラー詳細: {str(e)}
"""
    
    def _load_approval_config(self):
        """承認システムの設定を読み込み"""
        try:
            # 設定ファイルから承認モードを読み込み
            # 実装は後で追加
            pass
        except Exception as e:
            rich_ui.print_message(f"承認設定の読み込みに失敗: {e}", "warning")