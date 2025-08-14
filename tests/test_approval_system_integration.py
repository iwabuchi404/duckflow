"""
Integration tests for the approval system with CompanionCore and file operations.

This module tests the complete integration of the approval system with the
main companion functionality, ensuring that all components work together
seamlessly in real-world scenarios.
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


class TestCompanionCoreApprovalIntegration:
    """Test integration between CompanionCore and approval system."""
    
    def setup_method(self):
        """Set up test fixtures with temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.companion = CompanionCore()
        
        # Setup approval system
        config = ApprovalConfig(mode=ApprovalMode.STANDARD)
        self.companion.approval_gate = ApprovalGate(config=config)
        
        # Mock UI for testing
        self.mock_ui = Mock(spec=UserApprovalUI)
        self.companion.approval_gate.set_approval_ui(self.mock_ui)
    
    def teardown_method(self):
        """Clean up temporary directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('companion.core.CompanionCore._handle_file_operation')
    def test_file_operation_approval_integration(self, mock_handle):
        """Test that file operations go through approval system."""
        # Setup mock to approve
        self.mock_ui.show_approval_request.return_value = ApprovalResponse(
            approved=True,
            reason="User approved file creation",
            timestamp=time.time(),
            details={}
        )
        
        # Mock the actual file operation
        mock_handle.return_value = "File created successfully"
        
        # Simulate file creation request
        result = self.companion._handle_file_operation(
            'create_file',
            {
                'target': 'test_file.py',
                'file_path': os.path.join(self.temp_dir, 'test_file.py'),
                'content': 'print("Hello, World!")'
            }
        )
        
        # Verify approval was requested
        self.mock_ui.show_approval_request.assert_called_once()
        
        # Verify operation was executed after approval
        mock_handle.assert_called_once()
    
    def test_file_operation_rejection_handling(self):
        """Test handling of rejected file operations."""
        # Setup mock to reject
        self.mock_ui.show_approval_request.return_value = ApprovalResponse(
            approved=False,
            reason="User rejected file creation",
            timestamp=time.time(),
            details={}
        )
        
        # Create file ops with approval integration
        file_ops = SimpleFileOps()
        file_ops.approval_gate = self.companion.approval_gate
        
        # Attempt file creation
        result = file_ops.create_file(
            os.path.join(self.temp_dir, 'rejected_file.py'),
            'print("This should not be created")'
        )
        
        # Verify operation was rejected
        assert "rejected" in result.lower() or "denied" in result.lower()
        
        # Verify file was not created
        assert not os.path.exists(os.path.join(self.temp_dir, 'rejected_file.py'))
    
    def test_conversation_flow_with_approvals(self):
        """Test that conversation flow remains natural with approvals."""
        # Setup mock to approve
        self.mock_ui.show_approval_request.return_value = ApprovalResponse(
            approved=True,
            reason="User approved the operation",
            timestamp=time.time(),
            details={}
        )
        
        # Mock the process_message method to test conversation flow
        with patch.object(self.companion, 'process_message') as mock_process:
            mock_process.return_value = "I've created the file as requested."
            
            # Simulate user message requesting file creation
            response = self.companion.process_message(
                "Please create a Python script called hello.py that prints 'Hello, World!'"
            )
            
            # Verify response maintains natural conversation
            assert isinstance(response, str)
            assert len(response) > 0
            
            # Should not contain technical approval system details
            technical_terms = ['ApprovalGate', 'ApprovalResponse', 'risk_level']
            for term in technical_terms:
                assert term not in response
    
    def test_multiple_operations_approval_flow(self):
        """Test approval flow for multiple consecutive operations."""
        # Setup mock to approve all operations
        self.mock_ui.show_approval_request.return_value = ApprovalResponse(
            approved=True,
            reason="User approved operation",
            timestamp=time.time(),
            details={}
        )
        
        file_ops = SimpleFileOps()
        file_ops.approval_gate = self.companion.approval_gate
        
        # Perform multiple file operations
        operations = [
            ('create_file', os.path.join(self.temp_dir, 'file1.py'), 'content1'),
            ('create_file', os.path.join(self.temp_dir, 'file2.py'), 'content2'),
            ('write_file', os.path.join(self.temp_dir, 'file1.py'), 'modified content')
        ]
        
        results = []
        for op_type, file_path, content in operations:
            if op_type == 'create_file':
                result = file_ops.create_file(file_path, content)
            elif op_type == 'write_file':
                result = file_ops.write_file(file_path, content)
            results.append(result)
        
        # Verify all operations went through approval
        assert self.mock_ui.show_approval_request.call_count == 3
        
        # Verify all operations completed
        for result in results:
            assert result is not None
            assert "error" not in result.lower()


class TestFileOpsApprovalIntegration:
    """Test integration between SimpleFileOps and approval system."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.file_ops = SimpleFileOps()
        
        # Setup approval system
        config = ApprovalConfig(mode=ApprovalMode.STANDARD)
        self.file_ops.approval_gate = ApprovalGate(config=config)
        
        # Mock UI
        self.mock_ui = Mock(spec=UserApprovalUI)
        self.file_ops.approval_gate.set_approval_ui(self.mock_ui)
    
    def teardown_method(self):
        """Clean up temporary directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_create_file_with_approval(self):
        """Test file creation with approval system."""
        # Setup mock to approve
        self.mock_ui.show_approval_request.return_value = ApprovalResponse(
            approved=True,
            reason="User approved file creation",
            timestamp=time.time(),
            details={}
        )
        
        file_path = os.path.join(self.temp_dir, 'approved_file.py')
        content = 'print("This file was approved")'
        
        # Create file
        result = self.file_ops.create_file(file_path, content)
        
        # Verify approval was requested
        self.mock_ui.show_approval_request.assert_called_once()
        
        # Verify file was created
        assert os.path.exists(file_path)
        with open(file_path, 'r') as f:
            assert f.read() == content
        
        # Verify success message
        assert "success" in result.lower() or "created" in result.lower()
    
    def test_write_file_with_approval(self):
        """Test file writing with approval system."""
        # Create initial file
        file_path = os.path.join(self.temp_dir, 'test_file.py')
        with open(file_path, 'w') as f:
            f.write('initial content')
        
        # Setup mock to approve modification
        self.mock_ui.show_approval_request.return_value = ApprovalResponse(
            approved=True,
            reason="User approved file modification",
            timestamp=time.time(),
            details={}
        )
        
        new_content = 'modified content'
        
        # Modify file
        result = self.file_ops.write_file(file_path, new_content)
        
        # Verify approval was requested
        self.mock_ui.show_approval_request.assert_called_once()
        
        # Verify file was modified
        with open(file_path, 'r') as f:
            assert f.read() == new_content
        
        # Verify success message
        assert "success" in result.lower() or "written" in result.lower()
    
    def test_read_file_bypasses_approval(self):
        """Test that file reading bypasses approval system."""
        # Create test file
        file_path = os.path.join(self.temp_dir, 'read_test.py')
        content = 'test content for reading'
        with open(file_path, 'w') as f:
            f.write(content)
        
        # Read file
        result = self.file_ops.read_file(file_path)
        
        # Verify approval was not requested
        self.mock_ui.show_approval_request.assert_not_called()
        
        # Verify file content was returned
        assert content in result
    
    def test_list_files_bypasses_approval(self):
        """Test that file listing bypasses approval system."""
        # Create test files
        for i in range(3):
            file_path = os.path.join(self.temp_dir, f'test_file_{i}.py')
            with open(file_path, 'w') as f:
                f.write(f'content {i}')
        
        # List files
        result = self.file_ops.list_files(self.temp_dir)
        
        # Verify approval was not requested
        self.mock_ui.show_approval_request.assert_not_called()
        
        # Verify files were listed
        assert isinstance(result, str)
        assert 'test_file_0.py' in result
        assert 'test_file_1.py' in result
        assert 'test_file_2.py' in result
    
    def test_approval_timeout_handling(self):
        """Test handling of approval timeouts."""
        # Setup mock to timeout
        self.mock_ui.show_approval_request.side_effect = ApprovalTimeoutError(
            "Request timed out after 30 seconds"
        )
        
        file_path = os.path.join(self.temp_dir, 'timeout_file.py')
        
        # Attempt file creation
        result = self.file_ops.create_file(file_path, 'test content')
        
        # Verify operation was denied
        assert "timeout" in result.lower() or "denied" in result.lower()
        
        # Verify file was not created
        assert not os.path.exists(file_path)
    
    def test_approval_ui_error_handling(self):
        """Test handling of UI errors."""
        # Setup mock to raise UI error
        self.mock_ui.show_approval_request.side_effect = ApprovalUIError(
            "UI component failed"
        )
        
        file_path = os.path.join(self.temp_dir, 'ui_error_file.py')
        
        # Attempt file creation
        result = self.file_ops.create_file(file_path, 'test content')
        
        # Verify operation was denied
        assert "error" in result.lower() or "denied" in result.lower()
        
        # Verify file was not created
        assert not os.path.exists(file_path)


class TestApprovalModeIntegration:
    """Test integration of different approval modes."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.file_ops = SimpleFileOps()
        self.mock_ui = Mock(spec=UserApprovalUI)
    
    def teardown_method(self):
        """Clean up temporary directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_strict_mode_integration(self):
        """Test integration with strict approval mode."""
        # Setup strict mode
        config = ApprovalConfig(mode=ApprovalMode.STRICT)
        self.file_ops.approval_gate = ApprovalGate(config=config)
        self.file_ops.approval_gate.set_approval_ui(self.mock_ui)
        
        # Setup mock to approve
        self.mock_ui.show_approval_request.return_value = ApprovalResponse(
            approved=True,
            reason="User approved in strict mode",
            timestamp=time.time(),
            details={}
        )
        
        # Even read operations should require approval
        file_path = os.path.join(self.temp_dir, 'strict_test.py')
        with open(file_path, 'w') as f:
            f.write('test content')
        
        result = self.file_ops.read_file(file_path)
        
        # Verify approval was requested even for read
        self.mock_ui.show_approval_request.assert_called_once()
        
        # Verify operation completed
        assert 'test content' in result
    
    def test_trusted_mode_integration(self):
        """Test integration with trusted approval mode."""
        # Setup trusted mode
        config = ApprovalConfig(mode=ApprovalMode.TRUSTED)
        self.file_ops.approval_gate = ApprovalGate(config=config)
        self.file_ops.approval_gate.set_approval_ui(self.mock_ui)
        
        # High-risk operations should be auto-approved
        file_path = os.path.join(self.temp_dir, 'trusted_file.py')
        content = 'print("Trusted mode test")'
        
        result = self.file_ops.create_file(file_path, content)
        
        # Verify approval was not requested
        self.mock_ui.show_approval_request.assert_not_called()
        
        # Verify file was created
        assert os.path.exists(file_path)
        with open(file_path, 'r') as f:
            assert f.read() == content
    
    def test_mode_switching_integration(self):
        """Test switching between approval modes during operation."""
        # Start with standard mode
        config = ApprovalConfig(mode=ApprovalMode.STANDARD)
        self.file_ops.approval_gate = ApprovalGate(config=config)
        self.file_ops.approval_gate.set_approval_ui(self.mock_ui)
        
        # Setup mock to approve
        self.mock_ui.show_approval_request.return_value = ApprovalResponse(
            approved=True,
            reason="User approved",
            timestamp=time.time(),
            details={}
        )
        
        # Perform operation in standard mode
        file_path1 = os.path.join(self.temp_dir, 'standard_file.py')
        result1 = self.file_ops.create_file(file_path1, 'standard content')
        
        # Verify approval was requested
        assert self.mock_ui.show_approval_request.call_count == 1
        
        # Switch to trusted mode
        new_config = ApprovalConfig(mode=ApprovalMode.TRUSTED)
        self.file_ops.approval_gate.update_config(new_config)
        
        # Perform operation in trusted mode
        file_path2 = os.path.join(self.temp_dir, 'trusted_file.py')
        result2 = self.file_ops.create_file(file_path2, 'trusted content')
        
        # Verify no additional approval was requested
        assert self.mock_ui.show_approval_request.call_count == 1
        
        # Verify both files were created
        assert os.path.exists(file_path1)
        assert os.path.exists(file_path2)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])