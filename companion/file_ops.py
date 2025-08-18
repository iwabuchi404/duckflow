"""
SimpleFileOps - シンプルなファイル操作
Phase 1.5: 基本的なファイル操作機能

設計思想:
- 複雑な機能を排除し、基本的な操作のみ
- エラーメッセージは自然で分かりやすく
- 相棒らしい対話的な操作
"""

import os
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Literal
from datetime import datetime
from dataclasses import dataclass, field
import hashlib
import uuid
import asyncio

from codecrafter.ui.rich_ui import rich_ui
from codecrafter.base.config import ConfigManager

# 新しいシンプル承認システム
from .simple_approval import SimpleApprovalGate, ApprovalRequest, RiskLevel, ApprovalResult, ApprovalMode


class FileOperationError(Exception):
    """ファイル操作エラー"""
    pass


@dataclass
class FileOpOutcome:
    """ファイル操作の結果（V2 仕様）"""
    ok: bool
    op: Literal["create", "write", "read", "delete", "mkdir", "move", "copy"]
    path: str
    reason: Optional[str] = None
    before_hash: Optional[str] = None
    after_hash: Optional[str] = None
    changed: bool = False
    content: Optional[str] = None


class SimpleFileOps:
    """シンプルなファイル操作クラス"""
    
    def __init__(self, approval_mode: ApprovalMode = ApprovalMode.STANDARD, llm_enabled: bool = True):
        """初期化
        
        Args:
            approval_mode: 承認モード
            llm_enabled: LLM強化承認を有効にするか
        """
        self.current_directory = Path.cwd()
        self.approval_gate = SimpleApprovalGate(mode_override=approval_mode, llm_enabled=llm_enabled)
        self.llm_enabled = llm_enabled
        try:
            import os as _os
            from codecrafter.base.config import ConfigManager as _CM
            self.debug = _os.getenv("FILE_OPS_DEBUG") == "1" or _CM().is_debug_mode()
        except Exception:
            self.debug = False

    def _assess_write_risk(self, file_path: str) -> RiskLevel:
        """書き込みリスク評価"""
        if file_path.startswith('.') or 'config' in file_path.lower():
            return RiskLevel.HIGH
        elif file_path.endswith(('.py', '.js', '.ts', '.sh', '.bat')):
            return RiskLevel.MEDIUM
        elif file_path.endswith(('.txt', '.md', '.json', '.yaml', '.yml')):
            return RiskLevel.LOW
        else:
            return RiskLevel.MEDIUM

    def write_file_with_approval(self, file_path: str, content: str) -> FileOpOutcome:
        """承認付きファイル書き込み"""
        request = ApprovalRequest(
            operation="ファイル書き込み",
            description=f"ファイル '{file_path}' に内容を書き込みます",
            target=file_path,
            risk_level=self._assess_write_risk(file_path),
            details=f"サイズ: {len(content)}文字\n内容プレビュー:\n{content[:200]}{'...' if len(content) > 200 else ''}"
        )
        
        approval = self.approval_gate.request_approval(request)
        
        if not approval.approved:
            return FileOpOutcome(
                ok=False,
                op="write",
                path=file_path,
                reason=f"ユーザーによる拒否: {approval.reason}"
            )
        
        path = Path(file_path)
        before_hash = self._hash_file_if_exists(path)
        try:
            if not path.parent.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            after_hash = self._hash_file_if_exists(path)
            return FileOpOutcome(
                ok=True,
                op="write",
                path=str(path),
                before_hash=before_hash,
                after_hash=after_hash,
                changed=(before_hash != after_hash)
            )
        except Exception as e:
            return FileOpOutcome(ok=False, op="write", path=str(path), reason=str(e))
    
    async def write_file_with_llm_approval(self, file_path: str, content: str) -> FileOpOutcome:
        """LLM強化承認付きファイル書き込み"""
        request = ApprovalRequest(
            operation="ファイル書き込み",
            description=f"ファイル '{file_path}' に内容を書き込みます",
            target=file_path,
            risk_level=self._assess_write_risk(file_path),
            details=f"サイズ: {len(content)}文字\n内容プレビュー:\n{content[:200]}{'...' if len(content) > 200 else ''}"
        )
        
        # LLM強化承認を使用
        if self.llm_enabled and hasattr(self.approval_gate, 'request_approval_llm_enhanced'):
            approval = await self.approval_gate.request_approval_llm_enhanced(request)
        else:
            # フォールバック: 標準承認
            approval = self.approval_gate.request_approval(request)
        
        if not approval.approved:
            return FileOpOutcome(
                ok=False,
                op="write",
                path=file_path,
                reason=f"ユーザーによる拒否: {approval.reason}"
            )
        
        path = Path(file_path)
        before_hash = self._hash_file_if_exists(path)
        try:
            if not path.parent.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            after_hash = self._hash_file_if_exists(path)
            return FileOpOutcome(
                ok=True,
                op="write",
                path=str(path),
                before_hash=before_hash,
                after_hash=after_hash,
                changed=(before_hash != after_hash)
            )
        except Exception as e:
            return FileOpOutcome(ok=False, op="write", path=str(path), reason=str(e))

    @staticmethod
    def _hash_file_if_exists(path: Path) -> Optional[str]:
        try:
            if path.exists() and path.is_file():
                return hashlib.sha256(path.read_bytes()).hexdigest()
        except Exception:
            return None
        return None

    def create_file(self, file_path: str, content: str = "") -> Dict[str, Any]:
        """ファイルを作成"""
        outcome = self.write_file_with_approval(file_path, content)
        if not outcome.ok:
            return {"success": False, "message": outcome.reason or "unknown_error", "path": outcome.path}
        size = Path(outcome.path).stat().st_size if Path(outcome.path).exists() else 0
        return {
            "success": True,
            "message": f"ファイル {file_path} を作成しました",
            "path": outcome.path,
            "size": size,
            "created": datetime.now().isoformat(),
        }

    def write_file(self, file_path: str, content: str) -> Dict[str, Any]:
        """ファイルに書き込み"""
        outcome = self.write_file_with_approval(file_path, content)
        if not outcome.ok:
            return {"success": False, "message": outcome.reason or "unknown_error", "path": outcome.path}
        size = Path(outcome.path).stat().st_size if Path(outcome.path).exists() else 0
        lines = len(content.split('\n'))
        return {
            "success": True,
            "message": f"ファイル {file_path} に書き込みました",
            "path": outcome.path,
            "size": size,
            "lines": lines,
            "modified": datetime.now().isoformat(),
        }
    
    async def write_file_llm(self, file_path: str, content: str) -> Dict[str, Any]:
        """LLM強化ファイル書き込み"""
        outcome = await self.write_file_with_llm_approval(file_path, content)
        if not outcome.ok:
            return {"success": False, "message": outcome.reason or "unknown_error", "path": outcome.path}
        size = Path(outcome.path).stat().st_size if Path(outcome.path).exists() else 0
        lines = len(content.split('\n'))
        return {
            "success": True,
            "message": f"ファイル {file_path} に書き込みました（LLM強化承認）",
            "path": outcome.path,
            "size": size,
            "lines": lines,
            "modified": datetime.now().isoformat(),
        }
    
    async def create_file_llm(self, file_path: str, content: str = "") -> Dict[str, Any]:
        """LLM強化ファイル作成"""
        outcome = await self.write_file_with_llm_approval(file_path, content)
        if not outcome.ok:
            return {"success": False, "message": outcome.reason or "unknown_error", "path": outcome.path}
        size = Path(outcome.path).stat().st_size if Path(outcome.path).exists() else 0
        return {
            "success": True,
            "message": f"ファイル {file_path} を作成しました（LLM強化承認）",
            "path": outcome.path,
            "size": size,
            "created": datetime.now().isoformat(),
        }

    def read_file(self, file_path: str) -> str:
        """ファイルを読み取り"""
        path = Path(file_path)
        if not path.is_file():
            raise FileOperationError(f"ファイルが見つからないか、ファイルではありません: {file_path}")
        try:
            return path.read_text(encoding="utf-8")
        except Exception as e:
            raise FileOperationError(f"ファイル読み取り失敗: {e}")

    def list_files(self, directory_path: str = ".") -> List[Dict[str, Any]]:
        """ディレクトリ内のファイル一覧を取得"""
        try:
            path = Path(directory_path)
            if not path.is_dir():
                raise FileOperationError(f"これはディレクトリではありません: {directory_path}")
            
            files = []
            for item in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                try:
                    stat = item.stat()
                    files.append({
                        "name": item.name,
                        "path": str(item),
                        "type": "directory" if item.is_dir() else "file",
                        "size": stat.st_size if item.is_file() else 0,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
                except (PermissionError, OSError):
                    continue
            return files
        except Exception as e:
            raise FileOperationError(f"ファイル一覧の取得に失敗しました: {str(e)}")

    def create_directory(self, directory_path: str) -> Dict[str, Any]:
        """ディレクトリを作成"""
        request = ApprovalRequest(
            operation="ディレクトリ作成",
            description=f"ディレクトリ '{directory_path}' を作成します",
            target=directory_path,
            risk_level=RiskLevel.LOW
        )
        approval = self.approval_gate.request_approval(request)
        if not approval.approved:
            return {"success": False, "message": f"ユーザーによる拒否: {approval.reason}", "path": directory_path}

        try:
            path = Path(directory_path)
            path.mkdir(parents=True, exist_ok=True)
            return {"success": True, "message": f"ディレクトリ '{directory_path}' を作成しました", "path": str(path.absolute())}
        except Exception as e:
            raise FileOperationError(f"ディレクトリ作成に失敗しました: {directory_path} - {str(e)}")
