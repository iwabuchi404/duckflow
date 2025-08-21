"""
Enhanced v2.0システム専用の型定義
設計原則に基づく明確な型管理
"""

from enum import Enum
from typing import Literal, Union, Dict, Any, Optional
from dataclasses import dataclass


class ActionType(Enum):
    """Enhanced v2.0システムのアクションタイプ"""
    DIRECT_RESPONSE = "direct_response"
    FILE_OPERATION = "file_operation"
    CODE_EXECUTION = "code_execution"
    MULTI_STEP_TASK = "multi_step_task"
    PLAN_GENERATION = "plan_generation"
    SUMMARY_GENERATION = "summary_generation"
    CONTENT_EXTRACTION = "content_extraction"


class TaskPriority(Enum):
    """タスクの優先度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskStatus(Enum):
    """タスクの実行状態"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskContext:
    """タスク実行のコンテキスト"""
    task_id: str
    user_message: str
    action_type: ActionType
    priority: TaskPriority = TaskPriority.MEDIUM
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None


@dataclass
class IntentResult:
    """意図理解の結果"""
    action_type: ActionType
    confidence: float
    reasoning: str
    context: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class FileOperationRequest:
    """ファイル操作の要求"""
    operation: Literal["read", "write", "create", "delete", "list"]
    file_path: str
    content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class CodeExecutionRequest:
    """コード実行の要求"""
    code: str
    language: str
    context: Optional[Dict[str, Any]] = None
    timeout: Optional[int] = None


@dataclass
class PlanGenerationRequest:
    """プラン生成の要求"""
    description: str
    scope: str
    complexity: Literal["simple", "moderate", "complex"]
    metadata: Optional[Dict[str, Any]] = None


# Enhanced v2.0システムの型エイリアス
EnhancedActionType = ActionType
EnhancedTaskContext = TaskContext
EnhancedIntentResult = IntentResult
