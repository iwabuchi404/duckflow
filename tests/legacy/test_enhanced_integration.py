#!/usr/bin/env python3
"""
Enhanced v2.0システム統合テスト（LLM設定不要版）

Enhanced専用ループの統合動作をLLM設定なしでテストします。
"""

import sys
import queue
import threading
import time
import logging
import asyncio
from typing import Optional, Dict, Any

# Enhanced v2.0システムのインポート（LLM不要）
from companion.enhanced.chat_loop import EnhancedChatLoop
from companion.enhanced.task_loop import EnhancedTaskLoop
from companion.state.enums import Step, Status

# テスト用のログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class IntegrationTestResults:
    """統合テスト結果を記録するクラス"""
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
        print("🧪 Enhanced v2.0システム統合テスト結果")
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
        self.goal = "統合テスト目標"
        self.why_now = "Enhanced v2.0統合動作確認"
        self.constraints = ["LLM設定なし", "モックデータ使用"]
        self.plan_brief = ["統合テストの実行", "状態同期の確認"]
        self.open_questions = ["全コンポーネントが正常連携するか"]
        self.session_id = "integration-test-session"
        
    def set_step_status(self, step: Step, status: Status):
        """ステップとステータスを設定"""
        old_step, old_status = self.step, self.status
        self.step = step
        self.status = status
        print(f"   📊 AgentState更新: {old_step.value}.{old_status.value} → {step.value}.{status.value}")
    
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
            'last_delta': '統合テスト実行中',
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
        await asyncio.sleep(0.1)  # 非同期処理のシミュレート
        return {
            'intent': 'test_integration',
            'confidence': 0.95,
            'parameters': {'input': user_input, 'test_mode': True}
        }
    
    async def process_with_intent_result(self, intent_result):
        """意図処理のモック"""
        await asyncio.sleep(0.2)  # 非同期処理のシミュレート
        intent = intent_result.get('intent', 'unknown')
        return f"統合テスト処理完了: {intent}"

class MockDualLoopSystem:
    """テスト用のDualLoopSystemモック"""
    def __init__(self):
        self.session_id = "mock-dual-loop-system"
        self.enhanced_companion = MockEnhancedCompanion()
        self.agent_state = self.enhanced_companion.get_agent_state()
        self.running = False
    
    def get_current_state(self) -> str:
        return f"{self.agent_state.step.value}.{self.agent_state.status.value}"

def test_dual_loop_integration(results: IntegrationTestResults):
    """Dual-Loop統合テスト"""
    try:
        print("   🔄 Dual-Loop統合システム構築中...")
        
        # システム構築
        task_queue = queue.Queue()
        status_queue = queue.Queue()
        dual_loop_system = MockDualLoopSystem()
        
        chat_loop = EnhancedChatLoop(
            task_queue, status_queue, 
            dual_loop_system.enhanced_companion, 
            dual_loop_system
        )
        task_loop = EnhancedTaskLoop(
            task_queue, status_queue, 
            dual_loop_system.enhanced_companion, 
            dual_loop_system
        )
        
        # 統合確認
        assert chat_loop.agent_state is task_loop.agent_state, "AgentStateが統一されていない"
        assert chat_loop.agent_state is dual_loop_system.agent_state, "DualLoopSystemとの統合が不正"
        
        results.add_result("Dual-Loop統合", True, "システム構築と統合確認")
        
    except Exception as e:
        results.add_result("Dual-Loop統合", False, f"エラー: {e}")

def test_task_processing_flow(results: IntegrationTestResults):
    """タスク処理フロー統合テスト"""
    try:
        print("   🔄 タスク処理フロー統合テスト実行中...")
        
        # システム構築
        task_queue = queue.Queue()
        status_queue = queue.Queue()
        dual_loop_system = MockDualLoopSystem()
        
        chat_loop = EnhancedChatLoop(
            task_queue, status_queue, 
            dual_loop_system.enhanced_companion, 
            dual_loop_system
        )
        task_loop = EnhancedTaskLoop(
            task_queue, status_queue, 
            dual_loop_system.enhanced_companion, 
            dual_loop_system
        )
        
        # 初期状態確認
        initial_state = dual_loop_system.get_current_state()
        print(f"   📊 初期状態: {initial_state}")
        
        # タスクの作成と処理
        test_task = {
            'type': 'update_agent_state',
            'step': Step.PLANNING,
            'status': Status.IN_PROGRESS,
            'fixed_five': {
                'goal': '統合テスト実行',
                'why_now': 'システム動作確認',
                'constraints': ['テスト環境'],
                'plan_brief': ['統合テスト'],
                'open_questions': ['正常動作確認']
            }
        }
        
        # タスクキューに追加
        task_queue.put(test_task)
        
        # TaskLoopでタスク処理
        task_loop._execute_enhanced_task(test_task)
        
        # 状態変更確認
        updated_state = dual_loop_system.get_current_state()
        print(f"   📊 更新後状態: {updated_state}")
        
        # ChatLoopでも同じ状態が参照されることを確認
        chat_state = f"{chat_loop.agent_state.step.value}.{chat_loop.agent_state.status.value}"
        assert updated_state == chat_state, f"状態同期エラー: {updated_state} != {chat_state}"
        
        results.add_result("タスク処理フロー統合", True, f"状態変更: {initial_state} → {updated_state}")
        
    except Exception as e:
        results.add_result("タスク処理フロー統合", False, f"エラー: {e}")

