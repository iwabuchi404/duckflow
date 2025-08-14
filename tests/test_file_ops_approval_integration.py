"""
Test suite for SimpleFileOps approval system integration
SimpleFileOpsの承認システム統合テスト
"""

import pytest
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from companion.file_ops import SimpleFileOps, FileOperationError
from companion.approval_system import (
    ApprovalGate, ApprovalConfig, ApprovalMode, RiskLevel,
    OperationType, ApprovalResponse
)


class TestSimpleFileOpsApprovalIntegration:
    """SimpleFileOpsの承認システム統合テスト"""
    
    def setup_method(self):
        """各テストメソッドの前に実行される初期化"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "test.txt")
        
        # モック承認ゲートを作成
        self.mock_approval_gate = Mock(spec=ApprovalGate)
        self.file_ops = SimpleFileOps(approval_gate=self.mock_approval_gate)
        
        # rich_uiをモック化
        self.rich_ui_patcher = patch('companion.file_ops.rich_ui')
        self.mock_rich_ui = self.rich_ui_patcher.start()
        
        # timeをモック化（テスト高速化）
        self.time_patcher = patch('companion.file_ops.time')
        self.mock_time = self.time_patcher.start()
    
    def teardown_method(self):
        """各テストメソッドの後に実行されるクリーンアップ"""
        self.rich_ui_patcher.stop()
        self.time_patcher.stop()
        
        # テンポラリファイルをクリーンアップ
        if os.path.exists(self.test_file):
            os.remove(self.test_file)
        os.rmdir(self.temp_dir)
    
    def test_initialization_with_approval_gate(self):
        """承認ゲート付き初期化のテスト"""
        gate = ApprovalGate()
        file_ops = SimpleFileOps(approval_gate=gate)
        
        assert file_ops.approval_gate == gate
    
    def test_initialization_without_approval_gate(self):
        """承認ゲートなし初期化のテスト"""
        file_ops = SimpleFileOps()
        
        assert file_ops.approval_gate is not None
        assert isinstance(file_ops.approval_gate, ApprovalGate)
    
    def test_create_file_with_approval_granted(self):
        """ファイル作成（承認あり）のテスト"""
        # 承認ゲートが承認を返すようにモック
        mock_response = ApprovalResponse(approved=True)
        self.mock_approval_gate.request_approval.return_value = mock_response
        self.mock_approval_gate.is_approval_required.return_value = True
        
        result = self.file_ops.create_file(self.test_file, "test content")
        
        assert result["success"] is True
        assert result["path"] == self.test_file
        assert os.path.exists(self.test_file)
        
        # 承認が要求されたことを確認
        self.mock_approval_gate.request_approval.assert_called_once()
        
        # ファイル内容を確認
        with open(self.test_file, 'r') as f:
            assert f.read() == "test content"
    
    def test_create_file_with_approval_denied(self):
        """ファイル作成（承認拒否）のテスト"""
        # 承認ゲートが拒否を返すようにモック
        mock_response = ApprovalResponse(approved=False, reason="ユーザー拒否")
        self.mock_approval_gate.request_approval.return_value = mock_response
        self.mock_approval_gate.is_approval_required.return_value = True
        
        result = self.file_ops.create_file(self.test_file, "test content")
        
        assert result["success"] is False
        assert result["reason"] == "approval_denied"
        assert not os.path.exists(self.test_file)
        
        # 承認が要求されたことを確認
        self.mock_approval_gate.request_approval.assert_called_once()
        
        # 拒否メッセージが表示されることを確認
        warning_calls = [call for call in self.mock_rich_ui.print_message.call_args_list 
                        if "拒否されました" in str(call)]
        assert len(warning_calls) > 0
    
    def test_create_file_with_approval_not_required(self):
        """ファイル作成（承認不要）のテスト"""
        # 承認が不要な場合
        self.mock_approval_gate.is_approval_required.return_value = False
        
        result = self.file_ops.create_file(self.test_file, "test content")
        
        assert result["success"] is True
        assert os.path.exists(self.test_file)
        
        # 承認要求は呼ばれない
        self.mock_approval_gate.request_approval.assert_not_called()
    
    def test_create_file_with_approval_error(self):
        """ファイル作成（承認エラー）のテスト"""
        # 承認処理でエラーが発生
        self.mock_approval_gate.is_approval_required.return_value = True
        self.mock_approval_gate.request_approval.side_effect = Exception("承認エラー")
        
        result = self.file_ops.create_file(self.test_file, "test content")
        
        assert result["success"] is False
        assert result["reason"] == "approval_denied"
        assert not os.path.exists(self.test_file)
        
        # エラーメッセージが表示されることを確認
        self.mock_rich_ui.print_error.assert_called()
    
    def test_write_file_new_file_with_approval(self):
        """新規ファイル書き込み（承認あり）のテスト"""
        # 承認ゲートが承認を返すようにモック
        mock_response = ApprovalResponse(approved=True)
        self.mock_approval_gate.request_approval.return_value = mock_response
        self.mock_approval_gate.is_approval_required.return_value = True
        
        result = self.file_ops.write_file(self.test_file, "new content")
        
        assert result["success"] is True
        assert os.path.exists(self.test_file)
        
        # 承認が要求されたことを確認
        self.mock_approval_gate.request_approval.assert_called_once()
        
        # ファイル内容を確認
        with open(self.test_file, 'r') as f:
            assert f.read() == "new content"
    
    def test_write_file_existing_file_with_approval(self):
        """既存ファイル書き込み（承認あり）のテスト"""
        # 既存ファイルを作成
        with open(self.test_file, 'w') as f:
            f.write("original content")
        
        # 承認ゲートが承認を返すようにモック
        mock_response = ApprovalResponse(approved=True)
        self.mock_approval_gate.request_approval.return_value = mock_response
        self.mock_approval_gate.is_approval_required.return_value = True
        
        result = self.file_ops.write_file(self.test_file, "updated content")
        
        assert result["success"] is True
        
        # ファイル内容が更新されたことを確認
        with open(self.test_file, 'r') as f:
            assert f.read() == "updated content"
    
    def test_write_file_with_approval_denied(self):
        """ファイル書き込み（承認拒否）のテスト"""
        # 承認ゲートが拒否を返すようにモック
        mock_response = ApprovalResponse(approved=False, reason="ユーザー拒否")
        self.mock_approval_gate.request_approval.return_value = mock_response
        self.mock_approval_gate.is_approval_required.return_value = True
        
        result = self.file_ops.write_file(self.test_file, "test content")
        
        assert result["success"] is False
        assert result["reason"] == "approval_denied"
        assert not os.path.exists(self.test_file)
    
    def test_read_file_bypasses_approval(self):
        """ファイル読み取りが承認をバイパスすることのテスト"""
        # テストファイルを作成
        with open(self.test_file, 'w') as f:
            f.write("test content")
        
        content = self.file_ops.read_file(self.test_file)
        
        assert content == "test content"
        
        # 承認は要求されない
        self.mock_approval_gate.request_approval.assert_not_called()
        self.mock_approval_gate.is_approval_required.assert_not_called()
    
    def test_list_files_bypasses_approval(self):
        """ファイル一覧が承認をバイパスすることのテスト"""
        # テストファイルを作成
        with open(self.test_file, 'w') as f:
            f.write("test content")
        
        files = self.file_ops.list_files(self.temp_dir)
        
        assert len(files) > 0
        assert any(f["name"] == "test.txt" for f in files)
        
        # 承認は要求されない
        self.mock_approval_gate.request_approval.assert_not_called()
        self.mock_approval_gate.is_approval_required.assert_not_called()
    
    def test_request_approval_helper_method(self):
        """_request_approvalヘルパーメソッドのテスト"""
        # 承認が必要で、承認される場合
        self.mock_approval_gate.is_approval_required.return_value = True
        mock_response = ApprovalResponse(approved=True)
        self.mock_approval_gate.request_approval.return_value = mock_response
        
        result = self.file_ops._request_approval(
            operation_type=OperationType.CREATE_FILE,
            target="test.txt",
            description="テストファイル作成",
            risk_level=RiskLevel.HIGH_RISK,
            details={"test": "data"}
        )
        
        assert result is True
        self.mock_approval_gate.is_approval_required.assert_called_once()
        self.mock_approval_gate.request_approval.assert_called_once()
    
    def test_request_approval_not_required(self):
        """承認不要の場合のテスト"""
        # 承認が不要な場合
        self.mock_approval_gate.is_approval_required.return_value = False
        
        result = self.file_ops._request_approval(
            operation_type=OperationType.CREATE_FILE,
            target="test.txt",
            description="テストファイル作成",
            risk_level=RiskLevel.LOW_RISK,
            details={"test": "data"}
        )
        
        assert result is True
        self.mock_approval_gate.is_approval_required.assert_called_once()
        self.mock_approval_gate.request_approval.assert_not_called()
    
    def test_request_approval_with_exception(self):
        """承認処理での例外のテスト"""
        # 承認処理で例外が発生
        self.mock_approval_gate.is_approval_required.side_effect = Exception("テストエラー")
        
        result = self.file_ops._request_approval(
            operation_type=OperationType.CREATE_FILE,
            target="test.txt",
            description="テストファイル作成",
            risk_level=RiskLevel.HIGH_RISK,
            details={"test": "data"}
        )
        
        assert result is False
        self.mock_rich_ui.print_error.assert_called()


class TestSimpleFileOpsApprovalModes:
    """SimpleFileOpsの承認モード別テスト"""
    
    def setup_method(self):
        """各テストメソッドの前に実行される初期化"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "test.txt")
        
        # rich_uiをモック化
        self.rich_ui_patcher = patch('companion.file_ops.rich_ui')
        self.mock_rich_ui = self.rich_ui_patcher.start()
        
        # timeをモック化
        self.time_patcher = patch('companion.file_ops.time')
        self.mock_time = self.time_patcher.start()
    
    def teardown_method(self):
        """各テストメソッドの後に実行されるクリーンアップ"""
        self.rich_ui_patcher.stop()
        self.time_patcher.stop()
        
        if os.path.exists(self.test_file):
            os.remove(self.test_file)
        os.rmdir(self.temp_dir)
    
    def test_strict_mode_requires_approval(self):
        """STRICTモードで承認が必要なことのテスト"""
        config = ApprovalConfig(mode=ApprovalMode.STRICT)
        gate = ApprovalGate(config=config)
        file_ops = SimpleFileOps(approval_gate=gate)
        
        # UIをモック化して承認を自動で拒否
        with patch.object(gate, 'approval_ui') as mock_ui:
            mock_ui.show_approval_request.return_value = ApprovalResponse(approved=False)
            
            result = file_ops.create_file(self.test_file, "test")
            
            assert result["success"] is False
            assert not os.path.exists(self.test_file)
    
    def test_trusted_mode_bypasses_high_risk(self):
        """TRUSTEDモードで高リスク操作がバイパスされることのテスト"""
        config = ApprovalConfig(mode=ApprovalMode.TRUSTED)
        gate = ApprovalGate(config=config)
        file_ops = SimpleFileOps(approval_gate=gate)
        
        result = file_ops.create_file(self.test_file, "test")
        
        assert result["success"] is True
        assert os.path.exists(self.test_file)
    
    def test_excluded_path_bypasses_approval(self):
        """除外パスで承認がバイパスされることのテスト"""
        config = ApprovalConfig(
            mode=ApprovalMode.STRICT,
            excluded_paths=[self.temp_dir]
        )
        gate = ApprovalGate(config=config)
        file_ops = SimpleFileOps(approval_gate=gate)
        
        result = file_ops.create_file(self.test_file, "test")
        
        assert result["success"] is True
        assert os.path.exists(self.test_file)
    
    def test_excluded_extension_bypasses_approval(self):
        """除外拡張子で承認がバイパスされることのテスト"""
        config = ApprovalConfig(
            mode=ApprovalMode.STRICT,
            excluded_extensions=[".txt"]
        )
        gate = ApprovalGate(config=config)
        file_ops = SimpleFileOps(approval_gate=gate)
        
        result = file_ops.create_file(self.test_file, "test")
        
        assert result["success"] is True
        assert os.path.exists(self.test_file)


