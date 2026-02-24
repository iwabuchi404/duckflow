from typing import List, Optional, Dict, Any, Literal, Union
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
import uuid
from enum import Enum

# --- Enums ---

class SyntaxErrorInfo(BaseModel):
    """直前ターンで発生した構文エラーの情報"""
    error_type: str = Field(description="エラー種別 (例: unknown_tool, missing_param)")
    raw_snippet: str = Field(default='', description="問題のあった出力の抜粋")
    correction_hint: str = Field(default='', description="修正ガイド文")


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"

class AgentPhase(str, Enum):
    IDLE = "IDLE"
    THINKING = "THINKING"
    EXECUTING = "EXECUTING"
    AWAITING_USER = "AWAITING_USER"

class AgentMode(str, Enum):
    """Sym-Ops v3.1 の3モード"""
    PLANNING      = "planning"       # 目標明確・計画立案フェーズ
    INVESTIGATION = "investigation"  # 原因不明・OODAループフェーズ
    TASK          = "task"           # タスク実行フェーズ

# --- Vitals (Soul) ---

class Vitals(BaseModel):
    """アヒルの健康状態 (Sym-Ops v3.1)"""
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="自信 ::c (0.0-1.0)")
    safety: float = Field(1.0, ge=0.0, le=1.0, description="安全度 ::s (0.0-1.0, 0.5未満で確認要求)")
    memory: float = Field(1.0, ge=0.0, le=1.0, description="メモリ使用状況 ::m (0.0-1.0)")
    focus: float = Field(1.0, ge=0.0, le=1.0, description="集中力 ::f (0.0-1.0)")

    def decay(self, amount: float = 0.05):
        """ループごとの自然減衰"""
        self.safety = max(0.0, self.safety - amount)
        self.focus = max(0.0, self.focus - amount)

    def recover(self, amount: float = 0.3):
        """ユーザー応答後の回復"""
        self.safety = min(1.0, self.safety + amount)
        self.focus = min(1.0, self.focus + amount)

# --- Investigation State ---

class InvestigationState(BaseModel):
    """Investigationモードの調査状態"""
    hypothesis: str = Field("", description="現在の仮説")
    hypothesis_attempts: int = Field(0, description="仮説試行回数 (2回失敗でduck_call強制)")
    ooda_cycle: int = Field(0, description="OODAサイクル数")
    observations: List[str] = Field(default_factory=list, description="観察結果ログ")

# --- Pacemaker Intervention ---

class InterventionReason(BaseModel):
    """Pacemakerの介入理由"""
    type: Literal[
        "SAFETY_DEPLETED",
        "LOOP_EXHAUSTED",
        "FOCUS_LOST",
        "ERROR_CASCADE",
        "STAGNATION",
        "CONFIDENCE_LOW",
        "INVESTIGATION_STUCK"
    ]
    message: str
    severity: Literal["critical", "high", "medium", "low"]

# --- Hierarchical Planning Models ---

class Task(BaseModel):
    """最小実行単位"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    result: str = ""
    command: Optional[str] = None # 実行するコマンドがあれば
    file_path: Optional[str] = None # 編集するファイルがあれば
    action: Optional["Action"] = None # 実行するツールアクション (Explicit)

class Step(BaseModel):
    """中期目標 (1つのStepは複数のTaskを持つ)"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    tasks: List[Task] = Field(default_factory=list)
    
    def add_task(self, title: str, description: str = "") -> Task:
        task = Task(title=title, description=description)
        self.tasks.append(task)
        return task

class Plan(BaseModel):
    """長期計画"""
    goal: str
    steps: List[Step] = Field(default_factory=list)
    current_step_index: int = 0
    is_complete: bool = False

    def add_step(self, title: str, description: str = "") -> Step:
        step = Step(title=title, description=description)
        self.steps.append(step)
        return step
    
    def get_current_step(self) -> Optional[Step]:
        if 0 <= self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None

# --- Action Protocol ---

class Action(BaseModel):
    """LLMが生成する単一の行動"""
    name: str = Field(..., description="実行するツール/アクションの名前")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="アクションの引数")
    thought: str = Field(default="", description="このアクションを選んだ理由")

class ActionList(BaseModel):
    """LLMの出力全体"""
    actions: List[Action]
    reasoning: str = Field(..., description="全体的な思考プロセス")
    vitals: Optional[Dict[str, float]] = Field(default=None, description="アヒルのバイタル情報")

# --- Main State ---

