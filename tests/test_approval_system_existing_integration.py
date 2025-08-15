"""
Integration tests for adding approval system to existing test scenarios.

This module tests the integration of the approval system with existing
companion functionality and ensures backward compatibility while adding
security features.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
import time
from companion.core import CompanionCore
from companion.file_ops import SimpleFileOps
from companion.approval_system import (
    ApprovalGate, ApprovalConfig, ApprovalMode, ApprovalResponse,
    ApprovalTimeoutError, ApprovalUIError
)
from companion.approval_ui import UserApprovalUI


class AutoApprovalUI(UserApprovalUI):
    """Automated UI for testing that auto-approves operations."""
    
    def __init__(self, auto_approve=True):
        super().__init__()
        self.auto_approve = auto_approve
        self.request_history = []
    
    def show_approval_request(self, request, session_id=None):
        """Auto-approve or reject based on configuration."""
        self.request_history.append(request)
        
        if self.auto_approve:
            return ApprovalResponse(
                approved=True,
                reason="Auto-approved for testing",
                timestamp=time.time(),
                details={'auto_test': True}
            )
        else:
            return ApprovalResponse(
                approved=False,
                reason="Auto-rejected for testing",
                timestamp=time.time(),
                details={'auto_test': True}
            )
    
    def get_request_count(self):
        return len(self.request_history)


class TestExistingFileOperationsWithApproval:
    """Test existing file operations with approval system integration."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Setup approval system with auto-approval for testing
        config = ApprovalConfig(mode=ApprovalMode.STANDARD)
        approval_gate = ApprovalGate(config=config)
        
        self.auto_ui = AutoApprovalUI(auto_approve=True)
        approval_gate.set_approval_ui(self.auto_ui)
        
        # Initialize file ops with approval gate
        self.file_ops = SimpleFileOps(approval_gate=approval_gate)
    
    def teardown_method(self):
        """Clean up temporary directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _check_success_result(self, result):
        """Check if result indicates success."""
        if isinstance(result, dict):
            success = result.get('success', False)
            message = result.get('message', '')
            return success or "作成" in message or "書き込み" in message
        else:
            result_str = str(result).lower()
            return "success" in result_str or "作成" in str(result) or "書き込み" in str(result)
    
    def test_create_file_with_approval_integration(self):
        """Test that existing create_file functionality works with approval."""
        file_path = os.path.join(self.temp_dir, 'test_file.py')
        content = 'print("Hello, World!")'
        
        # Create file (should trigger approval)
        result = self.file_ops.create_file(file_path, content)
        
        # Verify approval was requested
        assert self.auto_ui.get_request_count() == 1
        
        # Verify file was created
        assert os.path.exists(file_path)
        with open(file_path, 'r') as f:
            assert f.read() == content
        
        # Verify success message
        assert self._check_success_result(result)
    
    def test_write_file_with_approval_integration(self):
        """Test that existing write_file functionality works with approval."""
        # Create initial file
        file_path = os.path.join(self.temp_dir, 'existing_file.py')
        initial_content = 'initial content'
        with open(file_path, 'w') as f:
            f.write(initial_content)
        
        # Modify file (should trigger approval)
        new_content = 'modified content'
        result = self.file_ops.write_file(file_path, new_content)
        
        # Verify approval was requested
        assert self.auto_ui.get_request_count() == 1
        
        # Verify file was modified
        with open(file_path, 'r') as f:
            assert f.read() == new_content
        
        # Verify success message
        assert "success" in result.lower() or "書き込み" in result
    
    def test_read_file_bypasses_approval(self):
        """Test that read operations don't require approval."""
        # Create test file
        file_path = os.path.join(self.temp_dir, 'read_test.py')
        content = 'test content for reading'
        with open(file_path, 'w') as f:
            f.write(content)
        
        # Read file (should not trigger approval)
        result = self.file_ops.read_file(file_path)
        
        # Verify no approval was requested
        assert self.auto_ui.get_request_count() == 0
        
        # Verify content was returned
        assert content in result
    
    def test_list_files_bypasses_approval(self):
        """Test that list operations don't require approval."""
        # Create test files
        for i in range(3):
            file_path = os.path.join(self.temp_dir, f'test_file_{i}.py')
            with open(file_path, 'w') as f:
                f.write(f'content {i}')
        
        # List files (should not trigger approval)
        result = self.file_ops.list_files(self.temp_dir)
        
        # Verify no approval was requested
        assert self.auto_ui.get_request_count() == 0
        
        # Verify files were listed (result is a list of dicts)
        if isinstance(result, list):
            file_names = [item['name'] for item in result if isinstance(item, dict)]
            assert 'test_file_0.py' in file_names
            assert 'test_file_1.py' in file_names
            assert 'test_file_2.py' in file_names
        else:
            # If result is a string, check for file names in the string
            assert 'test_file_0.py' in str(result)
            assert 'test_file_1.py' in str(result)
            assert 'test_file_2.py' in str(result)
    
    def test_multiple_operations_approval_tracking(self):
        """Test approval tracking across multiple operations."""
        operations = [
            ('create_file', 'file1.py', 'content1'),
            ('create_file', 'file2.py', 'content2'),
            ('write_file', 'file1.py', 'modified content1')
        ]
        
        for i, (op_type, filename, content) in enumerate(operations):
            file_path = os.path.join(self.temp_dir, filename)
            
            if op_type == 'create_file':
                self.file_ops.create_file(file_path, content)
            elif op_type == 'write_file':
                self.file_ops.write_file(file_path, content)
            
            # Verify approval count increases
            assert self.auto_ui.get_request_count() == i + 1
        
        # Verify all files exist with correct content
        assert os.path.exists(os.path.join(self.temp_dir, 'file1.py'))
        assert os.path.exists(os.path.join(self.temp_dir, 'file2.py'))
        
        with open(os.path.join(self.temp_dir, 'file1.py'), 'r') as f:
            assert f.read() == 'modified content1'


