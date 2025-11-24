#!/usr/bin/env python3
"""
ファイル名抽出機能のテストスクリプト
"""

import asyncio
import sys
import os

# パスを追加
sys.path.append(os.path.join(os.path.dirname(__file__), 'companion'))

async def test_filename_extraction():
    """ファイル名抽出機能のテスト"""
    
    try:
        from enhanced_core import EnhancedCompanionCore
        
        # EnhancedCompanionCoreのインスタンスを作成
        core = EnhancedCompanionCore()
        
        # テストメッセージ
        test_messages = [
            "test.pyを作成して",
            '"config.json" に設定を書き込んで',
            "`README.md` を読んで",
            "日本語ファイル.txtを作成して",
            "data/sample.csv を編集して",
            "ファイル名が特定できませんでした",
            "example.py の内容を確認して",
            "test_folder/script.sh を実行して",
            "設定ファイル.yaml を作成して",
            "ドキュメント.md を更新して"
        ]
        
        print("🔍 ファイル名抽出テスト開始")
        print("=" * 50)
        
        # テスト実行
        results = core.test_filename_extraction(test_messages)
        
        # 結果表示
        for message, extracted in results.items():
            status = "✅" if extracted != "抽出失敗" else "❌"
            print(f"{status} {message}")
            print(f"   抽出結果: {extracted}")
            print()
        
        print("=" * 50)
        print("🎯 テスト完了")
        
        # 成功率計算
        success_count = sum(1 for result in results.values() if result != "抽出失敗")
        total_count = len(results)
        success_rate = (success_count / total_count) * 100
        
        print(f"成功率: {success_count}/{total_count} ({success_rate:.1f}%)")
        
    except ImportError as e:
        print(f"❌ インポートエラー: {e}")
        print("companionフォルダのパスが正しく設定されているか確認してください")
    except Exception as e:
        print(f"❌ テスト実行エラー: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_filename_extraction())
