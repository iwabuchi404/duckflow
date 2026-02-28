import os
import json
import logging
from typing import List, Dict, Any, Optional, Union
from openai import OpenAI, AsyncOpenAI, APIError
from companion.state.agent_state import ActionList, Action
from companion.config.config_loader import config
from companion.base.response_preprocessor import default_preprocessor
from companion.utils.sym_ops import SymOpsProcessor

logger = logging.getLogger(__name__)

# コンテキスト長のフォールバックテーブル（API取得失敗時に使用）
# キー: モデルIDの部分一致で検索される
CONTEXT_LENGTH_FALLBACK: Dict[str, int] = {
    # OpenAI
    'gpt-4o': 128_000,
    'gpt-4o-mini': 128_000,
    'gpt-4-turbo': 128_000,
    'gpt-4': 8_192,
    'gpt-3.5-turbo': 16_385,
    # Anthropic
    'claude-sonnet-4.5': 200_000,
    'claude-opus-4': 200_000,
    'claude-haiku-4.5': 200_000,
    'claude-3-5-sonnet': 200_000,
    'claude-3-5-haiku': 200_000,
    'claude-3-opus': 200_000,
    'claude-3-sonnet': 200_000,
    'claude-3-haiku': 200_000,
    # Google
    'gemini-2.5-pro': 1_048_576,
    'gemini-2.5-flash': 1_048_576,
    'gemini-1.5-pro': 2_097_152,
    'gemini-1.5-flash': 1_048_576,
    # Meta (Groq / OpenRouter)
    'llama-3.3-70b': 131_072,
    'llama-3.1-70b': 131_072,
    'llama-3.1-8b': 131_072,
    # GLM
    'glm-4': 128_000,
    # DeepSeek
    'deepseek-chat': 128_000,
    'deepseek-r1': 128_000,
}

# API取得もフォールバックも失敗した場合のデフォルト
DEFAULT_CONTEXT_LENGTH = 128_000


