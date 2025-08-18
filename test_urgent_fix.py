#!/usr/bin/env python3
"""
緊急修正のテストスクリプト
"""

import os
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

# FILE_OPS_V2を有効化
os.environ["FILE_OPS_V2"] = "1"


def test_import_fixes():
    """importエラーの修正をテスト"""
    print("🧪 importエラーの修正をテスト")
    
    try:
        from companion.intent_understanding.intent_integration import OptionResolver, IntentUnderstandingSystem
        print("  ✅ IntentUnderstandingSystem import成功")
        
        from companion.intent_understanding.llm_intent_analyzer import IntentType, ComplexityLevel, IntentAnalysis
        print("  ✅ LLM Intent Analyzer import成功")
        
        from companion.intent_understanding.task_profile_classifier import TaskProfileType, TaskProfileResult
        print("  ✅ Task Profile Classifier import成功")
        
        return True
        
    except Exception as e:
        print(f"  ❌ import失敗: {e}")
        return False


def test_option_resolver_with_fixes():
    """修正されたOptionResolverのテスト"""
    print("\n🧪 修正されたOptionResolverのテスト")
    
    try:
        from companion.intent_understanding.intent_integration import OptionResolver
        
        # 問題のあった入力をテスト
        test_cases = [
            ("OKです、実装を開始してください", 1),
            ("OKです、フェーズ０を実装してください", 1),
            ("１で", 1),
            ("実装してください", 1),
        ]
        
        success_count = 0
        for input_text, expected in test_cases:
            result = OptionResolver.parse_selection(input_text)
            status = "✅" if result == expected else "❌"
            if result == expected:
                success_count += 1
            print(f"  {status} '{input_text}' -> {result} (期待値: {expected})")
        
        print(f"  📊 結果: {success_count}/{len(test_cases)} 成功")
        return success_count == len(test_cases)
        
    except Exception as e:
        print(f"  ❌ OptionResolverテスト失敗: {e}")
        return False


def test_execution_result_creation():
    """実行結果作成のテスト"""
    print("\n🧪 実行結果作成のテスト")
    
    try:
        from companion.intent_understanding.intent_integration import IntentUnderstandingSystem
        from codecrafter.base.llm_client import llm_manager
        
        # システムを初期化
        system = IntentUnderstandingSystem(llm_manager)
        
        # 実行結果を作成
        result = system._create_execution_result(
            "OKです、実装してください", 
            1, 
            {"plan_state": {"pending": True}}
        )
        
        print(f"  ✅ 実行結果作成成功")
        print(f"    - route_type: {result.route_type}")
        print(f"    - force_execution: {result.metadata.get('force_execution')}")
        print(f"    - selection: {result.metadata.get('selection')}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ 実行結果作成失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """メイン関数"""
    print("🚀 緊急修正のテスト開始\n")
    
    try:
        # テスト実行
        test1 = test_import_fixes()
        test2 = test_option_resolver_with_fixes()
        test3 = test_execution_result_creation()
        
        if all([test1, test2, test3]):
            print("\n✅ すべての緊急修正が成功しました！")
            print("\n🎯 修正内容:")
            print("  1. ExecutionComplexity → ComplexityLevel に修正")
            print("  2. AgentState.add_context → collected_context に修正")
            print("  3. 強制実行フラグ (force_execution) を追加")
            print("  4. 選択入力検出時の確実な実行ルート転送")
            
            print("\n🔧 期待される改善:")
            print("  - importエラーが解消される")
            print("  - AgentStateエラーが解消される")
            print("  - 選択入力が確実に実行ルートに転送される")
            print("  - 質問ループに戻らず実際のファイル操作が実行される")
        else:
            print("\n❌ 一部の修正が失敗しました")
            
    except Exception as e:
        print(f"❌ テスト中にエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()