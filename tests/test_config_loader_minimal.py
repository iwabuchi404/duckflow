from companion.config.config_loader import ConfigLoader


def test_config_loader_reads_top_level_agent_max_loops() -> None:
    """agent.max_loops should be read from the top-level agent section."""
    loader = ConfigLoader()
    original = loader._config
    try:
        loader._config = {"agent": {"max_loops": 17}, "llm": {"agent": {"max_loops": 99}}}

        assert loader.get("agent.max_loops") == 17
    finally:
        loader._config = original


def test_config_loader_environment_override_takes_precedence(monkeypatch) -> None:
    """DUCKFLOW_* environment variables should override YAML config values."""
    loader = ConfigLoader()
    original = loader._config
    try:
        loader._config = {"agent": {"max_loops": 17}}
        monkeypatch.setenv("DUCKFLOW_AGENT_MAX_LOOPS", "23")

        assert loader.get("agent.max_loops") == "23"
    finally:
        loader._config = original
