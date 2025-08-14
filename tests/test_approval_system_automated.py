"""
Automated testing support for the approval system.

This module provides automated testing capabilities that can auto-approve
operations for testing purposes, while maintaining security and validation.
"""

import pytest
from unittest.mock import Mock, patch
import time
import threading
from companion.approval_system import (
    ApprovalGate, ApprovalConfig, ApprovalMode, ApprovalResponse,
    RiskLevel, OperationInfo, ApprovalRequest
)
from companion.approval_ui import UserApprovalUI


class AutoApprovalUI(UserApprovalUI):
    """Automated UI for testing that auto-approves based on configuration."""
    
    def __init__(self, auto_approve=True, approval_delay=0.0, risk_filter=None):
        """
        Initialize automated approval UI.
        
        Args:
            auto_approve: Whether to automatically approve requests
            approval_delay: Delay in seconds before responding
            risk_filter: List of risk levels to auto-approve (None = all)
        """
        super().__init__()
        self.auto_approve = auto_approve
        self.approval_delay = approval_delay
        self.risk_filter = risk_filter or [RiskLevel.LOW_RISK, RiskLevel.HIGH_RISK, RiskLevel.CRITICAL_RISK]
        self.request_history = []
    
    def show_approval_request(self, request: ApprovalRequest, session_id: str) -> ApprovalResponse:
        """Show approval request with automated response."""
        # Record request for testing validation
        self.request_history.append({
            'request': request,
            'session_id': session_id,
            'timestamp': time.time()
        })
        
        # Apply delay if specified
        if self.approval_delay > 0:
            time.sleep(self.approval_delay)
        
        # Check risk filter
        if request.operation_info.risk_level not in self.risk_filter:
            return ApprovalResponse(
                approved=False,
                reason=f"Auto-rejected: {request.operation_info.risk_level.value} not in approved risk levels",
                timestamp=time.time(),
                details={'auto_test': True, 'risk_filtered': True}
            )
        
        # Auto-approve or reject based on configuration
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
        """Get number of approval requests received."""
        return len(self.request_history)
    
    def get_last_request(self):
        """Get the last approval request received."""
        return self.request_history[-1] if self.request_history else None
    
    def clear_history(self):
        """Clear request history."""
        self.request_history.clear()


