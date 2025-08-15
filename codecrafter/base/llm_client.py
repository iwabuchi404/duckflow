"""
LLMクライアント - 各プロバイダーとの統合
"""
import os
from typing import Any, Dict, Optional, List
from abc import ABC, abstractmethod

from langchain.schema import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain.callbacks.manager import CallbackManagerForLLMRun
from langchain.llms.base import LLM

try:
    from langchain_openai import ChatOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from langchain_anthropic import ChatAnthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    from langchain_groq import ChatGroq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

# OpenRouterはOpenAI互換なので、OpenAIが利用可能ならOpenRouterも利用可能
OPENROUTER_AVAILABLE = OPENAI_AVAILABLE

from .config import config_manager


class LLMClientError(Exception):
    """LLMクライアントエラー"""
    pass


class BaseLLMClient(ABC):
    """LLMクライアントの基底クラス"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    @abstractmethod
    def chat(self, messages: List[Dict[str, str]]) -> str:
        """チャット形式での対話"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """クライアントが利用可能かどうか"""
        pass


class OpenAIClient(BaseLLMClient):
    """OpenAI GPTクライアント"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        if not OPENAI_AVAILABLE:
            raise LLMClientError("langchain-openai がインストールされていません")
        
        api_key = config_manager.get_api_key('openai')
        if not api_key:
            raise LLMClientError("OPENAI_API_KEY が設定されていません")
        
        self.client = ChatOpenAI(
            model=config.get('model', 'gpt-4-turbo-preview'),
            temperature=config.get('temperature', 0.1),
            max_tokens=config.get('max_tokens', 4096),
            openai_api_key=api_key,
        )
    
    def chat(self, messages: List[Dict[str, str]]) -> str:
        """チャット形式での対話"""
        try:
            # メッセージをLangChain形式に変換
            langchain_messages = []
            for msg in messages:
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                
                if role == 'system':
                    langchain_messages.append(SystemMessage(content=content))
                elif role == 'assistant':
                    langchain_messages.append(AIMessage(content=content))
                else:  # user
                    langchain_messages.append(HumanMessage(content=content))
            
            # LLMに送信
            response = self.client.invoke(langchain_messages)
            return response.content
            
        except Exception as e:
            raise LLMClientError(f"OpenAI API呼び出しに失敗しました: {e}")
    
    def is_available(self) -> bool:
        """クライアントが利用可能かどうか"""
        return OPENAI_AVAILABLE and config_manager.get_api_key('openai') is not None


