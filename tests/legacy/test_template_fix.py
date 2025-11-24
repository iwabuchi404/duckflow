#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
テンプレート変数修正テスト
"""

import sys
import os
import logging
sys.path.insert(0, os.path.dirname(__file__))

# ログレベル設定
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')

async def test_template_fix():
    """修正されたテンプレート変数システムのテスト"""
    print("テンプレート変数修正テスト開始")
    
    try:
        from companion.state.agent_state import AgentState, Action
        from companion.enhanced_core import EnhancedCompanionCoreV7
        
        class MockDualLoopSystem:
            def __init__(self):
                self.agent_state = AgentState(session_id="test_template_fix")
                
        mock_system = MockDualLoopSystem()
        core = EnhancedCompanionCoreV7(mock_system)
        
        print("新しいActionID参照形式のテスト...")
        action_list = [
            Action(
                operation="file_ops.read_file",
                args={"file_path": "game_doc.md"},
                reasoning="ファイル読み込み"
            ),
            Action(
                operation="llm_service.synthesize_insights_from_files",
                args={
                    "task_description": "ファイル内容を要約してください",
                    "file_contents": {}
                },
                reasoning="LLM分析"
            ),
            Action(
                operation="response.echo",
                args={"message": "分析結果: {{@act_001_llm_service_synthesize_insights_from_files}}"},
                reasoning="新形式での結果表示"
            )
        ]
        
        results = await core._dispatch_action_list(action_list)
        
        print("実行結果:")
        for i, result in enumerate(results):
            result_preview = str(result)[:200] + "..." if len(str(result)) > 200 else str(result)
            print(f"  Action {i}: {result_preview}")
        
        # 最後の結果に分析内容が含まれているかチェック
        final_result = results[-1] if results else ""
        success = isinstance(final_result, str) and len(final_result) > 50 and "分析結果:" in final_result and "{{@" not in final_result
        
        print(f"\n{'✅ テンプレート変数修正成功' if success else '❌ テンプレート変数修正失敗'}")
        
        if success:
            print("新しいActionID参照形式が正常に動作しています")
        else:
            print("ActionID参照が正しく置換されていません")
            
        return success
        
    except Exception as e:
        print(f"テストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import asyncio
    success = asyncio.run(test_template_fix())
    exit(0 if success else 1)