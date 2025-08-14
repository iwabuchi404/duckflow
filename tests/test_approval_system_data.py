"""
Test suite for approval system data structures
承認システムのデータ構造のテスト
"""

import pytest
from datetime import datetime
from companion.approval_system import (
    RiskLevel, ApprovalMode, OperationInfo, ApprovalRequest, 
    ApprovalResponse, ApprovalLog, OperationType, OPERATION_RISK_MAPPING,
    ApprovalSystemError, ApprovalTimeoutError, ApprovalBypassAttemptError, ApprovalUIError
)


class TestRiskLevel:
    """RiskLevel enumのテスト"""
    
    def test_risk_level_values(self):
        """リスクレベルの値が正しいことを確認"""
        assert RiskLevel.LOW_RISK.value == "low_risk"
        assert RiskLevel.HIGH_RISK.value == "high_risk"
        assert RiskLevel.CRITICAL_RISK.value == "critical_risk"
    
    def test_risk_level_comparison(self):
        """リスクレベルの比較が可能であることを確認"""
        assert RiskLevel.LOW_RISK != RiskLevel.HIGH_RISK
        assert RiskLevel.HIGH_RISK != RiskLevel.CRITICAL_RISK


class TestApprovalMode:
    """ApprovalMode enumのテスト"""
    
    def test_approval_mode_values(self):
        """承認モードの値が正しいことを確認"""
        assert ApprovalMode.STRICT.value == "strict"
        assert ApprovalMode.STANDARD.value == "standard"
        assert ApprovalMode.TRUSTED.value == "trusted"


class TestOperationInfo:
    """OperationInfo dataclassのテスト"""
    
    def test_valid_operation_info_creation(self):
        """有効なOperationInfoの作成"""
        op_info = OperationInfo(
            operation_type="create_file",
            target="test.py",
            description="テストファイルを作成",
            risk_level=RiskLevel.HIGH_RISK,
            details={"size": 100},
            preview="print('hello')"
        )
        
        assert op_info.operation_type == "create_file"
        assert op_info.target == "test.py"
        assert op_info.description == "テストファイルを作成"
        assert op_info.risk_level == RiskLevel.HIGH_RISK
        assert op_info.details == {"size": 100}
        assert op_info.preview == "print('hello')"
    
    def test_operation_info_without_preview(self):
        """プレビューなしのOperationInfo作成"""
        op_info = OperationInfo(
            operation_type="read_file",
            target="test.py",
            description="ファイルを読み取り",
            risk_level=RiskLevel.LOW_RISK,
            details={}
        )
        
        assert op_info.preview is None
    
    def test_operation_info_validation_empty_operation_type(self):
        """operation_typeが空の場合のバリデーション"""
        with pytest.raises(ValueError, match="operation_type は必須です"):
            OperationInfo(
                operation_type="",
                target="test.py",
                description="テスト",
                risk_level=RiskLevel.HIGH_RISK,
                details={}
            )
    
    def test_operation_info_validation_empty_target(self):
        """targetが空の場合のバリデーション"""
        with pytest.raises(ValueError, match="target は必須です"):
            OperationInfo(
                operation_type="create_file",
                target="",
                description="テスト",
                risk_level=RiskLevel.HIGH_RISK,
                details={}
            )
    
    def test_operation_info_validation_empty_description(self):
        """descriptionが空の場合のバリデーション"""
        with pytest.raises(ValueError, match="description は必須です"):
            OperationInfo(
                operation_type="create_file",
                target="test.py",
                description="",
                risk_level=RiskLevel.HIGH_RISK,
                details={}
            )
    
    def test_operation_info_validation_invalid_risk_level(self):
        """無効なrisk_levelの場合のバリデーション"""
        with pytest.raises(ValueError, match="risk_level は RiskLevel enum である必要があります"):
            OperationInfo(
                operation_type="create_file",
                target="test.py",
                description="テスト",
                risk_level="invalid",  # 文字列は無効
                details={}
            )


class TestApprovalRequest:
    """ApprovalRequest dataclassのテスト"""
    
    def test_valid_approval_request_creation(self):
        """有効なApprovalRequestの作成"""
        op_info = OperationInfo(
            operation_type="create_file",
            target="test.py",
            description="テストファイルを作成",
            risk_level=RiskLevel.HIGH_RISK,
            details={}
        )
        
        timestamp = datetime.now()
        request = ApprovalRequest(
            operation_info=op_info,
            message="ファイルを作成してもよろしいですか？",
            timestamp=timestamp,
            session_id="test_session"
        )
        
        assert request.operation_info == op_info
        assert request.message == "ファイルを作成してもよろしいですか？"
        assert request.timestamp == timestamp
        assert request.session_id == "test_session"
    
    def test_approval_request_validation_invalid_operation_info(self):
        """無効なoperation_infoの場合のバリデーション"""
        with pytest.raises(ValueError, match="operation_info は OperationInfo である必要があります"):
            ApprovalRequest(
                operation_info="invalid",  # 文字列は無効
                message="テスト",
                timestamp=datetime.now(),
                session_id="test"
            )
    
    def test_approval_request_validation_empty_message(self):
        """messageが空の場合のバリデーション"""
        op_info = OperationInfo(
            operation_type="create_file",
            target="test.py",
            description="テスト",
            risk_level=RiskLevel.HIGH_RISK,
            details={}
        )
        
        with pytest.raises(ValueError, match="message は必須です"):
            ApprovalRequest(
                operation_info=op_info,
                message="",
                timestamp=datetime.now(),
                session_id="test"
            )
    
    def test_approval_request_validation_empty_session_id(self):
        """session_idが空の場合のバリデーション"""
        op_info = OperationInfo(
            operation_type="create_file",
            target="test.py",
            description="テスト",
            risk_level=RiskLevel.HIGH_RISK,
            details={}
        )
        
        with pytest.raises(ValueError, match="session_id は必須です"):
            ApprovalRequest(
                operation_info=op_info,
                message="テスト",
                timestamp=datetime.now(),
                session_id=""
            )


