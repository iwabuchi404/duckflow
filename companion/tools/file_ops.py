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

    async def read_file(self, path: str, start_line: int = 1, max_lines: int = 500) -> dict:
        """
        Read file content with line-based pagination.
        Use this to explore code or data. For large files, use start_line to paginate.
        
        Args:
            path: Path to the target file.
            start_line: Line number to start reading from (1-indexed).
            max_lines: Number of lines to read in this chunk (default 500).
        
        Returns:
            Dict containing 'content', 'size_bytes', and 'has_more' flag.
        """
        import itertools
        
        start_line = max(1, int(start_line))
        max_lines = max(1, int(max_lines))

        full_path = self._get_full_path(path)
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        if not full_path.is_file():
            raise IsADirectoryError(f"Path is a directory: {path}")
        
        size_bytes = os.path.getsize(full_path)
        
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                # 1-indexed to 0-indexed slce
                # islice(iterable, start, stop)
                # To read lines from start_line, we skip start_line - 1 lines.
                lines_it = itertools.islice(f, start_line - 1, start_line - 1 + max_lines)
                content_lines = list(lines_it)
                
                # Check if there is more content (has_more)
                # Next line check
                try:
                    next(f)
                    has_more = True
                except StopIteration:
                    has_more = False
            
            content = "".join(content_lines)
            
            # If empty but file exists
            if not content and start_line == 1:
                content = "(Empty file)"

            return {
                "path": path,
                "size_bytes": size_bytes,
                "showing_lines": f"{start_line}-{start_line + len(content_lines) - 1}",
                "content": content,
                "has_more": has_more
            }
            
        except UnicodeDecodeError:
            return {"error": f"File {path} is not a valid UTF-8 text file (encoding error)."}

    async def write_file(self, path: str, content: str) -> str:
        """
        Write or overwrite a file with the provided content.
        Creates parent directories automatically. 
        
        NOTE: Use a Sym-Ops content block (<<< >>>) for the 'content' parameter 
        when writing multi-line files or code.
        """
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
        """
        Perform a simple string replacement in a file.
        Replaces ALL occurrences of 'search' with 'replace'.
        Use this for quick fixes when full file rewrite is unnecessary.
        """
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
