#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ActionID+タイムスタンプシステムのテストスクリプト
"""

import asyncio
import logging
import sys
import os

# プロジェクトのルートをPythonパスに追加
sys.path.insert(0, os.path.dirname(__file__))

from companion.enhanced_dual_loop import EnhancedDualLoopSystem
from companion.state.agent_state import AgentState, Action

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_actionid_system():
    """ActionIDシステムの基本テスト"""
    print("🧪 ActionID+タイムスタンプシステムテスト開始")
    
    try:
        # システム初期化
        print("📋 システム初期化中...")
        dual_loop_system = EnhancedDualLoopSystem()
        await dual_loop_system.start()
        
        # EnhancedCompanionCoreを取得
        core = dual_loop_system.enhanced_companion
        
        # テスト用ActionListの作成
        print("📝 テスト用ActionList作成...")
        action_list = [
            Action(
                operation="file_ops.read_file",
                args={"file_path": "game_doc.md"},
                reasoning="テスト用のファイル読み込み"
            ),
            Action(
                operation="llm_service.synthesize_insights_from_files", 
                args={
                    "task_description": "game_doc.mdの内容を要約してください",
                    "file_contents": "{{@act_000_file_ops_read_file}}"  # ActionID参照
                },
                reasoning="ファイル内容をLLMで分析・要約"
            ),
            Action(
                operation="response.echo",
                args={"message": "分析結果: {{@act_001_llm_service_synthesize_insights_from_files}}"},
                reasoning="分析結果をユーザーに返信"
            )
        ]
        
        # ActionList実行
        print("🚀 ActionList実行中...")
        results = await core._dispatch_action_list(action_list)
        
        # 結果の確認
        print("✅ 実行結果:")
        for i, result in enumerate(results):
            print(f"  📋 Action {i}: {str(result)[:100]}...")
        
        # AgentStateのActionResult確認
        print("📊 AgentStateのActionResult確認:")
        action_results = core.agent_state.short_term_memory.get('action_results', [])
        print(f"  保存されたActionResult数: {len(action_results)}")
        
        for ar in action_results:
            print(f"  📌 {ar['action_id']} ({ar['operation']}) - {ar['timestamp']}")
            print(f"     結果: {str(ar['result'])[:80]}...")
        
        # 参照テスト
        print("🔗 ActionID参照テスト:")
        if len(action_results) >= 2:
            test_action_list_id = action_results[0]['action_list_id']
            
            # 特定のActionID参照
            file_result = core.agent_state.get_action_result_by_id(
                "act_000_file_ops_read_file", test_action_list_id
            )
            print(f"  📁 ファイル読み込み結果参照: {file_result is not None}")
            
            # 最新結果参照
            latest_file = core.agent_state.get_latest_result_by_operation("file_ops.read_file")
            print(f"  📄 最新ファイル結果参照: {latest_file is not None}")
            
            latest_analysis = core.agent_state.get_latest_result_by_operation("llm_service.synthesize_insights_from_files")
            print(f"  🔍 最新分析結果参照: {latest_analysis is not None}")
        
        print("✅ テスト完了")
        
    except Exception as e:
        print(f"❌ テストエラー: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        try:
            await dual_loop_system.stop()
            print("🔚 システム停止完了")
        except:
            pass

if __name__ == "__main__":
    asyncio.run(test_actionid_system())