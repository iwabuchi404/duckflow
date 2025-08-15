#!/usr/bin/env python3
"""
Dual-Loop System テスト

Step 1実装のテスト用スクリプト
"""

import sys
import time
import threading
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from companion.dual_loop import DualLoopSystem
    from codecrafter.ui.rich_ui import rich_ui
except ImportError as e:
    print(f"❌ インポートエラー: {e}")
    sys.exit(1)


def test_dual_loop_basic():
    """基本的なDual-Loop Systemのテスト"""
    print("🧪 Dual-Loop System 基本テスト開始")
    
    # システムの初期化
    system = DualLoopSystem()
    
    # 状態確認
    status = system.get_status()
    print(f"✅ システム初期化完了")
    print(f"   - 実行状態: {status['running']}")
    print(f"   - タスクキューサイズ: {status['task_queue_size']}")
    print(f"   - ステータスキューサイズ: {status['status_queue_size']}")
    
    # 短時間でのテスト実行
    def test_runner():
        """テスト実行用の関数"""
        time.sleep(2)  # 2秒待機
        print("🛑 テスト終了のためシステムを停止します")
        system.stop()
    
    # テスト実行スレッドを開始
    test_thread = threading.Thread(target=test_runner, daemon=True)
    test_thread.start()
    
    try:
        # システムを開始（メインスレッドで実行）
        print("🚀 システム開始（2秒後に自動終了）")
        system.start()
    except KeyboardInterrupt:
        print("⚠️ ユーザーによる中断")
    
    print("✅ テスト完了")


def test_queue_communication():
    """キュー通信のテスト"""
    print("\n🧪 キュー通信テスト開始")
    
    import queue
    
    # キューの作成
    task_queue = queue.Queue()
    status_queue = queue.Queue()
    
    # テストデータの送信
    test_tasks = [
        "テストタスク1",
        "テストタスク2", 
        "テストタスク3"
    ]
    
    for task in test_tasks:
        task_queue.put(task)
        print(f"📤 送信: {task}")
    
    # テストデータの受信
    print(f"📊 キューサイズ: {task_queue.qsize()}")
    
    while not task_queue.empty():
        task = task_queue.get()
        print(f"📥 受信: {task}")
        
        # 状態を送信
        status_queue.put(f"処理完了: {task}")
    
    # 状態の確認
    while not status_queue.empty():
        status = status_queue.get()
        print(f"📋 状態: {status}")
    
    print("✅ キュー通信テスト完了")


def main():
    """メイン関数"""
    print("🦆 Dual-Loop System テストスイート")
    print("=" * 50)
    
    # 基本テスト
    test_queue_communication()
    
    # 実際のシステムテスト（オプション）
    print("\n" + "=" * 50)
    print("実際のシステムテストを実行しますか？ (y/n)")
    
    try:
        choice = input().strip().lower()
        if choice in ['y', 'yes']:
            test_dual_loop_basic()
        else:
            print("テストをスキップしました")
    except KeyboardInterrupt:
        print("\nテストを中断しました")
    
    print("\n🎉 全テスト完了！")


if __name__ == "__main__":
    main()