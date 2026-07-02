from companion.base.llm_client import LLMClient
from companion.config.tier_profile import (
    TIER_HIGH,
    TIER_LOW,
    TIER_MID,
    resolve_tier_profile,
)


class _FakeConfig:
    """Minimal ConfigLoader stand-in for resolver tests."""

    def __init__(self, available_models):
        self._available_models = available_models

    def get(self, key_path, default=None):
        if key_path == "llm.available_models":
            return self._available_models
        return default


def test_unspecified_model_resolves_to_low_tier() -> None:
    """A model absent from available_models (or without a tier field) must
    default to 'low' — the same conservative-default philosophy as the
    context length fallback. Assuming strength is riskier than assuming
    weakness."""
    cfg = _FakeConfig(available_models=[])

    profile = resolve_tier_profile("some/unknown-model", cfg=cfg)

    assert profile.tier == TIER_LOW


def test_model_with_explicit_tier_is_resolved() -> None:
    """A model tagged with a tier in available_models must resolve to that
    tier's defaults, not the low-tier fallback."""
    cfg = _FakeConfig(
        available_models=[
            {"name": "Claude Sonnet", "model": "claude-sonnet-4.5", "tier": TIER_HIGH}
        ]
    )

    profile = resolve_tier_profile("claude-sonnet-4.5", cfg=cfg)

    assert profile.tier == TIER_HIGH
    assert profile.checkin_interval is None  # high tier: no forced check-in
    assert profile.max_loops == 35


def test_model_entry_without_tier_field_still_defaults_to_low() -> None:
    """An available_models entry that matches by model name but omits the
    tier field must not silently inherit a stronger tier."""
    cfg = _FakeConfig(
        available_models=[{"name": "Mystery Model", "model": "mystery-model"}]
    )

    profile = resolve_tier_profile("mystery-model", cfg=cfg)

    assert profile.tier == TIER_LOW


def test_per_model_override_replaces_single_field_only() -> None:
    """A model-specific override (e.g. max_loops) must not reset the rest of
    the tier's defaults."""
    cfg = _FakeConfig(
        available_models=[
            {
                "name": "Custom",
                "model": "glm-4.5-flash",
                "tier": TIER_LOW,
                "max_loops": 6,
            }
        ]
    )

    profile = resolve_tier_profile("glm-4.5-flash", cfg=cfg)

    assert profile.tier == TIER_LOW
    assert profile.max_loops == 6
    # Untouched fields keep the low-tier default.
    assert profile.checkin_interval == 5


def test_invalid_tier_value_falls_back_to_low() -> None:
    """A malformed tier string in config must not crash or silently be
    treated as a real tier; fall back to the conservative default."""
    cfg = _FakeConfig(
        available_models=[
            {"name": "Typo", "model": "typo-model", "tier": "ultra"}
        ]
    )

    profile = resolve_tier_profile("typo-model", cfg=cfg)

    assert profile.tier == TIER_LOW


def test_tier_defaults_are_ordered_low_to_high_in_permissiveness() -> None:
    """Sanity check that low/mid/high are meaningfully different, not
    accidentally identical placeholders."""
    low = resolve_tier_profile("l", cfg=_FakeConfig([{"model": "l", "tier": TIER_LOW}]))
    mid = resolve_tier_profile("m", cfg=_FakeConfig([{"model": "m", "tier": TIER_MID}]))
    high = resolve_tier_profile(
        "h", cfg=_FakeConfig([{"model": "h", "tier": TIER_HIGH}])
    )

    assert low.max_loops <= mid.max_loops <= high.max_loops
    assert low.repo_map_token_budget <= mid.repo_map_token_budget
    assert high.checkin_interval is None
    assert low.checkin_interval is not None and mid.checkin_interval is not None


def test_llm_client_exposes_tier_profile_at_init() -> None:
    """LLMClient must resolve and expose a TierProfile as soon as it is
    constructed, so downstream components (context length, future prompt
    sizing) can read it without re-deriving tier from raw config."""
    client = LLMClient(api_key="dummy", provider="groq", model="some-untagged-model")

    assert client.tier_profile.tier == TIER_LOW


def test_llm_client_refreshes_tier_profile_on_model_switch(monkeypatch) -> None:
    """Switching models must re-resolve the tier profile, not keep the
    profile of the previously active model cached from __init__."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy")
    client = LLMClient(api_key="dummy", provider="groq", model="model-a")
    assert client.tier_profile.tier == TIER_LOW

    calls = []
    original = resolve_tier_profile

    def _spy(model_name, provider=None, cfg=None):
        calls.append(model_name)
        return original(model_name, provider=provider, cfg=cfg)

    monkeypatch.setattr(
        "companion.base.llm_client.resolve_tier_profile", _spy
    )

    ok = client.reinitialize(provider="anthropic", model="claude-sonnet-4.5")

    assert ok is True
    assert calls == ["claude-sonnet-4.5"]
