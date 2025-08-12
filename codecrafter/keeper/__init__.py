"""
Duck Keeper - 統合アクセス制御システム

プロジェクトの全てのファイルシステム操作を統一されたルールに基づき、
効率的かつ安全に実行するための包括的なシステム
"""

from .duck_policy import DuckKeeperPolicy, duck_keeper
from .duck_fs import DuckFS, duck_fs, FileReadResult, FileWriteResult, DuckFileSystemError

__all__ = [
    "DuckKeeperPolicy", 
    "duck_keeper",
    "DuckFS", 
    "duck_fs",
    "FileReadResult",
    "FileWriteResult",
    "DuckFileSystemError"
]