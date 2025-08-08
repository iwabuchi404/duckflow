#!/usr/bin/env python3
"""
修正されたファイルアクセス機能をテスト
"""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from codecrafter.tools.file_tools import file_tools
from codecrafter.orchestration.graph_orchestrator import GraphOrchestrator
from codecrafter.state.agent_state import AgentState

def test_file_structure_simple():
    """シンプルなファイル構造テスト"""
    print("=== シンプルなファイルアクセステスト ===")
    
    # ダミー状態を作成
    state = AgentState(
        session_id="test",
        conversation_history=[]
    )
    
    orchestrator = GraphOrchestrator(state)
    
    # ファイル要求を生成
    user_message = "現在のファイル構造を教えて"
    requests = orchestrator._detect_file_info_requests(user_message)
    print(f"検出された要求: {requests}")
    
    if requests.get('list_files'):
        try:
            # 直接ファイルツールを使用（UIエラー回避）
            file_list = file_tools.list_files(".", recursive=True)
            print(f"発見したファイル数: {len(file_list)}")
            
            # プロジェクトファイルのみを表示
            project_files = [f for f in file_list if not any(ignore in f['path'] for ignore in ['.git', '__pycache__', '.venv', 'node_modules'])]
            
            print("\n=== プロジェクトファイル（上位20件） ===")
            for i, file_info in enumerate(project_files[:20]):
                name = file_info['name']
                size = file_info['size']
                path = file_info['relative_path']
                print(f"  {i+1:2d}. {name} ({size:,} bytes) - {path}")
            
            if len(project_files) > 20:
                print(f"     ... 他{len(project_files) - 20}件")
                
            return project_files
        except Exception as e:
            print(f"エラー: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    return []

if __name__ == "__main__":
    files = test_file_structure_simple()
    print(f"\n総計: {len(files)} プロジェクトファイル")