#!/usr/bin/env python3
"""
ワークスペース問題をデバッグ
"""
import os
import sys
sys.path.insert(0, os.path.abspath('.'))

from codecrafter.main_v2 import DuckflowAgentV2

def test_workspace_setup():
    """ワークスペース設定をテスト"""
    print("=== ワークスペース設定テスト ===")
    
    print(f"スクリプト実行時の作業ディレクトリ: {os.getcwd()}")
    
    # エージェント初期化
    agent = DuckflowAgentV2()
    
    print(f"エージェントのワークスペースパス: {agent.state.workspace.path}")
    print(f"実際の作業ディレクトリ: {os.getcwd()}")
    
    # ファイル一覧を直接取得してテスト
    try:
        from codecrafter.tools.file_tools import file_tools
        
        files_from_cwd = file_tools.list_files(os.getcwd(), recursive=True)
        files_from_workspace = file_tools.list_files(agent.state.workspace.path, recursive=True)
        
        print(f"\n現在のディレクトリのファイル数: {len(files_from_cwd)}")
        print(f"ワークスペースのファイル数: {len(files_from_workspace)}")
        
        if len(files_from_cwd) > 0:
            print("\n現在のディレクトリの最初の5ファイル:")
            for file_info in files_from_cwd[:5]:
                print(f"  - {file_info['name']} ({file_info['size']} bytes)")
        
        if len(files_from_workspace) > 0:
            print("\nワークスペースの最初の5ファイル:")
            for file_info in files_from_workspace[:5]:
                print(f"  - {file_info['name']} ({file_info['size']} bytes)")
        
        return files_from_workspace
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return []

if __name__ == "__main__":
    test_workspace_setup()