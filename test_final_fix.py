#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
最終修正テスト：波括弧1つサポート + LLMServiceツールエラー修正
"""

import sys
import os
import logging
sys.path.insert(0, os.path.dirname(__file__))

# ログレベル設定
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')

async def test_final_fix():
    """最終修正のテスト：波括弧1つ + LLMServiceエラー修正"""
    print("最終修正テスト開始")
    
    try:
        from companion.state.agent_state import AgentState, Action
        from companion.enhanced_core import EnhancedCompanionCoreV7
        
        class MockDualLoopSystem:
            def __init__(self):
                self.agent_state = AgentState(session_id="test_final_fix")
                
        mock_system = MockDualLoopSystem()
        core = EnhancedCompanionCoreV7(mock_system)
        
        print("実際のLLM生成ActionList形式（波括弧1つ）のテスト...")
        
        # 実際のLLMが生成したのと同じ形式のActionList
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
                    "file_contents": {"game_doc.md": "{@act_000_file_ops_read_file}"}  # 波括弧1つ
                },
                reasoning="LLM分析（修正されたツール設定で）"
            ),
            Action(
                operation="response.echo",
                args={"message": "分析結果: {@act_001_llm_service_synthesize_insights_from_files}"},  # 波括弧1つ
                reasoning="結果表示（波括弧1つ形式）"
            )
        ]
        
        results = await core._dispatch_action_list(action_list)
        
        print("実行結果:")
        for i, result in enumerate(results):
            if isinstance(result, str):
                result_preview = result[:200] + "..." if len(result) > 200 else result
                print(f"  Action {i}: {result_preview}")
            else:
                print(f"  Action {i}: {type(result).__name__} - {str(result)[:100]}...")
        
        # 成功条件チェック
        print("\n成功条件チェック:")
        
        # 1. ファイル読み込み成功
        file_read_success = isinstance(results[0], str) and len(results[0]) > 100
        print(f"  ✅ ファイル読み込み: {file_read_success}")
        
        # 2. LLMService分析成功（ツールエラーがないこと）
        llm_analysis_success = isinstance(results[1], str) and "エラーが発生しました" not in results[1] and len(results[1]) > 50
        print(f"  {'✅' if llm_analysis_success else '❌'} LLMService分析: {llm_analysis_success}")
        
        # 3. 波括弧1つの参照解決成功
        final_result_success = isinstance(results[2], str) and "分析結果:" in results[2] and "{@" not in results[2]
        print(f"  {'✅' if final_result_success else '❌'} 波括弧1つ参照解決: {final_result_success}")
        
        # 4. 全体の一貫性
        contains_analysis = isinstance(results[2], str) and len(results[2]) > 200
        print(f"  {'✅' if contains_analysis else '❌'} 分析結果の完全性: {contains_analysis}")
        
        all_success = file_read_success and llm_analysis_success and final_result_success and contains_analysis
        
        print(f"\n{'🎉 最終修正テスト成功' if all_success else '❌ 最終修正テスト失敗'}")
        
        if all_success:
            print("✅ 波括弧1つのテンプレート変数サポート成功")
            print("✅ LLMServiceのツール呼び出しエラー修正成功")
            print("✅ ファイル読み込み → LLM分析 → 結果表示の完全フロー成功")
        else:
            print("❌ 一部の機能に問題があります")
            
        return all_success
        
    except Exception as e:
        print(f"最終修正テストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import asyncio
    success = asyncio.run(test_final_fix())
    exit(0 if success else 1)