"""
Test suite for ApprovalGate configuration management
ApprovalGateの設定管理機能のテスト
"""

import pytest
import os
import tempfile
from unittest.mock import Mock, patch

from companion.approval_system import (
    ApprovalGate, ApprovalConfig, ApprovalMode, RiskLevel,
    OperationInfo, OperationType
)


class TestApprovalGateConfigManagement:
    """ApprovalGateの設定管理機能のテスト"""
    
    def setup_method(self):
        """各テストメソッドの前に実行される初期化"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "test_gate_config.json")
        
        # テスト用の設定
        self.test_config = ApprovalConfig(
            mode=ApprovalMode.STRICT,
            timeout_seconds=45,
            excluded_paths=["/tmp"],
            excluded_extensions=[".tmp"],
            config_file_path=self.config_file
        )
        
        # ApprovalGateインスタンス
        self.gate = ApprovalGate(config=self.test_config)
        
        # テスト用の操作情報
        self.operation_info = OperationInfo(
            operation_type=OperationType.CREATE_FILE,
            target="test.py",
            description="ファイル作成",
            risk_level=RiskLevel.HIGH_RISK,
            details={}
        )
    
    def teardown_method(self):
        """各テストメソッドの後に実行されるクリーンアップ"""
        if os.path.exists(self.config_file):
            os.remove(self.config_file)
        os.rmdir(self.temp_dir)
    
    def test_initialization_with_config(self):
        """設定付き初期化のテスト"""
        gate = ApprovalGate(config=self.test_config)
        
        assert gate.config == self.test_config
        assert gate.config.mode == ApprovalMode.STRICT
        assert gate.config.timeout_seconds == 45
        assert gate._max_bypass_attempts == self.test_config.max_bypass_attempts
    
    def test_initialization_with_default_config(self):
        """デフォルト設定での初期化のテスト"""
        gate = ApprovalGate()
        
        assert gate.config is not None
        assert gate.config.mode == ApprovalMode.STANDARD
        assert gate.config.timeout_seconds == 30
    
    def test_update_config(self):
        """設定更新のテスト"""
        new_config = ApprovalConfig(
            mode=ApprovalMode.TRUSTED,
            timeout_seconds=60,
            max_bypass_attempts=5
        )
        
        self.gate.update_config(new_config)
        
        assert self.gate.config == new_config
        assert self.gate.config.mode == ApprovalMode.TRUSTED
        assert self.gate.config.timeout_seconds == 60
        assert self.gate._max_bypass_attempts == 5
    
    def test_update_config_invalid_type(self):
        """無効な型での設定更新のテスト"""
        with pytest.raises(ValueError, match="ApprovalConfig である必要があります"):
            self.gate.update_config("invalid_config")
    
    def test_get_config(self):
        """設定取得のテスト"""
        config = self.gate.get_config()
        
        assert config == self.test_config
        assert config.mode == ApprovalMode.STRICT
    
    def test_update_approval_mode(self):
        """承認モード更新のテスト"""
        self.gate.update_approval_mode(ApprovalMode.TRUSTED)
        
        assert self.gate.config.mode == ApprovalMode.TRUSTED
    
    def test_add_remove_excluded_path(self):
        """除外パスの追加・削除のテスト"""
        # パス追加
        self.gate.add_excluded_path("/var/log")
        assert "/var/log" in self.gate.config.excluded_paths or os.path.normpath("/var/log") in self.gate.config.excluded_paths
        
        # パス削除
        self.gate.remove_excluded_path("/var/log")
        assert "/var/log" not in self.gate.config.excluded_paths and os.path.normpath("/var/log") not in self.gate.config.excluded_paths
    
    def test_add_remove_excluded_extension(self):
        """除外拡張子の追加・削除のテスト"""
        # 拡張子追加
        self.gate.add_excluded_extension(".log")
        assert ".log" in self.gate.config.excluded_extensions
        
        # 拡張子削除
        self.gate.remove_excluded_extension(".log")
        assert ".log" not in self.gate.config.excluded_extensions
    
    def test_save_and_load_config(self):
        """設定の保存・読み込みのテスト"""
        # 設定を変更
        self.gate.update_approval_mode(ApprovalMode.TRUSTED)
        self.gate.add_excluded_path("/var/log")
        
        # 保存
        self.gate.save_config()
        
        # 新しいゲートインスタンスで読み込み
        new_gate = ApprovalGate()
        new_gate.load_config(self.config_file)
        
        # 設定が正しく読み込まれたことを確認
        assert new_gate.config.mode == ApprovalMode.TRUSTED
        assert os.path.normpath("/var/log") in new_gate.config.excluded_paths
    
    def test_get_config_summary(self):
        """設定概要取得のテスト"""
        summary = self.gate.get_config_summary()
        
        assert summary["mode"] == "strict"
        assert "mode_description" in summary
        assert summary["timeout_seconds"] == 45
        assert summary["excluded_paths_count"] == 1
        assert summary["excluded_extensions_count"] == 1
        assert "show_preview" in summary
        assert "max_bypass_attempts" in summary
    
    def test_is_approval_required_with_config_modes(self):
        """設定モードに基づく承認要求判定のテスト"""
        # STRICTモード
        self.gate.update_approval_mode(ApprovalMode.STRICT)
        assert self.gate.is_approval_required(self.operation_info) is True
        
        # STANDARDモード
        self.gate.update_approval_mode(ApprovalMode.STANDARD)
        assert self.gate.is_approval_required(self.operation_info) is True  # HIGH_RISK
        
        # TRUSTEDモード
        self.gate.update_approval_mode(ApprovalMode.TRUSTED)
        assert self.gate.is_approval_required(self.operation_info) is False  # HIGH_RISK
    
    def test_is_approval_required_with_excluded_paths(self):
        """除外パスでの承認要求判定のテスト"""
        # 除外パスの操作
        excluded_operation = OperationInfo(
            operation_type=OperationType.CREATE_FILE,
            target="/tmp/test.txt",
            description="除外パスでのファイル作成",
            risk_level=RiskLevel.HIGH_RISK,
            details={}
        )
        
        # STRICTモードでも除外パスは承認不要
        self.gate.update_approval_mode(ApprovalMode.STRICT)
        assert self.gate.is_approval_required(excluded_operation) is False
        
        # 通常のパスは承認必要
        normal_operation = OperationInfo(
            operation_type=OperationType.CREATE_FILE,
            target="/home/user/test.txt",
            description="通常パスでのファイル作成",
            risk_level=RiskLevel.HIGH_RISK,
            details={}
        )
        assert self.gate.is_approval_required(normal_operation) is True
    
    def test_is_approval_required_with_excluded_extensions(self):
        """除外拡張子での承認要求判定のテスト"""
        # 除外拡張子の操作
        excluded_operation = OperationInfo(
            operation_type=OperationType.CREATE_FILE,
            target="/home/user/temp.tmp",
            description="除外拡張子でのファイル作成",
            risk_level=RiskLevel.HIGH_RISK,
            details={}
        )
        
        # STRICTモードでも除外拡張子は承認不要
        self.gate.update_approval_mode(ApprovalMode.STRICT)
        assert self.gate.is_approval_required(excluded_operation) is False
    
    def test_runtime_config_changes(self):
        """ランタイム設定変更のテスト"""
        # 初期状態での承認要求
        assert self.gate.is_approval_required(self.operation_info) is True
        
        # モードをTRUSTEDに変更
        self.gate.update_approval_mode(ApprovalMode.TRUSTED)
        assert self.gate.is_approval_required(self.operation_info) is False
        
        # 除外パスを追加
        self.gate.add_excluded_path("/home/user")
        user_operation = OperationInfo(
            operation_type=OperationType.CREATE_FILE,
            target="/home/user/test.txt",
            description="ユーザーディレクトリでのファイル作成",
            risk_level=RiskLevel.HIGH_RISK,
            details={}
        )
        assert self.gate.is_approval_required(user_operation) is False
        
        # 除外パスを削除
        self.gate.remove_excluded_path("/home/user")
        # TRUSTEDモードではHIGH_RISKは承認不要
        assert self.gate.is_approval_required(user_operation) is False
        
        # STRICTモードに戻す
        self.gate.update_approval_mode(ApprovalMode.STRICT)
        assert self.gate.is_approval_required(user_operation) is True


class TestApprovalGateConfigIntegration:
    """ApprovalGate設定管理の統合テスト"""
    
    def setup_method(self):
        """各テストメソッドの前に実行される初期化"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "integration_config.json")
    
    def teardown_method(self):
        """各テストメソッドの後に実行されるクリーンアップ"""
        if os.path.exists(self.config_file):
            os.remove(self.config_file)
        os.rmdir(self.temp_dir)
    
    def test_complete_config_workflow(self):
        """完全な設定ワークフローのテスト"""
        # 1. 初期設定でゲートを作成
        gate = ApprovalGate()
        
        # 2. 設定をカスタマイズ
        gate.update_approval_mode(ApprovalMode.STRICT)
        gate.config.timeout_seconds = 60
        gate.add_excluded_path("/tmp")
        gate.add_excluded_extension(".log")
        gate.config.config_file_path = self.config_file
        
        # 3. 設定を保存
        gate.save_config()
        
        # 4. 新しいゲートインスタンスで設定を読み込み
        new_gate = ApprovalGate()
        new_gate.load_config(self.config_file)
        
        # 5. 設定が正しく復元されたことを確認
        assert new_gate.config.mode == ApprovalMode.STRICT
        assert new_gate.config.timeout_seconds == 60
        assert os.path.normpath("/tmp") in new_gate.config.excluded_paths
        assert ".log" in new_gate.config.excluded_extensions
        
        # 6. 承認判定が正しく動作することを確認
        test_operation = OperationInfo(
            operation_type=OperationType.CREATE_FILE,
            target="/home/test.py",
            description="テストファイル作成",
            risk_level=RiskLevel.HIGH_RISK,
            details={}
        )
        
        excluded_operation = OperationInfo(
            operation_type=OperationType.CREATE_FILE,
            target="/tmp/temp.txt",
            description="除外パスでのファイル作成",
            risk_level=RiskLevel.HIGH_RISK,
            details={}
        )
        
        assert new_gate.is_approval_required(test_operation) is True
        assert new_gate.is_approval_required(excluded_operation) is False
    
    def test_config_persistence_across_mode_changes(self):
        """モード変更の永続化テスト"""
        gate = ApprovalGate()
        gate.config.config_file_path = self.config_file
        
        # 初期設定を保存
        gate.save_config()
        
        # モードを変更して保存
        gate.update_approval_mode(ApprovalMode.TRUSTED)
        gate.save_config()
        
        # 再読み込みして変更が反映されていることを確認
        reloaded_gate = ApprovalGate()
        reloaded_gate.load_config(self.config_file)
        assert reloaded_gate.config.mode == ApprovalMode.TRUSTED
        
        # さらにモードを変更
        reloaded_gate.update_approval_mode(ApprovalMode.STRICT)
        reloaded_gate.add_excluded_path("/var")
        reloaded_gate.save_config()
        
        # 最終確認
        final_gate = ApprovalGate()
        final_gate.load_config(self.config_file)
        assert final_gate.config.mode == ApprovalMode.STRICT
        assert os.path.normpath("/var") in final_gate.config.excluded_paths
    
    def test_config_summary_reflects_current_state(self):
        """設定概要が現在の状態を反映することのテスト"""
        gate = ApprovalGate()
        
        # 初期状態の概要
        initial_summary = gate.get_config_summary()
        assert initial_summary["mode"] == "standard"
        assert initial_summary["excluded_paths_count"] == 0
        
        # 設定を変更
        gate.update_approval_mode(ApprovalMode.STRICT)
        gate.add_excluded_path("/tmp")
        gate.add_excluded_path("/var/log")
        gate.add_excluded_extension(".tmp")
        
        # 変更後の概要
        updated_summary = gate.get_config_summary()
        assert updated_summary["mode"] == "strict"
        assert updated_summary["excluded_paths_count"] == 2
        assert updated_summary["excluded_extensions_count"] == 1
        
        # 設定を削除
        gate.remove_excluded_path("/tmp")
        gate.remove_excluded_extension(".tmp")
        
        # 削除後の概要
        final_summary = gate.get_config_summary()
        assert final_summary["excluded_paths_count"] == 1
        assert final_summary["excluded_extensions_count"] == 0