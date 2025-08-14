"""
Duckflow Companion - シンプルな相棒実装
Phase 1.5: 基本的なファイル操作機能付き相棒
"""

from .core import CompanionCore
from .file_ops import SimpleFileOps, FileOperationError

__all__ = ['CompanionCore', 'SimpleFileOps', 'FileOperationError']

# Phase 2以降で実装予定:
# from .actions import ActionSubsystem
# from .memory import MemoryStream