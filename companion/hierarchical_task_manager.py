"""
Hierarchical Task Manager - 階層タスク管理
Step 2: 2階層のタスク分割（親・子）機能
"""

import uuid
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum


class TaskStatus(Enum):
    """タスクの実行状態"""
    PENDING = "pending"        # 待機中
    RUNNING = "running"        # 実行中
    PAUSED = "paused"          # 一時停止
    COMPLETED = "completed"    # 完了
    FAILED = "failed"          # 失敗
    CANCELLED = "cancelled"    # キャンセル


class TaskPriority(Enum):
    """タスクの優先度"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class SubTask:
    """子タスク（サブタスク）"""
    task_id: str
    name: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    progress: float = 0.0  # 0.0-1.0
    result: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    depends_on: List[str] = field(default_factory=list)  # 依存する子タスクID
    context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "task_id": self.task_id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "progress": self.progress,
            "result": self.result,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "depends_on": self.depends_on,
            "context": self.context
        }


@dataclass
class ParentTask:
    """親タスク"""
    task_id: str
    name: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    sub_tasks: List[SubTask] = field(default_factory=list)
    progress: float = 0.0  # 0.0-1.0
    result: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    context: Dict[str, Any] = field(default_factory=dict)
    
    def add_sub_task(self, sub_task: SubTask) -> None:
        """子タスクを追加"""
        self.sub_tasks.append(sub_task)
    
    def get_sub_task(self, task_id: str) -> Optional[SubTask]:
        """子タスクを取得"""
        for sub_task in self.sub_tasks:
            if sub_task.task_id == task_id:
                return sub_task
        return None
    
    def update_progress(self) -> None:
        """子タスクの進捗から全体進捗を計算"""
        if not self.sub_tasks:
            self.progress = 0.0
            return
        
        total_progress = sum(sub_task.progress for sub_task in self.sub_tasks)
        self.progress = total_progress / len(self.sub_tasks)
    
    def get_next_executable_tasks(self) -> List[SubTask]:
        """実行可能な子タスクを取得（依存関係を考慮）"""
        executable_tasks = []
        
        for sub_task in self.sub_tasks:
            if sub_task.status != TaskStatus.PENDING:
                continue
            
            # 依存関係をチェック
            dependencies_met = True
            for dep_id in sub_task.depends_on:
                dep_task = self.get_sub_task(dep_id)
                if not dep_task or dep_task.status != TaskStatus.COMPLETED:
                    dependencies_met = False
                    break
            
            if dependencies_met:
                executable_tasks.append(sub_task)
        
        # 優先度でソート
        executable_tasks.sort(key=lambda t: t.priority.value, reverse=True)
        return executable_tasks
    
    def is_completed(self) -> bool:
        """すべての子タスクが完了しているかチェック"""
        return all(sub_task.status == TaskStatus.COMPLETED for sub_task in self.sub_tasks)
    
    def has_failed_tasks(self) -> bool:
        """失敗した子タスクがあるかチェック"""
        return any(sub_task.status == TaskStatus.FAILED for sub_task in self.sub_tasks)
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "task_id": self.task_id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "sub_tasks": [sub_task.to_dict() for sub_task in self.sub_tasks],
            "progress": self.progress,
            "result": self.result,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "context": self.context
        }


class HierarchicalTaskManager:
    """Step 2: 階層タスク管理クラス"""
    
    def __init__(self):
        """初期化"""
        self.parent_tasks: Dict[str, ParentTask] = {}
        self.current_parent_task: Optional[ParentTask] = None
        self.task_executor: Optional[Callable] = None
    
    def set_task_executor(self, executor: Callable) -> None:
        """タスク実行関数を設定
        
        Args:
            executor: タスクを実行するための関数
        """
        self.task_executor = executor
    
    def create_parent_task(self, name: str, description: str, 
                          priority: TaskPriority = TaskPriority.NORMAL) -> str:
        """親タスクを作成
        
        Args:
            name: タスク名
            description: タスクの説明
            priority: 優先度
            
        Returns:
            str: 作成された親タスクID
        """
        task_id = str(uuid.uuid4())[:8]
        
        parent_task = ParentTask(
            task_id=task_id,
            name=name,
            description=description,
            priority=priority
        )
        
        self.parent_tasks[task_id] = parent_task
        self.current_parent_task = parent_task
        
        return task_id
    
    def add_sub_task(self, parent_task_id: str, name: str, description: str,
                    priority: TaskPriority = TaskPriority.NORMAL,
                    depends_on: Optional[List[str]] = None) -> str:
        """子タスクを追加
        
        Args:
            parent_task_id: 親タスクID
            name: 子タスク名
            description: 子タスクの説明
            priority: 優先度
            depends_on: 依存する子タスクIDのリスト
            
        Returns:
            str: 作成された子タスクID
        """
        parent_task = self.parent_tasks.get(parent_task_id)
        if not parent_task:
            raise ValueError(f"親タスク {parent_task_id} が見つかりません")
        
        sub_task_id = f"{parent_task_id}_sub_{len(parent_task.sub_tasks) + 1}"
        
        sub_task = SubTask(
            task_id=sub_task_id,
            name=name,
            description=description,
            priority=priority,
            depends_on=depends_on or []
        )
        
        parent_task.add_sub_task(sub_task)
        
        return sub_task_id
    
    def start_parent_task(self, parent_task_id: str) -> bool:
        """親タスクの実行を開始
        
        Args:
            parent_task_id: 親タスクID
            
        Returns:
            bool: 開始に成功した場合True
        """
        parent_task = self.parent_tasks.get(parent_task_id)
        if not parent_task:
            return False
        
        parent_task.status = TaskStatus.RUNNING
        parent_task.started_at = datetime.now()
        self.current_parent_task = parent_task
        
        return True
    
    def get_next_sub_task(self, parent_task_id: Optional[str] = None) -> Optional[SubTask]:
        """次に実行すべき子タスクを取得
        
        Args:
            parent_task_id: 親タスクID（未指定の場合は現在のタスク）
            
        Returns:
            Optional[SubTask]: 次に実行すべき子タスク
        """
        if parent_task_id:
            parent_task = self.parent_tasks.get(parent_task_id)
        else:
            parent_task = self.current_parent_task
        
        if not parent_task:
            return None
        
        executable_tasks = parent_task.get_next_executable_tasks()
        return executable_tasks[0] if executable_tasks else None
    
    def update_sub_task_status(self, parent_task_id: str, sub_task_id: str, 
                              status: TaskStatus, progress: float = None,
                              result: str = None, error_message: str = None) -> bool:
        """子タスクの状態を更新
        
        Args:
            parent_task_id: 親タスクID
            sub_task_id: 子タスクID
            status: 新しい状態
            progress: 進捗（0.0-1.0）
            result: 実行結果
            error_message: エラーメッセージ
            
        Returns:
            bool: 更新に成功した場合True
        """
        parent_task = self.parent_tasks.get(parent_task_id)
        if not parent_task:
            return False
        
        sub_task = parent_task.get_sub_task(sub_task_id)
        if not sub_task:
            return False
        
        sub_task.status = status
        
        if progress is not None:
            sub_task.progress = progress
        
        if result is not None:
            sub_task.result = result
        
        if error_message is not None:
            sub_task.error_message = error_message
        
        if status == TaskStatus.RUNNING and sub_task.started_at is None:
            sub_task.started_at = datetime.now()
        
        if status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            sub_task.completed_at = datetime.now()
            if status == TaskStatus.COMPLETED:
                sub_task.progress = 1.0
        
        # 親タスクの進捗を更新
        parent_task.update_progress()
        
        # 親タスクの状態を更新
        if parent_task.is_completed():
            parent_task.status = TaskStatus.COMPLETED
            parent_task.completed_at = datetime.now()
        elif parent_task.has_failed_tasks():
            parent_task.status = TaskStatus.FAILED
        
        return True
    
    def decompose_task(self, task_description: str) -> Optional[str]:
        """タスクを自動的に分解して階層構造を作成
        
        Args:
            task_description: タスクの説明
            
        Returns:
            Optional[str]: 作成された親タスクID
        """
        # シンプルな分解ロジック（実際のプロジェクトではLLMを使用）
        parent_task_id = self.create_parent_task(
            name=f"分解タスク: {task_description[:30]}...",
            description=task_description
        )
        
        # 基本的な分解パターン
        if "ファイル" in task_description and ("作成" in task_description or "書く" in task_description):
            # ファイル作成タスクの分解
            self.add_sub_task(parent_task_id, "要件分析", "ファイルの要件と内容を分析")
            self.add_sub_task(parent_task_id, "ファイル作成", "実際のファイルを作成", depends_on=[f"{parent_task_id}_sub_1"])
            self.add_sub_task(parent_task_id, "検証", "作成されたファイルを検証", depends_on=[f"{parent_task_id}_sub_2"])
            
        elif "レビュー" in task_description or "確認" in task_description:
            # レビュータスクの分解
            self.add_sub_task(parent_task_id, "ファイル一覧取得", "レビュー対象ファイルをリストアップ")
            self.add_sub_task(parent_task_id, "コード解析", "各ファイルのコードを解析", depends_on=[f"{parent_task_id}_sub_1"])
            self.add_sub_task(parent_task_id, "レポート作成", "レビュー結果のレポートを作成", depends_on=[f"{parent_task_id}_sub_2"])
            
        elif "実装" in task_description:
            # 実装タスクの分解
            self.add_sub_task(parent_task_id, "設計", "実装の設計を行う")
            self.add_sub_task(parent_task_id, "コード作成", "実際のコードを作成", depends_on=[f"{parent_task_id}_sub_1"])
            self.add_sub_task(parent_task_id, "テスト", "作成したコードをテスト", depends_on=[f"{parent_task_id}_sub_2"])
            
        else:
            # 汎用的な分解
            self.add_sub_task(parent_task_id, "分析", "タスクの詳細を分析")
            self.add_sub_task(parent_task_id, "実行", "タスクを実行", depends_on=[f"{parent_task_id}_sub_1"])
            self.add_sub_task(parent_task_id, "確認", "実行結果を確認", depends_on=[f"{parent_task_id}_sub_2"])
        
        return parent_task_id
    
    def get_task_status_summary(self, parent_task_id: Optional[str] = None) -> Dict[str, Any]:
        """タスクの状態サマリーを取得
        
        Args:
            parent_task_id: 親タスクID（未指定の場合は現在のタスク）
            
        Returns:
            Dict[str, Any]: タスク状態のサマリー
        """
        if parent_task_id:
            parent_task = self.parent_tasks.get(parent_task_id)
        else:
            parent_task = self.current_parent_task
        
        if not parent_task:
            return {"error": "タスクが見つかりません"}
        
        summary = {
            "parent_task": {
                "id": parent_task.task_id,
                "name": parent_task.name,
                "status": parent_task.status.value,
                "progress": parent_task.progress,
                "total_sub_tasks": len(parent_task.sub_tasks)
            },
            "sub_tasks": []
        }
        
        for sub_task in parent_task.sub_tasks:
            summary["sub_tasks"].append({
                "id": sub_task.task_id,
                "name": sub_task.name,
                "status": sub_task.status.value,
                "progress": sub_task.progress,
                "depends_on": sub_task.depends_on
            })
        
        return summary
    
    def list_all_tasks(self) -> List[Dict[str, Any]]:
        """すべてのタスクのリストを取得"""
        return [task.to_dict() for task in self.parent_tasks.values()]