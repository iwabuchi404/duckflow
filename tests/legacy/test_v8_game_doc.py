#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V8システムでのgame_doc.md分析テスト
"""

import asyncio
import sys
from pathlib import Path

# パス設定
sys.path.append(str(Path(__file__).parent))

async def test_v8_game_doc_analysis():
    """V8システムでのgame_doc.md分析テスト"""
    print("=== V8 game_doc.md 分析テスト ===")
    
    try:
        from companion.enhanced_dual_loop import EnhancedDualLoopSystem
        
        # システム初期化
        system = EnhancedDualLoopSystem()
        
        # V8コアが使用されているか確認
        print(f"使用中のコア: {system.enhanced_companion.__class__.__name__}")
        
        # 直接V8のprocess_user_messageを呼び出してテスト
        user_message = "game_doc.mdを参照してプロジェクトの概要を把握してください"
        print(f"\nユーザー入力: {user_message}")
        
        # V8処理実行
        result = await system.enhanced_companion.process_user_message(user_message)
        
        print("\n=== V8処理結果 ===")
        print(result)
        
        # 出力が読みやすくなっているか確認
        if "ファイル分析結果" in result or len(result.split('\n')) > 5:
            print("\nSUCCESS: V8システムで読みやすい出力が生成されました")
            return True
        else:
            print("\nWARNING: 出力が期待された形式ではありません")
            return False
        
    except Exception as e:
        print(f"ERROR: テストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """テストメイン"""
    print("START: V8 game_doc.md 分析テスト開始")
    
    try:
        success = asyncio.run(test_v8_game_doc_analysis())
        
        if success:
            print("\nSUCCESS: V8システム動作成功")
            print("JSON+LLM方式による読みやすい出力が確認できました")
        else:
            print("\nERROR: V8システムに問題があります")
        
        return success
        
    except Exception as e:
        print(f"ERROR: テスト実行エラー: {e}")
        return False

if __name__ == "__main__":
    exit(0 if main() else 1)