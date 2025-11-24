#\!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
修正検証テスト：ActionID番号不一致の修正確認
"""

import sys
import os
import logging
sys.path.insert(0, os.path.dirname(__file__))

# ログレベル設定
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')

async def test_action_id_fix():
    """ActionID番号不一致修正の検証テスト"""
    print("ActionID番号不一致修正テスト開始")
    
    try:
        from companion.state.agent_state import AgentState, Action
        from companion.enhanced_core import EnhancedCompanionCoreV7
        
        class MockDualLoopSystem:
            def __init__(self):
                self.agent_state = AgentState(session_id="test_actionid_fix")
                
        mock_system = MockDualLoopSystem()
        core = EnhancedCompanionCoreV7(mock_system)
        
        print("4つのActionでの番号検証テスト...")
        
        # 4つのActionでActionID番号をテスト
        action_list = [
            Action(
                operation="file_ops.read_file",
                args={"file_path": "game_doc.md"},
                reasoning="ファイル読み込み（act_000）"
            ),
            Action(
                operation="llm_service.synthesize_insights_from_files",
                args={
                    "task_description": "ファイル内容を要約",
                    "file_contents": {"game_doc.md": "{@act_000_file_ops_read_file}"}
                },
                reasoning="LLM分析（act_001）"
            ),
            Action(
                operation="response.echo",
                args={"message": "分析結果: {@act_001_llm_service_synthesize_insights_from_files}"},
                reasoning="分析結果表示（act_002）"
            ),
            Action(
                operation="response.echo",
                args={"message": "完了報告。最初のファイル読み込み結果: {@act_000_file_ops_read_file}"},
                reasoning="完了報告（act_003）"
            )
        ]
        
        results = await core._dispatch_action_list(action_list)
        
        print("実行結果:")
        for i, result in enumerate(results):
            if isinstance(result, str):
                result_preview = result[:100] + "..." if len(result) > 100 else result
                print(f"  Action {i} (act_{i:03d}): {result_preview}")
            else:
                print(f"  Action {i} (act_{i:03d}): {type(result).__name__} - {str(result)[:100]}")
        
        # ActionID参照の成功確認
        print("\nActionID参照検証:")
        
        # Action 2のテンプレート変数が正しく置換されているか
        action2_success = isinstance(results[2], str) and "分析結果:" in results[2] and "{@act_001" not in results[2]
        print(f"  Action 2 (act_002) 参照成功: {'✅' if action2_success else '❌'}")
        
        # Action 3のテンプレート変数が正しく置換されているか  
        action3_success = isinstance(results[3], str) and "完了報告" in results[3] and "{@act_000" not in results[3]
        print(f"  Action 3 (act_003) 参照成功: {'✅' if action3_success else '❌'}")
        
        # 全体の成功判定
        all_success = action2_success and action3_success
        
        print(f"\n{'🎉 ActionID番号不一致修正成功' if all_success else '❌ ActionID番号不一致修正失敗'}")
        
        if all_success:
            print("✅ 0ベースのActionID番号が正しく動作")
            print("✅ 複数のActionID参照が正常に解決")
        else:
            print("❌ ActionID参照に問題があります")
            if not action2_success:
                print("  - Action 2のActionID参照が失敗")
            if not action3_success:
                print("  - Action 3のActionID参照が失敗")
                
        return all_success
        
    except Exception as e:
        print(f"ActionID修正テストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import asyncio
    success = asyncio.run(test_action_id_fix())
    exit(0 if success else 1)
