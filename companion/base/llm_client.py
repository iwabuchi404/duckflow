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
                 timeout: Optional[float] = None):
        
        # Load provider from config
        provider = config.get("llm.provider", "groq")
        logger.info(f"🔧 Initializing LLM Client with provider: {provider}")
        
        # Load API key based on provider (priority: param > env > config)
        api_key_env_var = None  # Track which env var we're looking for
        if api_key:
            self.api_key = api_key
            logger.info(f"✅ Using API key from parameter")
        elif provider == "groq":
            api_key_env_var = "GROQ_API_KEY"
            self.api_key = os.getenv("GROQ_API_KEY")
        elif provider == "openrouter":
            api_key_env_var = "OPENROUTER_API_KEY"
            self.api_key = os.getenv("OPENROUTER_API_KEY")
        elif provider == "anthropic":
            api_key_env_var = "ANTHROPIC_API_KEY"
            self.api_key = os.getenv("ANTHROPIC_API_KEY")
        elif provider == "openai":
            api_key_env_var = "OPENAI_API_KEY"
            self.api_key = os.getenv("OPENAI_API_KEY")
        elif provider == "google":
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
        elif provider == "groq":
            self.base_url = os.getenv("GROQ_BASE_URL") or "https://api.groq.com/openai/v1"
        elif provider == "openrouter":
            self.base_url = os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1"
        elif provider == "anthropic":
            self.base_url = os.getenv("ANTHROPIC_BASE_URL") or "https://api.anthropic.com/v1"
        elif provider == "openai":
            self.base_url = os.getenv("OPENAI_BASE_URL")  # None is OK, uses default
        else:
            self.base_url = os.getenv("OPENAI_BASE_URL")
        
        # Load model from config based on provider
        if model:
            self.model = model
        else:
            # Try environment variable first, then config
            self.model = os.getenv("DUCKFLOW_MODEL") or config.get(f"llm.{provider}.model", "llama-3.3-70b-versatile")
        
        # Load timeout from config
        self.timeout = timeout or config.get("llm_timeout_seconds", 60.0)
        
        # Token usage statistics
        self.usage_stats = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cost_estimate": 0.0  # Placeholder for cost calculation
        }
        
        logger.info(f"LLM Client initialized: provider={provider}, model={self.model}, base_url={self.base_url}")

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

    async def chat(self, messages: List[Dict[str, str]], response_model: Optional[type] = None) -> Union[Dict[str, Any], ActionList]:
        """
        Send messages to LLM and get a JSON response.
        If response_model is provided, validates and returns that Pydantic model.
        """
        if self.use_mock:
            return self._mock_chat(messages, response_model)

        try:
            logger.debug(f"Sending request to {self.model} via {self.base_url or 'default'}")
            
            temperature = config.get("llm.temperature", 0.1)
            max_tokens = config.get("llm.max_output_tokens", 4096)
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            # Update usage stats
            if response.usage:
                self.usage_stats["input_tokens"] += response.usage.prompt_tokens
                self.usage_stats["output_tokens"] += response.usage.completion_tokens
                self.usage_stats["total_tokens"] += response.usage.total_tokens
            
            # Debug: Log response structure
            logger.debug(f"Response object: {response}")
            logger.debug(f"Response choices: {response.choices}")
            
            content = response.choices[0].message.content
            
            # Debug: Log content before parsing
            if not content:
                logger.error(f"Empty content received. Full response: {response.model_dump_json()}")
                logger.error(f"Message object: {response.choices[0].message}")
            
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

    def _mock_chat(self, messages: List[Dict[str, str]], response_model: Optional[type] = None) -> Union[Dict[str, Any], ActionList]:
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
        
        return self._parse_response(mock_content, response_model)

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
                
                # Map path/command from @ notation
                # IMPORTANT: Tool signatures use 'path' not 'file_path'!
                if action.path:
                    if tool_name in ("create_file", "edit_file", "read_file", "delete_file"):
                        params["path"] = action.path
                        logger.debug(f"  → Set path={action.path}")
                    elif tool_name == "run_command":
                        params["command"] = action.path
                        logger.debug(f"  → Set command={action.path}")
                    elif tool_name == "list_directory":
                        params["path"] = action.path
                        logger.debug(f"  → Set path={action.path}")
                
                # Map content
                if action.content:
                    if tool_name in ("create_file", "edit_file"):
                        params["content"] = action.content
                        logger.debug(f"  → Set content (length={len(action.content)})")
                    elif tool_name in ("response", "duck_call"):
                        params["message"] = action.content
                        logger.debug(f"  → Set message (length={len(action.content)})")
                    elif tool_name == "finish":
                        params["result"] = action.content
                        logger.debug(f"  → Set result (length={len(action.content)})")
                    elif tool_name == "propose_plan":
                        params["goal"] = action.content
                        logger.debug(f"  → Set goal (length={len(action.content)})")
                
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
