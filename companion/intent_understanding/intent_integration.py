"""
Intent Integration System

LLMベース意図理解 + TaskProfile + Pecking Order統合システム
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from companion.intent_understanding.llm_intent_analyzer import LLMIntentAnalyzer, IntentAnalysis
from companion.intent_understanding.task_profile_classifier import TaskProfileClassifier, TaskProfileResult
from companion.task_management.pecking_order import PeckingOrder, TaskDecompositionResult
# LLMクライアントは動的にインポート（既存アダプターまたは新クライアント）


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
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.next_actions is None:
            self.next_actions = []
        if self.metadata is None:
            self.metadata = {}


class IntentUnderstandingSystem:
    """統合意図理解システム"""
    
    def __init__(self, llm_client):
        """統合システムを初期化"""
        self.llm_client = llm_client
        
        # 各コンポーネントの初期化
        self.intent_analyzer = LLMIntentAnalyzer(llm_client)
        self.task_profile_classifier = TaskProfileClassifier(llm_client)
        self.pecking_order = PeckingOrder(self.task_profile_classifier)
        
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
                user_input, intent_analysis, task_profile, task_decomposition
            )
            
            self.logger.info(f"意図理解完了: 信頼度 {result.overall_confidence:.2f}")
            return result
            
        except Exception as e:
            self.logger.error(f"統合意図理解エラー: {e}")
            return self._create_fallback_result(user_input, str(e))
    
    def _integrate_results(
        self,
        user_input: str,
        intent_analysis: IntentAnalysis,
        task_profile: TaskProfileResult,
        task_decomposition: TaskDecompositionResult
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
            metadata={
                "integration_method": "unified_understanding",
                "timestamp": self._get_current_timestamp()
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
