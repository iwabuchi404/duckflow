#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
簡単なActionIDシステムテスト
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

try:
    # テスト1: ActionResultクラス
    print("ActionResult クラステスト開始")
    from companion.state.action_result import ActionResult
    from datetime import datetime
    
    # ActionResult作成テスト
    result = ActionResult(
        action_id="test_001",
        operation="file_ops.read_file",
        result="テストファイル内容",
        timestamp=datetime.now(),
        action_list_id="al_test123",
        sequence_number=0
    )
    
    print(f"ActionResult作成成功: {result.action_id}")
    print(f"結果要約: {result.get_result_summary(30)}")
    print(f"辞書変換: {result.to_dict()}")
    
    # テスト2: AgentStateのActionResult管理
    print("\nAgentState ActionResult管理テスト開始")
    from companion.state.agent_state import AgentState
    
    agent_state = AgentState(session_id="test_session")
    
    # ActionResult追加テスト
    agent_state.add_action_result(
        action_id="test_001_file_ops_read_file",
        operation="file_ops.read_file",
        result="ファイル内容データ",
        action_list_id="al_test123",
        sequence_number=0
    )
    
    agent_state.add_action_result(
        action_id="test_002_llm_service_synthesize",
        operation="llm_service.synthesize_insights_from_files",
        result="分析結果データ",
        action_list_id="al_test123",
        sequence_number=1
    )
    
    print("ActionResult 2件追加完了")
    
    # 取得テスト
    result1 = agent_state.get_action_result_by_id("test_001_file_ops_read_file", "al_test123")
    result2 = agent_state.get_latest_result_by_operation("file_ops.read_file")
    
    print(f"ID指定取得: {result1 is not None}")
    print(f"最新結果取得: {result2 is not None}")
    
    # short_term_memory確認
    action_results = agent_state.short_term_memory.get('action_results', [])
    print(f"保存データ数: {len(action_results)}")
    
    for ar in action_results:
        print(f"  {ar['action_id']} ({ar['operation']}) - {ar['timestamp']}")
    
    print("\n基本テスト完了")
    
except Exception as e:
    print(f"テストエラー: {e}")
    import traceback
    traceback.print_exc()