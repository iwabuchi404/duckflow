"""
Intent Integration System

LLMベース意図理解 + TaskProfile + Pecking Order統合システム
"""

import logging
import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

from companion.intent_understanding.llm_intent_analyzer import LLMIntentAnalyzer, IntentAnalysis
from companion.intent_understanding.task_profile_classifier import TaskProfileClassifier, TaskProfileResult
from companion.task_management.pecking_order import PeckingOrder, TaskDecompositionResult
# LLMクライアントは動的にインポート（既存アダプターまたは新クライアント）


class RouteType(Enum):
    """ルーティングタイプの定義"""
    EXECUTION = "execution"           # ファイル操作などの実行
    DIRECT_RESPONSE = "direct_response"  # 直接応答
    CLARIFICATION = "clarification"   # 詳細確認
    SAFE_DEFAULT = "safe_default"     # 安全なデフォルト提案


class RiskLevel(Enum):
    """リスクレベルの定義"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PrerequisiteStatus(Enum):
    """前提条件の状態"""
    READY = "ready"                   # 実行準備完了
    NEEDS_CLARIFICATION = "needs_clarification"  # 詳細確認が必要
    INSUFFICIENT_INFO = "insufficient_info"       # 情報不足


@dataclass
class IntentUnderstandingResult:
    """統合意図理解結果"""
    user_input: str
    intent_analysis: IntentAnalysis
    task_profile: TaskProfileResult
    task_decomposition: TaskDecompositionResult
    overall_confidence: float
    processing_strategy: str
    next_actions: List[str]
    # ルーティング情報（新規追加）
    route_type: RouteType
    risk_level: RiskLevel
    prerequisite_status: PrerequisiteStatus
    routing_reason: str
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.next_actions is None:
            self.next_actions = []
        if self.metadata is None:
            self.metadata = {}


class OptionResolver:
    """選択入力リゾルバ - ユーザーの選択入力を正規化"""
    
    @staticmethod
    def parse_selection(text: str) -> Optional[int]:
        """選択入力をパースして選択番号を返す
        
        Args:
            text: ユーザーの入力テキスト
            
        Returns:
            Optional[int]: 選択番号（1ベース）、解釈できない場合はNone
        """
        if not text or not text.strip():
            return None
            
        # 正規化: 全角半角統一、空白・句読点除去
        import re
        normalized = re.sub(r'[　\s\.,。、]', '', text.strip())
        normalized = normalized.translate(str.maketrans('１２３４５６７８９０', '1234567890'))
        normalized = normalized.lower()
        
        # 選択パターンのマッピング（厳密な選択入力のみ）
        selection_mapping = {
            # 数字
            "1": 1, "2": 2, "3": 3, "4": 4, "5": 5,
            # 日本語数字
            "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
            "１": 1, "２": 2, "３": 3, "４": 4, "５": 5,
            # デフォルト系（明確に選択を指している場合のみ）
            "デフォルト": 1, "既定": 1, "推奨": 1, "おすすめ": 1,
            "default": 1, "recommended": 1,
            # 位置系（明確に選択肢を指している場合のみ）
            "上": 1, "一番上": 1, "最初": 1, "first": 1, "top": 1,
            "下": 2, "二番目": 2, "次": 2, "second": 2,
            # 承認系（プラン提示後の承認のみ）
            "はい": 1, "yes": 1, "ok": 1, "いいよ": 1, 
            "実行": 1, "進める": 1, "続行": 1, "go": 1, "proceed": 1,
            # より自然な承認表現（プラン提示後のみ）
            "それで": 1, "それでお願いします": 1, "それでいいです": 1,
            "了解": 1, "わかりました": 1, "承知": 1, "りょうかい": 1
        }
        
        # 直接マッチング
        if normalized in selection_mapping:
            return selection_mapping[normalized]
        
        # 数字の抽出を試行
        number_match = re.search(r'(\d+)', normalized)
        if number_match:
            try:
                num = int(number_match.group(1))
                if 1 <= num <= 9:  # 1-9の範囲のみ有効
                    return num
            except ValueError:
                pass
        
        # 「で」「を」などの助詞付きパターン + 部分マッチング
        for pattern, value in selection_mapping.items():
            if pattern in normalized:
                return value
        
        # より柔軟な承認表現の検出（プラン提示後のみ有効）
        approval_patterns = [
            "^ok$", "^それでいいです$", "^それで$", "^進めて$", "^続けて$"
        ]
        
        for pattern in approval_patterns:
            if re.search(pattern, normalized):
                return 1  # デフォルト選択として扱う
        
        return None
    
    @staticmethod
    def is_selection_input(text: str) -> bool:
        """入力が選択入力かどうかを判定"""
        return OptionResolver.parse_selection(text) is not None


class IntentUnderstandingSystem:
    """統合意図理解システム"""
    
    def __init__(self, llm_client):
        """統合システムを初期化"""
        self.llm_client = llm_client
        
        # 各コンポーネントの初期化
        self.intent_analyzer = LLMIntentAnalyzer(llm_client)
        self.task_profile_classifier = TaskProfileClassifier(llm_client)
        self.pecking_order = PeckingOrder(self.task_profile_classifier)
        self.option_resolver = OptionResolver()
        
        self.logger = logging.getLogger(__name__)
        
        # システム設定
        self.config = self._load_system_config()
    
    def _load_system_config(self) -> Dict[str, Any]:
        """システム設定の読み込み"""
        return {
            "llm_confidence_threshold": 0.7,
            "fallback_enabled": True,
            "max_retry_attempts": 3,
            "context_window_size": 5,  # 対話履歴の保持数
            "enable_debug_logging": True
        }
    
    async def understand_intent(
        self, 
        user_input: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> IntentUnderstandingResult:
        """
        統合意図理解の実行
        
        Args:
            user_input: ユーザーの入力
            context: 追加コンテキスト情報
            
        Returns:
            統合意図理解結果
        """
        try:
            self.logger.info(f"意図理解開始: {user_input[:50]}...")
            
            # Phase 0: 選択入力の検出と処理（プラン保留時のみ有効）
            plan_pending = bool(context and context.get("plan_state", {}).get("pending"))
            if plan_pending:
                selection = self.option_resolver.parse_selection(user_input)
                if selection is not None:
                    self.logger.info(f"選択入力を検出: {selection}")
                    self.logger.info(f"コンテキスト: {context}")
                    self.logger.info("既存プランの実行に転送")
                    result = self._create_execution_result(user_input, selection, context)
                    self.logger.info(f"実行結果作成完了: route_type={result.route_type}, force_execution={result.metadata.get('force_execution')}")
                    return result
            
            # Phase 1: LLM意図分析
            intent_analysis = await self.intent_analyzer.analyze_intent(user_input, context)
            self.logger.info(f"意図分析完了: {intent_analysis.primary_intent.value}")
            
            # Phase 2: TaskProfile分類
            task_profile = await self.task_profile_classifier.classify(user_input, context)
            self.logger.info(f"TaskProfile分類完了: {task_profile.profile_type.value}")
            
            # Phase 3: タスク分解（Pecking Order）
            task_decomposition = await self.pecking_order.decompose_intent(
                user_input, task_profile, context
            )
            self.logger.info(f"タスク分解完了: {len(task_decomposition.subtasks)}個のサブタスク")
            
            # Phase 4: 結果の統合と最適化
            result = self._integrate_results(
                user_input, intent_analysis, task_profile, task_decomposition, context
            )
            
            self.logger.info(f"意図理解完了: 信頼度 {result.overall_confidence:.2f}")
            return result
            
        except Exception as e:
            self.logger.error(f"統合意図理解エラー: {e}")
            return self._create_fallback_result(user_input, str(e))
    
    def _create_execution_result(
        self, 
        user_input: str, 
        selection: int, 
        context: Dict[str, Any]
    ) -> IntentUnderstandingResult:
        """選択入力に基づく実行結果を作成"""
        from companion.intent_understanding.llm_intent_analyzer import IntentType, ComplexityLevel, IntentAnalysis
        from companion.intent_understanding.task_profile_classifier import TaskProfileType, TaskProfileResult
        
        # 実行用の意図分析を作成
        intent_analysis = IntentAnalysis(
            primary_intent=IntentType.CREATION_REQUEST,
            secondary_intents=[],
            context_requirements=[],
            execution_complexity=ComplexityLevel.SIMPLE,
            confidence_score=0.9,
            reasoning="選択入力による実行要求",
            detected_targets=[],
            suggested_approach="選択されたプランの実行"
        )
        
        # 実行用のタスクプロファイルを作成
        task_profile = TaskProfileResult(
            profile_type=TaskProfileType.CREATION_REQUEST,
            confidence=0.9,
            reasoning="選択入力による実行要求",
            detected_intent="execution_request",
            complexity_assessment="simple",
            suggested_approach="direct_execution",
            context_requirements=[],
            detected_targets=[],
            metadata={}
        )
        
        # 実行用のタスク分解を作成（簡略化）
        from companion.task_management.pecking_order import TaskDecompositionResult
        task_decomposition = TaskDecompositionResult(
            main_task=None,  # 簡略化
            subtasks=[],
            decomposition_strategy="selected_plan_execution",
            estimated_complexity="simple",
            confidence_score=0.9,
            metadata={}
        )
        
        # プランが保留されているときのみ強制実行を許可
        force_exec = bool(context.get("plan_state", {}).get("pending"))

        return IntentUnderstandingResult(
            user_input=user_input,
            intent_analysis=intent_analysis,
            task_profile=task_profile,
            task_decomposition=task_decomposition,
            overall_confidence=0.9,
            processing_strategy="選択されたプランの実行",
            next_actions=[f"選択 {selection} のプランを実行"],
            route_type=RouteType.EXECUTION,
            risk_level=RiskLevel.MEDIUM,
            prerequisite_status=PrerequisiteStatus.READY,
            routing_reason=f"ユーザー選択 {selection} による実行ルート",
            metadata={
                "selection": selection,
                "execution_type": "selected_plan",
                "plan_context": context.get("plan_state", {}),
                "timestamp": self._get_current_timestamp(),
                "force_execution": force_exec  # 強制実行は保留プランがある場合のみ
            }
        )
    
    def _integrate_results(
        self,
        user_input: str,
        intent_analysis: IntentAnalysis,
        task_profile: TaskProfileResult,
        task_decomposition: TaskDecompositionResult,
        context: Optional[Dict[str, Any]] = None
    ) -> IntentUnderstandingResult:
        """結果の統合と最適化"""
        
        # 全体の信頼度を計算
        overall_confidence = self._calculate_overall_confidence(
            intent_analysis, task_profile, task_decomposition
        )
        
        # 処理戦略の決定
        processing_strategy = self._determine_processing_strategy(
            intent_analysis, task_profile, task_decomposition
        )
        
        # ルーティング決定（新規追加）
        routing_result = self._determine_routing(
            intent_analysis, task_profile, task_decomposition, context
        )
        
        # 次のアクションの決定
        next_actions = self._determine_next_actions(
            intent_analysis, task_profile, task_decomposition
        )
        
        return IntentUnderstandingResult(
            user_input=user_input,
            intent_analysis=intent_analysis,
            task_profile=task_profile,
            task_decomposition=task_decomposition,
            overall_confidence=overall_confidence,
            processing_strategy=processing_strategy,
            next_actions=next_actions,
            # ルーティング情報（新規追加）
            route_type=routing_result["route_type"],
            risk_level=routing_result["risk_level"],
            prerequisite_status=routing_result["prerequisite_status"],
            routing_reason=routing_result["routing_reason"],
            metadata={
                "integration_method": "unified_understanding",
                "timestamp": self._get_current_timestamp(),
                "routing_applied": True
            }
        )
    
    def _calculate_overall_confidence(
        self,
        intent_analysis: IntentAnalysis,
        task_profile: TaskProfileResult,
        task_decomposition: TaskDecompositionResult
    ) -> float:
        """全体の信頼度を計算"""
        
        # 各コンポーネントの信頼度
        intent_confidence = intent_analysis.confidence_score
        profile_confidence = task_profile.confidence
        decomposition_confidence = task_decomposition.confidence_score
        
        # 重み付き平均（意図分析を重視）
        weights = [0.4, 0.3, 0.3]
        overall_confidence = (
            intent_confidence * weights[0] +
            profile_confidence * weights[1] +
            decomposition_confidence * weights[2]
        )
        
        return min(1.0, max(0.0, overall_confidence))
    
    def _determine_routing(
        self,
        intent_analysis: IntentAnalysis,
        task_profile: TaskProfileResult,
        task_decomposition: TaskDecompositionResult,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """ルーティング決定表による処理方法の決定
        
        Args:
            intent_analysis: 意図分析結果
            task_profile: タスクプロファイル結果
            task_decomposition: タスク分解結果
            
        Returns:
            Dict: ルーティング決定結果
        """
        # 基本パラメータ
        profile_type = task_profile.profile_type.value
        confidence = intent_analysis.confidence_score
        
        # リスクレベルの評価
        risk_level = self._evaluate_risk_level(intent_analysis, task_profile, task_decomposition)
        
        # 前提条件の状態評価
        prerequisite_status = self._evaluate_prerequisites(intent_analysis, task_profile)
        
        # ルーティング決定表の適用
        route_type, routing_reason = self._apply_routing_table(
            profile_type, confidence, risk_level, prerequisite_status, context
        )
        
        return {
            "route_type": route_type,
            "risk_level": risk_level,
            "prerequisite_status": prerequisite_status,
            "routing_reason": routing_reason
        }
    
    def _evaluate_risk_level(
        self,
        intent_analysis: IntentAnalysis,
        task_profile: TaskProfileResult,
        task_decomposition: TaskDecompositionResult
    ) -> RiskLevel:
        """リスクレベルの評価"""
        profile_type = task_profile.profile_type.value
        complexity = intent_analysis.execution_complexity.value
        
        # ファイル操作系は中〜高リスク
        if profile_type in ["creation_request", "modification_request"]:
            if complexity == "complex":
                return RiskLevel.HIGH
            else:
                return RiskLevel.MEDIUM
        
        # 分析・検索系は低リスク
        elif profile_type in ["analysis_request", "search_request", "information_request"]:
            return RiskLevel.LOW
            
        # ガイダンス系は低リスク
        elif profile_type == "guidance_request":
            return RiskLevel.LOW
            
        # 不明な場合は高リスクと判定
        else:
            return RiskLevel.HIGH
    
    def _evaluate_prerequisites(
        self,
        intent_analysis: IntentAnalysis,
        task_profile: TaskProfileResult
    ) -> PrerequisiteStatus:
        """前提条件の状態評価"""
        confidence = intent_analysis.confidence_score
        abstraction_level = getattr(intent_analysis, 'abstraction_level', 'medium')
        
        # 高信頼度かつ具体的 → 実行準備完了
        if confidence >= 0.8 and abstraction_level in ["low", "medium"]:
            return PrerequisiteStatus.READY
            
        # 中信頼度または抽象度高 → 詳細確認が必要
        elif confidence >= 0.5 or abstraction_level == "high":
            return PrerequisiteStatus.NEEDS_CLARIFICATION
            
        # 低信頼度 → 情報不足
        else:
            return PrerequisiteStatus.INSUFFICIENT_INFO
    
    def _apply_routing_table(
        self,
        profile_type: str,
        confidence: float,
        risk_level: RiskLevel,
        prerequisite_status: PrerequisiteStatus,
        context: Optional[Dict[str, Any]] = None
    ) -> tuple[RouteType, str]:
        """ルーティング決定表の適用
        
        Args:
            profile_type: タスクプロファイルタイプ
            confidence: 信頼度スコア
            risk_level: リスクレベル
            prerequisite_status: 前提条件の状態
            context: 追加コンテキスト情報
            
        Returns:
            tuple: (ルートタイプ, 決定理由)
        """
        
        # コンテキストベースの優先ルーティング
        if context:
            plan_state = context.get("plan_state", {})
            if plan_state.get("pending") and prerequisite_status == PrerequisiteStatus.READY:
                return RouteType.EXECUTION, "保留中のプランが存在し前提条件が満たされている → 実行ルート"
        # Rule 1: creation/modification系は基本的にExecution
        if profile_type in ["creation_request", "modification_request"]:
            if prerequisite_status == PrerequisiteStatus.READY and confidence >= 0.7:
                return RouteType.EXECUTION, f"作成/修正要求（信頼度: {confidence:.2f}）→ 実行ルート"
            else:
                return RouteType.CLARIFICATION, f"作成/修正要求だが前提条件不足 → 詳細確認"
        
        # Rule 2: guidance系は基本的にDirectResponse
        elif profile_type == "guidance_request":
            return RouteType.DIRECT_RESPONSE, "ガイダンス要求 → 直接応答"
        
        # Rule 3: 分析・検索系は信頼度に基づく
        elif profile_type in ["analysis_request", "search_request", "information_request"]:
            if confidence >= 0.6:
                return RouteType.EXECUTION, f"分析/検索要求（信頼度: {confidence:.2f}）→ 実行ルート"
            else:
                return RouteType.CLARIFICATION, f"分析/検索要求だが信頼度不足 → 詳細確認"
        
        # Rule 4: unknown/high-abstract → Safe-Default
        else:
            if risk_level == RiskLevel.LOW and confidence >= 0.5:
                return RouteType.SAFE_DEFAULT, "不明な要求だが低リスク → 安全なデフォルト提案"
            else:
                return RouteType.CLARIFICATION, "不明な要求かつ高リスク → 詳細確認"
    
    def _determine_processing_strategy(
        self,
        intent_analysis: IntentAnalysis,
        task_profile: TaskProfileResult,
        task_decomposition: TaskDecompositionResult
    ) -> str:
        """処理戦略の決定"""
        
        # 複雑度に基づく戦略選択
        complexity = intent_analysis.execution_complexity.value
        
        if complexity == "complex":
            return "段階的実行戦略: 複雑なタスクを段階的に処理"
        elif complexity == "moderate":
            return "並行実行戦略: 中程度のタスクを並行処理"
        else:
            return "直接実行戦略: 単純なタスクを直接処理"
    
    def _determine_next_actions(
        self,
        intent_analysis: IntentAnalysis,
        task_profile: TaskProfileResult,
        task_decomposition: TaskDecompositionResult
    ) -> List[str]:
        """次のアクションの決定"""
        
        actions = []
        
        # 信頼度に基づくアクション
        if intent_analysis.confidence_score >= 0.8:
            actions.append("高信頼度: 直接実行を推奨")
        elif intent_analysis.confidence_score >= 0.6:
            actions.append("中信頼度: 確認後実行を推奨")
        else:
            actions.append("低信頼度: 詳細確認が必要")
        
        # TaskProfile別のアクション
        profile_actions = {
            "creation_request": "作成計画の詳細化",
            "analysis_request": "分析対象の明確化",
            "modification_request": "修正内容の確認",
            "search_request": "検索条件の最適化",
            "guidance_request": "相談内容の整理",
            "information_request": "情報範囲の特定"
        }
        
        profile_action = profile_actions.get(task_profile.profile_type.value, "標準処理")
        actions.append(f"TaskProfile: {profile_action}")
        
        # サブタスク数に基づくアクション
        subtask_count = len(task_decomposition.subtasks)
        if subtask_count > 5:
            actions.append("多段階処理: 優先順位の設定が必要")
        elif subtask_count > 3:
            actions.append("段階的処理: 順序の最適化を推奨")
        else:
            actions.append("シンプル処理: 直接実行可能")
        
        return actions
    
    def _create_fallback_result(self, user_input: str, error: str) -> IntentUnderstandingResult:
        """フォールバック用の結果作成"""
        
        # 基本的な意図分析
        fallback_intent = self.intent_analyzer._create_fallback_analysis(user_input, error)
        
        # 基本的なTaskProfile
        fallback_profile = self.task_profile_classifier.rule_classifier.classify(user_input)
        
        # 基本的なタスク分解
        fallback_decomposition = self.pecking_order._create_fallback_decomposition(
            user_input, fallback_profile, error
        )
        
        return IntentUnderstandingResult(
            user_input=user_input,
            intent_analysis=fallback_intent,
            task_profile=fallback_profile,
            task_decomposition=fallback_decomposition,
            overall_confidence=0.3,
            processing_strategy="フォールバック戦略: エラー処理",
            next_actions=["エラーの解決", "基本処理の実行"],
            # フォールバック時のルーティング情報
            route_type=RouteType.CLARIFICATION,
            risk_level=RiskLevel.HIGH,
            prerequisite_status=PrerequisiteStatus.INSUFFICIENT_INFO,
            routing_reason=f"エラーによるフォールバック: {error}",
            metadata={
                "fallback_reason": error,
                "integration_method": "fallback"
            }
        )
    
    def _get_current_timestamp(self) -> str:
        """現在のタイムスタンプを取得"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def get_system_status(self) -> Dict[str, Any]:
        """システムの状態を取得"""
        return {
            "llm_available": getattr(self.llm_client, 'is_available', lambda: True)(),
            "intent_analyzer_status": "active",
            "task_profile_classifier_status": "active",
            "pecking_order_status": "active",
            "total_tasks": self.pecking_order.task_hierarchy.get_task_count(),
            "completed_tasks": self.pecking_order.task_hierarchy.get_completed_task_count(),
            "overall_progress": self.pecking_order.get_overall_progress(),
            "system_config": self.config
        }
    
    def update_config(self, new_config: Dict[str, Any]):
        """システム設定の更新"""
        self.config.update(new_config)
        
        # 各コンポーネントの設定も更新
        if "llm_confidence_threshold" in new_config:
            self.task_profile_classifier.set_classification_mode(
                True, new_config["llm_confidence_threshold"]
            )
        
        if "fallback_enabled" in new_config:
            self.task_profile_classifier.enable_fallback(new_config["fallback_enabled"])
        
        self.logger.info(f"システム設定を更新: {new_config}")
    
    def print_understanding_summary(self, result: IntentUnderstandingResult):
        """意図理解結果のサマリー表示"""
        print(f"\n🦆 **統合意図理解結果**")
        print(f"📝 ユーザー入力: {result.user_input}")
        print(f"🎯 主要意図: {result.intent_analysis.primary_intent.value}")
        print(f"📊 TaskProfile: {result.task_profile.profile_type.value}")
        print(f"🔍 信頼度: {result.overall_confidence:.2%}")
        print(f"⚡ 処理戦略: {result.processing_strategy}")
        
        # ルーティング情報（新規追加）
        print(f"\n🚦 **ルーティング決定**")
        print(f"📍 ルート: {result.route_type.value}")
        print(f"⚠️ リスク: {result.risk_level.value}")
        print(f"✅ 前提条件: {result.prerequisite_status.value}")
        print(f"💭 決定理由: {result.routing_reason}")
        
        print(f"\n📋 サブタスク数: {len(result.task_decomposition.subtasks)}")
        print(f"🔄 分解戦略: {result.task_decomposition.decomposition_strategy}")
        
        print(f"\n➡️ 次のアクション:")
        for i, action in enumerate(result.next_actions, 1):
            print(f"  {i}. {action}")
        
        print(f"\n📈 システム状態:")
        status = self.get_system_status()
        print(f"  - LLM利用可能: {status['llm_available']}")
        print(f"  - 総タスク数: {status['total_tasks']}")
        print(f"  - 全体進捗: {status['overall_progress']:.1%}")
    
    def get_task_execution_plan(self, result: IntentUnderstandingResult) -> Dict[str, Any]:
        """タスク実行計画の取得"""
        return {
            "main_task": {
                "id": result.task_decomposition.main_task.id,
                "title": result.task_decomposition.main_task.title,
                "priority": result.task_decomposition.main_task.priority.value,
                "complexity": result.task_decomposition.main_task.complexity
            },
            "subtasks": [
                {
                    "id": subtask.id,
                    "title": subtask.title,
                    "priority": subtask.priority.value,
                    "step": subtask.metadata.get("step", 0)
                }
                for subtask in result.task_decomposition.subtasks
            ],
            "execution_order": self._determine_execution_order(result.task_decomposition),
            "estimated_duration": self._estimate_total_duration(result.task_decomposition),
            "critical_path": self._identify_critical_path(result.task_decomposition)
        }
    
    def _determine_execution_order(self, decomposition: TaskDecompositionResult) -> List[str]:
        """実行順序の決定"""
        # ステップ番号でソート
        sorted_subtasks = sorted(
            decomposition.subtasks,
            key=lambda x: x.metadata.get("step", 0)
        )
        return [subtask.id for subtask in sorted_subtasks]
    
    def _estimate_total_duration(self, decomposition: TaskDecompositionResult) -> int:
        """総所要時間の推定（分単位）"""
        total_duration = 0
        
        # メインタスクの推定時間
        if decomposition.main_task.estimated_duration:
            total_duration += decomposition.main_task.estimated_duration
        
        # サブタスクの推定時間
        for subtask in decomposition.subtasks:
            if subtask.estimated_duration:
                total_duration += subtask.estimated_duration
            else:
                # デフォルト推定時間
                complexity_duration = {
                    "simple": 5,
                    "moderate": 15,
                    "complex": 30
                }
                total_duration += complexity_duration.get(subtask.complexity, 15)
        
        return total_duration
    
    def _identify_critical_path(self, decomposition: TaskDecompositionResult) -> List[str]:
        """クリティカルパスの特定"""
        critical_tasks = []
        
        # 高優先度のタスクをクリティカルパスとして特定
        for subtask in decomposition.subtasks:
            if subtask.priority.value in ["high", "critical"]:
                critical_tasks.append(subtask.id)
        
        # メインタスクも含める
        critical_tasks.insert(0, decomposition.main_task.id)
        
        return critical_tasks
