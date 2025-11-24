"""
Duckflow v0.2.1-alpha 機能デモンストレーション用テストスクリプト
"""
import os
import sys

# エンコーディング設定
os.environ['PYTHONIOENCODING'] = 'utf-8'

def demo_basic_functionality():
    """基本機能のデモ"""
    print("=== Duckflow v0.2.1-alpha 基本機能テスト ===")
    
    # インポートテスト
    try:
        from codecrafter.main_v2 import DuckflowAgentV2
        from codecrafter.state.agent_state import AgentState, WorkspaceInfo
        from codecrafter.orchestration.graph_orchestrator import GraphOrchestrator
        from codecrafter.prompts.prompt_compiler import prompt_compiler
        from codecrafter.tools.rag_tools import rag_tools
        
        print("OK All imports successful")
        
        # AgentState初期化テスト
        workspace = WorkspaceInfo(path=".", files=[], last_modified=None)
        state = AgentState(session_id="demo-test", workspace=workspace)
        print("OK AgentState initialization successful")
        
        # プロンプトコンパイラテスト
        system_prompt = prompt_compiler.compile_system_prompt(state)
        print(f"OK System prompt compiled ({len(system_prompt)} characters)")
        
        # RAG状態確認
        rag_status = rag_tools.get_index_status()
        print(f"OK RAG status: {rag_status.get('status', 'unknown')}")
        
        # DuckflowAgent初期化テスト
        agent = DuckflowAgentV2()
        print("OK DuckflowAgentV2 initialization successful")
        
        print("\nSUCCESS All basic functionality tests passed!")
        return True
        
    except Exception as e:
        print(f"ERROR Test failed: {e}")
        return False

def demo_rag_functionality():
    """RAG機能のデモ（可能な場合）"""
    print("\n=== RAG機能テスト ===")
    
    try:
        from codecrafter.tools.rag_tools import rag_tools
        
        # RAG状態確認
        status = rag_tools.get_index_status()
        print(f"RAG Status: {status.get('status', 'unknown')}")
        
        if status.get('status') == 'error':
            print(f"RAG Error: {status.get('message', 'unknown error')}")
            print("💡 To enable RAG features:")
            print("   1. Set OpenAI API key in environment variables")
            print("   2. Or install sentence-transformers (will download ~500MB)")
            return False
        
        # インデックス状態表示のテスト
        print("OK RAG tools accessible")
        return True
        
    except Exception as e:
        print(f"ERROR RAG test failed: {e}")
        return False

def demo_prompt_enhancement():
    """強化されたプロンプトのデモ"""
    print("\n=== プロンプト強化機能テスト ===")
    
    try:
        from codecrafter.prompts.prompt_compiler import prompt_compiler
        from codecrafter.state.agent_state import AgentState, WorkspaceInfo
        from datetime import datetime
        
        # テスト用状態を作成
        workspace = WorkspaceInfo(
            path="./codecrafter", 
            files=["main.py", "config.py"], 
            current_file="main.py",
            last_modified=datetime.now()
        )
        
        state = AgentState(session_id="demo", workspace=workspace)
        state.current_task = "ファイル編集テスト"
        
        # 基本プロンプトのテスト
        basic_prompt = prompt_compiler.compile_system_prompt(state)
        print(f"OK Basic prompt: {len(basic_prompt)} characters")
        
        # RAG強化プロンプトのテスト（模擬検索結果）
        mock_rag_results = [
            {
                "file_path": "codecrafter/main.py",
                "language": "python", 
                "content": "class DuckflowAgent:\n    def __init__(self):\n        pass",
                "relevance_score": 0.85
            }
        ]
        
        rag_prompt = prompt_compiler.compile_system_prompt(state, mock_rag_results)
        print(f"OK RAG-enhanced prompt: {len(rag_prompt)} characters")
        print(f"OK Enhancement: +{len(rag_prompt) - len(basic_prompt)} characters of context")
        
        return True
        
    except Exception as e:
        print(f"ERROR Prompt test failed: {e}")
        return False

if __name__ == "__main__":
    print("Duckflow v0.2.1-alpha Test Suite")
    print("=" * 50)
    
    results = []
    
    # 基本機能テスト
    results.append(demo_basic_functionality())
    
    # RAG機能テスト
    results.append(demo_rag_functionality())
    
    # プロンプト強化テスト
    results.append(demo_prompt_enhancement())
    
    # 結果サマリー
    print("\n" + "=" * 50)
    print(f"Test Results: {sum(results)}/{len(results)} passed")
    
    if all(results):
        print("SUCCESS: All tests passed! Duckflow v0.2.1-alpha is ready for use.")
        print("\nTo start Duckflow:")
        print("   uv run python run_duckflow_v2.py")
        print("\nAvailable commands:")
        print("   - help: Show all commands")
        print("   - index: Index project for RAG search")
        print("   - search <query>: Search codebase")
        print("   - graph: Show LangGraph execution state")
    else:
        print("WARNING: Some tests failed. Check the error messages above.")