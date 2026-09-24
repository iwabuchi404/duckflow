from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml


class ConfigWriter:
    """Utility to write configuration to .env and duckflow.yaml."""

    def __init__(self, project_root: str = ".") -> None:
        self.root = Path(project_root).resolve()
        self.yaml_path = self.root / "duckflow.yaml"
        self.env_path = self.root / ".env"

    def write_env(self, key: str, value: str) -> None:
        """Write or update a key in the .env file.

        Args:
            key: Environment variable name.
            value: Environment variable value.

        Returns:
            None.
        """
        lines: list[str] = []
        if self.env_path.exists():
            with open(self.env_path, encoding="utf-8") as f:
                lines = f.readlines()

        found = False
        new_line = f"{key}={value}\n"

        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = new_line
                found = True
                break

        if not found:
            lines.append(new_line)

        with open(self.env_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

    def write_yaml(self, updates: dict[str, Any]) -> None:
        """Update duckflow.yaml with nested dictionary updates.

        Args:
            updates: Nested configuration values to merge.

        Returns:
            None.
        """
        data: dict[str, Any] = {}
        if self.yaml_path.exists():
            with open(self.yaml_path, encoding="utf-8") as f:
                try:
                    data = yaml.safe_load(f) or {}
                except yaml.YAMLError:
                    data = {}

        def deep_update(base: dict[str, Any], up: Mapping[str, Any]) -> None:
            for k, v in up.items():
                if isinstance(v, dict) and k in base and isinstance(base[k], dict):
                    deep_update(base[k], v)
                else:
                    base[k] = v

        deep_update(data, updates)

        with open(self.yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, sort_keys=False, allow_unicode=True)

    def ensure_gitignore(self) -> None:
        """Ensure .env is in .gitignore.

        Returns:
            None.
        """
        gitignore = self.root / ".gitignore"
        if gitignore.exists():
            with open(gitignore, encoding="utf-8") as f:
                content = f.read()
            if ".env" not in content:
                with open(gitignore, "a", encoding="utf-8") as f:
                    f.write("\n# Duckflow secrets\n.env\n")
        else:
            with open(gitignore, "w", encoding="utf-8") as f:
                f.write(".env\n")
