#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
プラン生成機能のデバッグ
"""

import asyncio
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

async def debug_plan_generation():
    """プラン生成機能をデバッグ"""
    print("=== プラン生成デバッグ ===")
    
    try:
        from companion.enhanced_dual_loop import EnhancedDualLoopSystem
        from companion.intent_understanding.intent_analyzer_llm import ActionType
        
        # システム初期化
        system = EnhancedDualLoopSystem()
        v8_core = system.enhanced_companion
        
        user_message = "ドキュメントをもとに実装プランを提案してください"
        
        # 1. 意図分析結果を確認
        print(f"ユーザー入力: {user_message}")
        intent_result = await v8_core.analyze_intent_only(user_message)
        print(f"意図分析結果: {intent_result}")
        
        # 2. ActionList生成を確認
        action_list = await v8_core._generate_action_list_v8(user_message, intent_result)
        print(f"生成されたActionList: {len(action_list)}個")
        for i, action in enumerate(action_list):
            print(f"  {i+1}. operation: {action.operation}")
            print(f"      args: {action.args}")
            print(f"      reasoning: {action.reasoning}")
        
        # 3. ActionType確認
        detected_action_type = intent_result.get("action_type")
        print(f"検出されたaction_type: {detected_action_type}")
        print(f"期待されるaction_type: plan_generation")
        
        # 4. プラン生成ツールが登録されているか確認
        plan_tools = v8_core.tools.get("plan_generator", {})
        print(f"プラン生成ツール登録状況: {list(plan_tools.keys())}")
        
        return len(action_list) > 0
        
    except Exception as e:
        print(f"ERROR: デバッグエラー: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """メインデバッグ関数"""
    print("START: プラン生成機能デバッグ開始")
    
    success = asyncio.run(debug_plan_generation())
    
    if success:
        print("\\nSUCCESS: プラン生成のActionListが正常に生成されました")
    else:
        print("\\nERROR: プラン生成に問題があります")
    
    return success

if __name__ == "__main__":
    exit(0 if main() else 1)