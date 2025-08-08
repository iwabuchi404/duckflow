#!/usr/bin/env python3
"""
AIの実際の実行をテスト
"""
import os
import sys
sys.path.insert(0, os.path.abspath('.'))

from codecrafter.main_v2 import DuckflowAgentV2

def test_ai_file_list():
    """AIのファイル一覧実行をテスト"""
    print("=== AI ファイル一覧実行テスト ===")
    
    # エージェント初期化
    agent = DuckflowAgentV2()
    agent.state.debug_mode = True  # デバッグモード有効化
    
    print(f"エージェントワークスペース: {agent.state.workspace.path}")
    print(f"現在のディレクトリ: {os.getcwd()}")
    
    # オーケストレーターを直接テスト
    print("\n=== オーケストレーターのファイル検出テスト ===")
    user_message = "ファイル一覧を"
    requests = agent.orchestrator._detect_file_info_requests(user_message)
    print(f"検出された要求: {requests}")
    
    if requests.get('list_files'):
        print("\n=== ファイルコンテキスト収集テスト ===")
        try:
            context = agent.orchestrator._gather_file_context(requests, agent.state)
            print(f"コンテキスト結果: {context.keys()}")
            
            if context.get('files_list'):
                print(f"ファイル一覧件数: {len(context['files_list'])}")
                if len(context['files_list']) > 0:
                    print("最初の3ファイル:")
                    for file_info in context['files_list'][:3]:
                        print(f"  - {file_info['name']} ({file_info['size']} bytes)")
            
            if context.get('errors'):
                print("エラー:")
                for error in context['errors']:
                    print(f"  - {error}")
                    
        except Exception as e:
            print(f"エラー: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n最終確認 - 現在のディレクトリ: {os.getcwd()}")

if __name__ == "__main__":
    test_ai_file_list()