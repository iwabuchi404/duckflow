"""
Existing LLM Adapter

既存のcodecrafterのLLMマネージャーを新システムで使用するためのアダプター
"""

import asyncio
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

# 既存のLLMマネージャーをインポート
from ..base.llm_client import llm_manager


class LLMProvider(Enum):
    """LLMプロバイダー（既存システム互換）"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GROQ = "groq"
    OPENROUTER = "openrouter"
    MOCK = "mock"


@dataclass
class LLMResponse:
    """LLM応答の構造化データ"""
    content: str
    provider: LLMProvider
    model: str
    tokens_used: Optional[int] = None
    confidence: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class ExistingLLMAdapter:
    """既存のLLMマネージャーを新システムで使用するためのアダプター"""
    
    def __init__(self):
        """アダプターを初期化"""
        self.llm_manager = llm_manager
        self.provider = self._detect_provider()
    
    def _detect_provider(self) -> LLMProvider:
        """現在のプロバイダーを検出"""
        provider_name = self.llm_manager.get_provider_name().lower()
        
        if provider_name == "openai":
            return LLMProvider.OPENAI
        elif provider_name == "anthropic":
            return LLMProvider.ANTHROPIC
        elif provider_name == "groq":
            return LLMProvider.GROQ
        elif provider_name == "openrouter":
            return LLMProvider.OPENROUTER
        elif provider_name == "mock":
            return LLMProvider.MOCK
        else:
            return LLMProvider.MOCK
    
    async def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> LLMResponse:
        """
        既存のLLMマネージャーを使用したチャット
        
        Args:
            prompt: ユーザープロンプト
            system_prompt: システムプロンプト
            max_tokens: 最大トークン数（既存システムでは設定済み）
            temperature: 創造性（既存システムでは設定済み）
            
        Returns:
            LLM応答
        """
        try:
            # 既存のLLMマネージャーを使用（非同期ラッパー）
            response_content = await asyncio.get_event_loop().run_in_executor(
                None,
                self.llm_manager.chat,
                prompt,
                system_prompt
            )
            
            return LLMResponse(
                content=response_content,
                provider=self.provider,
                model=self._get_current_model(),
                tokens_used=self._estimate_tokens(prompt + (system_prompt or "") + response_content),
                metadata={
                    "adapter": "existing_llm_manager",
                    "provider_name": self.llm_manager.get_provider_name()
                }
            )
            
        except Exception as e:
            return self._create_error_response(str(e))
    
    def _get_current_model(self) -> str:
        """現在のモデル名を取得"""
        provider_name = self.llm_manager.get_provider_name().lower()
        
        # 既存システムのデフォルトモデル
        model_defaults = {
            "openai": "gpt-4-turbo-preview",
            "anthropic": "claude-3-5-sonnet-20241022",
            "groq": "mixtral-8x7b-32768",
            "openrouter": "anthropic/claude-3-sonnet",
            "mock": "mock-model"
        }
        
        return model_defaults.get(provider_name, "unknown-model")
    
    def _estimate_tokens(self, text: str) -> int:
        """トークン数の概算"""
        # 簡易的な推定（1トークン ≈ 4文字）
        return len(text) // 4
    
    def _create_error_response(self, error_message: str) -> LLMResponse:
        """エラー時のレスポンス作成"""
        return LLMResponse(
            content=f"エラーが発生しました: {error_message}",
            provider=self.provider,
            model="error",
            confidence=0.0,
            metadata={"error": error_message}
        )
    
    def is_available(self) -> bool:
        """LLMが利用可能かチェック"""
        # モッククライアントでも利用可能とみなす（開発・テスト環境用）
        return True
    
    def get_provider_info(self) -> Dict[str, Any]:
        """プロバイダー情報を取得"""
        return {
            "provider": self.provider.value,
            "provider_name": self.llm_manager.get_provider_name(),
            "model": self._get_current_model(),
            "is_mock": self.llm_manager.is_mock_client(),
            "available": self.is_available()
        }


# デフォルトアダプターインスタンス
default_llm_adapter = ExistingLLMAdapter()