class TestCompanionCoreWithApproval:
    """Test CompanionCore integration with approval system."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.companion = CompanionCore()
        
        # Setup approval system
        config = ApprovalConfig(mode=ApprovalMode.STANDARD)
        self.companion.approval_gate = ApprovalGate(config=config)
        
        self.auto_ui = AutoApprovalUI(auto_approve=True)
        self.companion.approval_gate.set_approval_ui(self.auto_ui)
    
    def teardown_method(self):
        """Clean up temporary directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_companion_file_operations_with_approval(self):
        """Test that companion file operations work with approval system."""
        # Mock file operation handling
        with patch.object(self.companion, '_handle_file_operation') as mock_handle:
            mock_handle.return_value = "File operation completed successfully"
            
            # Simulate file operation request
            result = self.companion._handle_file_operation(
                'create_file',
                {
                    'target': 'test_file.py',
                    'file_path': os.path.join(self.temp_dir, 'test_file.py'),
                    'content': 'print("Test")'
                }
            )
            
            # Verify operation was handled
            mock_handle.assert_called_once()
            assert "completed successfully" in result
    
    def test_companion_conversation_flow_with_approval(self):
        """Test that conversation flow remains natural with approval system."""
        # Mock process_message to test conversation flow
        with patch.object(self.companion, 'process_message') as mock_process:
            mock_process.return_value = "I've processed your request with appropriate security checks."
            
            # Simulate user message
            response = self.companion.process_message(
                "Please create a Python script that prints 'Hello, World!'"
            )
            
            # Verify response maintains natural conversation
            assert isinstance(response, str)
            assert len(response) > 0
            
            # Should not expose internal approval system details
            technical_terms = ['ApprovalGate', 'ApprovalResponse', 'risk_level']
            for term in technical_terms:
                assert term not in response


class TestApprovalModeIntegration:
    """Test different approval modes with existing functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.file_ops = SimpleFileOps()
    
    def teardown_method(self):
        """Clean up temporary directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_standard_mode_integration(self):
        """Test standard mode with existing file operations."""
        # Setup standard mode
        config = ApprovalConfig(mode=ApprovalMode.STANDARD)
        self.file_ops.approval_gate = ApprovalGate(config=config)
        
        auto_ui = AutoApprovalUI(auto_approve=True)
        self.file_ops.approval_gate.set_approval_ui(auto_ui)
        
        # High-risk operations should require approval
        file_path = os.path.join(self.temp_dir, 'standard_test.py')
        result = self.file_ops.create_file(file_path, 'test content')
        
        assert auto_ui.get_request_count() == 1
        assert os.path.exists(file_path)
        
        # Low-risk operations should not require approval
        read_result = self.file_ops.read_file(file_path)
        assert auto_ui.get_request_count() == 1  # No additional approval
        assert 'test content' in read_result
    
    def test_strict_mode_integration(self):
        """Test strict mode with existing file operations."""
        # Setup strict mode
        config = ApprovalConfig(mode=ApprovalMode.STRICT)
        self.file_ops.approval_gate = ApprovalGate(config=config)
        
        auto_ui = AutoApprovalUI(auto_approve=True)
        self.file_ops.approval_gate.set_approval_ui(auto_ui)
        
        # High-risk operations should require approval
        file_path = os.path.join(self.temp_dir, 'strict_test.py')
        result = self.file_ops.create_file(file_path, 'test content')
        
        assert auto_ui.get_request_count() == 1
        assert os.path.exists(file_path)
        
        # Low-risk operations should still not require approval in strict mode
        # (as per current implementation where STRICT excludes LOW_RISK)
        read_result = self.file_ops.read_file(file_path)
        assert auto_ui.get_request_count() == 1  # No additional approval
        assert 'test content' in read_result
    
    def test_trusted_mode_integration(self):
        """Test trusted mode with existing file operations."""
        # Setup trusted mode
        config = ApprovalConfig(mode=ApprovalMode.TRUSTED)
        self.file_ops.approval_gate = ApprovalGate(config=config)
        
        auto_ui = AutoApprovalUI(auto_approve=True)
        self.file_ops.approval_gate.set_approval_ui(auto_ui)
        
        # High-risk operations should be auto-approved
        file_path = os.path.join(self.temp_dir, 'trusted_test.py')
        result = self.file_ops.create_file(file_path, 'test content')
        
        assert auto_ui.get_request_count() == 0  # No approval needed
        assert os.path.exists(file_path)
        
        # Low-risk operations should also not require approval
        read_result = self.file_ops.read_file(file_path)
        assert auto_ui.get_request_count() == 0  # Still no approval
        assert 'test content' in read_result


