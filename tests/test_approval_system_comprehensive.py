"""
Comprehensive test suite for the user approval system.

This module contains integration tests that validate the complete approval system
workflow, including all components working together, security measures, and
user experience flows.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import time
from companion.approval_system import (
    ApprovalGate, ApprovalConfig, ApprovalMode, RiskLevel,
    OperationInfo, ApprovalRequest, ApprovalResponse,
    OperationAnalyzer, ApprovalTimeoutError, ApprovalUIError,
    SecurityViolationError
)
from companion.approval_ui import UserApprovalUI
from companion.approval_response_handler import ApprovalResponseHandler


class TestComprehensiveApprovalWorkflow:
    """Test complete approval workflows from start to finish."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = ApprovalConfig(mode=ApprovalMode.STANDARD)
        self.gate = ApprovalGate(config=self.config)
        self.mock_ui = Mock(spec=UserApprovalUI)
        self.gate.set_approval_ui(self.mock_ui)
    
    def test_complete_file_creation_approval_workflow(self):
        """Test complete workflow for file creation approval."""
        # Setup mock UI to approve
        self.mock_ui.show_approval_request.return_value = ApprovalResponse(
            approved=True,
            reason="User approved file creation",
            timestamp=time.time(),
            details={}
        )
        
        # Request approval for file creation
        response = self.gate.request_approval(
            'create_file',
            {
                'target': 'new_file.py',
                'file_path': 'new_file.py',
                'content': 'print("Hello, World!")'
            },
            'test_session'
        )
        
        # Verify approval workflow
        assert response.approved is True
        assert "User approved" in response.reason
        assert response.timestamp > 0
        
        # Verify UI was called with correct parameters
        self.mock_ui.show_approval_request.assert_called_once()
        call_args = self.mock_ui.show_approval_request.call_args[0]
        request = call_args[0]
        
        assert isinstance(request, ApprovalRequest)
        assert request.operation_info.operation_type == 'create_file'
        assert request.operation_info.risk_level == RiskLevel.HIGH_RISK
        assert 'new_file.py' in request.operation_info.description
    
    def test_complete_file_modification_rejection_workflow(self):
        """Test complete workflow for file modification rejection."""
        # Setup mock UI to reject
        self.mock_ui.show_approval_request.return_value = ApprovalResponse(
            approved=False,
            reason="User rejected file modification",
            timestamp=time.time(),
            details={}
        )
        
        # Request approval for file modification
        response = self.gate.request_approval(
            'write_file',
            {
                'target': 'existing_file.py',
                'file_path': 'existing_file.py',
                'content': 'modified content'
            },
            'test_session'
        )
        
        # Verify rejection workflow
        assert response.approved is False
        assert "User rejected" in response.reason
        assert response.timestamp > 0
        
        # Verify UI interaction
        self.mock_ui.show_approval_request.assert_called_once()
    
    def test_low_risk_operation_bypass(self):
        """Test that low-risk operations bypass approval."""
        # Request approval for read operation (should bypass)
        response = self.gate.request_approval(
            'read_file',
            {'target': 'file.py', 'file_path': 'file.py'},
            'test_session'
        )
        
        # Verify automatic approval
        assert response.approved is True
        assert "low risk" in response.reason.lower()
        
        # Verify UI was not called
        self.mock_ui.show_approval_request.assert_not_called()
    
    def test_strict_mode_workflow(self):
        """Test approval workflow in strict mode."""
        # Switch to strict mode
        strict_config = ApprovalConfig(mode=ApprovalMode.STRICT)
        strict_gate = ApprovalGate(config=strict_config)
        strict_gate.set_approval_ui(self.mock_ui)
        
        # Setup mock UI to approve
        self.mock_ui.show_approval_request.return_value = ApprovalResponse(
            approved=True,
            reason="User approved in strict mode",
            timestamp=time.time(),
            details={}
        )
        
        # Even read operations should require approval in strict mode
        response = strict_gate.request_approval(
            'read_file',
            {'target': 'file.py', 'file_path': 'file.py'},
            'test_session'
        )
        
        # Verify approval was required
        assert response.approved is True
        self.mock_ui.show_approval_request.assert_called_once()
    
    def test_trusted_mode_workflow(self):
        """Test approval workflow in trusted mode."""
        # Switch to trusted mode
        trusted_config = ApprovalConfig(mode=ApprovalMode.TRUSTED)
        trusted_gate = ApprovalGate(config=trusted_config)
        trusted_gate.set_approval_ui(self.mock_ui)
        
        # Even high-risk operations should be auto-approved in trusted mode
        response = trusted_gate.request_approval(
            'create_file',
            {
                'target': 'new_file.py',
                'file_path': 'new_file.py',
                'content': 'print("Hello")'
            },
            'test_session'
        )
        
        # Verify automatic approval
        assert response.approved is True
        assert "trusted mode" in response.reason.lower()
        
        # Verify UI was not called
        self.mock_ui.show_approval_request.assert_not_called()


