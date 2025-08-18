"""
Phase 2 プロンプト修正後の Enhanced Dual Loop 動作確認
"""

import asyncio
import sys
import os

# パスを追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from companion.enhanced_dual_loop import EnhancedDualLoop


async def test_file_reading_fix():
    """ファイル読み込み修正の動作確認"""
    
    print("🔧 Phase 2 プロンプト修正後の動作確認テスト")
    print("=" * 60)
    
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

## 技術仕様
- エンジン: Unity
- プラットフォーム: PC, モバイル
""")
        print(f"📄 テスト用ファイル '{test_file}' を作成しました")
    
    try:
        # Enhanced Dual Loop 初期化
        dual_loop = EnhancedDualLoop()
        
        # ファイル読み込み要求をテスト
        user_message = "game_doc.mdを読んで内容を把握してください"
        
        print(f"\n📝 テスト入力: {user_message}")
        print("🚀 処理開始...")
        
        # 実行
        result = await dual_loop.process_user_message(user_message)
        
        print(f"\n📋 処理結果:")
        print("-" * 40)
        print(result)
        
        # 結果検証
        if "game_doc.md" in result and ("内容" in result or "概要" in result):
            print("\n✅ テスト成功: ファイル読み込みが正常に動作しました")
        else:
            print("\n❌ テスト失敗: ファイル読み込みが動作していません")
            
    except Exception as e:
        print(f"\n❌ エラー発生: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(test_file_reading_fix())