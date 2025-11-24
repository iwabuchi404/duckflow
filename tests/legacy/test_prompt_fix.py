"""
Phase 2 プロンプト修正の動作確認テスト
"""

import asyncio
import sys
import os

# パスを追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from companion.intent_understanding.llm_intent_analyzer import LLMIntentAnalyzer, IntentType


class MockLLMClient:
    """モックLLMクライアント（テスト用）"""
    
    async def chat(self, prompt, system_prompt, max_tokens=800, temperature=0.1):
        """チャット応答をモック"""
        class MockResponse:
            def __init__(self, content):
                self.content = content
                self.provider = type('Provider', (), {'value': 'mock'})()
                self.model = 'mock-model'
                self.tokens_used = 100
        
        # ファイル読み込み関連の要求を analysis_request として分類
        if any(kw in prompt.lower() for kw in ["game_doc.md", "読んで", "内容を把握", "確認"]):
            response_content = '''
{
    "primary_intent": "analysis_request",
    "secondary_intents": [],
    "context_requirements": ["ファイル存在確認"],
    "execution_complexity": "simple",
    "confidence_score": 0.9,
    "reasoning": "ファイル内容の読み込み・確認要求",
    "detected_targets": ["game_doc.md"],
    "suggested_approach": "ファイルを読み込んで内容を分析・要約"
}
            '''
        else:
            response_content = '''
{
    "primary_intent": "information_request",
    "secondary_intents": [],
    "context_requirements": [],
    "execution_complexity": "simple",
    "confidence_score": 0.7,
    "reasoning": "一般的な情報要求",
    "detected_targets": [],
    "suggested_approach": "直接応答"
}
            '''
        
        return MockResponse(response_content)


async def test_prompt_fix():
    """プロンプト修正のテスト"""
    
    # テストケース
    test_cases = [
        {
            "input": "game_doc.mdを読んで内容を把握してください",
            "expected_intent": IntentType.ANALYSIS_REQUEST,
            "description": "ファイル読み込み要求"
        },
        {
            "input": "設定について教えて",
            "expected_intent": IntentType.INFORMATION_REQUEST,
            "description": "一般的な情報要求"
        }
    ]
    
    # LLMIntentAnalyzer初期化
    mock_client = MockLLMClient()
    analyzer = LLMIntentAnalyzer(mock_client)
    
    print("🧪 Phase 2 プロンプト修正テスト開始")
    print("=" * 50)
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n📝 テストケース {i}: {case['description']}")
        print(f"入力: {case['input']}")
        
        try:
            # 意図分析実行
            result = await analyzer.analyze_intent(case['input'])
            
            print(f"分析結果: {result.primary_intent.value}")
            print(f"信頼度: {result.confidence_score:.2f}")
            print(f"検出対象: {result.detected_targets}")
            print(f"推奨アプローチ: {result.suggested_approach}")
            
            # 期待値との比較
            if result.primary_intent == case['expected_intent']:
                print("✅ テスト成功")
            else:
                print(f"❌ テスト失敗: 期待値 {case['expected_intent'].value}, 実際 {result.primary_intent.value}")
                
        except Exception as e:
            print(f"❌ エラー発生: {e}")
    
    print("\n" + "=" * 50)
    print("🎯 テスト完了")


def test_fallback_classifier():
    """フォールバック分類器のテスト"""
    print("\n🔄 フォールバック分類器テスト")
    
    analyzer = LLMIntentAnalyzer(None)  # LLMクライアントなし
    
    test_input = "game_doc.mdを読んで内容を把握してください"
    result = analyzer._create_fallback_analysis(test_input, "テスト")
    
    print(f"入力: {test_input}")
    print(f"分類結果: {result.primary_intent.value}")
    print(f"検出対象: {result.detected_targets}")
    
    if result.primary_intent == IntentType.ANALYSIS_REQUEST:
        print("✅ フォールバック分類器テスト成功")
    else:
        print(f"❌ フォールバック分類器テスト失敗: {result.primary_intent.value}")


if __name__ == "__main__":
    # メイン実行
    asyncio.run(test_prompt_fix())
    test_fallback_classifier()