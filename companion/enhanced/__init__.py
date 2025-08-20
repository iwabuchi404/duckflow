"""
Enhanced v2.0 専用モジュール

状態管理統一版のChatLoopとTaskLoopを提供。
AgentStateを直接参照し、StateMachineへの依存を完全に排除。
"""

from .chat_loop import EnhancedChatLoop
from .task_loop import EnhancedTaskLoop

__all__ = [
    'EnhancedChatLoop',
    'EnhancedTaskLoop'
]
