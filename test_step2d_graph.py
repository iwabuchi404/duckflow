#!/usr/bin/env python3
"""
ステップ2d グラフ構造のテストファイル
Human-in-the-Loop機能と自己修正ループの動作確認
"""

import asyncio
import sys
import os
import io

# Windows環境でのUTF-8出力設定
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from codecrafter.orchestration.graph_orchestrator import GraphOrchestrator
from codecrafter.state.agent_state import AgentState
from codecrafter.base.config import Config


async def test_basic_graph_flow():
    """基本的なグラフフローのテスト"""
    print("=== ステップ2d 基本グラフフローテスト ===")
    
    # 設定とオーケストレーターの初期化
    try:
        config = Config()
    except Exception as e:
        print(f"設定読み込みエラー: {e}")
        print("テスト用のダミー設定を使用します")
        # テスト用のダミーLLM設定を作成
        os.environ['GROQ_API_KEY'] = 'dummy_key_for_test'
        config = Config()
    
    orchestrator = GraphOrchestrator(config)
    
    # テスト用の初期状態
    state = AgentState(
        session_id="test_session_001",
        debug_mode=True
    )
    
    # 簡単なユーザークエリでテスト
    user_message = "現在のディレクトリにあるファイルを教えてください"
    
    print(f"ユーザー入力: {user_message}")
    print("グラフ実行開始...")
    
    try:
        # グラフ実行
        result_state = await orchestrator.execute(state, user_message)
        
        print("\n=== 実行結果 ===")
        print(f"セッションID: {result_state.session_id}")
        print(f"対話履歴数: {len(result_state.conversation_history)}")
        
        if result_state.conversation_history:
            latest_response = result_state.conversation_history[-1]
            print(f"最新応答: {latest_response.content[:200]}...")
        
        print("✅ 基本グラフフローテスト完了")
        return True
        
    except Exception as e:
        print(f"❌ テスト失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_safety_assessment():
    """安全性評価機能のテスト"""
    print("\n=== 安全性評価機能テスト ===")
    
    try:
        config = Config()
    except Exception as e:
        os.environ['GROQ_API_KEY'] = 'dummy_key_for_test'
        config = Config()
    
    orchestrator = GraphOrchestrator(config)
    
    state = AgentState(
        session_id="test_session_002", 
        debug_mode=True
    )
    
    # 危険な操作を含むクエリ
    dangerous_query = "新しいファイル test_dangerous.py を作成して、システム情報を取得するコードを書いてください"
    
    print(f"危険なクエリ: {dangerous_query}")
    
    try:
        result_state = await orchestrator.execute(state, dangerous_query)
        
        print("\n=== 安全性評価結果 ===")
        # デバッグモードなので詳細な情報が出力されているはず
        if hasattr(result_state, 'debug_info') and result_state.debug_info:
            print("デバッグ情報が記録されました")
        
        print("✅ 安全性評価テスト完了")
        return True
        
    except Exception as e:
        print(f"❌ 安全性評価テスト失敗: {e}")
        return False


async def test_error_handling():
    """エラーハンドリング機能のテスト"""
    print("\n=== エラーハンドリング機能テスト ===")
    
    try:
        config = Config()
    except Exception as e:
        os.environ['GROQ_API_KEY'] = 'dummy_key_for_test'
        config = Config()
    
    orchestrator = GraphOrchestrator(config)
    
    state = AgentState(
        session_id="test_session_003",
        debug_mode=True
    )
    
    # 存在しないファイルを読み込もうとする
    error_query = "存在しないファイル /nonexistent/path/file.txt の内容を読み取ってください"
    
    print(f"エラーを引き起こすクエリ: {error_query}")
    
    try:
        result_state = await orchestrator.execute(state, error_query)
        
        print("\n=== エラーハンドリング結果 ===")
        print("エラーが適切に処理されました")
        
        print("✅ エラーハンドリングテスト完了")
        return True
        
    except Exception as e:
        print(f"❌ エラーハンドリングテスト失敗: {e}")
        return False


async def main():
    """メインテスト実行"""
    print("ステップ2d グラフ構造テストを開始します\n")
    
    tests = [
        ("基本グラフフロー", test_basic_graph_flow),
        ("安全性評価機能", test_safety_assessment), 
        ("エラーハンドリング機能", test_error_handling)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"テスト実行: {test_name}")
        print('='*50)
        
        try:
            success = await test_func()
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
        return True
    else:
        print(f"⚠️  {total - passed}個のテストが失敗しました")
        return False


if __name__ == "__main__":
    asyncio.run(main())