"""
Test suite for approval system security features
承認システムのセキュリティ機能のテスト
"""

import pytest
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from companion.approval_system import (
    ApprovalGate, ApprovalConfig, ApprovalMode, RiskLevel,
    OperationInfo, OperationType, ApprovalResponse,
    ApprovalBypassAttemptError, SecurityViolationError,
    ApprovalTimeoutError, ApprovalUIError
)


class TestApprovalSecurityFeatures:
    """承認システムのセキュリティ機能テスト"""
    
    def setup_method(self):
        """各テストメソッドの前に実行される初期化"""
        self.config = ApprovalConfig(mode=ApprovalMode.STANDARD)
        self.gate = ApprovalGate(config=self.config)
        
        # テスト用の操作情報
        self.test_operation = OperationInfo(
            operation_type=OperationType.CREATE_FILE,
            target="test.py",
            description="テストファイル作成",
            risk_level=RiskLevel.HIGH_RISK,
            details={"content": "test"}
        )
        
        self.critical_operation = OperationInfo(
            operation_type=OperationType.DELETE_FILE,
            target="important.txt",
            description="重要ファイル削除",
            risk_level=RiskLevel.CRITICAL_RISK,
            details={}
        )
    
    def test_security_logging_initialization(self):
        """セキュリティログの初期化テスト"""
        assert hasattr(self.gate, 'security_logs')
        assert isinstance(self.gate.security_logs, list)
        assert len(self.gate.security_logs) == 0
        assert self.gate._security_monitoring_enabled is True
    
    def test_log_security_event(self):
        """セキュリティイベントログのテスト"""
        self.gate._log_security_event(
            "test_event",
            "Test security event",
            self.test_operation,
            {"test": "data"}
        )
        
        assert len(self.gate.security_logs) == 1
        log_entry = self.gate.security_logs[0]
        
        assert log_entry["event_type"] == "test_event"
        assert log_entry["message"] == "Test security event"
        assert log_entry["operation_info"] is not None
        assert log_entry["details"]["test"] == "data"
        assert "timestamp" in log_entry
    
    def test_security_logging_disabled(self):
        """セキュリティログ無効時のテスト"""
        self.gate.enable_security_monitoring(False)
        
        self.gate._log_security_event(
            "test_event",
            "This should not be logged"
        )
        
        # 無効化後のイベントはログされない（enable_security_monitoringのログのみ）
        assert len(self.gate.security_logs) == 1
        assert self.gate.security_logs[0]["event_type"] == "monitoring_toggle"
    
    def test_bypass_attempt_detection_suspicious_call_stack(self):
        """疑わしい呼び出しスタックでのバイパス試行検出テスト"""
        # 疑わしい呼び出しスタックをシミュレート
        suspicious_stack = ["main", "open", "write", "create_file"]
        
        with pytest.raises(ApprovalBypassAttemptError) as exc_info:
            self.gate._detect_bypass_attempt(self.test_operation, suspicious_stack)
        
        assert "Suspicious function call" in str(exc_info.value)
        assert self.gate._bypass_attempts == 1
        assert len(self.gate.security_logs) > 0
        
        # セキュリティログを確認
        bypass_logs = [log for log in self.gate.security_logs if log["event_type"] == "bypass_attempt"]
        assert len(bypass_logs) == 1
    
    def test_bypass_attempt_detection_critical_operation(self):
        """重要操作での不適切なフローでのバイパス試行検出テスト"""
        # 適切な承認フローを経ていない呼び出しスタック
        improper_stack = ["main", "execute", "delete_file"]
        
        with pytest.raises(ApprovalBypassAttemptError) as exc_info:
            self.gate._detect_bypass_attempt(self.critical_operation, improper_stack)
        
        assert "without proper approval flow" in str(exc_info.value)
        assert self.gate._bypass_attempts == 1
    
    def test_proper_approval_flow_detection(self):
        """適切な承認フローの検出テスト"""
        # 適切な承認フローを含む呼び出しスタック
        proper_stack = ["main", "request_approval", "show_approval_request", "create_file"]
        
        result = self.gate._has_proper_approval_flow(proper_stack)
        assert result is True
        
        # 不適切なフロー
        improper_stack = ["main", "direct_call", "create_file"]
        result = self.gate._has_proper_approval_flow(improper_stack)
        assert result is False
    
    def test_rapid_operations_detection(self):
        """連続操作の検出テスト"""
        # 複数の操作ログを作成（同じタイプの操作を短時間で実行）
        from companion.approval_system import ApprovalLog
        
        current_time = datetime.now()
        for i in range(6):  # 5回以上の同じ操作
            log_entry = ApprovalLog(
                operation_info=self.test_operation,
                approved=True,
                reason="test",
                user_response_time=1.0,
                timestamp=current_time - timedelta(seconds=i),
                session_id="test"
            )
            self.gate.approval_logs.append(log_entry)
        
        # 連続操作が検出されるはず
        result = self.gate._detect_rapid_operations(self.test_operation)
        assert result is True
    
    def test_max_bypass_attempts_exceeded(self):
        """最大バイパス試行回数超過のテスト"""
        suspicious_stack = ["main", "open", "write"]
        
        # 最大試行回数まで試行
        for i in range(self.gate._max_bypass_attempts - 1):
            with pytest.raises(ApprovalBypassAttemptError):
                self.gate._detect_bypass_attempt(self.test_operation, suspicious_stack)
        
        # 最大回数を超えた場合はSecurityViolationErrorが発生
        with pytest.raises(SecurityViolationError) as exc_info:
            self.gate._detect_bypass_attempt(self.test_operation, suspicious_stack)
        
        assert "Maximum approval bypass attempts" in str(exc_info.value)
        assert exc_info.value.violation_type == "max_bypass_attempts_exceeded"
    
    def test_fail_safe_response_creation(self):
        """フェイルセーフ応答作成のテスト"""
        test_error = ApprovalBypassAttemptError("Test bypass attempt")
        
        response = self.gate._create_fail_safe_response(test_error, self.test_operation)
        
        assert response.approved is False
        assert "安全のため操作を拒否" in response.reason
        assert response.details["fail_safe_triggered"] is True
        assert response.details["error_type"] == "ApprovalBypassAttemptError"
        
        # フェイルセーフログが記録されることを確認
        fail_safe_logs = [log for log in self.gate.security_logs if log["event_type"] == "fail_safe_triggered"]
        assert len(fail_safe_logs) == 1
    
    def test_security_logs_retrieval(self):
        """セキュリティログ取得のテスト"""
        # 複数のイベントをログ
        self.gate._log_security_event("bypass_attempt", "Test bypass 1")
        self.gate._log_security_event("security_violation", "Test violation")
        self.gate._log_security_event("bypass_attempt", "Test bypass 2")
        
        # 全ログ取得
        all_logs = self.gate.get_security_logs()
        assert len(all_logs) == 3
        
        # イベントタイプでフィルタ
        bypass_logs = self.gate.get_security_logs(event_type="bypass_attempt")
        assert len(bypass_logs) == 2
        
        violation_logs = self.gate.get_security_logs(event_type="security_violation")
        assert len(violation_logs) == 1
        
        # 件数制限
        limited_logs = self.gate.get_security_logs(limit=2)
        assert len(limited_logs) == 2
    
    def test_security_summary(self):
        """セキュリティサマリーのテスト"""
        # いくつかのセキュリティイベントを生成
        self.gate._log_security_event("bypass_attempt", "Test bypass")
        self.gate._log_security_event("security_violation", "Test violation")
        self.gate._bypass_attempts = 2
        
        summary = self.gate.get_security_summary()
        
        assert summary["total_security_events"] == 2
        assert summary["bypass_attempts"] == 2
        assert summary["max_bypass_attempts"] == 3
        assert summary["event_type_counts"]["bypass_attempt"] == 1
        assert summary["event_type_counts"]["security_violation"] == 1
        assert summary["monitoring_enabled"] is True
        assert summary["last_event_time"] is not None
    
    def test_security_state_reset(self):
        """セキュリティ状態リセットのテスト"""
        # セキュリティイベントを生成
        self.gate._log_security_event("bypass_attempt", "Test bypass")
        self.gate._bypass_attempts = 2
        
        # リセット前の状態確認
        assert len(self.gate.security_logs) == 1
        assert self.gate._bypass_attempts == 2
        
        # リセット実行
        self.gate.reset_security_state()
        
        # リセット後の状態確認
        assert self.gate._bypass_attempts == 0
        assert len(self.gate.security_logs) == 1  # リセットイベントのログのみ
        assert self.gate.security_logs[0]["event_type"] == "security_reset"
    
    def test_security_monitoring_toggle(self):
        """セキュリティ監視の有効/無効切り替えテスト"""
        # 初期状態は有効
        assert self.gate._security_monitoring_enabled is True
        
        # 無効化
        self.gate.enable_security_monitoring(False)
        assert self.gate._security_monitoring_enabled is False
        
        # 再有効化
        self.gate.enable_security_monitoring(True)
        assert self.gate._security_monitoring_enabled is True
        
        # 切り替えログが記録されることを確認
        toggle_logs = [log for log in self.gate.security_logs if log["event_type"] == "monitoring_toggle"]
        assert len(toggle_logs) == 2


