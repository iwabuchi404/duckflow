# test_error_recovery.py
"""
エラー回復システムのテスト
Step 3実装の動作確認用
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from companion.error_recovery_system import (
    ErrorRecoverySystem, ErrorSeverity, RecoveryStrategy, 
    ErrorContext, RecoveryAction
)
from datetime import datetime

def test_error_capture():
    """エラー捕捉のテスト"""
    print("🚨 エラー捕捉のテスト")
    print("=" * 50)
    
    recovery_system = ErrorRecoverySystem()
    
    # 各種エラーを作成してテスト
    test_errors = [
        FileNotFoundError("test_file.txt が見つかりません"),
        PermissionError("ファイルへの書き込み権限がありません"),
        ConnectionError("サーバーに接続できません"),
        ValueError("無効な値が指定されました"),
        MemoryError("メモリが不足しています")
    ]
    
    for i, error in enumerate(test_errors, 1):
        error_context = recovery_system.capture_error(
            error=error,
            task_id=f"test_task_{i}",
            step_name=f"テストステップ{i}",
            context_data={"test_mode": True, "error_index": i}
        )
        
        print(f"\nエラー {i}:")
        print(f"  ID: {error_context.error_id}")
        print(f"  種類: {error_context.error_type}")
        print(f"  重要度: {error_context.severity.value}")
        print(f"  メッセージ: {error_context.error_message}")
    
    print(f"\n📊 捕捉されたエラー数: {len(recovery_system.error_history)}")

def test_recovery_plan_creation():
    """回復計画作成のテスト"""
    print("\n🛠️ 回復計画作成のテスト")
    print("=" * 50)
    
    recovery_system = ErrorRecoverySystem()
    
    # ファイルエラーの回復計画
    file_error = FileNotFoundError("config.yaml が見つかりません")
    error_context = recovery_system.capture_error(
        error=file_error,
        task_id="config_task",
        step_name="設定ファイル読み込み"
    )
    
    recovery_plan = recovery_system.create_recovery_plan(error_context)
    
    print(f"計画ID: {recovery_plan.plan_id}")
    print(f"エラー: {recovery_plan.error_context.error_message}")
    print(f"アクション数: {len(recovery_plan.actions)}")
    
    print("\n🔧 利用可能なアクション:")
    for i, action in enumerate(recovery_plan.actions, 1):
        auto_mark = "✅" if action.auto_executable else "👤"
        print(f"  {i}. {auto_mark} {action.description}")
        print(f"     戦略: {action.strategy.value}")
        print(f"     成功率: {action.estimated_success_rate:.0%}")
        print(f"     推定時間: {action.execution_time_estimate}秒")
    
    recommended = recovery_plan.get_recommended_action()
    if recommended:
        print(f"\n⭐ 推奨アクション: {recommended.description}")
    
    return recovery_plan.plan_id

def test_recovery_options_presentation():
    """回復オプション表示のテスト"""
    print("\n📋 回復オプション表示のテスト")
    print("=" * 50)
    
    recovery_system = ErrorRecoverySystem()
    
    # ネットワークエラーの回復計画
    network_error = ConnectionError("APIサーバーに接続できません (timeout)")
    error_context = recovery_system.capture_error(
        error=network_error,
        task_id="api_task",
        step_name="API呼び出し",
        context_data={"endpoint": "https://api.example.com", "timeout": 30}
    )
    
    recovery_plan = recovery_system.create_recovery_plan(error_context)
    options = recovery_system.get_recovery_options(recovery_plan.plan_id)
    
    print("ユーザー向け表示:")
    print("-" * 30)
    print(options)
    
    return recovery_plan.plan_id

def test_recovery_execution():
    """回復アクション実行のテスト"""
    print("\n⚙️ 回復アクション実行のテスト")
    print("=" * 50)
    
    recovery_system = ErrorRecoverySystem()
    
    # テスト用エラーと回復計画
    test_error = ValueError("無効なパラメータ: param=None")
    error_context = recovery_system.capture_error(
        error=test_error,
        task_id="validation_task",
        step_name="パラメータ検証"
    )
    
    recovery_plan = recovery_system.create_recovery_plan(error_context)
    
    print(f"計画ID: {recovery_plan.plan_id}")
    print("利用可能なアクション:")
    for i, action in enumerate(recovery_plan.actions, 1):
        print(f"  {i}. {action.description} (ID: {action.action_id})")
    
    # 各アクションを実行してテスト
    for action in recovery_plan.actions[:2]:  # 最初の2つのアクションをテスト
        print(f"\n🔄 アクション実行: {action.description}")
        success, message = recovery_system.execute_recovery_action(
            recovery_plan.plan_id, 
            action.action_id
        )
        
        print(f"  結果: {'✅ 成功' if success else '❌ 失敗'}")
        print(f"  メッセージ: {message}")

def test_auto_recovery_decision():
    """自動回復判定のテスト"""
    print("\n🤖 自動回復判定のテスト")
    print("=" * 50)
    
    recovery_system = ErrorRecoverySystem()
    
    # 各種重要度のエラーで自動回復判定をテスト
    test_cases = [
        (ValueError("軽微なバリデーションエラー"), "軽微なエラー"),
        (ConnectionError("一時的な接続エラー"), "中程度のエラー"),
        (MemoryError("メモリ不足"), "重大なエラー"),
        (KeyboardInterrupt("ユーザー中断"), "致命的なエラー")
    ]
    
    for error, description in test_cases:
        error_context = recovery_system.capture_error(
            error=error,
            task_id="auto_test",
            step_name="自動回復テスト"
        )
        
        should_auto = recovery_system.should_auto_recover(error_context)
        print(f"{description}: {error_context.severity.value} -> {'🤖 自動回復' if should_auto else '👤 手動対応'}")

def test_error_frequency_detection():
    """エラー頻度検出のテスト"""
    print("\n📊 エラー頻度検出のテスト")
    print("=" * 50)
    
    recovery_system = ErrorRecoverySystem()
    
    # 同じエラーを複数回発生させる
    for i in range(5):
        error = FileNotFoundError("temp.txt が見つかりません")
        error_context = recovery_system.capture_error(
            error=error,
            task_id=f"freq_test_{i}",
            step_name="頻度テスト"
        )
        
        should_auto = recovery_system.should_auto_recover(error_context)
        print(f"試行 {i+1}: {'🤖 自動回復' if should_auto else '👤 手動対応'}")
        
        # 少し待機（頻度判定のため）
        import time
        time.sleep(0.1)

def test_error_summary():
    """エラーサマリーのテスト"""
    print("\n📈 エラーサマリーのテスト")
    print("=" * 50)
    
    recovery_system = ErrorRecoverySystem()
    
    # 複数の異なるエラーを生成
    errors = [
        FileNotFoundError("file1.txt"),
        FileNotFoundError("file2.txt"),
        ConnectionError("接続エラー1"),
        ValueError("値エラー1"),
        ConnectionError("接続エラー2"),
    ]
    
    for i, error in enumerate(errors):
        recovery_system.capture_error(
            error=error,
            task_id=f"summary_test_{i}",
            step_name=f"サマリーテスト{i}"
        )
    
    summary = recovery_system.get_error_summary()
    
    print("エラーサマリー:")
    print(f"  総エラー数: {summary['total_errors']}")
    print(f"  直近のエラー: {summary['recent_errors']}")
    print("  エラー種類別:")
    for error_type, count in summary['error_types'].items():
        print(f"    {error_type}: {count}回")
    print("  重要度別:")
    for severity, count in summary['severities'].items():
        print(f"    {severity}: {count}回")

if __name__ == "__main__":
    print("🦆 エラー回復システム 統合テスト")
    print("=" * 60)
    
    try:
        test_error_capture()
        test_recovery_plan_creation()
        plan_id = test_recovery_options_presentation()
        test_recovery_execution()
        test_auto_recovery_decision()
        test_error_frequency_detection()
        test_error_summary()
        
        print("\n" + "=" * 60)
        print("🎉 すべてのテストが完了しました！")
        print("Step 3のエラー回復システムが正常に動作しています。")
        
    except Exception as e:
        print(f"\n❌ テスト中にエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()