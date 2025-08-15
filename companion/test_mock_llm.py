"""
Mock LLM Client for Testing

テスト用のモックLLMクライアント
"""

import asyncio
from typing import Dict, Any, Optional
from dataclasses import dataclass

from companion.llm.llm_client import LLMClient, LLMResponse, LLMProvider


class MockLLMClient(LLMClient):
    """テスト用のモックLLMクライアント"""
    
    def __init__(self, provider: LLMProvider = LLMProvider.OPENAI):
        """モッククライアントを初期化"""
        self.provider = provider
        self.mock_responses = self._load_mock_responses()
    
    def _load_mock_responses(self) -> Dict[str, str]:
        """モック応答を読み込み"""
        return {
            "intent_analysis": """{
                "primary_intent": "creation_request",
                "secondary_intents": ["analysis_request"],
                "context_requirements": ["プロジェクト構造", "技術要件"],
                "execution_complexity": "complex",
                "confidence_score": 0.85,
                "reasoning": "新規スクリプト作成の要求",
                "detected_targets": ["Python", "ファイル分析"],
                "suggested_approach": "段階的な実装"
            }""",
            
            "task_profile": """{
                "profile_type": "creation_request",
                "confidence": 0.85,
                "reasoning": "新規作成要求の明確な指示",
                "detected_intent": "creation_request",
                "complexity_assessment": "complex",
                "suggested_approach": "段階的実装",
                "context_requirements": ["技術要件", "設計仕様"],
                "detected_targets": ["Python", "ファイル分析"]
            }""",
            
            "content_plan": """{
                "title": "ファイル分析Pythonスクリプト",
                "outline": ["概要", "実装", "テスト"],
                "key_points": ["効率的な処理", "エラーハンドリング"],
                "estimated_length": "中程度",
                "target_audience": "開発者",
                "tone": "技術的"
            }"""
        }
    
    async def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> LLMResponse:
        """モックチャット応答"""
        await asyncio.sleep(0.1)  # 非同期処理をシミュレート
        
        # プロンプトの内容に基づいて応答を選択
        if "意図分析" in prompt or "intent" in prompt.lower():
            content = self.mock_responses["intent_analysis"]
        elif "TaskProfile" in prompt or "profile" in prompt.lower():
            content = self.mock_responses["task_profile"]
        elif "コンテンツ" in prompt or "content" in prompt.lower():
            content = self.mock_responses["content_plan"]
        else:
            content = '{"result": "モック応答"}'
        
        return LLMResponse(
            content=content,
            provider=self.provider,
            model="mock-model",
            tokens_used=len(content) // 4
        )
    
    def is_available(self) -> bool:
        """常に利用可能"""
        return True


# テスト用のモッククライアントインスタンス
mock_llm_client = MockLLMClient()