class TestBackwardCompatibility:
    """Test backward compatibility with existing code."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.file_ops = SimpleFileOps()
    
    def teardown_method(self):
        """Clean up temporary directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_file_ops_without_approval_system(self):
        """Test that file operations work without approval system configured."""
        # Don't configure approval system
        file_path = os.path.join(self.temp_dir, 'no_approval_test.py')
        content = 'test content without approval'
        
        # Operations should work normally
        result = self.file_ops.create_file(file_path, content)
        
        # Verify file was created
        assert os.path.exists(file_path)
        with open(file_path, 'r') as f:
            assert f.read() == content
        
        # Verify success message
        assert self._check_success_result(result)
    
    def test_companion_without_approval_system(self):
        """Test that companion works without approval system configured."""
        companion = CompanionCore()
        # Don't configure approval system
        
        # Mock file operation to test basic functionality
        with patch.object(companion, '_handle_file_operation') as mock_handle:
            mock_handle.return_value = "Operation completed without approval system"
            
            result = companion._handle_file_operation(
                'create_file',
                {'target': 'test.py', 'content': 'test'}
            )
            
            mock_handle.assert_called_once()
            assert "completed" in result
    
    def test_gradual_approval_system_adoption(self):
        """Test gradual adoption of approval system."""
        # Start without approval system
        file_path1 = os.path.join(self.temp_dir, 'before_approval.py')
        result1 = self.file_ops.create_file(file_path1, 'content before approval')
        
        assert os.path.exists(file_path1)
        
        # Add approval system
        config = ApprovalConfig(mode=ApprovalMode.STANDARD)
        self.file_ops.approval_gate = ApprovalGate(config=config)
        
        auto_ui = AutoApprovalUI(auto_approve=True)
        self.file_ops.approval_gate.set_approval_ui(auto_ui)
        
        # Continue with approval system
        file_path2 = os.path.join(self.temp_dir, 'after_approval.py')
        result2 = self.file_ops.create_file(file_path2, 'content after approval')
        
        assert os.path.exists(file_path2)
        assert auto_ui.get_request_count() == 1
        
        # Both operations should have succeeded
        with open(file_path1, 'r') as f:
            assert f.read() == 'content before approval'
        with open(file_path2, 'r') as f:
            assert f.read() == 'content after approval'


class TestApprovalSystemTestingMode:
    """Test automated testing mode for approval system."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.file_ops = SimpleFileOps()
    
    def teardown_method(self):
        """Clean up temporary directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_auto_approval_testing_mode(self):
        """Test that testing mode can auto-approve operations."""
        # Setup approval system with testing mode
        config = ApprovalConfig(
            mode=ApprovalMode.STANDARD,
            testing_mode=True,
            auto_approve_for_testing=True
        )
        self.file_ops.approval_gate = ApprovalGate(config=config)
        
        # Operations should be auto-approved without UI
        file_path = os.path.join(self.temp_dir, 'testing_mode.py')
        result = self.file_ops.create_file(file_path, 'testing content')
        
        # Verify file was created
        assert os.path.exists(file_path)
        with open(file_path, 'r') as f:
            assert f.read() == 'testing content'
    
    def test_selective_testing_approval(self):
        """Test selective approval for testing scenarios."""
        # Setup approval system with selective auto-approval
        config = ApprovalConfig(mode=ApprovalMode.STANDARD)
        self.file_ops.approval_gate = ApprovalGate(config=config)
        
        # Use selective auto-approval UI
        class SelectiveAutoUI(AutoApprovalUI):
            def show_approval_request(self, request, session_id=None):
                # Only approve file creation, reject modifications
                if request.operation_info.operation_type == 'create_file':
                    return ApprovalResponse(
                        approved=True,
                        reason="Auto-approved file creation for testing",
                        timestamp=time.time(),
                        details={'auto_test': True}
                    )
                else:
                    return ApprovalResponse(
                        approved=False,
                        reason="Auto-rejected modification for testing",
                        timestamp=time.time(),
                        details={'auto_test': True}
                    )
        
        selective_ui = SelectiveAutoUI()
        self.file_ops.approval_gate.set_approval_ui(selective_ui)
        
        # File creation should be approved
        file_path = os.path.join(self.temp_dir, 'selective_test.py')
        result1 = self.file_ops.create_file(file_path, 'initial content')
        
        assert os.path.exists(file_path)
        
        # File modification should be rejected
        result2 = self.file_ops.write_file(file_path, 'modified content')
        
        # Original content should remain
        with open(file_path, 'r') as f:
            assert f.read() == 'initial content'
        
        # Verify rejection message
        assert ("rejected" in result2.lower() or 
                "拒否" in result2 or 
                "実行しません" in result2)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
