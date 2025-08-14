"""
User Approval System - ユーザー承認システム
Duckflow Companionのセキュリティ機能

設計思想:
- すべての危険操作は承認ゲートを通る
- AIが承認システムをバイパスできない
- 相棒らしい自然な対話を維持
- フェイルセーフ設計（エラー時は操作拒否）
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
import json
import os
from pathlib import Path


class RiskLevel(Enum):
    """操作のリスクレベル"""
    LOW_RISK = "low_risk"        # ファイル読み取り、一覧表示
    HIGH_RISK = "high_risk"      # ファイル作成、編集、コード実行
    CRITICAL_RISK = "critical_risk"  # システム操作（将来拡張用）


class ApprovalMode(Enum):
    """承認システムのモード"""
    STRICT = "strict"      # すべてのファイル操作で承認
    STANDARD = "standard"  # HIGH_RISK操作のみ承認
    TRUSTED = "trusted"    # 承認なし（デバッグ用）


@dataclass
class OperationInfo:
    """操作情報の詳細"""
    operation_type: str        # "create_file", "write_file", "execute_code", etc.
    target: str               # ファイル名、コマンド等
    description: str          # 操作の説明
    risk_level: RiskLevel     # リスクレベル
    details: Dict[str, Any]   # 追加詳細情報
    preview: Optional[str] = None    # 内容のプレビュー
    
    def __post_init__(self):
        """データ検証"""
        if not self.operation_type:
            raise ValueError("operation_type は必須です")
        if not self.target:
            raise ValueError("target は必須です")
        if not self.description:
            raise ValueError("description は必須です")
        if not isinstance(self.risk_level, RiskLevel):
            raise ValueError("risk_level は RiskLevel enum である必要があります")
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換
        
        Returns:
            Dict[str, Any]: 操作情報の辞書
        """
        return {
            "operation_type": self.operation_type,
            "target": self.target,
            "description": self.description,
            "risk_level": self.risk_level.value if hasattr(self.risk_level, 'value') else str(self.risk_level),
            "details": self.details,
            "preview": self.preview
        }


@dataclass
class ApprovalRequest:
    """承認要求の情報"""
    operation_info: OperationInfo
    message: str              # ユーザーへの説明メッセージ
    timestamp: datetime
    session_id: str
    
    def __post_init__(self):
        """データ検証"""
        if not isinstance(self.operation_info, OperationInfo):
            raise ValueError("operation_info は OperationInfo である必要があります")
        if not self.message:
            raise ValueError("message は必須です")
        if not self.session_id:
            raise ValueError("session_id は必須です")


@dataclass
class ApprovalResponse:
    """承認応答の情報"""
    approved: bool
    reason: Optional[str] = None     # 拒否理由（オプション）
    timestamp: Optional[datetime] = None
    alternative_suggested: bool = False
    details: Dict[str, Any] = field(default_factory=dict)  # 追加詳細情報
    
    def __post_init__(self):
        """データ検証とデフォルト値設定"""
        if self.timestamp is None:
            self.timestamp = datetime.now()
        
        # 拒否された場合は理由が推奨される
        if not self.approved and not self.reason:
            self.reason = "ユーザーにより拒否されました"


@dataclass
class ApprovalLog:
    """承認ログの記録"""
    timestamp: datetime
    operation_info: OperationInfo
    approved: bool
    user_response_time: float  # 応答時間（秒）
    session_id: str
    
    def __post_init__(self):
        """データ検証"""
        if not isinstance(self.operation_info, OperationInfo):
            raise ValueError("operation_info は OperationInfo である必要があります")
        if self.user_response_time < 0:
            raise ValueError("user_response_time は0以上である必要があります")


# 承認システム関連の例外クラス

class ApprovalSystemError(Exception):
    """承認システムの基底例外クラス"""
    pass


class ApprovalTimeoutError(ApprovalSystemError):
    """承認要求がタイムアウトした場合"""
    
    def __init__(self, message: str, timeout_seconds: Optional[int] = None,
                 operation_info: Optional['OperationInfo'] = None):
        super().__init__(message)
        self.timeout_seconds = timeout_seconds
        self.operation_info = operation_info
        self.timestamp = datetime.now()


