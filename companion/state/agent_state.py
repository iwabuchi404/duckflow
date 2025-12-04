from typing import List, Optional, Dict, Any, Literal, Union
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
import uuid
from enum import Enum

# --- Enums ---

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

# --- Vitals (Soul) ---

class Vitals(BaseModel):
    """アヒルの健康状態"""
    mood: float = Field(1.0, ge=0.0, le=1.0, description="機嫌 (0.0-1.0)")
    focus: float = Field(1.0, ge=0.0, le=1.0, description="集中力 (0.0-1.0)")
    stamina: float = Field(1.0, ge=0.0, le=1.0, description="体力 (0.0-1.0)")
    
    def decay(self, amount: float = 0.05):
        self.stamina = max(0.0, self.stamina - amount)
        self.focus = max(0.0, self.focus - amount)

    def recover(self, amount: float = 0.3):
        self.stamina = min(1.0, self.stamina + amount)
        self.focus = min(1.0, self.focus + amount)

# --- Pacemaker Intervention ---

class InterventionReason(BaseModel):
    """Pacemakerの介入理由"""
    type: Literal[
        "STAMINA_DEPLETED",
        "LOOP_EXHAUSTED", 
        "FOCUS_LOST",
        "ERROR_CASCADE",
        "STAGNATION",
        "CONFIDENCE_LOW"
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

# --- Main State ---

class AgentState(BaseModel):
    """エージェントの全状態を保持するSingle Source of Truth"""
    phase: AgentPhase = AgentPhase.IDLE
    vitals: Vitals = Field(default_factory=Vitals)
    
    # Context
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)
    current_plan: Optional[Plan] = None
    
    # Working Memory
    working_directory: str = "."
    known_files: List[str] = Field(default_factory=list)
    
    # Last Action Result
    last_action_result: Optional[str] = None
    
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
        context.append(f"Vitals: Mood={self.vitals.mood:.2f}, Focus={self.vitals.focus:.2f}, Stamina={self.vitals.stamina:.2f}")
        
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
        Determine the appropriate context mode for prompt generation.
        Returns: "normal", "planning", or "task_execution"
        """
        # If no plan exists, we're in normal mode
        if not self.current_plan:
            return "normal"
        
        current_step = self.current_plan.get_current_step()
        
        # If we have a step but no tasks yet, we're in planning/task generation mode
        if current_step and not current_step.tasks:
            return "task_execution"
        
        # If we have tasks, we're executing them
        if current_step and current_step.tasks:
            return "task_execution"
        
        # If we're between steps or just created a plan, we're in planning mode
        if not current_step and not self.current_plan.is_complete:
            return "planning"
        
        return "normal"

