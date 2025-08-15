"""
Task Hierarchy System

階層的タスク管理のためのデータ構造
"""

import uuid
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from companion.intent_understanding.task_profile_classifier import TaskProfileType


class TaskStatus(Enum):
    """タスクの状態"""
    PENDING = "pending"        # 待機中
    IN_PROGRESS = "in_progress"  # 実行中
    COMPLETED = "completed"    # 完了
    FAILED = "failed"          # 失敗
    CANCELLED = "cancelled"    # キャンセル


class TaskPriority(Enum):
    """タスクの優先度"""
    LOW = "low"           # 低
    MEDIUM = "medium"     # 中
    HIGH = "high"         # 高
    CRITICAL = "critical" # 緊急


@dataclass
class TaskNode:
    """タスクノード"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    task_profile: Optional[TaskProfileType] = None
    complexity: str = "moderate"
    
    # 階層構造
    parent_id: Optional[str] = None
    children: List[str] = field(default_factory=list)  # 子タスクのIDリスト
    
    # 実行情報
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    estimated_duration: Optional[int] = None  # 分単位
    
    # メタデータ
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.children is None:
            self.children = []
    
    def add_child(self, child_id: str):
        """子タスクを追加"""
        if child_id not in self.children:
            self.children.append(child_id)
    
    def remove_child(self, child_id: str):
        """子タスクを削除"""
        if child_id in self.children:
            self.children.remove(child_id)
    
    def is_leaf(self) -> bool:
        """リーフノードかどうか"""
        return len(self.children) == 0
    
    def is_root(self) -> bool:
        """ルートノードかどうか"""
        return self.parent_id is None
    
    def get_depth(self, task_hierarchy: 'TaskHierarchy') -> int:
        """タスクの深さを取得"""
        if self.is_root():
            return 0
        
        parent = task_hierarchy.get_task(self.parent_id)
        if parent:
            return parent.get_depth(task_hierarchy) + 1
        
        return 0
    
    def get_all_descendants(self, task_hierarchy: 'TaskHierarchy') -> List[str]:
        """全ての子孫タスクのIDを取得"""
        descendants = []
        
        for child_id in self.children:
            descendants.append(child_id)
            child = task_hierarchy.get_task(child_id)
            if child:
                descendants.extend(child.get_all_descendants(task_hierarchy))
        
        return descendants
    
    def get_progress(self) -> float:
        """進捗率を取得（0.0-1.0）"""
        if self.status == TaskStatus.COMPLETED:
            return 1.0
        elif self.status == TaskStatus.FAILED or self.status == TaskStatus.CANCELLED:
            return 0.0
        elif self.status == TaskStatus.IN_PROGRESS:
            return 0.5
        else:
            return 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "task_profile": self.task_profile.value if self.task_profile else None,
            "complexity": self.complexity,
            "parent_id": self.parent_id,
            "children": self.children,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "estimated_duration": self.estimated_duration,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TaskNode':
        """辞書から作成"""
        # 日時フィールドの変換
        created_at = None
        if data.get("created_at"):
            try:
                created_at = datetime.fromisoformat(data["created_at"])
            except ValueError:
                created_at = datetime.now()
        
        started_at = None
        if data.get("started_at"):
            try:
                started_at = datetime.fromisoformat(data["started_at"])
            except ValueError:
                pass
        
        completed_at = None
        if data.get("completed_at"):
            try:
                completed_at = datetime.fromisoformat(data["completed_at"])
            except ValueError:
                pass
        
        # 列挙型フィールドの変換
        status = TaskStatus(data.get("status", "pending"))
        priority = TaskPriority(data.get("priority", "medium"))
        task_profile = None
        if data.get("task_profile"):
            try:
                task_profile = TaskProfileType(data["task_profile"])
            except ValueError:
                pass
        
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            title=data.get("title", ""),
            description=data.get("description", ""),
            status=status,
            priority=priority,
            task_profile=task_profile,
            complexity=data.get("complexity", "moderate"),
            parent_id=data.get("parent_id"),
            children=data.get("children", []),
            created_at=created_at,
            started_at=started_at,
            completed_at=completed_at,
            estimated_duration=data.get("estimated_duration"),
            metadata=data.get("metadata", {})
        )


@dataclass
class TaskHierarchy:
    """タスク階層管理システム"""
    
    def __init__(self):
        """タスク階層を初期化"""
        self.tasks: Dict[str, TaskNode] = {}
        self.root_tasks: List[str] = []
    
    def add_task(self, task: TaskNode) -> str:
        """タスクを追加"""
        self.tasks[task.id] = task
        
        if task.is_root():
            if task.id not in self.root_tasks:
                self.root_tasks.append(task.id)
        else:
            # 親タスクに子として追加
            parent = self.get_task(task.parent_id)
            if parent:
                parent.add_child(task.id)
        
        return task.id
    
    def remove_task(self, task_id: str) -> bool:
        """タスクを削除"""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        
        # 子タスクを再帰的に削除
        for child_id in task.children[:]:  # コピーを作成してイテレート
            self.remove_task(child_id)
        
        # 親タスクから子として削除
        if not task.is_root():
            parent = self.get_task(task.parent_id)
            if parent:
                parent.remove_child(task_id)
        else:
            if task_id in self.root_tasks:
                self.root_tasks.remove(task_id)
        
        # タスク自体を削除
        del self.tasks[task_id]
        return True
    
    def get_task(self, task_id: str) -> Optional[TaskNode]:
        """タスクを取得"""
        return self.tasks.get(task_id)
    
    def get_root_tasks(self) -> List[TaskNode]:
        """ルートタスクを取得"""
        return [self.tasks[task_id] for task_id in self.root_tasks if task_id in self.tasks]
    
    def get_children(self, task_id: str) -> List[TaskNode]:
        """子タスクを取得"""
        task = self.get_task(task_id)
        if not task:
            return []
        
        return [self.tasks[child_id] for child_id in task.children if child_id in self.tasks]
    
    def get_parent(self, task_id: str) -> Optional[TaskNode]:
        """親タスクを取得"""
        task = self.get_task(task_id)
        if not task or task.is_root():
            return None
        
        return self.get_task(task.parent_id)
    
    def get_leaf_tasks(self) -> List[TaskNode]:
        """リーフタスクを取得"""
        return [task for task in self.tasks.values() if task.is_leaf()]
    
    def get_tasks_by_status(self, status: TaskStatus) -> List[TaskNode]:
        """状態別にタスクを取得"""
        return [task for task in self.tasks.values() if task.status == status]
    
    def get_tasks_by_priority(self, priority: TaskPriority) -> List[TaskNode]:
        """優先度別にタスクを取得"""
        return [task for task in self.tasks.values() if task.priority == priority]
    
    def get_tasks_by_profile(self, profile: TaskProfileType) -> List[TaskNode]:
        """TaskProfile別にタスクを取得"""
        return [task for task in self.tasks.values() if task.task_profile == profile]
    
    def get_task_count(self) -> int:
        """タスク総数を取得"""
        return len(self.tasks)
    
    def get_completed_task_count(self) -> int:
        """完了タスク数を取得"""
        return len(self.get_tasks_by_status(TaskStatus.COMPLETED))
    
    def get_overall_progress(self) -> float:
        """全体の進捗率を取得"""
        if not self.tasks:
            return 0.0
        
        total_progress = sum(task.get_progress() for task in self.tasks.values())
        return total_progress / len(self.tasks)
    
    def get_critical_path(self) -> List[TaskNode]:
        """クリティカルパスを取得（簡易版）"""
        # 優先度が高いタスクを優先
        high_priority_tasks = self.get_tasks_by_priority(TaskPriority.CRITICAL)
        if high_priority_tasks:
            return high_priority_tasks
        
        # 次に高優先度
        high_priority_tasks = self.get_tasks_by_priority(TaskPriority.HIGH)
        if high_priority_tasks:
            return high_priority_tasks
        
        # デフォルトは中優先度
        return self.get_tasks_by_priority(TaskPriority.MEDIUM)
    
    def validate_hierarchy(self) -> List[str]:
        """階層構造の妥当性を検証"""
        errors = []
        
        for task_id, task in self.tasks.items():
            # 親タスクの存在確認
            if not task.is_root():
                parent = self.get_task(task.parent_id)
                if not parent:
                    errors.append(f"タスク {task_id} の親タスク {task.parent_id} が存在しません")
            
            # 子タスクの存在確認
            for child_id in task.children:
                child = self.get_task(child_id)
                if not child:
                    errors.append(f"タスク {task_id} の子タスク {child_id} が存在しません")
                elif child.parent_id != task_id:
                    errors.append(f"タスク {child_id} の親タスクが {task_id} と一致しません")
        
        return errors
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "tasks": {task_id: task.to_dict() for task_id, task in self.tasks.items()},
            "root_tasks": self.root_tasks
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TaskHierarchy':
        """辞書から作成"""
        hierarchy = cls()
        
        # タスクの復元
        for task_id, task_data in data.get("tasks", {}).items():
            task = TaskNode.from_dict(task_data)
            hierarchy.tasks[task_id] = task
        
        # ルートタスクの復元
        hierarchy.root_tasks = data.get("root_tasks", [])
        
        return hierarchy
    
    def print_hierarchy(self, task_id: Optional[str] = None, indent: int = 0):
        """階層構造を表示（デバッグ用）"""
        if task_id is None:
            # ルートタスクから開始
            for root_id in self.root_tasks:
                self.print_hierarchy(root_id, indent)
            return
        
        task = self.get_task(task_id)
        if not task:
            return
        
        # インデントとタスク情報を表示
        prefix = "  " * indent
        status_icon = {
            TaskStatus.PENDING: "⏳",
            TaskStatus.IN_PROGRESS: "🔄",
            TaskStatus.COMPLETED: "✅",
            TaskStatus.FAILED: "❌",
            TaskStatus.CANCELLED: "🚫"
        }.get(task.status, "❓")
        
        priority_icon = {
            TaskPriority.LOW: "🔽",
            TaskPriority.MEDIUM: "➡️",
            TaskPriority.HIGH: "🔼",
            TaskPriority.CRITICAL: "🚨"
        }.get(task.priority, "❓")
        
        print(f"{prefix}{status_icon} {priority_icon} {task.title} ({task.status.value})")
        
        # 子タスクを再帰的に表示
        for child_id in task.children:
            self.print_hierarchy(child_id, indent + 1)