class TestApprovalGateSecurityIntegration:
    """ApprovalGateのセキュリティ統合テスト"""
    
    def setup_method(self):
        """各テストメソッドの前に実行される初期化"""
        self.config = ApprovalConfig(mode=ApprovalMode.STANDARD)
        self.gate = ApprovalGate(config=self.config)
        
        # モック承認UIを設定
        self.mock_ui = Mock()
        self.gate.set_approval_ui(self.mock_ui)
    
    def test_request_approval_with_bypass_attempt(self):
        """承認要求でバイパス試行が検出された場合のテスト"""
        # バイパス試行を検出するようにモック
        with patch.object(self.gate, '_detect_bypass_attempt') as mock_detect:
            mock_detect.side_effect = ApprovalBypassAttemptError("Test bypass attempt")
            
            response = self.gate.request_approval(
                OperationType.CREATE_FILE,
                {"file_path": "test.py", "content": "test"},
                "test_session"
            )
            
            # フェイルセーフ応答が返されることを確認
            assert response.approved is False
            assert "安全のため操作を拒否" in response.reason
            assert response.details["fail_safe_triggered"] is True
    
    def test_request_approval_with_security_violation(self):
        """承認要求でセキュリティ違反が検出された場合のテスト"""
        # セキュリティ違反を検出するようにモック
        with patch.object(self.gate, '_detect_bypass_attempt') as mock_detect:
            mock_detect.side_effect = SecurityViolationError(
                "Max attempts exceeded", "max_bypass_attempts_exceeded"
            )
            
            response = self.gate.request_approval(
                OperationType.CREATE_FILE,
                {"file_path": "test.py", "content": "test"},
                "test_session"
            )
            
            # フェイルセーフ応答が返されることを確認
            assert response.approved is False
            assert "安全のため操作を拒否" in response.reason
    
    def test_request_approval_with_timeout_error(self):
        """承認要求でタイムアウトエラーが発生した場合のテスト"""
        # タイムアウトエラーを発生させるようにモック
        self.mock_ui.show_approval_request.side_effect = ApprovalTimeoutError("Timeout occurred")
        
        response = self.gate.request_approval(
            OperationType.CREATE_FILE,
            {"file_path": "test.py", "content": "test"},
            "test_session"
        )
        
        # フェイルセーフ応答が返されることを確認
        assert response.approved is False
        assert "安全のため操作を拒否" in response.reason
    
    def test_request_approval_with_ui_error(self):
        """承認要求でUIエラーが発生した場合のテスト"""
        # UIエラーを発生させるようにモック
        self.mock_ui.show_approval_request.side_effect = ApprovalUIError("UI Error")
        
        response = self.gate.request_approval(
            OperationType.CREATE_FILE,
            {"file_path": "test.py", "content": "test"},
            "test_session"
        )
        
        # フェイルセーフ応答が返されることを確認
        assert response.approved is False
        assert "安全のため操作を拒否" in response.reason
    
    def test_request_approval_with_unexpected_error(self):
        """承認要求で予期しないエラーが発生した場合のテスト"""
        # 予期しないエラーを発生させるようにモック
        self.mock_ui.show_approval_request.side_effect = Exception("Unexpected error")
        
        response = self.gate.request_approval(
            OperationType.CREATE_FILE,
            {"file_path": "test.py", "content": "test"},
            "test_session"
        )
        
        # フェイルセーフ応答が返されることを確認
        assert response.approved is False
        assert "安全のため操作を拒否" in response.reason
    
    def test_security_logging_during_normal_operation(self):
        """通常操作中のセキュリティログのテスト"""
        # 正常な承認応答を設定
        self.mock_ui.show_approval_request.return_value = ApprovalResponse(approved=True)
        
        # バイパス試行が検出されないようにモック
        with patch.object(self.gate, '_detect_bypass_attempt') as mock_detect:
            mock_detect.return_value = False
            
            response = self.gate.request_approval(
                OperationType.CREATE_FILE,
                {"file_path": "test.py", "content": "test"},
                "test_session"
            )
            
            assert response.approved is True
            
            # セキュリティ関連のログが記録されていないことを確認
            security_logs = self.gate.get_security_logs()
            bypass_logs = [log for log in security_logs if log["event_type"] == "bypass_attempt"]
            assert len(bypass_logs) == 0


