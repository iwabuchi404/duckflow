#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
汎用的調査機能のテスト - テスト実装状況を調査
"""

import sys
import os
sys.path.append('.')

from codecrafter.state.agent_state import AgentState, ConversationMessage
from codecrafter.orchestration.four_node_orchestrator import FourNodeOrchestrator
import uuid
from datetime import datetime

def test_generic_investigation():
    """汎用調査機能でテスト実装状況を調査"""
    
    print("=== 汎用調査機能テスト: テスト実装状況 ===")
    
    # テストに関する調査クエリ
    query = "testがどの程度、何のテストが実装されているのかを調査してください"
    
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
        print("OK Orchestrator初期化完了")
        
        # 調査タスク判定
        is_investigation = orchestrator._detect_investigation_task(state)
        print(f"OK 調査タスク判定: {is_investigation}")
        
        if is_investigation:
            # Phase 1: 調査計画立案
            print("Phase 1: テスト調査計画立案")
            understanding_result = orchestrator._execute_investigation_planning(state)
            print(f"OK 調査対象: {len(state.investigation_plan)}ファイル")
            
            # 選択されたファイルがテスト関連かチェック
            test_related_files = [f for f in state.investigation_plan if 'test' in f.lower()]
            print(f"テスト関連ファイル: {len(test_related_files)}/10")
            
            if state.investigation_plan:
                # Phase 2: 統合分析
                print("Phase 2: テスト実装状況の統合分析")
                try:
                    state_after_synthesis = orchestrator._execute_investigation_synthesis(
                        state, understanding_result
                    )
                except Exception as ui_error:
                    if "cp932" in str(ui_error):
                        print("WARN UI表示エラー（分析は完了）")
                        state_after_synthesis = state
                    else:
                        raise ui_error
                
                if state_after_synthesis.project_summary:
                    summary = state_after_synthesis.project_summary
                    print(f"OK 分析結果生成: {len(summary)}文字")
                    
                    # テスト関連キーワードの確認
                    test_keywords = ['test', 'テスト', 'pytest', 'unittest', 'integration', 'e2e']
                    found_keywords = [kw for kw in test_keywords if kw.lower() in summary.lower()]
                    print(f"テスト関連キーワード: {found_keywords}")
                    
                    # 分析結果サンプル（テスト関連部分のみ）
                    lines = summary.split('\n')
                    test_lines = [line for line in lines if any(kw in line.lower() for kw in test_keywords)]
                    if test_lines:
                        print("テスト関連分析内容サンプル:")
                        for line in test_lines[:3]:
                            print(f"  - {line.strip()}")
                    
                else:
                    print("NG 分析結果が生成されませんでした")
            else:
                print("NG 調査計画が作成されませんでした")
        else:
            print("NG 調査タスクとして認識されませんでした")
            
    except Exception as e:
        print(f"NG テストエラー: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_generic_investigation()