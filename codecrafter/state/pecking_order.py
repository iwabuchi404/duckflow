"""
The Pecking Order - 階層的タスク管理システム

鳥の社会の「階層序列（Pecking Order）」をメタファーとし、
親タスクとサブタスクの厳格な階層関係と実行順序を管理する。
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class TaskStatus(Enum):
    """タスクの実行状態"""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS" 
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Task(BaseModel):
    """階層的タスクを表現するクラス
    
    鳥の社会における個体を表現し、親子関係と実行順序を管理する。
    各タスクは一つの親と複数の子を持つ木構造を形成する。
    """
    
    # 基本情報
    id: str = Field(default_factory=lambda: f"task_{uuid.uuid4().hex[:8]}", description="タスクの一意識別子")
    description: str = Field(description="タスクの説明（例: 'JWTライブラリをインストールする'）")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="タスクの実行状態")
    
    # 階層構造
    parent_id: Optional[str] = Field(default=None, description="親タスク（つついた鳥）のID")
    sub_tasks: List['Task'] = Field(default_factory=list, description="子タスク（つつかれる鳥）のリスト")
    
    # 実行結果
    result: Optional[str] = Field(default=None, description="タスクの実行結果")
    error: Optional[str] = Field(default=None, description="エラーメッセージ")
    
    # メタデータ
    created_at: datetime = Field(default_factory=datetime.now, description="作成日時")
    started_at: Optional[datetime] = Field(default=None, description="実行開始時刻")
    completed_at: Optional[datetime] = Field(default=None, description="完了時刻")
    priority: int = Field(default=0, description="優先度（高い値ほど高優先度）")
    
    # 設定フラグ  
    allow_parallel: bool = Field(default=False, description="子タスクの並列実行を許可するか")
    is_critical: bool = Field(default=False, description="失敗時に親タスクも失敗とするか")
    
    class Config:
        # Pydanticの再帰参照を有効にする
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def add_sub_task(self, task: 'Task') -> None:
        """子タスクを追加する
        
        Args:
            task: 追加する子タスク
        """
        task.parent_id = self.id
        self.sub_tasks.append(task)
    
    def remove_sub_task(self, task_id: str) -> bool:
        """指定されたIDの子タスクを削除する
        
        Args:
            task_id: 削除するタスクのID
            
        Returns:
            削除に成功した場合True
        """
        for i, task in enumerate(self.sub_tasks):
            if task.id == task_id:
                self.sub_tasks.pop(i)
                return True
        return False
    
    def find_task_by_id(self, task_id: str) -> Optional['Task']:
        """指定されたIDのタスクを階層内から検索する
        
        Args:
            task_id: 検索するタスクのID
            
        Returns:
            見つかったタスク、見つからない場合None
        """
        if self.id == task_id:
            return self
            
        for sub_task in self.sub_tasks:
            found = sub_task.find_task_by_id(task_id)
            if found:
                return found
                
        return None
    
    def get_next_pending_task(self) -> Optional['Task']:
        """次に実行すべきPENDINGタスクを取得する
        
        深さ優先探索でPENDINGタスクを検索する。
        子タスクがある場合は子タスクを優先する。
        
        Returns:
            次に実行すべきタスク、ない場合None
        """
        # 自分自身がPENDINGの場合
        if self.status == TaskStatus.PENDING:
            # 子タスクがある場合は子タスクを優先
            if self.sub_tasks:
                for sub_task in self.sub_tasks:
                    next_task = sub_task.get_next_pending_task()
                    if next_task:
                        return next_task
            # 子タスクが全て完了または子タスクがない場合は自分自身
            return self
        
        # 自分自身がIN_PROGRESSの場合は子タスクをチェック
        elif self.status == TaskStatus.IN_PROGRESS:
            for sub_task in self.sub_tasks:
                next_task = sub_task.get_next_pending_task()
                if next_task:
                    return next_task
        
        return None
    
    def update_status(self, new_status: TaskStatus, result: Optional[str] = None, error: Optional[str] = None) -> None:
        """タスクの状態を更新する
        
        Args:
            new_status: 新しい状態
            result: 実行結果（任意）
            error: エラーメッセージ（任意）
        """
        old_status = self.status
        self.status = new_status
        
        if result is not None:
            self.result = result
        if error is not None:
            self.error = error
            
        # タイムスタンプの更新
        if new_status == TaskStatus.IN_PROGRESS and old_status == TaskStatus.PENDING:
            self.started_at = datetime.now()
        elif new_status in [TaskStatus.COMPLETED, TaskStatus.FAILED] and old_status == TaskStatus.IN_PROGRESS:
            self.completed_at = datetime.now()
    
    def get_completion_rate(self) -> float:
        """タスクツリーの完了率を計算する
        
        Returns:
            完了率（0.0-1.0）
        """
        if not self.sub_tasks:
            # 末端タスクの場合
            return 1.0 if self.status == TaskStatus.COMPLETED else 0.0
        
        # 子タスクの完了率の平均を計算
        total_rate = sum(sub_task.get_completion_rate() for sub_task in self.sub_tasks)
        return total_rate / len(self.sub_tasks)
    
    def get_all_tasks_flat(self) -> List['Task']:
        """階層構造を平坦化してすべてのタスクを取得する
        
        Returns:
            すべてのタスクのリスト
        """
        tasks = [self]
        for sub_task in self.sub_tasks:
            tasks.extend(sub_task.get_all_tasks_flat())
        return tasks
    
    def get_status_summary(self) -> Dict[str, Any]:
        """タスクツリーの状態サマリーを取得する
        
        Returns:
            状態サマリーの辞書
        """
        all_tasks = self.get_all_tasks_flat()
        
        status_counts = {}
        for status in TaskStatus:
            status_counts[status.value] = sum(1 for task in all_tasks if task.status == status)
        
        return {
            "total_tasks": len(all_tasks),
            "completion_rate": self.get_completion_rate(),
            "status_breakdown": status_counts,
            "root_task": {
                "id": self.id,
                "description": self.description,
                "status": self.status.value
            },
            "current_task": self._get_current_task_info()
        }
    
    def _get_current_task_info(self) -> Optional[Dict[str, str]]:
        """現在実行中のタスク情報を取得する"""
        current = self.get_next_pending_task()
        if current:
            return {
                "id": current.id,
                "description": current.description,
                "status": current.status.value
            }
        
        # PENDING タスクがない場合、IN_PROGRESS タスクを探す
        all_tasks = self.get_all_tasks_flat()
        for task in all_tasks:
            if task.status == TaskStatus.IN_PROGRESS:
                return {
                    "id": task.id,
                    "description": task.description,
                    "status": task.status.value
                }
        
        return None
    
    def to_hierarchical_string(self, indent: int = 0) -> str:
        """階層構造を文字列で表現する（デバッグ用）
        
        Args:
            indent: インデントレベル
            
        Returns:
            階層構造の文字列表現
        """
        prefix = "  " * indent
        status_symbol = {
            TaskStatus.PENDING: "⏳",
            TaskStatus.IN_PROGRESS: "🔄", 
            TaskStatus.COMPLETED: "✅",
            TaskStatus.FAILED: "❌"
        }
        
        result = f"{prefix}{status_symbol[self.status]} {self.description} ({self.id})\n"
        
        for sub_task in self.sub_tasks:
            result += sub_task.to_hierarchical_string(indent + 1)
            
        return result


class PeckingOrderManager:
    """The Pecking Order 管理クラス
    
    タスクツリーの操作と状態管理を行う。
    """
    
    def __init__(self, main_goal: str = ""):
        """初期化
        
        Args:
            main_goal: メインゴールの説明
        """
        self.main_goal = main_goal
        self.task_tree: Optional[Task] = None
        self.current_task_id: Optional[str] = None
    
    def create_root_task(self, description: str) -> Task:
        """ルートタスクを作成する
        
        Args:
            description: ルートタスクの説明
            
        Returns:
            作成されたルートタスク
        """
        self.task_tree = Task(description=description)
        return self.task_tree
    
    def add_sub_task(self, parent_id: str, description: str, priority: int = 0) -> Optional[Task]:
        """指定された親タスクに子タスクを追加する
        
        Args:
            parent_id: 親タスクのID
            description: 子タスクの説明
            priority: 優先度
            
        Returns:
            作成された子タスク、親が見つからない場合None
        """
        if not self.task_tree:
            return None
            
        parent = self.task_tree.find_task_by_id(parent_id)
        if not parent:
            return None
            
        sub_task = Task(description=description, priority=priority)
        parent.add_sub_task(sub_task)
        return sub_task
    
    def get_current_task(self) -> Optional[Task]:
        """現在実行中のタスクを取得する
        
        Returns:
            現在実行中のタスク、ない場合None
        """
        if not self.task_tree:
            return None
            
        if self.current_task_id:
            return self.task_tree.find_task_by_id(self.current_task_id)
        
        return None
    
    def get_next_task(self) -> Optional[Task]:
        """次に実行すべきタスクを取得する
        
        Returns:
            次に実行すべきタスク、ない場合None
        """
        if not self.task_tree:
            return None
            
        return self.task_tree.get_next_pending_task()
    
    def start_task(self, task_id: str) -> bool:
        """指定されたタスクを開始する
        
        Args:
            task_id: 開始するタスクのID
            
        Returns:
            開始に成功した場合True
        """
        if not self.task_tree:
            return False
            
        task = self.task_tree.find_task_by_id(task_id)
        if not task or task.status != TaskStatus.PENDING:
            return False
            
        task.update_status(TaskStatus.IN_PROGRESS)
        self.current_task_id = task_id
        return True
    
    def complete_task(self, task_id: str, result: Optional[str] = None) -> bool:
        """指定されたタスクを完了する
        
        Args:
            task_id: 完了するタスクのID
            result: 実行結果
            
        Returns:
            完了に成功した場合True
        """
        if not self.task_tree:
            return False
            
        task = self.task_tree.find_task_by_id(task_id)
        if not task:
            return False
            
        task.update_status(TaskStatus.COMPLETED, result=result)
        
        # 現在のタスクが完了した場合は次のタスクに移る
        if self.current_task_id == task_id:
            next_task = self.get_next_task()
            self.current_task_id = next_task.id if next_task else None
            
        return True
    
    def fail_task(self, task_id: str, error: str) -> bool:
        """指定されたタスクを失敗させる
        
        Args:
            task_id: 失敗させるタスクのID
            error: エラーメッセージ
            
        Returns:
            失敗処理に成功した場合True
        """
        if not self.task_tree:
            return False
            
        task = self.task_tree.find_task_by_id(task_id)
        if not task:
            return False
            
        task.update_status(TaskStatus.FAILED, error=error)
        
        # クリティカルタスクの場合は親タスクも失敗させる
        if task.is_critical and task.parent_id:
            return self.fail_task(task.parent_id, f"Critical sub-task failed: {error}")
        
        return True
    
    def get_status_summary(self) -> Dict[str, Any]:
        """The Pecking Order の状態サマリーを取得する
        
        Returns:
            状態サマリーの辞書
        """
        if not self.task_tree:
            return {
                "main_goal": self.main_goal,
                "task_tree": None,
                "current_task_id": None,
                "total_tasks": 0,
                "completion_rate": 0.0
            }
        
        task_summary = self.task_tree.get_status_summary()
        
        return {
            "main_goal": self.main_goal,
            "current_task_id": self.current_task_id,
            "total_tasks": task_summary["total_tasks"],
            "completion_rate": task_summary["completion_rate"],
            "status_breakdown": task_summary["status_breakdown"],
            "root_task": task_summary["root_task"],
            "current_task": task_summary["current_task"]
        }
    
    def to_string(self) -> str:
        """The Pecking Order の文字列表現を取得する
        
        Returns:
            階層構造の文字列表現
        """
        if not self.task_tree:
            return f"The Pecking Order: {self.main_goal}\n(No tasks defined)"
        
        header = f"The Pecking Order: {self.main_goal}\n"
        header += "=" * len(header) + "\n"
        
        return header + self.task_tree.to_hierarchical_string()


# Task クラスの再帰参照を解決
Task.model_rebuild()