class LLMClient:
    """
    Simplified LLM Client for Duckflow v4.
    Enforces JSON mode and structured output.
    Settings are loaded from config/config.yaml.
    """
    def __init__(self, 
                 api_key: Optional[str] = None, 
                 base_url: Optional[str] = None, 
                 model: Optional[str] = None,
                 timeout: Optional[float] = None,
                 provider: Optional[str] = None):
        
        # Load provider from config or parameter
        self.provider = provider or config.get("llm.provider", "groq")
        logger.info(f"🔧 Initializing LLM Client with provider: {self.provider}")
        
        # Load API key based on provider (priority: param > env > config)
        api_key_env_var = None  # Track which env var we're looking for
        if api_key:
            self.api_key = api_key
            logger.info(f"✅ Using API key from parameter")
        elif self.provider == "groq":
            api_key_env_var = "GROQ_API_KEY"
            self.api_key = os.getenv("GROQ_API_KEY")
        elif self.provider == "openrouter":
            api_key_env_var = "OPENROUTER_API_KEY"
            self.api_key = os.getenv("OPENROUTER_API_KEY")
        elif self.provider == "anthropic":
            api_key_env_var = "ANTHROPIC_API_KEY"
            self.api_key = os.getenv("ANTHROPIC_API_KEY")
        elif self.provider == "openai":
            api_key_env_var = "OPENAI_API_KEY"
            self.api_key = os.getenv("OPENAI_API_KEY")
        elif self.provider == "google":
            api_key_env_var = "GOOGLE_API_KEY"
            self.api_key = os.getenv("GOOGLE_API_KEY")
        else:
            # Fallback: try common keys
            api_key_env_var = "OPENAI_API_KEY or GROQ_API_KEY"
            self.api_key = os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY")
        
        # Log API key status
        if api_key_env_var:
            if self.api_key:
                masked_key = self.api_key[:8] + "..." + self.api_key[-4:] if len(self.api_key) > 12 else "***"
                logger.info(f"✅ Found {api_key_env_var}: {masked_key}")
            else:
                logger.warning(f"❌ Environment variable {api_key_env_var} not found or empty")
        
        # Load base URL based on provider
        if base_url:
            self.base_url = base_url
        elif self.provider == "groq":
            self.base_url = os.getenv("GROQ_BASE_URL") or "https://api.groq.com/openai/v1"
        elif self.provider == "openrouter":
            self.base_url = os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1"
        elif self.provider == "anthropic":
            self.base_url = os.getenv("ANTHROPIC_BASE_URL") or "https://api.anthropic.com/v1"
        elif self.provider == "openai":
            self.base_url = os.getenv("OPENAI_BASE_URL")  # None is OK, uses default
        else:
            self.base_url = os.getenv("OPENAI_BASE_URL")
        
        if model:
            self.model = model
        else:
            # Try environment variable first, then config
            self.model = os.getenv("DUCKFLOW_MODEL") or config.get(f"llm.{self.provider}.model")
            
            # Additional fallback if model is still empty/None
            if not self.model:
                self.model = "llama-3.3-70b-versatile"
                logger.warning(f"Model was not set for provider {self.provider}. Falling back to default: {self.model}")
        
        # Load timeout from config
        self.timeout = timeout or config.get("llm_timeout_seconds", 60.0)
        
        # Token usage statistics
        self.usage_stats = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cost_estimate": 0.0  # Placeholder for cost calculation
        }
        
        logger.info(f"LLM Client initialized: provider={self.provider}, model={self.model}, base_url={self.base_url}")

        # Check for dummy key or empty key
        if not self.api_key or self.api_key == "dummy-key":
            logger.warning("API Key not found or is dummy. Using Mock LLM for testing.")
            self.use_mock = True
        else:
            self.use_mock = False
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout
            )
    
    def reinitialize(self, provider: Optional[str] = None, model: Optional[str] = None) -> bool:
        """
        Reinitialize the LLM client with new provider/model settings.
        
        Args:
            provider: New provider name (e.g., 'openai', 'groq', 'openrouter')
            model: New model name (e.g., 'gpt-4o', 'llama-3.3-70b-versatile')
            
        Returns:
            True if reinitialization was successful, False otherwise
        """
        try:
            # Store old values for rollback
            old_provider = self.provider
            old_model = self.model
            old_base_url = self.base_url
            old_api_key = self.api_key
            old_client = self.client if hasattr(self, 'client') else None
            old_use_mock = self.use_mock
            
            # Update provider if specified
            if provider:
                self.provider = provider
            
            # Update model if specified
            if model:
                self.model = model
            elif not self.model:
                self.model = "llama-3.3-70b-versatile"
            
            logger.info(f"🔄 Reinitializing LLM Client: provider={self.provider}, model={self.model}")
            
            # Reload API key for new provider
            api_key_env_var = None
            if self.provider == "groq":
                api_key_env_var = "GROQ_API_KEY"
                self.api_key = os.getenv("GROQ_API_KEY")
            elif self.provider == "openrouter":
                api_key_env_var = "OPENROUTER_API_KEY"
                self.api_key = os.getenv("OPENROUTER_API_KEY")
            elif self.provider == "anthropic":
                api_key_env_var = "ANTHROPIC_API_KEY"
                self.api_key = os.getenv("ANTHROPIC_API_KEY")
            elif self.provider == "openai":
                api_key_env_var = "OPENAI_API_KEY"
                self.api_key = os.getenv("OPENAI_API_KEY")
            elif self.provider == "google":
                api_key_env_var = "GOOGLE_API_KEY"
                self.api_key = os.getenv("GOOGLE_API_KEY")
            else:
                self.api_key = os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY")
            
            if not self.api_key:
                logger.error(f"❌ API key not found for provider: {self.provider} (env var: {api_key_env_var})")
                # Rollback
                self.provider = old_provider
                self.model = old_model
                self.base_url = old_base_url
                self.api_key = old_api_key
                if old_client:
                    self.client = old_client
                self.use_mock = old_use_mock
                return False
            
            # Reload base URL for new provider
            if self.provider == "groq":
                self.base_url = os.getenv("GROQ_BASE_URL") or "https://api.groq.com/openai/v1"
            elif self.provider == "openrouter":
                self.base_url = os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1"
            elif self.provider == "anthropic":
                self.base_url = os.getenv("ANTHROPIC_BASE_URL") or "https://api.anthropic.com/v1"
            elif self.provider == "openai":
                self.base_url = os.getenv("OPENAI_BASE_URL")
            else:
                self.base_url = os.getenv("OPENAI_BASE_URL")
            
            # Create new client
            self.use_mock = False
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout
            )
            
            logger.info(f"✅ LLM Client reinitialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to reinitialize LLM client: {e}")
            # Rollback on error
            self.provider = old_provider
            self.model = old_model
            self.base_url = old_base_url
            self.api_key = old_api_key
            if old_client:
                self.client = old_client
            self.use_mock = old_use_mock
            return False
    
    async def test_connection(self) -> bool:
        """
        Test the connection to the LLM API with a simple request.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            if self.use_mock:
                return True
            
            logger.info("🔍 Testing LLM connection...")
            test_messages = [{"role": "user", "content": "ping"}]
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=test_messages,
                temperature=0.1,
                max_tokens=10,
            )
            
            if response and response.choices:
                logger.info("✅ Connection test successful")
                return True
            else:
                logger.error("❌ Connection test failed: No response")
                return False
                
        except Exception as e:
            logger.error(f"❌ Connection test failed: {e}")
            return False

    async def get_context_length(self) -> int:
        """
        モデルのコンテキスト長を取得する。

        取得優先順位:
            1. OpenRouter API（/api/v1/models でモデル一覧から検索）
            2. フォールバックテーブル（CONTEXT_LENGTH_FALLBACK）
            3. デフォルト値（DEFAULT_CONTEXT_LENGTH = 128,000）

        Returns:
            コンテキスト長（トークン数）
        """
        # 1. OpenRouter APIから取得を試みる
        if self.provider == 'openrouter' and self.api_key:
            try:
                import httpx
                async with httpx.AsyncClient(timeout=10.0) as http:
                    resp = await http.get(
                        'https://openrouter.ai/api/v1/models',
                        headers={'Authorization': f'Bearer {self.api_key}'}
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        models = data.get('data', [])
                        for m in models:
                            if m.get('id') == self.model:
                                ctx = m.get('context_length', 0)
                                if ctx > 0:
                                    logger.info(
                                        f"Context length from OpenRouter API: "
                                        f"{self.model} = {ctx:,} tokens"
                                    )
                                    return ctx
                        logger.warning(
                            f"Model {self.model} not found in OpenRouter models list"
                        )
                    else:
                        logger.warning(
                            f"OpenRouter /models API returned {resp.status_code}"
                        )
            except Exception as e:
                logger.warning(f"Failed to fetch context length from OpenRouter: {e}")

        # 2. フォールバックテーブルから部分一致検索
        model_lower = self.model.lower()
        for key, length in CONTEXT_LENGTH_FALLBACK.items():
            if key in model_lower:
                logger.info(
                    f"Context length from fallback table: "
                    f"{self.model} matched '{key}' = {length:,} tokens"
                )
                return length

        # 3. デフォルト値
        logger.warning(
            f"Context length unknown for {self.model}, "
            f"using default: {DEFAULT_CONTEXT_LENGTH:,} tokens"
        )
        return DEFAULT_CONTEXT_LENGTH

    async def chat(self, messages: List[Dict[str, str]], response_model: Optional[type] = None, temperature: Optional[float] = None, raw: bool = False) -> Union[Dict[str, Any], ActionList, str]:
        """
        Send messages to LLM and get a JSON response.
        If response_model is provided, validates and returns that Pydantic model.
        Supports prompt caching for OpenRouter and Anthropic.
        """
        if self.use_mock:
            return self._mock_chat(messages, response_model, raw=raw)

        # 1. プロバイダーに応じてメッセージを調整（キャッシュマーカーの処理）
        processed_messages = []
        supports_caching = self.provider in ["openrouter", "anthropic", "deepseek"]
        
        for msg in messages:
            m = msg.copy()
            if "cache_control" in m and not supports_caching:
                # キャッシュ非対応プロバイダー（OpenAI純正等）の場合はマーカーを削除
                del m["cache_control"]
            processed_messages.append(m)

        # 2. 追加のヘッダー（OpenRouter用）
        extra_headers = {}
        if self.provider == "openrouter":
            extra_headers["HTTP-Referer"] = "https://github.com/duckflow/duckflow"
            extra_headers["X-Title"] = "Duckflow Agent"

        MAX_EMPTY_RETRIES = 2

        try:
            logger.debug(f"Sending request to {self.model} via {self.base_url or 'default'}")

            if temperature is None:
                temperature = config.get("llm.temperature", 0.7)
            max_tokens = config.get("llm.max_output_tokens", 4096)
            
            content = None
            for attempt in range(1, MAX_EMPTY_RETRIES + 2):
                # OpenAI SDKを使用してリクエスト送信
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=processed_messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    extra_headers=extra_headers
                )

                # Update usage stats
                if response.usage:
                    self.usage_stats["input_tokens"] += response.usage.prompt_tokens
                    self.usage_stats["output_tokens"] += response.usage.completion_tokens
                    self.usage_stats["total_tokens"] += response.usage.total_tokens
                    
                    # キャッシュヒット情報をログに記録（OpenRouter/Anthropic拡張）
                    if hasattr(response.usage, 'extra_fields'):
                        # OpenRouter might put cache info here
                        pass
                    
                    # Log caching info if available in response
                    usage_dict = response.usage.model_dump()
                    cache_read = usage_dict.get("prompt_tokens_details", {}).get("cached_tokens", 0)
                    if cache_read > 0:
                        logger.info(f"🚀 Prompt Cache Hit: {cache_read:,} tokens")

                content = response.choices[0].message.content

                if content:
                    break  # 正常なレスポンスを取得

                # 空レスポンス: リトライ可能ならリトライ
                logger.warning(
                    f"Empty response from LLM (attempt {attempt}/{MAX_EMPTY_RETRIES + 1}). "
                    f"Model: {self.model}"
                )
                if attempt <= MAX_EMPTY_RETRIES:
                    import asyncio as _asyncio
                    await _asyncio.sleep(1.0)  # 短いバックオフ
                    # temperatureを少し上げてリトライ（同じ空出力を避ける）
                    temperature = min(temperature + 0.1, 1.0)
                    logger.info(f"Retrying with temperature={temperature:.1f}...")
                else:
                    logger.error(f"Empty content after {attempt} attempts. Full response: {response.model_dump_json()}")
                    logger.error(f"Message object: {response.choices[0].message}")

            if raw:
                return content

            return self._parse_response(content, response_model)

        except APIError as e:
            logger.error(f"LLM API Error: {e}")
            # Return an error action to notify the user
            error_msg = f"LLM API Error ({e.code}): {e.message}"
            return ActionList(
                reasoning="An error occurred while communicating with the LLM API.",
                actions=[
                    Action(
                        name="response",
                        parameters={"message": f"⚠️ {error_msg}"},
                        thought="Reporting API error to user."
                    )
                ]
            )
        except Exception as e:
            logger.error(f"Unexpected error in LLMClient: {e}")
            error_msg = f"Unexpected Error: {str(e)}"
            return ActionList(
                reasoning="An unexpected error occurred.",
                actions=[
                    Action(
                        name="response",
                        parameters={"message": f"⚠️ {error_msg}"},
                        thought="Reporting unexpected error to user."
                    )
                ]
            )

    def _mock_chat(self, messages: List[Dict[str, str]], response_model: Optional[type] = None, raw: bool = False) -> Union[Dict[str, Any], ActionList, str]:
        """Generate a mock response for testing."""
        logger.info("🦆 [MOCK] Generating response...")
        
        # Simple heuristic mock
        last_msg = messages[-1]['content'].lower()
        
        # Check if we're being asked for a PlanProposal (contains "steps")
        if response_model and "PlanProposal" in str(response_model):
            mock_content = json.dumps({
                "steps": [
                    {"title": "Mock Step 1", "description": "This is a mock step for testing"},
                    {"title": "Mock Step 2", "description": "Another mock step"},
                    {"title": "Mock Step 3", "description": "Final mock step"}
                ]
            })
        # Check if we're being asked for a TaskListProposal (contains "tasks")
        elif response_model and "TaskListProposal" in str(response_model):
            mock_content = json.dumps({
                "tasks": [
                    {"title": "Mock Task 1", "description": "First mock task"},
                    {"title": "Mock Task 2", "description": "Second mock task"}
                ]
            })
        # Check if we're being asked for an ExecutionSummary (contains "summary")
        elif response_model and "ExecutionSummary" in str(response_model):
            mock_content = json.dumps({
                "summary": "This is a mock execution summary. All tasks were processed according to the plan.",
                "highlights": [
                    "Successfully completed primary tasks",
                    "No critical errors encountered",
                    "Performance was within expected limits"
                ],
                "next_steps": "Proceed to the next phase of the project."
            })
        # Default ActionList response
        else:
            mock_content = json.dumps({
                "reasoning": "I am running in MOCK mode because no API key was found. I will respond to the user.",
                "actions": [
                    {
                        "name": "response",
                        "parameters": {
                            "message": "I am currently running in MOCK mode (No API Key found). I cannot generate real intelligence, but I can test the loop! 🦆"
                        },
                        "thought": "Informing the user about mock mode."
                    }
                ]
            })
        
        if raw:
            return mock_content
            
        return self._parse_response(mock_content, response_model)

    @staticmethod
    def _parse_replace_content(content: str, params: dict) -> None:
        """
        replace_in_file のコンテンツブロックから search/replace を抽出する。

        対応フォーマット:
        1. search=... replace=... （インラインパラメータ、既にparamsにある場合）
        2. コンテンツブロック内のキーワード形式:
           search: old_text
           replace: new_text
        3. 2行だけの場合: 1行目=search, 2行目=replace

        Args:
            content: コンテンツブロックのテキスト
            params: 既存のパラメータ辞書（search/replaceが追加される）
        """
        import re

        # 既にインラインパラメータで渡されている場合はスキップ
        if 'search' in params and 'replace' in params:
            return

        # フォーマット1: search="..." replace="..." パターン
        search_match = re.search(r'search\s*=\s*"([^"]*)"', content)
        replace_match = re.search(r'replace\s*=\s*"([^"]*)"', content)
        if search_match and replace_match:
            params['search'] = search_match.group(1)
            params['replace'] = replace_match.group(1)
            return

        # フォーマット1b: クォートなし search=... replace=...
        search_match = re.search(r'search\s*=\s*(.+?)(?:\s+replace\s*=|$)', content, re.DOTALL)
        replace_match = re.search(r'replace\s*=\s*(.+)', content, re.DOTALL)
        if search_match and replace_match:
            params['search'] = search_match.group(1).strip()
            params['replace'] = replace_match.group(1).strip()
            return

        # フォーマット2: 2行のみ → 1行目=search, 2行目=replace
        lines = content.strip().split('\n')
        if len(lines) == 2:
            params['search'] = lines[0]
            params['replace'] = lines[1]
            return

        # フォールバック: content全体をsearchに、replaceは空文字
        logger.warning(f"Could not parse replace_in_file content: {content[:100]}")
        params['search'] = content
        params['replace'] = ''

    def _parse_response(self, content: str, response_model: Optional[type] = None):
        if not content:
            logger.error(f"Empty response from LLM. Content type: {type(content)}, Content value: {repr(content)}")
            raise ValueError("Empty response from LLM")

        logger.info(f"📥 Raw LLM Response (FULL):\n{content}")
        logger.info(f"📏 Response length: {len(content)} chars")
        
        processor = SymOpsProcessor()
        
        try:
            # Process with Sym-Ops (Auto-Repair -> Fuzzy Parse)
            result = processor.process(content)
            
            # Log warnings if any
            if result.warnings:
                for warning in result.warnings:
                    logger.warning(f"⚠️ Sym-Ops Warning: {warning}")
            
            logger.info(f"✅ Successfully parsed Sym-Ops format. Actions: {len(result.actions)}")
            
            # Convert to ActionList (Internal Model)
            actions = []
            for action in result.actions:
                # Map Sym-Ops action to internal Action model
                
                # Determine tool name and params
                tool_name = action.type
                params = action.params.copy() if action.params else {}
                
                logger.debug(f"🔍 Mapping action: type={tool_name}, path={action.path}, content_len={len(action.content) if action.content else 0}")
                
                # --- Sym-Ops → parameters マッピング ---
                # 特殊ルール: @target が "path" 以外のパラメータ名にマップされるツール
                # デフォルト: @target → params["path"]
                _TARGET_PARAM = {
                    "run_command":        "command",
                    "investigate":        "reason",
                    "submit_hypothesis":  "hypothesis",
                    "finish_investigation": "conclusion",
                    "search_archives":    "query",
                    "recall":             "query",
                    "note":               "message",
                    "response":           "message",
                    "report":             "message",
                    "duck_call":          "message",
                    "finish":             "result",
                }
                # 特殊ルール: <<<content>>> が "content" 以外のパラメータ名にマップされるツール
                # デフォルト: <<<content>>> → params["content"]
                _CONTENT_PARAM = {
                    "run_command":        "command",
                    "investigate":        "reason",
                    "submit_hypothesis":  "hypothesis",
                    "finish_investigation": "conclusion",
                    "search_archives":    "query",
                    "recall":             "query",
                    "note":               "message",
                    "response":           "message",
                    "report":             "message",
                    "duck_call":          "message",
                    "finish":             "result",
                    "propose_plan":       "goal",
                }

                # @target マッピング
                if action.path:
                    if tool_name == "read_file":
                        # 拡張構文: "path 1 500" → path, start=1, end=500
                        parts = action.path.split()
                        params["path"] = parts[0]
                        if len(parts) >= 2 and parts[1].isdigit():
                            params["start"] = int(parts[1])
                        if len(parts) >= 3 and parts[2].isdigit():
                            params["end"] = int(parts[2])
                    elif tool_name == "mark_task_complete":
                        # @0, @1 などを task_index に変換
                        try:
                            params["task_index"] = int(action.path)
                        except (ValueError, TypeError):
                            logger.warning(f"Could not parse task_index from path: {action.path!r}")
                            params["task_index"] = 0
                    else:
                        # デフォルト or 特殊マップから解決
                        param_name = _TARGET_PARAM.get(tool_name, "path")
                        params[param_name] = action.path
                    logger.debug(f"  → Set @target: {params}")

                # <<<content>>> マッピング
                if action.content:
                    if tool_name == "replace_in_file":
                        # YAML 風フォーマットから search/replace を抽出
                        self._parse_replace_content(action.content, params)
                        logger.debug(f"  → Parsed replace_in_file: search={params.get('search', '')[:30]}, replace={params.get('replace', '')[:30]}")
                    elif tool_name == "mark_task_complete":
                        # @target で処理済み。content ブロックは無視
                        if "task_index" not in params:
                            logger.warning("Sym-Ops: 'mark_task_complete' missing @index. Defaulting to 0.")
                            params["task_index"] = 0
                    else:
                        # デフォルト or 特殊マップから解決
                        param_name = _CONTENT_PARAM.get(tool_name, "content")
                        params[param_name] = action.content
                        logger.debug(f"  → Set content → {param_name} (length={len(action.content)})")
                                
                logger.debug(f"  → Final params: {list(params.keys())}")
                
                actions.append(Action(
                    name=tool_name,
                    parameters=params,
                    thought=f"Confidence: {action.confidence}"
                ))
            
            # Construct ActionList
            # Join thoughts for reasoning
            reasoning = "\n".join(result.thoughts) if result.thoughts else "No reasoning provided."
            
            action_list = ActionList(
                reasoning=reasoning,
                actions=actions,
                vitals=result.vitals
            )
            
            return action_list

        except Exception as e:
            logger.error(f"Failed to parse Sym-Ops response: {e}")
            # Fallback to raw text response
            logger.info("⚠️ Applying Raw Text Fallback: Treating content as 'response' action.")
            return ActionList(
                reasoning="[FALLBACK] The LLM returned raw text that could not be parsed even with Sym-Ops.",
                actions=[
                    Action(
                        name="response",
                        parameters={"message": content},
                        thought="Fallback for raw text response"
                    )
                ]
            )

# Global instance for convenience
default_client = LLMClient()


# Default client instance
_default_client_instance = None

def get_default_client() -> LLMClient:
    """
    Get or create a default LLM client instance.
    Creates a new instance each time to ensure latest config is used.
    """
    global _default_client_instance
    if _default_client_instance is None:
        _default_client_instance = LLMClient()
    return LLMClient()


# For backward compatibility: expose default_client as a property
class _DefaultClientGetter:
    """Allows accessing default_client as a dynamic getter."""
    def __call__(self):
        return get_default_client()

    def __getattr__(self, name):
        return getattr(get_default_client(), name)

    def __init__(self):
        # For backward compatibility with isintance checks
        pass


# For backward compatibility: expose default_client at module level
_default_client = _DefaultClientGetter()
