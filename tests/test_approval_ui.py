"""
Test suite for UserApprovalUI class
UserApprovalUIクラスのテスト
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from companion.approval_ui import UserApprovalUI
from companion.approval_system import (
    ApprovalRequest, ApprovalResponse, OperationInfo, RiskLevel, OperationType,
    ApprovalTimeoutError, ApprovalUIError
)


class TestUserApprovalUI:
    """UserApprovalUIクラスのテスト"""
    
    def setup_method(self):
        """各テストメソッドの前に実行される初期化"""
        self.ui = UserApprovalUI(timeout_seconds=30)
        
        # テスト用の操作情報
        self.operation_info = OperationInfo(
            operation_type=OperationType.CREATE_FILE,
            target="test.py",
            description="ファイル 'test.py' を作成",
            risk_level=RiskLevel.HIGH_RISK,
            details={"content": "print('hello')"},
            preview="print('hello')"
        )
        
        # テスト用の承認要求
        self.approval_request = ApprovalRequest(
            operation_info=self.operation_info,
            message="テスト承認要求",
            timestamp=datetime.now(),
            session_id="test_session"
        )
    
    def test_initialization_default(self):
        """デフォルト初期化のテスト"""
        ui = UserApprovalUI()
        
        assert ui.timeout_seconds == 30
        assert len(ui.thinking_expressions) > 0
        assert len(ui.approval_expressions) > 0
        assert len(ui.thanks_expressions) > 0
        assert len(ui.understanding_expressions) > 0
    
    def test_initialization_custom_timeout(self):
        """カスタムタイムアウトでの初期化テスト"""
        ui = UserApprovalUI(timeout_seconds=60)
        
        assert ui.timeout_seconds == 60
    
    @patch('companion.approval_ui.rich_ui')
    def test_show_approval_request_approved(self, mock_rich_ui):
        """承認された場合のテスト"""
        # rich_uiのget_confirmationをモック
        mock_rich_ui.get_confirmation.return_value = True
        
        response = self.ui.show_approval_request(self.approval_request)
        
        assert response.approved is True
        assert isinstance(response.timestamp, datetime)
        
        # UIメソッドが呼ばれたことを確認
        mock_rich_ui.print_message.assert_called()
        mock_rich_ui.print_panel.assert_called()
        mock_rich_ui.get_confirmation.assert_called_once()
    
    @patch('companion.approval_ui.rich_ui')
    def test_show_approval_request_rejected(self, mock_rich_ui):
        """拒否された場合のテスト"""
        # rich_uiのget_confirmationをモック
        mock_rich_ui.get_confirmation.return_value = False
        
        response = self.ui.show_approval_request(self.approval_request)
        
        assert response.approved is False
        assert isinstance(response.timestamp, datetime)
        
        # UIメソッドが呼ばれたことを確認
        mock_rich_ui.print_message.assert_called()
        mock_rich_ui.print_panel.assert_called()
        mock_rich_ui.get_confirmation.assert_called_once()
    
    @patch('companion.approval_ui.rich_ui')
    @patch('companion.approval_ui.time.sleep')  # sleepをモックして高速化
    def test_show_approval_request_keyboard_interrupt(self, mock_sleep, mock_rich_ui):
        """キーボード割り込みのテスト"""
        # _get_user_responseでKeyboardInterruptを発生させる
        def mock_get_user_response():
            raise KeyboardInterrupt()
        
        # _get_user_responseメソッドをモック
        self.ui._get_user_response = mock_get_user_response
        
        response = self.ui.show_approval_request(self.approval_request)
        
        assert response.approved is False
        assert response.reason == "ユーザーによりキャンセルされました"
    
    @patch('companion.approval_ui.rich_ui')
    def test_show_approval_request_ui_error(self, mock_rich_ui):
        """UI関連エラーのテスト"""
        # 例外を発生させる
        mock_rich_ui.print_panel.side_effect = Exception("UI エラー")
        
        with pytest.raises(ApprovalUIError, match="承認UI処理中にエラーが発生しました"):
            self.ui.show_approval_request(self.approval_request)
    
    def test_format_operation_details_basic(self):
        """基本的な操作詳細整形のテスト"""
        details = self.ui.format_operation_details(self.operation_info)
        
        assert "ファイル 'test.py' を作成" in details
        assert "test.py" in details
        assert "高リスク" in details
        assert "print('hello')" in details
    
    def test_format_operation_details_no_content(self):
        """内容なしの操作詳細整形のテスト"""
        operation_info = OperationInfo(
            operation_type=OperationType.READ_FILE,
            target="test.txt",
            description="ファイル 'test.txt' を読み取り",
            risk_level=RiskLevel.LOW_RISK,
            details={}
        )
        
        details = self.ui.format_operation_details(operation_info)
        
        assert "ファイル 'test.txt' を読み取り" in details
        assert "test.txt" in details
        assert "低リスク" in details
    
    def test_format_operation_details_long_content(self):
        """長い内容の操作詳細整形のテスト"""
        long_content = "a" * 150  # 100文字を超える長い内容
        operation_info = OperationInfo(
            operation_type=OperationType.CREATE_FILE,
            target="test.py",
            description="テスト",
            risk_level=RiskLevel.HIGH_RISK,
            details={"content": long_content}
        )
        
        details = self.ui.format_operation_details(operation_info)
        
        assert "..." in details  # 省略記号が含まれる
        assert len(details) < len(long_content) + 100  # 詳細が短縮されている
    
    def test_format_operation_details_with_command(self):
        """コマンド付きの操作詳細整形のテスト"""
        operation_info = OperationInfo(
            operation_type=OperationType.EXECUTE_PYTHON,
            target="script.py",
            description="Pythonスクリプトを実行",
            risk_level=RiskLevel.HIGH_RISK,
            details={"command": "python script.py --verbose"}
        )
        
        details = self.ui.format_operation_details(operation_info)
        
        assert "python script.py --verbose" in details
        assert "コマンド:" in details
    
    def test_format_operation_details_with_size(self):
        """サイズ付きの操作詳細整形のテスト"""
        operation_info = OperationInfo(
            operation_type=OperationType.CREATE_FILE,
            target="large_file.txt",
            description="大きなファイルを作成",
            risk_level=RiskLevel.HIGH_RISK,
            details={"size": 1024}
        )
        
        details = self.ui.format_operation_details(operation_info)
        
        assert "1024 bytes" in details
        assert "サイズ:" in details
    
    @patch('companion.approval_ui.rich_ui')
    def test_show_risk_warning_low_risk(self, mock_rich_ui):
        """低リスク警告表示のテスト"""
        self.ui.show_risk_warning(RiskLevel.LOW_RISK, "安全な操作")
        
        # 安全メッセージが表示されることを確認
        mock_rich_ui.print_message.assert_called()
        call_args = mock_rich_ui.print_message.call_args_list
        assert any("安全です" in str(call) for call in call_args)
    
    @patch('companion.approval_ui.rich_ui')
    def test_show_risk_warning_high_risk(self, mock_rich_ui):
        """高リスク警告表示のテスト"""
        self.ui.show_risk_warning(RiskLevel.HIGH_RISK, "危険な操作")
        
        # 警告メッセージが表示されることを確認
        mock_rich_ui.print_message.assert_called()
        call_args = mock_rich_ui.print_message.call_args_list
        assert any("変更を加える可能性" in str(call) for call in call_args)
    
    @patch('companion.approval_ui.rich_ui')
    def test_show_risk_warning_critical_risk(self, mock_rich_ui):
        """重要リスク警告表示のテスト"""
        self.ui.show_risk_warning(RiskLevel.CRITICAL_RISK, "重大な操作")
        
        # 重大警告メッセージが表示されることを確認
        mock_rich_ui.print_message.assert_called()
        call_args = mock_rich_ui.print_message.call_args_list
        assert any("重大な影響" in str(call) for call in call_args)
        assert any("システムファイルの破損" in str(call) for call in call_args)
    
    @patch('companion.approval_ui.rich_ui')
    def test_show_preview(self, mock_rich_ui):
        """プレビュー表示のテスト"""
        preview_content = "print('Hello, World!')"
        
        self.ui._show_preview(preview_content)
        
        # プレビューパネルが表示されることを確認
        mock_rich_ui.print_panel.assert_called_once()
        call_args = mock_rich_ui.print_panel.call_args
        assert preview_content in call_args[0][0]  # 最初の引数（content）
        assert "プレビュー" in call_args[0][1]  # 2番目の引数（title）
    
    @patch('companion.approval_ui.rich_ui')
    def test_get_user_response_approved(self, mock_rich_ui):
        """ユーザー応答取得（承認）のテスト"""
        mock_rich_ui.get_confirmation.return_value = True
        
        response = self.ui._get_user_response()
        
        assert response is True
        mock_rich_ui.get_confirmation.assert_called_once()
    
    @patch('companion.approval_ui.rich_ui')
    def test_get_user_response_rejected(self, mock_rich_ui):
        """ユーザー応答取得（拒否）のテスト"""
        mock_rich_ui.get_confirmation.return_value = False
        
        response = self.ui._get_user_response()
        
        assert response is False
        mock_rich_ui.get_confirmation.assert_called_once()
    
    @patch('companion.approval_ui.rich_ui')
    def test_get_user_response_keyboard_interrupt(self, mock_rich_ui):
        """ユーザー応答取得（キーボード割り込み）のテスト"""
        mock_rich_ui.get_confirmation.side_effect = KeyboardInterrupt()
        
        response = self.ui._get_user_response()
        
        assert response is False
    
    @patch('companion.approval_ui.rich_ui')
    def test_get_user_response_with_error_retry(self, mock_rich_ui):
        """ユーザー応答取得（エラー後リトライ）のテスト"""
        # 最初はエラー、2回目は成功
        mock_rich_ui.get_confirmation.side_effect = [Exception("入力エラー"), True]
        
        response = self.ui._get_user_response()
        
        assert response is True
        assert mock_rich_ui.get_confirmation.call_count == 2
        mock_rich_ui.print_error.assert_called_once()
    
    def test_format_risk_level_all_levels(self):
        """全リスクレベルの整形テスト"""
        # 低リスク
        formatted = self.ui._format_risk_level(RiskLevel.LOW_RISK)
        assert "🟢" in formatted
        assert "低リスク" in formatted
        
        # 高リスク
        formatted = self.ui._format_risk_level(RiskLevel.HIGH_RISK)
        assert "🟡" in formatted
        assert "高リスク" in formatted
        
        # 重要リスク
        formatted = self.ui._format_risk_level(RiskLevel.CRITICAL_RISK)
        assert "🔴" in formatted
        assert "重要リスク" in formatted
    
    @patch('companion.approval_ui.rich_ui')
    def test_show_approval_summary(self, mock_rich_ui):
        """承認サマリー表示のテスト"""
        self.ui.show_approval_summary(
            approved_count=3,
            rejected_count=2,
            total_time=45.5
        )
        
        # サマリーパネルが表示されることを確認
        mock_rich_ui.print_panel.assert_called_once()
        call_args = mock_rich_ui.print_panel.call_args
        summary_content = call_args[0][0]
        
        assert "総操作数: 5" in summary_content
        assert "承認: 3" in summary_content
        assert "拒否: 2" in summary_content
        assert "45.5秒" in summary_content
        assert "60.0%" in summary_content  # 3/5 * 100
    
    @patch('companion.approval_ui.rich_ui')
    def test_show_approval_summary_no_operations(self, mock_rich_ui):
        """操作なしの承認サマリー表示のテスト"""
        self.ui.show_approval_summary(
            approved_count=0,
            rejected_count=0,
            total_time=0.0
        )
        
        # 操作がない場合は何も表示されない
        mock_rich_ui.print_panel.assert_not_called()
    
    @patch('companion.approval_ui.rich_ui')
    def test_show_bypass_warning(self, mock_rich_ui):
        """バイパス警告表示のテスト"""
        self.ui.show_bypass_warning(attempt_count=2, max_attempts=3)
        
        # バイパス警告パネルが表示されることを確認
        mock_rich_ui.print_panel.assert_called_once()
        call_args = mock_rich_ui.print_panel.call_args
        warning_content = call_args[0][0]
        
        assert "バイパス試行を検出" in warning_content
        assert "2/3" in warning_content
        assert "残り試行回数: 1" in warning_content
    
    @patch('companion.approval_ui.rich_ui')
    def test_show_timeout_warning(self, mock_rich_ui):
        """タイムアウト警告表示のテスト"""
        self.ui.show_timeout_warning(timeout_seconds=30)
        
        # タイムアウト警告パネルが表示されることを確認
        mock_rich_ui.print_panel.assert_called_once()
        call_args = mock_rich_ui.print_panel.call_args
        warning_content = call_args[0][0]
        
        assert "30 秒でタイムアウト" in warning_content
        assert "自動的に拒否" in warning_content
    
    @patch('companion.approval_ui.rich_ui')
    def test_show_error_message_basic(self, mock_rich_ui):
        """基本的なエラーメッセージ表示のテスト"""
        error_msg = "テストエラー"
        
        self.ui.show_error_message(error_msg)
        
        # エラーメッセージが表示されることを確認
        mock_rich_ui.print_message.assert_called()
        call_args = mock_rich_ui.print_message.call_args_list
        
        # 相棒らしいメッセージが含まれることを確認
        assert any("うまくいかなかった" in str(call) for call in call_args)
        assert any(error_msg in str(call) for call in call_args)
        assert any("もう一度試してみましょう" in str(call) for call in call_args)
    
    @patch('companion.approval_ui.rich_ui')
    def test_show_error_message_with_suggestion(self, mock_rich_ui):
        """提案付きエラーメッセージ表示のテスト"""
        error_msg = "テストエラー"
        suggestion = "別の方法を試してください"
        
        self.ui.show_error_message(error_msg, suggestion)
        
        # エラーメッセージと提案が表示されることを確認
        mock_rich_ui.print_message.assert_called()
        call_args = mock_rich_ui.print_message.call_args_list
        
        assert any(error_msg in str(call) for call in call_args)
        assert any(suggestion in str(call) for call in call_args)
    
    @patch('companion.approval_ui.rich_ui')
    @patch('companion.approval_ui.time.sleep')  # sleepをモックして高速化
    def test_show_approval_request_with_preview(self, mock_sleep, mock_rich_ui):
        """プレビュー付き承認要求のテスト"""
        mock_rich_ui.get_confirmation.return_value = True
        
        # プレビュー付きの操作情報
        operation_info_with_preview = OperationInfo(
            operation_type=OperationType.CREATE_FILE,
            target="test.py",
            description="ファイル作成",
            risk_level=RiskLevel.HIGH_RISK,
            details={},
            preview="print('Hello, World!')"
        )
        
        request_with_preview = ApprovalRequest(
            operation_info=operation_info_with_preview,
            message="テスト",
            timestamp=datetime.now(),
            session_id="test"
        )
        
        response = self.ui.show_approval_request(request_with_preview)
        
        assert response.approved is True
        
        # プレビューパネルが表示されたことを確認
        panel_calls = [call for call in mock_rich_ui.print_panel.call_args_list 
                      if "プレビュー" in str(call)]
        assert len(panel_calls) > 0
    
    @patch('companion.approval_ui.rich_ui')
    @patch('companion.approval_ui.time.sleep')
    def test_show_approval_request_no_preview(self, mock_sleep, mock_rich_ui):
        """プレビューなし承認要求のテスト"""
        mock_rich_ui.get_confirmation.return_value = True
        
        # プレビューなしの操作情報
        operation_info_no_preview = OperationInfo(
            operation_type=OperationType.READ_FILE,
            target="test.txt",
            description="ファイル読み取り",
            risk_level=RiskLevel.LOW_RISK,
            details={}
        )
        
        request_no_preview = ApprovalRequest(
            operation_info=operation_info_no_preview,
            message="テスト",
            timestamp=datetime.now(),
            session_id="test"
        )
        
        response = self.ui.show_approval_request(request_no_preview)
        
        assert response.approved is True
        
        # プレビューパネルが表示されていないことを確認
        panel_calls = [call for call in mock_rich_ui.print_panel.call_args_list 
                      if "プレビュー" in str(call)]
        assert len(panel_calls) == 0