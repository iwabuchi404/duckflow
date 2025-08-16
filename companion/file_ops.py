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

from codecrafter.ui.rich_ui import rich_ui

# 承認システム
from .approval_system import (
    ApprovalGate, OperationInfo, OperationType, RiskLevel,
    ApprovalResponse, ApprovalRequest
)


class FileOperationError(Exception):
    """ファイル操作エラー"""
    pass


@dataclass
class FileOpOutcome:
    """ファイル操作の結果（V2 仕様）

    UI/ログ/上流ロジックがこの結果契約に依存できるようにする。
    """
    ok: bool
    op: Literal["create", "write", "read", "delete", "mkdir", "move", "copy"]
    path: str
    reason: Optional[str] = None
    before_hash: Optional[str] = None
    after_hash: Optional[str] = None
    changed: bool = False
    content: Optional[str] = None  # 読み取り系で使用


@dataclass
class OperationLog:
    """C-1: 構造化操作ログ
    
    フェーズCで追加される操作の詳細記録
    """
    operation_id: str
    success: bool
    operation: str  # 操作タイプ
    args: Dict[str, Any]  # 操作引数
    preview: Optional[str] = None  # 内容プレビュー
    error_code: Optional[str] = None  # エラーコード
    error_message: Optional[str] = None  # エラーメッセージ
    started_at: datetime = field(default_factory=datetime.now)
    finished_at: Optional[datetime] = None
    session_id: Optional[str] = None
    approval_required: bool = False
    approval_granted: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "operation_id": self.operation_id,
            "success": self.success,
            "operation": self.operation,
            "args": self.args,
            "preview": self.preview,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "session_id": self.session_id,
            "approval_required": self.approval_required,
            "approval_granted": self.approval_granted,
            "duration_seconds": (self.finished_at - self.started_at).total_seconds() if self.finished_at else None
        }
    
    def to_failure_summary(self) -> str:
        """失敗時のサマリー文字列を生成（C-2で使用）"""
        if self.success:
            return ""
        
        duration = ""
        if self.finished_at:
            duration = f" ({(self.finished_at - self.started_at).total_seconds():.1f}秒後)"
        
        return f"""操作失敗 - {self.operation}{duration}
対象: {self.args.get('target', 'unknown')}
エラー: {self.error_message or '不明なエラー'}
コード: {self.error_code or 'N/A'}"""


