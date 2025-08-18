#!/usr/bin/env python3
"""
実行阻害修正のテストスクリプト
"""

import os
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

# FILE_OPS_V2を有効化
os.environ["FILE_OPS_V2"] = "1"

from companion.intent_understanding.intent_integration import OptionResolver


def test_improved_option_resolver():
    """改善されたOptionResolverのテスト"""
    print("🧪 改善されたOptionResolverのテスト")
    
    test_cases = [
        # 既存のテストケース
        ("1", 1),
        ("１", 1),
        ("デフォルト", 1),
        ("はい", 1),
        
        # 新しく追加されたケース
        ("OKです、実装を開始してください", 1),
        ("実装開始してください", 1),
        ("開始してください", 1),
        ("実装してください", 1),
        ("やってください", 1),
        ("お願いします", 1),
        
        # 部分マッチのテスト
        ("OK、実装を開始しましょう", 1),
        ("実装を開始したいです", 1),
        ("進めてください", 1),
        
        # 無効なケース
        ("これは無効な入力です", None),
        ("", None),
    ]
    
    success_count = 0
    for input_text, expected in test_cases:
        result = OptionResolver.parse_selection(input_text)
        status = "✅" if result == expected else "❌"
        if result == expected:
            success_count += 1
        print(f"  {status} '{input_text}' -> {result} (期待値: {expected})")
    
    print(f"\n📊 結果: {success_count}/{len(test_cases)} 成功")
    return success_count == len(test_cases)


def main():
    """メイン関数"""
    print("🚀 実行阻害修正のテスト開始\n")
    
    try:
        success = test_improved_option_resolver()
        
        if success:
            print("\n✅ すべてのテストが成功しました！")
            print("\n🎯 修正内容:")
            print("  1. 選択入力の検出範囲を拡大")
            print("     - 'OKです、実装を開始してください' を認識")
            print("     - '実装開始', '開始してください' などを追加")
            print("     - 正規表現による柔軟なパターンマッチング")
            print("  2. プラン状態の管理を改善")
            print("     - プラン提示時に自動的にプラン状態を設定")
            print("     - 選択入力検出時にプラン状態をチェック")
            print("  3. コンテキスト連携の強化")
            print("     - 意図理解システムにプラン状態を渡す")
            print("     - EnhancedCompanionCoreでプラン状態を管理")
            
            print("\n🔧 期待される改善:")
            print("  - 'OKです、実装を開始してください' が実行ルートに転送される")
            print("  - プラン提示後の選択入力が確実に検出される")
            print("  - 質問ループに戻らず、実際のファイル操作が実行される")
        else:
            print("\n❌ 一部のテストが失敗しました")
            
    except Exception as e:
        print(f"❌ テスト中にエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()