class TestApprovalSystemSecurity:
    """Test security measures and bypass prevention."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = ApprovalConfig(mode=ApprovalMode.STANDARD)
        self.gate = ApprovalGate(config=self.config)
        self.mock_ui = Mock(spec=UserApprovalUI)
        self.gate.set_approval_ui(self.mock_ui)
    
    def test_bypass_attempt_detection(self):
        """Test detection of approval bypass attempts."""
        # Attempt to bypass by not setting UI
        gate_no_ui = ApprovalGate(config=self.config)
        
        # Should fail safely
        response = gate_no_ui.request_approval(
            'create_file',
            {'target': 'test.py', 'file_path': 'test.py', 'content': 'test'},
            'test_session'
        )
        
        assert response.approved is False
        assert "fail-safe" in response.reason.lower()
        assert response.details.get('fail_safe_triggered') is True
    
    def test_malicious_operation_detection(self):
        """Test detection of potentially malicious operations."""
        # Test with suspicious file paths
        suspicious_operations = [
            {
                'operation': 'create_file',
                'params': {
                    'target': '/etc/passwd',
                    'file_path': '/etc/passwd',
                    'content': 'malicious content'
                }
            },
            {
                'operation': 'write_file',
                'params': {
                    'target': '~/.ssh/authorized_keys',
                    'file_path': '~/.ssh/authorized_keys',
                    'content': 'ssh-rsa malicious_key'
                }
            }
        ]
        
        for op in suspicious_operations:
            response = self.gate.request_approval(
                op['operation'],
                op['params'],
                'test_session'
            )
            
            # Should be classified as critical risk
            self.mock_ui.show_approval_request.assert_called()
            call_args = self.mock_ui.show_approval_request.call_args[0]
            request = call_args[0]
            
            assert request.operation_info.risk_level == RiskLevel.CRITICAL_RISK
            self.mock_ui.reset_mock()
    
    def test_fail_safe_on_analyzer_error(self):
        """Test fail-safe behavior when operation analyzer fails."""
        # Mock analyzer to raise exception
        with patch.object(self.gate.analyzer, 'analyze_operation') as mock_analyze:
            mock_analyze.side_effect = Exception("Analyzer error")
            
            response = self.gate.request_approval(
                'create_file',
                {'target': 'test.py', 'file_path': 'test.py', 'content': 'test'},
                'test_session'
            )
            
            # Should fail safely
            assert response.approved is False
            assert "fail-safe" in response.reason.lower()
            assert response.details.get('fail_safe_triggered') is True
    
    def test_fail_safe_on_ui_error(self):
        """Test fail-safe behavior when UI fails."""
        # Mock UI to raise exception
        self.mock_ui.show_approval_request.side_effect = Exception("UI error")
        
        response = self.gate.request_approval(
            'create_file',
            {'target': 'test.py', 'file_path': 'test.py', 'content': 'test'},
            'test_session'
        )
        
        # Should fail safely
        assert response.approved is False
        assert "fail-safe" in response.reason.lower()
        assert response.details.get('fail_safe_triggered') is True


class TestApprovalSystemPerformance:
    """Test performance characteristics of the approval system."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = ApprovalConfig(mode=ApprovalMode.STANDARD)
        self.gate = ApprovalGate(config=self.config)
        self.mock_ui = Mock(spec=UserApprovalUI)
        self.gate.set_approval_ui(self.mock_ui)
    
    def test_approval_response_time(self):
        """Test that approval requests are processed quickly."""
        # Setup mock UI with instant response
        self.mock_ui.show_approval_request.return_value = ApprovalResponse(
            approved=True,
            reason="Quick approval",
            timestamp=time.time(),
            details={}
        )
        
        # Measure response time
        start_time = time.time()
        response = self.gate.request_approval(
            'create_file',
            {'target': 'test.py', 'file_path': 'test.py', 'content': 'test'},
            'test_session'
        )
        end_time = time.time()
        
        # Should be very fast (under 100ms for processing)
        processing_time = end_time - start_time
        assert processing_time < 0.1  # 100ms
        assert response.approved is True
    
    def test_low_risk_bypass_performance(self):
        """Test that low-risk operations are processed very quickly."""
        # Measure bypass time
        start_time = time.time()
        response = self.gate.request_approval(
            'read_file',
            {'target': 'file.py', 'file_path': 'file.py'},
            'test_session'
        )
        end_time = time.time()
        
        # Should be extremely fast (under 10ms)
        processing_time = end_time - start_time
        assert processing_time < 0.01  # 10ms
        assert response.approved is True
    
    def test_multiple_concurrent_requests(self):
        """Test handling of multiple concurrent approval requests."""
        import threading
        import queue
        
        # Setup mock UI
        self.mock_ui.show_approval_request.return_value = ApprovalResponse(
            approved=True,
            reason="Concurrent approval",
            timestamp=time.time(),
            details={}
        )
        
        # Create multiple threads making approval requests
        results = queue.Queue()
        
        def make_request(request_id):
            response = self.gate.request_approval(
                'create_file',
                {
                    'target': f'test_{request_id}.py',
                    'file_path': f'test_{request_id}.py',
                    'content': f'# Test file {request_id}'
                },
                f'session_{request_id}'
            )
            results.put((request_id, response))
        
        # Start multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=make_request, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all requests were handled
        assert results.qsize() == 5
        while not results.empty():
            request_id, response = results.get()
            assert response.approved is True


