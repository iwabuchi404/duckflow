# tests/test_agent_state.py
"""
AgentStateクラスのテスト
"""
import pytest
from datetime import datetime
from codecrafter.state.agent_state import AgentState, ConversationMessage, TaskStep


class TestConversationMessage:
    """ConversationMessageクラスのテスト"""
    
    def test_conversation_message_creation(self):
        """ConversationMessage作成のテスト"""
        message = ConversationMessage(
            role="user",
            content="テストメッセージ"
        )
        
        assert message.role == "user"
        assert message.content == "テストメッセージ"
        assert isinstance(message.timestamp, datetime)
        assert message.metadata == {}
    
    def test_conversation_message_with_metadata(self):
        """メタデータ付きConversationMessage作成のテスト"""
        metadata = {"source": "test", "priority": "high"}
        message = ConversationMessage(
            role="assistant",
            content="応答メッセージ",
            metadata=metadata
        )
        
        assert message.role == "assistant"
        assert message.content == "応答メッセージ"
        assert message.metadata == metadata


class TestTaskStep:
    """TaskStepクラスのテスト"""
    
    def test_task_step_creation(self):
        """TaskStep作成のテスト"""
        step = TaskStep(
            id="step1",
            description="テストステップ"
        )
        
        assert step.id == "step1"
        assert step.description == "テストステップ"
        assert step.status == "pending"
        assert step.result is None
        assert step.error is None
        assert isinstance(step.created_at, datetime)
        assert step.completed_at is None
    
    def test_task_step_with_status(self):
        """ステータス指定のTaskStep作成のテスト"""
        step = TaskStep(
            id="step2",
            description="完了済みステップ",
            status="completed",
            result="成功"
        )
        
        assert step.status == "completed"
        assert step.result == "成功"


class TestAgentState:
    """AgentStateクラスのテスト"""
    
    def test_agent_state_creation(self):
        """AgentState作成のテスト"""
        state = AgentState(session_id="test-session")
        
        assert state.session_id == "test-session"
        assert state.conversation_history == []
        assert state.current_task is None
        assert state.task_steps == []
        assert isinstance(state.created_at, datetime)
        assert isinstance(state.last_activity, datetime)
        assert state.debug_mode is False
        assert state.auto_approve is False
    
    def test_add_message(self):
        """メッセージ追加のテスト"""
        state = AgentState(session_id="test-session")
        initial_activity = state.last_activity
        
        state.add_message("user", "こんにちは")
        
        assert len(state.conversation_history) == 1
        message = state.conversation_history[0]
        assert message.role == "user"
        assert message.content == "こんにちは"
        assert state.last_activity > initial_activity
    
    def test_add_message_with_metadata(self):
        """メタデータ付きメッセージ追加のテスト"""
        state = AgentState(session_id="test-session")
        metadata = {"command": "help"}
        
        state.add_message("user", "help", metadata)
        
        message = state.conversation_history[0]
        assert message.metadata == metadata
    
    def test_start_task(self):
        """タスク開始のテスト"""
        state = AgentState(session_id="test-session")
        
        # 既存のタスクステップを追加
        state.task_steps.append(TaskStep(id="old", description="古いステップ"))
        
        state.start_task("新しいタスク")
        
        assert state.current_task == "新しいタスク"
        assert len(state.task_steps) == 0  # クリアされる
    
    def test_add_task_step(self):
        """タスクステップ追加のテスト"""
        state = AgentState(session_id="test-session")
        
        step = state.add_task_step("step1", "最初のステップ")
        
        assert len(state.task_steps) == 1
        assert step.id == "step1"
        assert step.description == "最初のステップ"
        assert state.task_steps[0] == step
    
    def test_update_task_step(self):
        """タスクステップ更新のテスト"""
        state = AgentState(session_id="test-session")
        step = state.add_task_step("step1", "テストステップ")
        
        success = state.update_task_step("step1", "completed", "成功")
        
        assert success is True
        assert step.status == "completed"
        assert step.result == "成功"
        assert step.completed_at is not None
    
    def test_update_nonexistent_task_step(self):
        """存在しないタスクステップ更新のテスト"""
        state = AgentState(session_id="test-session")
        
        success = state.update_task_step("nonexistent", "completed")
        
        assert success is False
    
    def test_get_recent_messages(self):
        """最近のメッセージ取得のテスト"""
        state = AgentState(session_id="test-session")
        
        # 複数メッセージを追加
        for i in range(15):
            state.add_message("user", f"メッセージ {i}")
        
        # デフォルト（10件）取得
        recent = state.get_recent_messages()
        assert len(recent) == 10
        assert recent[0].content == "メッセージ 5"
        assert recent[-1].content == "メッセージ 14"
        
        # 5件取得
        recent5 = state.get_recent_messages(5)
        assert len(recent5) == 5
        assert recent5[0].content == "メッセージ 10"
    
    def test_get_recent_messages_fewer_than_limit(self):
        """制限数未満のメッセージ取得のテスト"""
        state = AgentState(session_id="test-session")
        
        # 3件だけ追加
        for i in range(3):
            state.add_message("user", f"メッセージ {i}")
        
        recent = state.get_recent_messages(10)
        assert len(recent) == 3
    
    def test_get_active_task_steps(self):
        """アクティブなタスクステップ取得のテスト"""
        state = AgentState(session_id="test-session")
        
        # 異なるステータスのステップを追加
        state.add_task_step("pending", "待機中")
        state.add_task_step("in_progress", "実行中")
        state.add_task_step("completed", "完了済み")
        
        # completedステップを更新
        state.update_task_step("completed", "completed")
        
        active_steps = state.get_active_task_steps()
        assert len(active_steps) == 2
        active_ids = [step.id for step in active_steps]
        assert "pending" in active_ids
        assert "in_progress" in active_ids
        assert "completed" not in active_ids