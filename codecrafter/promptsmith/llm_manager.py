"""
PromptSmith専用LLM管理システム
役割別AI設定を管理し、適切なLLMクライアントを提供する
"""

from typing import Dict, Optional, Any
from codecrafter.base.config import config_manager
from codecrafter.base.llm_client import llm_manager


class PromptSmithLLMManager:
    """PromptSmith専用LLM管理クラス"""
    
    def __init__(self):
        """初期化"""
        self._ai_clients: Dict[str, Any] = {}
        self._config_cache: Dict[str, Dict[str, Any]] = {}
    
    def get_ai_client(self, ai_role: str):
        """
        指定されたAI役割のクライアントを取得
        
        Args:
            ai_role: AI役割名 ("tester_ai", "evaluator_ai", "optimizer_ai", "conversation_analyzer", "target_ai")
            
        Returns:
            LLMクライアントオブジェクト
        """
        # キャッシュから取得
        if ai_role in self._ai_clients:
            return self._ai_clients[ai_role]
        
        # PromptSmith設定を確認
        promptsmith_config = config_manager.get_promptsmith_config()
        if not promptsmith_config or not promptsmith_config.evaluation.separate_ai_roles:
            # 役割別設定が無効の場合はメインLLMクライアントを使用
            return llm_manager.current_client
        
        # 役割別プロバイダーと設定を取得
        provider = config_manager.get_promptsmith_provider(ai_role)
        ai_config = config_manager.get_promptsmith_ai_config(ai_role)
        
        if not provider or not ai_config:
            # 設定がない場合はメインLLMクライアントを使用
            return llm_manager.current_client
        
        # 役割別クライアントを作成
        client = self._create_ai_client(provider, ai_config, ai_role)
        self._ai_clients[ai_role] = client
        
        return client
    
    def _create_ai_client(self, provider: str, ai_config: Dict[str, Any], ai_role: str):
        """
        指定された設定でLLMクライアントを作成
        
        Args:
            provider: プロバイダー名
            ai_config: AI設定
            ai_role: AI役割名
            
        Returns:
            LLMクライアント
        """
        # APIキーを取得
        api_key = config_manager.get_api_key(provider)
        if not api_key:
            print(f"[WARNING] {provider} API key not found for {ai_role}, using main LLM client")
            return llm_manager.current_client
        
        # プロバイダー別クライアント作成
        try:
            if provider == "openai":
                from codecrafter.base.llm_client import OpenAIClient
                return OpenAIClient(ai_config)
            elif provider == "anthropic":
                from codecrafter.base.llm_client import AnthropicClient
                return AnthropicClient(ai_config)
            elif provider == "groq":
                from codecrafter.base.llm_client import GroqClient
                return GroqClient(ai_config)
            elif provider == "google":
                from codecrafter.base.llm_client import GoogleClient
                return GoogleClient(ai_config)
            elif provider == "openrouter":
                from codecrafter.base.llm_client import OpenRouterClient
                return OpenRouterClient(ai_config)
            else:
                print(f"[WARNING] Unsupported provider {provider} for {ai_role}, using main LLM client")
                return llm_manager.current_client
                
        except Exception as e:
            print(f"[ERROR] Failed to create {provider} client for {ai_role}: {e}")
            return llm_manager.current_client
    
    def chat_with_role(self, ai_role: str, message: str, conversation_history: Optional[list] = None) -> str:
        """
        指定されたAI役割でチャットを実行
        
        Args:
            ai_role: AI役割名
            message: メッセージ
            conversation_history: 会話履歴
            
        Returns:
            AIからの応答
        """
        client = self.get_ai_client(ai_role)
        
        # 会話履歴がある場合は含める
        messages = []
        if conversation_history:
            messages.extend(conversation_history)
        
        messages.append({"role": "user", "content": message})
        
        try:
            response = client.chat(messages)
            return response
        except Exception as e:
            print(f"[ERROR] Chat failed for {ai_role}: {e}")
            return f"Error: Failed to get response from {ai_role}"
    
    def get_role_info(self, ai_role: str) -> Dict[str, Any]:
        """
        指定されたAI役割の設定情報を取得
        
        Args:
            ai_role: AI役割名
            
        Returns:
            AI役割設定情報
        """
        provider = config_manager.get_promptsmith_provider(ai_role)
        ai_config = config_manager.get_promptsmith_ai_config(ai_role)
        
        return {
            "role": ai_role,
            "provider": provider,
            "config": ai_config,
            "has_api_key": bool(config_manager.get_api_key(provider)) if provider else False
        }
    
    def get_all_roles_info(self) -> Dict[str, Dict[str, Any]]:
        """
        全AI役割の設定情報を取得
        
        Returns:
            全AI役割の設定情報辞書
        """
        roles = ["tester_ai", "evaluator_ai", "optimizer_ai", "conversation_analyzer", "target_ai"]
        
        return {
            role: self.get_role_info(role) for role in roles
        }
    
    def is_separate_roles_enabled(self) -> bool:
        """役割別AI設定が有効かどうかを確認"""
        promptsmith_config = config_manager.get_promptsmith_config()
        return (promptsmith_config and 
                promptsmith_config.evaluation.separate_ai_roles)
    
    def clear_cache(self) -> None:
        """キャッシュをクリア"""
        self._ai_clients.clear()
        self._config_cache.clear()


# グローバルなPromptSmith LLM管理インスタンス
promptsmith_llm_manager = PromptSmithLLMManager()