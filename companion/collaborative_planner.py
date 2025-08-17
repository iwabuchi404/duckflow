# collaborative_planner.py
"""
Collaborative Planner - 協調的計画機能
Step 3: ユーザーとの共同計画立案システム

ユーザーとの対話を通じて、複雑なタスクの実行計画を事前に立て、
承認を得てから実行する機能を提供する。
"""

import uuid
from typing import Dict, List, Any, Optional, Tuple, Literal
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

from .hierarchical_task_manager import HierarchicalTaskManager, TaskPriority


class PlanStatus(Enum):
    """計画の状態"""
    DRAFT = "draft"              # 下書き
    PROPOSED = "proposed"        # 提案済み
    USER_REVIEWING = "reviewing" # ユーザー確認中
    APPROVED = "approved"        # 承認済み
    REJECTED = "rejected"        # 却下
    MODIFIED = "modified"        # 修正中
    EXECUTING = "executing"      # 実行中
    COMPLETED = "completed"      # 完了
    FAILED = "failed"           # 失敗


@dataclass
class ActionSpec:
    """実行可能なアクション仕様（構造化）"""
    kind: Literal['create', 'write', 'mkdir', 'run', 'read', 'analyze']
    path: Optional[str] = None
    content: Optional[str] = None
    optional: bool = False
    description: str = ""
    
    def __post_init__(self):
        """初期化後の処理 - 欠落項目をテンプレートで充足"""
        if not self.description:
            self.description = self._generate_default_description()
        
        # パスが必要な操作で欠落している場合のデフォルト
        if self.kind in ['create', 'write', 'mkdir'] and not self.path:
            self.path = self._generate_default_path()
        
        # コンテンツが必要な操作で欠落している場合のデフォルト
        if self.kind in ['create', 'write'] and self.content is None:
            self.content = self._generate_default_content()
    
    def _generate_default_description(self) -> str:
        """デフォルトの説明を生成"""
        descriptions = {
            'create': f"ファイル {self.path or 'new_file.txt'} を作成",
            'write': f"ファイル {self.path or 'existing_file.txt'} を更新",
            'mkdir': f"ディレクトリ {self.path or 'new_directory'} を作成",
            'run': f"コマンド実行",
            'read': f"ファイル {self.path or 'target_file.txt'} を読み取り",
            'analyze': f"コード解析を実行"
        }
        return descriptions.get(self.kind, f"{self.kind} 操作を実行")
    
    def _generate_default_path(self) -> str:
        """デフォルトのパスを生成"""
        defaults = {
            'create': 'new_file.txt',
            'write': 'updated_file.txt',
            'mkdir': 'new_directory'
        }
        return defaults.get(self.kind, 'default_target')
    
    def _generate_default_content(self) -> str:
        """デフォルトのコンテンツを生成"""
        if self.kind == 'create':
            return f"# 新規作成されたファイル\n# 作成日時: {datetime.now().isoformat()}\n\n"
        elif self.kind == 'write':
            return f"# 更新されたファイル\n# 更新日時: {datetime.now().isoformat()}\n\n"
        return ""
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "kind": self.kind,
            "path": self.path,
            "content": self.content,
            "optional": self.optional,
            "description": self.description
        }


@dataclass
class TaskEstimate:
    """タスク実行時間の推定"""
    min_duration: int  # 最短時間（秒）
    max_duration: int  # 最長時間（秒）
    complexity: str    # 複雑度 (low/medium/high)
    confidence: float  # 推定信頼度 (0.0-1.0)
    
    @property
    def estimated_duration(self) -> int:
        """推定時間（平均）"""
        return (self.min_duration + self.max_duration) // 2
    
    @property
    def duration_range_str(self) -> str:
        """実行時間の範囲文字列"""
        min_str = self._format_duration(self.min_duration)
        max_str = self._format_duration(self.max_duration)
        return f"{min_str}〜{max_str}"
    
    def _format_duration(self, seconds: int) -> str:
        """秒数を読みやすい形式に変換"""
        if seconds < 60:
            return f"{seconds}秒"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes}分"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            if minutes > 0:
                return f"{hours}時間{minutes}分"
            else:
                return f"{hours}時間"


