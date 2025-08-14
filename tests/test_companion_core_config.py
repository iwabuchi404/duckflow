"""
Test suite for CompanionCore approval configuration management
CompanionCoreの承認設定管理機能のテスト
"""

import pytest
import os
import tempfile
from unittest.mock import Mock, patch

from companion.core import CompanionCore
from companion.approval_system import ApprovalMode, ApprovalConfig


class TestCompanionCoreConfigManagement:
    """CompanionCoreの承認設定管理機能のテスト"""
    
    def setup_method(self):
        """各テストメソッドの前に実行される初期化"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "test_companion_config.json")
        
        # rich_uiをモック化
        self.rich_ui_patcher = patch('companion.core.rich_ui')
        self.mock_rich_ui = self.rich_ui_patcher.start()
        
        # CompanionCoreインスタンス
        self.companion = CompanionCore()
        self.companion.approval_gate.config.config_file_path = self.config_file
    
    def teardown_method(self):
        """各テストメソッドの後に実行されるクリーンアップ"""
        self.rich_ui_patcher.stop()
        
        if os.path.exists(self.config_file):
            os.remove(self.config_file)
        os.rmdir(self.temp_dir)
    
    def test_initialization_loads_config(self):
        """初期化時に設定が読み込まれることのテスト"""
        # 設定ファイルを作成
        test_config = ApprovalConfig(
            mode=ApprovalMode.STRICT,
            timeout_seconds=60,
            config_file_path=self.config_file
        )
        test_config.save_to_file()
        
        # 新しいCompanionCoreインスタンスを作成
        with patch('companion.core.rich_ui'):
            new_companion = CompanionCore()
            new_companion.approval_gate.config.config_file_path = self.config_file
            new_companion._load_approval_config()
        
        # 設定が読み込まれていることを確認
        assert new_companion.approval_gate.config.mode == ApprovalMode.STRICT
        assert new_companion.approval_gate.config.timeout_seconds == 60
    
    def test_get_approval_config(self):
        """承認設定取得のテスト"""
        config = self.companion.get_approval_config()
        
        assert isinstance(config, ApprovalConfig)
        assert config.mode == ApprovalMode.STANDARD  # デフォルト
    
    def test_update_approval_mode_success(self):
        """承認モード更新（成功）のテスト"""
        result = self.companion.update_approval_mode(ApprovalMode.STRICT)
        
        assert "strict" in result
        assert "変更しました" in result
        assert self.companion.approval_gate.config.mode == ApprovalMode.STRICT
        
        # 成功メッセージが表示されることを確認
        self.mock_rich_ui.print_message.assert_called()
        call_args = self.mock_rich_ui.print_message.call_args
        assert "success" in str(call_args)
    
    def test_update_approval_mode_with_save_error(self):
        """承認モード更新（保存エラー）のテスト"""
        # save_configでエラーを発生させる
        with patch.object(self.companion.approval_gate, 'save_config', side_effect=Exception("保存エラー")):
            result = self.companion.update_approval_mode(ApprovalMode.TRUSTED)
        
        assert "失敗しました" in result
        assert "保存エラー" in result
        
        # エラーメッセージが表示されることを確認
        self.mock_rich_ui.print_error.assert_called()
    
    def test_add_approval_exclusion_path(self):
        """承認除外パス追加のテスト"""
        result = self.companion.add_approval_exclusion(path="/tmp")
        
        assert "追加しました" in result
        assert "/tmp" in result
        assert os.path.normpath("/tmp") in self.companion.approval_gate.config.excluded_paths
        
        # 成功メッセージが表示されることを確認
        self.mock_rich_ui.print_message.assert_called()
    
    def test_add_approval_exclusion_extension(self):
        """承認除外拡張子追加のテスト"""
        result = self.companion.add_approval_exclusion(extension=".tmp")
        
        assert "追加しました" in result
        assert ".tmp" in result
        assert ".tmp" in self.companion.approval_gate.config.excluded_extensions
    
    def test_add_approval_exclusion_no_params(self):
        """承認除外追加（パラメータなし）のテスト"""
        result = self.companion.add_approval_exclusion()
        
        assert "指定してください" in result
    
    def test_add_approval_exclusion_error(self):
        """承認除外追加（エラー）のテスト"""
        with patch.object(self.companion.approval_gate, 'add_excluded_path', side_effect=Exception("追加エラー")):
            result = self.companion.add_approval_exclusion(path="/tmp")
        
        assert "失敗しました" in result
        assert "追加エラー" in result
        self.mock_rich_ui.print_error.assert_called()
    
    def test_remove_approval_exclusion_path(self):
        """承認除外パス削除のテスト"""
        # まず除外パスを追加
        self.companion.approval_gate.add_excluded_path("/tmp")
        
        result = self.companion.remove_approval_exclusion(path="/tmp")
        
        assert "削除しました" in result
        assert "/tmp" in result
        assert os.path.normpath("/tmp") not in self.companion.approval_gate.config.excluded_paths
    
    def test_remove_approval_exclusion_extension(self):
        """承認除外拡張子削除のテスト"""
        # まず除外拡張子を追加
        self.companion.approval_gate.add_excluded_extension(".tmp")
        
        result = self.companion.remove_approval_exclusion(extension=".tmp")
        
        assert "削除しました" in result
        assert ".tmp" in result
        assert ".tmp" not in self.companion.approval_gate.config.excluded_extensions
    
    def test_show_approval_config(self):
        """承認設定表示のテスト"""
        # 設定をカスタマイズ
        self.companion.approval_gate.update_approval_mode(ApprovalMode.STRICT)
        self.companion.approval_gate.add_excluded_path("/tmp")
        self.companion.approval_gate.add_excluded_extension(".log")
        
        result = self.companion.show_approval_config()
        
        assert "承認システム設定" in result
        assert "strict" in result or "厳格" in result
        assert "/tmp" in result
        assert ".log" in result
        
        # パネル表示が呼ばれることを確認
        self.mock_rich_ui.print_panel.assert_called()
    
    def test_show_approval_config_error(self):
        """承認設定表示（エラー）のテスト"""
        with patch.object(self.companion.approval_gate, 'get_config', side_effect=Exception("設定エラー")):
            result = self.companion.show_approval_config()
        
        assert "失敗しました" in result
        assert "設定エラー" in result
        self.mock_rich_ui.print_error.assert_called()
    
    def test_get_approval_statistics(self):
        """承認統計取得のテスト"""
        # モック統計データ
        mock_stats = {
            "total_requests": 10,
            "approved_count": 7,
            "rejected_count": 3,
            "approval_rate": 70.0,
            "average_response_time": 5.2
        }
        
        with patch.object(self.companion.approval_gate, 'get_approval_statistics', return_value=mock_stats):
            result = self.companion.get_approval_statistics()
        
        assert "承認統計" in result
        assert "10" in result  # total_requests
        assert "7" in result   # approved_count
        assert "3" in result   # rejected_count
        assert "70.0%" in result  # approval_rate
        assert "5.2秒" in result  # average_response_time
        
        # パネル表示が呼ばれることを確認
        self.mock_rich_ui.print_panel.assert_called()
    
    def test_get_approval_statistics_error(self):
        """承認統計取得（エラー）のテスト"""
        with patch.object(self.companion.approval_gate, 'get_approval_statistics', side_effect=Exception("統計エラー")):
            result = self.companion.get_approval_statistics()
        
        assert "失敗しました" in result
        assert "統計エラー" in result
        self.mock_rich_ui.print_error.assert_called()
    
    def test_reset_approval_config(self):
        """承認設定リセットのテスト"""
        # 設定をカスタマイズ
        self.companion.approval_gate.update_approval_mode(ApprovalMode.STRICT)
        self.companion.approval_gate.add_excluded_path("/tmp")
        
        result = self.companion.reset_approval_config()
        
        assert "リセットしました" in result
        assert "標準モード" in result or "standard" in result
        
        # 設定がデフォルトに戻っていることを確認
        assert self.companion.approval_gate.config.mode == ApprovalMode.STANDARD
        assert len(self.companion.approval_gate.config.excluded_paths) == 0
        
        # 成功メッセージが表示されることを確認
        self.mock_rich_ui.print_message.assert_called()
    
    def test_reset_approval_config_error(self):
        """承認設定リセット（エラー）のテスト"""
        with patch.object(self.companion.approval_gate, 'save_config', side_effect=Exception("保存エラー")):
            result = self.companion.reset_approval_config()
        
        assert "失敗しました" in result
        assert "保存エラー" in result
        self.mock_rich_ui.print_error.assert_called()


class TestCompanionCoreConfigIntegration:
    """CompanionCore設定管理の統合テスト"""
    
    def setup_method(self):
        """各テストメソッドの前に実行される初期化"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "integration_companion_config.json")
        
        # rich_uiをモック化
        self.rich_ui_patcher = patch('companion.core.rich_ui')
        self.mock_rich_ui = self.rich_ui_patcher.start()
    
    def teardown_method(self):
        """各テストメソッドの後に実行されるクリーンアップ"""
        self.rich_ui_patcher.stop()
        
        if os.path.exists(self.config_file):
            os.remove(self.config_file)
        os.rmdir(self.temp_dir)
    
    def test_complete_config_management_workflow(self):
        """完全な設定管理ワークフローのテスト"""
        companion = CompanionCore()
        companion.approval_gate.config.config_file_path = self.config_file
        
        # 1. 初期設定を確認
        initial_config = companion.get_approval_config()
        assert initial_config.mode == ApprovalMode.STANDARD
        
        # 2. モードを変更
        result = companion.update_approval_mode(ApprovalMode.STRICT)
        assert "変更しました" in result
        assert companion.approval_gate.config.mode == ApprovalMode.STRICT
        
        # 3. 除外設定を追加
        companion.add_approval_exclusion(path="/tmp")
        companion.add_approval_exclusion(extension=".log")
        
        # 4. 設定を表示
        config_display = companion.show_approval_config()
        assert "厳格" in config_display or "strict" in config_display
        assert "tmp" in config_display  # パス正規化を考慮
        assert ".log" in config_display
        
        # 5. 設定をリセット
        reset_result = companion.reset_approval_config()
        assert "リセットしました" in reset_result
        
        # 6. リセット後の設定を確認
        final_config = companion.get_approval_config()
        assert final_config.mode == ApprovalMode.STANDARD
        assert len(final_config.excluded_paths) == 0
        assert len(final_config.excluded_extensions) == 0
    
    def test_config_persistence_across_companion_instances(self):
        """CompanionCoreインスタンス間での設定永続化テスト"""
        # 最初のインスタンスで設定を変更
        companion1 = CompanionCore()
        companion1.approval_gate.config.config_file_path = self.config_file
        
        companion1.update_approval_mode(ApprovalMode.TRUSTED)
        companion1.add_approval_exclusion(path="/var/log")
        companion1.approval_gate.save_config()
        
        # 2番目のインスタンスで設定を読み込み
        companion2 = CompanionCore()
        companion2.approval_gate.config.config_file_path = self.config_file
        companion2._load_approval_config()
        
        # 設定が正しく引き継がれていることを確認
        assert companion2.approval_gate.config.mode == ApprovalMode.TRUSTED
        assert os.path.normpath("/var/log") in companion2.approval_gate.config.excluded_paths
    
    def test_error_handling_with_graceful_degradation(self):
        """エラー処理と優雅な劣化のテスト"""
        companion = CompanionCore()
        
        # 存在しない設定ファイルを指定
        companion.approval_gate.config.config_file_path = "/nonexistent/path/config.json"
        
        # エラーが発生しても動作することを確認
        config = companion.get_approval_config()
        assert config is not None
        assert config.mode == ApprovalMode.STANDARD  # デフォルト設定
        
        # 設定変更も正常に動作することを確認
        result = companion.update_approval_mode(ApprovalMode.STRICT)
        # 保存でエラーが発生するが、メモリ上の設定は変更される
        assert companion.approval_gate.config.mode == ApprovalMode.STRICT