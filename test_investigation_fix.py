#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ProjectContextエラー修正後のテスト
"""

import sys
import os
sys.path.append('.')

from codecrafter.state.agent_state import AgentState, ConversationMessage
from codecrafter.orchestration.four_node_orchestrator import FourNodeOrchestrator
import uuid
from datetime import datetime

def test_investigation_fix():
    """修正後の調査機能をテスト"""
    
    print("=== ProjectContextエラー修正後テスト ===")
    
    # テストクエリ
    query = "promptスミスのシナリオを実際のコードを確認して教えて"
    
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
        
        # Phase 1: 調査計画立案
        understanding_result = orchestrator._execute_investigation_planning(state)
        print(f"OK Phase 1 完了: {len(state.investigation_plan)}ファイル選択")
        
        if state.investigation_plan:
            # Phase 2: 統合分析（修正版）
            state_after_synthesis = orchestrator._execute_investigation_synthesis(
                state, understanding_result
            )
            
            if state_after_synthesis.project_summary:
                print(f"OK Phase 2 完了: {len(state_after_synthesis.project_summary)}文字の分析結果")
                print(f"分析結果サンプル: {state_after_synthesis.project_summary[:200]}...")
            else:
                print("NG Phase 2 失敗: 分析結果が空")
        else:
            print("NG Phase 1 失敗: 調査計画が空")
            
    except Exception as e:
        print(f"NG テストエラー: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_investigation_fix()