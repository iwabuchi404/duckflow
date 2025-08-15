"""
Improved Mock LLM Client

より現実的な意図理解を提供するモックLLMクライアント
"""

import asyncio
from typing import Dict, Any, Optional
from dataclasses import dataclass

from .llm.llm_client import LLMClient, LLMResponse, LLMProvider


class ImprovedMockLLMClient(LLMClient):
    """改善されたモックLLMクライアント"""
    
    def __init__(self, provider: LLMProvider = LLMProvider.OPENAI):
        """モッククライアントを初期化"""
        self.provider = provider
        self.mock_responses = self._load_improved_mock_responses()
    
    def _load_improved_mock_responses(self) -> Dict[str, str]:
        """改善されたモック応答を読み込み"""
        return {
            # 情報要求・意見要求
            "opinion": """{
                "primary_intent": "information_request",
                "secondary_intents": ["analysis_request"],
                "context_requirements": ["プロジェクト概要", "技術的特徴"],
                "execution_complexity": "moderate",
                "confidence_score": 0.88,
                "reasoning": "プロジェクトについての意見・分析を求めている",
                "detected_targets": ["プロジェクト全体"],
                "suggested_approach": "プロジェクト分析と評価"
            }""",
            
            # 作成要求
            "creation": """{
                "primary_intent": "creation_request",
                "secondary_intents": ["analysis_request"],
                "context_requirements": ["技術要件", "設計仕様"],
                "execution_complexity": "complex",
                "confidence_score": 0.92,
                "reasoning": "新規スクリプト作成の明確な指示",
                "detected_targets": ["Python", "スクリプト"],
                "suggested_approach": "段階的実装"
            }""",
            
            # ファイル内容確認
            "file_content": """{
                "primary_intent": "information_request",
                "secondary_intents": ["search_request"],
                "context_requirements": ["ファイル内容", "ファイル構造"],
                "execution_complexity": "simple",
                "confidence_score": 0.85,
                "reasoning": "特定ファイルの内容確認要求",
                "detected_targets": ["README", "ファイル"],
                "suggested_approach": "ファイル読み取りと内容表示"
            }""",
            
            # 分析要求
            "analysis": """{
                "primary_intent": "analysis_request",
                "secondary_intents": ["information_request"],
                "context_requirements": ["分析対象", "分析基準"],
                "execution_complexity": "moderate",
                "confidence_score": 0.87,
                "reasoning": "コード品質分析の明確な要求",
                "detected_targets": ["コード", "品質"],
                "suggested_approach": "多角的分析と評価"
            }""",
            
            # 検索要求
            "search": """{
                "primary_intent": "search_request",
                "secondary_intents": ["information_request"],
                "context_requirements": ["検索対象", "検索条件"],
                "execution_complexity": "simple",
                "confidence_score": 0.83,
                "reasoning": "特定要素の検索要求",
                "detected_targets": ["関数", "コード"],
                "suggested_approach": "効率的な検索と結果表示"
            }""",
            
            # ガイダンス要求
            "guidance": """{
                "primary_intent": "guidance_request",
                "secondary_intents": ["information_request"],
                "context_requirements": ["相談内容", "関連情報"],
                "execution_complexity": "simple",
                "confidence_score": 0.80,
                "reasoning": "手順や方法についての相談",
                "detected_targets": ["手順", "方法"],
                "suggested_approach": "段階的説明とアドバイス"
            }"""
        }
    
    async def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> LLMResponse:
        """改善されたモックチャット応答"""
        await asyncio.sleep(0.1)  # 非同期処理をシミュレート
        
        # プロンプトの内容に基づいて適切な応答を選択
        content = self._select_appropriate_response(prompt)
        
        return LLMResponse(
            content=content,
            provider=self.provider,
            model="improved-mock-model",
            tokens_used=len(content) // 4
        )
    
    def _select_appropriate_response(self, prompt: str) -> str:
        """プロンプトに基づいて適切な応答を選択"""
        prompt_lower = prompt.lower()
        
        # 意見・分析要求の検出
        if any(kw in prompt_lower for kw in ["意見", "考え", "どう思う", "評価", "分析"]):
            return self.mock_responses["opinion"]
        
        # 作成要求の検出
        if any(kw in prompt_lower for kw in ["作成", "作って", "実装", "書いて", "構築", "新規"]):
            return self.mock_responses["creation"]
        
        # ファイル内容確認の検出
        if any(kw in prompt_lower for kw in ["内容", "確認", "見て", "開いて", "読んで", "ファイル"]):
            return self.mock_responses["file_content"]
        
        # 分析要求の検出
        if any(kw in prompt_lower for kw in ["分析", "評価", "診断", "チェック", "品質", "問題"]):
            return self.mock_responses["analysis"]
        
        # 検索要求の検出
        if any(kw in prompt_lower for kw in ["検索", "探して", "見つけて", "調べて", "特定", "関数"]):
            return self.mock_responses["search"]
        
        # ガイダンス要求の検出
        if any(kw in prompt_lower for kw in ["説明", "教えて", "案内", "手順", "方法", "相談"]):
            return self.mock_responses["guidance"]
        
        # デフォルト（情報要求）
        return self.mock_responses["opinion"]
    
    def is_available(self) -> bool:
        """常に利用可能"""
        return True


# 改善されたモッククライアントインスタンス
improved_mock_llm_client = ImprovedMockLLMClient()
