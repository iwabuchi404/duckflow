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

    def set_workspace_root(self, path: str):
        """Set the workspace root directory."""
        self.workspace_root = Path(path).resolve()
        if not self.workspace_root.exists():
            self.workspace_root.mkdir(parents=True, exist_ok=True)
        print(f"📂 Workspace set to: {self.workspace_root}")

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

    def file_exists(self, path: str) -> bool:
        """Check if a file exists within the workspace."""
        try:
            return self._get_full_path(path).exists()
        except Exception:
            return False

    async def read_file(self, path: str, start_line: int = 1, max_lines: int = 500) -> str:
        """
        Read content of a file with line-based pagination.
        
        Args:
            path: Path to the file
            start_line: Line number to start from (1-indexed, default: 1)
            max_lines: Maximum number of lines to read (default: 500)
        """
        # Ensure types and validate
        start_line = max(1, int(start_line))  # Ensure at least 1
        max_lines = max(1, int(max_lines))    # Ensure at least 1

        full_path = self._get_full_path(path)
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        if not full_path.is_file():
            raise IsADirectoryError(f"Path is a directory: {path}")
        
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            total_lines = len(lines)
            
            # Handle empty file
            if total_lines == 0:
                return f"<FILE_CONTENT path='{path}' total_lines='0' showing_lines='0-0'>\n(Empty file)\n</FILE_CONTENT>"
            
            # Calculate indices (convert to 0-indexed)
            start_idx = start_line - 1
            
            # Handle out of range start_line
            if start_idx >= total_lines:
                return f"<FILE_CONTENT path='{path}' total_lines='{total_lines}' showing_lines='0-0'>\nError: start_line {start_line} exceeds total lines ({total_lines}). Use start_line between 1 and {total_lines}.\n</FILE_CONTENT>"
            
            end_idx = min(start_idx + max_lines, total_lines)
            
            selected_lines = lines[start_idx:end_idx]
            content = "".join(selected_lines)
            
            actual_end_line = start_line + len(selected_lines) - 1
            
            response = [
                f"<FILE_CONTENT path='{path}' total_lines='{total_lines}' showing_lines='{start_line}-{actual_end_line}'>",
                content,
                "</FILE_CONTENT>"
            ]
            
            # Add warning if there is more content
            if end_idx < total_lines:
                remaining_lines = total_lines - end_idx
                next_start = end_idx + 1
                response.append(
                    f"\n<WARNING>File has more content. {remaining_lines} lines remaining (lines {next_start}-{total_lines}). "
                    f"Use read_file(path='{path}', start_line={next_start}) to read the next chunk.</WARNING>"
                )
            
            return "\n".join(response)
            
        except UnicodeDecodeError:
            return f"Error: File {path} is not a valid UTF-8 text file (encoding error)."

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

    async def replace_in_file(self, path: str, search: str, replace: str) -> str:
        """Replace text in a file. Replaces all occurrences of search with replace."""
        full_path = self._get_full_path(path)
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        if not full_path.is_file():
            raise IsADirectoryError(f"Path is a directory: {path}")
        
        # Read current content
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Count occurrences
        count = content.count(search)
        if count == 0:
            return f"No occurrences of '{search}' found in {path}"
        
        # Replace
        new_content = content.replace(search, replace)
        
        # Write back
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        
        return f"Replaced {count} occurrence(s) of '{search}' in {path}"

    async def find_files(self, pattern: str = "*", recursive: bool = True) -> List[str]:
        """
        Find files matching a pattern.
        Supports wildcards like *.py, test_*.md, etc.
        """
        from fnmatch import fnmatch
        
        results = []
        
        def search_dir(directory: Path, depth: int = 0):
            if depth > 10:  # Prevent infinite recursion
                return
            
            try:
                for item in directory.iterdir():
                    # Skip hidden files/dirs
                    if item.name.startswith("."):
                        continue
                    
                    # Check if it's within workspace
                    try:
                        rel_path = item.relative_to(self.workspace_root)
                    except ValueError:
                        continue  # Outside workspace
                    
                    # Match files
                    if item.is_file() and fnmatch(item.name, pattern):
                        results.append(str(rel_path))
                    
                    # Recurse into directories
                    if item.is_dir() and recursive:
                        search_dir(item, depth + 1)
            except PermissionError:
                pass  # Skip directories we can't access
        
        search_dir(self.workspace_root)
        return sorted(results)

    async def delete_file(self, path: str) -> str:
        """Delete a file. This is a dangerous operation - use with caution."""
        full_path = self._get_full_path(path)
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        if full_path.is_dir():
            raise IsADirectoryError(f"Path is a directory. Use delete_directory instead: {path}")
        
        # Delete the file
        full_path.unlink()
        return f"Deleted file: {path}"

# Global instance
file_ops = FileOps()