class AnthropicClient(BaseLLMClient):
    """Anthropic Claudeクライアント"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        if not ANTHROPIC_AVAILABLE:
            raise LLMClientError("langchain-anthropic がインストールされていません")
        
        api_key = config_manager.get_api_key('anthropic')
        if not api_key:
            raise LLMClientError("ANTHROPIC_API_KEY が設定されていません")
        
        self.client = ChatAnthropic(
            model=config.get('model', 'claude-3-5-sonnet-20241022'),
            temperature=config.get('temperature', 0.1),
            max_tokens=config.get('max_tokens', 4096),
            anthropic_api_key=api_key,
        )
    
    def chat(self, messages: List[Dict[str, str]]) -> str:
        """チャット形式での対話"""
        try:
            # メッセージをLangChain形式に変換
            langchain_messages = []
            for msg in messages:
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                
                if role == 'system':
                    langchain_messages.append(SystemMessage(content=content))
                elif role == 'assistant':
                    langchain_messages.append(AIMessage(content=content))
                else:  # user
                    langchain_messages.append(HumanMessage(content=content))
            
            # LLMに送信
            response = self.client.invoke(langchain_messages)
            return response.content
            
        except Exception as e:
            raise LLMClientError(f"Anthropic API呼び出しに失敗しました: {e}")
    
    def is_available(self) -> bool:
        """クライアントが利用可能かどうか"""
        return ANTHROPIC_AVAILABLE and config_manager.get_api_key('anthropic') is not None


class GroqClient(BaseLLMClient):
    """Groq LLamaクライアント"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        if not GROQ_AVAILABLE:
            raise LLMClientError("langchain-groq がインストールされていません")
        
        api_key = config_manager.get_api_key('groq')
        if not api_key:
            raise LLMClientError("GROQ_API_KEY が設定されていません")
        
        self.client = ChatGroq(
            model=config.get('model', 'mixtral-8x7b-32768'),
            temperature=config.get('temperature', 0.1),
            max_tokens=config.get('max_tokens', 8192),
            groq_api_key=api_key,
        )
    
    def chat(self, messages: List[Dict[str, str]]) -> str:
        """チャット形式での対話"""
        try:
            # メッセージの検証と前処理
            if not messages:
                raise LLMClientError("メッセージが空です")
            
            # メッセージをLangChain形式に変換
            langchain_messages = []
            for msg in messages:
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                
                # 空のコンテンツをスキップ
                if not content or not content.strip():
                    continue
                
                # コンテンツの長さ制限（Groq APIの制限を考慮）
                if len(content) > 32000:  # 安全マージンを設けて32K文字に制限
                    content = content[:32000] + "...(省略)"
                
                if role == 'system':
                    langchain_messages.append(SystemMessage(content=content))
                elif role == 'assistant':
                    langchain_messages.append(AIMessage(content=content))
                else:  # user
                    langchain_messages.append(HumanMessage(content=content))
            
            if not langchain_messages:
                raise LLMClientError("有効なメッセージがありません")
            
            # LLMに送信
            response = self.client.invoke(langchain_messages)
            
            if not response or not hasattr(response, 'content'):
                raise LLMClientError("Groq APIから無効な応答を受信しました")
            
            return response.content
            
        except Exception as e:
            # より詳細なエラー情報を提供
            error_msg = str(e)
            if "400" in error_msg or "Bad Request" in error_msg:
                raise LLMClientError(f"Groq API リクエストエラー (400): リクエスト内容を確認してください - {error_msg}")
            elif "401" in error_msg or "Unauthorized" in error_msg:
                raise LLMClientError(f"Groq API 認証エラー (401): API キーを確認してください - {error_msg}")
            elif "429" in error_msg or "rate limit" in error_msg.lower():
                raise LLMClientError(f"Groq API レート制限エラー (429): しばらく待ってから再試行してください - {error_msg}")
            elif "500" in error_msg or "Internal Server Error" in error_msg:
                raise LLMClientError(f"Groq API サーバーエラー (500): しばらく待ってから再試行してください - {error_msg}")
            else:
                raise LLMClientError(f"Groq API呼び出しに失敗しました: {error_msg}")
    
    def is_available(self) -> bool:
        """クライアントが利用可能かどうか"""
        return GROQ_AVAILABLE and config_manager.get_api_key('groq') is not None


