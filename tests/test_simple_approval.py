"""
SimpleApprovalGate のテスト
"""

import pytest
import tempfile
import os
from unittest.mock import patch, MagicMock
from datetime import datetime

from companion.simple_approval import (
    SimpleApprovalGate, ApprovalRequest, ApprovalResult, 
    ApprovalMode, RiskLevel, assess_file_risk, create_approval_request
)


class TestSimpleApprovalGate:
    """SimpleApprovalGate のテストクラス"""
    
    def test_init_with_config(self):
        """設定読み込みテスト"""
        with patch('codecrafter.base.config.config_manager') as mock_config:
            mock_config.config.get.return_value = {
                'mode': 'strict',
                'timeout_seconds': 60,
                'ui': {'auto_approve_all': True}
            }
            
            gate = SimpleApprovalGate()
            assert gate.config['mode'] == 'strict'
            assert gate.config['timeout_seconds'] == 60
            assert gate.config['ui']['auto_approve_all'] == True
    
    def test_init_fallback_config(self):
        """設定読み込み失敗時のフォールバック"""
        # _load_configメソッドでフォールバック設定を返すようにモック
        with patch.object(SimpleApprovalGate, '_load_config') as mock_load:
            mock_load.return_value = {
                'mode': 'standard',
                'timeout_seconds': 30,
                'show_preview': True,
                'max_preview_length': 200,
                'ui': {
                    'non_interactive': False,
                    'auto_approve_low': False,
                    'auto_approve_high': False,
                    'auto_approve_all': False
                }
            }
            
            gate = SimpleApprovalGate()
            
            # フォールバック設定が使用される
            assert gate.config['mode'] == 'standard'
            assert gate.config['timeout_seconds'] == 30
            assert gate.config['ui']['auto_approve_all'] == False
    
    def test_auto_approve_all(self):
        """全自動承認テスト"""
        with patch('codecrafter.base.config.config_manager') as mock_config:
            mock_config.config.get.return_value = {
                'ui': {'auto_approve_all': True}
            }
            
            gate = SimpleApprovalGate()
            request = ApprovalRequest(
                operation="test_operation",
                description="テスト操作",
                target="test.txt",
                risk_level=RiskLevel.HIGH
            )
            
            result = gate.request_approval(request)
            
            assert result.approved == True
            assert "全自動承認設定" in result.reason
            assert len(gate.approval_history) == 1
    
    def test_auto_approve_low_risk(self):
        """低リスク自動承認テスト"""
        with patch('codecrafter.base.config.config_manager') as mock_config:
            mock_config.config.get.return_value = {
                'ui': {'auto_approve_low': True}
            }
            
            gate = SimpleApprovalGate()
            request = ApprovalRequest(
                operation="test_operation",
                description="テスト操作",
                target="test.txt",
                risk_level=RiskLevel.LOW
            )
            
            result = gate.request_approval(request)
            
            assert result.approved == True
            assert "低リスク自動承認" in result.reason
    
    def test_trusted_mode_low_risk(self):
        """信頼モード低リスク自動承認テスト"""
        with patch('codecrafter.base.config.config_manager') as mock_config:
            mock_config.config.get.return_value = {
                'mode': 'trusted',
                'ui': {'auto_approve_low': False}  # 低リスク設定はOFFでも信頼モードで承認
            }
            
            gate = SimpleApprovalGate()
            request = ApprovalRequest(
                operation="test_operation", 
                description="テスト操作",
                target="test.txt",
                risk_level=RiskLevel.LOW
            )
            
            result = gate.request_approval(request)
            
            assert result.approved == True
            assert "信頼モード - 低リスク自動承認" in result.reason
    
    def test_non_interactive_mode(self):
        """非対話モードテスト"""
        with patch('codecrafter.base.config.config_manager') as mock_config:
            mock_config.config.get.return_value = {
                'ui': {'non_interactive': True}
            }
            
            gate = SimpleApprovalGate()
            request = ApprovalRequest(
                operation="test_operation",
                description="テスト操作", 
                target="test.txt"
            )
            
            result = gate.request_approval(request)
            
            assert result.approved == False
            assert "非対話モード" in result.reason
    
    @patch('builtins.input', return_value='y')
    def test_fallback_approval_yes(self, mock_input):
        """フォールバック承認（Yes）テスト"""
        with patch('codecrafter.base.config.config_manager') as mock_config:
            mock_config.config.get.return_value = {'ui': {}}
            
            gate = SimpleApprovalGate()
            gate.ui = None  # Rich UIを無効化してフォールバック使用
            
            request = ApprovalRequest(
                operation="test_operation",
                description="テスト操作",
                target="test.txt"
            )
            
            result = gate.request_approval(request)
            
            assert result.approved == True
            assert result.reason == "ユーザー判断"
    
    @patch('builtins.input', return_value='n')
    def test_fallback_approval_no(self, mock_input):
        """フォールバック承認（No）テスト"""
        with patch('codecrafter.base.config.config_manager') as mock_config:
            mock_config.config.get.return_value = {'ui': {}}
            
            gate = SimpleApprovalGate()
            gate.ui = None  # Rich UIを無効化してフォールバック使用
            
            request = ApprovalRequest(
                operation="test_operation",
                description="テスト操作",
                target="test.txt"
            )
            
            result = gate.request_approval(request)
            
            assert result.approved == False
            assert result.reason == "ユーザー拒否"
    
    def test_strict_mode_confirmation(self):
        """厳格モード再確認テスト"""
        with patch('codecrafter.base.config.config_manager') as mock_config:
            mock_config.config.get.return_value = {
                'mode': 'strict',
                'ui': {}
            }
            
            gate = SimpleApprovalGate()
            
            # UIモックの設定
            mock_ui = MagicMock()
            mock_ui.get_confirmation.side_effect = [True, False]  # 最初の承認はOK、再確認はNG
            gate.ui = mock_ui
            
            request = ApprovalRequest(
                operation="test_operation",
                description="テスト操作",
                target="test.txt",
                risk_level=RiskLevel.HIGH
            )
            
            result = gate.request_approval(request)
            
            # 最終確認で拒否されることを確認
            assert result.approved == False
            assert "厳格モード - 最終確認で拒否" in result.reason
    
    def test_approval_history(self):
        """承認履歴テスト"""
        with patch('codecrafter.base.config.config_manager') as mock_config:
            mock_config.config.get.return_value = {
                'ui': {'auto_approve_all': True}
            }
            
            gate = SimpleApprovalGate()
            
            # 複数の承認要求
            for i in range(3):
                request = ApprovalRequest(
                    operation=f"test_operation_{i}",
                    description=f"テスト操作{i}",
                    target=f"test{i}.txt"
                )
                gate.request_approval(request)
            
            # 履歴確認
            history = gate.get_approval_history()
            assert len(history) == 3
            
            # 履歴クリア
            gate.clear_history()
            assert len(gate.get_approval_history()) == 0