class SimpleFileOps:
    """シンプルなファイル操作クラス
    
    相棒らしい対話的なファイル操作を提供
    C-1: 構造化操作ログ機能を統合
    """
    
    def __init__(self, approval_gate: Optional[ApprovalGate] = None):
        """初期化
        
        Args:
            approval_gate: 承認ゲート（Noneの場合は新規作成）
        """
        self.current_directory = Path.cwd()
        self.approval_gate = approval_gate or ApprovalGate()
        
        # C-1: 構造化操作ログ
        self.operation_logs: List[OperationLog] = []
        self.max_logs = 100  # 最大ログ保持数
    
    def _create_operation_log(self, operation: str, args: Dict[str, Any], 
                             session_id: Optional[str] = None) -> OperationLog:
        """新しい操作ログを作成
        
        Args:
            operation: 操作タイプ
            args: 操作引数
            session_id: セッションID
            
        Returns:
            OperationLog: 作成されたログ
        """
        operation_id = str(uuid.uuid4())
        preview = None
        
        # プレビューの生成
        if 'content' in args and args['content']:
            content = str(args['content'])
            if len(content) > 100:
                preview = content[:100] + "..."
            else:
                preview = content
        
        log = OperationLog(
            operation_id=operation_id,
            success=False,  # 初期状態は失敗（完了時に更新）
            operation=operation,
            args=args.copy(),
            preview=preview,
            session_id=session_id
        )
        
        self.operation_logs.append(log)
        
        # ログ数制限
        if len(self.operation_logs) > self.max_logs:
            self.operation_logs = self.operation_logs[-self.max_logs:]
        
        return log
    
    def _complete_operation_log(self, log: OperationLog, success: bool, 
                               error_code: Optional[str] = None,
                               error_message: Optional[str] = None) -> None:
        """操作ログを完了
        
        Args:
            log: 更新するログ
            success: 成功フラグ
            error_code: エラーコード
            error_message: エラーメッセージ
        """
        log.success = success
        log.finished_at = datetime.now()
        log.error_code = error_code
        log.error_message = error_message
    
    def get_operation_logs(self, failed_only: bool = False, 
                          limit: Optional[int] = None) -> List[OperationLog]:
        """操作ログを取得
        
        Args:
            failed_only: 失敗したログのみを取得
            limit: 取得するログ数の上限
            
        Returns:
            List[OperationLog]: ログのリスト
        """
        logs = self.operation_logs
        
        if failed_only:
            logs = [log for log in logs if not log.success]
        
        if limit:
            logs = logs[-limit:]
        
        return logs
    
    def get_recent_failures(self, limit: int = 3) -> List[OperationLog]:
        """C-2用: 最近の失敗ログを取得
        
        Args:
            limit: 取得する失敗ログ数の上限
            
        Returns:
            List[OperationLog]: 最近の失敗ログ
        """
        failed_logs = [log for log in self.operation_logs if not log.success]
        return failed_logs[-limit:] if failed_logs else []

    # --- V2 ユーティリティ（冪等/検証） ---
    @staticmethod
    def _sha256_bytes(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def _sha256_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def _hash_file_if_exists(path: Path) -> Optional[str]:
        try:
            if path.exists() and path.is_file():
                return hashlib.sha256(path.read_bytes()).hexdigest()
        except Exception:
            return None
        return None

    def _request_approval(self, operation_type: str, target: str, 
                         description: str, risk_level: RiskLevel, 
                         details: Dict[str, Any], session_id: str = "file_ops") -> bool:
        """承認を要求
        
        Args:
            operation_type: 操作タイプ
            target: 対象ファイル/ディレクトリ
            description: 操作の説明
            risk_level: リスクレベル
            details: 操作の詳細
            session_id: セッションID
            
        Returns:
            bool: 承認された場合True
        """
        try:
            # 操作情報を作成
            try:
                operation_info = OperationInfo(
                    operation_type=operation_type,
                    target=target,
                    description=description,
                    risk_level=risk_level,
                    details=details
                )
            except Exception as info_error:
                rich_ui.print_error(f"操作情報の作成に失敗しました: {info_error}")
                return False  # 操作情報作成失敗時は拒否
            
            # 承認が必要かチェック（エラー時は優雅な劣化）
            try:
                approval_required = self.approval_gate.is_approval_required(operation_info)
            except Exception as check_error:
                rich_ui.print_error(f"承認要求判定でエラーが発生しました: {check_error}")
                # エラー時は安全のため承認必要として処理
                approval_required = True
            
            if not approval_required:
                return True
            
            # 承認要求を作成
            try:
                approval_request = ApprovalRequest(
                    operation_info=operation_info,
                    message=f"ファイル操作の承認が必要です: {description}",
                    timestamp=datetime.now(),
                    session_id=session_id
                )
            except Exception as request_error:
                rich_ui.print_error(f"承認要求の作成に失敗しました: {request_error}")
                return False  # 承認要求作成失敗時は拒否
            
            # 承認を要求（エラー時は優雅な劣化）
            try:
                response = self.approval_gate.request_approval(
                    operation_type, 
                    details, 
                    session_id
                )
                return response.approved
            except Exception as approval_error:
                rich_ui.print_error(f"承認要求でエラーが発生しました: {approval_error}")
                return False  # 承認要求失敗時は拒否
            
        except Exception as e:
            rich_ui.print_error(f"承認処理で予期しないエラーが発生しました: {e}")
            # 予期しないエラー時は安全のため拒否
            return False

    # --- V2: PREVIEW 生成と一体化ヘルパ ---
    @staticmethod
    def _make_diff_preview(current: str, nxt: str, limit: int = 800) -> str:
        try:
            import difflib
            diff = difflib.unified_diff(
                current.splitlines(), nxt.splitlines(),
                fromfile="current", tofile="next", lineterm=""
            )
            text = "\n".join(list(diff))
            if len(text) > limit:
                return text[:limit] + "\n... (diff truncated)"
            return text if text else (nxt[:limit] + ("..." if len(nxt) > limit else ""))
        except Exception:
            # フォールバック: 新内容の冒頭
            return nxt[:limit] + ("..." if len(nxt) > limit else "")

    def apply_with_approval_write(self, file_path: str, content: str, session_id: Optional[str] = None) -> FileOpOutcome:
        """承認→実行→検証を一体化した安全書き込みヘルパ（V2）"""
        path = Path(file_path)
        current_text = ""
        if path.exists() and path.is_file():
            try:
                current_text = path.read_text(encoding="utf-8")
            except Exception:
                current_text = ""

        preview = self._make_diff_preview(current_text, content)
        op_type = "create_file" if not path.exists() else "write_file"

        approved = self._request_approval(
            operation_type=op_type,
            target=str(path),
            description=f"ファイル '{file_path}' を{'作成' if op_type=='create_file' else '更新'}",
            risk_level=RiskLevel.HIGH_RISK,
            details={
                "file_path": str(path),
                "content_length": len(content),
                "file_exists": path.exists(),
                "content": preview,
                "preview_type": "diff"
            },
            session_id=session_id or "file_ops_v2",
        )

        if not approved:
            return FileOpOutcome(
                ok=False,
                op="create" if op_type == "create_file" else "write",
                path=str(path),
                reason="approval_denied",
                before_hash=self._hash_file_if_exists(path),
                after_hash=self._hash_file_if_exists(path),
                changed=False,
            )

        rich_ui.print_message("🔎 PREVIEW(差分) → 承認済み。実行に進みます。", "info")
        outcome = self.create_or_write_file_v2(file_path, content, session_id=session_id)
        if outcome.ok:
            rich_ui.print_message("🏁 RESULT: ファイル操作が検証付きで完了しました。", "success")
        else:
            rich_ui.print_message(f"⚠️ RESULT: 失敗 ({outcome.reason})", "warning")
        return outcome

    # --- V2: 冪等で検証付きの作成/書込 API（既存APIは保持） ---
    def create_or_write_file_v2(self, file_path: str, content: str, session_id: Optional[str] = None) -> FileOpOutcome:
        """新規作成 or 上書き（冪等・検証・結果型）

        - 既存と内容が同一なら changed=False で成功とする。
        - 承認→実行→ポスト条件検証（存在/ハッシュ一致）まで行う。
        """
        path = Path(file_path)

        before_hash = self._hash_file_if_exists(path)
        desired_hash = self._sha256_text(content)

        # 同一内容ならスキップ（成功）
        if before_hash is not None:
            try:
                if path.read_text(encoding="utf-8") == content:
                    return FileOpOutcome(
                        ok=True,
                        op="write",
                        path=str(path),
                        reason="no_change",
                        before_hash=before_hash,
                        after_hash=before_hash,
                        changed=False,
                    )
            except Exception:
                # 読み取り不能時は通常フローへ
                pass

        # 承認要求（create or write）
        op_type = "create_file" if not path.exists() else "write_file"
        approved = self._request_approval(
            operation_type=op_type,
            target=str(path),
            description=f"ファイル '{file_path}' を{'作成' if op_type=='create_file' else '更新'}",
            risk_level=RiskLevel.HIGH_RISK,
            details={
                "file_path": str(path),
                "content_length": len(content),
                "file_exists": path.exists(),
            },
            session_id=session_id or "file_ops_v2",
        )
        if not approved:
            return FileOpOutcome(
                ok=False,
                op="create" if op_type == "create_file" else "write",
                path=str(path),
                reason="approval_denied",
                before_hash=before_hash,
                after_hash=before_hash,
                changed=False,
            )

        # 親ディレクトリ作成
        try:
            if not path.parent.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return FileOpOutcome(
                ok=False,
                op="mkdir",
                path=str(path.parent),
                reason=f"mkdir_failed: {e}",
                before_hash=None,
                after_hash=None,
                changed=False,
            )

        # バックアップ
        backup_bytes: Optional[bytes] = None
        if path.exists() and path.is_file():
            try:
                backup_bytes = path.read_bytes()
            except Exception:
                backup_bytes = None

        # 書き込み実行
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            # 失敗時ロールバック（可能なら）
            if backup_bytes is not None:
                try:
                    path.write_bytes(backup_bytes)
                except Exception:
                    pass
            return FileOpOutcome(
                ok=False,
                op="write" if path.exists() else "create",
                path=str(path),
                reason=f"write_failed: {e}",
                before_hash=before_hash,
                after_hash=self._hash_file_if_exists(path),
                changed=False,
            )

        # 検証
        after_hash = self._hash_file_if_exists(path)
        if (after_hash is None) or (after_hash != desired_hash):
            # 不一致 → 可能ならロールバック
            if backup_bytes is not None:
                try:
                    path.write_bytes(backup_bytes)
                except Exception:
                    pass
            return FileOpOutcome(
                ok=False,
                op="write" if before_hash is not None else "create",
                path=str(path),
                reason="post_condition_failed",
                before_hash=before_hash,
                after_hash=after_hash,
                changed=False,
            )

        return FileOpOutcome(
            ok=True,
            op="write" if before_hash is not None else "create",
            path=str(path),
            reason=None,
            before_hash=before_hash,
            after_hash=after_hash,
            changed=(before_hash != after_hash),
        )

    def read_file_v2(self, file_path: str) -> FileOpOutcome:
        """読み取り（結果型 + ハッシュ付き）"""
        path = Path(file_path)
        if not path.exists():
            return FileOpOutcome(ok=False, op="read", path=str(path), reason="not_found")
        if not path.is_file():
            return FileOpOutcome(ok=False, op="read", path=str(path), reason="not_a_file")
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return FileOpOutcome(ok=False, op="read", path=str(path), reason="decode_error")
        except Exception as e:
            return FileOpOutcome(ok=False, op="read", path=str(path), reason=f"read_failed: {e}")
        h = self._sha256_text(content)
        return FileOpOutcome(ok=True, op="read", path=str(path), after_hash=h, content=content)
    
    def create_file(self, file_path: str, content: str = "", session_id: Optional[str] = None) -> Dict[str, Any]:
        """ファイルを作成（C-1: ログ機能統合版）
        
        Args:
            file_path: ファイルパス
            content: ファイル内容（デフォルトは空）
            session_id: セッションID
            
        Returns:
            Dict[str, Any]: 操作結果
        """
        # V2 フラグが有効なら新実装に委譲
        if os.getenv("FILE_OPS_V2") == "1":
            outcome = self.apply_with_approval_write(file_path, content, session_id=session_id)
            if not outcome.ok:
                return {"success": False, "message": outcome.reason or "unknown_error", "path": outcome.path, "reason": outcome.reason}
            size = Path(outcome.path).stat().st_size if Path(outcome.path).exists() else 0
            return {
                "success": True,
                "message": f"ファイル {file_path} を作成しました",
                "path": outcome.path,
                "size": size,
                "created": datetime.now().isoformat(),
            }

        # C-1: 操作ログを作成（V1）
        operation_log = self._create_operation_log(
            operation="create_file",
            args={
                "target": file_path,
                "content": content,
                "content_length": len(content)
            },
            session_id=session_id
        )
        
        try:
            path = Path(file_path)
            
            # 承認を要求
            approval_granted = self._request_approval(
                operation_type="create_file",
                target=str(path),
                description=f"ファイル '{file_path}' を作成",
                risk_level=RiskLevel.HIGH_RISK,
                details={
                    "file_path": str(path),
                    "content_length": len(content),
                    "content_preview": content[:100] + "..." if len(content) > 100 else content
                }
            )
            
            # ログに承認情報を記録
            operation_log.approval_required = True
            operation_log.approval_granted = approval_granted
            
            if not approval_granted:
                error_msg = f"ファイル作成が拒否されました: {file_path}"
                rich_ui.print_message(f"🚫 {error_msg}", "warning")
                
                # C-1: 失敗ログを完了
                self._complete_operation_log(
                    operation_log, 
                    success=False, 
                    error_code="APPROVAL_DENIED",
                    error_message=error_msg
                )
                
                return {
                    "success": False,
                    "message": error_msg,
                    "path": str(path),
                    "reason": "approval_denied"
                }
            
            rich_ui.print_message("📝 ファイルを作成しています...", "info")
            time.sleep(0.3)
            
            path = Path(file_path)
            
            # 親ディレクトリが存在しない場合は作成
            if not path.parent.exists():
                rich_ui.print_message(f"📁 ディレクトリ {path.parent} を作成します...", "info")
                path.parent.mkdir(parents=True, exist_ok=True)
                time.sleep(0.2)
            
            # ファイルが既に存在する場合の確認
            if path.exists():
                rich_ui.print_message(f"⚠️ ファイル {file_path} は既に存在します", "warning")
                rich_ui.print_message("🔄 上書きします...", "info")
            
            # ファイル作成
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # 成功メッセージ
            file_size = path.stat().st_size
            rich_ui.print_message(f"✅ ファイルを作成しました！({file_size} bytes)", "success")
            
            # C-1: 成功ログを完了
            self._complete_operation_log(operation_log, success=True)
            
            return {
                "success": True,
                "message": f"ファイル {file_path} を作成しました",
                "path": str(path),
                "size": file_size,
                "created": datetime.now().isoformat(),
                "operation_id": operation_log.operation_id  # C-1: ログIDを含める
            }
            
        except PermissionError as e:
            error_msg = f"権限がありません: {file_path}"
            rich_ui.print_message(f"❌ {error_msg}", "error")
            
            # C-1: 失敗ログを完了
            self._complete_operation_log(
                operation_log, 
                success=False, 
                error_code="PERMISSION_ERROR",
                error_message=error_msg
            )
            
            raise FileOperationError(error_msg)
        except Exception as e:
            error_msg = f"ファイル作成に失敗しました: {str(e)}"
            rich_ui.print_message(f"❌ {error_msg}", "error")
            
            # C-1: 失敗ログを完了
            self._complete_operation_log(
                operation_log, 
                success=False, 
                error_code="GENERAL_ERROR",
                error_message=error_msg
            )
            
            raise FileOperationError(error_msg)
    
    def read_file(self, file_path: str) -> str:
        """ファイルを読み取り
        
        Args:
            file_path: ファイルパス
            
        Returns:
            str: ファイル内容
            
        Note:
            読み取り操作は低リスクのため承認をバイパス
        """
        try:
            rich_ui.print_message("📖 ファイルを読み取っています...", "info")
            time.sleep(0.2)
            
            path = Path(file_path)
            
            if not path.exists():
                error_msg = f"ファイルが見つかりません: {file_path}"
                rich_ui.print_message(f"❌ {error_msg}", "error")
                raise FileOperationError(error_msg)
            
            if not path.is_file():
                error_msg = f"これはファイルではありません: {file_path}"
                rich_ui.print_message(f"❌ {error_msg}", "error")
                raise FileOperationError(error_msg)
            
            # ファイル読み取り
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 成功メッセージ
            lines = len(content.split('\n'))
            chars = len(content)
            rich_ui.print_message(f"✅ ファイルを読み取りました！({lines}行, {chars}文字)", "success")
            
            return content
            
        except UnicodeDecodeError:
            error_msg = f"文字エンコーディングエラー: {file_path}"
            rich_ui.print_message(f"❌ {error_msg}", "error")
            raise FileOperationError(error_msg)
        except PermissionError:
            error_msg = f"読み取り権限がありません: {file_path}"
            rich_ui.print_message(f"❌ {error_msg}", "error")
            raise FileOperationError(error_msg)
        except Exception as e:
            error_msg = f"ファイル読み取りに失敗しました: {str(e)}"
            rich_ui.print_message(f"❌ {error_msg}", "error")
            raise FileOperationError(error_msg)
    
    def write_file(self, file_path: str, content: str) -> Dict[str, Any]:
        """ファイルに書き込み
        
        Args:
            file_path: ファイルパス
            content: 書き込む内容
            
        Returns:
            Dict[str, Any]: 操作結果
        """
        # V2 フラグが有効なら新実装に委譲
        if os.getenv("FILE_OPS_V2") == "1":
            outcome = self.apply_with_approval_write(file_path, content)
            if not outcome.ok:
                return {"success": False, "message": outcome.reason or "unknown_error", "path": outcome.path, "reason": outcome.reason}
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

        try:
            path = Path(file_path)
            
            # 既存ファイルかどうかを確認
            file_exists = path.exists()
            operation_type = "write_file" if file_exists else "create_file"
            description = f"ファイル '{file_path}' を{'更新' if file_exists else '作成'}"
            
            # 承認を要求
            approval_granted = self._request_approval(
                operation_type=operation_type,
                target=str(path),
                description=description,
                risk_level=RiskLevel.HIGH_RISK,
                details={
                    "file_path": str(path),
                    "content_length": len(content),
                    "content_preview": content[:100] + "..." if len(content) > 100 else content,
                    "file_exists": file_exists,
                    "lines": len(content.split('\n'))
                }
            )
            
            if not approval_granted:
                error_msg = f"ファイル書き込みが拒否されました: {file_path}"
                rich_ui.print_message(f"🚫 {error_msg}", "warning")
                return {
                    "success": False,
                    "message": error_msg,
                    "path": str(path),
                    "reason": "approval_denied"
                }
            
            rich_ui.print_message("✍️ ファイルに書き込んでいます...", "info")
            time.sleep(0.3)
            
            path = Path(file_path)
            
            # 親ディレクトリが存在しない場合は作成
            if not path.parent.exists():
                rich_ui.print_message(f"📁 ディレクトリ {path.parent} を作成します...", "info")
                path.parent.mkdir(parents=True, exist_ok=True)
                time.sleep(0.2)
            
            # ファイル書き込み
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # 成功メッセージ
            file_size = path.stat().st_size
            lines = len(content.split('\n'))
            rich_ui.print_message(f"✅ ファイルに書き込みました！({lines}行, {file_size} bytes)", "success")
            
            return {
                "success": True,
                "message": f"ファイル {file_path} に書き込みました",
                "path": str(path),
                "size": file_size,
                "lines": lines,
                "modified": datetime.now().isoformat()
            }
            
        except PermissionError:
            error_msg = f"書き込み権限がありません: {file_path}"
            rich_ui.print_message(f"❌ {error_msg}", "error")
            raise FileOperationError(error_msg)
        except Exception as e:
            error_msg = f"ファイル書き込みに失敗しました: {str(e)}"
            rich_ui.print_message(f"❌ {error_msg}", "error")
            raise FileOperationError(error_msg)
    
    def list_files(self, directory_path: str = ".") -> List[Dict[str, Any]]:
        """ディレクトリ内のファイル一覧を取得
        
        Args:
            directory_path: ディレクトリパス（デフォルトは現在のディレクトリ）
            
        Returns:
            List[Dict[str, Any]]: ファイル情報のリスト
            
        Note:
            一覧表示操作は低リスクのため承認をバイパス
        """
        try:
            rich_ui.print_message("📂 ファイル一覧を取得しています...", "info")
            time.sleep(0.2)
            
            path = Path(directory_path)
            
            if not path.exists():
                error_msg = f"ディレクトリが見つかりません: {directory_path}"
                rich_ui.print_message(f"❌ {error_msg}", "error")
                raise FileOperationError(error_msg)
            
            if not path.is_dir():
                error_msg = f"これはディレクトリではありません: {directory_path}"
                rich_ui.print_message(f"❌ {error_msg}", "error")
                raise FileOperationError(error_msg)
            
            # ファイル一覧取得
            files = []
            for item in path.iterdir():
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
                    # アクセスできないファイルはスキップ
                    continue
            
            # ソート（ディレクトリ優先、その後名前順）
            files.sort(key=lambda x: (x["type"] != "directory", x["name"].lower()))
            
            # 成功メッセージ
            file_count = len([f for f in files if f["type"] == "file"])
            dir_count = len([f for f in files if f["type"] == "directory"])
            rich_ui.print_message(f"✅ ファイル一覧を取得しました！(ファイル: {file_count}, ディレクトリ: {dir_count})", "success")
            
            return files
            
        except PermissionError:
            error_msg = f"ディレクトリへのアクセス権限がありません: {directory_path}"
            rich_ui.print_message(f"❌ {error_msg}", "error")
            raise FileOperationError(error_msg)
        except Exception as e:
            error_msg = f"ファイル一覧の取得に失敗しました: {str(e)}"
            rich_ui.print_message(f"❌ {error_msg}", "error")
            raise FileOperationError(error_msg)
    
    def file_exists(self, file_path: str) -> bool:
        """ファイルの存在確認
        
        Args:
            file_path: ファイルパス
            
        Returns:
            bool: ファイルが存在する場合True
        """
        return Path(file_path).exists()
    
    def get_current_directory(self) -> str:
        """現在のディレクトリを取得
        
        Returns:
            str: 現在のディレクトリパス
        """
        return str(Path.cwd())
    
    def create_directory(self, directory_path: str) -> Dict[str, Any]:
        """ディレクトリを作成
        
        Args:
            directory_path: 作成するディレクトリのパス
            
        Returns:
            Dict[str, Any]: 操作結果
        """
        try:
            path = Path(directory_path)
            
            # 既に存在する場合
            if path.exists():
                if path.is_dir():
                    return {
                        "success": True,
                        "message": f"ディレクトリ '{directory_path}' は既に存在します",
                        "path": str(path.absolute())
                    }
                else:
                    return {
                        "success": False,
                        "reason": "file_exists",
                        "message": f"'{directory_path}' は既にファイルとして存在します"
                    }
            
            # 承認を要求
            if not self._request_approval(
                "create_directory", 
                directory_path,
                f"ディレクトリ '{directory_path}' を作成",
                RiskLevel.LOW_RISK,
                {
                    "operation": "create_directory",
                    "path": directory_path,
                    "parent_exists": path.parent.exists()
                }
            ):
                return {
                    "success": False,
                    "reason": "approval_denied",
                    "message": f"ディレクトリ作成が拒否されました: {directory_path}"
                }
            
            # ディレクトリを作成（親ディレクトリも含めて）
            path.mkdir(parents=True, exist_ok=True)
            
            return {
                "success": True,
                "message": f"ディレクトリ '{directory_path}' を作成しました",
                "path": str(path.absolute())
            }
            
        except PermissionError:
            error_msg = f"ディレクトリ作成の権限がありません: {directory_path}"
            rich_ui.print_error(error_msg)
            raise FileOperationError(error_msg)
        except Exception as e:
            error_msg = f"ディレクトリ作成に失敗しました: {directory_path} - {str(e)}"
            rich_ui.print_error(error_msg)
            raise FileOperationError(error_msg)
    
    def change_directory(self, directory_path: str) -> Dict[str, Any]:
        """ディレクトリを変更
        
        Args:
            directory_path: 変更先ディレクトリパス
            
        Returns:
            Dict[str, Any]: 操作結果
        """
        try:
            rich_ui.print_message("📁 ディレクトリを変更しています...", "info")
            time.sleep(0.2)
            
            path = Path(directory_path).resolve()
            
            if not path.exists():
                error_msg = f"ディレクトリが見つかりません: {directory_path}"
                rich_ui.print_message(f"❌ {error_msg}", "error")
                raise FileOperationError(error_msg)
            
            if not path.is_dir():
                error_msg = f"これはディレクトリではありません: {directory_path}"
                rich_ui.print_message(f"❌ {error_msg}", "error")
                raise FileOperationError(error_msg)
            
            # ディレクトリ変更
            os.chdir(path)
            self.current_directory = path
            
            # 成功メッセージ
            rich_ui.print_message(f"✅ ディレクトリを変更しました: {path}", "success")
            
            return {
                "success": True,
                "message": f"ディレクトリを {path} に変更しました",
                "old_path": str(Path.cwd()),
                "new_path": str(path)
            }
            
        except PermissionError:
            error_msg = f"ディレクトリへのアクセス権限がありません: {directory_path}"
            rich_ui.print_message(f"❌ {error_msg}", "error")
            raise FileOperationError(error_msg)
        except Exception as e:
            error_msg = f"ディレクトリ変更に失敗しました: {str(e)}"
            rich_ui.print_message(f"❌ {error_msg}", "error")
            raise FileOperationError(error_msg)
