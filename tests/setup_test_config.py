from pathlib import Path
import os
import yaml

print("Setting up dummy config for tests...")
config_dir = Path("config")
config_file = config_dir / "config.yaml"
backup_file = config_dir / "config.yaml.bak"

if config_file.exists():
    print(f"Backing up existing {config_file} to {backup_file}")
    try:
        os.rename(config_file, backup_file)
    except OSError as e:
        print(f"Could not create backup, file may be in use: {e}")

config_dir.mkdir(exist_ok=True)
dummy_config = {
    "llm": {"provider": "openai", "api_key": "dummy_key"},
    "summary_llm": {"provider": "openai", "api_key": "dummy_key"},
    "approval": {"mode": "standard"}
}
with open(config_file, "w", encoding="utf-8") as f:
    yaml.dump(dummy_config, f)
print(f"Dummy config created at {config_file.resolve()}")
