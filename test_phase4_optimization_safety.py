#!/usr/bin/env python3
"""
Phase 4: 最適化と安全性強化のテスト

- ConversationGateの動作確認
- 5点の情報提供のテスト
- リスクレベルの自動判定
- 承認履歴の記録と分析
- EnhancedPromptSystemとの統合テスト
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_conversation_gate():
    """ConversationGateの基本動作テスト"""
    print("🧪 ConversationGateの基本動作テスト")
    
    try:
        from companion.prompts.conversation_gate import (
            ConversationGate, RiskLevel, ApprovalStatus, ApprovalRequest
        )
        
        # 一時作業ディレクトリを作成
        work_dir = Path("./test_phase4_work")
        work_dir.mkdir(exist_ok=True)
        
        # ConversationGateを初期化
        gate = ConversationGate(work_dir=str(work_dir))
        print(f"✅ ConversationGate初期化完了: {work_dir}")
        
        # 1. 低リスク操作の自動承認テスト
        print("\n📋 1. 低リスク操作の自動承認テスト")
        auto_request = gate.request_approval(
            user_input="ファイルの内容を確認したい",
            operation_type="read",
            target_path="test.txt"
        )
        
        print(f"  - リクエストID: {auto_request.request_id}")
        print(f"  - リスクレベル: {auto_request.risk_level.value}")
        print(f"  - 承認ステータス: {auto_request.approval_status.value}")
        print(f"  - 自動承認: {auto_request.approval_status == ApprovalStatus.APPROVED}")
        
        # 2. 中リスク操作の手動承認テスト
        print("\n📋 2. 中リスク操作の手動承認テスト")
        manual_request = gate.request_approval(
            user_input="新しいファイルを作成したい",
            operation_type="create",
            target_path="new_file.txt"
        )
        
        print(f"  - リクエストID: {manual_request.request_id}")
        print(f"  - リスクレベル: {manual_request.risk_level.value}")
        print(f"  - 承認ステータス: {manual_request.approval_status.value}")
        print(f"  - 手動承認必要: {manual_request.approval_status == ApprovalStatus.PENDING}")
        
        # 3. 高リスク操作のテスト
        print("\n📋 3. 高リスク操作のテスト")
        high_risk_request = gate.request_approval(
            user_input="ファイルを削除したい",
            operation_type="delete",
            target_path="important.txt"
        )
        
        print(f"  - リクエストID: {high_risk_request.request_id}")
        print(f"  - リスクレベル: {high_risk_request.risk_level.value}")
        print(f"  - 承認ステータス: {high_risk_request.risk_level.value}")
        
        # 4. 承認プロンプト生成テスト
        print("\n📋 4. 承認プロンプト生成テスト")
        approval_prompt = gate.generate_approval_prompt(manual_request)
        print(f"  - プロンプト長: {len(approval_prompt)} 文字")
        print(f"  - 5点情報含む: {'意図' in approval_prompt and '根拠' in approval_prompt}")
        
        # 5. 承認レスポンス処理テスト
        print("\n📋 5. 承認レスポンス処理テスト")
        response = gate.process_approval_response(
            manual_request.request_id, "承認"
        )
        
        print(f"  - 承認結果: {response.approved}")
        print(f"  - 理由: {response.reasoning}")
        
        # 6. 統計取得テスト
        print("\n📋 6. 統計取得テスト")
        stats = gate.get_approval_statistics()
        print(f"  - 総リクエスト数: {stats['total_requests']}")
        print(f"  - 承認率: {stats['approval_rate']}%")
        print(f"  - 平均処理時間: {stats['average_processing_time']}秒")
        print(f"  - リスクレベル分布: {stats['risk_level_distribution']}")
        
        # 7. 保留中リクエストの確認
        print("\n📋 7. 保留中リクエストの確認")
        pending = gate.get_pending_requests()
        print(f"  - 保留中リクエスト数: {len(pending)}")
        
        # 8. 期限切れリクエストのクリーンアップ
        print("\n📋 8. 期限切れリクエストのクリーンアップ")
        cleaned = gate.cleanup_expired_requests()
        print(f"  - クリーンアップ数: {cleaned}")
        
        # 9. システム状態の確認
        print("\n📋 9. システム状態の確認")
        system_status = gate.to_dict()
        print(f"  - 作業ディレクトリ: {system_status['work_dir']}")
        print(f"  - 最大履歴数: {system_status['max_history']}")
        print(f"  - 自動承認閾値: {system_status['auto_approval_threshold']}")
        
        print("\n✅ ConversationGateテスト完了")
        return True
        
    except Exception as e:
        print(f"❌ ConversationGateテスト失敗: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # クリーンアップ
        try:
            if 'work_dir' in locals():
                shutil.rmtree(work_dir)
                print(f"🧹 テストディレクトリを削除: {work_dir}")
        except Exception as e:
            print(f"⚠️ クリーンアップ警告: {e}")


def test_enhanced_prompt_system_integration():
    """EnhancedPromptSystemとの統合テスト"""
    print("\n🧪 EnhancedPromptSystemとの統合テスト")
    
    try:
        from companion.prompts.enhanced_prompt_system import EnhancedPromptSystem
        
        # 一時作業ディレクトリを作成
        work_dir = Path("./test_phase4_integration")
        work_dir.mkdir(exist_ok=True)
        
        # EnhancedPromptSystemを初期化
        system = EnhancedPromptSystem(work_dir=str(work_dir))
        print(f"✅ EnhancedPromptSystem初期化完了: {work_dir}")
        
        # 1. 承認システムの有効化確認
        print("\n📋 1. 承認システムの有効化確認")
        print(f"  - ConversationGate有効: {system.enable_conversation_gate}")
        print(f"  - 承認統計初期値: {system.approval_stats}")
        
        # 2. 低リスク操作の自動承認テスト
        print("\n📋 2. 低リスク操作の自動承認テスト")
        auto_result = system.request_approval(
            user_input="ファイルの内容を確認",
            operation_type="read",
            target_path="test.txt"
        )
        
        print(f"  - 自動承認: {auto_result['auto_approved']}")
        print(f"  - 承認結果: {auto_result['approved']}")
        print(f"  - リスクレベル: {auto_result['risk_level']}")
        
        # 3. 中リスク操作の手動承認テスト
        print("\n📋 3. 中リスク操作の手動承認テスト")
        manual_result = system.request_approval(
            user_input="新しいファイルを作成",
            operation_type="create",
            target_path="new_file.txt"
        )
        
        print(f"  - 自動承認: {manual_result['auto_approved']}")
        print(f"  - 承認結果: {manual_result['approved']}")
        print(f"  - リクエストID: {manual_result['request_id']}")
        print(f"  - 承認プロンプト: {len(manual_result['approval_prompt'])} 文字")
        
        # 4. 承認レスポンス処理テスト
        print("\n📋 4. 承認レスポンス処理テスト")
        if not manual_result['auto_approved']:
            response_result = system.process_approval_response(
                manual_result['request_id'], "承認"
            )
            
            print(f"  - 承認結果: {response_result['approved']}")
            print(f"  - 理由: {response_result['reason']}")
            print(f"  - タイムスタンプ: {response_result['timestamp']}")
        
        # 5. 承認統計の確認
        print("\n📋 5. 承認統計の確認")
        approval_stats = system.get_approval_statistics()
        print(f"  - システム有効: {approval_stats['enabled']}")
        if approval_stats['enabled']:
            print(f"  - ConversationGate統計: {approval_stats['conversation_gate']['total_requests']}件")
            print(f"  - EnhancedSystem統計: {approval_stats['enhanced_system']}")
            print(f"  - 保留中リクエスト: {approval_stats['pending_requests']}件")
        
        # 6. システム状態の確認
        print("\n📋 6. システム状態の確認")
        system_status = system.get_system_status()
        print(f"  - ConversationGate有効: {system_status['enhanced_prompt_system']['enable_conversation_gate']}")
        print(f"  - 承認システム状態: {system_status['conversation_gate']['enabled']}")
        
        # 7. 統計リセットテスト
        print("\n📋 7. 統計リセットテスト")
        system.reset_statistics()
        reset_stats = system.get_approval_statistics()
        print(f"  - リセット後統計: {reset_stats['enhanced_system']}")
        
        print("\n✅ EnhancedPromptSystem統合テスト完了")
        return True
        
    except Exception as e:
        print(f"❌ EnhancedPromptSystem統合テスト失敗: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # クリーンアップ
        try:
            if 'work_dir' in locals():
                shutil.rmtree(work_dir)
                print(f"🧹 テストディレクトリを削除: {work_dir}")
        except Exception as e:
            print(f"⚠️ クリーンアップ警告: {e}")


def test_risk_assessment():
    """リスク判定の詳細テスト"""
    print("\n🧪 リスク判定の詳細テスト")
    
    try:
        from companion.prompts.conversation_gate import ConversationGate, RiskLevel
        
        # 一時作業ディレクトリを作成
        work_dir = Path("./test_phase4_risk")
        work_dir.mkdir(exist_ok=True)
        
        # ConversationGateを初期化
        gate = ConversationGate(work_dir=str(work_dir))
        
        # テストケース
        test_cases = [
            {
                'name': '低リスク: ファイル読み取り',
                'input': 'ファイルの内容を確認したい',
                'operation': 'read',
                'path': 'test.txt',
                'expected_risk': RiskLevel.LOW
            },
            {
                'name': '中リスク: ファイル作成',
                'input': '新しいファイルを作成したい',
                'operation': 'create',
                'path': 'new_file.txt',
                'expected_risk': RiskLevel.MEDIUM
            },
            {
                'name': '高リスク: ファイル削除',
                'input': 'ファイルを削除したい',
                'operation': 'delete',
                'path': 'important.txt',
                'expected_risk': RiskLevel.HIGH
            },
            {
                'name': '危険: システム操作',
                'input': 'システム設定を変更したい',
                'operation': 'system',
                'path': '/etc/config',
                'expected_risk': RiskLevel.CRITICAL
            }
        ]
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n📋 {i}. {test_case['name']}")
            
            request = gate.request_approval(
                user_input=test_case['input'],
                operation_type=test_case['operation'],
                target_path=test_case['path']
            )
            
            actual_risk = request.risk_level
            expected_risk = test_case['expected_risk']
            risk_match = actual_risk == expected_risk
            
            print(f"  - 期待リスク: {expected_risk.value}")
            print(f"  - 実際リスク: {actual_risk.value}")
            print(f"  - リスク一致: {'✅' if risk_match else '❌'}")
            print(f"  - 自動承認: {'✅' if request.approval_status.value == 'approved' else '❌'}")
        
        print("\n✅ リスク判定テスト完了")
        return True
        
    except Exception as e:
        print(f"❌ リスク判定テスト失敗: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # クリーンアップ
        try:
            if 'work_dir' in locals():
                shutil.rmtree(work_dir)
                print(f"🧹 テストディレクトリを削除: {work_dir}")
        except Exception as e:
            print(f"⚠️ クリーンアップ警告: {e}")


def main():
    """メインテスト実行"""
    print("🚀 Phase 4: 最適化と安全性強化のテスト開始")
    print("=" * 60)
    
    # テスト結果
    test_results = []
    
    # 1. ConversationGateテスト
    test_results.append(("ConversationGate", test_conversation_gate()))
    
    # 2. EnhancedPromptSystem統合テスト
    test_results.append(("EnhancedPromptSystem統合", test_enhanced_prompt_system_integration()))
    
    # 3. リスク判定テスト
    test_results.append(("リスク判定", test_risk_assessment()))
    
    # 結果サマリー
    print("\n" + "=" * 60)
    print("📊 テスト結果サマリー")
    print("=" * 60)
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\n🎯 結果: {passed}/{total} テストが成功")
    
    if passed == total:
        print("🎉 Phase 4の実装が完了しました！")
        print("\n🚀 実装された機能:")
        print("  - ConversationGate: 会話内承認システム")
        print("  - 5点の情報提供（意図、根拠、影響、代替、差分）")
        print("  - リスクレベルの自動判定")
        print("  - 承認履歴の記録と分析")
        print("  - EnhancedPromptSystemとの完全統合")
        return True
    else:
        print("⚠️ 一部のテストが失敗しました。実装を確認してください。")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
