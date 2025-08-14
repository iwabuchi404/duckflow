"""
Test suite for ApprovalResponseHandler class
ApprovalResponseHandlerクラスのテスト
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from concurrent.futures import TimeoutError as FutureTimeoutError

from companion.approval_response_handler import ApprovalResponseHandler
from companion.approval_ui import UserApprovalUI
from companion.approval_system import (
    ApprovalRequest, ApprovalResponse, OperationInfo, RiskLevel, OperationType,
    ApprovalTimeoutError, ApprovalUIError
)


class TestApprovalResponseHandler:
    """ApprovalResponseHandlerクラスのテスト"""
    
    def setup_method(self):
        """各テストメソッドの前に実行される初期化"""
        self.mock_ui = Mock(spec=UserApprovalUI)
        self.handler = ApprovalResponseHandler(self.mock_ui, timeout_seconds=5)
        
        # テスト用の操作情報
        self.operation_info = OperationInfo(
            operation_type=OperationType.CREATE_FILE,
            target="test.py",
            description="ファイル 'test.py' を作成",
            risk_level=RiskLevel.HIGH_RISK,
            details={"content": "print('hello')"}
        )
        
        # テスト用の承認要求
        self.approval_request = ApprovalRequest(
            operation_info=self.operation_info,
            message="テスト承認要求",
            timestamp=datetime.now(),
            session_id="test_session"
        )
    
    def teardown_method(self):
        """各テストメソッドの後に実行されるクリーンアップ"""
        self.handler.cleanup()
    
    def test_initialization(self):
        """初期化のテスト"""
        handler = ApprovalResponseHandler(self.mock_ui, timeout_seconds=10)
        
        assert handler.ui == self.mock_ui
        assert handler.default_timeout == 10
        assert handler.executor is not None
        assert len(handler.alternative_generators) > 0
        
        handler.cleanup()
    
    def test_initialization_default_timeout(self):
        """デフォルトタイムアウトでの初期化テスト"""
        handler = ApprovalResponseHandler(self.mock_ui)
        
        assert handler.default_timeout == 30
        handler.cleanup()
    
    @patch('companion.approval_response_handler.rich_ui')
    def test_handle_approval_with_timeout_success(self, mock_rich_ui):
        """タイムアウト付き承認処理（成功）のテスト"""
        # UIが正常に応答を返すようにモック
        expected_response = ApprovalResponse(approved=True)
        self.mock_ui.show_approval_request.return_value = expected_response
        
        response = self.handler.handle_approval_with_timeout(self.approval_request, timeout_seconds=1)
        
        assert response == expected_response
        self.mock_ui.show_approval_request.assert_called_once_with(self.approval_request)
    
    @patch('companion.approval_response_handler.rich_ui')
    def test_handle_approval_with_timeout_long_timeout_warning(self, mock_rich_ui):
        """長時間タイムアウトでの警告表示テスト"""
        expected_response = ApprovalResponse(approved=True)
        self.mock_ui.show_approval_request.return_value = expected_response
        
        # 長時間タイムアウト（60秒超）
        response = self.handler.handle_approval_with_timeout(self.approval_request, timeout_seconds=120)
        
        assert response == expected_response
        # タイムアウト警告が表示されることを確認
        self.mock_ui.show_timeout_warning.assert_called_once_with(120)
    
    def test_handle_approval_with_timeout_timeout_error(self):
        """タイムアウトエラーのテスト"""
        # UIが長時間応答しないようにモック
        def slow_response(request):
            import time
            time.sleep(2)  # タイムアウト時間（1秒）より長く待機
            return ApprovalResponse(approved=True)
        
        self.mock_ui.show_approval_request.side_effect = slow_response
        
        with pytest.raises(ApprovalTimeoutError, match="承認要求がタイムアウトしました"):
            self.handler.handle_approval_with_timeout(self.approval_request, timeout_seconds=1)
    
    def test_handle_approval_with_timeout_ui_error(self):
        """UI関連エラーのテスト"""
        # UIがエラーを発生させるようにモック
        self.mock_ui.show_approval_request.side_effect = Exception("UI エラー")
        
        with pytest.raises(ApprovalUIError, match="承認処理中にエラーが発生しました"):
            self.handler.handle_approval_with_timeout(self.approval_request)
    
    @patch('companion.approval_response_handler.rich_ui')
    def test_handle_rejection_with_alternatives_file_creation(self, mock_rich_ui):
        """ファイル作成拒否時の代替案提案テスト"""
        # ユーザーが代替案を選択しないようにモック
        mock_rich_ui.get_user_input.return_value = ""
        
        response = self.handler.handle_rejection_with_alternatives(
            self.approval_request, 
            "ユーザー拒否"
        )
        
        assert response.approved is False
        assert response.alternative_suggested is True
        assert "分かりました" in response.reason or "承知しました" in response.reason
        
        # 理解メッセージが表示されることを確認
        mock_rich_ui.print_message.assert_called()
    
    @patch('companion.approval_response_handler.rich_ui')
    def test_handle_rejection_with_alternatives_selection(self, mock_rich_ui):
        """代替案選択のテスト"""
        # ユーザーが最初の代替案を選択
        mock_rich_ui.get_user_input.return_value = "1"
        
        response = self.handler.handle_rejection_with_alternatives(
            self.approval_request,
            "ユーザー拒否"
        )
        
        assert response.approved is False
        assert response.alternative_suggested is True
        assert "代替案:" in response.reason
    
    @patch('companion.approval_response_handler.rich_ui')
    def test_handle_rejection_with_alternatives_invalid_selection(self, mock_rich_ui):
        """無効な代替案選択のテスト"""
        # ユーザーが無効な番号を入力
        mock_rich_ui.get_user_input.return_value = "999"
        
        response = self.handler.handle_rejection_with_alternatives(
            self.approval_request,
            "ユーザー拒否"
        )
        
        assert response.approved is False
        # 無効な番号の警告が表示されることを確認
        warning_calls = [call for call in mock_rich_ui.print_message.call_args_list 
                        if "無効な番号" in str(call)]
        assert len(warning_calls) > 0
    
    @patch('companion.approval_response_handler.rich_ui')
    def test_handle_rejection_with_alternatives_error(self, mock_rich_ui):
        """代替案処理エラーのテスト"""
        # get_user_inputでエラーを発生させる
        mock_rich_ui.get_user_input.side_effect = Exception("入力エラー")
        
        response = self.handler.handle_rejection_with_alternatives(
            self.approval_request,
            "ユーザー拒否"
        )
        
        assert response.approved is False
        # エラー時は通常の拒否メッセージが返される
        assert response.approved is False
        assert "分かりました" in response.reason or "承知しました" in response.reason
    
    @patch('companion.approval_response_handler.rich_ui')
    def test_create_confirmation_dialog_standard(self, mock_rich_ui):
        """標準確認ダイアログのテスト"""
        mock_rich_ui.get_confirmation.return_value = True
        
        result = self.handler.create_confirmation_dialog(
            "テストメッセージ",
            RiskLevel.LOW_RISK,
            {"key": "value"}
        )
        
        assert result is True
        mock_rich_ui.print_message.assert_called()
        mock_rich_ui.get_confirmation.assert_called_once()
    
    @patch('companion.approval_response_handler.rich_ui')
    def test_create_confirmation_dialog_high_risk(self, mock_rich_ui):
        """高リスク確認ダイアログのテスト"""
        # 2段階確認で両方ともTrue
        mock_rich_ui.get_confirmation.side_effect = [True, True]
        
        result = self.handler.create_confirmation_dialog(
            "高リスク操作",
            RiskLevel.HIGH_RISK
        )
        
        assert result is True
        assert mock_rich_ui.get_confirmation.call_count == 2
    
    @patch('companion.approval_response_handler.rich_ui')
    def test_create_confirmation_dialog_high_risk_first_rejection(self, mock_rich_ui):
        """高リスク確認ダイアログ（第1段階拒否）のテスト"""
        # 第1段階で拒否
        mock_rich_ui.get_confirmation.side_effect = [False]
        
        result = self.handler.create_confirmation_dialog(
            "高リスク操作",
            RiskLevel.HIGH_RISK
        )
        
        assert result is False
        assert mock_rich_ui.get_confirmation.call_count == 1
    
    @patch('companion.approval_response_handler.rich_ui')
    def test_create_confirmation_dialog_critical_risk(self, mock_rich_ui):
        """重要リスク確認ダイアログのテスト"""
        # 3段階確認で全てTrue
        mock_rich_ui.get_confirmation.side_effect = [True, True, True]
        
        result = self.handler.create_confirmation_dialog(
            "重要リスク操作",
            RiskLevel.CRITICAL_RISK
        )
        
        assert result is True
        assert mock_rich_ui.get_confirmation.call_count == 3
    
    @patch('companion.approval_response_handler.rich_ui')
    def test_create_confirmation_dialog_critical_risk_second_rejection(self, mock_rich_ui):
        """重要リスク確認ダイアログ（第2段階拒否）のテスト"""
        # 第1段階は承認、第2段階で拒否
        mock_rich_ui.get_confirmation.side_effect = [True, False]
        
        result = self.handler.create_confirmation_dialog(
            "重要リスク操作",
            RiskLevel.CRITICAL_RISK
        )
        
        assert result is False
        assert mock_rich_ui.get_confirmation.call_count == 2
    
    @patch('companion.approval_response_handler.rich_ui')
    def test_create_confirmation_dialog_error(self, mock_rich_ui):
        """確認ダイアログエラーのテスト"""
        mock_rich_ui.get_confirmation.side_effect = Exception("確認エラー")
        
        result = self.handler.create_confirmation_dialog(
            "テストメッセージ",
            RiskLevel.LOW_RISK
        )
        
        # エラー時は安全のため拒否
        assert result is False
        mock_rich_ui.print_error.assert_called()
    
    def test_generate_alternatives_file_creation(self):
        """ファイル作成代替案生成のテスト"""
        alternatives = self.handler._generate_alternatives(self.operation_info)
        
        assert len(alternatives) > 0
        assert any("プレビュー" in alt["title"] for alt in alternatives)
        assert any("別の場所" in alt["title"] for alt in alternatives)
    
    def test_generate_alternatives_file_write(self):
        """ファイル書き込み代替案生成のテスト"""
        write_operation = OperationInfo(
            operation_type=OperationType.WRITE_FILE,
            target="test.py",
            description="ファイル書き込み",
            risk_level=RiskLevel.HIGH_RISK,
            details={}
        )
        
        alternatives = self.handler._generate_alternatives(write_operation)
        
        assert len(alternatives) > 0
        assert any("バックアップ" in alt["title"] for alt in alternatives)
        assert any("新しいファイル" in alt["title"] for alt in alternatives)
    
    def test_generate_alternatives_file_delete(self):
        """ファイル削除代替案生成のテスト"""
        delete_operation = OperationInfo(
            operation_type=OperationType.DELETE_FILE,
            target="test.py",
            description="ファイル削除",
            risk_level=RiskLevel.HIGH_RISK,
            details={}
        )
        
        alternatives = self.handler._generate_alternatives(delete_operation)
        
        assert len(alternatives) > 0
        assert any("内容を確認" in alt["title"] for alt in alternatives)
        assert any("移動" in alt["title"] for alt in alternatives)
    
    def test_generate_alternatives_code_execution(self):
        """コード実行代替案生成のテスト"""
        exec_operation = OperationInfo(
            operation_type=OperationType.EXECUTE_PYTHON,
            target="script.py",
            description="Python実行",
            risk_level=RiskLevel.HIGH_RISK,
            details={}
        )
        
        alternatives = self.handler._generate_alternatives(exec_operation)
        
        assert len(alternatives) > 0
        assert any("内容を確認" in alt["title"] for alt in alternatives)
        assert any("構文チェック" in alt["title"] for alt in alternatives)
    
    def test_generate_alternatives_command_execution(self):
        """コマンド実行代替案生成のテスト"""
        cmd_operation = OperationInfo(
            operation_type=OperationType.EXECUTE_COMMAND,
            target="ls -la",
            description="コマンド実行",
            risk_level=RiskLevel.HIGH_RISK,
            details={}
        )
        
        alternatives = self.handler._generate_alternatives(cmd_operation)
        
        assert len(alternatives) > 0
        assert any("説明を表示" in alt["title"] for alt in alternatives)
        assert any("ドライラン" in alt["title"] for alt in alternatives)
    
    def test_generate_alternatives_unknown_operation(self):
        """未知の操作の代替案生成のテスト"""
        unknown_operation = OperationInfo(
            operation_type="unknown_operation",
            target="test",
            description="未知の操作",
            risk_level=RiskLevel.HIGH_RISK,
            details={}
        )
        
        alternatives = self.handler._generate_alternatives(unknown_operation)
        
        # デフォルトの汎用代替案が返される
        assert len(alternatives) > 0
        assert any("情報確認" in alt["title"] for alt in alternatives)
        assert any("別の方法を相談" in alt["title"] for alt in alternatives)
    
    @patch('companion.approval_response_handler.rich_ui')
    def test_present_alternatives(self, mock_rich_ui):
        """代替案提示のテスト"""
        alternatives = [
            {"title": "代替案1", "description": "説明1", "action": "action1"},
            {"title": "代替案2", "description": "説明2", "action": "action2"}
        ]
        
        self.handler._present_alternatives(alternatives)
        
        # 代替案が表示されることを確認
        mock_rich_ui.print_message.assert_called()
        call_args_list = mock_rich_ui.print_message.call_args_list
        
        # 代替案のタイトルと説明が含まれることを確認
        assert any("代替案1" in str(call) for call in call_args_list)
        assert any("代替案2" in str(call) for call in call_args_list)
    
    @patch('companion.approval_response_handler.rich_ui')
    def test_present_alternatives_empty(self, mock_rich_ui):
        """空の代替案提示のテスト"""
        self.handler._present_alternatives([])
        
        # 空の場合は何も表示されない
        mock_rich_ui.print_message.assert_not_called()
    
    @patch('companion.approval_response_handler.rich_ui')
    def test_get_alternative_selection_valid(self, mock_rich_ui):
        """有効な代替案選択のテスト"""
        alternatives = [
            {"title": "代替案1", "description": "説明1", "action": "action1"},
            {"title": "代替案2", "description": "説明2", "action": "action2"}
        ]
        
        mock_rich_ui.get_user_input.return_value = "1"
        
        result = self.handler._get_alternative_selection(alternatives)
        
        assert result == "代替案1"
    
    @patch('companion.approval_response_handler.rich_ui')
    def test_get_alternative_selection_empty_input(self, mock_rich_ui):
        """空入力での代替案選択のテスト"""
        alternatives = [
            {"title": "代替案1", "description": "説明1", "action": "action1"}
        ]
        
        mock_rich_ui.get_user_input.return_value = ""
        
        result = self.handler._get_alternative_selection(alternatives)
        
        assert result is None
    
    @patch('companion.approval_response_handler.rich_ui')
    def test_get_alternative_selection_invalid_number(self, mock_rich_ui):
        """無効な番号での代替案選択のテスト"""
        alternatives = [
            {"title": "代替案1", "description": "説明1", "action": "action1"}
        ]
        
        mock_rich_ui.get_user_input.return_value = "abc"
        
        result = self.handler._get_alternative_selection(alternatives)
        
        assert result is None
        # エラーメッセージが表示されることを確認
        error_calls = [call for call in mock_rich_ui.print_message.call_args_list 
                      if "数字を入力" in str(call)]
        assert len(error_calls) > 0
    
    @patch('companion.approval_response_handler.rich_ui')
    def test_get_alternative_selection_out_of_range(self, mock_rich_ui):
        """範囲外番号での代替案選択のテスト"""
        alternatives = [
            {"title": "代替案1", "description": "説明1", "action": "action1"}
        ]
        
        mock_rich_ui.get_user_input.return_value = "5"  # 範囲外
        
        result = self.handler._get_alternative_selection(alternatives)
        
        assert result is None
        # エラーメッセージが表示されることを確認
        error_calls = [call for call in mock_rich_ui.print_message.call_args_list 
                      if "無効な番号" in str(call)]
        assert len(error_calls) > 0
    
    @patch('companion.approval_response_handler.rich_ui')
    def test_get_alternative_selection_error(self, mock_rich_ui):
        """代替案選択エラーのテスト"""
        alternatives = [
            {"title": "代替案1", "description": "説明1", "action": "action1"}
        ]
        
        mock_rich_ui.get_user_input.side_effect = Exception("入力エラー")
        
        result = self.handler._get_alternative_selection(alternatives)
        
        assert result is None
        mock_rich_ui.print_error.assert_called()
    
    @patch('companion.approval_response_handler.rich_ui')
    def test_handle_timeout(self, mock_rich_ui):
        """タイムアウト処理のテスト"""
        response = self.handler._handle_timeout(self.approval_request, 30)
        
        assert response.approved is False
        assert "30秒" in response.reason
        assert "経過した" in response.reason or "応答がなかった" in response.reason or "停止しました" in response.reason
        
        # タイムアウトメッセージと再試行提案が表示されることを確認
        mock_rich_ui.print_message.assert_called()
        call_args_list = mock_rich_ui.print_message.call_args_list
        
        timeout_calls = [call for call in call_args_list if "タイムアウト" in str(call) or "応答がなかった" in str(call)]
        retry_calls = [call for call in call_args_list if "再度実行" in str(call)]
        
        assert len(timeout_calls) > 0
        assert len(retry_calls) > 0
    
    def test_cleanup(self):
        """クリーンアップのテスト"""
        # executorが存在することを確認
        assert hasattr(self.handler, 'executor')
        
        # クリーンアップを実行
        self.handler.cleanup()
        
        # executorがシャットダウンされることを確認（例外が発生しないことで確認）
        # 実際のシャットダウン状態の確認は困難なため、例外が発生しないことで確認

class TestAdvancedApprovalResponseHandling:
    """高度な承認応答処理のテスト"""
    
    def setup_method(self):
        """各テストメソッドの前に実行される初期化"""
        self.mock_ui = Mock(spec=UserApprovalUI)
        self.handler = ApprovalResponseHandler(self.mock_ui, timeout_seconds=30)
        
        # テスト用の操作情報
        self.create_file_operation = OperationInfo(
            operation_type=OperationType.CREATE_FILE,
            target="test.py",
            description="ファイル 'test.py' を作成",
            risk_level=RiskLevel.HIGH_RISK,
            details={"content": "print('hello')"},
            preview="print('hello')"
        )
        
        self.execute_operation = OperationInfo(
            operation_type=OperationType.EXECUTE_PYTHON,
            target="script.py",
            description="Pythonスクリプトを実行",
            risk_level=RiskLevel.HIGH_RISK,
            details={"command": "python script.py"}
        )
        
        self.delete_operation = OperationInfo(
            operation_type=OperationType.DELETE_FILE,
            target="important.txt",
            description="ファイル 'important.txt' を削除",
            risk_level=RiskLevel.CRITICAL_RISK,
            details={}
        )
    
    def teardown_method(self):
        """各テストメソッドの後に実行されるクリーンアップ"""
        self.handler.cleanup()
    
    @patch('companion.approval_response_handler.rich_ui')
    def test_timeout_with_countdown_display(self, mock_rich_ui):
        """カウントダウン表示付きタイムアウトのテスト"""
        # UIが長時間応答しないようにモック（タイムアウトを発生させる）
        def slow_response(request):
            import time
            time.sleep(10)  # タイムアウト時間より長く待機
            return ApprovalResponse(approved=True)
        
        self.mock_ui.show_approval_request.side_effect = slow_response
        
        approval_request = ApprovalRequest(
            operation_info=self.create_file_operation,
            message="タイムアウトテスト",
            timestamp=datetime.now(),
            session_id="timeout_test"
        )
        
        with pytest.raises(ApprovalTimeoutError):
            self.handler.handle_approval_with_timeout(approval_request, timeout_seconds=1)
        
        # show_approval_requestが呼ばれることを確認
        self.mock_ui.show_approval_request.assert_called_once()
    
    @patch('companion.approval_response_handler.rich_ui')
    def test_confirmation_dialog_with_impact_analysis(self, mock_rich_ui):
        """影響分析付き確認ダイアログのテスト"""
        # 3段階確認で全て承認（CRITICAL_RISKの場合）
        mock_rich_ui.get_confirmation.side_effect = [True, True, True]
        
        result = self.handler.create_confirmation_dialog(
            "重要ファイル削除",
            RiskLevel.CRITICAL_RISK,
            {"show_impact": True}
        )
        
        assert result is True
        # CRITICAL_RISKなので3回確認が呼ばれる
        assert mock_rich_ui.get_confirmation.call_count == 3
    
    @patch('companion.approval_response_handler.rich_ui')
    def test_alternative_selection_with_detailed_options(self, mock_rich_ui):
        """詳細オプション付き代替案選択のテスト"""
        # ユーザーが詳細な代替案を選択
        mock_rich_ui.get_user_input.return_value = "1"
        
        approval_request = ApprovalRequest(
            operation_info=self.execute_operation,
            message="スクリプト実行拒否",
            timestamp=datetime.now(),
            session_id="alternative_test"
        )
        
        response = self.handler.handle_rejection_with_alternatives(
            approval_request,
            "安全性の懸念"
        )
        
        assert response.approved is False
        assert response.alternative_suggested is True
        
        # 代替案の詳細が含まれることを確認
        assert "代替案:" in response.reason
    
    @patch('companion.approval_response_handler.rich_ui')
    def test_multi_step_confirmation_for_critical_operations(self, mock_rich_ui):
        """重要操作の多段階確認テスト"""
        # 3段階確認で全て承認
        mock_rich_ui.get_confirmation.side_effect = [True, True, True]
        
        result = self.handler.create_confirmation_dialog(
            "システム設定ファイル削除",
            RiskLevel.CRITICAL_RISK,
            {
                "warnings": [
                    "この操作は元に戻せません",
                    "システムに重大な影響を与える可能性があります"
                ]
            }
        )
        
        assert result is True
        assert mock_rich_ui.get_confirmation.call_count == 3
        
        # 各段階で適切な警告が表示されることを確認
        warning_calls = [call for call in mock_rich_ui.print_message.call_args_list 
                        if "警告" in str(call) or "注意" in str(call)]
        assert len(warning_calls) > 0
    
    @patch('companion.approval_response_handler.rich_ui')
    def test_rejection_with_reason_analysis(self, mock_rich_ui):
        """理由分析付き拒否処理のテスト"""
        mock_rich_ui.get_user_input.return_value = ""  # 代替案を選択しない
        
        approval_request = ApprovalRequest(
            operation_info=self.create_file_operation,
            message="ファイル作成要求",
            timestamp=datetime.now(),
            session_id="reason_test"
        )
        
        response = self.handler.handle_rejection_with_alternatives(
            approval_request,
            "ファイル名が不適切"
        )
        
        assert response.approved is False
        assert "ファイル名が不適切" in response.reason or "分かりました" in response.reason
        
        # 理解メッセージが表示されることを確認
        understanding_calls = [call for call in mock_rich_ui.print_message.call_args_list 
                             if "分かりました" in str(call) or "承知しました" in str(call)]
        assert len(understanding_calls) > 0
    
    def test_alternative_generation_context_aware(self):
        """コンテキスト対応代替案生成のテスト"""
        # ファイル作成の代替案
        create_alternatives = self.handler._generate_alternatives(self.create_file_operation)
        assert any("プレビュー" in alt["title"] for alt in create_alternatives)
        assert any("別の場所" in alt["title"] for alt in create_alternatives)
        
        # コード実行の代替案
        exec_alternatives = self.handler._generate_alternatives(self.execute_operation)
        assert any("内容を確認" in alt["title"] for alt in exec_alternatives)
        assert any("構文チェック" in alt["title"] for alt in exec_alternatives)
        
        # ファイル削除の代替案
        delete_alternatives = self.handler._generate_alternatives(self.delete_operation)
        assert any("内容を確認" in alt["title"] for alt in delete_alternatives)
        assert any("移動" in alt["title"] for alt in delete_alternatives)
        
        # 各操作タイプで異なる代替案が生成されることを確認
        create_titles = {alt["title"] for alt in create_alternatives}
        exec_titles = {alt["title"] for alt in exec_alternatives}
        delete_titles = {alt["title"] for alt in delete_alternatives}
        
        # 完全に同じではないことを確認（一部重複は許可）
        assert create_titles != exec_titles
        assert exec_titles != delete_titles
        assert create_titles != delete_titles
    
    @patch('companion.approval_response_handler.rich_ui')
    def test_error_recovery_in_alternative_handling(self, mock_rich_ui):
        """代替案処理でのエラー回復テスト"""
        # 最初の入力でエラー、2回目で正常な選択
        mock_rich_ui.get_user_input.side_effect = [
            Exception("一時的なエラー"),
            "1"  # 正常な選択
        ]
        
        approval_request = ApprovalRequest(
            operation_info=self.create_file_operation,
            message="エラー回復テスト",
            timestamp=datetime.now(),
            session_id="error_recovery_test"
        )
        
        response = self.handler.handle_rejection_with_alternatives(
            approval_request,
            "テスト拒否"
        )
        
        # エラーが発生しても適切に処理されることを確認
        assert response.approved is False
        
        # エラーメッセージが表示されることを確認
        error_calls = [call for call in mock_rich_ui.print_error.call_args_list]
        # エラーが発生した場合は通常の拒否処理にフォールバック
        assert len(error_calls) > 0 or "分かりました" in response.reason
    
    @patch('companion.approval_response_handler.rich_ui')
    def test_timeout_with_graceful_degradation(self, mock_rich_ui):
        """タイムアウト時の優雅な劣化テスト"""
        approval_request = ApprovalRequest(
            operation_info=self.execute_operation,
            message="タイムアウト劣化テスト",
            timestamp=datetime.now(),
            session_id="graceful_timeout_test"
        )
        
        response = self.handler._handle_timeout(approval_request, 30)
        
        assert response.approved is False
        assert "30秒" in response.reason
        
        # タイムアウト時の適切なメッセージが含まれることを確認
        assert any(keyword in response.reason for keyword in [
            "経過した", "応答がなかった", "停止しました", "タイムアウト"
        ])
        
        # 再試行の提案が表示されることを確認
        retry_calls = [call for call in mock_rich_ui.print_message.call_args_list 
                      if "再度実行" in str(call) or "もう一度" in str(call)]
        assert len(retry_calls) > 0