"""
Phase 2 プロンプト修正後の Enhanced CompanionCore 動作確認
"""

import asyncio
import sys
import os

# パスを追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from companion.enhanced_core import EnhancedCompanionCore
from companion.simple_approval import ApprovalMode


async def test_enhanced_core_fix():
    """Enhanced CompanionCore での修正確認"""
    
    print("🔧 Enhanced CompanionCore Phase 2 修正確認")
    print("=" * 50)
    
    # テスト用ファイルが存在するか確認
    test_file = "game_doc.md"
    if not os.path.exists(test_file):
        # テスト用ファイルを作成
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("""# ゲームデザインドキュメント

## 概要
これはテスト用のゲームデザインドキュメントです。

## 主要機能
- プレイヤー移動システム
- アイテム収集機能
- スコアシステム
""")
        print(f"📄 テスト用ファイル '{test_file}' を作成しました")
    
    try:
        # Enhanced CompanionCore 初期化
        enhanced_core = EnhancedCompanionCore(approval_mode=ApprovalMode.TRUSTED)
        
        user_message = "game_doc.mdを読んで内容を把握してください"
        print(f"\n📝 テスト入力: {user_message}")
        
        # 意図分析
        intent_result = await enhanced_core.analyze_intent_only(user_message)
        action_type = intent_result['action_type']
        
        print(f"🎯 意図分析結果: {action_type.value}")
        
        # 処理実行
        if action_type.value == "file_operation":
            print("📁 ファイル操作として認識されました")
            
            # 処理実行
            result = await enhanced_core.process_with_intent_result(intent_result)
            
            print(f"\n📋 処理結果:")
            print("-" * 30)
            print(result[:500] + "..." if len(result) > 500 else result)
            
            # 結果検証
            if "game_doc.md" in result and ("内容" in result or "概要" in result):
                print("\n✅ Enhanced CompanionCore修正成功")
            else:
                print("\n❌ ファイル読み込みが期待通りに動作していません")
        else:
            print(f"❌ 期待したアクションタイプ（file_operation）ではありません: {action_type.value}")
            
    except Exception as e:
        print(f"❌ エラー発生: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 50)


if __name__ == "__main__":
    asyncio.run(test_enhanced_core_fix())