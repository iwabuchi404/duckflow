import pytest

from companion.base.llm_client import LLMClient, CONTEXT_LENGTH_FALLBACK
from companion.config.tier_profile import TIER_LOW, _TIER_DEFAULTS


@pytest.mark.asyncio
async def test_unknown_model_uses_conservative_default() -> None:
    """Weak/local models absent from the fallback table must not be
    over-estimated as large-context (previously defaulted to 128K).

    An untagged model resolves to the low tier, so the default should match
    the low tier's conservative unknown_model_context_length (16K), not a
    flat global default.
    """
    client = LLMClient(api_key="dummy", provider="groq", model="totally-unknown-model")

    ctx_len = await client.get_context_length()

    expected = _TIER_DEFAULTS[TIER_LOW].unknown_model_context_length
    assert ctx_len == expected
    assert expected <= 32_000
    assert client.context_length_source == "default"


@pytest.mark.asyncio
async def test_known_model_uses_fallback_table() -> None:
    """A model present in the fallback table should not fall through to the
    conservative default."""
    client = LLMClient(api_key="dummy", provider="groq", model="claude-haiku-4.5")

    ctx_len = await client.get_context_length()

    assert ctx_len == CONTEXT_LENGTH_FALLBACK["claude-haiku-4.5"]
    assert client.context_length_source == "fallback"