class TestAutomatedApprovalSystem:
    """Test automated approval system for testing scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = ApprovalConfig(mode=ApprovalMode.STANDARD)
        self.gate = ApprovalGate(config=self.config)
    
    def test_auto_approval_ui_basic(self):
        """Test basic auto-approval functionality."""
        # Setup auto-approval UI
        auto_ui = AutoApprovalUI(auto_approve=True)
        self.gate.set_approval_ui(auto_ui)
        
        # Request approval
        response = self.gate.request_approval(
            'create_file',
            {'target': 'test.py', 'file_path': 'test.py', 'content': 'test'},
            'test_session'
        )
        
        # Verify auto-approval
        assert response.approved is True
        assert "auto-approved" in response.reason.lower()
        assert response.details.get('auto_test') is True
        
        # Verify request was recorded
        assert auto_ui.get_request_count() == 1
        last_request = auto_ui.get_last_request()
        assert last_request['session_id'] == 'test_session'
    
    def test_auto_rejection_ui(self):
        """Test auto-rejection functionality."""
        # Setup auto-rejection UI
        auto_ui = AutoApprovalUI(auto_approve=False)
        self.gate.set_approval_ui(auto_ui)
        
        # Request approval
        response = self.gate.request_approval(
            'create_file',
            {'target': 'test.py', 'file_path': 'test.py', 'content': 'test'},
            'test_session'
        )
        
        # Verify auto-rejection
        assert response.approved is False
        assert "auto-rejected" in response.reason.lower()
        assert response.details.get('auto_test') is True
    
    def test_risk_level_filtering(self):
        """Test auto-approval with risk level filtering."""
        # Setup UI to only approve low-risk operations
        auto_ui = AutoApprovalUI(
            auto_approve=True,
            risk_filter=[RiskLevel.LOW_RISK]
        )
        self.gate.set_approval_ui(auto_ui)
        
        # Test low-risk operation (should be approved)
        response1 = self.gate.request_approval(
            'read_file',
            {'target': 'file.py', 'file_path': 'file.py'},
            'test_session'
        )
        
        # Test high-risk operation (should be rejected)
        response2 = self.gate.request_approval(
            'create_file',
            {'target': 'test.py', 'file_path': 'test.py', 'content': 'test'},
            'test_session'
        )
        
        # Verify filtering
        assert response1.approved is True  # Low risk approved
        assert response2.approved is False  # High risk rejected
        assert response2.details.get('risk_filtered') is True
    
    def test_approval_delay_simulation(self):
        """Test approval delay simulation for performance testing."""
        # Setup UI with delay
        delay_time = 0.1  # 100ms delay
        auto_ui = AutoApprovalUI(auto_approve=True, approval_delay=delay_time)
        self.gate.set_approval_ui(auto_ui)
        
        # Measure response time
        start_time = time.time()
        response = self.gate.request_approval(
            'create_file',
            {'target': 'test.py', 'file_path': 'test.py', 'content': 'test'},
            'test_session'
        )
        end_time = time.time()
        
        # Verify delay was applied
        actual_delay = end_time - start_time
        assert actual_delay >= delay_time
        assert response.approved is True
    
    def test_concurrent_auto_approvals(self):
        """Test concurrent auto-approvals for stress testing."""
        import queue
        
        # Setup auto-approval UI
        auto_ui = AutoApprovalUI(auto_approve=True)
        self.gate.set_approval_ui(auto_ui)
        
        # Create multiple threads making concurrent requests
        results = queue.Queue()
        num_threads = 10
        
        def make_request(thread_id):
            response = self.gate.request_approval(
                'create_file',
                {
                    'target': f'test_{thread_id}.py',
                    'file_path': f'test_{thread_id}.py',
                    'content': f'# Test file {thread_id}'
                },
                f'session_{thread_id}'
            )
            results.put((thread_id, response))
        
        # Start threads
        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=make_request, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify all requests were handled
        assert results.qsize() == num_threads
        assert auto_ui.get_request_count() == num_threads
        
        # Verify all were approved
        while not results.empty():
            thread_id, response = results.get()
            assert response.approved is True
            assert response.details.get('auto_test') is True


class TestApprovalSystemTestModes:
    """Test different testing modes for the approval system."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = ApprovalConfig(mode=ApprovalMode.STANDARD)
        self.gate = ApprovalGate(config=self.config)
    
    def test_testing_mode_configuration(self):
        """Test configuration of testing mode."""
        # Create testing configuration
        test_config = ApprovalConfig(
            mode=ApprovalMode.STANDARD,
            testing_mode=True,
            auto_approve_for_testing=True
        )
        
        test_gate = ApprovalGate(config=test_config)
        
        # In testing mode, should auto-approve without UI
        response = test_gate.request_approval(
            'create_file',
            {'target': 'test.py', 'file_path': 'test.py', 'content': 'test'},
            'test_session'
        )
        
        # Should be auto-approved
        assert response.approved is True
        assert "testing" in response.reason.lower()
    
    def test_selective_auto_approval(self):
        """Test selective auto-approval for specific operations."""
        # Setup UI that only approves file creation
        class SelectiveAutoUI(AutoApprovalUI):
            def show_approval_request(self, request, session_id):
                if request.operation_info.operation_type == 'create_file':
                    return ApprovalResponse(
                        approved=True,
                        reason="Auto-approved file creation",
                        timestamp=time.time(),
                        details={'auto_test': True, 'selective': True}
                    )
                else:
                    return ApprovalResponse(
                        approved=False,
                        reason="Auto-rejected non-creation operation",
                        timestamp=time.time(),
                        details={'auto_test': True, 'selective': True}
                    )
        
        selective_ui = SelectiveAutoUI()
        self.gate.set_approval_ui(selective_ui)
        
        # Test file creation (should be approved)
        response1 = self.gate.request_approval(
            'create_file',
            {'target': 'test.py', 'file_path': 'test.py', 'content': 'test'},
            'test_session'
        )
        
        # Test file writing (should be rejected)
        response2 = self.gate.request_approval(
            'write_file',
            {'target': 'test.py', 'file_path': 'test.py', 'content': 'modified'},
            'test_session'
        )
        
        # Verify selective approval
        assert response1.approved is True
        assert response1.details.get('selective') is True
        assert response2.approved is False
        assert response2.details.get('selective') is True
    
    def test_test_scenario_validation(self):
        """Test validation of test scenarios."""
        # Setup auto-approval UI with validation
        auto_ui = AutoApprovalUI(auto_approve=True)
        self.gate.set_approval_ui(auto_ui)
        
        # Define test scenario
        test_operations = [
            ('create_file', {'target': 'file1.py', 'content': 'test1'}),
            ('write_file', {'target': 'file1.py', 'content': 'modified'}),
            ('read_file', {'target': 'file1.py'}),
            ('create_file', {'target': 'file2.py', 'content': 'test2'})
        ]
        
        # Execute test scenario
        responses = []
        for operation, params in test_operations:
            response = self.gate.request_approval(
                operation,
                params,
                'test_scenario'
            )
            responses.append((operation, response))
        
        # Validate scenario execution
        assert len(responses) == len(test_operations)
        
        # Verify request history matches scenario
        assert auto_ui.get_request_count() == len(test_operations)
        
        # Verify operation types in history
        for i, (expected_op, _) in enumerate(test_operations):
            request_record = auto_ui.request_history[i]
            actual_op = request_record['request'].operation_info.operation_type
            assert actual_op == expected_op
    
    def test_performance_benchmarking(self):
        """Test performance benchmarking capabilities."""
        # Setup fast auto-approval UI
        auto_ui = AutoApprovalUI(auto_approve=True, approval_delay=0.001)  # 1ms delay
        self.gate.set_approval_ui(auto_ui)
        
        # Benchmark multiple operations
        num_operations = 100
        start_time = time.time()
        
        for i in range(num_operations):
            response = self.gate.request_approval(
                'create_file',
                {
                    'target': f'benchmark_{i}.py',
                    'file_path': f'benchmark_{i}.py',
                    'content': f'# Benchmark file {i}'
                },
                f'benchmark_session_{i}'
            )
            assert response.approved is True
        
        end_time = time.time()
        total_time = end_time - start_time
        avg_time_per_operation = total_time / num_operations
        
        # Verify performance metrics
        assert auto_ui.get_request_count() == num_operations
        assert avg_time_per_operation < 0.01  # Should be under 10ms per operation
        
        # Log performance results for analysis
        print(f"Processed {num_operations} operations in {total_time:.3f}s")
        print(f"Average time per operation: {avg_time_per_operation*1000:.2f}ms")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])