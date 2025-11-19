import os
import json
import logging
from typing import List, Dict, Any, Optional, Union
from openai import OpenAI, AsyncOpenAI, APIError
from companion.state.agent_state import ActionList, Action
from companion.config.config_loader import config

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
        
        # Load API key (priority: param > env > config)
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY")
        
        # Load base URL
        if provider == "groq":
            self.base_url = base_url or os.getenv("GROQ_BASE_URL") or "https://api.groq.com/openai/v1"
        else:
            self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        
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
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.1, # Low temperature for deterministic actions
            )

            # Update usage stats
            if response.usage:
                self.usage_stats["input_tokens"] += response.usage.prompt_tokens
                self.usage_stats["output_tokens"] += response.usage.completion_tokens
                self.usage_stats["total_tokens"] += response.usage.total_tokens
            
            content = response.choices[0].message.content
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
            raise ValueError("Empty response from LLM")

        logger.debug(f"Raw LLM Response: {content}")

        # Parse JSON
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {content}")
            raise ValueError(f"LLM did not return valid JSON: {e}")

        # Validate with Pydantic if model provided
        if response_model:
            try:
                return response_model.model_validate(data)
            except Exception as e:
                logger.error(f"Pydantic validation failed: {e}")
                raise ValueError(f"Response did not match expected schema: {e}")
        
        return data

# Global instance for convenience
default_client = LLMClient()
