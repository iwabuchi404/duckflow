"""Provider-specific configuration resolution for LLM clients.

Centralises the mapping from provider name to environment variable names
and default base URLs so that ``LLMClient.__init__`` and ``reinitialize``
no longer duplicate lengthy if/elif chains.
"""

import logging
import os

logger = logging.getLogger(__name__)

# provider -> (env-var name for the API key, default base URL or None)
_PROVIDER_REGISTRY: dict[str, tuple[str, str | None]] = {
    "groq": ("GROQ_API_KEY", "https://api.groq.com/openai/v1"),
    "openrouter": ("OPENROUTER_API_KEY", "https://openrouter.ai/api/v1"),
    "anthropic": ("ANTHROPIC_API_KEY", "https://api.anthropic.com/v1"),
    "openai": ("OPENAI_API_KEY", None),
    "google": ("GOOGLE_API_KEY", None),
}

# provider -> env-var name for a custom base-URL override
_BASE_URL_ENV: dict[str, str] = {
    "groq": "GROQ_BASE_URL",
    "openrouter": "OPENROUTER_BASE_URL",
    "anthropic": "ANTHROPIC_BASE_URL",
    "openai": "OPENAI_BASE_URL",
}


def resolve_api_key(provider: str) -> tuple[str | None, str]:
    """Look up the API key for *provider* from the environment.

    Args:
        provider: Provider identifier (e.g. ``"openai"``, ``"groq"``).

    Returns:
        ``(api_key_value_or_None, env_var_name_used_for_lookup)``
    """
    entry = _PROVIDER_REGISTRY.get(provider)
    if entry is not None:
        env_var, _ = entry
        return os.getenv(env_var), env_var

    # Unknown provider: try common fallback keys
    key = os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY")
    return key, "OPENAI_API_KEY or GROQ_API_KEY"


def resolve_base_url(provider: str) -> str | None:
    """Return the base URL for *provider*, respecting env-var overrides.

    Args:
        provider: Provider identifier (e.g. ``"openai"``, ``"groq"``).

    Returns:
        The resolved base URL, or ``None`` when the SDK default should be used.
    """
    env_var = _BASE_URL_ENV.get(provider)
    env_override = os.getenv(env_var) if env_var else None
    if env_override:
        return env_override

    entry = _PROVIDER_REGISTRY.get(provider)
    if entry is not None:
        _, default_url = entry
        return default_url

    # Unknown provider: fall back to OpenAI env-var or None
    return os.getenv("OPENAI_BASE_URL")
