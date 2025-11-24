#!/usr/bin/env python3
"""
Enhanced v2.0システム パフォーマンステスト

Enhanced専用ループのパフォーマンスと効率性をテストします。
"""

import sys
import queue
import threading
import time
import logging
import asyncio
from typing import Optional, Dict, Any, List
import statistics

# Enhanced v2.0システムのインポート
from companion.enhanced.chat_loop import EnhancedChatLoop
from companion.enhanced.task_loop import EnhancedTaskLoop
from companion.state.enums import Step, Status

# テスト用のログ設定（パフォーマンステストでは警告レベル以上のみ）
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class PerformanceTestResults:
    """パフォーマンステスト結果を記録するクラス"""
    def __init__(self):
        self.results = {}
        self.benchmarks = {}
    
    def add_performance_result(self, test_name: str, duration: float, operations: int, success: bool = True):
        """パフォーマンス結果を追加"""
        ops_per_second = operations / duration if duration > 0 else 0
        
        self.results[test_name] = {
            'duration': duration,
            'operations': operations,
            'ops_per_second': ops_per_second,
            'success': success
        }
        
        if success:
            print(f"✅ {test_name}")
            print(f"   ⏱️  実行時間: {duration:.3f}秒")
            print(f"   🔢 操作数: {operations}")
            print(f"   ⚡ スループット: {ops_per_second:.1f} ops/sec")
        else:
            print(f"❌ {test_name}: FAILED")
    
    def add_benchmark(self, test_name: str, measurements: List[float]):
        """ベンチマーク結果を追加"""
        if measurements:
            avg = statistics.mean(measurements)
            median = statistics.median(measurements)
            std_dev = statistics.stdev(measurements) if len(measurements) > 1 else 0
            min_val = min(measurements)
            max_val = max(measurements)
            
            self.benchmarks[test_name] = {
                'measurements': measurements,
                'average': avg,
                'median': median,
                'std_dev': std_dev,
                'min': min_val,
                'max': max_val
            }
            
            print(f"📊 {test_name} ベンチマーク:")
            print(f"   平均: {avg:.3f}秒")
            print(f"   中央値: {median:.3f}秒")
            print(f"   標準偏差: {std_dev:.3f}秒")
            print(f"   最小: {min_val:.3f}秒")
            print(f"   最大: {max_val:.3f}秒")
    
    def print_summary(self):
        print("\n" + "=" * 60)
        print("🚀 Enhanced v2.0システム パフォーマンステスト結果")
        print("=" * 60)
        
        if self.results:
            print("\n📈 パフォーマンス結果:")
            for test_name, result in self.results.items():
                print(f"  {test_name}:")
                print(f"    実行時間: {result['duration']:.3f}秒")
                print(f"    スループット: {result['ops_per_second']:.1f} ops/sec")
        
        if self.benchmarks:
            print("\n📊 ベンチマーク結果:")
            for test_name, benchmark in self.benchmarks.items():
                print(f"  {test_name}:")
                print(f"    平均応答時間: {benchmark['average']:.3f}秒")
                print(f"    安定性(標準偏差): {benchmark['std_dev']:.3f}秒")
        
        print("=" * 60)

class MockAgentState:
    """高速テスト用のAgentStateモック"""
    def __init__(self):
        self.step = Step.IDLE
        self.status = Status.PENDING
        self.goal = "パフォーマンステスト"
        self.update_count = 0
        
    def set_step_status(self, step: Step, status: Status):
        """高速状態更新"""
        self.step = step
        self.status = status
        self.update_count += 1

class MockEnhancedCompanion:
    """高速テスト用のEnhancedCompanionモック"""
    def __init__(self):
        self.agent_state = MockAgentState()
    
    def get_agent_state(self):
        return self.agent_state

class MockDualLoopSystem:
    """高速テスト用のDualLoopSystemモック"""
    def __init__(self):
        self.session_id = "performance-test"
        self.enhanced_companion = MockEnhancedCompanion()
        self.agent_state = self.enhanced_companion.get_agent_state()
    
    def get_current_state(self) -> str:
        return f"{self.agent_state.step.value}.{self.agent_state.status.value}"

def test_instantiation_performance(results: PerformanceTestResults):
    """インスタンス化パフォーマンステスト"""
    print("   🔄 インスタンス化パフォーマンステスト実行中...")
    
    iterations = 1000
    start_time = time.time()
    
    try:
        for i in range(iterations):
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
            
            # インスタンスの破棄
            del chat_loop, task_loop, dual_loop_system
        
        duration = time.time() - start_time
        results.add_performance_result("インスタンス化", duration, iterations)
        
    except Exception as e:
        results.add_performance_result("インスタンス化", 0, 0, False)
        print(f"エラー: {e}")

