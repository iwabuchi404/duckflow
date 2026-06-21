"""
Tests for companion/modules/model_manager.py

ModelManager handles OpenRouter model list caching.
These tests exercise cache load/save and UI formatting without network access.
"""

import json
from datetime import datetime
from pathlib import Path

from companion.modules.model_manager import ModelManager


class TestModelManagerInit:
    def test_creates_cache_directory(self, tmp_path: Path) -> None:
        cache = tmp_path / "sub" / "models.json"
        ModelManager(cache_file=cache)
        assert cache.parent.exists()

    def test_default_models_empty(self, tmp_path: Path) -> None:
        cache = tmp_path / "models.json"
        mm = ModelManager(cache_file=cache)
        assert mm.models == []
        assert mm.last_updated is None


class TestLoadCache:
    def test_load_nonexistent_returns_false(self, tmp_path: Path) -> None:
        cache = tmp_path / "does_not_exist.json"
        mm = ModelManager(cache_file=cache)
        assert mm.load_cache() is False

    def test_load_valid_cache(self, tmp_path: Path) -> None:
        cache = tmp_path / "models.json"
        data = {
            "models": [
                {
                    "id": "openai/gpt-4",
                    "name": "GPT-4",
                    "provider": "openrouter",
                    "context_length": 8192,
                    "prompt_price": "0.03",
                    "completion_price": "0.06",
                    "description": "GPT-4 model",
                }
            ],
            "last_updated": "2026-06-20T12:00:00",
        }
        cache.write_text(json.dumps(data))
        mm = ModelManager(cache_file=cache)
        assert len(mm.models) == 1
        assert mm.models[0]["id"] == "openai/gpt-4"
        assert mm.last_updated is not None

    def test_load_cache_without_timestamp(self, tmp_path: Path) -> None:
        cache = tmp_path / "models.json"
        data = {"models": [{"id": "test"}], "last_updated": None}
        cache.write_text(json.dumps(data))
        mm = ModelManager(cache_file=cache)
        assert len(mm.models) == 1
        assert mm.last_updated is None

    def test_load_corrupt_json_returns_false(self, tmp_path: Path) -> None:
        cache = tmp_path / "models.json"
        cache.write_text("not json at all {{{")
        mm = ModelManager(cache_file=cache)
        # corrupt file → load_cache during __init__ fails → models stays empty
        assert mm.models == []


class TestSaveCache:
    def test_save_and_reload(self, tmp_path: Path) -> None:
        cache = tmp_path / "models.json"
        mm = ModelManager(cache_file=cache)
        mm.models = [
            {
                "id": "anthropic/claude-3",
                "name": "Claude 3",
                "provider": "openrouter",
                "context_length": 200000,
                "prompt_price": "0.01",
                "completion_price": "0.03",
                "description": "Claude 3 model",
            }
        ]
        mm.last_updated = datetime(2026, 6, 20, 10, 0, 0)
        assert mm.save_cache() is True

        mm2 = ModelManager(cache_file=cache)
        assert len(mm2.models) == 1
        assert mm2.models[0]["id"] == "anthropic/claude-3"
        assert mm2.last_updated is not None

    def test_save_without_timestamp(self, tmp_path: Path) -> None:
        cache = tmp_path / "models.json"
        mm = ModelManager(cache_file=cache)
        mm.models = [{"id": "x"}]
        mm.last_updated = None
        assert mm.save_cache() is True


class TestGetModelsForUI:
    def test_empty_models_returns_empty(self, tmp_path: Path) -> None:
        cache = tmp_path / "models.json"
        mm = ModelManager(cache_file=cache)
        assert mm.get_models_for_ui() == []

    def test_format_with_context_length(self, tmp_path: Path) -> None:
        cache = tmp_path / "models.json"
        mm = ModelManager(cache_file=cache)
        mm.models = [{"id": "openai/gpt-4", "name": "GPT-4", "context_length": 8192}]
        options = mm.get_models_for_ui()
        assert len(options) == 1
        display, value = options[0]
        assert "GPT-4" in display
        assert "8k context" in display
        assert value["model"] == "openai/gpt-4"
        assert value["provider"] == "openrouter"

    def test_format_without_context_length(self, tmp_path: Path) -> None:
        cache = tmp_path / "models.json"
        mm = ModelManager(cache_file=cache)
        mm.models = [{"id": "test/model", "name": "Test", "context_length": 0}]
        options = mm.get_models_for_ui()
        display, _ = options[0]
        assert "context" not in display
