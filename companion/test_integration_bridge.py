"""
Test Integration Bridge

統合ブリッジのテスト用ファイル
"""

import asyncio
import sys
import os

# パスを追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from companion.integration_bridge import intent_bridge, IntegratedIntentResult


async def test_integration_bridge():
    """統合ブリッジのテスト"""
    print("🦆 統合ブリッジテスト開始")
    print("=" * 60)
    
    # テストケース
    test_cases = [
        {
            "input": "このプロジェクトについてあなたの意見を教えてください",
            "description": "情報要求（意見・分析）",
            "expected_type": "analysis_report"
        },
        {
            "input": "新しいPythonスクリプトを作成してください",
            "description": "作成要求",
            "expected_type": "code_generation"
        },
        {
            "input": "READMEファイルの内容を確認してください",
            "description": "ファイル内容確認",
            "expected_type": "information_search"
        },
        {
            "input": "コードの品質を分析してください",
            "description": "分析要求",
            "expected_type": "analysis_report"
        },
        {
            "input": "特定の関数を探してください",
            "description": "検索要求",
            "expected_type": "information_search"
        }
    ]
    
    print(f"🚀 {len(test_cases)}個のテストケースを実行します")
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*50}")
        print(f"📋 テストケース {i}: {test_case['description']}")
        print(f"入力: {test_case['input']}")
        print(f"期待: {test_case['expected_type']}")
        print(f"{'='*50}")
        
        try:
            # 統合ブリッジで意図理解を実行
            result = await intent_bridge.analyze_user_intent(
                test_case["input"],
                workspace_files=["README.md", "main.py", "design-doc.md"]
            )
            
            # 結果の表示
            print(f"✅ 結果:")
            print(f"  - 操作タイプ: {result.operation_type}")
            print(f"  - ファイル読み取り: {result.needs_file_read}")
            print(f"  - 信頼度: {result.overall_confidence:.2%}")
            print(f"  - ルーティング理由: {result.routing_reason}")
            print(f"  - 検出パターン: {result.detected_patterns}")
            
            if result.target_files:
                print(f"  - 対象ファイル: {result.target_files}")
            
            # LLMベースシステムの詳細結果
            if result.llm_intent_analysis:
                print(f"  - LLM意図: {result.llm_intent_analysis.primary_intent.value}")
                print(f"  - 複雑度: {result.llm_intent_analysis.execution_complexity.value}")
            
            if result.task_profile:
                print(f"  - TaskProfile: {result.task_profile.profile_type.value}")
            
            if result.task_decomposition:
                print(f"  - サブタスク数: {len(result.task_decomposition.subtasks)}")
            
            # 期待値との比較
            if result.operation_type == test_case["expected_type"]:
                print(f"🎯 期待値と一致: {result.operation_type}")
            else:
                print(f"⚠️  期待値と異なる: 期待={test_case['expected_type']}, 実際={result.operation_type}")
            
            print(f"✅ テストケース {i} 完了")
            
        except Exception as e:
            print(f"❌ テストケース {i} でエラー: {e}")
            continue
    
    print(f"\n🎉 統合ブリッジテスト完了！")


async def main():
    """メイン関数"""
    await test_integration_bridge()


if __name__ == "__main__":
    asyncio.run(main())
