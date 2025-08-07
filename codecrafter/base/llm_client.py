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
            response = self.client(langchain_messages)
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
            response = self.client(langchain_messages)
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
            response = self.client(langchain_messages)
            return response.content
            
        except Exception as e:
            raise LLMClientError(f"Groq API呼び出しに失敗しました: {e}")
    
    def is_available(self) -> bool:
        """クライアントが利用可能かどうか"""
        return GROQ_AVAILABLE and config_manager.get_api_key('groq') is not None


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
        self._initialize_client()
    
    def _initialize_client(self) -> None:
        """クライアントを初期化"""
        provider = self.config.llm.provider.lower()
        llm_config = config_manager.get_llm_config()
        
        try:
            if provider == 'openai':
                self.current_client = OpenAIClient(llm_config)
            elif provider == 'anthropic':
                self.current_client = AnthropicClient(llm_config)
            elif provider == 'groq':
                self.current_client = GroqClient(llm_config)
            else:
                # 未対応のプロバイダーまたは設定不備の場合はモッククライアント
                self.current_client = MockClient(llm_config)
                
        except LLMClientError as e:
            print(f"警告: LLMクライアントの初期化に失敗しました: {e}")
            print("モッククライアントを使用します。")
            self.current_client = MockClient(llm_config)
    
    def chat(self, message: str, system_prompt: Optional[str] = None) -> str:
        """シンプルなチャット"""
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
        
        return self.current_client.chat(messages)
    
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
        elif isinstance(self.current_client, MockClient):
            return "Mock"
        else:
            return "Unknown"
    
    def is_mock_client(self) -> bool:
        """モッククライアントかどうか"""
        return isinstance(self.current_client, MockClient)


# グローバルなLLM管理インスタンス
llm_manager = LLMManager()