class TestApprovalResponse:
    """ApprovalResponse dataclassのテスト"""
    
    def test_approved_response(self):
        """承認された応答のテスト"""
        response = ApprovalResponse(approved=True)
        
        assert response.approved is True
        assert response.reason is None
        assert response.alternative_suggested is False
        assert isinstance(response.timestamp, datetime)
    
    def test_rejected_response_with_reason(self):
        """理由付きで拒否された応答のテスト"""
        response = ApprovalResponse(
            approved=False,
            reason="ユーザーが拒否しました",
            alternative_suggested=True
        )
        
        assert response.approved is False
        assert response.reason == "ユーザーが拒否しました"
        assert response.alternative_suggested is True
        assert isinstance(response.timestamp, datetime)
    
    def test_rejected_response_default_reason(self):
        """理由なしで拒否された場合のデフォルト理由"""
        response = ApprovalResponse(approved=False)
        
        assert response.approved is False
        assert response.reason == "ユーザーにより拒否されました"
        assert response.alternative_suggested is False


class TestApprovalLog:
    """ApprovalLog dataclassのテスト"""
    
    def test_valid_approval_log_creation(self):
        """有効なApprovalLogの作成"""
        op_info = OperationInfo(
            operation_type="create_file",
            target="test.py",
            description="テスト",
            risk_level=RiskLevel.HIGH_RISK,
            details={}
        )
        
        timestamp = datetime.now()
        log = ApprovalLog(
            timestamp=timestamp,
            operation_info=op_info,
            approved=True,
            user_response_time=2.5,
            session_id="test_session"
        )
        
        assert log.timestamp == timestamp
        assert log.operation_info == op_info
        assert log.approved is True
        assert log.user_response_time == 2.5
        assert log.session_id == "test_session"
    
    def test_approval_log_validation_invalid_operation_info(self):
        """無効なoperation_infoの場合のバリデーション"""
        with pytest.raises(ValueError, match="operation_info は OperationInfo である必要があります"):
            ApprovalLog(
                timestamp=datetime.now(),
                operation_info="invalid",
                approved=True,
                user_response_time=1.0,
                session_id="test"
            )
    
    def test_approval_log_validation_negative_response_time(self):
        """負の応答時間の場合のバリデーション"""
        op_info = OperationInfo(
            operation_type="create_file",
            target="test.py",
            description="テスト",
            risk_level=RiskLevel.HIGH_RISK,
            details={}
        )
        
        with pytest.raises(ValueError, match="user_response_time は0以上である必要があります"):
            ApprovalLog(
                timestamp=datetime.now(),
                operation_info=op_info,
                approved=True,
                user_response_time=-1.0,
                session_id="test"
            )


class TestOperationType:
    """OperationType定数のテスト"""
    
    def test_operation_type_constants(self):
        """操作タイプ定数の値確認"""
        assert OperationType.CREATE_FILE == "create_file"
        assert OperationType.WRITE_FILE == "write_file"
        assert OperationType.READ_FILE == "read_file"
        assert OperationType.EXECUTE_PYTHON == "execute_python"


class TestOperationRiskMapping:
    """操作リスクマッピングのテスト"""
    
    def test_low_risk_operations(self):
        """低リスク操作のマッピング確認"""
        assert OPERATION_RISK_MAPPING[OperationType.READ_FILE] == RiskLevel.LOW_RISK
        assert OPERATION_RISK_MAPPING[OperationType.LIST_FILES] == RiskLevel.LOW_RISK
    
    def test_high_risk_operations(self):
        """高リスク操作のマッピング確認"""
        assert OPERATION_RISK_MAPPING[OperationType.CREATE_FILE] == RiskLevel.HIGH_RISK
        assert OPERATION_RISK_MAPPING[OperationType.WRITE_FILE] == RiskLevel.HIGH_RISK
        assert OPERATION_RISK_MAPPING[OperationType.EXECUTE_PYTHON] == RiskLevel.HIGH_RISK
    
    def test_critical_risk_operations(self):
        """重要リスク操作のマッピング確認"""
        assert OPERATION_RISK_MAPPING[OperationType.INSTALL_PACKAGE] == RiskLevel.CRITICAL_RISK
        assert OPERATION_RISK_MAPPING[OperationType.MODIFY_SYSTEM] == RiskLevel.CRITICAL_RISK


class TestExceptions:
    """例外クラスのテスト"""
    
    def test_approval_system_error(self):
        """ApprovalSystemError基底例外"""
        with pytest.raises(ApprovalSystemError):
            raise ApprovalSystemError("テストエラー")
    
    def test_approval_timeout_error(self):
        """ApprovalTimeoutError例外"""
        with pytest.raises(ApprovalTimeoutError):
            raise ApprovalTimeoutError("タイムアウト")
    
    def test_approval_bypass_attempt_error(self):
        """ApprovalBypassAttemptError例外"""
        with pytest.raises(ApprovalBypassAttemptError):
            raise ApprovalBypassAttemptError("バイパス試行")
    
    def test_approval_ui_error(self):
        """ApprovalUIError例外"""
        with pytest.raises(ApprovalUIError):
            raise ApprovalUIError("UI エラー")
    
    def test_exception_inheritance(self):
        """例外の継承関係確認"""
        assert issubclass(ApprovalTimeoutError, ApprovalSystemError)
        assert issubclass(ApprovalBypassAttemptError, ApprovalSystemError)
        assert issubclass(ApprovalUIError, ApprovalSystemError)