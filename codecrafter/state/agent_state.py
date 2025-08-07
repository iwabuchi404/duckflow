"""
エージェントの状態を管理するためのデータクラス
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ConversationMessage(BaseModel):
    """対話メッセージを表現するクラス"""
    
    role: str = Field(description="メッセージの役割 (user, assistant, system)")
    content: str = Field(description="メッセージの内容")
    timestamp: datetime = Field(default_factory=datetime.now, description="メッセージのタイムスタンプ")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="追加のメタデータ")


class TaskStep(BaseModel):
    """タスクステップを表現するクラス"""
    
    id: str = Field(description="ステップのID")
    description: str = Field(description="ステップの説明")
    status: str = Field(default="pending", description="ステップの状態 (pending, in_progress, completed, failed)")
    result: Optional[str] = Field(default=None, description="ステップの実行結果")
    error: Optional[str] = Field(default=None, description="エラーメッセージ")
    created_at: datetime = Field(default_factory=datetime.now, description="作成日時")
    completed_at: Optional[datetime] = Field(default=None, description="完了日時")


class WorkspaceInfo(BaseModel):
    """ワークスペース情報を表現するクラス"""
    
    path: str = Field(description="ワークスペースのパス")
    files: List[str] = Field(default_factory=list, description="ワークスペース内のファイル一覧")
    current_file: Optional[str] = Field(default=None, description="現在作業中のファイル")
    last_modified: Optional[datetime] = Field(default=None, description="最終更新日時")


class AgentState(BaseModel):
    """エージェントの全体状態を管理するメインクラス"""
    
    # 対話履歴
    conversation_history: List[ConversationMessage] = Field(
        default_factory=list, 
        description="対話履歴"
    )
    
    # 現在のタスク
    current_task: Optional[str] = Field(default=None, description="現在実行中のタスク")
    task_steps: List[TaskStep] = Field(default_factory=list, description="タスクのステップ一覧")
    
    # ワークスペース情報
    workspace: Optional[WorkspaceInfo] = Field(default=None, description="ワークスペース情報")
    
    # エージェントのメタデータ
    session_id: str = Field(description="セッションID")
    created_at: datetime = Field(default_factory=datetime.now, description="セッション開始時刻")
    last_activity: datetime = Field(default_factory=datetime.now, description="最終活動時刻")
    
    # 設定とフラグ
    debug_mode: bool = Field(default=False, description="デバッグモード")
    auto_approve: bool = Field(default=False, description="自動承認モード")
    
    def add_message(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """対話履歴にメッセージを追加"""
        message = ConversationMessage(
            role=role,
            content=content,
            metadata=metadata or {}
        )
        self.conversation_history.append(message)
        self.last_activity = datetime.now()
    
    def start_task(self, task_description: str) -> None:
        """新しいタスクを開始"""
        self.current_task = task_description
        self.task_steps.clear()
        self.last_activity = datetime.now()
    
    def add_task_step(self, step_id: str, description: str) -> TaskStep:
        """タスクステップを追加"""
        step = TaskStep(id=step_id, description=description)
        self.task_steps.append(step)
        self.last_activity = datetime.now()
        return step
    
    def update_task_step(self, step_id: str, status: str, result: Optional[str] = None, error: Optional[str] = None) -> bool:
        """タスクステップを更新"""
        for step in self.task_steps:
            if step.id == step_id:
                step.status = status
                step.result = result
                step.error = error
                if status in ["completed", "failed"]:
                    step.completed_at = datetime.now()
                self.last_activity = datetime.now()
                return True
        return False
    
    def get_recent_messages(self, count: int = 10) -> List[ConversationMessage]:
        """最近のメッセージを取得"""
        return self.conversation_history[-count:] if len(self.conversation_history) > count else self.conversation_history
    
    def get_active_task_steps(self) -> List[TaskStep]:
        """アクティブなタスクステップを取得"""
        return [step for step in self.task_steps if step.status in ["pending", "in_progress"]]