class ApprovalBypassAttemptError(ApprovalSystemError):
    """承認システムのバイパス試行を検出"""
    
    def __init__(self, message: str, operation_info: Optional['OperationInfo'] = None, 
                 attempt_details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.operation_info = operation_info
        self.attempt_details = attempt_details or {}
        self.timestamp = datetime.now()


class ApprovalUIError(ApprovalSystemError):
    """承認UI関連のエラー"""
    
    def __init__(self, message: str, ui_component: Optional[str] = None,
                 original_error: Optional[Exception] = None):
        super().__init__(message)
        self.ui_component = ui_component
        self.original_error = original_error
        self.timestamp = datetime.now()


class SecurityViolationError(ApprovalSystemError):
    """セキュリティ違反エラー"""
    
    def __init__(self, message: str, violation_type: str, 
                 details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.violation_type = violation_type
        self.details = details or {}
        self.timestamp = datetime.now()


class ApprovalSystemFailureError(ApprovalSystemError):
    """承認システム全体の障害エラー"""
    
    def __init__(self, message: str, failure_type: str,
                 component: Optional[str] = None,
                 original_error: Optional[Exception] = None):
        super().__init__(message)
        self.failure_type = failure_type
        self.component = component
        self.original_error = original_error
        self.timestamp = datetime.now()


class ApprovalConfigurationError(ApprovalSystemError):
    """承認システム設定エラー"""
    
    def __init__(self, message: str, config_key: Optional[str] = None,
                 config_value: Optional[Any] = None):
        super().__init__(message)
        self.config_key = config_key
        self.config_value = config_value
        self.timestamp = datetime.now()


# 操作タイプの定数
class OperationType:
    """操作タイプの定数定義"""
    
    # ファイル操作
    CREATE_FILE = "create_file"
    WRITE_FILE = "write_file"
    READ_FILE = "read_file"
    DELETE_FILE = "delete_file"
    LIST_FILES = "list_files"
    
    # ディレクトリ操作
    CREATE_DIRECTORY = "create_directory"
    DELETE_DIRECTORY = "delete_directory"
    CHANGE_DIRECTORY = "change_directory"
    
    # コード実行
    EXECUTE_PYTHON = "execute_python"
    EXECUTE_COMMAND = "execute_command"
    RUN_TESTS = "run_tests"
    
    # システム操作（将来拡張用）
    INSTALL_PACKAGE = "install_package"
    MODIFY_SYSTEM = "modify_system"


# リスクレベルマッピング
OPERATION_RISK_MAPPING = {
    # 低リスク操作
    OperationType.READ_FILE: RiskLevel.LOW_RISK,
    OperationType.LIST_FILES: RiskLevel.LOW_RISK,
    
    # 高リスク操作
    OperationType.CREATE_FILE: RiskLevel.HIGH_RISK,
    OperationType.WRITE_FILE: RiskLevel.HIGH_RISK,
    OperationType.DELETE_FILE: RiskLevel.HIGH_RISK,
    OperationType.CREATE_DIRECTORY: RiskLevel.HIGH_RISK,
    OperationType.DELETE_DIRECTORY: RiskLevel.HIGH_RISK,
    OperationType.EXECUTE_PYTHON: RiskLevel.HIGH_RISK,
    OperationType.EXECUTE_COMMAND: RiskLevel.HIGH_RISK,
    OperationType.RUN_TESTS: RiskLevel.HIGH_RISK,
    
    # 重要リスク操作（将来拡張用）
    OperationType.INSTALL_PACKAGE: RiskLevel.CRITICAL_RISK,
    OperationType.MODIFY_SYSTEM: RiskLevel.CRITICAL_RISK,
}


class OperationAnalyzer:
    """操作の分析とリスク判定を行うクラス
    
    設計思想:
    - 操作の詳細を分析してOperationInfoを生成
    - リスクレベルを正確に判定
    - ユーザー向けの分かりやすい説明を生成
    """
    
    def __init__(self):
        """初期化"""
        self.risk_mapping = OPERATION_RISK_MAPPING.copy()
    
    def analyze_operation(self, operation_type: str, params: Dict[str, Any]) -> OperationInfo:
        """操作を分析してOperationInfoを生成
        
        Args:
            operation_type: 操作タイプ（OperationType定数）
            params: 操作パラメータ（target, content等）
            
        Returns:
            OperationInfo: 分析された操作情報
            
        Raises:
            ValueError: 無効な操作タイプまたはパラメータ
        """
        if not operation_type:
            raise ValueError("operation_type は必須です")
        
        if not isinstance(params, dict):
            raise ValueError("params は辞書である必要があります")
        
        # ターゲットの取得
        target = params.get('target', '')
        if not target:
            raise ValueError("params に 'target' は必須です")
        
        # リスクレベルの判定
        risk_level = self.classify_risk(operation_type, target)
        
        # 説明の生成
        description = self.generate_description(operation_type, params)
        
        # プレビューの生成（該当する場合）
        preview = self._generate_preview(operation_type, params)
        
        return OperationInfo(
            operation_type=operation_type,
            target=target,
            description=description,
            risk_level=risk_level,
            details=params.copy(),
            preview=preview
        )
    
    def classify_risk(self, operation_type: str, target: str) -> RiskLevel:
        """操作のリスクレベルを判定
        
        Args:
            operation_type: 操作タイプ
            target: 操作対象（ファイル名等）
            
        Returns:
            RiskLevel: 判定されたリスクレベル
        """
        # 基本的なリスクレベル
        base_risk = self.risk_mapping.get(operation_type, RiskLevel.HIGH_RISK)
        
        # ターゲットに基づく追加判定
        if target:
            # システムファイルや重要なディレクトリの場合はリスクを上げる
            dangerous_patterns = [
                '/etc/', '/sys/', '/proc/', 'C:\\Windows\\', 'C:\\System32\\',
                '.ssh/', '.git/config', 'passwd', 'shadow'
            ]
            
            for pattern in dangerous_patterns:
                if pattern in target:
                    if base_risk == RiskLevel.HIGH_RISK:
                        return RiskLevel.CRITICAL_RISK
                    elif base_risk == RiskLevel.LOW_RISK:
                        return RiskLevel.HIGH_RISK
        
        return base_risk
    
    def generate_description(self, operation_type: str, params: Dict[str, Any]) -> str:
        """ユーザー向けの操作説明を生成
        
        Args:
            operation_type: 操作タイプ
            params: 操作パラメータ
            
        Returns:
            str: 分かりやすい操作説明
        """
        target = params.get('target', '不明')
        
        descriptions = {
            OperationType.CREATE_FILE: f"ファイル '{target}' を作成",
            OperationType.WRITE_FILE: f"ファイル '{target}' に書き込み",
            OperationType.READ_FILE: f"ファイル '{target}' を読み取り",
            OperationType.DELETE_FILE: f"ファイル '{target}' を削除",
            OperationType.LIST_FILES: f"ディレクトリ '{target}' のファイル一覧を表示",
            OperationType.CREATE_DIRECTORY: f"ディレクトリ '{target}' を作成",
            OperationType.DELETE_DIRECTORY: f"ディレクトリ '{target}' を削除",
            OperationType.CHANGE_DIRECTORY: f"ディレクトリを '{target}' に変更",
            OperationType.EXECUTE_PYTHON: f"Pythonファイル '{target}' を実行",
            OperationType.EXECUTE_COMMAND: f"コマンド '{target}' を実行",
            OperationType.RUN_TESTS: f"テスト '{target}' を実行",
            OperationType.INSTALL_PACKAGE: f"パッケージ '{target}' をインストール",
            OperationType.MODIFY_SYSTEM: f"システム設定 '{target}' を変更",
        }
        
        base_description = descriptions.get(operation_type, f"操作 '{operation_type}' を実行")
        
        # 追加情報があれば含める
        if 'content' in params and params['content']:
            content_preview = params['content'][:50]
            if len(params['content']) > 50:
                content_preview += "..."
            base_description += f" (内容: {content_preview})"
        
        return base_description
    
    def _generate_preview(self, operation_type: str, params: Dict[str, Any]) -> Optional[str]:
        """操作のプレビューを生成（該当する場合）
        
        Args:
            operation_type: 操作タイプ
            params: 操作パラメータ
            
        Returns:
            Optional[str]: プレビュー文字列（該当しない場合はNone）
        """
        # ファイル作成・書き込み操作の場合、内容のプレビューを生成
        if operation_type in [OperationType.CREATE_FILE, OperationType.WRITE_FILE]:
            content = params.get('content', '')
            if content:
                # 最初の200文字をプレビューとして返す
                if len(content) <= 200:
                    return content
                else:
                    return content[:200] + "\n... (続きがあります)"
        
        # コマンド実行の場合、実行するコマンドを表示
        elif operation_type in [OperationType.EXECUTE_COMMAND, OperationType.EXECUTE_PYTHON]:
            command = params.get('command', params.get('target', ''))
            if command:
                return f"実行コマンド: {command}"
        
        return None
    
    def get_risk_explanation(self, risk_level: RiskLevel) -> str:
        """リスクレベルの説明を取得
        
        Args:
            risk_level: リスクレベル
            
        Returns:
            str: リスクレベルの説明
        """
        explanations = {
            RiskLevel.LOW_RISK: "この操作は安全です。システムに変更を加えません。",
            RiskLevel.HIGH_RISK: "この操作はファイルやシステムに変更を加える可能性があります。",
            RiskLevel.CRITICAL_RISK: "この操作はシステムに重大な影響を与える可能性があります。十分注意してください。"
        }
        
        return explanations.get(risk_level, "リスクレベルが不明です。")
    
    def add_custom_risk_mapping(self, operation_type: str, risk_level: RiskLevel) -> None:
        """カスタムリスクマッピングを追加
        
        Args:
            operation_type: 操作タイプ
            risk_level: リスクレベル
        """
        self.risk_mapping[operation_type] = risk_level


@dataclass
class ApprovalConfig:
    """承認システムの設定"""
    
    mode: ApprovalMode = ApprovalMode.STANDARD
    auto_approve_read: bool = True
    require_confirmation_for_overwrite: bool = True
    show_content_preview: bool = True
    max_preview_length: int = 200
    timeout_seconds: int = 30
    
    def __post_init__(self):
        """設定値の検証"""
        if not isinstance(self.mode, ApprovalMode):
            raise ValueError("mode は ApprovalMode enum である必要があります")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds は正の値である必要があります")
        if self.max_preview_length <= 0:
            raise ValueError("max_preview_length は正の値である必要があります")


class ApprovalGate:
    """承認ゲート - すべての危険操作はここを通る
    
    設計思想:
    - すべての危険操作の単一通過点
    - AIによるバイパスを完全に防止
    - フェイルセーフ設計（エラー時は操作拒否）
    - 相棒らしい自然な対話を維持
    """
    
    def __init__(self, config: Optional[ApprovalConfig] = None):
        """初期化
        
        Args:
            config: 承認設定（Noneの場合はデフォルト設定）
        """
        self.config = config or ApprovalConfig()
        self.analyzer = OperationAnalyzer()
        self.approval_logs: List[ApprovalLog] = []
        
        # バイパス試行検出用のフラグ
        self._bypass_attempts = 0
        self._max_bypass_attempts = 3
        
        # セキュリティログ
        self.security_logs: List[Dict[str, Any]] = []
        self._security_monitoring_enabled = True
        
        # 承認UI（後で設定される）
        self.approval_ui = None
    
    def set_approval_ui(self, approval_ui) -> None:
        """承認UIを設定
        
        Args:
            approval_ui: UserApprovalUIインスタンス
        """
        self.approval_ui = approval_ui
    
    def request_approval(self, operation_type: str, params: Dict[str, Any], session_id: str) -> ApprovalResponse:
        """承認を要求し、結果を返す
        
        Args:
            operation_type: 操作タイプ
            params: 操作パラメータ
            session_id: セッションID
            
        Returns:
            ApprovalResponse: 承認結果
            
        Raises:
            ApprovalBypassAttemptError: バイパス試行を検出した場合
            ApprovalUIError: UI関連のエラー
            ApprovalTimeoutError: タイムアウトした場合
        """
        try:
            # 操作を分析（エラー時は優雅な劣化）
            try:
                operation_info = self.analyzer.analyze_operation(operation_type, params)
            except Exception as analyzer_error:
                # アナライザーエラー時のフォールバック操作情報を作成
                fallback_operation = OperationInfo(
                    operation_type=operation_type,
                    target=str(params.get('file_path', params.get('target', 'unknown'))),
                    description=f"操作分析失敗: {operation_type}",
                    risk_level=RiskLevel.CRITICAL_RISK,  # 安全のため最高リスクに設定
                    details=params
                )
                return self._create_fail_safe_response(analyzer_error, fallback_operation)
            
            # セキュリティチェック（バイパス試行検出）
            try:
                self._detect_bypass_attempt(operation_info)
            except (ApprovalBypassAttemptError, SecurityViolationError) as e:
                # セキュリティ違反の場合は即座に拒否
                return self._create_fail_safe_response(e, operation_info)
            
            # 承認が必要かチェック（設定エラー時は優雅な劣化）
            try:
                approval_required = self.is_approval_required(operation_info)
            except Exception as config_error:
                # 設定エラー時は安全のため承認必要として処理
                self._log_security_event(
                    "config_error",
                    f"Configuration error during approval check: {str(config_error)}",
                    operation_info,
                    {"error": str(config_error)}
                )
                approval_required = True  # 安全のため承認必要とする
            
            if not approval_required:
                # 承認不要の場合は自動承認
                response = ApprovalResponse(approved=True, reason="低リスク操作のため自動承認")
                self._log_approval(operation_info, response, 0.0, session_id)
                return response
            
            # 承認UIが設定されていない場合はフェイルセーフ
            if self.approval_ui is None:
                ui_error = ApprovalUIError("承認UIが設定されていません")
                return self._create_fail_safe_response(ui_error, operation_info)
            
            # 承認要求を作成
            approval_request = ApprovalRequest(
                operation_info=operation_info,
                message=self._generate_approval_message(operation_info),
                timestamp=datetime.now(),
                session_id=session_id
            )
            
            # ユーザーに承認を要求
            start_time = datetime.now()
            response = self.approval_ui.show_approval_request(approval_request)
            end_time = datetime.now()
            
            response_time = (end_time - start_time).total_seconds()
            
            # 承認ログを記録
            self._log_approval(operation_info, response, response_time, session_id)
            
            # 拒否された場合の処理
            if not response.approved:
                rejection_message = self.handle_rejection(operation_info, response.reason or "")
                response.reason = rejection_message
                response.alternative_suggested = True
            
            return response
            
        except (ApprovalBypassAttemptError, SecurityViolationError) as e:
            # セキュリティ違反は即座に拒否応答を返す
            return self._create_fail_safe_response(e, operation_info)
            
        except ApprovalTimeoutError as e:
            # タイムアウトエラーの専用処理
            return self._handle_timeout_error(
                e.timeout_seconds or self.config.timeout_seconds, 
                operation_info
            )
            
        except ApprovalUIError as e:
            # UIエラーの専用処理
            ui_response = self._handle_ui_error(e, operation_info)
            
            # 回復を試行
            recovery_response = self._recover_from_error(e, operation_info)
            if recovery_response:
                return recovery_response
            
            return ui_response
            
        except ApprovalSystemFailureError as e:
            # システム障害の専用処理
            return self._handle_system_failure(e, operation_info, e.component or "unknown")
            
        except ApprovalConfigurationError as e:
            # 設定エラーの専用処理
            config_response = self._handle_system_failure(e, operation_info, "configuration")
            
            # 設定の回復を試行
            recovery_response = self._recover_from_error(e, operation_info)
            if recovery_response:
                return recovery_response
            
            return config_response
            
        except Exception as e:
            # 予期しないエラーの処理
            # まず回復を試行
            recovery_response = self._recover_from_error(e, operation_info)
            if recovery_response:
                return recovery_response
            
            # 回復に失敗した場合は優雅な劣化
            return self._graceful_degradation(e, operation_info, "safe")
    
    def is_approval_required(self, operation_info: OperationInfo) -> bool:
        """承認が必要かどうかを判定
        
        Args:
            operation_info: 操作情報
            
        Returns:
            bool: 承認が必要な場合True
        """
        # 除外パスのチェック
        if hasattr(operation_info, 'target') and operation_info.target:
            if self.config.is_path_excluded(operation_info.target):
                return False
        
        # 設定に基づく承認要求判定
        return self.config.is_approval_required(operation_info.risk_level)
    
    def handle_rejection(self, operation_info: OperationInfo, reason: str) -> str:
        """拒否時の対応（代替案提案等）
        
        Args:
            operation_info: 操作情報
            reason: 拒否理由
            
        Returns:
            str: 相棒らしい拒否対応メッセージ
        """
        base_message = f"分かりました。{operation_info.description}は実行しません。"
        
        # 操作タイプに応じた代替案提案
        alternatives = []
        
        if operation_info.operation_type == OperationType.CREATE_FILE:
            alternatives.append("代わりに、ファイルの内容だけを表示することもできます")
            alternatives.append("または、別の安全な場所にファイルを作成することも可能です")
        
        elif operation_info.operation_type == OperationType.WRITE_FILE:
            alternatives.append("代わりに、変更内容をプレビューとして表示できます")
            alternatives.append("または、バックアップを作成してから変更することも可能です")
        
        elif operation_info.operation_type in [OperationType.EXECUTE_PYTHON, OperationType.EXECUTE_COMMAND]:
            alternatives.append("代わりに、実行予定のコードを確認することができます")
            alternatives.append("または、より安全な方法で同じ結果を得る方法を提案できます")
        
        elif operation_info.operation_type == OperationType.DELETE_FILE:
            alternatives.append("代わりに、ファイルの内容を確認することができます")
            alternatives.append("または、ファイルを別の場所に移動することも可能です")
        
        if alternatives:
            alternative_text = "、".join(alternatives[:2])  # 最大2つの代替案
            base_message += f"\n\n{alternative_text}。どうしますか？"
        else:
            base_message += "\n\n他に何かお手伝いできることはありますか？"
        
        return base_message
    
    def _generate_approval_message(self, operation_info: OperationInfo) -> str:
        """承認要求メッセージを生成
        
        Args:
            operation_info: 操作情報
            
        Returns:
            str: 承認要求メッセージ
        """
        risk_explanation = self.analyzer.get_risk_explanation(operation_info.risk_level)
        
        message = f"🤔 {operation_info.description}を実行したいのですが、よろしいでしょうか？\n\n"
        message += f"📋 詳細: {operation_info.target}\n"
        message += f"⚠️ リスクレベル: {operation_info.risk_level.value}\n"
        message += f"💡 説明: {risk_explanation}\n"
        
        # プレビューがある場合は表示
        if operation_info.preview and self.config.show_preview:
            preview = operation_info.preview
            if len(preview) > self.config.max_preview_length:
                preview = preview[:self.config.max_preview_length] + "..."
            message += f"\n📄 プレビュー:\n{preview}\n"
        
        message += "\n実行してもよろしいですか？"
        
        return message
    

    
    def _log_approval(self, operation_info: OperationInfo, response: ApprovalResponse, 
                     response_time: float, session_id: str) -> None:
        """承認ログを記録
        
        Args:
            operation_info: 操作情報
            response: 承認応答
            response_time: 応答時間
            session_id: セッションID
        """
        log_entry = ApprovalLog(
            timestamp=datetime.now(),
            operation_info=operation_info,
            approved=response.approved,
            user_response_time=response_time,
            session_id=session_id
        )
        
        self.approval_logs.append(log_entry)
        
        # ログが多くなりすぎないよう制限（最新100件のみ保持）
        if len(self.approval_logs) > 100:
            self.approval_logs = self.approval_logs[-100:]
    
    def get_approval_statistics(self) -> Dict[str, Any]:
        """承認統計を取得
        
        Returns:
            Dict[str, Any]: 承認統計情報
        """
        if not self.approval_logs:
            return {
                "total_requests": 0,
                "approved_count": 0,
                "rejected_count": 0,
                "approval_rate": 0.0,
                "average_response_time": 0.0
            }
        
        total_requests = len(self.approval_logs)
        approved_count = sum(1 for log in self.approval_logs if log.approved)
        rejected_count = total_requests - approved_count
        approval_rate = approved_count / total_requests * 100
        average_response_time = sum(log.user_response_time for log in self.approval_logs) / total_requests
        
        return {
            "total_requests": total_requests,
            "approved_count": approved_count,
            "rejected_count": rejected_count,
            "approval_rate": approval_rate,
            "average_response_time": average_response_time
        }
    
    def clear_logs(self) -> None:
        """承認ログをクリア"""
        self.approval_logs.clear()
        self._bypass_attempts = 0
    
    def update_config(self, new_config: ApprovalConfig) -> None:
        """設定を更新
        
        Args:
            new_config: 新しい設定
        """
        if not isinstance(new_config, ApprovalConfig):
            raise ValueError("new_config は ApprovalConfig である必要があります")
        
        self.config = new_config
        self._max_bypass_attempts = new_config.max_bypass_attempts
    
    def get_config(self) -> ApprovalConfig:
        """現在の設定を取得
        
        Returns:
            ApprovalConfig: 現在の設定
        """
        return self.config
    
    def update_approval_mode(self, new_mode: ApprovalMode) -> None:
        """承認モードを更新
        
        Args:
            new_mode: 新しい承認モード
        """
        self.config.update_mode(new_mode)
    
    def add_excluded_path(self, path: str) -> None:
        """除外パスを追加
        
        Args:
            path: 除外するパス
        """
        self.config.add_excluded_path(path)
    
    def remove_excluded_path(self, path: str) -> None:
        """除外パスを削除
        
        Args:
            path: 削除するパス
        """
        self.config.remove_excluded_path(path)
    
    def add_excluded_extension(self, extension: str) -> None:
        """除外拡張子を追加
        
        Args:
            extension: 除外する拡張子
        """
        self.config.add_excluded_extension(extension)
    
    def remove_excluded_extension(self, extension: str) -> None:
        """除外拡張子を削除
        
        Args:
            extension: 削除する拡張子
        """
        self.config.remove_excluded_extension(extension)
    
    def save_config(self, file_path: Optional[str] = None) -> None:
        """設定をファイルに保存
        
        Args:
            file_path: 保存先ファイルパス（Noneの場合はデフォルトパス）
        """
        self.config.save_to_file(file_path)
    
    def load_config(self, file_path: Optional[str] = None) -> None:
        """設定をファイルから読み込み
        
        Args:
            file_path: 読み込み元ファイルパス（Noneの場合はデフォルトパス）
        """
        self.config = ApprovalConfig.load_from_file(file_path)
        self._max_bypass_attempts = self.config.max_bypass_attempts
    
    def get_config_summary(self) -> Dict[str, Any]:
        """設定の概要を取得
        
        Returns:
            Dict[str, Any]: 設定概要
        """
        return {
            "mode": self.config.mode.value,
            "mode_description": self.config.get_mode_description(),
            "timeout_seconds": self.config.timeout_seconds,
            "excluded_paths_count": len(self.config.excluded_paths),
            "excluded_extensions_count": len(self.config.excluded_extensions),
            "show_preview": self.config.show_preview,
            "show_impact_analysis": self.config.show_impact_analysis,
            "use_countdown": self.config.use_countdown,
            "max_bypass_attempts": self.config.max_bypass_attempts,
            "require_confirmation_for_critical": self.config.require_confirmation_for_critical
        }
    
    def _log_security_event(self, event_type: str, message: str, 
                           operation_info: Optional[OperationInfo] = None,
                           details: Optional[Dict[str, Any]] = None) -> None:
        """セキュリティイベントをログに記録
        
        Args:
            event_type: イベントタイプ
            message: ログメッセージ
            operation_info: 操作情報
            details: 追加詳細情報
        """
        if not self._security_monitoring_enabled:
            return
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "message": message,
            "operation_info": operation_info.to_dict() if operation_info else None,
            "details": details or {},
            "bypass_attempts": self._bypass_attempts
        }
        
        self.security_logs.append(log_entry)
        
        # ログが多くなりすぎないよう制限（最新500件のみ保持）
        if len(self.security_logs) > 500:
            self.security_logs = self.security_logs[-500:]
        
        # 重要なセキュリティイベントは即座に警告
        if event_type in ["bypass_attempt", "security_violation", "critical_error"]:
            print(f"🚨 SECURITY ALERT: {message}")
    
    def _detect_bypass_attempt(self, operation_info: OperationInfo, 
                              call_stack: Optional[List[str]] = None) -> bool:
        """承認システムバイパス試行を検出
        
        Args:
            operation_info: 操作情報
            call_stack: 呼び出しスタック
            
        Returns:
            bool: バイパス試行が検出された場合True
            
        Raises:
            ApprovalBypassAttemptError: バイパス試行が検出された場合
        """
        import inspect
        
        # 呼び出しスタックを取得
        if call_stack is None:
            call_stack = [frame.function for frame in inspect.stack()]
        
        # 疑わしいパターンを検出
        suspicious_patterns = [
            # 直接的なファイル操作関数の呼び出し
            "open", "write", "create", "delete", "remove", "unlink",
            # システム関数の直接呼び出し
            "system", "exec", "eval", "subprocess",
            # 承認システムを迂回する可能性のある関数
            "__setattr__", "__delattr__", "setattr", "delattr"
        ]
        
        bypass_indicators = []
        
        # 呼び出しスタックの分析
        for frame_func in call_stack:
            if any(pattern in frame_func.lower() for pattern in suspicious_patterns):
                bypass_indicators.append(f"Suspicious function call: {frame_func}")
        
        # 操作情報の分析
        if operation_info.risk_level == RiskLevel.CRITICAL_RISK:
            # 重要リスク操作の場合、より厳格にチェック
            if not self._has_proper_approval_flow(call_stack):
                bypass_indicators.append("Critical operation without proper approval flow")
        
        # 連続的な操作の検出
        if self._detect_rapid_operations(operation_info):
            bypass_indicators.append("Rapid consecutive operations detected")
        
        # バイパス試行が検出された場合
        if bypass_indicators:
            self._bypass_attempts += 1
            
            details = {
                "indicators": bypass_indicators,
                "call_stack": call_stack,
                "operation": operation_info.to_dict(),
                "attempt_number": self._bypass_attempts
            }
            
            self._log_security_event(
                "bypass_attempt",
                f"Approval bypass attempt detected: {', '.join(bypass_indicators)}",
                operation_info,
                details
            )
            
            # 最大試行回数を超えた場合
            if self._bypass_attempts >= self._max_bypass_attempts:
                self._log_security_event(
                    "security_violation",
                    f"Maximum bypass attempts ({self._max_bypass_attempts}) exceeded",
                    operation_info,
                    details
                )
                
                raise SecurityViolationError(
                    f"Maximum approval bypass attempts exceeded ({self._max_bypass_attempts})",
                    "max_bypass_attempts_exceeded",
                    details
                )
            
            raise ApprovalBypassAttemptError(
                f"Approval system bypass attempt detected: {', '.join(bypass_indicators)}",
                operation_info,
                details
            )
        
        return False
    
    def _has_proper_approval_flow(self, call_stack: List[str]) -> bool:
        """適切な承認フローを経ているかチェック
        
        Args:
            call_stack: 呼び出しスタック
            
        Returns:
            bool: 適切な承認フローを経ている場合True
        """
        # 承認システム関連の関数が呼び出しスタックに含まれているかチェック
        approval_functions = [
            "request_approval", "show_approval_request", "_request_approval",
            "is_approval_required", "handle_approval"
        ]
        
        return any(func in call_stack for func in approval_functions)
    
    def _detect_rapid_operations(self, operation_info: OperationInfo) -> bool:
        """連続的な操作を検出
        
        Args:
            operation_info: 操作情報
            
        Returns:
            bool: 連続的な操作が検出された場合True
        """
        current_time = datetime.now()
        
        # 過去10秒以内の操作をチェック
        recent_operations = [
            log for log in self.approval_logs
            if (current_time - log.timestamp).total_seconds() < 10
        ]
        
        # 同じタイプの操作が5回以上連続している場合は疑わしい
        same_type_operations = [
            log for log in recent_operations
            if log.operation_info.operation_type == operation_info.operation_type
        ]
        
        return len(same_type_operations) >= 5
    
    def _create_fail_safe_response(self, error: Exception, 
                                  operation_info: OperationInfo) -> ApprovalResponse:
        """フェイルセーフ応答を作成
        
        Args:
            error: 発生したエラー
            operation_info: 操作情報
            
        Returns:
            ApprovalResponse: 安全のため拒否する応答
        """
        error_details = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "operation": operation_info.to_dict(),
            "fail_safe_triggered": True
        }
        
        self._log_security_event(
            "fail_safe_triggered",
            f"Fail-safe mechanism triggered due to {type(error).__name__}: {str(error)}",
            operation_info,
            error_details
        )
        
        return ApprovalResponse(
            approved=False,
            reason=f"安全のため操作を拒否しました。エラー: {str(error)}",
            timestamp=datetime.now(),
            details=error_details,
            alternative_suggested=False
        )
    
    def get_security_logs(self, event_type: Optional[str] = None, 
                         limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """セキュリティログを取得
        
        Args:
            event_type: フィルタするイベントタイプ
            limit: 取得する最大件数
            
        Returns:
            List[Dict[str, Any]]: セキュリティログのリスト
        """
        logs = self.security_logs
        
        if event_type:
            logs = [log for log in logs if log["event_type"] == event_type]
        
        if limit:
            logs = logs[-limit:]
        
        return logs
    
    def get_security_summary(self) -> Dict[str, Any]:
        """セキュリティサマリーを取得
        
        Returns:
            Dict[str, Any]: セキュリティ統計情報
        """
        total_events = len(self.security_logs)
        
        event_counts = {}
        for log in self.security_logs:
            event_type = log["event_type"]
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
        
        recent_events = [
            log for log in self.security_logs
            if (datetime.now() - datetime.fromisoformat(log["timestamp"])).total_seconds() < 3600
        ]
        
        return {
            "total_security_events": total_events,
            "bypass_attempts": self._bypass_attempts,
            "max_bypass_attempts": self._max_bypass_attempts,
            "event_type_counts": event_counts,
            "recent_events_count": len(recent_events),
            "monitoring_enabled": self._security_monitoring_enabled,
            "last_event_time": self.security_logs[-1]["timestamp"] if self.security_logs else None
        }
    
    def reset_security_state(self) -> None:
        """セキュリティ状態をリセット（テスト用）"""
        self._bypass_attempts = 0
        self.security_logs.clear()
        
        self._log_security_event(
            "security_reset",
            "Security state has been reset",
            None,
            {"reset_by": "system"}
        )
    
    def enable_security_monitoring(self, enabled: bool = True) -> None:
        """セキュリティ監視の有効/無効を切り替え
        
        Args:
            enabled: 有効にする場合True
        """
        self._security_monitoring_enabled = enabled
        
        self._log_security_event(
            "monitoring_toggle",
            f"Security monitoring {'enabled' if enabled else 'disabled'}",
            None,
            {"monitoring_enabled": enabled}
        )


class ApprovalMode(Enum):
    """承認モード"""
    STRICT = "strict"        # すべてのファイル操作で承認が必要
    STANDARD = "standard"    # 高リスク操作のみ承認が必要（デフォルト）
    TRUSTED = "trusted"      # 重要リスク操作のみ承認が必要


@dataclass
class ApprovalConfig:
    """承認システムの設定
    
    承認モード、タイムアウト、除外パターンなどを管理
    """
    
    # 基本設定
    mode: ApprovalMode = ApprovalMode.STANDARD
    timeout_seconds: int = 30
    
    # 除外設定
    excluded_paths: List[str] = field(default_factory=list)
    excluded_extensions: List[str] = field(default_factory=list)
    
    # UI設定
    show_preview: bool = True
    show_impact_analysis: bool = True
    use_countdown: bool = True
    max_preview_length: int = 200
    
    # セキュリティ設定
    max_bypass_attempts: int = 3
    require_confirmation_for_critical: bool = True
    
    # 設定ファイルのパス
    config_file_path: Optional[str] = None
    
    def __post_init__(self):
        """初期化後の処理"""
        if self.config_file_path is None:
            # デフォルトの設定ファイルパス
            self.config_file_path = os.path.join(
                os.path.expanduser("~"), 
                ".duckflow", 
                "approval_config.json"
            )
    
    def is_approval_required(self, risk_level: RiskLevel) -> bool:
        """指定されたリスクレベルで承認が必要かを判定
        
        Args:
            risk_level: 操作のリスクレベル
            
        Returns:
            bool: 承認が必要な場合True
        """
        if self.mode == ApprovalMode.STRICT:
            # STRICTモード: 低リスク以外はすべて承認が必要
            return risk_level != RiskLevel.LOW_RISK
        
        elif self.mode == ApprovalMode.STANDARD:
            # STANDARDモード: 高リスク以上で承認が必要
            return risk_level in [RiskLevel.HIGH_RISK, RiskLevel.CRITICAL_RISK]
        
        elif self.mode == ApprovalMode.TRUSTED:
            # TRUSTEDモード: 重要リスクのみ承認が必要
            return risk_level == RiskLevel.CRITICAL_RISK
        
        else:
            # 不明なモードの場合は安全のため承認を要求
            return True
    
    def is_path_excluded(self, file_path: str) -> bool:
        """指定されたパスが除外対象かを判定
        
        Args:
            file_path: チェックするファイルパス
            
        Returns:
            bool: 除外対象の場合True
        """
        file_path = os.path.normpath(file_path)
        
        # 除外パスのチェック
        for excluded_path in self.excluded_paths:
            excluded_path = os.path.normpath(excluded_path)
            if file_path.startswith(excluded_path):
                return True
        
        # 除外拡張子のチェック
        file_extension = os.path.splitext(file_path)[1].lower()
        if file_extension in self.excluded_extensions:
            return True
        
        return False
    
    def get_timeout_for_risk_level(self, risk_level: RiskLevel) -> int:
        """リスクレベルに応じたタイムアウト時間を取得
        
        Args:
            risk_level: 操作のリスクレベル
            
        Returns:
            int: タイムアウト時間（秒）
        """
        if risk_level == RiskLevel.CRITICAL_RISK:
            # 重要リスクは長めのタイムアウト
            return self.timeout_seconds * 2
        else:
            return self.timeout_seconds
    
    def save_to_file(self, file_path: Optional[str] = None) -> None:
        """設定をファイルに保存
        
        Args:
            file_path: 保存先ファイルパス（Noneの場合はデフォルトパス）
            
        Raises:
            OSError: ファイル保存に失敗した場合
        """
        if file_path is None:
            file_path = self.config_file_path
        
        # ディレクトリが存在しない場合は作成
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # 設定をJSONに変換
        config_dict = {
            "mode": self.mode.value,
            "timeout_seconds": self.timeout_seconds,
            "excluded_paths": self.excluded_paths,
            "excluded_extensions": self.excluded_extensions,
            "show_preview": self.show_preview,
            "show_impact_analysis": self.show_impact_analysis,
            "use_countdown": self.use_countdown,
            "max_bypass_attempts": self.max_bypass_attempts,
            "require_confirmation_for_critical": self.require_confirmation_for_critical
        }
        
        # ファイルに保存
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load_from_file(cls, file_path: Optional[str] = None) -> 'ApprovalConfig':
        """ファイルから設定を読み込み
        
        Args:
            file_path: 読み込み元ファイルパス（Noneの場合はデフォルトパス）
            
        Returns:
            ApprovalConfig: 読み込まれた設定
            
        Raises:
            OSError: ファイル読み込みに失敗した場合
            ValueError: 設定ファイルの形式が不正な場合
        """
        if file_path is None:
            # デフォルトパスを生成
            file_path = os.path.join(
                os.path.expanduser("~"), 
                ".duckflow", 
                "approval_config.json"
            )
        
        if not os.path.exists(file_path):
            # ファイルが存在しない場合はデフォルト設定を返す
            config = cls()
            config.config_file_path = file_path
            return config
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                config_dict = json.load(f)
            
            # ApprovalModeを変換
            mode = ApprovalMode(config_dict.get("mode", ApprovalMode.STANDARD.value))
            
            # ApprovalConfigを作成
            config = cls(
                mode=mode,
                timeout_seconds=config_dict.get("timeout_seconds", 30),
                excluded_paths=config_dict.get("excluded_paths", []),
                excluded_extensions=config_dict.get("excluded_extensions", []),
                show_preview=config_dict.get("show_preview", True),
                show_impact_analysis=config_dict.get("show_impact_analysis", True),
                use_countdown=config_dict.get("use_countdown", True),
                max_bypass_attempts=config_dict.get("max_bypass_attempts", 3),
                require_confirmation_for_critical=config_dict.get("require_confirmation_for_critical", True),
                config_file_path=file_path
            )
            
            return config
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            raise ValueError(f"設定ファイルの形式が不正です: {e}")
    
    def update_mode(self, new_mode: ApprovalMode) -> None:
        """承認モードを更新
        
        Args:
            new_mode: 新しい承認モード
        """
        self.mode = new_mode
    
    def add_excluded_path(self, path: str) -> None:
        """除外パスを追加
        
        Args:
            path: 除外するパス
        """
        normalized_path = os.path.normpath(path)
        if normalized_path not in self.excluded_paths:
            self.excluded_paths.append(normalized_path)
    
    def remove_excluded_path(self, path: str) -> None:
        """除外パスを削除
        
        Args:
            path: 削除するパス
        """
        normalized_path = os.path.normpath(path)
        if normalized_path in self.excluded_paths:
            self.excluded_paths.remove(normalized_path)
    
    def add_excluded_extension(self, extension: str) -> None:
        """除外拡張子を追加
        
        Args:
            extension: 除外する拡張子（例: '.tmp'）
        """
        if not extension.startswith('.'):
            extension = '.' + extension
        extension = extension.lower()
        if extension not in self.excluded_extensions:
            self.excluded_extensions.append(extension)
    
    def remove_excluded_extension(self, extension: str) -> None:
        """除外拡張子を削除
        
        Args:
            extension: 削除する拡張子
        """
        if not extension.startswith('.'):
            extension = '.' + extension
        extension = extension.lower()
        if extension in self.excluded_extensions:
            self.excluded_extensions.remove(extension)
    
    def get_mode_description(self) -> str:
        """現在のモードの説明を取得
        
        Returns:
            str: モードの説明
        """
        descriptions = {
            ApprovalMode.STRICT: "厳格モード - すべてのファイル操作で承認が必要",
            ApprovalMode.STANDARD: "標準モード - 高リスク操作で承認が必要（推奨）",
            ApprovalMode.TRUSTED: "信頼モード - 重要リスク操作のみ承認が必要"
        }
        return descriptions.get(self.mode, "不明なモード")
    
    def to_dict(self) -> Dict[str, Any]:
        """設定を辞書形式で取得
        
        Returns:
            Dict[str, Any]: 設定の辞書
        """
        return {
            "mode": self.mode.value,
            "mode_description": self.get_mode_description(),
            "timeout_seconds": self.timeout_seconds,
            "excluded_paths": self.excluded_paths,
            "excluded_extensions": self.excluded_extensions,
            "show_preview": self.show_preview,
            "show_impact_analysis": self.show_impact_analysis,
            "use_countdown": self.use_countdown,
            "max_bypass_attempts": self.max_bypass_attempts,
            "require_confirmation_for_critical": self.require_confirmation_for_critical,
            "config_file_path": self.config_file_path
        }
    
    def __str__(self) -> str:
        """設定の文字列表現
        
        Returns:
            str: 設定の概要
        """
        return f"ApprovalConfig(mode={self.mode.value}, timeout={self.timeout_seconds}s)"


    def _log_security_event(self, event_type: str, message: str, 
                           operation_info: Optional[OperationInfo] = None,
                           details: Optional[Dict[str, Any]] = None) -> None:
        """セキュリティイベントをログに記録
        
        Args:
            event_type: イベントタイプ
            message: ログメッセージ
            operation_info: 操作情報
            details: 追加詳細情報
        """
        if not self._security_monitoring_enabled:
            return
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "message": message,
            "operation_info": operation_info.to_dict() if operation_info else None,
            "details": details or {},
            "bypass_attempts": self._bypass_attempts
        }
        
        self.security_logs.append(log_entry)
        
        # ログが多くなりすぎないよう制限（最新500件のみ保持）
        if len(self.security_logs) > 500:
            self.security_logs = self.security_logs[-500:]
        
        # 重要なセキュリティイベントは即座に警告
        if event_type in ["bypass_attempt", "security_violation", "critical_error"]:
            print(f"🚨 SECURITY ALERT: {message}")
    
    def _detect_bypass_attempt(self, operation_info: OperationInfo, 
                              call_stack: Optional[List[str]] = None) -> bool:
        """承認システムバイパス試行を検出
        
        Args:
            operation_info: 操作情報
            call_stack: 呼び出しスタック
            
        Returns:
            bool: バイパス試行が検出された場合True
            
        Raises:
            ApprovalBypassAttemptError: バイパス試行が検出された場合
        """
        import inspect
        
        # 呼び出しスタックを取得
        if call_stack is None:
            call_stack = [frame.function for frame in inspect.stack()]
        
        # 疑わしいパターンを検出
        suspicious_patterns = [
            # 直接的なファイル操作関数の呼び出し
            "open", "write", "create", "delete", "remove", "unlink",
            # システム関数の直接呼び出し
            "system", "exec", "eval", "subprocess",
            # 承認システムを迂回する可能性のある関数
            "__setattr__", "__delattr__", "setattr", "delattr"
        ]
        
        bypass_indicators = []
        
        # 呼び出しスタックの分析
        for frame_func in call_stack:
            if any(pattern in frame_func.lower() for pattern in suspicious_patterns):
                bypass_indicators.append(f"Suspicious function call: {frame_func}")
        
        # 操作情報の分析
        if operation_info.risk_level == RiskLevel.CRITICAL_RISK:
            # 重要リスク操作の場合、より厳格にチェック
            if not self._has_proper_approval_flow(call_stack):
                bypass_indicators.append("Critical operation without proper approval flow")
        
        # 連続的な操作の検出
        if self._detect_rapid_operations(operation_info):
            bypass_indicators.append("Rapid consecutive operations detected")
        
        # バイパス試行が検出された場合
        if bypass_indicators:
            self._bypass_attempts += 1
            
            details = {
                "indicators": bypass_indicators,
                "call_stack": call_stack,
                "operation": operation_info.to_dict(),
                "attempt_number": self._bypass_attempts
            }
            
            self._log_security_event(
                "bypass_attempt",
                f"Approval bypass attempt detected: {', '.join(bypass_indicators)}",
                operation_info,
                details
            )
            
            # 最大試行回数を超えた場合
            if self._bypass_attempts >= self._max_bypass_attempts:
                self._log_security_event(
                    "security_violation",
                    f"Maximum bypass attempts ({self._max_bypass_attempts}) exceeded",
                    operation_info,
                    details
                )
                
                raise SecurityViolationError(
                    f"Maximum approval bypass attempts exceeded ({self._max_bypass_attempts})",
                    "max_bypass_attempts_exceeded",
                    details
                )
            
            raise ApprovalBypassAttemptError(
                f"Approval system bypass attempt detected: {', '.join(bypass_indicators)}",
                operation_info,
                details
            )
        
        return False
    
    def _has_proper_approval_flow(self, call_stack: List[str]) -> bool:
        """適切な承認フローを経ているかチェック
        
        Args:
            call_stack: 呼び出しスタック
            
        Returns:
            bool: 適切な承認フローを経ている場合True
        """
        # 承認システム関連の関数が呼び出しスタックに含まれているかチェック
        approval_functions = [
            "request_approval", "show_approval_request", "_request_approval",
            "is_approval_required", "handle_approval"
        ]
        
        return any(func in call_stack for func in approval_functions)
    
    def _detect_rapid_operations(self, operation_info: OperationInfo) -> bool:
        """連続的な操作を検出
        
        Args:
            operation_info: 操作情報
            
        Returns:
            bool: 連続的な操作が検出された場合True
        """
        current_time = datetime.now()
        
        # 過去10秒以内の操作をチェック
        recent_operations = [
            log for log in self.approval_logs
            if (current_time - log.timestamp).total_seconds() < 10
        ]
        
        # 同じタイプの操作が5回以上連続している場合は疑わしい
        same_type_operations = [
            log for log in recent_operations
            if log.operation_info.operation_type == operation_info.operation_type
        ]
        
        return len(same_type_operations) >= 5
    
    def _create_fail_safe_response(self, error: Exception, 
                                  operation_info: OperationInfo) -> ApprovalResponse:
        """フェイルセーフ応答を作成
        
        Args:
            error: 発生したエラー
            operation_info: 操作情報
            
        Returns:
            ApprovalResponse: 安全のため拒否する応答
        """
        error_details = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "operation": operation_info.to_dict(),
            "fail_safe_triggered": True
        }
        
        self._log_security_event(
            "fail_safe_triggered",
            f"Fail-safe mechanism triggered due to {type(error).__name__}: {str(error)}",
            operation_info,
            error_details
        )
        
        return ApprovalResponse(
            approved=False,
            reason=f"安全のため操作を拒否しました。エラー: {str(error)}",
            timestamp=datetime.now(),
            details=error_details,
            alternative_suggested=False
        )
    
    def get_security_logs(self, event_type: Optional[str] = None, 
                         limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """セキュリティログを取得
        
        Args:
            event_type: フィルタするイベントタイプ
            limit: 取得する最大件数
            
        Returns:
            List[Dict[str, Any]]: セキュリティログのリスト
        """
        logs = self.security_logs
        
        if event_type:
            logs = [log for log in logs if log["event_type"] == event_type]
        
        if limit:
            logs = logs[-limit:]
        
        return logs
    
    def get_security_summary(self) -> Dict[str, Any]:
        """セキュリティサマリーを取得
        
        Returns:
            Dict[str, Any]: セキュリティ統計情報
        """
        total_events = len(self.security_logs)
        
        event_counts = {}
        for log in self.security_logs:
            event_type = log["event_type"]
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
        
        recent_events = [
            log for log in self.security_logs
            if (datetime.now() - datetime.fromisoformat(log["timestamp"])).total_seconds() < 3600
        ]
        
        return {
            "total_security_events": total_events,
            "bypass_attempts": self._bypass_attempts,
            "max_bypass_attempts": self._max_bypass_attempts,
            "event_type_counts": event_counts,
            "recent_events_count": len(recent_events),
            "monitoring_enabled": self._security_monitoring_enabled,
            "last_event_time": self.security_logs[-1]["timestamp"] if self.security_logs else None
        }
    
    def reset_security_state(self) -> None:
        """セキュリティ状態をリセット（テスト用）"""
        self._bypass_attempts = 0
        self.security_logs.clear()
        
        self._log_security_event(
            "security_reset",
            "Security state has been reset",
            None,
            {"reset_by": "system"}
        )
    
    def enable_security_monitoring(self, enabled: bool = True) -> None:
        """セキュリティ監視の有効/無効を切り替え
        
        Args:
            enabled: 有効にする場合True
        """
        self._security_monitoring_enabled = enabled
        
        self._log_security_event(
            "monitoring_toggle",
            f"Security monitoring {'enabled' if enabled else 'disabled'}",
            None,
            {"monitoring_enabled": enabled}
        )    

    
    def _handle_timeout_error(self, timeout_seconds: int, 
                             operation_info: OperationInfo) -> ApprovalResponse:
        """タイムアウトエラーの処理
        
        Args:
            timeout_seconds: タイムアウト時間
            operation_info: 操作情報
            
        Returns:
            ApprovalResponse: タイムアウト時の安全な応答
        """
        error_details = {
            "timeout_seconds": timeout_seconds,
            "operation": operation_info.to_dict(),
            "error_type": "timeout",
            "fail_safe_triggered": True
        }
        
        self._log_security_event(
            "timeout_error",
            f"Approval request timed out after {timeout_seconds} seconds",
            operation_info,
            error_details
        )
        
        return ApprovalResponse(
            approved=False,
            reason=f"承認要求が{timeout_seconds}秒でタイムアウトしました。安全のため操作を拒否します。",
            timestamp=datetime.now(),
            details=error_details,
            alternative_suggested=True
        )
    
    def _handle_ui_error(self, ui_error: Exception, 
                        operation_info: OperationInfo) -> ApprovalResponse:
        """UIエラーの処理
        
        Args:
            ui_error: UIエラー
            operation_info: 操作情報
            
        Returns:
            ApprovalResponse: UIエラー時の安全な応答
        """
        error_details = {
            "ui_error_type": type(ui_error).__name__,
            "ui_error_message": str(ui_error),
            "operation": operation_info.to_dict(),
            "error_type": "ui_failure",
            "fail_safe_triggered": True
        }
        
        self._log_security_event(
            "ui_error",
            f"UI error occurred: {type(ui_error).__name__}: {str(ui_error)}",
            operation_info,
            error_details
        )
        
        return ApprovalResponse(
            approved=False,
            reason=f"承認UIでエラーが発生しました。安全のため操作を拒否します。エラー: {str(ui_error)}",
            timestamp=datetime.now(),
            details=error_details,
            alternative_suggested=False
        )
    
    def _handle_system_failure(self, system_error: Exception,
                              operation_info: OperationInfo,
                              component: str = "unknown") -> ApprovalResponse:
        """システム障害の処理
        
        Args:
            system_error: システムエラー
            operation_info: 操作情報
            component: 障害が発生したコンポーネント
            
        Returns:
            ApprovalResponse: システム障害時の安全な応答
        """
        error_details = {
            "system_error_type": type(system_error).__name__,
            "system_error_message": str(system_error),
            "failed_component": component,
            "operation": operation_info.to_dict(),
            "error_type": "system_failure",
            "fail_safe_triggered": True
        }
        
        self._log_security_event(
            "system_failure",
            f"System failure in {component}: {type(system_error).__name__}: {str(system_error)}",
            operation_info,
            error_details
        )
        
        return ApprovalResponse(
            approved=False,
            reason=f"承認システムで障害が発生しました（{component}）。安全のため操作を拒否します。",
            timestamp=datetime.now(),
            details=error_details,
            alternative_suggested=False
        )
    
    def _validate_system_health(self) -> bool:
        """システムの健全性をチェック
        
        Returns:
            bool: システムが正常な場合True
            
        Raises:
            ApprovalSystemFailureError: システムに問題がある場合
        """
        health_issues = []
        
        # 設定の健全性チェック
        if not self.config:
            health_issues.append("Configuration is missing")
        elif not isinstance(self.config, ApprovalConfig):
            health_issues.append("Invalid configuration type")
        
        # アナライザーの健全性チェック
        if not self.analyzer:
            health_issues.append("Operation analyzer is missing")
        
        # ログシステムの健全性チェック
        if not hasattr(self, 'approval_logs'):
            health_issues.append("Approval logging system is not initialized")
        
        if not hasattr(self, 'security_logs'):
            health_issues.append("Security logging system is not initialized")
        
        # セキュリティ監視の健全性チェック
        if not hasattr(self, '_security_monitoring_enabled'):
            health_issues.append("Security monitoring is not initialized")
        
        # バイパス検出の健全性チェック
        if not hasattr(self, '_bypass_attempts'):
            health_issues.append("Bypass detection system is not initialized")
        
        if health_issues:
            raise ApprovalSystemFailureError(
                f"System health check failed: {', '.join(health_issues)}",
                "health_check_failure",
                "approval_gate"
            )
        
        return True
    
    def _graceful_degradation(self, error: Exception, 
                             operation_info: OperationInfo,
                             degradation_level: str = "safe") -> ApprovalResponse:
        """優雅な劣化処理
        
        Args:
            error: 発生したエラー
            operation_info: 操作情報
            degradation_level: 劣化レベル ("safe", "minimal", "emergency")
            
        Returns:
            ApprovalResponse: 劣化時の応答
        """
        error_details = {
            "original_error_type": type(error).__name__,
            "original_error_message": str(error),
            "degradation_level": degradation_level,
            "operation": operation_info.to_dict(),
            "graceful_degradation": True
        }
        
        if degradation_level == "safe":
            # 安全な劣化：すべての操作を拒否
            reason = "システムエラーが発生しました。安全のため操作を拒否します。"
            approved = False
            
        elif degradation_level == "minimal":
            # 最小限の劣化：低リスク操作のみ許可
            if operation_info.risk_level == RiskLevel.LOW_RISK:
                reason = "システムエラーが発生しましたが、低リスク操作のため許可します。"
                approved = True
            else:
                reason = "システムエラーが発生しました。高リスク操作のため拒否します。"
                approved = False
                
        elif degradation_level == "emergency":
            # 緊急劣化：すべてのシステムを停止
            reason = "緊急システム障害が発生しました。すべての操作を停止します。"
            approved = False
            error_details["emergency_stop"] = True
            
        else:
            # 不明な劣化レベル：最も安全な選択
            reason = "不明なシステム状態です。安全のため操作を拒否します。"
            approved = False
        
        self._log_security_event(
            "graceful_degradation",
            f"Graceful degradation activated: {degradation_level} - {str(error)}",
            operation_info,
            error_details
        )
        
        return ApprovalResponse(
            approved=approved,
            reason=reason,
            timestamp=datetime.now(),
            details=error_details,
            alternative_suggested=not approved
        )
    
    def _recover_from_error(self, error: Exception, 
                           operation_info: OperationInfo) -> Optional[ApprovalResponse]:
        """エラーからの回復を試行
        
        Args:
            error: 発生したエラー
            operation_info: 操作情報
            
        Returns:
            Optional[ApprovalResponse]: 回復に成功した場合の応答、失敗した場合はNone
        """
        recovery_attempts = []
        
        try:
            # 設定の再読み込みを試行
            if isinstance(error, ApprovalConfigurationError):
                recovery_attempts.append("config_reload")
                self.config = ApprovalConfig.load_from_file()
                
            # UIの再初期化を試行
            elif isinstance(error, ApprovalUIError):
                recovery_attempts.append("ui_reinit")
                # UIの再初期化は外部から行う必要があるため、ここでは記録のみ
                
            # セキュリティ状態のリセットを試行
            elif isinstance(error, (ApprovalBypassAttemptError, SecurityViolationError)):
                recovery_attempts.append("security_reset")
                # セキュリティ違反の場合は回復を試行しない（安全のため）
                return None
                
            # システム健全性の再チェック
            self._validate_system_health()
            
            # 回復成功をログ
            self._log_security_event(
                "error_recovery_success",
                f"Successfully recovered from {type(error).__name__}: {', '.join(recovery_attempts)}",
                operation_info,
                {
                    "original_error": str(error),
                    "recovery_attempts": recovery_attempts,
                    "recovery_successful": True
                }
            )
            
            # 回復後の安全な応答を返す
            return ApprovalResponse(
                approved=False,  # 回復後も安全のため一度拒否
                reason=f"システムエラーから回復しました。安全のため今回の操作は拒否しますが、再度お試しください。",
                timestamp=datetime.now(),
                details={
                    "recovery_successful": True,
                    "recovery_attempts": recovery_attempts
                },
                alternative_suggested=True
            )
            
        except Exception as recovery_error:
            # 回復に失敗
            self._log_security_event(
                "error_recovery_failed",
                f"Failed to recover from {type(error).__name__}: {str(recovery_error)}",
                operation_info,
                {
                    "original_error": str(error),
                    "recovery_error": str(recovery_error),
                    "recovery_attempts": recovery_attempts,
                    "recovery_successful": False
                }
            )
            
            return None
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """エラー統計を取得
        
        Returns:
            Dict[str, Any]: エラー統計情報
        """
        error_events = [
            log for log in self.security_logs
            if log["event_type"] in [
                "timeout_error", "ui_error", "system_failure",
                "graceful_degradation", "error_recovery_success", "error_recovery_failed"
            ]
        ]
        
        error_counts = {}
        recovery_success_count = 0
        recovery_failure_count = 0
        
        for event in error_events:
            event_type = event["event_type"]
            error_counts[event_type] = error_counts.get(event_type, 0) + 1
            
            if event_type == "error_recovery_success":
                recovery_success_count += 1
            elif event_type == "error_recovery_failed":
                recovery_failure_count += 1
        
        total_recovery_attempts = recovery_success_count + recovery_failure_count
        recovery_rate = (recovery_success_count / total_recovery_attempts * 100) if total_recovery_attempts > 0 else 0
        
        return {
            "total_error_events": len(error_events),
            "error_type_counts": error_counts,
            "recovery_attempts": total_recovery_attempts,
            "recovery_success_count": recovery_success_count,
            "recovery_failure_count": recovery_failure_count,
            "recovery_success_rate": recovery_rate,
            "last_error_time": error_events[-1]["timestamp"] if error_events else None
        } 
   
    def _recover_from_error(self, error: Exception, 
                           operation_info: OperationInfo) -> Optional[ApprovalResponse]:
        """エラーからの回復を試行
        
        Args:
            error: 発生したエラー
            operation_info: 操作情報
            
        Returns:
            Optional[ApprovalResponse]: 回復できた場合の応答、できない場合はNone
        """
        # 現在は回復機能は実装せず、常にNoneを返す
        # 将来的にはエラータイプに応じた回復処理を実装可能
        return None
    
    def _handle_timeout_error(self, timeout_seconds: int, 
                             operation_info: OperationInfo) -> ApprovalResponse:
        """タイムアウトエラーの処理
        
        Args:
            timeout_seconds: タイムアウト時間
            operation_info: 操作情報
            
        Returns:
            ApprovalResponse: タイムアウト時の応答
        """
        timeout_details = {
            "timeout_seconds": timeout_seconds,
            "operation": operation_info.to_dict(),
            "fail_safe_triggered": True,
            "error_type": "ApprovalTimeoutError"
        }
        
        self._log_security_event(
            "timeout_occurred",
            f"Approval request timed out after {timeout_seconds} seconds",
            operation_info,
            timeout_details
        )
        
        return ApprovalResponse(
            approved=False,
            reason=f"承認要求が{timeout_seconds}秒でタイムアウトしました。安全のため操作を拒否します。",
            timestamp=datetime.now(),
            details=timeout_details,
            alternative_suggested=False
        )