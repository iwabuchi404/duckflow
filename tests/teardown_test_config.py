from pathlib import Path
import os

print("Tearing down dummy config...")
config_dir = Path("config")
config_file = config_dir / "config.yaml"
backup_file = config_dir / "config.yaml.bak"

if config_file.exists():
    try:
        os.remove(config_file)
        print("Dummy config removed.")
    except OSError as e:
        print(f"Could not remove dummy config: {e}")

if backup_file.exists():
    print(f"Restoring backup from {backup_file}")
    try:
        os.rename(backup_file, config_file)
    except OSError as e:
        print(f"Could not restore backup: {e}")