def test_state_update_performance(results: PerformanceTestResults):
    """状態更新パフォーマンステスト"""
    print("   🔄 状態更新パフォーマンステスト実行中...")
    
    # セットアップ
    task_queue = queue.Queue()
    status_queue = queue.Queue()
    dual_loop_system = MockDualLoopSystem()
    
    task_loop = EnhancedTaskLoop(
        task_queue, status_queue, 
        dual_loop_system.enhanced_companion, 
        dual_loop_system
    )
    
    # 状態更新テスト
    iterations = 10000
    states = [
        (Step.PLANNING, Status.IN_PROGRESS),
        (Step.EXECUTION, Status.IN_PROGRESS),
        (Step.REVIEW, Status.SUCCESS),
        (Step.IDLE, Status.PENDING)
    ]
    
    start_time = time.time()
    
    try:
        for i in range(iterations):
            step, status = states[i % len(states)]
            task_loop._update_agent_state_step(step, status)
        
        duration = time.time() - start_time
        results.add_performance_result("状態更新", duration, iterations)
        
        # 更新回数確認
        assert dual_loop_system.agent_state.update_count == iterations, "更新回数が一致しない"
        
    except Exception as e:
        results.add_performance_result("状態更新", 0, 0, False)
        print(f"エラー: {e}")

def test_queue_performance(results: PerformanceTestResults):
    """キューパフォーマンステスト"""
    print("   🔄 キューパフォーマンステスト実行中...")
    
    task_queue = queue.Queue()
    status_queue = queue.Queue()
    
    iterations = 50000
    start_time = time.time()
    
    try:
        # タスクキューへの書き込み
        for i in range(iterations):
            task = {
                'type': 'performance_test',
                'id': i,
                'data': f'test_data_{i}'
            }
            task_queue.put(task)
        
        # タスクキューからの読み込み
        for i in range(iterations):
            task = task_queue.get_nowait()
            assert task['id'] == i, f"タスクID不一致: {task['id']} != {i}"
        
        duration = time.time() - start_time
        results.add_performance_result("キュー操作", duration, iterations * 2)  # 読み書き両方
        
    except Exception as e:
        results.add_performance_result("キュー操作", 0, 0, False)
        print(f"エラー: {e}")

def test_concurrent_performance(results: PerformanceTestResults):
    """並行処理パフォーマンステスト"""
    print("   🔄 並行処理パフォーマンステスト実行中...")
    
    measurements = []
    iterations = 100
    
    try:
        for i in range(iterations):
            start_time = time.time()
            
            # 複数のシステムを同時に作成
            systems = []
            for j in range(10):
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
                
                systems.append((chat_loop, task_loop, dual_loop_system))
            
            # 状態更新
            for chat_loop, task_loop, dual_loop_system in systems:
                task_loop._update_agent_state_step(Step.EXECUTION, Status.SUCCESS)
            
            duration = time.time() - start_time
            measurements.append(duration)
            
            # クリーンアップ
            del systems
        
        results.add_benchmark("並行処理", measurements)
        
    except Exception as e:
        print(f"並行処理テストエラー: {e}")

def test_memory_efficiency(results: PerformanceTestResults):
    """メモリ効率性テスト"""
    print("   🔄 メモリ効率性テスト実行中...")
    
    try:
        import gc
        import psutil
        import os
        process = psutil.Process(os.getpid())
        
        # 初期メモリ使用量
        gc.collect()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # 大量のインスタンス作成
        systems = []
        iterations = 1000
        
        start_time = time.time()
        
        for i in range(iterations):
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
            
            systems.append((chat_loop, task_loop, dual_loop_system))
        
        # メモリ使用量測定
        peak_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # クリーンアップ
        del systems
        gc.collect()
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        duration = time.time() - start_time
        
        print(f"   💾 初期メモリ: {initial_memory:.1f}MB")
        print(f"   💾 ピークメモリ: {peak_memory:.1f}MB")
        print(f"   💾 最終メモリ: {final_memory:.1f}MB")
        print(f"   💾 メモリ増加: {peak_memory - initial_memory:.1f}MB")
        print(f"   💾 1インスタンスあたり: {(peak_memory - initial_memory) / iterations * 1024:.1f}KB")
        
        results.add_performance_result("メモリ効率性", duration, iterations)
        
    except ImportError:
        print("   ⚠️  psutilが利用できないため、メモリ効率性テストをスキップします")
    except Exception as e:
        print(f"メモリ効率性テストエラー: {e}")

def main():
    """メインパフォーマンステスト関数"""
    print("🚀 Enhanced v2.0システム パフォーマンステスト開始")
    print("=" * 60)
    
    results = PerformanceTestResults()
    
    # パフォーマンステスト実行
    print("\n📋 Test 1: インスタンス化パフォーマンステスト")
    test_instantiation_performance(results)
    
    print("\n📋 Test 2: 状態更新パフォーマンステスト")
    test_state_update_performance(results)
    
    print("\n📋 Test 3: キューパフォーマンステスト")
    test_queue_performance(results)
    
    print("\n📋 Test 4: 並行処理パフォーマンステスト")
    test_concurrent_performance(results)
    
    print("\n📋 Test 5: メモリ効率性テスト")
    test_memory_efficiency(results)
    
    # 結果サマリー
    results.print_summary()
    
    print("\n🎉 パフォーマンステスト完了!")

if __name__ == "__main__":
    main()
