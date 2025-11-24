"""
Phase 2 プロンプト修正後のルーティング動作確認
"""

import asyncio
import sys
import os

# パスを追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from companion.core import CompanionCore, ActionType
from companion.simple_approval import ApprovalMode


async def test_routing_fix():
    """ルーティング修正の動作確認"""
    
    print("🔧 Phase 2 プロンプト修正後のルーティング確認")
    print("=" * 50)
    
    try:
        # CompanionCore 初期化
        companion = CompanionCore(approval_mode=ApprovalMode.TRUSTED)
        
        # テストケース
        test_cases = [
            {
                "input": "game_doc.mdを読んで内容を把握してください",
                "expected_action": ActionType.FILE_OPERATION,
                "description": "ファイル読み込み要求"
            },
            {
                "input": "設定について教えて",
                "expected_action": ActionType.DIRECT_RESPONSE,
                "description": "一般的な情報要求"
            }
        ]
        
        for i, case in enumerate(test_cases, 1):
            print(f"\n📝 テストケース {i}: {case['description']}")
            print(f"入力: {case['input']}")
            
            # 意図分析のみ実行
            intent_result = await companion.analyze_intent_only(case['input'])
            action_type = intent_result['action_type']
            
            print(f"分析結果: {action_type.value}")
            
            # 期待値との比較
            if action_type == case['expected_action']:
                print("✅ ルーティング成功")
            else:
                print(f"❌ ルーティング失敗: 期待値 {case['expected_action'].value}, 実際 {action_type.value}")
                
            # 詳細情報表示
            if 'understanding_result' in intent_result and intent_result['understanding_result']:
                ur = intent_result['understanding_result']
                if hasattr(ur, 'task_profile'):
                    print(f"TaskProfile: {ur.task_profile.profile_type.value}")
                if hasattr(ur, 'intent_analysis'):
                    print(f"Intent: {ur.intent_analysis.primary_intent.value}")
    
    except Exception as e:
        print(f"❌ エラー発生: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 50)


if __name__ == "__main__":
    asyncio.run(test_routing_fix())