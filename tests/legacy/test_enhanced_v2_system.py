#!/usr/bin/env python3
"""
Enhanced v2.0システム動作テスト

リファクタリング完了後のEnhanced v2.0システムの動作を
包括的にテストするスクリプト。
"""

import sys
import queue
import threading
import time
import logging
import asyncio
from typing import Optional, Dict, Any

# Enhanced v2.0システムのインポート
from companion.enhanced.chat_loop import EnhancedChatLoop
from companion.enhanced.task_loop import EnhancedTaskLoop
from companion.state.enums import Step, Status

# テスト用のログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class TestResults:
    """テスト結果を記録するクラス"""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results = []
    
    def add_result(self, test_name: str, success: bool, message: str = ""):
        result = {
            'test': test_name,
            'success': success,
            'message': message,
            'timestamp': time.time()
        }
        self.results.append(result)
        
        if success:
            self.passed += 1
            print(f"✅ {test_name}: PASS {message}")
        else:
            self.failed += 1
            print(f"❌ {test_name}: FAIL {message}")
    
    def print_summary(self):
        total = self.passed + self.failed
        success_rate = (self.passed / total * 100) if total > 0 else 0
        
        print("\n" + "=" * 60)
        print("🧪 Enhanced v2.0システム動作テスト結果")
        print("=" * 60)
        print(f"総テスト数: {total}")
        print(f"成功: {self.passed}")
        print(f"失敗: {self.failed}")
        print(f"成功率: {success_rate:.1f}%")
        print("=" * 60)

class MockAgentState:
    """テスト用のAgentStateモック"""
    def __init__(self):
        self.step = Step.IDLE
        self.status = Status.PENDING
        self.goal = "テスト目標"
        self.why_now = "動作テストのため"
        self.constraints = ["テスト環境での実行"]
        self.plan_brief = ["Enhanced v2.0の動作確認"]
        self.open_questions = ["全機能が正常に動作するか"]
        self.session_id = "test-session-enhanced-v2"
        
    def set_step_status(self, step: Step, status: Status):
        """ステップとステータスを設定"""
        self.step = step
        self.status = status
        print(f"   📊 AgentState更新: {step.value}.{status.value}")
    
    def get_context_summary(self) -> Dict[str, Any]:
        """コンテキストサマリーを返す"""
        return {
            'goal': self.goal,
            'why_now': self.why_now,
            'constraints': self.constraints,
            'plan_brief': self.plan_brief,
            'open_questions': self.open_questions,
            'current_step': self.step.value,
            'current_status': self.status.value,
            'last_delta': 'テスト実行中',
            'conversation_count': 1,
            'created_at': '2025-01-20',
            'vitals': {'mood': '良好', 'focus': '集中', 'stamina': '満タン'}
        }

class MockEnhancedCompanion:
    """テスト用のEnhancedCompanionモック"""
    def __init__(self):
        self.agent_state = MockAgentState()
    
    def get_agent_state(self):
        return self.agent_state
    
    async def analyze_intent_only(self, user_input: str):
        """意図分析のモック"""
        return {
            'intent': 'test_intent',
            'confidence': 0.95,
            'parameters': {'input': user_input}
        }
    
    async def process_with_intent_result(self, intent_result):
        """意図処理のモック"""
        await asyncio.sleep(0.1)  # 非同期処理のシミュレート
        return f"処理完了: {intent_result.get('intent', 'unknown')}"

class MockDualLoopSystem:
    """テスト用のDualLoopSystemモック"""
    def __init__(self):
        self.session_id = "test-dual-loop-system"
        self.agent_state = MockAgentState()
    
    def get_current_state(self) -> str:
        return f"{self.agent_state.step.value}.{self.agent_state.status.value}"

