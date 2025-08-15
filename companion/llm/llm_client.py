"""
Companion LLM Client

マルチプロバイダーLLMクライアント
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

# 環境変数の読み込み
def load_env_vars():
    """環境変数を読み込み"""
    env_vars = {}
    
    # APIキー
    env_vars['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY')
    env_vars['ANTHROPIC_API_KEY'] = os.getenv('ANTHROPIC_API_KEY')
    env_vars['OPENROUTER_API_KEY'] = os.getenv('OPENROUTER_API_KEY')
    
    # 設定
    env_vars['DEFAULT_LLM_PROVIDER'] = os.getenv('DEFAULT_LLM_PROVIDER', 'openai')
    env_vars['DEFAULT_MODEL'] = os.getenv('DEFAULT_MODEL', 'gpt-4')
    env_vars['MAX_TOKENS'] = int(os.getenv('MAX_TOKENS', '1000'))
    env_vars['TEMPERATURE'] = float(os.getenv('TEMPERATURE', '0.1'))
    
    return env_vars

# 環境変数を読み込み
ENV_VARS = load_env_vars()

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class LLMProvider(Enum):
    """LLMプロバイダー"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OPENROUTER = "openrouter"


@dataclass
class LLMResponse:
    """LLM応答の構造化データ"""
    content: str
    provider: LLMProvider
    model: str
    tokens_used: Optional[int] = None
    confidence: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class LLMClient:
    """シンプルなLLMクライアント"""
    
    def __init__(self, provider: LLMProvider = LLMProvider.OPENAI):
        """LLMクライアントを初期化"""
        self.provider = provider
        self.logger = logging.getLogger(__name__)
        
        # 設定の読み込み
        self.config = self._load_config()
        
        # プロバイダーの初期化
        self._initialize_provider()
    
    def _load_config(self) -> Dict[str, Any]:
        """設定を読み込み"""
        config = {
            "openai": {
                "api_key": os.getenv("OPENAI_API_KEY"),
                "base_url": os.getenv("OPENAI_BASE_URL"),
                "default_model": "gpt-4o-mini"
            },
            "anthropic": {
                "api_key": os.getenv("ANTHROPIC_API_KEY"),
                "default_model": "claude-3-haiku-20240307"
            },
            "openrouter": {
                "api_key": os.getenv("OPENROUTER_API_KEY"),
                "base_url": "https://openrouter.ai/api/v1",
                "default_model": "anthropic/claude-3-haiku"
            }
        }
        
        return config
    
    def _initialize_provider(self):
        """プロバイダーを初期化"""
        if self.provider == LLMProvider.OPENAI and OPENAI_AVAILABLE:
            if not self.config["openai"]["api_key"]:
                self.logger.warning("OpenAI API key not found")
                
        elif self.provider == LLMProvider.ANTHROPIC and ANTHROPIC_AVAILABLE:
            if not self.config["anthropic"]["api_key"]:
                self.logger.warning("Anthropic API key not found")
                
        elif self.provider == LLMProvider.OPENROUTER:
            if not self.config["openrouter"]["api_key"]:
                self.logger.warning("OpenRouter API key not found")
    
    async def chat(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.1,
        **kwargs
    ) -> LLMResponse:
        """
        LLMとの対話を実行
        
        Args:
            prompt: ユーザープロンプト
            system_prompt: システムプロンプト
            model: 使用モデル
            max_tokens: 最大トークン数
            temperature: 創造性（0.0-1.0）
            
        Returns:
            LLM応答
        """
        try:
            if self.provider == LLMProvider.OPENAI:
                return await self._chat_openai(
                    prompt, system_prompt, model, max_tokens, temperature, **kwargs
                )
            elif self.provider == LLMProvider.ANTHROPIC:
                return await self._chat_anthropic(
                    prompt, system_prompt, model, max_tokens, temperature, **kwargs
                )
            elif self.provider == LLMProvider.OPENROUTER:
                return await self._chat_openrouter(
                    prompt, system_prompt, model, max_tokens, temperature, **kwargs
                )
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")
                
        except Exception as e:
            self.logger.error(f"LLM chat error: {e}")
            return self._create_error_response(str(e))
    
    async def _chat_openai(
        self, 
        prompt: str, 
        system_prompt: Optional[str],
        model: Optional[str],
        max_tokens: int,
        temperature: float,
        **kwargs
    ) -> LLMResponse:
        """OpenAI APIを使用したチャット"""
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI library not available")
        
        model = model or self.config["openai"]["default_model"]
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        # OpenAI v1.0+ 対応
        client = openai.OpenAI(
            api_key=self.config["openai"]["api_key"],
            base_url=self.config["openai"]["base_url"]
        )
        
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs
        )
        
        return LLMResponse(
            content=response.choices[0].message.content,
            provider=LLMProvider.OPENAI,
            model=model,
            tokens_used=response.usage.total_tokens if hasattr(response, 'usage') else None,
            metadata={"response_id": response.id}
        )
    
    async def _chat_anthropic(
        self, 
        prompt: str, 
        system_prompt: Optional[str],
        model: Optional[str],
        max_tokens: int,
        temperature: float,
        **kwargs
    ) -> LLMResponse:
        """Anthropic APIを使用したチャット"""
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("Anthropic library not available")
        
        model = model or self.config["anthropic"]["default_model"]
        
        client = anthropic.Anthropic(api_key=self.config["anthropic"]["api_key"])
        
        # システムプロンプトの処理
        if system_prompt:
            prompt = f"{system_prompt}\n\n{prompt}"
        
        response = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
            **kwargs
        )
        
        return LLMResponse(
            content=response.content[0].text,
            provider=LLMProvider.ANTHROPIC,
            model=model,
            tokens_used=response.usage.input_tokens + response.usage.output_tokens if hasattr(response, 'usage') else None,
            metadata={"response_id": response.id}
        )
    
    async def _chat_openrouter(
        self, 
        prompt: str, 
        system_prompt: Optional[str],
        model: Optional[str],
        max_tokens: int,
        temperature: float,
        **kwargs
    ) -> LLMResponse:
        """OpenRouter APIを使用したチャット"""
        import aiohttp
        
        model = model or self.config["openrouter"]["default_model"]
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        headers = {
            "Authorization": f"Bearer {self.config['openrouter']['api_key']}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            **kwargs
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.config['openrouter']['base_url']}/chat/completions",
                headers=headers,
                json=data
            ) as response:
                result = await response.json()
                
                if response.status != 200:
                    raise Exception(f"OpenRouter API error: {result}")
                
                return LLMResponse(
                    content=result["choices"][0]["message"]["content"],
                    provider=LLMProvider.OPENROUTER,
                    model=model,
                    tokens_used=result["usage"]["total_tokens"] if "usage" in result else None,
                    metadata={"response_id": result["id"]}
                )
    
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
        if self.provider == LLMProvider.OPENAI:
            return OPENAI_AVAILABLE and bool(self.config["openai"]["api_key"])
        elif self.provider == LLMProvider.ANTHROPIC:
            return ANTHROPIC_AVAILABLE and bool(self.config["anthropic"]["api_key"])
        elif self.provider == LLMProvider.OPENROUTER:
            return bool(self.config["openrouter"]["api_key"])
        return False


# デフォルトLLMクライアント
default_llm_client = LLMClient(LLMProvider.OPENAI)
