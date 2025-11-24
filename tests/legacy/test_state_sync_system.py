#!/usr/bin/env python3
"""
設計ドキュメント4.4節で実装した状態同期システムのテスト用スクリプト

このスクリプトは、以下の機能をテストします：
1. 状態所有者の一元化
2. ループからの参照による状態管理
3. コールバックによる同期
4. 状態の整合性チェック
5. エラー時の復旧処理
"""

import sys
import os
import logging
from datetime import datetime

# プロジェクトのルートディレクトリをパスに追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from companion.enhanced_dual_loop import EnhancedDualLoopSystem
from companion.state.enums import Step, Status


def setup_logging():
    """ログ設定をセットアップ"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('state_sync_test.log')
        ]
    )


def test_state_synchronization():
    """状態同期システムのテスト"""
    print("🔄 状態同期システムのテストを開始します...")
    
    try:
        # EnhancedDualLoopSystemを初期化
        print("📋 EnhancedDualLoopSystemを初期化中...")
        dual_loop_system = EnhancedDualLoopSystem()
        
        # 初期状態を確認
        print("\n📊 初期状態の確認:")
        initial_state = dual_loop_system.get_system_state_summary()
        print(f"  セッションID: {initial_state['session_id']}")
        print(f"  StateMachine状態: {initial_state['state_machine_state']}")
        print(f"  AgentState状態: {initial_state['agent_state_state']}")
        
        # 状態同期の状況を確認
        print("\n🔄 状態同期の状況:")
        sync_status = dual_loop_system.state_machine.get_sync_status()
        print(f"  コールバック数: {sync_status['total_callbacks']}")
        print(f"  同期成功率: {sync_status['sync_success_rate']:.1f}%")
        
        # 状態遷移のテスト
        print("\n🔄 状態遷移のテスト:")
        
        # PLANNING状態に遷移
        print("  → PLANNING状態に遷移")
        success = dual_loop_system.state_machine.transition_to(Step.PLANNING, Status.IN_PROGRESS, "テスト: 計画立案開始")
        print(f"    結果: {'成功' if success else '失敗'}")
        
        # 状態の確認
        current_state = dual_loop_system.get_system_state_summary()
        print(f"    現在の状態: {current_state['state_machine_state']}")
        print(f"    AgentState状態: {current_state['agent_state_state']}")
        
        # EXECUTION状態に遷移
        print("  → EXECUTION状態に遷移")
        success = dual_loop_system.state_machine.transition_to(Step.EXECUTION, Status.IN_PROGRESS, "テスト: 実行開始")
        print(f"    結果: {'成功' if success else '失敗'}")
        
        # 状態の確認
        current_state = dual_loop_system.get_system_state_summary()
        print(f"    現在の状態: {current_state['state_machine_state']}")
        print(f"    AgentState状態: {current_state['agent_state_state']}")
        
        # REVIEW状態に遷移
        print("  → REVIEW状態に遷移")
        success = dual_loop_system.state_machine.transition_to(Step.REVIEW, Status.IN_PROGRESS, "テスト: レビュー開始")
        print(f"    結果: {'成功' if success else '失敗'}")
        
        # 状態の確認
        current_state = dual_loop_system.get_system_state_summary()
        print(f"    現在の状態: {current_state['state_machine_state']}")
        print(f"    AgentState状態: {current_state['agent_state_state']}")
        
        # COMPLETED状態に遷移
        print("  → COMPLETED状態に遷移")
        success = dual_loop_system.state_machine.transition_to(Step.COMPLETED, Status.SUCCESS, "テスト: 完了")
        print(f"    結果: {'成功' if success else '失敗'}")
        
        # 状態の確認
        current_state = dual_loop_system.get_system_state_summary()
        print(f"    現在の状態: {current_state['state_machine_state']}")
        print(f"    AgentState状態: {current_state['agent_state_state']}")
        
        # IDLE状態にリセット
        print("  → IDLE状態にリセット")
        dual_loop_system.state_machine.reset_to_idle()
        
        # 最終状態の確認
        print("\n📊 最終状態の確認:")
        final_state = dual_loop_system.get_system_state_summary()
        print(f"  StateMachine状態: {final_state['state_machine_state']}")
        print(f"  AgentState状態: {final_state['agent_state_state']}")
        
        # 状態同期の健全性レポート
        print("\n🏥 状態同期の健全性レポート:")
        health_report = dual_loop_system.get_sync_health_report()
        if 'error' not in health_report:
            print(f"  同期状況: {health_report['sync_status']}")
            print(f"  推奨事項:")
            for rec in health_report['recommendations']:
                print(f"    • {rec}")
        else:
            print(f"  エラー: {health_report['error']}")
        
        # 状態履歴の確認
        print("\n📜 状態履歴の確認:")
        state_history = dual_loop_system.state_machine.get_state_history(limit=10)
        print(f"  状態変更履歴: {len(state_history)}件")
        for i, history in enumerate(state_history[-5:], 1):  # 最新5件
            print(f"    {i}. {history['step']}.{history['status']} (トリガー: {history['trigger']})")
        
        # 同期履歴の確認
        print("\n🔄 同期履歴の確認:")
        sync_history = dual_loop_system.state_machine.get_sync_history(limit=10)
        print(f"  同期履歴: {len(sync_history)}件")
        for i, sync in enumerate(sync_history[-5:], 1):  # 最新5件
            status = "✅" if sync['sync_success'] else "❌"
            print(f"    {i}. {status} {sync['step']}.{sync['status']} (トリガー: {sync['trigger']})")
        
        print("\n✅ 状態同期システムのテストが完了しました！")
        
        return True
        
    except Exception as e:
        print(f"❌ テスト中にエラーが発生しました: {e}")
        logging.error(f"テストエラー: {e}", exc_info=True)
        return False


def test_error_recovery():
    """エラー復旧処理のテスト"""
    print("\n🚨 エラー復旧処理のテストを開始します...")
    
    try:
        # EnhancedDualLoopSystemを初期化
        dual_loop_system = EnhancedDualLoopSystem()
        
        # 不正な状態遷移を試行（エラー状態のテスト）
        print("  → 不正な状態遷移を試行（エラー状態のテスト）")
        
        # ERROR状態に強制遷移
        success = dual_loop_system.state_machine.force_transition(Step.ERROR, Status.ERROR, "テスト: エラー状態")
        print(f"    強制遷移結果: {'成功' if success else '失敗'}")
        
        # 現在の状態を確認
        current_state = dual_loop_system.get_system_state_summary()
        print(f"    現在の状態: {current_state['state_machine_state']}")
        print(f"    AgentState状態: {current_state['agent_state_state']}")
        
        # エラー状態からの復帰
        print("  → エラー状態からの復帰")
        success = dual_loop_system.state_machine.transition_to(Step.IDLE, Status.PENDING, "テスト: エラー復帰")
        print(f"    復帰結果: {'成功' if success else '失敗'}")
        
        # 最終状態を確認
        final_state = dual_loop_system.get_system_state_summary()
        print(f"    最終状態: {final_state['state_machine_state']}")
        
        print("✅ エラー復旧処理のテストが完了しました！")
        return True
        
    except Exception as e:
        print(f"❌ エラー復旧テスト中にエラーが発生しました: {e}")
        logging.error(f"エラー復旧テストエラー: {e}", exc_info=True)
        return False


def test_integrity_checks():
    """状態整合性チェックのテスト"""
    print("\n🔍 状態整合性チェックのテストを開始します...")
    
    try:
        # EnhancedDualLoopSystemを初期化
        dual_loop_system = EnhancedDualLoopSystem()
        
        # 整合性チェックの有効/無効をテスト
        print("  → 整合性チェックの有効/無効をテスト")
        
        # 整合性チェックを無効化
        dual_loop_system.state_machine.enable_integrity_checks(False)
        print("    整合性チェックを無効化")
        
        # 不正な状態遷移を試行
        print("  → 整合性チェック無効時の不正な状態遷移を試行")
        success = dual_loop_system.state_machine.transition_to(Step.ERROR, Status.SUCCESS, "テスト: 不正な状態")
        print(f"    結果: {'成功' if success else '失敗'}")
        
        # 整合性チェックを再有効化
        dual_loop_system.state_machine.enable_integrity_checks(True)
        print("    整合性チェックを再有効化")
        
        # 現在の状態の整合性を検証
        print("  → 現在の状態の整合性を検証")
        is_valid = dual_loop_system.state_machine.validate_current_state()
        print(f"    整合性: {'有効' if is_valid else '無効'}")
        
        # 正常な状態にリセット
        dual_loop_system.state_machine.reset_to_idle()
        
        print("✅ 状態整合性チェックのテストが完了しました！")
        return True
        
    except Exception as e:
        print(f"❌ 整合性チェックテスト中にエラーが発生しました: {e}")
        logging.error(f"整合性チェックテストエラー: {e}", exc_info=True)
        return False


def main():
    """メイン関数"""
    print("🦆 Duckflow v3 状態同期システム テスト")
    print("=" * 50)
    
    # ログ設定
    setup_logging()
    
    # テスト実行
    tests = [
        ("状態同期システム", test_state_synchronization),
        ("エラー復旧処理", test_error_recovery),
        ("状態整合性チェック", test_integrity_checks),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name}で予期しないエラーが発生しました: {e}")
            results.append((test_name, False))
    
    # テスト結果のサマリー
    print(f"\n{'='*50}")
    print("📊 テスト結果サマリー")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 成功" if result else "❌ 失敗"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n総合結果: {passed}/{total} テストが成功")
    
    if passed == total:
        print("🎉 すべてのテストが成功しました！")
        return 0
    else:
        print("⚠️ 一部のテストが失敗しました。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