def test_enhanced_chat_loop_basic(results: TestResults):
    """EnhancedChatLoopの基本動作テスト"""
    try:
        task_queue = queue.Queue()
        status_queue = queue.Queue()
        enhanced_companion = MockEnhancedCompanion()
        dual_loop_system = MockDualLoopSystem()
        
        chat_loop = EnhancedChatLoop(task_queue, status_queue, enhanced_companion, dual_loop_system)
        
        # 基本属性の確認
        assert hasattr(chat_loop, 'agent_state'), "agent_state属性が存在しない"
        assert hasattr(chat_loop, '_handle_enhanced_command'), "_handle_enhanced_command メソッドが存在しない"
        assert hasattr(chat_loop, '_show_enhanced_status'), "_show_enhanced_status メソッドが存在しない"
        assert hasattr(chat_loop, '_show_detailed_state'), "_show_detailed_state メソッドが存在しない"
        
        # AgentState参照の確認
        assert chat_loop.agent_state is dual_loop_system.agent_state, "AgentStateの参照が正しくない"
        
        results.add_result("EnhancedChatLoop基本動作", True, "インスタンス化とメソッド存在確認")
        
    except Exception as e:
        results.add_result("EnhancedChatLoop基本動作", False, f"エラー: {e}")

def test_enhanced_task_loop_basic(results: TestResults):
    """EnhancedTaskLoopの基本動作テスト"""
    try:
        task_queue = queue.Queue()
        status_queue = queue.Queue()
        enhanced_companion = MockEnhancedCompanion()
        dual_loop_system = MockDualLoopSystem()
        
        task_loop = EnhancedTaskLoop(task_queue, status_queue, enhanced_companion, dual_loop_system)
        
        # 基本属性の確認
        assert hasattr(task_loop, 'agent_state'), "agent_state属性が存在しない"
        assert hasattr(task_loop, '_execute_enhanced_task'), "_execute_enhanced_task メソッドが存在しない"
        assert hasattr(task_loop, '_process_enhanced_intent'), "_process_enhanced_intent メソッドが存在しない"
        assert hasattr(task_loop, '_update_agent_state_step'), "_update_agent_state_step メソッドが存在しない"
        
        # AgentState参照の確認
        assert task_loop.agent_state is dual_loop_system.agent_state, "AgentStateの参照が正しくない"
        
        results.add_result("EnhancedTaskLoop基本動作", True, "インスタンス化とメソッド存在確認")
        
    except Exception as e:
        results.add_result("EnhancedTaskLoop基本動作", False, f"エラー: {e}")

def test_agent_state_unification(results: TestResults):
    """AgentState統一状態管理テスト"""
    try:
        task_queue = queue.Queue()
        status_queue = queue.Queue()
        enhanced_companion = MockEnhancedCompanion()
        dual_loop_system = MockDualLoopSystem()
        
        chat_loop = EnhancedChatLoop(task_queue, status_queue, enhanced_companion, dual_loop_system)
        task_loop = EnhancedTaskLoop(task_queue, status_queue, enhanced_companion, dual_loop_system)
        
        # 同一AgentStateインスタンスの確認
        assert chat_loop.agent_state is task_loop.agent_state, "ChatLoopとTaskLoopで異なるAgentState"
        assert chat_loop.agent_state is dual_loop_system.agent_state, "ChatLoopとDualLoopSystemで異なるAgentState"
        assert task_loop.agent_state is dual_loop_system.agent_state, "TaskLoopとDualLoopSystemで異なるAgentState"
        
        # 状態変更の同期確認
        original_step = dual_loop_system.agent_state.step
        original_status = dual_loop_system.agent_state.status
        
        # TaskLoopから状態を変更
        task_loop._update_agent_state_step(Step.EXECUTION, Status.IN_PROGRESS)
        
        # 全てのループで同じ状態が参照されることを確認
        assert chat_loop.agent_state.step == Step.EXECUTION, "ChatLoopの状態が更新されていない"
        assert task_loop.agent_state.step == Step.EXECUTION, "TaskLoopの状態が更新されていない"
        assert dual_loop_system.agent_state.step == Step.EXECUTION, "DualLoopSystemの状態が更新されていない"
        
        results.add_result("AgentState統一状態管理", True, "状態同期とインスタンス統一確認")
        
    except Exception as e:
        results.add_result("AgentState統一状態管理", False, f"エラー: {e}")

