from companion.config.config_loader import ConfigLoader


def test_config_loader_reads_top_level_agent_max_loops() -> None:
    """agent.max_loops should be read from the top-level agent section."""
    loader = ConfigLoader()
    original = loader._config
    try:
        loader._config = {
            "agent": {"max_loops": 17},
            "llm": {"agent": {"max_loops": 99}},
        }

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


def test_config_loader_reload_reloads_from_disk(tmp_path, monkeypatch) -> None:
    """reload() should discard cached config and read duckflow.yaml again."""
    package_file = tmp_path / "companion" / "config" / "config_loader.py"
    package_file.parent.mkdir(parents=True)
    package_file.write_text("", encoding="utf-8")
    config_path = tmp_path / "duckflow.yaml"
    config_path.write_text("agent:\n  max_loops: 31\n", encoding="utf-8")

    loader = ConfigLoader()
    original = loader._config
    monkeypatch.setattr("companion.config.config_loader.Path", lambda _: package_file)
    try:
        loader._config = {"agent": {"max_loops": 10}}
        loader.reload()

        assert loader.get("agent.max_loops") == 31
    finally:
        loader._config = original
