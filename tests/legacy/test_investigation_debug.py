#!/usr/bin/env python3
"""調査機能のデバッグテスト"""

import sys
import os
sys.path.append('.')

from codecrafter.state.agent_state import AgentState, ConversationMessage
from codecrafter.orchestration.four_node_orchestrator import FourNodeOrchestrator
from codecrafter.services.llm_service import llm_service
import uuid
from datetime import datetime

def test_investigation_functionality():
    """調査機能の各段階をテスト"""
    
    print("=== 調査機能デバッグテスト開始 ===")
    
    # 1. AgentStateの作成
    state = AgentState(
        session_id=str(uuid.uuid4()),
        conversation_history=[
            ConversationMessage(
                role="user",
                content="promptスミスのシナリオを実際のコードを確認して教えて",
                timestamp=datetime.now()
            )
        ]
    )
    
    print(f"1. AgentState作成完了: {state.session_id}")
    
    # 2. FourNodeOrchestratorの初期化
    try:
        orchestrator = FourNodeOrchestrator(state)
        print("2. FourNodeOrchestrator初期化完了")
    except Exception as e:
        print(f"2. Orchestrator初期化エラー: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 3. 調査タスク判定のテスト
    try:
        is_investigation = orchestrator._detect_investigation_task(state)
        print(f"3. 調査タスク判定: {is_investigation}")
    except Exception as e:
        print(f"3. 調査タスク判定エラー: {e}")
        return
    
    # 4. ファイル探索のテスト
    try:
        # globを直接テスト
        import glob
        from pathlib import Path
        
        all_files = []
        search_patterns = ["**/*.py", "**/*.md", "**/*.yaml"]
        
        cwd = os.getcwd()
        print(f"4. 現在のディレクトリ: {cwd}")
        
        for pattern in search_patterns:
            matches = glob.glob(pattern, recursive=True)
            print(f"   パターン {pattern}: {len(matches)} マッチ")
            all_files.extend(matches)
        
        unique_files = list(set(all_files))
        print(f"4. ファイル探索完了: {len(unique_files)}ファイル発見")
        
        if unique_files:
            print(f"   サンプルファイル: {unique_files[:3]}")
        
    except Exception as e:
        print(f"4. ファイル探索エラー: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 5. LLM優先順位付けのテスト
    if unique_files:
        try:
            prioritized = llm_service.prioritize_files_for_task(
                "promptスミスのシナリオを実際のコードを確認して教えて",
                unique_files[:50]  # 最初の50ファイルで試す
            )
            print(f"5. LLM優先順位付け完了: {len(prioritized)}ファイル")
            if prioritized:
                print("   優先ファイル:")
                for i, f in enumerate(prioritized[:5], 1):
                    print(f"     {i}. {f}")
        except Exception as e:
            print(f"5. LLM優先順位付けエラー: {e}")
            import traceback
            traceback.print_exc()
    
    print("=== テスト完了 ===")

if __name__ == "__main__":
    test_investigation_functionality()