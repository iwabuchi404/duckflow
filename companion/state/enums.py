from enum import Enum

class Step(Enum):
    """システムの実行ステップ（統一定義）"""
    IDLE = "IDLE"
    THINKING = "THINKING"
    PLANNING = "PLANNING"
    EXECUTION = "EXECUTION"
    REVIEW = "REVIEW"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    AWAITING_USER_INPUT = "AWAITING_USER_INPUT"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"

class Status(Enum):
    """各ステップの実行ステータス（統一定義）"""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"  # RUNNINGの代替
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"              # FAILEDの代替
    CANCELLED = "CANCELLED"
    REQUIRES_USER_INPUT = "REQUIRES_USER_INPUT"
