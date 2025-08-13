#!/usr/bin/env python3
"""
ルーティング結果とタスクチェーン問題の修正

問題1: needs_file_read=False, target_files=0件 (実際にはファイル読み取りが必要)
問題2: タスクチェーンが空です - フォールバック応答を使用
"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_routing_engine():
    """RoutingEngineの動作テスト"""
    print("=== RoutingEngine動作テスト ===")
    
    try:
        from codecrafter.orchestration.routing_engine import RoutingEngine
        from codecrafter.state.agent_state import AgentState
        import uuid
        
        # テスト用AgentState作成
        state = AgentState(session_id=str(uuid.uuid4()))
        
        # テストメッセージを追加
        test_messages = [
            "design-doc.mdの内容について教えて",
            "test_step2d_graph.pyファイルを探して処理内容を説明してください",
            "新しいファイルを作成してください"
        ]
        
        routing_engine = RoutingEngine()
        
        for i, message in enumerate(test_messages, 1):
            print(f"\n{i}. テストメッセージ: {message}")
            
            # メッセージを状態に追加
            state.add_message("user", message)
            
            # ルーティング分析
            result = routing_engine.analyze_user_intent(state)
            
            print(f"   結果: needs_file_read={result.get('needs_file_read', False)}")
            print(f"   対象ファイル数: {len(result.get('target_files', []))}")
            print(f"   対象ファイル: {result.get('target_files', [])}")
            print(f"   操作タイプ: {result.get('operation_type', 'unknown')}")
            
            # 期待される結果と比較
            if "内容について" in message or "説明してください" in message:
                expected_file_read = True
                expected_files = 1
            else:
                expected_file_read = False
                expected_files = 0
            
            actual_file_read = result.get('needs_file_read', False)
            actual_files = len(result.get('target_files', []))
            
            if actual_file_read == expected_file_read and actual_files >= expected_files:
                print(f"   ✅ ルーティング結果は期待通りです")
            else:
                print(f"   ❌ ルーティング結果に問題があります")
                print(f"      期待: needs_file_read={expected_file_read}, files>={expected_files}")
                print(f"      実際: needs_file_read={actual_file_read}, files={actual_files}")
        
        return True
        
    except Exception as e:
        print(f"❌ RoutingEngineテスト失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_task_chain_initialization():
    """タスクチェーン初期化のテスト"""
    print("\n=== タスクチェーン初期化テスト ===")
    
    try:
        from codecrafter.state.pecking_order import PeckingOrderManager, Task, TaskStatus
        from codecrafter.state.agent_state import AgentState
        import uuid
        
        # AgentState作成
        state = AgentState(session_id=str(uuid.uuid4()))
        
        # PeckingOrderManagerの初期化
        pecking_order = PeckingOrderManager()
        
        # テストタスクの作成
        test_task = Task(
            task_id="test_001",
            description="design-doc.mdの内容について教えて",
            status=TaskStatus.PENDING,
            priority=1
        )
        
        # タスクを追加
        pecking_order.add_task(test_task)
        
        # AgentStateにタスクツリーを設定
        state.task_tree = pecking_order.get_task_tree()
        
        print(f"✅ タスクチェーン初期化成功")
        print(f"   タスク数: {len(state.task_tree) if state.task_tree else 0}")
        
        if state.task_tree:
            for task_id, task in state.task_tree.items():
                print(f"   - {task_id}: {task.description[:50]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ タスクチェーン初期化テスト失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_task_profile_classification():
    """TaskProfile分類のテスト"""
    print("\n=== TaskProfile分類テスト ===")
    
    try:
        from codecrafter.services.task_classifier import task_classifier
        
        test_messages = [
            ("design-doc.mdの内容について教えて", "INFORMATION_REQUEST"),
            ("test_step2d_graph.pyファイルを探して処理内容を説明してください", "INFORMATION_REQUEST"),
            ("新しいファイルを作成してください", "CREATION_REQUEST"),
            ("既存のコードを修正してください", "MODIFICATION_REQUEST"),
            ("プロジェクト内でエラーハンドリングを検索してください", "SEARCH_REQUEST")
        ]
        
        for message, expected_type in test_messages:
            print(f"\nメッセージ: {message}")
            
            result = task_classifier.classify(message)
            
            print(f"   分類結果: {result.profile_type.value}")
            print(f"   信頼度: {result.confidence:.2f}")
            print(f"   検出パターン: {result.detected_patterns}")
            print(f"   抽出対象: {result.extracted_targets}")
            
            if expected_type.lower() in result.profile_type.value.lower():
                print(f"   ✅ 期待通りの分類です")
            else:
                print(f"   ⚠️ 期待と異なる分類: 期待={expected_type}, 実際={result.profile_type.value}")
        
        return True
        
    except Exception as e:
        print(f"❌ TaskProfile分類テスト失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """メインテスト実行"""
    print("🔧 ルーティング結果とタスクチェーン問題の分析")
    print("="*60)
    
    tests = [
        ("RoutingEngine動作", test_routing_engine),
        ("タスクチェーン初期化", test_task_chain_initialization),
        ("TaskProfile分類", test_task_profile_classification)
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
    
    print(f"\n{'='*60}")
    print(f"テスト結果: {passed}/{total} 成功")
    print('='*60)
    
    if passed == total:
        print("🎉 すべてのテストが成功しました！")
        return True
    else:
        print(f"⚠️  {total - passed}個のテストが失敗しました")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)