class AgentState(BaseModel):
    """エージェントの全状態を保持するSingle Source of Truth"""
    phase: AgentPhase = AgentPhase.IDLE
    vitals: Vitals = Field(default_factory=Vitals)

    # Sym-Ops v3.1 モード管理
    current_mode: AgentMode = AgentMode.PLANNING
    investigation_state: Optional[InvestigationState] = None

    # Context
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)
    current_plan: Optional[Plan] = None

    # Working Memory
    working_directory: str = "."
    known_files: List[str] = Field(default_factory=list)

    # Last Action Result
    last_action_result: Optional[str] = None

    # 直前ターンの構文エラー（次ターンのプロンプトに注入後クリアされる）
    last_syntax_errors: List[SyntaxErrorInfo] = Field(default_factory=list)

    # セッション管理
    session_id: str = Field(
        default_factory=lambda: datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + str(uuid.uuid4())[:4],
        description='セッション識別子（YYYYMMDD_HHMMSS_xxxx 形式）'
    )
    created_at: datetime = Field(default_factory=datetime.now, description='セッション開始日時')
    last_active: datetime = Field(default_factory=datetime.now, description='最終アクティブ日時')
    turn_count: int = Field(default=0, description='ターン数（ユーザー入力回数）')
    
    def add_message(self, role: str, content: str):
        self.conversation_history.append({"role": role, "content": content})
        
    async def add_message_with_pruning(
        self, 
        role: str, 
        content: str, 
        memory_manager: Any = None
    ):
        """
        メッセージを追加し、必要なら履歴を整理
        
        Args:
            role: メッセージのロール ("user", "assistant", "system")
            content: メッセージ内容
            memory_manager: MemoryManagerインスタンス（Noneなら整理しない）
        """
        # 通常の追加
        self.add_message(role, content)
        
        # 整理チェック
        if memory_manager and memory_manager.should_prune(self.conversation_history):
            self.conversation_history, stats = await memory_manager.prune_history(
                self.conversation_history
            )
            
            # 統計ログ (loggerが必要だが、ここではprintか無視)
            if stats.get("pruned"):
                pass # 呼び出し元でログ出力されることを期待、あるいはここでprint

    def update_vitals(self):
        self.vitals.decay()

    def to_prompt_context(self) -> str:
        """プロンプトに埋め込むためのコンテキスト情報を生成"""
        context = []
        context.append(f"Phase: {self.phase.value}")
        context.append(f"Mode: {self.current_mode.value}")
        context.append(
            f"Vitals: Confidence={self.vitals.confidence:.2f}, "
            f"Safety={self.vitals.safety:.2f}, "
            f"Memory={self.vitals.memory:.2f}, "
            f"Focus={self.vitals.focus:.2f}"
        )
        # Investigationモード中は調査状態を追加
        if self.investigation_state:
            inv = self.investigation_state
            context.append(
                f"Investigation: hypothesis_attempts={inv.hypothesis_attempts}/2, "
                f"ooda_cycle={inv.ooda_cycle}, "
                f"hypothesis='{inv.hypothesis}'"
            )
        
        if self.current_plan:
            context.append(f"\nCurrent Plan: {self.current_plan.goal}")
            current_step = self.current_plan.get_current_step()
            if current_step:
                context.append(f"Current Step: {current_step.title} ({current_step.status.value})")
                if current_step.tasks:
                    pending_tasks = [t for t in current_step.tasks if t.status == TaskStatus.PENDING]
                    completed_tasks = [t for t in current_step.tasks if t.status == TaskStatus.COMPLETED]
                    context.append(f"Tasks: {len(completed_tasks)}/{len(current_step.tasks)} completed")
        
        if self.last_action_result:
            context.append(f"\nLast Result:\n{self.last_action_result}")
            
        return "\n".join(context)

    def get_context_mode(self) -> str:
        """
        Sym-Ops v3.1 のモードを返す。
        Returns: "planning", "investigation", or "task"
        """
        return self.current_mode.value

    def enter_investigation_mode(self):
        """Investigationモードへ遷移し、調査状態を初期化する"""
        self.current_mode = AgentMode.INVESTIGATION
        self.investigation_state = InvestigationState()

    def enter_planning_mode(self):
        """Planningモードへ遷移し、調査状態をクリアする"""
        self.current_mode = AgentMode.PLANNING
        self.investigation_state = None

    def enter_task_mode(self):
        """Taskモードへ遷移する"""
        self.current_mode = AgentMode.TASK

    def touch(self) -> None:
        """
        ターン完了時に last_active を更新し turn_count をインクリメントする。
        セッション保存前に呼ぶ。
        """
        self.last_active = datetime.now()
        self.turn_count += 1

    def to_session_dict(self) -> dict:
        """
        セッションファイルへの保存用にJSONシリアライズする。

        Returns:
            全フィールドをJSON互換型に変換した辞書
        """
        return self.model_dump(mode='json')

    @classmethod
    def from_session_dict(cls, data: dict) -> 'AgentState':
        """
        セッションファイルから AgentState を復元する。

        Args:
            data: to_session_dict() で生成したJSON辞書

        Returns:
            復元された AgentState インスタンス
        """
        return cls.model_validate(data)

