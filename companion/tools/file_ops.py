import os
import shutil
from typing import List, Optional
from pathlib import Path

class FileOps:
    """
    File Operations with Duck Keeper Safety.
    """
    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root).resolve()

    def _is_safe_path(self, path: str) -> bool:
        """Duck Keeper: Ensure path is within workspace."""
        try:
            target_path = (self.workspace_root / path).resolve()
            return self.workspace_root in target_path.parents or target_path == self.workspace_root
        except Exception:
            return False

    def _get_full_path(self, path: str) -> Path:
        if not self._is_safe_path(path):
            raise PermissionError(f"Duck Keeper Alert: Access denied to {path} (Outside workspace)")
        return (self.workspace_root / path).resolve()

    async def read_file(self, path: str) -> str:
        """Read content of a file."""
        full_path = self._get_full_path(path)
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        if not full_path.is_file():
            raise IsADirectoryError(f"Path is a directory: {path}")
        
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()

    async def write_file(self, path: str, content: str) -> str:
        """Write content to a file. Creates directories if needed."""
        full_path = self._get_full_path(path)
        
        # Create parent directories
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        return f"Successfully wrote to {path}"

    async def list_files(self, path: str = ".") -> List[str]:
        """List files and directories in a path."""
        full_path = self._get_full_path(path)
        if not full_path.exists():
            raise FileNotFoundError(f"Path not found: {path}")
        
        results = []
        for item in full_path.iterdir():
            # Ignore hidden files/dirs (starting with .)
            if item.name.startswith("."):
                continue
                
            prefix = "[DIR] " if item.is_dir() else "[FILE]"
            rel_path = item.relative_to(self.workspace_root)
            results.append(f"{prefix} {rel_path}")
        
        return sorted(results)

    async def mkdir(self, path: str) -> str:
        """Create a directory."""
        full_path = self._get_full_path(path)
        full_path.mkdir(parents=True, exist_ok=True)
        return f"Created directory {path}"

# Global instance
file_ops = FileOps()
