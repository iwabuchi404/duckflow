"""
Pecking Order System

階層的タスク管理とTaskProfile統合システム
"""

import logging
from dataclasses import dataclass
from typing import Any

from companion.task_management.task_hierarchy import (
    TaskHierarchy,
    TaskNode,
    TaskPriority,
    TaskProfileResult,
    TaskProfileType,
    TaskStatus,
)


@dataclass
class TaskDecompositionResult:
    """タスク分解結果"""

    main_task: TaskNode
    subtasks: list[TaskNode]
    decomposition_strategy: str
    estimated_complexity: str
    confidence_score: float
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.subtasks is None:
            self.subtasks = []
        if self.metadata is None:
            self.metadata = {}


class PeckingOrder:
    """階層的タスク管理システム（The Pecking Order）"""

    def __init__(self, task_profile_classifier: Any) -> None:
        """Pecking Orderを初期化する。

        Args:
            task_profile_classifier: 既存の分類器インスタンス。現在の分解処理では直接使用しない。
        """
        self.task_profile_classifier = task_profile_classifier
        self.task_hierarchy = TaskHierarchy()
        self.logger = logging.getLogger(__name__)

        # TaskProfile別の最大サブタスク数設定
        self.max_subtasks_config = self._load_max_subtasks_config()

        # 分解戦略の設定
        self.decomposition_strategies = self._load_decomposition_strategies()

    def _load_max_subtasks_config(self) -> dict[TaskProfileType, int]:
        """TaskProfile別の最大サブタスク数設定"""
        return {
            TaskProfileType.CREATION_REQUEST: 7,  # 作成系は多段階
            TaskProfileType.ANALYSIS_REQUEST: 5,  # 分析系は中程度
            TaskProfileType.MODIFICATION_REQUEST: 6,  # 修正系は中程度
            TaskProfileType.SEARCH_REQUEST: 4,  # 検索系は少なめ
            TaskProfileType.GUIDANCE_REQUEST: 3,  # ガイダンス系は少なめ
            TaskProfileType.INFORMATION_REQUEST: 3,  # 情報系は少なめ
        }

    def _load_decomposition_strategies(self) -> dict[TaskProfileType, str]:
        """TaskProfile別の分解戦略"""
        return {
            TaskProfileType.CREATION_REQUEST: "段階的実装戦略",
            TaskProfileType.ANALYSIS_REQUEST: "多角的分析戦略",
            TaskProfileType.MODIFICATION_REQUEST: "安全修正戦略",
            TaskProfileType.SEARCH_REQUEST: "効率探索戦略",
            TaskProfileType.GUIDANCE_REQUEST: "段階的説明戦略",
            TaskProfileType.INFORMATION_REQUEST: "情報収集戦略",
        }

    async def decompose_intent(
        self,
        user_input: str,
        task_profile_result: TaskProfileResult,
        context: dict[str, Any] | None = None,
    ) -> TaskDecompositionResult:
        """
        意図理解結果に基づくタスク分解

        Args:
            user_input: ユーザーの入力
            task_profile_result: TaskProfile分類結果
            context: 追加コンテキスト情報

        Returns:
            タスク分解結果
        """
        try:
            # メインタスクの作成
            main_task = self._create_main_task(user_input, task_profile_result)

            # サブタスクの生成
            subtasks = await self._generate_subtasks(
                user_input, task_profile_result, main_task, context
            )

            # タスク階層に追加
            self.task_hierarchy.add_task(main_task)
            for subtask in subtasks:
                self.task_hierarchy.add_task(subtask)

            # 分解戦略の決定
            strategy = self.decomposition_strategies.get(
                task_profile_result.profile_type, "標準戦略"
            )

            return TaskDecompositionResult(
                main_task=main_task,
                subtasks=subtasks,
                decomposition_strategy=strategy,
                estimated_complexity=task_profile_result.complexity_assessment,
                confidence_score=task_profile_result.confidence,
                metadata={
                    "task_profile": task_profile_result.profile_type.value,
                    "decomposition_method": "llm_based",
                },
            )

        except Exception as e:
            self.logger.error(f"タスク分解エラー: {e}")
            return self._create_fallback_decomposition(
                user_input, task_profile_result, str(e)
            )

    def _create_main_task(
        self, user_input: str, task_profile_result: TaskProfileResult
    ) -> TaskNode:
        """メインタスクの作成"""

        # 優先度の決定
        priority = self._determine_priority(task_profile_result)

        # 複雑度の決定
        complexity = task_profile_result.complexity_assessment

        return TaskNode(
            title=f"メインタスク: {user_input[:50]}...",
            description=user_input,
            priority=priority,
            task_profile=task_profile_result.profile_type,
            complexity=complexity,
            metadata={
                "original_input": user_input,
                "task_profile": task_profile_result.profile_type.value,
                "confidence": task_profile_result.confidence,
            },
        )

    def _determine_priority(
        self, task_profile_result: TaskProfileResult
    ) -> TaskPriority:
        """優先度の決定"""

        # 信頼度に基づく優先度調整
        confidence = task_profile_result.confidence

        if confidence >= 0.9:
            return TaskPriority.HIGH
        elif confidence >= 0.7:
            return TaskPriority.MEDIUM
        else:
            return TaskPriority.LOW

    async def _generate_subtasks(
        self,
        user_input: str,
        task_profile_result: TaskProfileResult,
        main_task: TaskNode,
        context: dict[str, Any] | None,
    ) -> list[TaskNode]:
        """サブタスクの生成"""

        # 最大サブタスク数の取得
        max_subtasks = self.max_subtasks_config.get(task_profile_result.profile_type, 3)

        # TaskProfile別のサブタスク生成戦略
        if task_profile_result.profile_type == TaskProfileType.CREATION_REQUEST:
            subtasks = self._generate_creation_subtasks(user_input, max_subtasks)
        elif task_profile_result.profile_type == TaskProfileType.ANALYSIS_REQUEST:
            subtasks = self._generate_analysis_subtasks(user_input, max_subtasks)
        elif task_profile_result.profile_type == TaskProfileType.MODIFICATION_REQUEST:
            subtasks = self._generate_modification_subtasks(user_input, max_subtasks)
        elif task_profile_result.profile_type == TaskProfileType.SEARCH_REQUEST:
            subtasks = self._generate_search_subtasks(user_input, max_subtasks)
        elif task_profile_result.profile_type == TaskProfileType.GUIDANCE_REQUEST:
            subtasks = self._generate_guidance_subtasks(user_input, max_subtasks)
        else:  # INFORMATION_REQUEST
            subtasks = self._generate_information_subtasks(user_input, max_subtasks)

        # 親タスクIDの設定
        for subtask in subtasks:
            subtask.parent_id = main_task.id

        return subtasks[:max_subtasks]  # 最大数に制限

    def _generate_creation_subtasks(
        self, user_input: str, max_count: int
    ) -> list[TaskNode]:
        """作成系サブタスクの生成"""
        subtasks = [
            TaskNode(
                title="要件分析",
                description="ユーザー要求の詳細分析と仕様の明確化",
                priority=TaskPriority.HIGH,
                complexity="simple",
                metadata={"step": 1, "type": "analysis"},
            ),
            TaskNode(
                title="設計・計画",
                description="実装方法の設計と実行計画の策定",
                priority=TaskPriority.HIGH,
                complexity="moderate",
                metadata={"step": 2, "type": "planning"},
            ),
            TaskNode(
                title="実装・作成",
                description="実際のファイル・コードの作成",
                priority=TaskPriority.HIGH,
                complexity="moderate",
                metadata={"step": 3, "type": "implementation"},
            ),
            TaskNode(
                title="検証・テスト",
                description="作成された内容の検証とテスト",
                priority=TaskPriority.MEDIUM,
                complexity="simple",
                metadata={"step": 4, "type": "verification"},
            ),
            TaskNode(
                title="ドキュメント作成",
                description="使用方法や説明文書の作成",
                priority=TaskPriority.LOW,
                complexity="simple",
                metadata={"step": 5, "type": "documentation"},
            ),
        ]

        return subtasks[:max_count]

    def _generate_analysis_subtasks(
        self, user_input: str, max_count: int
    ) -> list[TaskNode]:
        """分析系サブタスクの生成"""
        subtasks = [
            TaskNode(
                title="対象特定",
                description="分析対象のファイル・コードの特定",
                priority=TaskPriority.HIGH,
                complexity="simple",
                metadata={"step": 1, "type": "identification"},
            ),
            TaskNode(
                title="データ収集",
                description="分析に必要な情報・データの収集",
                priority=TaskPriority.HIGH,
                complexity="moderate",
                metadata={"step": 2, "type": "collection"},
            ),
            TaskNode(
                title="分析実行",
                description="実際の分析処理の実行",
                priority=TaskPriority.HIGH,
                complexity="moderate",
                metadata={"step": 3, "type": "analysis"},
            ),
            TaskNode(
                title="結果評価",
                description="分析結果の評価と問題点の特定",
                priority=TaskPriority.MEDIUM,
                complexity="moderate",
                metadata={"step": 4, "type": "evaluation"},
            ),
            TaskNode(
                title="改善提案",
                description="分析結果に基づく改善提案の作成",
                priority=TaskPriority.MEDIUM,
                complexity="moderate",
                metadata={"step": 5, "type": "proposal"},
            ),
        ]

        return subtasks[:max_count]

    def _generate_modification_subtasks(
        self, user_input: str, max_count: int
    ) -> list[TaskNode]:
        """修正系サブタスクの生成"""
        subtasks = [
            TaskNode(
                title="修正対象特定",
                description="修正が必要な箇所の特定",
                priority=TaskPriority.HIGH,
                complexity="simple",
                metadata={"step": 1, "type": "identification"},
            ),
            TaskNode(
                title="影響範囲分析",
                description="修正による影響範囲の分析",
                priority=TaskPriority.HIGH,
                complexity="moderate",
                metadata={"step": 2, "type": "impact_analysis"},
            ),
            TaskNode(
                title="修正計画策定",
                description="安全な修正のための計画策定",
                priority=TaskPriority.HIGH,
                complexity="moderate",
                metadata={"step": 3, "type": "planning"},
            ),
            TaskNode(
                title="修正実行",
                description="実際の修正処理の実行",
                priority=TaskPriority.HIGH,
                complexity="moderate",
                metadata={"step": 4, "type": "implementation"},
            ),
            TaskNode(
                title="修正検証",
                description="修正内容の検証とテスト",
                priority=TaskPriority.MEDIUM,
                complexity="simple",
                metadata={"step": 5, "type": "verification"},
            ),
            TaskNode(
                title="バックアップ確認",
                description="修正前の状態のバックアップ確認",
                priority=TaskPriority.MEDIUM,
                complexity="simple",
                metadata={"step": 6, "type": "backup"},
            ),
        ]

        return subtasks[:max_count]

    def _generate_search_subtasks(
        self, user_input: str, max_count: int
    ) -> list[TaskNode]:
        """検索系サブタスクの生成"""
        subtasks = [
            TaskNode(
                title="検索条件設定",
                description="検索対象と条件の明確化",
                priority=TaskPriority.HIGH,
                complexity="simple",
                metadata={"step": 1, "type": "setup"},
            ),
            TaskNode(
                title="検索実行",
                description="ファイル・コードの検索実行",
                priority=TaskPriority.HIGH,
                complexity="moderate",
                metadata={"step": 2, "type": "execution"},
            ),
            TaskNode(
                title="結果整理",
                description="検索結果の整理と分類",
                priority=TaskPriority.MEDIUM,
                complexity="simple",
                metadata={"step": 3, "type": "organization"},
            ),
            TaskNode(
                title="関連性評価",
                description="検索結果の関連性と重要度の評価",
                priority=TaskPriority.MEDIUM,
                complexity="moderate",
                metadata={"step": 4, "type": "evaluation"},
            ),
        ]

        return subtasks[:max_count]

    def _generate_guidance_subtasks(
        self, user_input: str, max_count: int
    ) -> list[TaskNode]:
        """ガイダンス系サブタスクの生成"""
        subtasks = [
            TaskNode(
                title="相談内容理解",
                description="ユーザーの相談内容の詳細理解",
                priority=TaskPriority.HIGH,
                complexity="simple",
                metadata={"step": 1, "type": "understanding"},
            ),
            TaskNode(
                title="関連情報収集",
                description="相談内容に関連する情報の収集",
                priority=TaskPriority.HIGH,
                complexity="moderate",
                metadata={"step": 2, "type": "collection"},
            ),
            TaskNode(
                title="アドバイス作成",
                description="具体的で実用的なアドバイスの作成",
                priority=TaskPriority.HIGH,
                complexity="moderate",
                metadata={"step": 3, "type": "advice"},
            ),
        ]

        return subtasks[:max_count]

    def _generate_information_subtasks(
        self, user_input: str, max_count: int
    ) -> list[TaskNode]:
        """情報系サブタスクの生成"""
        subtasks = [
            TaskNode(
                title="情報要求理解",
                description="ユーザーが求めている情報の明確化",
                priority=TaskPriority.HIGH,
                complexity="simple",
                metadata={"step": 1, "type": "understanding"},
            ),
            TaskNode(
                title="情報収集",
                description="要求された情報の収集",
                priority=TaskPriority.HIGH,
                complexity="moderate",
                metadata={"step": 2, "type": "collection"},
            ),
            TaskNode(
                title="情報整理・表示",
                description="収集した情報の整理と分かりやすい表示",
                priority=TaskPriority.MEDIUM,
                complexity="simple",
                metadata={"step": 3, "type": "presentation"},
            ),
        ]

        return subtasks[:max_count]

    def _create_fallback_decomposition(
        self, user_input: str, task_profile_result: TaskProfileResult, error: str
    ) -> TaskDecompositionResult:
        """フォールバック用のタスク分解"""

        # 基本的なメインタスク
        main_task = TaskNode(
            title=f"基本タスク: {user_input[:30]}...",
            description=user_input,
            priority=TaskPriority.MEDIUM,
            task_profile=task_profile_result.profile_type,
            complexity="moderate",
            metadata={"fallback_reason": error},
        )

        # 基本的なサブタスク
        subtasks = [
            TaskNode(
                title="要求理解",
                description="ユーザー要求の基本理解",
                priority=TaskPriority.HIGH,
                complexity="simple",
                parent_id=main_task.id,
                metadata={"step": 1, "type": "basic"},
            ),
            TaskNode(
                title="基本処理",
                description="基本的な処理の実行",
                priority=TaskPriority.HIGH,
                complexity="moderate",
                parent_id=main_task.id,
                metadata={"step": 2, "type": "basic"},
            ),
            TaskNode(
                title="結果提供",
                description="処理結果の提供",
                priority=TaskPriority.MEDIUM,
                complexity="simple",
                parent_id=main_task.id,
                metadata={"step": 3, "type": "basic"},
            ),
        ]

        return TaskDecompositionResult(
            main_task=main_task,
            subtasks=subtasks,
            decomposition_strategy="フォールバック戦略",
            estimated_complexity="moderate",
            confidence_score=0.3,
            metadata={"fallback_reason": error, "decomposition_method": "fallback"},
        )

    def get_task_hierarchy(self) -> TaskHierarchy:
        """タスク階層を取得"""
        return self.task_hierarchy

    def get_current_tasks(self) -> list[TaskNode]:
        """現在実行中のタスクを取得"""
        return self.task_hierarchy.get_tasks_by_status(TaskStatus.IN_PROGRESS)

    def get_pending_tasks(self) -> list[TaskNode]:
        """待機中のタスクを取得"""
        return self.task_hierarchy.get_tasks_by_status(TaskStatus.PENDING)

    def get_completed_tasks(self) -> list[TaskNode]:
        """完了したタスクを取得"""
        return self.task_hierarchy.get_tasks_by_status(TaskStatus.COMPLETED)

    def get_overall_progress(self) -> float:
        """全体の進捗率を取得"""
        return self.task_hierarchy.get_overall_progress()

    def print_current_status(self) -> None:
        """現在のタスク状況を出力する。"""
        print("\n🦆 Pecking Order 現在の状況")
        print(f"総タスク数: {self.task_hierarchy.get_task_count()}")
        print(f"完了タスク数: {self.task_hierarchy.get_completed_task_count()}")
        print(f"全体進捗率: {self.get_overall_progress():.1%}")

        print("\n📋 タスク階層:")
        self.task_hierarchy.print_hierarchy()
