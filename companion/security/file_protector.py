"""
Phase 1 FileProtector

Rules:
- Allow read anywhere for now
- Allow create/write/delete only inside configured work_dir
- Reject dangerous extensions for write/delete
"""
from pathlib import Path
from typing import List


class FileProtector:
    def __init__(self, work_dir: str, safe_extensions: List[str]):
        self.work_dir = str(Path(work_dir).resolve())
        self.safe_extensions = safe_extensions
        self._dangerous_ext = [".exe", ".bat", ".sh", ".ps1"]

    def is_inside_workdir(self, file_path: str) -> bool:
        try:
            abs_path = str(Path(file_path).resolve())
            return abs_path.startswith(self.work_dir)
        except Exception:
            return False

    def is_safe_extension(self, file_path: str) -> bool:
        lower = file_path.lower()
        for ext in self._dangerous_ext:
            if lower.endswith(ext):
                return False
        if not any(lower.endswith(ext) for ext in self.safe_extensions):
            # If extension not explicitly safe, treat as unsafe for writes
            return False
        return True

    def check_operation(self, operation: str, file_path: str) -> bool:
        op = (operation or "").lower()
        if op in ["write", "create", "delete", "move", "copy", "mkdir"]:
            if not self.is_inside_workdir(file_path):
                return False
            if op in ["write", "create", "delete"] and not self.is_safe_extension(file_path):
                return False
            return True
        # read/list are always allowed in Phase 1
        return True