def test_queue_communication(results: TestResults):
    """キュー通信テスト"""
    try:
        task_queue = queue.Queue()
        status_queue = queue.Queue()
        enhanced_companion = MockEnhancedCompanion()
        dual_loop_system = MockDualLoopSystem()
        
        chat_loop = EnhancedChatLoop(task_queue, status_queue, enhanced_companion, dual_loop_system)
        task_loop = EnhancedTaskLoop(task_queue, status_queue, enhanced_companion, dual_loop_system)
        
        # タスクキューへのメッセージ送信
        test_task = {
            'type': 'update_agent_state',
            'step': Step.PLANNING,
            'status': Status.IN_PROGRESS
        }
        task_queue.put(test_task)
        
        # タスクキューからの受信確認
        received_task = task_queue.get_nowait()
        assert received_task == test_task, "タスクキューの通信が正しくない"
        
        # ステータスキューへのメッセージ送信
        test_status = {
            'type': 'test_status',
            'message': 'テストメッセージ'
        }
        status_queue.put(test_status)
        
        # ステータスキューからの受信確認
        received_status = status_queue.get_nowait()
        assert received_status == test_status, "ステータスキューの通信が正しくない"
        
        results.add_result("キュー通信", True, "TaskQueueとStatusQueueの通信確認")
        
    except Exception as e:
        results.add_result("キュー通信", False, f"エラー: {e}")

def test_error_handling(results: TestResults):
    """エラーハンドリングテスト"""
    try:
        task_queue = queue.Queue()
        status_queue = queue.Queue()
        enhanced_companion = MockEnhancedCompanion()
        dual_loop_system = MockDualLoopSystem()
        
        task_loop = EnhancedTaskLoop(task_queue, status_queue, enhanced_companion, dual_loop_system)
        
        # 不正なタスクデータでのエラーハンドリング
        invalid_task = {
            'type': 'invalid_task_type',
            'invalid_data': 'test'
        }
        
        # エラーハンドリングが正常に動作することを確認
        try:
            # タスクをキューに追加してから処理
            task_queue.put(invalid_task)
            task_loop._execute_enhanced_task(invalid_task)
            # エラーが発生せずに処理が完了することを確認
            results.add_result("エラーハンドリング", True, "不正なタスクタイプの処理")
        except Exception as e:
            results.add_result("エラーハンドリング", False, f"予期しないエラー: {e}")
            
    except Exception as e:
        results.add_result("エラーハンドリング", False, f"セットアップエラー: {e}")

def main():
    """メインテスト関数"""
    print("🚀 Enhanced v2.0システム動作テスト開始")
    print("=" * 60)
    
    results = TestResults()
    
    # Test 1: Enhanced専用ループの基本動作テスト
    print("\n📋 Test 1: Enhanced専用ループの基本動作テスト")
    test_enhanced_chat_loop_basic(results)
    test_enhanced_task_loop_basic(results)
    
    # Test 2: AgentState統一状態管理テスト
    print("\n📋 Test 2: AgentState統一状態管理テスト")
    test_agent_state_unification(results)
    
    # Test 3: キュー通信テスト
    print("\n📋 Test 3: キュー通信テスト")
    test_queue_communication(results)
    
    # Test 4: エラーハンドリングテスト
    print("\n📋 Test 4: エラーハンドリングテスト")
    test_error_handling(results)
    
    # 結果サマリー
    results.print_summary()
    
    # 終了コード
    sys.exit(0 if results.failed == 0 else 1)

if __name__ == "__main__":
    main()