class TestSimpleFileOpsApprovalIntegrationEnd2End:
    """SimpleFileOpsの承認システム統合エンドツーエンドテスト"""
    
    def setup_method(self):
        """各テストメソッドの前に実行される初期化"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "test.txt")
        
        # rich_uiをモック化
        self.rich_ui_patcher = patch('companion.file_ops.rich_ui')
        self.mock_rich_ui = self.rich_ui_patcher.start()
        
        # timeをモック化
        self.time_patcher = patch('companion.file_ops.time')
        self.mock_time = self.time_patcher.start()
    
    def teardown_method(self):
        """各テストメソッドの後に実行されるクリーンアップ"""
        self.rich_ui_patcher.stop()
        self.time_patcher.stop()
        
        if os.path.exists(self.test_file):
            os.remove(self.test_file)
        os.rmdir(self.temp_dir)
    
    def test_complete_file_operation_workflow(self):
        """完全なファイル操作ワークフローのテスト"""
        # 標準モードの承認ゲート
        config = ApprovalConfig(mode=ApprovalMode.STANDARD)
        gate = ApprovalGate(config=config)
        file_ops = SimpleFileOps(approval_gate=gate)
        
        # 承認UIをモック化して自動承認
        with patch.object(gate, 'approval_ui') as mock_ui:
            mock_ui.show_approval_request.return_value = ApprovalResponse(approved=True)
            
            # 1. ファイル作成（承認必要）
            create_result = file_ops.create_file(self.test_file, "initial content")
            assert create_result["success"] is True
            assert os.path.exists(self.test_file)
            
            # 2. ファイル読み取り（承認不要）
            content = file_ops.read_file(self.test_file)
            assert content == "initial content"
            
            # 3. ファイル更新（承認必要）
            write_result = file_ops.write_file(self.test_file, "updated content")
            assert write_result["success"] is True
            
            # 4. 更新内容を確認
            updated_content = file_ops.read_file(self.test_file)
            assert updated_content == "updated content"
            
            # 5. ディレクトリ一覧（承認不要）
            files = file_ops.list_files(self.temp_dir)
            assert len(files) > 0
            assert any(f["name"] == "test.txt" for f in files)
    
    def test_mixed_approval_responses(self):
        """承認・拒否が混在する場合のテスト"""
        config = ApprovalConfig(mode=ApprovalMode.STANDARD)
        gate = ApprovalGate(config=config)
        file_ops = SimpleFileOps(approval_gate=gate)
        
        # 承認UIをモック化
        with patch.object(gate, 'approval_ui') as mock_ui:
            # 最初は拒否、次は承認
            mock_ui.show_approval_request.side_effect = [
                ApprovalResponse(approved=False, reason="ユーザー拒否"),
                ApprovalResponse(approved=True)
            ]
            
            # 1. ファイル作成（拒否）
            create_result1 = file_ops.create_file(self.test_file, "content1")
            assert create_result1["success"] is False
            assert not os.path.exists(self.test_file)
            
            # 2. ファイル作成（承認）
            create_result2 = file_ops.create_file(self.test_file, "content2")
            assert create_result2["success"] is True
            assert os.path.exists(self.test_file)
            
            # ファイル内容を確認
            content = file_ops.read_file(self.test_file)
            assert content == "content2"