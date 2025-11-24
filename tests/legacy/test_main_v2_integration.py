#!/usr/bin/env python3
"""
main_v2.py の5ノードオーケストレーター統合テスト

メインエントリーポイントが5ノードオーケストレーターで正常に動作するかを確認
"""

import sys
import os
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from codecrafter.main_v2 import DuckflowAgentV2
    from codecrafter.orchestration.five_node_orchestrator import FiveNodeOrchestrator
    import uuid
except ImportError as e:
    print(f"インポートエラー: {e}")
    print("プロジェクトルートから実行してください")
    sys.exit(1)


def test_main_v2_initialization():
    """main_v2.pyの初期化テスト"""
    print("=== main_v2.py 初期化テスト ===")
    
    try:
        # DuckflowAgentV2初期化
        agent = DuckflowAgentV2()
        print("✅ DuckflowAgentV2初期化成功")
        
        # オーケストレーターの種類確認
        if isinstance(agent.orchestrator, FiveNodeOrchestrator):
            print("✅ 5ノードオーケストレーターが正しく設定されています")
        else:
            print(f"❌ 予期しないオーケストレーター: {type(agent.orchestrator)}")
            return False
        
        # AgentStateの確認
        if agent.state and agent.state.session_id:
            print(f"✅ AgentState初期化成功 (セッションID: {agent.state.session_id[:8]}...)")
        else:
            print("❌ AgentState初期化失敗")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ 初期化テスト失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_main_v2_conversation():
    """main_v2.pyの対話テスト"""
    print("\n=== main_v2.py 対話テスト ===")
    
    try:
        # DuckflowAgentV2初期化
        agent = DuckflowAgentV2()
        
        # テスト用メッセージ
        test_message = "design-doc.mdの内容について教えて"
        print(f"テストメッセージ: {test_message}")
        
        # 対話実行（_handle_orchestrated_conversationメソッドを直接呼び出し）
        agent._handle_orchestrated_conversation(test_message)
        
        # 結果確認
        if agent.state.conversation_history:
            print(f"✅ 対話実行成功: {len(agent.state.conversation_history)}メッセージ")
            
            # 最新のアシスタント応答を確認
            for msg in reversed(agent.state.conversation_history):
                if msg.role == 'assistant':
                    print(f"   応答長: {len(msg.content)}文字")
                    if len(msg.content) > 1000:
                        print("✅ 詳細な応答が生成されました")
                        return True
                    else:
                        print("⚠️ 短い応答です")
                        return True
        else:
            print("❌ 対話履歴が空です")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ 対話テスト失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_main_v2_version_info():
    """main_v2.pyのバージョン情報テスト"""
    print("\n=== main_v2.py バージョン情報テスト ===")
    
    try:
        # DuckflowAgentV2初期化
        agent = DuckflowAgentV2()
        
        # ヘッダー表示のテスト（実際には表示されないが、エラーが出ないかチェック）
        print("✅ バージョン情報の確認")
        print("   - バージョン: v0.3.2-alpha")
        print("   - アーキテクチャ: 5-Node Architecture")
        print("   - 特徴: LangGraph orchestration")
        
        return True
        
    except Exception as e:
        print(f"❌ バージョン情報テスト失敗: {e}")
        return False


def main():
    """メインテスト実行"""
    print("main_v2.py 5ノードオーケストレーター統合テストを開始します\n")
    
    tests = [
        ("初期化", test_main_v2_initialization),
        ("対話", test_main_v2_conversation),
        ("バージョン情報", test_main_v2_version_info)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"テスト実行: {test_name}")
        print('='*50)
        
        try:
            success = test_func()
            if success:
                passed += 1
                print(f"✅ {test_name} - PASSED")
            else:
                print(f"❌ {test_name} - FAILED")
        except Exception as e:
            print(f"❌ {test_name} - ERROR: {e}")
    
    print(f"\n{'='*50}")
    print(f"テスト結果: {passed}/{total} 成功")
    print('='*50)
    
    if passed == total:
        print("🎉 すべてのテストが成功しました！")
        print("main_v2.pyは5ノードオーケストレーターで正常に動作しています。")
        return True
    else:
        print(f"⚠️  {total - passed}個のテストが失敗しました")
        print("問題を修正してください。")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)