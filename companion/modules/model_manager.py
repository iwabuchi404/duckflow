import os
import json
import logging
import asyncio
from typing import List, Dict, Any, Optional
from pathlib import Path
import urllib.request
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class ModelManager:
    """
    Manages LLM models, specifically fetching and caching from OpenRouter.
    """
    def __init__(self, cache_file: Optional[Path] = None):
        if cache_file:
            self.cache_file = cache_file
        else:
            # Default cache in project root or home
            self.cache_file = Path.home() / ".duckflow" / "openrouter_models.json"
        
        # Ensure directory exists
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.models: List[Dict[str, Any]] = []
        self.last_updated: Optional[datetime] = None
        self.load_cache()

    def load_cache(self) -> bool:
        """Load models from local cache file."""
        try:
            if not self.cache_file.exists():
                return False
            
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.models = data.get("models", [])
                timestamp = data.get("last_updated")
                if timestamp:
                    self.last_updated = datetime.fromisoformat(timestamp)
                return True
        except Exception as e:
            logger.error(f"Failed to load model cache: {e}")
            return False

    def save_cache(self) -> bool:
        """Save current models to local cache file."""
        try:
            data = {
                "models": self.models,
                "last_updated": self.last_updated.isoformat() if self.last_updated else None
            }
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Failed to save model cache: {e}")
            return False

    async def fetch_openrouter_models(self, force: bool = False) -> List[Dict[str, Any]]:
        """
        Fetch models from OpenRouter API.
        If force is False and cache is fresh (less than 1 day), returns cache.
        """
        # Check cache freshness (1 day)
        if not force and self.models and self.last_updated:
            if datetime.now() - self.last_updated < timedelta(days=1):
                logger.debug("Using cached OpenRouter model list")
                return self.models

        logger.info("📡 Fetching OpenRouter model list...")
        
        try:
            # Using urllib.request for minimal dependencies
            # OpenRouter models endpoint doesn't require API key for listing
            url = "https://openrouter.ai/api/v1/models"
            
            def _fetch():
                with urllib.request.urlopen(url, timeout=10) as response:
                    return json.loads(response.read().decode())

            # Run synchronous urllib in thread pool
            data = await asyncio.to_thread(_fetch)
            
            raw_models = data.get("data", [])
            processed_models = []
            
            for m in raw_models:
                # Basic info
                model_id = m.get("id")
                name = m.get("name", model_id)
                context_length = m.get("context_length", 0)
                
                # Pricing
                pricing = m.get("pricing", {})
                prompt_price = pricing.get("prompt", "0")
                completion_price = pricing.get("completion", "0")
                
                # Description
                description = m.get("description", "")
                
                processed_models.append({
                    "id": model_id,
                    "name": name,
                    "provider": "openrouter",
                    "context_length": context_length,
                    "prompt_price": prompt_price,
                    "completion_price": completion_price,
                    "description": description
                })
            
            # Sort by name
            processed_models.sort(key=lambda x: x["name"])
            
            self.models = processed_models
            self.last_updated = datetime.now()
            self.save_cache()
            
            logger.info(f"✅ Successfully fetched {len(self.models)} models from OpenRouter")
            return self.models

        except Exception as e:
            logger.error(f"Failed to fetch models from OpenRouter: {e}")
            return self.models # Return cache if fetch fails

    def get_models_for_ui(self) -> List[tuple]:
        """Format models for UI selection menu."""
        options = []
        for m in self.models:
            display = f"{m['name']} ({m['id']})"
            if m.get('context_length'):
                display += f" - [dim]{m['context_length']//1024}k context[/dim]"
            
            value = {
                "provider": "openrouter",
                "model": m['id'],
                "name": m['name']
            }
            options.append((display, value))
        return options

# Global instance
model_manager = ModelManager()