class OpenRouterClient(BaseLLMClient):
    """OpenRouter APIクライアント（OpenAI互換）"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        if not OPENROUTER_AVAILABLE:
            raise LLMClientError("langchain-openai がインストールされていません（OpenRouter用）")
        
        api_key = config_manager.get_api_key('openrouter')
        if not api_key:
            raise LLMClientError("OPENROUTER_API_KEY が設定されていません")
        
        # OpenRouterはOpenAI互換API
        self.client = ChatOpenAI(
            model=config.get('model', 'anthropic/claude-3-sonnet'),
            temperature=config.get('temperature', 0.1),
            max_tokens=config.get('max_tokens', 4096),
            openai_api_key=api_key,
            openai_api_base="https://openrouter.ai/api/v1",
            model_kwargs={
                "extra_headers": {
                    "HTTP-Referer": "https://duckflow.app",
                    "X-Title": "Duckflow AI Coding Agent"
                }
            }
        )
    
    def chat(self, messages: List[Dict[str, str]]) -> str:
        """チャット形式での対話"""
        # 辞書形式をLangChainメッセージに変換
        langchain_messages = []
        for msg in messages:
            role = msg['role']
            content = msg['content']
            
            if role == 'user':
                langchain_messages.append(HumanMessage(content=content))
            elif role == 'assistant':
                langchain_messages.append(AIMessage(content=content))
            elif role == 'system':
                langchain_messages.append(SystemMessage(content=content))
        
        try:
            response = self.client.invoke(langchain_messages)
            return response.content
        except Exception as e:
            raise LLMClientError(f"OpenRouter API error: {str(e)}")
    
    def is_available(self) -> bool:
        """利用可能かどうかを確認"""
        return OPENROUTER_AVAILABLE and config_manager.get_api_key('openrouter') is not None


class MockClient(BaseLLMClient):
    """モッククライアント（テスト用）"""
    
    def chat(self, messages: List[Dict[str, str]]) -> str:
        """モック応答を返す"""
        return "こちらはモッククライアントです。実際のLLMクライアントを使用するには、適切なAPIキーを設定してください。"
    
    def is_available(self) -> bool:
        """常に利用可能"""
        return True


class LLMManager:
    """LLM管理クラス"""
    
    def __init__(self):
        self.config = config_manager.load_config()
        self.current_client: Optional[BaseLLMClient] = None
        self.summary_client: Optional[BaseLLMClient] = None  # 要約用クライアント
        self._initialize_client()
    
    def _initialize_client(self) -> None:
        """クライアントを初期化"""
        # メインクライアント初期化
        provider = self.config.llm.provider.lower()
        llm_config = config_manager.get_llm_config()
        
        try:
            if provider == 'openai':
                self.current_client = OpenAIClient(llm_config)
            elif provider == 'anthropic':
                self.current_client = AnthropicClient(llm_config)
            elif provider == 'groq':
                self.current_client = GroqClient(llm_config)
            elif provider == 'openrouter':
                self.current_client = OpenRouterClient(llm_config)
            else:
                # 未対応のプロバイダーまたは設定不備の場合はモッククライアント
                self.current_client = MockClient(llm_config)
                
        except LLMClientError as e:
            print(f"警告: LLMクライアントの初期化に失敗しました: {e}")
            print("モッククライアントを使用します。")
            self.current_client = MockClient(llm_config)
        
        # 要約用クライアント初期化 (ステップ2c)
        try:
            summary_provider = self.config.summary_llm.provider.lower()
            summary_config = getattr(self.config.summary_llm, summary_provider, {})
            if isinstance(summary_config, dict):
                if summary_provider == 'openai':
                    self.summary_client = OpenAIClient(summary_config)
                elif summary_provider == 'anthropic':
                    self.summary_client = AnthropicClient(summary_config)
                elif summary_provider == 'groq':
                    self.summary_client = GroqClient(summary_config)
                elif summary_provider == 'openrouter':
                    self.summary_client = OpenRouterClient(summary_config)
                else:
                    self.summary_client = self.current_client  # フォールバック
            else:
                self.summary_client = self.current_client  # フォールバック
        except Exception:
            # 要約用クライアントの初期化に失敗した場合はメインクライアントを使用
            self.summary_client = self.current_client
    
    def chat(self, message: str, system_prompt: Optional[str] = None, client_type: str = "main") -> str:
        """シンプルなチャット
        
        Args:
            message: ユーザーメッセージ
            system_prompt: システムプロンプト
            client_type: クライアントタイプ ("main" または "summary")
        
        Returns:
            LLMの応答
        """
        messages = []
        
        if system_prompt:
            messages.append({
                'role': 'system',
                'content': system_prompt
            })
        
        messages.append({
            'role': 'user',
            'content': message
        })
        
        # クライアントタイプに応じて適切なクライアントを選択
        client = self.summary_client if client_type == "summary" else self.current_client
        return client.chat(messages)
    
    def chat_with_history(self, messages: List[Dict[str, str]]) -> str:
        """履歴付きチャット"""
        return self.current_client.chat(messages)
    
    def get_provider_name(self) -> str:
        """現在のプロバイダー名を取得"""
        if isinstance(self.current_client, OpenAIClient):
            return "OpenAI"
        elif isinstance(self.current_client, AnthropicClient):
            return "Anthropic"
        elif isinstance(self.current_client, GroqClient):
            return "Groq"
        elif isinstance(self.current_client, OpenRouterClient):
            return "OpenRouter"
        elif isinstance(self.current_client, MockClient):
            return "Mock"
        else:
            return "Unknown"
    
    def is_mock_client(self) -> bool:
        """モッククライアントかどうか"""
        return isinstance(self.current_client, MockClient)



    def get_default_client(self) -> BaseLLMClient:
        """デフォルトクライアントを取得 (後方互換性のため)
        
        Returns:
            現在のメインクライアント
        """
        return self.current_client
    
    def get_client(self, client_type: str = "main") -> BaseLLMClient:
        """指定されたタイプのクライアントを取得
        
        Args:
            client_type: クライアントタイプ ("main" または "summary")
            
        Returns:
            指定されたクライアント
        """
        if client_type == "summary":
            return self.summary_client
        return self.current_client

# グローバルなLLM管理インスタンス
llm_manager = LLMManager()