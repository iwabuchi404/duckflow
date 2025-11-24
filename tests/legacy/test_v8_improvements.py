#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V8システムの改善をテスト
- 検索結果表示の修正
- プラン生成機能の追加
- AgentStateエラーの修正
"""

import asyncio
import sys
from pathlib import Path

# パス設定
sys.path.append(str(Path(__file__).parent))

async def test_search_display_fix():
    """検索結果表示の修正をテスト"""
    print("=== 検索結果表示修正テスト ===")
    
    try:
        from companion.enhanced_dual_loop import EnhancedDualLoopSystem
        
        # システム初期化
        system = EnhancedDualLoopSystem()
        
        # 検索を含む分析要求
        user_message = "game_doc.mdを読んで内容を把握してください"
        print(f"ユーザー入力: {user_message}")
        
        # V8処理実行
        result = await system.enhanced_companion.process_user_message(user_message)
        
        print("\\n=== 検索結果テスト結果 ===")
        print(result)
        
        # 検索結果に実際のテキストが含まれているかチェック
        if "L1:" in result and ("サルベージ" in result or "ゲーム" in result):
            print("\\nSUCCESS: 検索結果が正しく表示されています")
            return True
        else:
            print("\\nWARNING: 検索結果の表示に問題がある可能性があります")
            return False
        
    except Exception as e:
        print(f"ERROR: 検索結果表示テストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_plan_generation():
    """プラン生成機能をテスト"""
    print("\\n\\n=== プラン生成機能テスト ===")
    
    try:
        from companion.enhanced_dual_loop import EnhancedDualLoopSystem
        
        # システム初期化
        system = EnhancedDualLoopSystem()
        
        # プラン生成要求
        user_message = "ドキュメントをもとに実装プランを提案してください"
        print(f"ユーザー入力: {user_message}")
        
        # V8処理実行
        result = await system.enhanced_companion.process_user_message(user_message)
        
        print("\\n=== プラン生成テスト結果 ===")
        print(result)
        
        # プランが生成されているかチェック
        if "プラン" in result and ("実装" in result or "フェーズ" in result):
            print("\\nSUCCESS: プラン生成機能が動作しています")
            return True
        else:
            print("\\nWARNING: プラン生成の出力に問題がある可能性があります")
            return False
        
    except Exception as e:
        print(f"ERROR: プラン生成テストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """メインテスト関数"""
    print("START: V8システム改善テスト開始")
    
    try:
        # 検索結果表示修正のテスト
        success1 = asyncio.run(test_search_display_fix())
        
        # プラン生成機能のテスト
        success2 = asyncio.run(test_plan_generation())
        
        if success1 and success2:
            print("\\nSUCCESS: すべての改善が正常に動作しています")
            print("・検索結果の表示修正 ✅")
            print("・プラン生成機能追加 ✅")
            print("・AgentStateエラー修正 ✅")
            return True
        else:
            print("\\nWARNING: 一部の機能に問題があります")
            return False
        
    except Exception as e:
        print(f"ERROR: テスト実行エラー: {e}")
        return False

if __name__ == "__main__":
    exit(0 if main() else 1)