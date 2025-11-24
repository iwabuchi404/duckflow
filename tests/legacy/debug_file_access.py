#!/usr/bin/env python3
"""
ファイルアクセス機能デバッグ用スクリプト
"""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from codecrafter.tools.file_tools import file_tools
from codecrafter.orchestration.graph_orchestrator import GraphOrchestrator
from codecrafter.state.agent_state import AgentState

def test_file_list_direct():
    """ファイルツールを直接テスト"""
    print("=== ファイルツール直接テスト ===")
    try:
        files = file_tools.list_files(".", recursive=True)
        print(f"発見したファイル数: {len(files)}")
        for i, file_info in enumerate(files[:10]):
            print(f"  {i+1}. {file_info['name']} ({file_info['size']} bytes)")
        if len(files) > 10:
            print(f"  ... 他{len(files) - 10}件")
        return files
    except Exception as e:
        print(f"エラー: {e}")
        return []

def test_file_detection():
    """ファイル要求検出機能をテスト"""
    print("\n=== ファイル要求検出テスト ===")
    
    # ダミー状態を作成
    state = AgentState(
        session_id="test",
        conversation_history=[]
    )
    
    orchestrator = GraphOrchestrator(state)
    
    test_messages = [
        "現在のファイル構造を教えて",
        "ファイル一覧を見せて",
        "config.yamlを読んで",
        "ls してください"
    ]
    
    for msg in test_messages:
        print(f"\nメッセージ: '{msg}'")
        requests = orchestrator._detect_file_info_requests(msg)
        print(f"検出結果: {requests}")

def test_file_context_gathering():
    """ファイルコンテキスト収集をテスト"""
    print("\n=== ファイルコンテキスト収集テスト ===")
    
    # ダミー状態を作成
    state = AgentState(
        session_id="test",
        conversation_history=[]
    )
    
    orchestrator = GraphOrchestrator(state)
    
    # テスト要求
    requests = {
        'list_files': True,
        'read_files': ['main.py'],
        'get_file_info': []
    }
    
    print(f"テスト要求: {requests}")
    try:
        context = orchestrator._gather_file_context(requests, state)
        print(f"収集したコンテキスト: {context.keys()}")
        
        if context.get('files_list'):
            print(f"ファイル一覧件数: {len(context['files_list'])}")
        
        if context.get('file_contents'):
            print(f"読み込みファイル数: {len(context['file_contents'])}")
            for file_path in context['file_contents']:
                print(f"  - {file_path}: {len(context['file_contents'][file_path])} 文字")
        
        if context.get('errors'):
            print(f"エラー: {context['errors']}")
            
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_file_list_direct()
    test_file_detection()
    test_file_context_gathering()