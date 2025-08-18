#!/usr/bin/env python3
"""
Dual-Loop System デバッグ用スクリプト
"""

import sys
import time
import asyncio
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from companion.core import CompanionCore
    from codecrafter.ui.rich_ui import rich_ui
except ImportError as e:
    print(f"❌ インポートエラー: {e}")
    sys.exit(1)


async def test_companion_core_directly():
    """CompanionCoreを直接テスト"""
    print("🧪 CompanionCore 直接テスト")
    
    companion = CompanionCore()
    
    test_message = "内容をレビューしてみてください"
    print(f"📤 テストメッセージ: {test_message}")
    
    try:
        result = await companion.process_message(test_message)
        print(f"📥 結果: {result}")
        print(f"📊 結果の長さ: {len(result) if result else 0}文字")
        
        if not result:
            print("⚠️ 結果が空です")
        elif result.strip() == "":
            print("⚠️ 結果が空白のみです")
        else:
            print("✅ 正常な結果を取得")
            
    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()


def main():
    """メイン関数"""
    print("🦆 Dual-Loop System デバッグ")
    print("=" * 50)
    
    # CompanionCoreの直接テスト
    asyncio.run(test_companion_core_directly())
    
    print("\n🎉 デバッグ完了！")


if __name__ == "__main__":
    main()