class TestHelperFunctions:
    """ヘルパー関数のテスト"""
    
    def test_assess_file_risk(self):
        """ファイルリスク評価テスト"""
        # 高リスク
        assert assess_file_risk('.env') == RiskLevel.HIGH
        assert assess_file_risk('config.yaml') == RiskLevel.HIGH
        
        # 中リスク
        assert assess_file_risk('script.py') == RiskLevel.MEDIUM
        assert assess_file_risk('app.js') == RiskLevel.MEDIUM
        
        # 低リスク
        assert assess_file_risk('readme.md') == RiskLevel.LOW
        assert assess_file_risk('data.json') == RiskLevel.LOW
        
        # その他（中リスク）
        assert assess_file_risk('unknown.xyz') == RiskLevel.MEDIUM
    
    def test_create_approval_request(self):
        """承認要求作成ヘルパーテスト"""
        request = create_approval_request(
            operation="test_op",
            target="test.txt", 
            description="テスト",
            risk_level=RiskLevel.HIGH,
            details="詳細情報"
        )
        
        assert request.operation == "test_op"
        assert request.target == "test.txt"
        assert request.description == "テスト"
        assert request.risk_level == RiskLevel.HIGH
        assert request.details == "詳細情報"


class TestErrorHandling:
    """エラーハンドリングテスト"""
    
    def test_config_load_error(self):
        """設定読み込みエラー処理"""
        with patch.object(SimpleApprovalGate, '_load_config') as mock_load:
            mock_load.return_value = {
                'mode': 'standard',
                'timeout_seconds': 30,
                'show_preview': True,
                'max_preview_length': 200,
                'ui': {
                    'non_interactive': False,
                    'auto_approve_low': False,
                    'auto_approve_high': False,
                    'auto_approve_all': False
                }
            }
            
            gate = SimpleApprovalGate()
            
            # フォールバック設定が使用される
            assert gate.config['mode'] == 'standard'
    
    def test_ui_error_fallback(self):
        """UI エラー時のフォールバック"""
        with patch('codecrafter.base.config.config_manager') as mock_config:
            mock_config.config.get.return_value = {'ui': {}}
            
            gate = SimpleApprovalGate()
            
            # UIでエラーが発生する場合
            mock_ui = MagicMock()
            mock_ui.get_confirmation.side_effect = Exception("UI Error")
            gate.ui = mock_ui
            
            with patch('builtins.input', return_value='y'):
                request = ApprovalRequest(
                    operation="test_operation",
                    description="テスト操作",
                    target="test.txt"
                )
                
                result = gate.request_approval(request)
                
                # フォールバックで処理される
                assert result.approved == True
    
    def test_fallback_input_error(self):
        """フォールバック入力エラー処理"""
        with patch('codecrafter.base.config.config_manager') as mock_config:
            mock_config.config.get.return_value = {'ui': {}}
            
            gate = SimpleApprovalGate()
            gate.ui = None
            
            with patch('builtins.input', side_effect=Exception("Input Error")):
                request = ApprovalRequest(
                    operation="test_operation",
                    description="テスト操作",
                    target="test.txt"
                )
                
                result = gate.request_approval(request)
                
                # エラー時の動作確認（フォールバックで処理される）
                assert result.approved == False
                # フォールバック処理でユーザー拒否となる
                assert result.reason in ["ユーザー拒否", "承認処理エラー: Input Error"]


if __name__ == "__main__":
    pytest.main([__file__])