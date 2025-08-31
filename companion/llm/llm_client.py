"""
Companion LLM Client

マルチプロバイダーLLMクライアント
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

# 環境変数の読み込み
def load_env_vars():
    """環境変数を読み込み"""
    env_vars = {}
    
    # .envファイルの読み込み
    from ..config.config_manager import load_config
    try:
        config = load_config()
        env_vars['DEFAULT_LLM_PROVIDER'] = config.llm_provider
        env_vars['DEFAULT_MODEL'] = config.llm_model
        env_vars['MAX_TOKENS'] = config.llm_max_retries
        env_vars['TEMPERATURE'] = config.llm_temperature
    except Exception as e:
        print(f"設定読み込みエラー: {e}")
        # デフォルト値を使用
        env_vars['DEFAULT_LLM_PROVIDER'] = 'groq'
        env_vars['DEFAULT_MODEL'] = 'openai/gpt-oss-20b'
        env_vars['MAX_TOKENS'] = 1000
        env_vars['TEMPERATURE'] = 0.1
    
    # APIキー（環境変数から直接読み込み）
    env_vars['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY')
    env_vars['ANTHROPIC_API_KEY'] = os.getenv('ANTHROPIC_API_KEY')
    env_vars['OPENROUTER_API_KEY'] = os.getenv('OPENROUTER_API_KEY')
    env_vars['GROQ_API_KEY'] = os.getenv('GROQ_API_KEY')
    
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
    GROQ = "groq"
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
    
    def __init__(self, provider: LLMProvider = None):
        """LLMクライアントを初期化"""
        self.logger = logging.getLogger(__name__)
        
        # .envファイルの明示的な読み込み
        try:
            from dotenv import load_dotenv
            load_dotenv()
            self.logger.info(".envファイルを読み込みました")
        except ImportError:
            self.logger.warning("python-dotenvがインストールされていません")
        except Exception as e:
            self.logger.warning(f".envファイル読み込みエラー: {e}")
        
        # 設定の読み込み
        self.config = self._load_config()
        
        # プロバイダーの設定
        if provider is None:
            # config.yamlからデフォルトプロバイダーを読み込み
            try:
                from ..config.config_manager import load_config
                config = load_config()
                if config.llm_provider == "groq":
                    self.provider = LLMProvider.GROQ
                elif config.llm_provider == "anthropic":
                    self.provider = LLMProvider.ANTHROPIC
                elif config.llm_provider == "openai":
                    self.provider = LLMProvider.OPENAI
                elif config.llm_provider == "openrouter":
                    self.provider = LLMProvider.OPENROUTER
                else:
                    self.provider = LLMProvider.GROQ  # デフォルト
            except Exception as e:
                self.logger.warning(f"設定読み込みエラー: {e}, デフォルトプロバイダーを使用")
                self.provider = LLMProvider.GROQ  # デフォルト
        else:
            self.provider = provider
        
        # プロバイダーの初期化
        self._initialize_provider()
    
    def _load_config(self) -> Dict[str, Any]:
        """設定を読み込み"""
        from ..config.config_manager import load_config
        
        try:
            config = load_config()
            
            # 環境変数の読み込み状況をログ出力
            self.logger.info(f"環境変数読み込み状況:")
            self.logger.info(f"  GROQ_API_KEY: {os.getenv('GROQ_API_KEY', 'Not found')[:10]}..." if os.getenv('GROQ_API_KEY') else "  GROQ_API_KEY: Not found")
            self.logger.info(f"  OPENAI_API_KEY: {os.getenv('OPENAI_API_KEY', 'Not found')[:10]}..." if os.getenv('OPENAI_API_KEY') else "  OPENAI_API_KEY: Not found")
            self.logger.info(f"  設定ファイルプロバイダー: {config.llm_provider}")
            
            # 環境変数を優先的に読み込み、設定ファイルはフォールバック
            config_data = {
                "openai": {
                    "api_key": os.getenv("OPENAI_API_KEY") or (config.llm_api_key if config.llm_provider == "openai" else ""),
                    "base_url": os.getenv("OPENAI_BASE_URL"),
                    "default_model": config.llm_model if config.llm_provider == "openai" else "gpt-4o-mini"
                },
                "anthropic": {
                    "api_key": os.getenv("ANTHROPIC_API_KEY") or (config.llm_api_key if config.llm_provider == "anthropic" else ""),
                    "default_model": config.llm_model if config.llm_provider == "anthropic" else "claude-3-haiku-20240307"
                },
                "groq": {
                    "api_key": os.getenv("GROQ_API_KEY") or (config.llm_api_key if config.llm_provider == "groq" else ""),
                    "default_model": config.llm_model if config.llm_provider == "groq" else "openai/gpt-oss-20b"
                },
                "openrouter": {
                    "api_key": os.getenv("OPENROUTER_API_KEY") or (config.llm_api_key if config.llm_provider == "openrouter" else ""),
                    "base_url": "https://openrouter.ai/api/v1",
                    "default_model": config.llm_model if config.llm_provider == "openrouter" else "anthropic/claude-3-5-sonnet-20241022"
                }
            }
            
            # 設定データの読み込み状況をログ出力
            self.logger.info(f"設定データ読み込み状況:")
            self.logger.info(f"  GROQ API Key: {config_data['groq']['api_key'][:10]}..." if config_data['groq']['api_key'] else "  GROQ API Key: Not found")
            
            return config_data
            
        except Exception as e:
            self.logger.warning(f"設定読み込みエラー: {e}, デフォルト設定を使用")
            
            # デフォルト設定（環境変数のみ）
            return {
                "openai": {
                    "api_key": os.getenv("OPENAI_API_KEY"),
                    "base_url": os.getenv("OPENAI_BASE_URL"),
                    "default_model": "gpt-4o-mini"
                },
                "anthropic": {
                    "api_key": os.getenv("ANTHROPIC_API_KEY"),
                    "default_model": "claude-3-haiku-20240307"
                },
                "groq": {
                    "api_key": os.getenv("GROQ_API_KEY"),
                    "default_model": "openai/gpt-oss-20b"
                },
                "openrouter": {
                    "api_key": os.getenv("OPENROUTER_API_KEY"),
                    "base_url": "https://openrouter.ai/api/v1",
                    "default_model": "anthropic/claude-3-5-sonnet-20241022"
                }
            }
    
    def _initialize_provider(self):
        """プロバイダーを初期化"""
        if self.provider == LLMProvider.OPENAI and OPENAI_AVAILABLE:
            if not self.config["openai"]["api_key"]:
                self.logger.warning("OpenAI API key not found")
                
        elif self.provider == LLMProvider.ANTHROPIC and ANTHROPIC_AVAILABLE:
            if not self.config["anthropic"]["api_key"]:
                self.logger.warning("Anthropic API key not found")
                
        elif self.provider == LLMProvider.GROQ:
            if not self.config["groq"]["api_key"]:
                self.logger.warning("Groq API key not found")
                
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
            elif self.provider == LLMProvider.GROQ:
                return await self._chat_groq(
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
    
    async def _chat_groq(
        self, 
        prompt: str, 
        system_prompt: Optional[str],
        model: Optional[str],
        max_tokens: int,
        temperature: float,
        **kwargs
    ) -> LLMResponse:
        """Groq APIを使用したチャット（再試行機能付き）"""
        max_retries = 3
        retry_delay = 2  # 秒
        
        for attempt in range(max_retries):
            try:
                import groq
                
                model = model or self.config["groq"]["default_model"]
                api_key = self.config["groq"]["api_key"]
                
                if not api_key:
                    raise ValueError("Groq API key not found")
                
                client = groq.Groq(api_key=api_key)
                
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})
                
                # toolsパラメーターを処理
                groq_params = {
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature
                }
                
                # toolsとtool_choiceパラメーターを追加
                if 'tools' in kwargs and kwargs['tools']:
                    groq_params['tools'] = kwargs['tools']
                    if 'tool_choice' in kwargs:
                        groq_params['tool_choice'] = kwargs['tool_choice']
                
                # その他のkwargsを追加（toolsとtool_choice以外）
                for key, value in kwargs.items():
                    if key not in ['tools', 'tool_choice']:
                        groq_params[key] = value
                
                # デバッグログ
                self.logger.info(f"Groq API パラメーター: tools={bool(groq_params.get('tools'))}, tool_choice={groq_params.get('tool_choice', 'N/A')}")
                
                # GROQクライアントは同期的なメソッドなのでawaitは不要
                response = client.chat.completions.create(**groq_params)
                
                # デバッグ: レスポンスオブジェクトの詳細をログ出力
                self.logger.info(f"Groq API レスポンスオブジェクト: {type(response)}")
                self.logger.info(f"Groq API レスポンス属性: {dir(response)}")
                self.logger.info(f"Groq API choices: {len(response.choices) if hasattr(response, 'choices') else 'N/A'}")
                
                if hasattr(response, 'choices') and len(response.choices) > 0:
                    choice = response.choices[0]
                    self.logger.info(f"Groq API choice オブジェクト: {type(choice)}")
                    self.logger.info(f"Groq API choice 属性: {dir(choice)}")
                    
                    if hasattr(choice, 'message'):
                        message = choice.message
                        self.logger.info(f"Groq API message オブジェクト: {type(message)}")
                        self.logger.info(f"Groq API message 属性: {dir(message)}")
                        self.logger.info(f"Groq API message.content: {repr(message.content)}")
                        self.logger.info(f"Groq API message.tool_calls: {getattr(message, 'tool_calls', 'N/A')}")
                    else:
                        self.logger.error("Groq API choiceにmessage属性がありません")
                else:
                    self.logger.error("Groq API responseにchoicesがありません")
                
                # ツール呼び出しとコンテンツ両方を処理
                message = response.choices[0].message
                content = message.content
                tool_calls = getattr(message, 'tool_calls', None)
                
                # コンテンツが空の場合の処理
                if not content and not tool_calls:
                    if attempt < max_retries - 1:  # 最後の試行でない場合
                        self.logger.warning(f"Groq APIから空レスポンス（試行 {attempt + 1}/{max_retries}）、{retry_delay}秒後に再試行")
                        await asyncio.sleep(retry_delay)
                        continue
                    else:
                        self.logger.error("Groq APIから空レスポンス、最大試行回数に達しました")
                        raise ValueError("Groq APIからコンテンツとツール呼び出しの両方がNoneです")
                
                # ツール呼び出しがある場合はJSON形式で返す
                if tool_calls:
                    import json
                    tool_call_data = {
                        "tool_calls": [
                            {
                                "function": {
                                    "name": tool_call.function.name,
                                    "arguments": tool_call.function.arguments
                                }
                            } for tool_call in tool_calls
                        ]
                    }
                    content = json.dumps(tool_call_data, ensure_ascii=False)
                    self.logger.info(f"Groq API ツール呼び出し受信: {len(tool_calls)}件")
                
                # デバッグ用ログ
                self.logger.info(f"Groq API レスポンス内容（文字数: {len(content) if content else 0}）: {content[:100] if content else 'None'}...")
                
                return LLMResponse(
                    content=content,
                    provider=LLMProvider.GROQ,
                    model=model,
                    tokens_used=response.usage.total_tokens if hasattr(response, 'usage') else None,
                    metadata={"response_id": response.id, "has_tool_calls": tool_calls is not None}
                )
                
            except ImportError:
                raise ImportError("Groq library not available. Install with: pip install groq")
            except Exception as e:
                if attempt < max_retries - 1:
                    self.logger.warning(f"Groq API呼び出しエラー（試行 {attempt + 1}/{max_retries}）: {e}、{retry_delay}秒後に再試行")
                    await asyncio.sleep(retry_delay)
                    continue
                else:
                    self.logger.error(f"Groq API呼び出しエラー、最大試行回数に達しました: {e}")
                    raise
    
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
        elif self.provider == LLMProvider.GROQ:
            return bool(self.config["groq"]["api_key"])
        elif self.provider == LLMProvider.OPENROUTER:
            return bool(self.config["openrouter"]["api_key"])
        return False


# デフォルトLLMクライアント
default_llm_client = LLMClient(LLMProvider.OPENAI)
