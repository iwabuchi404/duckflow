"""
Duckflow メインエントリーポイント (V2 へ移行済み)
このモジュールは後方互換のために残し、実装は main_v2 へ委譲します。
"""

from .main_v2 import DuckflowAgentV2 as DuckflowAgent
from .main_v2 import main

__all__ = ["DuckflowAgent", "main"]