class TestSecurityExceptions:
    """セキュリティ例外クラスのテスト"""
    
    def test_approval_bypass_attempt_error(self):
        """ApprovalBypassAttemptErrorのテスト"""
        operation_info = OperationInfo(
            operation_type=OperationType.CREATE_FILE,
            target="test.py",
            description="Test operation",
            risk_level=RiskLevel.HIGH_RISK,
            details={}
        )
        
        attempt_details = {"suspicious_calls": ["open", "write"]}
        
        error = ApprovalBypassAttemptError(
            "Bypass attempt detected",
            operation_info,
            attempt_details
        )
        
        assert str(error) == "Bypass attempt detected"
        assert error.operation_info == operation_info
        assert error.attempt_details == attempt_details
        assert isinstance(error.timestamp, datetime)
    
    def test_security_violation_error(self):
        """SecurityViolationErrorのテスト"""
        details = {"attempts": 5, "max_attempts": 3}
        
        error = SecurityViolationError(
            "Max attempts exceeded",
            "max_bypass_attempts_exceeded",
            details
        )
        
        assert str(error) == "Max attempts exceeded"
        assert error.violation_type == "max_bypass_attempts_exceeded"
        assert error.details == details
        assert isinstance(error.timestamp, datetime)
    
    def test_security_exceptions_inheritance(self):
        """セキュリティ例外の継承関係のテスト"""
        from companion.approval_system import ApprovalSystemError
        
        bypass_error = ApprovalBypassAttemptError("Test")
        violation_error = SecurityViolationError("Test", "test_type")
        
        assert isinstance(bypass_error, ApprovalSystemError)
        assert isinstance(violation_error, ApprovalSystemError)
        assert isinstance(bypass_error, Exception)
        assert isinstance(violation_error, Exception)