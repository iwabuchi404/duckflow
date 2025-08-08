#!/usr/bin/env python3
"""
ステップ2d グラフ構造のユニットテスト
APIキーなしでグラフの構造とノード定義をテスト
"""

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
from codecrafter.base.config import ConfigManager


def test_graph_structure():
    """グラフ構造の定義テスト"""
    print("=== グラフ構造テスト ===")
    
    # ダミー設定でテスト
    os.environ['GROQ_API_KEY'] = 'dummy_key_for_test'
    config_manager = ConfigManager()
    config = config_manager.load_config()
    orchestrator = GraphOrchestrator(config)
    
    try:
        # グラフ構築をテスト
        graph = orchestrator._build_graph()
        print("✅ グラフ構築成功")
        
        # ノード一覧を取得
        nodes = list(graph.nodes.keys())
        expected_nodes = [
            "思考", "コンテキスト収集", "危険性評価", 
            "人間承認", "ツール実行", "結果確認", "エラー分析"
        ]
        
        print(f"定義されたノード: {nodes}")
        print(f"期待されるノード: {expected_nodes}")
        
        # ノードの数をチェック
        if len(nodes) == len(expected_nodes):
            print("✅ ノード数が正しい")
        else:
            print(f"❌ ノード数が違います: {len(nodes)} != {len(expected_nodes)}")
        
        # 各ノードが存在するかチェック
        missing_nodes = []
        for expected_node in expected_nodes:
            if expected_node not in nodes:
                missing_nodes.append(expected_node)
        
        if not missing_nodes:
            print("✅ すべてのノードが定義されています")
        else:
            print(f"❌ 不足しているノード: {missing_nodes}")
        
        return len(missing_nodes) == 0
        
    except Exception as e:
        print(f"❌ グラフ構築エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_node_functions():
    """ノード関数の存在テスト"""
    print("\n=== ノード関数存在テスト ===")
    
    os.environ['GROQ_API_KEY'] = 'dummy_key_for_test'
    config_manager = ConfigManager()
    config = config_manager.load_config()
    orchestrator = GraphOrchestrator(config)
    
    expected_methods = [
        '_thinking_node',
        '_context_collection_node',
        '_safety_assessment_node',
        '_human_approval_node',
        '_tool_execution_node',
        '_result_verification_node',
        '_error_analysis_node'
    ]
    
    missing_methods = []
    for method_name in expected_methods:
        if not hasattr(orchestrator, method_name):
            missing_methods.append(method_name)
        else:
            print(f"✅ {method_name} が存在")
    
    if not missing_methods:
        print("✅ すべてのノード関数が定義されています")
        return True
    else:
        print(f"❌ 不足しているノード関数: {missing_methods}")
        return False


def test_routing_functions():
    """ルーティング関数の存在テスト"""
    print("\n=== ルーティング関数存在テスト ===")
    
    os.environ['GROQ_API_KEY'] = 'dummy_key_for_test'
    config_manager = ConfigManager()
    config = config_manager.load_config()
    orchestrator = GraphOrchestrator(config)
    
    expected_routing_methods = [
        '_requires_human_approval',
        '_process_human_decision',
        '_should_analyze_errors',
        '_should_retry_after_error'
    ]
    
    missing_routing = []
    for method_name in expected_routing_methods:
        if not hasattr(orchestrator, method_name):
            missing_routing.append(method_name)
        else:
            print(f"✅ {method_name} が存在")
    
    if not missing_routing:
        print("✅ すべてのルーティング関数が定義されています")
        return True
    else:
        print(f"❌ 不足しているルーティング関数: {missing_routing}")
        return False


def test_helper_functions():
    """ヘルパー関数の存在テスト"""
    print("\n=== ヘルパー関数存在テスト ===")
    
    os.environ['GROQ_API_KEY'] = 'dummy_key_for_test'
    config_manager = ConfigManager()
    config = config_manager.load_config()
    orchestrator = GraphOrchestrator(config)
    
    expected_helper_methods = [
        '_analyze_safety_risks',
        '_analyze_tool_error'
    ]
    
    missing_helpers = []
    for method_name in expected_helper_methods:
        if not hasattr(orchestrator, method_name):
            missing_helpers.append(method_name)
        else:
            print(f"✅ {method_name} が存在")
    
    if not missing_helpers:
        print("✅ すべてのヘルパー関数が定義されています")
        return True
    else:
        print(f"❌ 不足しているヘルパー関数: {missing_helpers}")
        return False


def main():
    """メインテスト実行"""
    print("ステップ2d グラフ構造ユニットテストを開始します\n")
    
    tests = [
        ("グラフ構造", test_graph_structure),
        ("ノード関数存在", test_node_functions),
        ("ルーティング関数存在", test_routing_functions),
        ("ヘルパー関数存在", test_helper_functions)
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
        print("🎉 すべての構造テストが成功しました！")
        return True
    else:
        print(f"⚠️  {total - passed}個のテストが失敗しました")
        return False


if __name__ == "__main__":
    main()