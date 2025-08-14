"""
Test suite for ApprovalConfig and ApprovalMode
承認設定とモードのテスト
"""

import pytest
import os
import tempfile
import json
from pathlib import Path

from companion.approval_system import (
    ApprovalConfig, ApprovalMode, RiskLevel
)


class TestApprovalMode:
    """ApprovalModeのテスト"""
    
    def test_approval_mode_values(self):
        """ApprovalModeの値のテスト"""
        assert ApprovalMode.STRICT.value == "strict"
        assert ApprovalMode.STANDARD.value == "standard"
        assert ApprovalMode.TRUSTED.value == "trusted"
    
    def test_approval_mode_enum_members(self):
        """ApprovalModeの列挙メンバーのテスト"""
        modes = list(ApprovalMode)
        assert len(modes) == 3
        assert ApprovalMode.STRICT in modes
        assert ApprovalMode.STANDARD in modes
        assert ApprovalMode.TRUSTED in modes


class TestApprovalConfig:
    """ApprovalConfigのテスト"""
    
    def setup_method(self):
        """各テストメソッドの前に実行される初期化"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "test_config.json")
    
    def teardown_method(self):
        """各テストメソッドの後に実行されるクリーンアップ"""
        # テンポラリファイルをクリーンアップ
        if os.path.exists(self.config_file):
            os.remove(self.config_file)
        os.rmdir(self.temp_dir)
    
    def test_default_initialization(self):
        """デフォルト初期化のテスト"""
        config = ApprovalConfig()
        
        assert config.mode == ApprovalMode.STANDARD
        assert config.timeout_seconds == 30
        assert config.excluded_paths == []
        assert config.excluded_extensions == []
        assert config.show_preview is True
        assert config.show_impact_analysis is True
        assert config.use_countdown is True
        assert config.max_bypass_attempts == 3
        assert config.require_confirmation_for_critical is True
        assert config.config_file_path is not None
    
    def test_custom_initialization(self):
        """カスタム初期化のテスト"""
        config = ApprovalConfig(
            mode=ApprovalMode.STRICT,
            timeout_seconds=60,
            excluded_paths=["/tmp", "/var/log"],
            excluded_extensions=[".tmp", ".log"],
            show_preview=False,
            config_file_path=self.config_file
        )
        
        assert config.mode == ApprovalMode.STRICT
        assert config.timeout_seconds == 60
        assert config.excluded_paths == ["/tmp", "/var/log"]
        assert config.excluded_extensions == [".tmp", ".log"]
        assert config.show_preview is False
        assert config.config_file_path == self.config_file
    
    def test_is_approval_required_strict_mode(self):
        """STRICTモードでの承認要求判定テスト"""
        config = ApprovalConfig(mode=ApprovalMode.STRICT)
        
        assert config.is_approval_required(RiskLevel.LOW_RISK) is False
        assert config.is_approval_required(RiskLevel.HIGH_RISK) is True
        assert config.is_approval_required(RiskLevel.CRITICAL_RISK) is True
    
    def test_is_approval_required_standard_mode(self):
        """STANDARDモードでの承認要求判定テスト"""
        config = ApprovalConfig(mode=ApprovalMode.STANDARD)
        
        assert config.is_approval_required(RiskLevel.LOW_RISK) is False
        assert config.is_approval_required(RiskLevel.HIGH_RISK) is True
        assert config.is_approval_required(RiskLevel.CRITICAL_RISK) is True
    
    def test_is_approval_required_trusted_mode(self):
        """TRUSTEDモードでの承認要求判定テスト"""
        config = ApprovalConfig(mode=ApprovalMode.TRUSTED)
        
        assert config.is_approval_required(RiskLevel.LOW_RISK) is False
        assert config.is_approval_required(RiskLevel.HIGH_RISK) is False
        assert config.is_approval_required(RiskLevel.CRITICAL_RISK) is True
    
    def test_is_path_excluded(self):
        """パス除外判定のテスト"""
        config = ApprovalConfig(
            excluded_paths=["/tmp", "/var/log"],
            excluded_extensions=[".tmp", ".log"]
        )
        
        # 除外パスのテスト
        assert config.is_path_excluded("/tmp/test.txt") is True
        assert config.is_path_excluded("/var/log/app.log") is True
        assert config.is_path_excluded("/home/user/file.txt") is False
        
        # 除外拡張子のテスト
        assert config.is_path_excluded("/home/user/temp.tmp") is True
        assert config.is_path_excluded("/home/user/app.log") is True
        assert config.is_path_excluded("/home/user/document.txt") is False
        
        # 大文字小文字の区別なし
        assert config.is_path_excluded("/home/user/temp.TMP") is True
        assert config.is_path_excluded("/home/user/app.LOG") is True
    
    def test_get_timeout_for_risk_level(self):
        """リスクレベル別タイムアウト取得のテスト"""
        config = ApprovalConfig(timeout_seconds=30)
        
        assert config.get_timeout_for_risk_level(RiskLevel.LOW_RISK) == 30
        assert config.get_timeout_for_risk_level(RiskLevel.HIGH_RISK) == 30
        assert config.get_timeout_for_risk_level(RiskLevel.CRITICAL_RISK) == 60  # 2倍
    
    def test_save_and_load_config(self):
        """設定の保存と読み込みのテスト"""
        # 設定を作成
        original_config = ApprovalConfig(
            mode=ApprovalMode.STRICT,
            timeout_seconds=45,
            excluded_paths=["/tmp"],
            excluded_extensions=[".tmp"],
            show_preview=False,
            config_file_path=self.config_file
        )
        
        # 保存
        original_config.save_to_file()
        
        # 読み込み
        loaded_config = ApprovalConfig.load_from_file(self.config_file)
        
        # 比較
        assert loaded_config.mode == ApprovalMode.STRICT
        assert loaded_config.timeout_seconds == 45
        assert loaded_config.excluded_paths == ["/tmp"]
        assert loaded_config.excluded_extensions == [".tmp"]
        assert loaded_config.show_preview is False
        assert loaded_config.config_file_path == self.config_file
    
    def test_load_nonexistent_config(self):
        """存在しない設定ファイルの読み込みテスト"""
        nonexistent_file = os.path.join(self.temp_dir, "nonexistent.json")
        
        config = ApprovalConfig.load_from_file(nonexistent_file)
        
        # デフォルト設定が返される
        assert config.mode == ApprovalMode.STANDARD
        assert config.timeout_seconds == 30
        assert config.config_file_path == nonexistent_file
    
    def test_load_invalid_config(self):
        """不正な設定ファイルの読み込みテスト"""
        # 不正なJSONファイルを作成
        with open(self.config_file, 'w') as f:
            f.write("invalid json content")
        
        with pytest.raises(ValueError, match="設定ファイルの形式が不正です"):
            ApprovalConfig.load_from_file(self.config_file)
    
    def test_update_mode(self):
        """モード更新のテスト"""
        config = ApprovalConfig(mode=ApprovalMode.STANDARD)
        
        config.update_mode(ApprovalMode.STRICT)
        assert config.mode == ApprovalMode.STRICT
        
        config.update_mode(ApprovalMode.TRUSTED)
        assert config.mode == ApprovalMode.TRUSTED
    
    def test_add_remove_excluded_path(self):
        """除外パスの追加・削除のテスト"""
        config = ApprovalConfig()
        
        # パス追加
        config.add_excluded_path("/tmp")
        assert "/tmp" in config.excluded_paths
        
        config.add_excluded_path("/var/log")
        assert "/var/log" in config.excluded_paths
        
        # 重複追加は無視される
        config.add_excluded_path("/tmp")
        assert config.excluded_paths.count("/tmp") == 1
        
        # パス削除
        config.remove_excluded_path("/tmp")
        assert "/tmp" not in config.excluded_paths
        assert "/var/log" in config.excluded_paths
    
    def test_add_remove_excluded_extension(self):
        """除外拡張子の追加・削除のテスト"""
        config = ApprovalConfig()
        
        # 拡張子追加
        config.add_excluded_extension(".tmp")
        assert ".tmp" in config.excluded_extensions
        
        config.add_excluded_extension("log")  # ドットなしでも追加可能
        assert ".log" in config.excluded_extensions
        
        # 大文字小文字は正規化される
        config.add_excluded_extension(".TXT")
        assert ".txt" in config.excluded_extensions
        
        # 重複追加は無視される
        config.add_excluded_extension(".tmp")
        assert config.excluded_extensions.count(".tmp") == 1
        
        # 拡張子削除
        config.remove_excluded_extension(".tmp")
        assert ".tmp" not in config.excluded_extensions
        assert ".log" in config.excluded_extensions
    
    def test_get_mode_description(self):
        """モード説明取得のテスト"""
        config = ApprovalConfig()
        
        config.mode = ApprovalMode.STRICT
        assert "厳格モード" in config.get_mode_description()
        
        config.mode = ApprovalMode.STANDARD
        assert "標準モード" in config.get_mode_description()
        
        config.mode = ApprovalMode.TRUSTED
        assert "信頼モード" in config.get_mode_description()
    
    def test_to_dict(self):
        """辞書変換のテスト"""
        config = ApprovalConfig(
            mode=ApprovalMode.STRICT,
            timeout_seconds=45,
            excluded_paths=["/tmp"],
            config_file_path=self.config_file
        )
        
        config_dict = config.to_dict()
        
        assert config_dict["mode"] == "strict"
        assert config_dict["timeout_seconds"] == 45
        assert config_dict["excluded_paths"] == ["/tmp"]
        assert "mode_description" in config_dict
        assert config_dict["config_file_path"] == self.config_file
    
    def test_str_representation(self):
        """文字列表現のテスト"""
        config = ApprovalConfig(mode=ApprovalMode.STRICT, timeout_seconds=45)
        
        str_repr = str(config)
        assert "ApprovalConfig" in str_repr
        assert "strict" in str_repr
        assert "45s" in str_repr
    
    def test_config_file_path_normalization(self):
        """設定ファイルパスの正規化テスト"""
        config = ApprovalConfig(
            excluded_paths=["../temp", "logs\\app"],
            config_file_path=self.config_file
        )
        
        # パスが正規化されることを確認
        config.add_excluded_path("../another/path")
        
        # 除外判定でも正規化されたパスが使用される
        normalized_temp = os.path.normpath("../temp")
        if normalized_temp in config.excluded_paths:
            assert config.is_path_excluded("../temp/file.txt") is True


class TestApprovalConfigIntegration:
    """ApprovalConfigの統合テスト"""
    
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
        # 1. 初期設定を作成
        config = ApprovalConfig(config_file_path=self.config_file)
        
        # 2. 設定をカスタマイズ
        config.update_mode(ApprovalMode.STRICT)
        config.timeout_seconds = 60
        config.add_excluded_path("/tmp")
        config.add_excluded_extension(".log")
        config.show_preview = False
        
        # 3. 設定を保存
        config.save_to_file()
        
        # 4. 新しいインスタンスで設定を読み込み
        loaded_config = ApprovalConfig.load_from_file(self.config_file)
        
        # 5. 設定が正しく保存・読み込みされたことを確認
        assert loaded_config.mode == ApprovalMode.STRICT
        assert loaded_config.timeout_seconds == 60
        assert os.path.normpath("/tmp") in loaded_config.excluded_paths
        assert ".log" in loaded_config.excluded_extensions
        assert loaded_config.show_preview is False
        
        # 6. 承認要求判定のテスト
        assert loaded_config.is_approval_required(RiskLevel.HIGH_RISK) is True
        assert loaded_config.is_path_excluded("/tmp/test.txt") is True
        assert loaded_config.is_path_excluded("/home/app.log") is True
        
        # 7. タイムアウト設定のテスト
        assert loaded_config.get_timeout_for_risk_level(RiskLevel.HIGH_RISK) == 60
        assert loaded_config.get_timeout_for_risk_level(RiskLevel.CRITICAL_RISK) == 120
    
    def test_config_persistence_across_modifications(self):
        """設定変更の永続化テスト"""
        # 初期設定
        config = ApprovalConfig(config_file_path=self.config_file)
        config.save_to_file()
        
        # 設定を変更して保存
        config.update_mode(ApprovalMode.TRUSTED)
        config.add_excluded_path("/var/log")
        config.save_to_file()
        
        # 再読み込みして変更が反映されていることを確認
        reloaded_config = ApprovalConfig.load_from_file(self.config_file)
        assert reloaded_config.mode == ApprovalMode.TRUSTED
        assert os.path.normpath("/var/log") in reloaded_config.excluded_paths
        
        # さらに変更
        reloaded_config.timeout_seconds = 90
        reloaded_config.remove_excluded_path("/var/log")
        reloaded_config.add_excluded_extension(".bak")
        reloaded_config.save_to_file()
        
        # 最終確認
        final_config = ApprovalConfig.load_from_file(self.config_file)
        assert final_config.mode == ApprovalMode.TRUSTED
        assert final_config.timeout_seconds == 90
        assert os.path.normpath("/var/log") not in final_config.excluded_paths
        assert ".bak" in final_config.excluded_extensions