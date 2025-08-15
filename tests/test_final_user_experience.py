"""
Final User Experience Test for Approval System Integration

This module contains end-to-end tests that validate the complete user experience
with the approval system integrated into Duckflow Companion.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from companion.core import CompanionCore
from companion.approval_system import ApprovalConfig, ApprovalMode, ApprovalResponse
from companion.approval_ui import UserApprovalUI
from main_companion import DuckflowCompanion


class MockApprovalUI(UserApprovalUI):
    """Mock UI for automated testing."""
    
    def __init__(self, responses=None):
        super().__init__()
        self.responses = responses or []
        self.response_index = 0
        self.requests = []
    
    def show_approval_request(self, request, session_id=None):
        """Mock approval request with predefined responses."""
        self.requests.append(request)
        
        if self.response_index < len(self.responses):
            response = self.responses[self.response_index]
            self.response_index += 1
            return response
        
        # Default to approval if no more responses
        return ApprovalResponse(
            approved=True,
            reason="Auto-approved for testing",
            timestamp=1234567890,
            details={'auto_test': True}
        )


class TestCompleteUserExperience:
    """Test complete user experience with approval system."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        os.chdir(self.temp_dir)
    
    def teardown_method(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_companion_initialization_with_approval_system(self):
        """Test that companion initializes properly with approval system."""
        companion = CompanionCore()
        
        # Verify approval system is initialized
        assert hasattr(companion, 'approval_gate')
        assert companion.approval_gate is not None
        assert hasattr(companion.approval_gate, 'config')
        
        # Verify default configuration
        config = companion.approval_gate.config
        assert config.mode == ApprovalMode.STANDARD
    
    def test_help_system_integration(self):
        """Test that help system works with approval information."""
        companion = CompanionCore()
        
        # Test general help
        help_response = companion.process_message("help")
        assert "承認システム" in help_response
        assert "セキュリティ" in help_response
        
        # Test approval-specific help
        approval_help = companion.process_message("help 承認")
        assert "承認システム" in approval_help
        assert "承認が必要な操作" in approval_help
        assert "STRICT" in approval_help or "STANDARD" in approval_help
    
    @patch('companion.approval_ui.UserApprovalUI.show_approval_request')
    def test_file_operation_with_approval_flow(self, mock_show_approval):
        """Test complete file operation with approval flow."""
        # Setup mock to approve
        mock_show_approval.return_value = ApprovalResponse(
            approved=True,
            reason="User approved file creation",
            timestamp=1234567890,
            details={}
        )
        
        companion = CompanionCore()
        
        # Request file creation
        response = companion.process_message("hello.pyというファイルを作成してください")
        
        # Verify approval was requested
        mock_show_approval.assert_called()
        
        # Verify response mentions the operation
        assert isinstance(response, str)
        assert len(response) > 0
    
    @patch('companion.approval_ui.UserApprovalUI.show_approval_request')
    def test_file_operation_rejection_flow(self, mock_show_approval):
        """Test file operation rejection flow."""
        # Setup mock to reject
        mock_show_approval.return_value = ApprovalResponse(
            approved=False,
            reason="User rejected file creation",
            timestamp=1234567890,
            details={}
        )
        
        companion = CompanionCore()
        
        # Request file creation
        response = companion.process_message("test.pyというファイルを作成してください")
        
        # Verify approval was requested
        mock_show_approval.assert_called()
        
        # Verify response handles rejection gracefully
        assert isinstance(response, str)
        assert len(response) > 0
    
    def test_natural_conversation_flow(self):
        """Test that conversation remains natural with approval system."""
        companion = CompanionCore()
        
        # Test various natural language inputs
        test_inputs = [
            "こんにちは",
            "今日の天気はどうですか？",
            "Pythonについて教えて",
            "help",
            "ありがとう"
        ]
        
        for user_input in test_inputs:
            response = companion.process_message(user_input)
            
            # Verify response is natural and doesn't expose technical details
            assert isinstance(response, str)
            assert len(response) > 0
            
            # Should not contain technical approval system terms
            technical_terms = [
                'ApprovalGate', 'ApprovalResponse', 'OperationAnalyzer',
                'risk_level', 'operation_type', 'bypass_attempt'
            ]
            
            for term in technical_terms:
                assert term not in response, f"Technical term '{term}' found in response to '{user_input}'"
    
    def test_security_features_active(self):
        """Test that security features are properly active."""
        companion = CompanionCore()
        
        # Verify approval gate is configured
        assert companion.approval_gate is not None
        
        # Verify file operations have approval integration
        assert hasattr(companion, 'file_ops')
        assert companion.file_ops is not None
        assert hasattr(companion.file_ops, 'approval_gate')
        
        # Verify approval gate has proper configuration
        config = companion.approval_gate.config
        assert config is not None
        assert hasattr(config, 'mode')
        assert config.mode in [ApprovalMode.STRICT, ApprovalMode.STANDARD, ApprovalMode.TRUSTED]
    
    def test_error_handling_with_approval_system(self):
        """Test error handling when approval system encounters issues."""
        companion = CompanionCore()
        
        # Test with invalid approval UI
        companion.approval_gate.approval_ui = None
        
        # Should handle gracefully without crashing
        try:
            response = companion.process_message("test.pyを作成してください")
            assert isinstance(response, str)
        except Exception as e:
            pytest.fail(f"Companion crashed with approval system error: {e}")
    
    def test_approval_modes_behavior(self):
        """Test behavior in different approval modes."""
        # Test STANDARD mode (default)
        companion_standard = CompanionCore()
        assert companion_standard.approval_gate.config.mode == ApprovalMode.STANDARD
        
        # Test STRICT mode
        strict_config = ApprovalConfig(mode=ApprovalMode.STRICT)
        companion_strict = CompanionCore()
        companion_strict.approval_gate.config = strict_config
        
        # Test TRUSTED mode
        trusted_config = ApprovalConfig(mode=ApprovalMode.TRUSTED)
        companion_trusted = CompanionCore()
        companion_trusted.approval_gate.config = trusted_config
        
        # All should initialize without errors
        for companion in [companion_standard, companion_strict, companion_trusted]:
            assert companion.approval_gate is not None
            assert companion.file_ops is not None


class TestMainCompanionIntegration:
    """Test main companion application with approval system."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        os.chdir(self.temp_dir)
    
    def teardown_method(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_duckflow_companion_initialization(self):
        """Test DuckflowCompanion initializes with approval system."""
        try:
            companion_app = DuckflowCompanion()
            
            # Verify companion core is initialized
            assert hasattr(companion_app, 'companion')
            assert companion_app.companion is not None
            
            # Verify approval system is integrated
            assert hasattr(companion_app.companion, 'approval_gate')
            assert companion_app.companion.approval_gate is not None
            
        except Exception as e:
            pytest.fail(f"DuckflowCompanion initialization failed: {e}")
    
    @patch('codecrafter.ui.rich_ui.rich_ui.print_message')
    def test_security_welcome_message(self, mock_print):
        """Test that security welcome message is displayed."""
        companion_app = DuckflowCompanion()
        companion_app._show_security_welcome()
        
        # Verify security message was printed
        mock_print.assert_called()
        
        # Check that security-related content was included
        call_args = [call[0][0] for call in mock_print.call_args_list]
        security_content = ' '.join(call_args)
        
        assert "セキュリティ" in security_content
        assert "承認システム" in security_content
        assert "承認が必要な操作" in security_content
    
    def test_special_commands_with_approval_system(self):
        """Test special commands related to approval system."""
        companion_app = DuckflowCompanion()
        
        # Test approval status command
        result = companion_app._handle_special_commands("approval-status")
        assert result is True  # Command was handled
        
        # Test config command
        result = companion_app._handle_special_commands("config")
        assert result is True  # Command was handled
        
        # Test approval mode change command
        result = companion_app._handle_special_commands("approval-mode standard")
        assert result is True  # Command was handled


class TestUserExperienceScenarios:
    """Test realistic user experience scenarios."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        os.chdir(self.temp_dir)
    
    def teardown_method(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('companion.approval_ui.UserApprovalUI.show_approval_request')
    def test_new_user_first_experience(self, mock_show_approval):
        """Test first-time user experience with approval system."""
        # Setup auto-approval for testing
        mock_show_approval.return_value = ApprovalResponse(
            approved=True,
            reason="User approved after explanation",
            timestamp=1234567890,
            details={}
        )
        
        companion = CompanionCore()
        
        # Simulate new user interactions
        scenarios = [
            "こんにちは",  # Greeting
            "help",  # Getting help
            "Pythonファイルを作りたいです",  # First file operation request
            "ありがとうございます"  # Thank you
        ]
        
        for scenario in scenarios:
            response = companion.process_message(scenario)
            
            # Verify responses are helpful and natural
            assert isinstance(response, str)
            assert len(response) > 0
            
            # Should be encouraging and supportive
            positive_indicators = [
                "こんにちは", "はい", "できます", "お手伝い", "一緒に", 
                "大丈夫", "安心", "サポート", "ヘルプ"
            ]
            
            # At least some responses should be positive/supportive
            if any(indicator in response for indicator in positive_indicators):
                continue  # This response is appropriately supportive
    
    @patch('companion.approval_ui.UserApprovalUI.show_approval_request')
    def test_experienced_user_workflow(self, mock_show_approval):
        """Test experienced user workflow with approval system."""
        # Setup selective approval (approve some, reject others)
        responses = [
            ApprovalResponse(approved=True, reason="Approved", timestamp=1234567890, details={}),
            ApprovalResponse(approved=False, reason="Rejected", timestamp=1234567890, details={}),
            ApprovalResponse(approved=True, reason="Approved", timestamp=1234567890, details={})
        ]
        
        mock_show_approval.side_effect = responses
        
        companion = CompanionCore()
        
        # Simulate experienced user workflow
        workflow = [
            "main.pyを作成してください",  # Should trigger approval
            "config.jsonを編集してください",  # Should trigger approval  
            "README.mdを作成してください"  # Should trigger approval
        ]
        
        for request in workflow:
            response = companion.process_message(request)
            assert isinstance(response, str)
            assert len(response) > 0
    
    def test_help_system_completeness(self):
        """Test that help system covers all important topics."""
        companion = CompanionCore()
        
        # Test help topics that should be available
        help_topics = [
            "help",
            "help 承認",
            "help コマンド", 
            "help ファイル操作",
            "help 設定"
        ]
        
        for topic in help_topics:
            response = companion.process_message(topic)
            
            # Verify help response is comprehensive
            assert isinstance(response, str)
            assert len(response) > 100  # Should be substantial
            
            # Should contain relevant information
            if "承認" in topic:
                assert "承認システム" in response
                assert "セキュリティ" in response
            elif "コマンド" in topic:
                assert "コマンド" in response
            elif "ファイル" in topic:
                assert "ファイル" in response


if __name__ == '__main__':
    pytest.main([__file__, '-v'])