"""
Enhanced AgentState for Phase 1

- Adds the fixed five items (goal, why_now, constraints, plan_brief, open_questions)
- Introduces Step/Status enums to separate activity kind and outcome state
- Keeps compatibility with legacy fields used by EnhancedCompanionCore

Note: This file is based on `codecrafter/state/agent_state.py` with minimal
extensions required for Phase 1 integration.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from enum import Enum
from pydantic import BaseModel, Field

from .enums import Step, Status


class ConversationMessage(BaseModel):
    role: str = Field(description="メッセージの役割 (user, assistant, system)")
    content: str = Field(description="メッセージの内容")
    timestamp: datetime = Field(default_factory=datetime.now, description="メッセージのタイムスタンプ")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="追加のメタデータ")


class TaskStep(BaseModel):
    id: str = Field(description="ステップのID")
    description: str = Field(description="ステップの説明")
    status: str = Field(default="pending", description="ステップの状態 (pending, in_progress, completed, failed)")
    result: Optional[str] = Field(default=None, description="ステップの実行結果")
    error: Optional[str] = Field(default=None, description="エラーメッセージ")
    created_at: datetime = Field(default_factory=datetime.now, description="作成日時")
    completed_at: Optional[datetime] = Field(default=None, description="完了日時")


class WorkspaceInfo(BaseModel):
    path: str = Field(description="ワークスペースのパス")
    files: List[str] = Field(default_factory=list, description="ワークスペース内のファイル一覧")
    current_file: Optional[str] = Field(default=None, description="現在作業中のファイル")
    last_modified: Optional[datetime] = Field(default=None, description="最終更新日時")


class ToolExecution(BaseModel):
    tool_name: str = Field(description="実行したツール名")
    arguments: Dict[str, Any] = Field(description="ツールの引数")
    result: Optional[Any] = Field(default=None, description="ツールの実行結果")
    error: Optional[str] = Field(default=None, description="エラーメッセージ")
    execution_time: float = Field(default=0.0, description="実行時間（秒）")
    timestamp: datetime = Field(default_factory=datetime.now, description="実行時刻")


class Vitals(BaseModel):
    mood: float = Field(default=1.0, description="気分・機嫌 (0.0-1.0)")
    focus: float = Field(default=1.0, description="集中力 (0.0-1.0)")
    stamina: float = Field(default=1.0, description="体力 (0.0-1.0)")
    total_loops: int = Field(default=0, description="総ループ回数")
    error_count: int = Field(default=0, description="エラー発生回数")
    last_confidence_score: float = Field(default=1.0, description="最新の自己評価スコア")
    consecutive_similar_actions: int = Field(default=0, description="連続した類似アクション回数")

    def update_mood(self, confidence_score: float, user_feedback: Optional[float] = None):
        self.last_confidence_score = confidence_score
        self.mood = 0.7 * confidence_score + 0.3 * self.mood
        if user_feedback is not None:
            self.mood = min(1.0, self.mood + user_feedback * 0.2)
        self.mood = max(0.0, min(1.0, self.mood))

    def update_focus(self, is_progress: bool = True, context_size: int = 0):
        if is_progress:
            self.focus = min(1.0, self.focus + 0.1)
            self.consecutive_similar_actions = 0
        else:
            self.consecutive_similar_actions += 1
            focus_penalty = 0.15 * min(self.consecutive_similar_actions, 5)
            self.focus = max(0.0, self.focus - focus_penalty)
        if context_size > 5000:
            self.focus = max(0.0, self.focus - 0.05)

    def update_stamina(self, had_error: bool = False):
        self.total_loops += 1
        loop_penalty = 0.02 * self.total_loops
        if had_error:
            self.error_count += 1
            error_penalty = 0.1 * self.error_count
        else:
            error_penalty = 0
        self.stamina = max(0.0, 1.0 - loop_penalty - error_penalty)


class GraphState(BaseModel):
    current_node: Optional[str] = Field(default=None, description="現在実行中のノード")
    next_nodes: List[str] = Field(default_factory=list, description="次に実行予定のノード一覧")
    execution_path: List[str] = Field(default_factory=list, description="実行済みノードのパス")
    loop_count: int = Field(default=0, description="ループ実行回数")
    max_loops: int = Field(default=5, description="最大ループ回数")


class AgentState(BaseModel):
    """エージェントの全体状態（Phase 1 拡張版）"""

    model_config = {"arbitrary_types_allowed": True}

    # 固定5項目（文脈の核）
    goal: str = Field(default="", description="目的（1行、最大200文字）")
    why_now: str = Field(default="", description="なぜ今やるのか（1行、最大200文字）")
    constraints: List[str] = Field(default_factory=list, description="制約（最大2個、各100文字以内）")
    plan_brief: List[str] = Field(default_factory=list, description="直近の短い計画（最大3手）")
    open_questions: List[str] = Field(default_factory=list, description="未解決の問い（最大2個）")

    # 追加フィールド
    short_term_memory: Dict[str, Any] = Field(default_factory=dict, description="タスクをまたいで引き継がれる短期記憶")
    context_refs: List[str] = Field(default_factory=list, description="関連参照")
    decision_log: List[str] = Field(default_factory=list, description="採択済みの方針ログ")
    pending_gate: bool = Field(default=False, description="承認待ちの有無")
    last_delta: str = Field(default="", description="直近の変更の要約")

    # 行動と結果（分離）
    step: Step = Field(default=Step.IDLE, description="現在のステップ")
    status: Status = Field(default=Status.PENDING, description="現在のステータス")

    # 既存フィールド（互換性維持）
    conversation_history: List[ConversationMessage] = Field(default_factory=list, description="対話履歴")
    current_task: Optional[str] = Field(default=None, description="現在実行中のタスク")
    task_steps: List[TaskStep] = Field(default_factory=list, description="タスクのステップ一覧")
    workspace: Optional[WorkspaceInfo] = Field(default=None, description="ワークスペース情報")
    tool_executions: List[ToolExecution] = Field(default_factory=list, description="ツール実行履歴")
    graph_state: GraphState = Field(default_factory=GraphState, description="グラフの実行状態")
    session_id: str = Field(description="セッションID")
    created_at: datetime = Field(default_factory=datetime.now, description="セッション開始時刻")
    last_activity: datetime = Field(default_factory=datetime.now, description="最終活動時刻")
    debug_mode: bool = Field(default=False, description="デバッグモード")
    auto_approve: bool = Field(default=False, description="自動承認モード")
    vitals: Vitals = Field(default_factory=Vitals, description="エージェントの健康状態バイタル")
    error_count: int = Field(default=0, description="エラー発生回数")
    last_error: Optional[str] = Field(default=None, description="最後に発生したエラー")
    retry_count: int = Field(default=0, description="リトライ回数")
    max_retries: int = Field(default=3, description="最大リトライ回数")
    history_summary: Optional[str] = Field(default=None, description="対話履歴の要約")
    summary_created_at: Optional[datetime] = Field(default=None, description="要約作成時刻")
    original_conversation_length: int = Field(default=0, description="要約前の元の対話数")
    safety_assessment: Dict[str, Any] = Field(default_factory=dict, description="安全性評価結果")
    error_analysis: Dict[str, Any] = Field(default_factory=dict, description="エラー分析結果")
    approval_result: Optional[str] = Field(default=None, description="人間承認の結果")
    collected_context: Dict[str, Any] = Field(default_factory=dict, description="収集済みコンテキスト")
    rag_context: List[Dict[str, Any]] = Field(default_factory=list, description="直近のRAG検索結果")

    def add_message(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        message = ConversationMessage(role=role, content=content, metadata=metadata or {})
        self.conversation_history.append(message)
        self.last_activity = datetime.now()

    def set_fixed_five(self, goal: str = "", why_now: str = "", constraints: Optional[List[str]] = None,
                       plan_brief: Optional[List[str]] = None, open_questions: Optional[List[str]] = None) -> None:
        self.goal = goal[:200]
        self.why_now = why_now[:200]
        self.constraints = (constraints or [])[:2]
        self.plan_brief = (plan_brief or [])[:3]
        self.open_questions = (open_questions or [])[:2]
        self.last_delta = "fixed_five_updated"

    def set_step_status(self, step: Step, status: Status) -> None:
        self.step = step
        self.status = status
        self.last_delta = f"step={step.value}, status={status.value}"

    def get_context_summary(self) -> Dict[str, Any]:
        """コンテキストサマリーを取得"""
        return {
            "session_id": self.session_id,
            "conversation_count": len(self.conversation_history),
            "current_step": self.step.value,
            "current_status": self.status.value,
            "goal": self.goal,
            "why_now": self.why_now,
            "constraints": self.constraints,
            "plan_brief": self.plan_brief,
            "open_questions": self.open_questions,
            "last_delta": self.last_delta,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "vitals": {
                "mood": self.vitals.mood,
                "focus": self.vitals.focus,
                "stamina": self.vitals.stamina,
                "total_loops": self.vitals.total_loops,
                "error_count": self.vitals.error_count
            }
        }

    def needs_memory_management(self) -> bool:
        """記憶管理が必要かチェック"""
        return len(self.conversation_history) > 20

    def create_memory_summary(self) -> bool:
        """記憶要約を作成"""
        try:
            if len(self.conversation_history) <= 10:
                return False
            
            recent_messages = self.conversation_history[-10:]
            old_messages = self.conversation_history[:-10]
            
            if old_messages:
                summary_content = f"過去{len(old_messages)}件のメッセージを要約"
                summary_message = ConversationMessage(
                    role="system",
                    content=summary_content,
                    metadata={"type": "memory_summary", "count": len(old_messages)}
                )
                
                self.conversation_history = [summary_message] + recent_messages
                self.history_summary = summary_content
                self.summary_created_at = datetime.now()
                self.original_conversation_length = len(old_messages)
                
                return True
            
            return False
            
        except Exception:
            return False

    def get_memory_status(self) -> Dict[str, Any]:
        """記憶管理の状態を取得"""
        return {
            "total_messages": len(self.conversation_history),
            "has_summary": self.history_summary is not None,
            "summary_created_at": self.summary_created_at.isoformat() if self.summary_created_at else None,
            "original_length": self.original_conversation_length,
            "needs_management": self.needs_memory_management()
        }

    def get_recent_messages(self, count: int = 10) -> List[ConversationMessage]:
        """最近のメッセージを取得（互換API）"""
        if not self.conversation_history:
            return []
        if count <= 0:
            return []
        return self.conversation_history[-count:] if len(self.conversation_history) > count else self.conversation_history