class TestApprovalSystemUsability:
    """Test user experience and usability aspects."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = ApprovalConfig(mode=ApprovalMode.STANDARD)
        self.gate = ApprovalGate(config=self.config)
        self.real_ui = UserApprovalUI()
        self.gate.set_approval_ui(self.real_ui)
    
    def test_operation_description_clarity(self):
        """Test that operation descriptions are clear and user-friendly."""
        analyzer = OperationAnalyzer()
        
        # Test various operations
        operations = [
            ('create_file', {
                'target': 'new_script.py',
                'file_path': 'scripts/new_script.py',
                'content': 'print("Hello, World!")'
            }),
            ('write_file', {
                'target': 'config.json',
                'file_path': 'config/config.json',
                'content': '{"setting": "value"}'
            }),
            ('read_file', {
                'target': 'data.txt',
                'file_path': 'data/data.txt'
            })
        ]
        
        for operation, params in operations:
            info = analyzer.analyze_operation(operation, params)
            
            # Description should be clear and informative
            assert len(info.description) > 20  # Reasonable length
            assert info.target in info.description  # Contains target
            assert operation.replace('_', ' ') in info.description.lower()
            
            # Should not contain technical jargon
            technical_terms = ['params', 'dict', 'kwargs', 'args']
            for term in technical_terms:
                assert term not in info.description.lower()
    
    def test_risk_level_communication(self):
        """Test that risk levels are communicated appropriately."""
        analyzer = OperationAnalyzer()
        
        # Test risk level descriptions
        risk_operations = [
            ('read_file', {'target': 'file.txt'}, RiskLevel.LOW_RISK),
            ('create_file', {'target': 'new.py', 'content': 'code'}, RiskLevel.HIGH_RISK),
            ('write_file', {'target': '/etc/passwd', 'content': 'root:x:0:0'}, RiskLevel.CRITICAL_RISK)
        ]
        
        for operation, params, expected_risk in risk_operations:
            info = analyzer.analyze_operation(operation, params)
            assert info.risk_level == expected_risk
            
            # Risk should be reflected in description appropriately
            if expected_risk == RiskLevel.CRITICAL_RISK:
                risk_indicators = ['critical', 'dangerous', 'system', 'security']
                assert any(indicator in info.description.lower() for indicator in risk_indicators)
    
    @patch('builtins.input')
    def test_natural_language_responses(self, mock_input):
        """Test that the system uses natural language in responses."""
        # Mock user input for approval
        mock_input.return_value = 'y'
        
        # Create a request that will show natural language
        response = self.gate.request_approval(
            'create_file',
            {
                'target': 'test_script.py',
                'file_path': 'test_script.py',
                'content': 'print("Testing natural language")'
            },
            'test_session'
        )
        
        # Response should use natural language
        assert response.approved is True
        natural_indicators = ['approved', 'allowed', 'permitted', 'user']
        assert any(indicator in response.reason.lower() for indicator in natural_indicators)
        
        # Should not contain technical error codes or jargon
        technical_terms = ['0x', 'errno', 'exception', 'traceback']
        for term in technical_terms:
            assert term not in response.reason.lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])