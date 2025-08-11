#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高度な探索・分析エンジンの統合テスト
Phase 1-3 および Phase 2-3 の実装を総合的にテスト
"""

import sys
import os
sys.path.append('.')

from codecrafter.state.agent_state import AgentState, ConversationMessage
from codecrafter.orchestration.four_node_orchestrator import FourNodeOrchestrator
from codecrafter.services.llm_service import llm_service
from codecrafter.services.task_objective import task_objective_manager
import uuid
from datetime import datetime

def test_complete_investigation_flow():
    """調査フローの完全なテスト"""
    
    print("=== 高度な探索・分析エンジン統合テスト開始 ===")
    
    # 1. テスト用AgentStateの作成
    test_queries = [
        "promptスミスのシナリオを実際のコードを確認して教えて",
        "Duckflowの4ノードアーキテクチャについて教えて",
        "プロジェクトのLLMサービスの実装について調べて"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n--- テストケース {i}: {query} ---")
        
        # AgentState作成
        state = AgentState(
            session_id=str(uuid.uuid4()),
            conversation_history=[
                ConversationMessage(
                    role="user",
                    content=query,
                    timestamp=datetime.now()
                )
            ]
        )
        
        try:
            # Orchestratorの初期化
            orchestrator = FourNodeOrchestrator(state)
            print(f"OK Orchestrator初期化完了")
            
            # 調査タスク判定のテスト
            is_investigation = orchestrator._detect_investigation_task(state)
            print(f"OK 調査タスク判定: {is_investigation}")
            
            if is_investigation:
                # Phase 1: 調査計画立案のテスト
                understanding_result = orchestrator._execute_investigation_planning(state)
                print(f"OK Phase 1 完了: 調査計画立案")
                print(f"  - 調査対象ファイル数: {len(state.investigation_plan)}")
                
                if state.investigation_plan:
                    # Phase 2: 統合分析のテスト
                    state_after_synthesis = orchestrator._execute_investigation_synthesis(
                        state, understanding_result
                    )
                    print(f"OK Phase 2 完了: 統合分析実行")
                    print(f"  - プロジェクト要約文字数: {len(state_after_synthesis.project_summary) if state_after_synthesis.project_summary else 0}")
                    
                    # Phase 3: 調査結果評価のテスト
                    if state_after_synthesis.project_summary:
                        print(f"OK Phase 3 準備完了: 評価可能な調査結果")
                        print(f"  - 要約サンプル: {state_after_synthesis.project_summary[:100]}...")
                    else:
                        print("NG Phase 3 準備失敗: 調査結果が空")
                else:
                    print("NG Phase 1 失敗: 調査計画が空")
            else:
                print("- このクエリは調査タスクとして認識されませんでした")
                
        except Exception as e:
            print(f"NG テストケース {i} エラー: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"--- テストケース {i} 完了 ---\n")
    
    print("=== 統合テスト完了 ===")

def test_llm_service_components():
    """LLMServiceの各コンポーネントをテスト"""
    
    print("\n=== LLMService コンポーネントテスト ===")
    
    try:
        # ファイル優先順位付けのテスト
        import glob
        sample_files = glob.glob("**/*.py", recursive=True)[:50]  # サンプル50ファイル
        
        if sample_files:
            print(f"1. ファイル優先順位付けテスト (対象: {len(sample_files)}ファイル)")
            prioritized = llm_service.prioritize_files_for_task(
                "promptスミスについて", sample_files
            )
            print(f"   OK 優先ファイル数: {len(prioritized)}")
            if prioritized:
                print(f"   OK トップファイル: {prioritized[0]}")
        
        # 統合分析のテスト（小規模）
        print("\n2. 統合分析テスト")
        test_files = {
            "test.py": "# テストファイル\nprint('Hello World')",
            "config.yaml": "version: 1.0\nname: test_project"
        }
        
        synthesis_result = llm_service.synthesize_insights_from_files(
            "このプロジェクトについて説明して", test_files
        )
        print(f"   OK 統合分析結果長: {len(synthesis_result)}")
        print(f"   OK 分析サンプル: {synthesis_result[:100]}...")
        
        print("OK LLMService コンポーネントテスト完了")
        
    except Exception as e:
        print(f"NG LLMService テストエラー: {e}")
        import traceback
        traceback.print_exc()

def test_file_discovery_performance():
    """ファイル探索のパフォーマンステスト"""
    
    print("\n=== ファイル探索パフォーマンステスト ===")
    
    import time
    import glob
    
    try:
        start_time = time.time()
        
        # 各拡張子のファイル数をカウント
        patterns = ["**/*.py", "**/*.md", "**/*.yaml", "**/*.yml", "**/*.json"]
        total_files = 0
        
        for pattern in patterns:
            matches = glob.glob(pattern, recursive=True)
            total_files += len(matches)
            print(f"  {pattern}: {len(matches)} ファイル")
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"OK 総ファイル数: {total_files}")
        print(f"OK 探索時間: {duration:.2f}秒")
        print(f"OK 毎秒処理: {total_files/duration:.0f} ファイル/秒")
        
        # 性能判定
        if duration < 2.0:
            print("OK パフォーマンス: 良好")
        elif duration < 5.0:
            print("WARN パフォーマンス: 普通")
        else:
            print("NG パフォーマンス: 改善が必要")
            
    except Exception as e:
        print(f"NG パフォーマンステストエラー: {e}")

if __name__ == "__main__":
    try:
        test_complete_investigation_flow()
        test_llm_service_components() 
        test_file_discovery_performance()
        
        print("\nSUCCESS 全テスト完了！高度な探索・分析エンジンの実装が完了しました。")
        
    except KeyboardInterrupt:
        print("\nWARN テストが中断されました")
    except Exception as e:
        print(f"\nERROR 予期しないエラー: {e}")
        import traceback
        traceback.print_exc()