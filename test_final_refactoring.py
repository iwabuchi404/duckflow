#!/usr/bin/env python3
"""
最終リファクタリングテスト

状態遷移一元管理と依存関係分離のテスト
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# テスト用の一時ディレクトリを作成
test_dir = Path(tempfile.mkdtemp(prefix="test_final_refactoring_"))
os.chdir(test_dir)

print(f"テストディレクトリ: {test_dir}")

def test_state_machine():
    """ステートマシンのテスト"""
    print("\n=== ステートマシンテスト ===")
    
    try:
        from companion.state_machine import StateMachine, Step, Status
        
        # ステートマシンの初期化
        sm = StateMachine()
        print("✅ ステートマシン初期化成功")
        
        # 初期状態の確認
        current_state = sm.get_current_state()
        print(f"初期状態: {current_state}")
        assert current_state['step'] == 'IDLE'
        assert current_state['status'] == 'PENDING'
        
        # 状態遷移のテスト
        # IDLE → PLANNING
        result = sm.transition_to(Step.PLANNING, Status.RUNNING, "テスト開始")
        assert result == True
        print("✅ IDLE → PLANNING 遷移成功")
        
        current_state = sm.get_current_state()
        assert current_state['step'] == 'PLANNING'
        assert current_state['status'] == 'RUNNING'
        
        # PLANNING → EXECUTION (PLANNINGをSUCCESSに変更してから)
        result = sm.transition_to(Step.PLANNING, Status.SUCCESS, "計画完了")
        assert result == True
        print("✅ PLANNING → SUCCESS 遷移成功")
        
        result = sm.transition_to(Step.EXECUTION, Status.RUNNING, "実行開始")
        assert result == True
        print("✅ PLANNING → EXECUTION 遷移成功")
        
        # EXECUTION → SUCCESS
        result = sm.transition_to(Step.EXECUTION, Status.SUCCESS, "実行完了")
        assert result == True
        print("✅ EXECUTION → SUCCESS 遷移成功")
        
        # EXECUTION → REVIEW
        result = sm.transition_to(Step.REVIEW, Status.RUNNING, "検証開始")
        assert result == True
        print("✅ EXECUTION → REVIEW 遷移成功")
        
        # REVIEW → SUCCESS
        result = sm.transition_to(Step.REVIEW, Status.SUCCESS, "検証完了")
        assert result == True
        print("✅ REVIEW → SUCCESS 遷移成功")
        
        # REVIEW → COMPLETED
        result = sm.transition_to(Step.COMPLETED, Status.SUCCESS, "完了")
        assert result == True
        print("✅ REVIEW → COMPLETED 遷移成功")
        
        # COMPLETED → IDLE
        result = sm.transition_to(Step.IDLE, Status.PENDING, "リセット")
        assert result == True
        print("✅ COMPLETED → IDLE 遷移成功")
        
        # 状態履歴の確認
        history = sm.get_state_history()
        assert len(history) >= 6  # 初期状態 + 5回の遷移
        print(f"✅ 状態履歴: {len(history)}件")
        
        # システム健全性の確認
        health = sm.get_system_health()
        print(f"✅ システム健全性: {health['system_stable']}")
        
        print("✅ ステートマシンテスト完了")
        return True
        
    except Exception as e:
        print(f"❌ ステートマシンテスト失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_ui():
    """UIシステムのテスト"""
    print("\n=== UIシステムテスト ===")
    
    try:
        from companion.ui import rich_ui, print_success, print_error, print_info
        
        # 基本UI関数のテスト
        print_success("成功メッセージ")
        print_error("エラーメッセージ")
        print_info("情報メッセージ")
        
        # RichUIインスタンスのテスト
        assert hasattr(rich_ui, 'print_success')
        assert hasattr(rich_ui, 'print_error')
        assert hasattr(rich_ui, 'print_info')
        
        # パネル表示のテスト
        rich_ui.print_panel("テストパネル", "テストタイトル")
        
        # テーブル表示のテスト
        data = [["項目1", "値1"], ["項目2", "値2"]]
        headers = ["項目", "値"]
        rich_ui.print_table(headers, data, "テストテーブル")
        
        print("✅ UIシステムテスト完了")
        return True
        
    except Exception as e:
        print(f"❌ UIシステムテスト失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_config_manager():
    """設定管理のテスト"""
    print("\n=== 設定管理テスト ===")
    
    try:
        from companion.config.config_manager import ConfigManager, Config
        
        # 設定マネージャーの初期化
        config_dir = test_dir / "config"
        cm = ConfigManager(str(config_dir))
        print("✅ 設定マネージャー初期化成功")
        
        # 設定の取得
        config = cm.get_config()
        assert isinstance(config, Config)
        print(f"✅ 設定取得成功: {config.app_name}")
        
        # 設定の更新
        result = cm.update_config({
            'debug': True,
            'max_conversation_history': 200
        })
        assert result == True
        print("✅ 設定更新成功")
        
        # 設定の検証
        validation = cm.validate_config()
        assert validation['valid'] == True
        print("✅ 設定検証成功")
        
        # 設定のエクスポート
        yaml_config = cm.export_config("yaml")
        assert "debug: true" in yaml_config
        print("✅ 設定エクスポート成功")
        
        # 設定のサマリー
        summary = cm.get_config_summary()
        assert 'config_valid' in summary
        print("✅ 設定サマリー取得成功")
        
        print("✅ 設定管理テスト完了")
        return True
        
    except Exception as e:
        print(f"❌ 設定管理テスト失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_log_manager():
    """ログ管理のテスト"""
    print("\n=== ログ管理テスト ===")
    
    try:
        from companion.logging.log_manager import LogManager, LogConfig
        
        # ログマネージャーの初期化
        log_dir = test_dir / "logs"
        log_config = LogConfig(
            file_path=str(log_dir / "test.log"),
            enable_debug_log=True,
            enable_performance_log=True,
            enable_security_log=True
        )
        lm = LogManager(log_config)
        print("✅ ログマネージャー初期化成功")
        
        # ロガーの取得
        logger = lm.get_logger("test_logger")
        assert logger is not None
        print("✅ ロガー取得成功")
        
        # ログレベルの設定
        lm.set_log_level("test_logger", "DEBUG")
        print("✅ ログレベル設定成功")
        
        # パフォーマンスログの記録
        lm.log_performance("テスト操作", 0.123, {"test": True})
        print("✅ パフォーマンスログ記録成功")
        
        # セキュリティログの記録
        lm.log_security("テストセキュリティイベント", "WARNING", {"test": True})
        print("✅ セキュリティログ記録成功")
        
        # ログ統計の取得
        stats = lm.get_log_statistics()
        assert 'total_loggers' in stats
        print("✅ ログ統計取得成功")
        
        # クリーンアップ
        lm.cleanup()
        print("✅ ログマネージャークリーンアップ成功")
        
        print("✅ ログ管理テスト完了")
        return True
        
    except Exception as e:
        print(f"❌ ログ管理テスト失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_enhanced_dual_loop_integration():
    """EnhancedDualLoopSystem統合テスト"""
    print("\n=== EnhancedDualLoopSystem統合テスト ===")
    
    try:
        from companion.enhanced_dual_loop import EnhancedDualLoopSystem
        from companion.state_machine import Step, Status
        
        # システムの初期化
        system = EnhancedDualLoopSystem()
        print("✅ EnhancedDualLoopSystem初期化成功")
        
        # ステートマシンの存在確認
        assert hasattr(system, 'state_machine')
        print("✅ ステートマシン統合確認")
        
        # ステートマシンの初期状態確認
        current_state = system.state_machine.get_current_state()
        assert current_state['step'] == 'IDLE'
        print("✅ ステートマシン初期状態確認")
        
        # 状態遷移のテスト
        result = system.state_machine.transition_to(Step.PLANNING, Status.RUNNING, "統合テスト")
        assert result == True
        print("✅ 統合ステートマシン遷移成功")
        
        # システム状態の取得
        status = system.get_status()
        assert 'phase1' in status
        print("✅ システム状態取得成功")
        
        print("✅ EnhancedDualLoopSystem統合テスト完了")
        return True
        
    except Exception as e:
        print(f"❌ EnhancedDualLoopSystem統合テスト失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """メインテスト実行"""
    print("🚀 最終リファクタリングテスト開始")
    
    test_results = []
    
    # 各テストの実行
    test_results.append(("ステートマシン", test_state_machine()))
    test_results.append(("UIシステム", test_ui()))
    test_results.append(("設定管理", test_config_manager()))
    test_results.append(("ログ管理", test_log_manager()))
    test_results.append(("EnhancedDualLoopSystem統合", test_enhanced_dual_loop_integration()))
    
    # 結果の集計
    print("\n=== テスト結果 ===")
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\n📊 結果: {passed}/{total} テスト成功")
    
    if passed == total:
        print("🎉 すべてのテストが成功しました！")
        return True
    else:
        print("⚠️ 一部のテストが失敗しました")
        return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    finally:
        # テストディレクトリのクリーンアップ
        try:
            shutil.rmtree(test_dir)
            print(f"🧹 テストディレクトリをクリーンアップ: {test_dir}")
        except Exception as e:
            print(f"⚠️ クリーンアップエラー: {e}")