def test_concurrent_operations(results: IntegrationTestResults):
    """並行操作統合テスト"""
    try:
        print("   🔄 並行操作統合テスト実行中...")
        
        # システム構築
        task_queue = queue.Queue()
        status_queue = queue.Queue()
        dual_loop_system = MockDualLoopSystem()
        
        chat_loop = EnhancedChatLoop(
            task_queue, status_queue, 
            dual_loop_system.enhanced_companion, 
            dual_loop_system
        )
        task_loop = EnhancedTaskLoop(
            task_queue, status_queue, 
            dual_loop_system.enhanced_companion, 
            dual_loop_system
        )
        
        # 複数のタスクを並行処理
        tasks = [
            {
                'type': 'update_agent_state',
                'step': Step.PLANNING,
                'status': Status.IN_PROGRESS
            },
            {
                'type': 'update_agent_state',
                'step': Step.EXECUTION,
                'status': Status.IN_PROGRESS
            },
            {
                'type': 'update_agent_state',
                'step': Step.REVIEW,
                'status': Status.SUCCESS
            }
        ]
        
        # タスクを順次処理
        for i, task in enumerate(tasks):
            print(f"   📋 タスク {i+1} 処理中...")
            task_queue.put(task)
            task_loop._execute_enhanced_task(task)
            
            # 状態確認
            current_state = dual_loop_system.get_current_state()
            expected_step = task['step'].value
            expected_status = task['status'].value
            expected_state = f"{expected_step}.{expected_status}"
            
            assert current_state == expected_state, f"状態不一致: {current_state} != {expected_state}"
        
        final_state = dual_loop_system.get_current_state()
        results.add_result("並行操作統合", True, f"最終状態: {final_state}")
        
    except Exception as e:
        results.add_result("並行操作統合", False, f"エラー: {e}")

def test_status_communication(results: IntegrationTestResults):
    """ステータス通信統合テスト"""
    try:
        print("   🔄 ステータス通信統合テスト実行中...")
        
        # システム構築
        task_queue = queue.Queue()
        status_queue = queue.Queue()
        dual_loop_system = MockDualLoopSystem()
        
        task_loop = EnhancedTaskLoop(
            task_queue, status_queue, 
            dual_loop_system.enhanced_companion, 
            dual_loop_system
        )
        
        # ステータス通知テスト
        test_status = {
            'type': 'task_completed',
            'message': '統合テスト完了',
            'step': 'REVIEW',
            'status': 'SUCCESS'
        }
        
        # TaskLoopからステータス通知
        task_loop._send_enhanced_status(test_status)
        
        # ステータスキューから受信確認
        received_status = status_queue.get_nowait()
        
        # 必要なフィールドの確認
        assert 'timestamp' in received_status, "タイムスタンプが含まれていない"
        assert 'agent_state_step' in received_status, "agent_state_stepが含まれていない"
        assert 'agent_state_status' in received_status, "agent_state_statusが含まれていない"
        assert received_status['type'] == test_status['type'], "typeが正しくない"
        assert received_status['message'] == test_status['message'], "messageが正しくない"
        
        results.add_result("ステータス通信統合", True, "ステータス通知と受信確認")
        
    except Exception as e:
        results.add_result("ステータス通信統合", False, f"エラー: {e}")

def main():
    """メイン統合テスト関数"""
    print("🚀 Enhanced v2.0システム統合テスト開始")
    print("=" * 60)
    
    results = IntegrationTestResults()
    
    # 統合テスト実行
    print("\n📋 Test 1: Dual-Loop統合テスト")
    test_dual_loop_integration(results)
    
    print("\n📋 Test 2: タスク処理フロー統合テスト")
    test_task_processing_flow(results)
    
    print("\n📋 Test 3: 並行操作統合テスト")
    test_concurrent_operations(results)
    
    print("\n📋 Test 4: ステータス通信統合テスト")
    test_status_communication(results)
    
    # 結果サマリー
    results.print_summary()
    
    # 終了コード
    sys.exit(0 if results.failed == 0 else 1)

if __name__ == "__main__":
    main()
