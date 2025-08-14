"""
Test suite for ApprovalGate class
ApprovalGateクラスのテスト
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from companion.approval_system import (
    ApprovalGate, ApprovalConfig, ApprovalMode, OperationInfo, 
    ApprovalRequest, ApprovalResponse, RiskLevel, OperationType,
    ApprovalBypassAttemptError, ApprovalUIError, ApprovalTimeoutError
)


class MockApprovalUI:
    """テスト用のモック承認UI"""
    
    def __init__(self, default_response: bool = True, response_delay: float = 1.0):
        self.default_response = default_response
        self.response_delay = response_delay
        self.last_request = None
    
    def show_approval_request(self, request: ApprovalRequest) -> ApprovalResponse:
        """承認要求を表示（モック）"""
        self.last_request = request
        
        # 遅延をシミュレート
        import time
        time.sleep(self.response_delay)
        
        return ApprovalResponse(
            approved=self.default_response,
            reason="テスト応答" if not self.default_response else None
        )


class TestApprovalConfig:
    """ApprovalConfigクラスのテスト"""
    
    def test_default_config(self):
        """デフォルト設定のテスト"""
        config = ApprovalConfig()
        
        assert config.mode == ApprovalMode.STANDARD
        assert config.auto_approve_read is True
        assert config.require_confirmation_for_overwrite is True
        assert config.show_content_preview is True
        assert config.max_preview_length == 200
        assert config.timeout_seconds == 30
    
    def test_custom_config(self):
        """カスタム設定のテスト"""
        config = ApprovalConfig(
            mode=ApprovalMode.STRICT,
            auto_approve_read=False,
            timeout_seconds=60,
            max_preview_length=100
        )
        
        assert config.mode == ApprovalMode.STRICT
        assert config.auto_approve_read is False
        assert config.timeout_seconds == 60
        assert config.max_preview_length == 100
    
    def test_config_validation_invalid_mode(self):
        """無効なモードの場合のバリデーション"""
        with pytest.raises(ValueError, match="mode は ApprovalMode enum である必要があります"):
            ApprovalConfig(mode="invalid")
    
    def test_config_validation_invalid_timeout(self):
        """無効なタイムアウトの場合のバリデーション"""
        with pytest.raises(ValueError, match="timeout_seconds は正の値である必要があります"):
            ApprovalConfig(timeout_seconds=0)
    
    def test_config_validation_invalid_preview_length(self):
        """無効なプレビュー長の場合のバリデーション"""
        with pytest.raises(ValueError, match="max_preview_length は正の値である必要があります"):
            ApprovalConfig(max_preview_length=-1)


class TestApprovalGate:
    """ApprovalGateクラスのテスト"""
    
    def setup_method(self):
        """各テストメソッドの前に実行される初期化"""
        self.config = ApprovalConfig()
        self.gate = ApprovalGate(self.config)
        self.mock_ui = MockApprovalUI()
        self.gate.set_approval_ui(self.mock_ui)
    
    def test_initialization_default_config(self):
        """デフォルト設定での初期化テスト"""
        gate = ApprovalGate()
        
        assert gate.config is not None
        assert gate.config.mode == ApprovalMode.STANDARD
        assert gate.analyzer is not None
        assert gate.approval_logs == []
        assert gate._bypass_attempts == 0
        assert gate.approval_ui is None
    
    def test_initialization_custom_config(self):
        """カスタム設定での初期化テスト"""
        custom_config = ApprovalConfig(mode=ApprovalMode.STRICT)
        gate = ApprovalGate(custom_config)
        
        assert gate.config.mode == ApprovalMode.STRICT
    
    def test_set_approval_ui(self):
        """承認UI設定のテスト"""
        gate = ApprovalGate()
        mock_ui = MockApprovalUI()
        
        gate.set_approval_ui(mock_ui)
        assert gate.approval_ui == mock_ui
    
    def test_is_approval_required_standard_mode(self):
        """標準モードでの承認要否判定テスト"""
        # 高リスク操作は承認必要
        high_risk_op = OperationInfo(
            operation_type=OperationType.CREATE_FILE,
            target="test.py",
            description="テスト",
            risk_level=RiskLevel.HIGH_RISK,
            details={}
        )
        assert self.gate.is_approval_required(high_risk_op) is True
        
        # 低リスク操作は承認不要（auto_approve_read=True）
        low_risk_op = OperationInfo(
            operation_type=OperationType.READ_FILE,
            target="test.py",
            description="テスト",
            risk_level=RiskLevel.LOW_RISK,
            details={}
        )
        assert self.gate.is_approval_required(low_risk_op) is False
    
    def test_is_approval_required_strict_mode(self):
        """厳格モードでの承認要否判定テスト"""
        self.gate.config.mode = ApprovalMode.STRICT
        
        # 低リスク操作でも承認必要
        low_risk_op = OperationInfo(
            operation_type=OperationType.READ_FILE,
            target="test.py",
            description="テスト",
            risk_level=RiskLevel.LOW_RISK,
            details={}
        )
        assert self.gate.is_approval_required(low_risk_op) is True
    
    def test_is_approval_required_trusted_mode(self):
        """信頼モードでの承認要否判定テスト"""
        self.gate.config.mode = ApprovalMode.TRUSTED
        
        # 高リスク操作でも承認不要
        high_risk_op = OperationInfo(
            operation_type=OperationType.CREATE_FILE,
            target="test.py",
            description="テスト",
            risk_level=RiskLevel.HIGH_RISK,
            details={}
        )
        assert self.gate.is_approval_required(high_risk_op) is False
    
    def test_is_approval_required_auto_approve_read_disabled(self):
        """読み取り自動承認無効時のテスト"""
        self.gate.config.auto_approve_read = False
        
        # 低リスク操作でも承認必要
        low_risk_op = OperationInfo(
            operation_type=OperationType.READ_FILE,
            target="test.py",
            description="テスト",
            risk_level=RiskLevel.LOW_RISK,
            details={}
        )
        assert self.gate.is_approval_required(low_risk_op) is True
    
    def test_request_approval_auto_approved(self):
        """自動承認のテスト"""
        params = {'target': 'test.txt'}
        
        response = self.gate.request_approval(
            OperationType.READ_FILE, 
            params, 
            "test_session"
        )
        
        assert response.approved is True
        assert "自動承認" in response.reason
        assert len(self.gate.approval_logs) == 1
    
    def test_request_approval_user_approved(self):
        """ユーザー承認のテスト"""
        self.mock_ui.default_response = True
        params = {'target': 'test.py', 'content': 'print("hello")'}
        
        response = self.gate.request_approval(
            OperationType.CREATE_FILE,
            params,
            "test_session"
        )
        
        assert response.approved is True
        assert len(self.gate.approval_logs) == 1
        assert self.mock_ui.last_request is not None
    
    def test_request_approval_user_rejected(self):
        """ユーザー拒否のテスト"""
        self.mock_ui.default_response = False
        params = {'target': 'test.py', 'content': 'print("hello")'}
        
        response = self.gate.request_approval(
            OperationType.CREATE_FILE,
            params,
            "test_session"
        )
        
        assert response.approved is False
        assert response.alternative_suggested is True
        assert "代わりに" in response.reason or "他に何か" in response.reason
        assert len(self.gate.approval_logs) == 1
    
    def test_request_approval_no_ui_error(self):
        """承認UI未設定時のエラーテスト"""
        gate = ApprovalGate()  # UI未設定
        params = {'target': 'test.py'}
        
        response = gate.request_approval(
            OperationType.CREATE_FILE,
            params,
            "test_session"
        )
        
        # フェイルセーフとして拒否される
        assert response.approved is False
        assert "承認UIが設定されていません" in response.reason
    
    def test_request_approval_bypass_detection(self):
        """バイパス試行検出のテスト"""
        # バイパス試行を含むパラメータ
        params = {'target': 'test.py', 'bypass_approval': 'true'}
        
        # 複数回試行してバイパス検出
        exception_raised = False
        for i in range(4):  # max_bypass_attempts = 3 を超える
            try:
                self.gate.request_approval(
                    OperationType.CREATE_FILE,
                    params,
                    "test_session"
                )
            except ApprovalBypassAttemptError:
                # 例外が発生したことを記録
                exception_raised = True
                assert i >= 2  # 3回目（インデックス2）以降で例外が発生
                break
        
        # 例外が発生したことを確認
        assert exception_raised, "ApprovalBypassAttemptError が発生しませんでした"
    
    def test_generate_approval_message(self):
        """承認メッセージ生成のテスト"""
        operation_info = OperationInfo(
            operation_type=OperationType.CREATE_FILE,
            target="test.py",
            description="ファイル 'test.py' を作成",
            risk_level=RiskLevel.HIGH_RISK,
            details={},
            preview="print('hello')"
        )
        
        message = self.gate._generate_approval_message(operation_info)
        
        assert "test.py" in message
        assert "high_risk" in message
        assert "print('hello')" in message
        assert "実行してもよろしいですか？" in message
    
    def test_generate_approval_message_no_preview(self):
        """プレビューなしの承認メッセージ生成テスト"""
        self.gate.config.show_content_preview = False
        
        operation_info = OperationInfo(
            operation_type=OperationType.CREATE_FILE,
            target="test.py",
            description="ファイル 'test.py' を作成",
            risk_level=RiskLevel.HIGH_RISK,
            details={},
            preview="print('hello')"
        )
        
        message = self.gate._generate_approval_message(operation_info)
        
        assert "test.py" in message
        assert "print('hello')" not in message  # プレビューは含まれない
    
    def test_generate_approval_message_long_preview(self):
        """長いプレビューの承認メッセージ生成テスト"""
        long_preview = "a" * 300  # max_preview_length (200) を超える
        
        operation_info = OperationInfo(
            operation_type=OperationType.CREATE_FILE,
            target="test.py",
            description="ファイル 'test.py' を作成",
            risk_level=RiskLevel.HIGH_RISK,
            details={},
            preview=long_preview
        )
        
        message = self.gate._generate_approval_message(operation_info)
        
        assert "..." in message  # 省略記号が含まれる
        assert len(message) < len(long_preview) + 100  # メッセージが短縮されている
    
    def test_handle_rejection_create_file(self):
        """ファイル作成拒否時の対応テスト"""
        operation_info = OperationInfo(
            operation_type=OperationType.CREATE_FILE,
            target="test.py",
            description="ファイル 'test.py' を作成",
            risk_level=RiskLevel.HIGH_RISK,
            details={}
        )
        
        message = self.gate.handle_rejection(operation_info, "ユーザー拒否")
        
        assert "実行しません" in message
        assert "代わりに" in message
        assert "内容だけを表示" in message or "安全な場所" in message
    
    def test_handle_rejection_execute_code(self):
        """コード実行拒否時の対応テスト"""
        operation_info = OperationInfo(
            operation_type=OperationType.EXECUTE_PYTHON,
            target="script.py",
            description="Pythonファイル 'script.py' を実行",
            risk_level=RiskLevel.HIGH_RISK,
            details={}
        )
        
        message = self.gate.handle_rejection(operation_info, "ユーザー拒否")
        
        assert "実行しません" in message
        assert "代わりに" in message
        assert "コードを確認" in message or "安全な方法" in message
    
    def test_handle_rejection_unknown_operation(self):
        """未知の操作拒否時の対応テスト"""
        operation_info = OperationInfo(
            operation_type="unknown_operation",
            target="test",
            description="未知の操作",
            risk_level=RiskLevel.HIGH_RISK,
            details={}
        )
        
        message = self.gate.handle_rejection(operation_info, "ユーザー拒否")
        
        assert "実行しません" in message
        assert "他に何か" in message
    
    def test_detect_bypass_attempt_suspicious_params(self):
        """疑わしいパラメータでのバイパス検出テスト"""
        # 疑わしいパラメータ（値に含まれる場合）
        assert self.gate._detect_bypass_attempt("test", {"config": "bypass_approval"}) is True
        assert self.gate._detect_bypass_attempt("test", {"setting": "disable_approval"}) is True
        assert self.gate._detect_bypass_attempt("test", {"option": "skip_approval"}) is True
        
        # 疑わしいパラメータ（キー名に含まれる場合）
        assert self.gate._detect_bypass_attempt("test", {"bypass_approval": "true"}) is True
        assert self.gate._detect_bypass_attempt("test", {"disable_approval": "yes"}) is True
        
        # 正常なパラメータ
        assert self.gate._detect_bypass_attempt("test", {"target": "normal_file.py"}) is False
        assert self.gate._detect_bypass_attempt("test", {"content": "print('hello')"}) is False
    
    def test_detect_bypass_attempt_suspicious_operation_type(self):
        """疑わしい操作タイプでのバイパス検出テスト"""
        assert self.gate._detect_bypass_attempt("disable_approval", {}) is True
        assert self.gate._detect_bypass_attempt("bypass_approval_check", {}) is True
        assert self.gate._detect_bypass_attempt("skip_approval_system", {}) is True
        assert self.gate._detect_bypass_attempt("normal_operation", {}) is False
    
    def test_approval_logging(self):
        """承認ログ記録のテスト"""
        params = {'target': 'test.py'}
        
        # 複数の承認要求を実行
        self.gate.request_approval(OperationType.READ_FILE, params, "session1")
        self.gate.request_approval(OperationType.READ_FILE, params, "session2")
        
        assert len(self.gate.approval_logs) == 2
        assert self.gate.approval_logs[0].session_id == "session1"
        assert self.gate.approval_logs[1].session_id == "session2"
    
    def test_approval_logging_limit(self):
        """承認ログ制限のテスト"""
        params = {'target': 'test.py'}
        
        # 101回の承認要求を実行（制限は100）
        for i in range(101):
            self.gate.request_approval(OperationType.READ_FILE, params, f"session{i}")
        
        # 最新100件のみ保持されている
        assert len(self.gate.approval_logs) == 100
        assert self.gate.approval_logs[0].session_id == "session1"  # 最初の1件は削除
        assert self.gate.approval_logs[-1].session_id == "session100"
    
    def test_get_approval_statistics_empty(self):
        """空の承認統計テスト"""
        stats = self.gate.get_approval_statistics()
        
        assert stats["total_requests"] == 0
        assert stats["approved_count"] == 0
        assert stats["rejected_count"] == 0
        assert stats["approval_rate"] == 0.0
        assert stats["average_response_time"] == 0.0
    
    def test_get_approval_statistics_with_data(self):
        """データありの承認統計テスト"""
        params = {'target': 'test.py'}
        
        # 承認と拒否を混在させる
        self.mock_ui.default_response = True
        self.gate.request_approval(OperationType.CREATE_FILE, params, "session1")
        
        self.mock_ui.default_response = False
        self.gate.request_approval(OperationType.CREATE_FILE, params, "session2")
        
        stats = self.gate.get_approval_statistics()
        
        assert stats["total_requests"] == 2
        assert stats["approved_count"] == 1
        assert stats["rejected_count"] == 1
        assert stats["approval_rate"] == 50.0
        assert stats["average_response_time"] > 0
    
    def test_clear_logs(self):
        """ログクリアのテスト"""
        params = {'target': 'test.py'}
        
        # ログを作成
        self.gate.request_approval(OperationType.READ_FILE, params, "session1")
        assert len(self.gate.approval_logs) == 1
        
        # ログをクリア
        self.gate.clear_logs()
        assert len(self.gate.approval_logs) == 0
        assert self.gate._bypass_attempts == 0
    
    def test_update_config(self):
        """設定更新のテスト"""
        new_config = ApprovalConfig(mode=ApprovalMode.STRICT)
        
        self.gate.update_config(new_config)
        assert self.gate.config.mode == ApprovalMode.STRICT
    
    def test_update_config_invalid(self):
        """無効な設定更新のテスト"""
        with pytest.raises(ValueError, match="new_config は ApprovalConfig である必要があります"):
            self.gate.update_config("invalid")
    
    def test_request_approval_exception_handling(self):
        """例外処理のテスト"""
        # UIが例外を発生させる場合
        class ErrorUI:
            def show_approval_request(self, request):
                raise Exception("UI エラー")
        
        self.gate.set_approval_ui(ErrorUI())
        params = {'target': 'test.py'}
        
        response = self.gate.request_approval(
            OperationType.CREATE_FILE,
            params,
            "test_session"
        )
        
        # フェイルセーフとして拒否される
        assert response.approved is False
        assert "承認システムエラー" in response.reason