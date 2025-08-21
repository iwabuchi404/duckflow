#!/usr/bin/env python3
"""
LLMクライアント - LLMとの通信管理

codecrafterから分離し、companion内で完結するように調整
"""

import json
import logging
import asyncio
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class LLMRequest:
    """LLMリクエスト"""
    prompt: str
    model: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: int = 1000
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            'prompt': self.prompt,
            'model': self.model,
            'temperature': self.temperature,
            'max_tokens': self.max_tokens,
            'metadata': self.metadata,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class LLMResponse:
    """LLMレスポンス"""
    content: str
    model: str
    usage: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            'content': self.content,
            'model': self.model,
            'usage': self.usage,
            'metadata': self.metadata,
            'timestamp': self.timestamp.isoformat()
        }


class LLMClientError(Exception):
    """LLMクライアントエラー"""
    pass


class ExternalManagerClient:
    """外部LLMマネージャー（codecrafter）のchatを利用するプロキシクライアント"""

    def __init__(self, provider: str, model: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        self.provider = provider
        self.model = model or "external-default"

    async def generate(self, request: LLMRequest) -> LLMResponse:
        try:
            # 遅延インポート（存在しない環境ではImportError）
            from codecrafter.base.llm_client import llm_manager as external_llm_manager

            system_prompt = None
            try:
                system_prompt = request.metadata.get('system_prompt') if request.metadata else None
            except Exception:
                system_prompt = None

            loop = asyncio.get_event_loop()
            # 同期関数をスレッドで実行
            content = await loop.run_in_executor(
                None,
                external_llm_manager.chat,
                request.prompt,
                system_prompt
            )

            usage = {
                'prompt_tokens': len(request.prompt.split()),
                'completion_tokens': len(str(content).split()),
                'total_tokens': len(request.prompt.split()) + len(str(content).split())
            }

            return LLMResponse(
                content=str(content),
                model=self.model,
                usage=usage,
                metadata={'external': True, 'provider': self.provider}
            )
        except Exception as e:
            raise LLMClientError(f"外部LLM呼び出しに失敗しました: {e}")


class MockLLMClient:
    """モックLLMクライアント（テスト用）"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.request_count = 0
        self.response_count = 0
        
        # 設定ファイルからプロバイダー情報を読み込み
        self.provider = self._load_config_provider()
        self.model = self._load_config_model()
        
        self.logger.info(f"MockLLMClient初期化完了 - プロバイダー: {self.provider}, モデル: {self.model}")
    
    def _load_config_provider(self) -> str:
        """設定ファイルからプロバイダーを読み込み"""
        try:
            import yaml
            import os
            
            config_path = "config/config.yaml"
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    return config.get('llm', {}).get('provider', 'mock')
            return 'mock'
        except Exception as e:
            self.logger.warning(f"設定ファイル読み込みエラー: {e}")
            return 'mock'
    
    def _load_config_model(self) -> str:
        """設定ファイルからモデルを読み込み"""
        try:
            import yaml
            import os
            
            config_path = "config/config.yaml"
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    provider = config.get('llm', {}).get('provider', 'mock')
                    if provider in config.get('llm', {}):
                        return config['llm'][provider].get('model', 'mock-model')
            return 'mock-model'
        except Exception as e:
            self.logger.warning(f"設定ファイル読み込みエラー: {e}")
            return 'mock-model'
    
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """モック生成"""
        try:
            self.request_count += 1
            
            # 意図分析要求の場合はJSON形式で応答
            if "意図" in request.prompt or "分析" in request.prompt or "JSON" in request.prompt:
                mock_content = """{
  "intent": "information_request",
  "confidence": 0.85,
  "action_type": "file_operation",
  "parameters": {
    "target_file": "game_doc.md",
    "operation": "read_and_analyze"
  }
}"""
            # ファイル読み取り要求の場合は実際のファイルを読み取る
            elif "game_doc.md" in request.prompt or "ファイル" in request.prompt or "読んで" in request.prompt:
                try:
                    import os
                    if os.path.exists("game_doc.md"):
                        with open("game_doc.md", "r", encoding="utf-8") as f:
                            file_content = f.read()
                        mock_content = f"""ファイル内容を確認しました。

**game_doc.md の概要:**

{file_content[:500]}{'...' if len(file_content) > 500 else ''}

このファイルはゲーム開発に関するドキュメントのようです。詳細な内容を確認する必要がありますか？"""
                    else:
                        mock_content = "ファイル 'game_doc.md' が見つかりません。ファイルが存在するか確認してください。"
                except Exception as e:
                    mock_content = f"ファイル読み取りエラー: {str(e)}"
            else:
                # 通常のモックレスポンス
                mock_content = f"モックLLMレスポンス #{self.request_count}\n\n要求: {request.prompt[:100]}..."
            
            response = LLMResponse(
                content=mock_content,
                model=self.model,  # 設定ファイルのモデル名を使用
                usage={
                    'prompt_tokens': len(request.prompt.split()),
                    'completion_tokens': len(mock_content.split()),
                    'total_tokens': len(request.prompt.split()) + len(mock_content.split())
                },
                metadata={
                    'mock': True, 
                    'request_id': self.request_count,
                    'provider': self.provider,
                    'config_model': self.model
                }
            )
            
            self.response_count += 1
            self.logger.info(f"モックLLMレスポンス生成: {self.response_count}")
            
            return response
            
        except Exception as e:
            self.logger.error(f"モックLLM生成エラー: {e}")
            raise LLMClientError(f"モックLLM生成エラー: {str(e)}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """統計情報を取得"""
        return {
            'request_count': self.request_count,
            'response_count': self.response_count,
            'client_type': 'mock'
        }


class LLMManager:
    """LLMマネージャー"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.clients: Dict[str, Union[MockLLMClient, ExternalManagerClient]] = {}
        self.default_client = "mock"

        # モッククライアントを常に初期化
        self.clients["mock"] = MockLLMClient()

        # APIキーと設定に基づいて実クライアントの初期化を試行
        self._try_init_real_client()

        # モックが許可されているかチェック
        self._mock_allowed = self._is_mock_allowed()

        # 本番環境チェック
        if self._is_production_environment():
            # 本番環境では絶対にモックLLMを許可しない
            if self.default_client == "mock":
                raise LLMClientError(
                    "本番環境では絶対にモックLLMは使用できません。実LLMのAPIキーを設定してください。"
                )
        else:
            # 開発環境ではモックLLMを許可
            self.logger.info("開発環境: モックLLMの使用を許可")
            if self.default_client == "mock" and not self._mock_allowed:
                # 開発環境でもモックが許可されていない場合はエラー
                raise LLMClientError(
                    "開発環境でモックLLMが許可されていません。DUCKFLOW_ALLOW_MOCK=1を設定してください。"
                )

        self.logger.info(f"LLMManager初期化完了。デフォルトクライアント: {self.default_client}")

    def _is_mock_allowed(self) -> bool:
        import os
        # テスト実行時や明示許可のときのみモックを許可
        return bool(os.getenv('DUCKFLOW_ALLOW_MOCK') or os.getenv('PYTEST_CURRENT_TEST'))
    
    def _is_production_environment(self) -> bool:
        """本番環境かどうかをチェック"""
        try:
            import os
            
            # 環境変数で本番環境フラグをチェック
            if os.getenv('DUCKFLOW_ENV') == 'production':
                self.logger.info("環境変数DUCKFLOW_ENV=productionにより本番環境と判定")
                return True
            
            # APIキーの存在で本番環境と判断
            api_keys = [
                'OPENAI_API_KEY',
                'ANTHROPIC_API_KEY', 
                'GROQ_API_KEY',
                'OPENROUTER_API_KEY'
            ]
            
            found_keys = []
            for key in api_keys:
                if os.getenv(key):
                    found_keys.append(key)
            
            if found_keys:
                self.logger.info(f"APIキーが設定されているため本番環境と判定: {found_keys}")
                return True
            
            # 開発環境の場合はFalse
            self.logger.info("APIキーが設定されていないため開発環境と判定")
            return False
            
        except Exception as e:
            self.logger.warning(f"環境チェックエラー: {e}")
            # エラーの場合は安全側に倒して本番環境とみなす
            self.logger.warning("環境チェックエラーのため、安全側に倒して本番環境と判定")
            return True

    def _try_init_real_client(self):
        """環境変数からAPIキーを検知し、実クライアントを初期化・設定する"""
        import os
        
        # サポートされているプロバイダーと対応する環境変数
        supported_providers = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "groq": "GROQ_API_KEY",
            "google": "GOOGLE_AI_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
        }

        for provider, env_key in supported_providers.items():
            if os.getenv(env_key):
                self.logger.info(f"{env_key} を検知。{provider} の実LLMクライアントを初期化します。")
                # ExternalManagerClientは汎用プロキシとして使用
                # 実際のモデル名は外部のllm_managerに依存する
                self.clients['external'] = ExternalManagerClient(provider=provider)
                self.default_client = 'external'
                # 最初のキーが見つかった時点でループを抜ける
                self.logger.info(f"実LLMに自動切替完了: provider={provider}")
                return
    
    def get_client(self, client_name: Optional[str] = None) -> Union[MockLLMClient]:
        """LLMクライアントを取得"""
        name = client_name or self.default_client
        
        if name not in self.clients:
            self.logger.warning(f"LLMクライアントが見つかりません: {name}、モッククライアントを使用")
            name = "mock"
        
        return self.clients[name]
    
    async def generate(self, prompt: str, model: str = "gpt-4", 
                      temperature: float = 0.7, max_tokens: int = 1000,
                      client_name: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> str:
        """LLMでテキスト生成"""
        try:
            client = self.get_client(client_name)
            
            # 本番環境チェック
            if self._is_production_environment():
                if self.default_client == 'mock':
                    raise LLMClientError("本番環境では絶対にモックLLMは使用できません。実LLMのAPIキーを設定してください。")
                if isinstance(client, MockLLMClient):
                    raise LLMClientError("本番環境では絶対にモックLLMは使用できません。実LLMのAPIキーを設定してください。")
            else:
                # 開発環境でのみモックLLMを許可
                if self.default_client == 'mock' and not getattr(self, '_mock_allowed', False):
                    raise LLMClientError("モックLLMはテスト時のみ許可されています。実LLMのAPIキーを設定してください。")
            
            request = LLMRequest(
                prompt=prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                metadata=metadata or {}
            )
            
            response = await client.generate(request)
            
            self.logger.info(f"LLM生成完了: {response.model} ({len(response.content)}文字)")
            return response.content
            
        except Exception as e:
            self.logger.error(f"LLM生成エラー: {e}")
            return f"LLM生成エラー: {str(e)}"
    
    def add_client(self, name: str, client: Union[MockLLMClient]) -> bool:
        """LLMクライアントを追加"""
        try:
            self.clients[name] = client
            self.logger.info(f"LLMクライアント追加: {name}")
            return True
            
        except Exception as e:
            self.logger.error(f"LLMクライアント追加エラー: {e}")
            return False
    
    def remove_client(self, name: str) -> bool:
        """LLMクライアントを削除"""
        try:
            if name in self.clients and name != "mock":
                del self.clients[name]
                self.logger.info(f"LLMクライアント削除: {name}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"LLMクライアント削除エラー: {e}")
            return False
    
    def set_default_client(self, name: str) -> bool:
        """デフォルトクライアントを設定"""
        try:
            if name in self.clients:
                self.default_client = name
                self.logger.info(f"デフォルトLLMクライアント設定: {name}")
                return True
            else:
                self.logger.warning(f"LLMクライアントが見つかりません: {name}")
                return False
                
        except Exception as e:
            self.logger.error(f"デフォルトLLMクライアント設定エラー: {e}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """統計情報を取得"""
        stats = {
            'total_clients': len(self.clients),
            'default_client': self.default_client,
            'clients': {}
        }
        
        for name, client in self.clients.items():
            if hasattr(client, 'get_statistics'):
                stats['clients'][name] = client.get_statistics()
            else:
                stats['clients'][name] = {'type': type(client).__name__}
        
        return stats
    
    def get_provider_name(self) -> str:
        """現在のプロバイダー名を取得"""
        return self.default_client
    
    def _is_production_environment(self) -> bool:
        """本番環境かどうかをチェック"""
        try:
            import os
            
            # 環境変数で本番環境フラグをチェック
            if os.getenv('DUCKFLOW_ENV') == 'production':
                self.logger.info("環境変数DUCKFLOW_ENV=productionにより本番環境と判定")
                return True
            
            # APIキーの存在で本番環境と判断
            api_keys = [
                'OPENAI_API_KEY',
                'ANTHROPIC_API_KEY', 
                'GROQ_API_KEY',
                'OPENROUTER_API_KEY'
            ]
            
            found_keys = []
            for key in api_keys:
                if os.getenv(key):
                    found_keys.append(key)
            
            if found_keys:
                self.logger.info(f"APIキーが設定されているため本番環境と判定: {found_keys}")
                return True
            
            # 開発環境の場合はFalse
            self.logger.info("APIキーが設定されていないため開発環境と判定")
            return False
            
        except Exception as e:
            self.logger.warning(f"環境チェックエラー: {e}")
            # エラーの場合は安全側に倒して本番環境とみなす
            self.logger.warning("環境チェックエラーのため、安全側に倒して本番環境と判定")
            return True
    
    def is_mock_client(self) -> bool:
        """現在のクライアントがモックかどうかチェック"""
        return self.default_client == "mock"
    
    def chat_with_history(self, messages: List[Dict[str, str]]) -> str:
        """履歴付きチャット（既存システム互換）"""
        try:
            # 最後のユーザーメッセージを取得
            user_message = None
            for msg in reversed(messages):
                if msg.get('role') == 'user':
                    user_message = msg.get('content', '')
                    break
            
            if not user_message:
                return "ユーザーメッセージが見つかりません"
            
            # システムメッセージを構築
            system_prompt = ""
            for msg in messages:
                if msg.get('role') == 'system':
                    system_prompt = msg.get('content', '')
                    break
            
            # 非同期生成を同期的に実行
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 既存のループが実行中の場合は、新しいループを作成
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            asyncio.run,
                            self.generate(user_message, metadata={'system_prompt': system_prompt})
                        )
                        return future.result()
                else:
                    return asyncio.run(self.generate(user_message, metadata={'system_prompt': system_prompt}))
            except RuntimeError:
                # ループが実行中でない場合
                return asyncio.run(self.generate(user_message, metadata={'system_prompt': system_prompt}))
                
        except Exception as e:
            self.logger.error(f"履歴付きチャットエラー: {e}")
            return f"チャットエラー: {str(e)}"
    
    def chat(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """シンプルなチャット（既存システム互換）"""
        try:
            metadata = {}
            if system_prompt:
                metadata['system_prompt'] = system_prompt
            
            # 非同期生成を同期的に実行
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 既存のループが実行中の場合は、新しいループを作成
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            asyncio.run,
                            self.generate(prompt, metadata=metadata)
                        )
                        return future.result()
                else:
                    return asyncio.run(self.generate(prompt, metadata=metadata))
            except RuntimeError:
                # ループが実行中でない場合
                return asyncio.run(self.generate(prompt, metadata=metadata))
                
        except Exception as e:
            self.logger.error(f"チャットエラー: {e}")
            return f"チャットエラー: {str(e)}"
    
    def to_dict(self) -> Dict[str, Any]:
        """オブジェクトの状態を辞書形式で取得"""
        return {
            'clients': list(self.clients.keys()),
            'default_client': self.default_client,
            'statistics': self.get_statistics()
        }


# グローバルインスタンス
llm_manager = LLMManager()


# 便利な関数
def get_llm_client(client_name: Optional[str] = None):
    """LLMクライアントを取得"""
    return llm_manager.get_client(client_name)


async def generate_text(prompt: str, model: str = "gpt-4", 
                       temperature: float = 0.7, max_tokens: int = 1000,
                       client_name: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> str:
    """LLMでテキスト生成"""
    return await llm_manager.generate(prompt, model, temperature, max_tokens, client_name, metadata)


def add_llm_client(name: str, client):
    """LLMクライアントを追加"""
    return llm_manager.add_client(name, client)


def set_default_llm_client(name: str) -> bool:
    """デフォルトLLMクライアントを設定"""
    return llm_manager.set_default_client(name)