@dataclass
class PlanStep:
    """計画のステップ"""
    step_id: str
    name: str
    description: str
    estimate: TaskEstimate
    dependencies: List[str] = field(default_factory=list)
    priority: TaskPriority = TaskPriority.NORMAL
    optional: bool = False  # オプションのステップかどうか
    user_input_required: bool = False  # ユーザー入力が必要かどうか
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "step_id": self.step_id,
            "name": self.name,
            "description": self.description,
            "estimate": {
                "duration_range": self.estimate.duration_range_str,
                "complexity": self.estimate.complexity,
                "confidence": self.estimate.confidence
            },
            "dependencies": self.dependencies,
            "priority": self.priority.value,
            "optional": self.optional,
            "user_input_required": self.user_input_required
        }


@dataclass
class ExecutionPlan:
    """実行計画"""
    plan_id: str
    title: str
    description: str
    steps: List[PlanStep]
    status: PlanStatus = PlanStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.now)
    estimated_total_time: Optional[int] = None
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """初期化後の処理"""
        if self.estimated_total_time is None:
            self.estimated_total_time = self._calculate_total_time()
    
    def _calculate_total_time(self) -> int:
        """総実行時間を計算"""
        return sum(step.estimate.estimated_duration for step in self.steps if not step.optional)
    
    def get_total_time_str(self) -> str:
        """総実行時間の文字列表現"""
        estimate = TaskEstimate(
            min_duration=sum(s.estimate.min_duration for s in self.steps if not s.optional),
            max_duration=sum(s.estimate.max_duration for s in self.steps if not s.optional),
            complexity="mixed",
            confidence=min(s.estimate.confidence for s in self.steps)
        )
        return estimate.duration_range_str
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "plan_id": self.plan_id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "estimated_total_time": self.get_total_time_str(),
            "steps": [step.to_dict() for step in self.steps],
            "user_preferences": self.user_preferences
        }
    
    def to_action_specs(self, selection: Optional[int] = None) -> List[ActionSpec]:
        """計画をActionSpecリストに変換
        
        Args:
            selection: ユーザーの選択（1ベース）
            
        Returns:
            List[ActionSpec]: 実行可能なアクション仕様リスト
        """
        action_specs = []
        
        # 選択されたステップのみ、または全ステップを処理
        steps_to_process = self.steps
        if selection is not None and 1 <= selection <= len(self.steps):
            steps_to_process = [self.steps[selection - 1]]
        
        for step in steps_to_process:
            # ステップの内容からActionSpecを推測
            action_spec = self._step_to_action_spec(step)
            if action_spec:
                action_specs.append(action_spec)
        
        return action_specs
    
    def _step_to_action_spec(self, step: PlanStep) -> Optional[ActionSpec]:
        """PlanStepをActionSpecに変換"""
        step_name_lower = step.name.lower()
        step_desc_lower = step.description.lower()
        
        # ファイル作成系
        if any(keyword in step_name_lower for keyword in ['作成', 'create', '新規']):
            return ActionSpec(
                kind='create',
                path=self._extract_file_path(step.description) or 'new_file.txt',
                content=f"# {step.name}\n# {step.description}\n\n",
                description=step.description,
                optional=step.optional
            )
        
        # ファイル更新系
        elif any(keyword in step_name_lower for keyword in ['更新', '修正', 'write', 'update', 'edit']):
            return ActionSpec(
                kind='write',
                path=self._extract_file_path(step.description) or 'updated_file.txt',
                content=f"# 更新: {step.name}\n# {step.description}\n\n",
                description=step.description,
                optional=step.optional
            )
        
        # ディレクトリ作成系
        elif any(keyword in step_name_lower for keyword in ['ディレクトリ', 'フォルダ', 'mkdir', 'directory']):
            return ActionSpec(
                kind='mkdir',
                path=self._extract_file_path(step.description) or 'new_directory',
                description=step.description,
                optional=step.optional
            )
        
        # 解析系
        elif any(keyword in step_name_lower for keyword in ['解析', '分析', 'analyze', 'review']):
            return ActionSpec(
                kind='analyze',
                path=self._extract_file_path(step.description),
                description=step.description,
                optional=step.optional
            )
        
        # 読み取り系
        elif any(keyword in step_name_lower for keyword in ['読み取り', '確認', 'read', 'check']):
            return ActionSpec(
                kind='read',
                path=self._extract_file_path(step.description),
                description=step.description,
                optional=step.optional
            )
        
        # デフォルト（実行系）
        else:
            return ActionSpec(
                kind='run',
                description=step.description,
                optional=step.optional
            )
    
    def _extract_file_path(self, text: str) -> Optional[str]:
        """テキストからファイルパスを抽出"""
        import re
        
        # 一般的なファイルパスパターン
        patterns = [
            r'["\']([^"\']+\.[a-zA-Z0-9]+)["\']',  # クォート内のファイル
            r'([a-zA-Z0-9_/\\.-]+\.[a-zA-Z0-9]+)',  # 拡張子付きファイル
            r'([a-zA-Z0-9_/\\.-]+)',  # 一般的なパス
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        
        return None


class CollaborativePlanner:
    """Step 3: 協調的計画システム"""
    
    def __init__(self):
        """初期化"""
        self.plans: Dict[str, ExecutionPlan] = {}
        self.current_plan_id: Optional[str] = None
        self.hierarchical_manager = HierarchicalTaskManager()
        
        # タスク複雑度の推定データベース（簡易版）
        self.complexity_patterns = {
            # ファイル操作
            "ファイル読み": TaskEstimate(5, 15, "low", 0.9),
            "ファイル作成": TaskEstimate(10, 30, "low", 0.8),
            "ファイル編集": TaskEstimate(15, 60, "medium", 0.7),
            "ディレクトリ作成": TaskEstimate(5, 10, "low", 0.95),
            
            # コード解析
            "コード解析": TaskEstimate(30, 120, "medium", 0.6),
            "レビュー": TaskEstimate(60, 300, "medium", 0.5),
            "リファクタリング": TaskEstimate(300, 1800, "high", 0.4),
            
            # プロジェクト操作
            "プロジェクト設定": TaskEstimate(60, 180, "medium", 0.6),
            "テスト実行": TaskEstimate(30, 180, "medium", 0.7),
            "ビルド": TaskEstimate(60, 300, "medium", 0.6),
            
            # デフォルト
            "デフォルト": TaskEstimate(30, 90, "medium", 0.5)
        }
    
    def analyze_and_create_plan(self, task_description: str) -> str:
        """タスクを分析して実行計画を作成
        
        Args:
            task_description: タスクの説明
            
        Returns:
            str: 作成された計画ID
        """
        plan_id = str(uuid.uuid4())[:8]
        
        # タスクの複雑度を判定
        complexity_level = self._assess_task_complexity(task_description)
        
        if complexity_level == "simple":
            # シンプルなタスクは従来通り即実行
            return None
        
        # 複雑なタスクは計画を作成
        plan = self._create_detailed_plan(plan_id, task_description, complexity_level)
        self.plans[plan_id] = plan
        self.current_plan_id = plan_id
        
        return plan_id
    
    def _assess_task_complexity(self, task_description: str) -> str:
        """タスクの複雑度を評価
        
        Args:
            task_description: タスクの説明
            
        Returns:
            str: 複雑度レベル (simple/medium/complex)
        """
        description_lower = task_description.lower()
        
        # 複雑度判定のキーワード
        complex_keywords = [
            "プロジェクト", "システム", "複数", "全体", "統合", "アーキテクチャ",
            "リファクタリング", "最適化", "設計", "実装", "開発"
        ]
        
        medium_keywords = [
            "解析", "レビュー", "テスト", "チェック", "確認", "修正", "更新"
        ]
        
        # キーワードベースの判定
        if any(keyword in description_lower for keyword in complex_keywords):
            return "complex"
        elif any(keyword in description_lower for keyword in medium_keywords):
            return "medium"
        else:
            return "simple"
    
    def _create_detailed_plan(self, plan_id: str, task_description: str, complexity: str) -> ExecutionPlan:
        """詳細な実行計画を作成
        
        Args:
            plan_id: 計画ID
            task_description: タスクの説明
            complexity: 複雑度
            
        Returns:
            ExecutionPlan: 作成された実行計画
        """
        title = f"実行計画: {task_description[:30]}{'...' if len(task_description) > 30 else ''}"
        
        # 基本的な計画ステップを生成
        steps = self._generate_plan_steps(task_description, complexity)
        
        return ExecutionPlan(
            plan_id=plan_id,
            title=title,
            description=task_description,
            steps=steps,
            status=PlanStatus.PROPOSED
        )
    
    def _generate_plan_steps(self, task_description: str, complexity: str) -> List[PlanStep]:
        """計画ステップを生成
        
        Args:
            task_description: タスクの説明
            complexity: 複雑度
            
        Returns:
            List[PlanStep]: 生成されたステップリスト
        """
        steps = []
        description_lower = task_description.lower()
        
        # ステップ生成の基本パターン
        if complexity == "complex":
            # 複雑なタスクの場合
            steps.extend(self._create_complex_task_steps(description_lower))
        else:
            # 中程度のタスクの場合
            steps.extend(self._create_medium_task_steps(description_lower))
        
        return steps
    
    def _create_complex_task_steps(self, description_lower: str) -> List[PlanStep]:
        """複雑なタスクのステップを作成"""
        steps = []
        step_counter = 1
        
        # 1. 事前分析
        steps.append(PlanStep(
            step_id=f"step_{step_counter}",
            name="事前分析",
            description="タスクの詳細分析と要件の整理",
            estimate=self.complexity_patterns.get("コード解析", self.complexity_patterns["デフォルト"]),
            priority=TaskPriority.HIGH
        ))
        step_counter += 1
        
        # 2. タスク固有のステップ
        if "プロジェクト" in description_lower or "システム" in description_lower:
            steps.append(PlanStep(
                step_id=f"step_{step_counter}",
                name="プロジェクト構造の確認",
                description="プロジェクトファイルの構造と依存関係を確認",
                estimate=self.complexity_patterns.get("プロジェクト設定", self.complexity_patterns["デフォルト"]),
                dependencies=[f"step_{step_counter-1}"]
            ))
            step_counter += 1
        
        if "リファクタリング" in description_lower:
            steps.append(PlanStep(
                step_id=f"step_{step_counter}",
                name="リファクタリング計画",
                description="変更箇所の特定と影響範囲の分析",
                estimate=self.complexity_patterns.get("リファクタリング", self.complexity_patterns["デフォルト"]),
                dependencies=[f"step_{step_counter-1}"]
            ))
            step_counter += 1
        
        # 3. 実行フェーズ
        steps.append(PlanStep(
            step_id=f"step_{step_counter}",
            name="メイン実行",
            description="主要な作業の実行",
            estimate=TaskEstimate(120, 600, "high", 0.4),
            dependencies=[f"step_{step_counter-1}"],
            priority=TaskPriority.HIGH
        ))
        step_counter += 1
        
        # 4. 検証
        steps.append(PlanStep(
            step_id=f"step_{step_counter}",
            name="結果検証",
            description="実行結果の確認とテスト",
            estimate=self.complexity_patterns.get("テスト実行", self.complexity_patterns["デフォルト"]),
            dependencies=[f"step_{step_counter-1}"],
            optional=False
        ))
        
        return steps
    
    def _create_medium_task_steps(self, description_lower: str) -> List[PlanStep]:
        """中程度のタスクのステップを作成"""
        steps = []
        step_counter = 1
        
        # 1. 準備
        steps.append(PlanStep(
            step_id=f"step_{step_counter}",
            name="タスク準備",
            description="必要なファイルやリソースの確認",
            estimate=TaskEstimate(15, 45, "low", 0.8)
        ))
        step_counter += 1
        
        # 2. メイン作業
        if "解析" in description_lower or "レビュー" in description_lower:
            estimate = self.complexity_patterns.get("コード解析", self.complexity_patterns["デフォルト"])
        else:
            estimate = self.complexity_patterns["デフォルト"]
        
        steps.append(PlanStep(
            step_id=f"step_{step_counter}",
            name="メイン作業",
            description="主要なタスクの実行",
            estimate=estimate,
            dependencies=[f"step_{step_counter-1}"],
            priority=TaskPriority.NORMAL
        ))
        step_counter += 1
        
        # 3. 確認
        steps.append(PlanStep(
            step_id=f"step_{step_counter}",
            name="結果確認",
            description="作業結果の確認と整理",
            estimate=TaskEstimate(10, 30, "low", 0.9),
            dependencies=[f"step_{step_counter-1}"]
        ))
        
        return steps
    
    def get_plan_presentation(self, plan_id: str) -> str:
        """計画をユーザー向けに整形して表示用文字列を生成
        
        Args:
            plan_id: 計画ID
            
        Returns:
            str: 表示用文字列
        """
        plan = self.plans.get(plan_id)
        if not plan:
            return "❌ 計画が見つかりません"
        
        presentation = f"""
🗓️ **実行計画の提案**

**タスク:** {plan.description}
**推定時間:** {plan.get_total_time_str()}
**ステップ数:** {len(plan.steps)}個

**実行手順:**
"""
        
        for i, step in enumerate(plan.steps, 1):
            icon = "⭐" if step.priority == TaskPriority.HIGH else "📋"
            optional_mark = " (オプション)" if step.optional else ""
            deps_info = f" (依存: {', '.join(step.dependencies)})" if step.dependencies else ""
            
            presentation += f"\n{i}. {icon} **{step.name}**{optional_mark}"
            presentation += f"\n   {step.description}"
            presentation += f"\n   📊 推定時間: {step.estimate.duration_range_str} (複雑度: {step.estimate.complexity}){deps_info}"
        
        presentation += f"""

**質問:**
- この計画で進めてよろしいですか？
- 順序を変更したい部分はありますか？
- スキップしたいステップはありますか？

**コマンド:**
- `承認` または `approve` - 計画を承認して実行開始
- `修正` または `modify` - 計画の修正を相談
- `拒否` または `reject` - 計画を却下
"""
        
        return presentation.strip()
    
    def process_user_feedback(self, plan_id: str, feedback: str) -> Tuple[bool, str]:
        """ユーザーフィードバックを処理
        
        Args:
            plan_id: 計画ID
            feedback: ユーザーのフィードバック
            
        Returns:
            Tuple[bool, str]: (処理成功, レスポンスメッセージ)
        """
        plan = self.plans.get(plan_id)
        if not plan:
            return False, "❌ 計画が見つかりません"
        
        feedback_lower = feedback.lower().strip()
        
        # 承認
        if feedback_lower in ['承認', 'approve', 'ok', 'yes', 'はい', 'いいよ', 'お願いします']:
            plan.status = PlanStatus.APPROVED
            return True, "✅ 計画が承認されました！実行を開始します。"
        
        # 却下
        elif feedback_lower in ['拒否', 'reject', 'no', 'いいえ', 'やめて', 'キャンセル']:
            plan.status = PlanStatus.REJECTED
            return True, "❌ 計画が却下されました。別のアプローチを検討しましょう。"
        
        # 修正要求
        elif feedback_lower in ['修正', 'modify', '変更', '調整']:
            plan.status = PlanStatus.MODIFIED
            return True, "🔧 計画の修正を承りました。どの部分を変更したいですか？"
        
        # 具体的な修正指示の解析
        else:
            modification_result = self._process_modification_request(plan, feedback)
            return modification_result
    
    def _process_modification_request(self, plan: ExecutionPlan, request: str) -> Tuple[bool, str]:
        """修正要求を処理
        
        Args:
            plan: 実行計画
            request: 修正要求
            
        Returns:
            Tuple[bool, str]: (処理成功, レスポンスメッセージ)
        """
        request_lower = request.lower()
        
        # 順序変更
        if "順序" in request_lower or "順番" in request_lower:
            return True, "📝 順序の変更を承りました。どのステップをどこに移動したいですか？"
        
        # ステップのスキップ
        if "スキップ" in request_lower or "飛ばし" in request_lower or "省略" in request_lower:
            return True, "⏭️ ステップのスキップを承りました。どのステップを省略しますか？"
        
        # 時間の調整
        if "時間" in request_lower or "早く" in request_lower or "遅く" in request_lower:
            return True, "⏰ 実行時間の調整を承りました。どのような変更をお望みですか？"
        
        # その他の修正要求
        plan.status = PlanStatus.MODIFIED
        return True, f"🔧 修正要求を受け付けました: '{request}'\n詳細な調整方法を検討します。"
    
    def convert_plan_to_hierarchical_tasks(self, plan_id: str) -> Optional[str]:
        """計画を階層タスクに変換
        
        Args:
            plan_id: 計画ID
            
        Returns:
            Optional[str]: 作成された親タスクID
        """
        plan = self.plans.get(plan_id)
        if not plan or plan.status != PlanStatus.APPROVED:
            return None
        
        # 親タスクを作成
        parent_task_id = self.hierarchical_manager.create_parent_task(
            name=plan.title,
            description=plan.description,
            priority=TaskPriority.NORMAL
        )
        
        # 各ステップを子タスクとして追加
        for step in plan.steps:
            self.hierarchical_manager.add_sub_task(
                parent_task_id=parent_task_id,
                name=step.name,
                description=step.description,
                priority=step.priority,
                depends_on=step.dependencies
            )
        
        plan.status = PlanStatus.EXECUTING
        return parent_task_id
    
    def get_current_plan(self) -> Optional[ExecutionPlan]:
        """現在の計画を取得"""
        if not self.current_plan_id:
            return None
        return self.plans.get(self.current_plan_id)
    
    def list_plans(self) -> List[Dict[str, Any]]:
        """すべての計画をリスト形式で取得"""
        return [plan.to_dict() for plan in self.plans.values()]