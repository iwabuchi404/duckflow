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
            
            # 行番号付きで整形（LLMがedit_linesで行番号を参照できるようにする）
            numbered_lines = []
            for i, line in enumerate(content_lines, start=start_line):
                # 行番号を右寄せ（最大4桁）+ パイプ区切り
                numbered_lines.append(f"{i:4d}| {line.rstrip('\n')}")
            content = "\n".join(numbered_lines)

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
        既存ファイルを上書きする場合はユーザー承認が必要。

        NOTE: Use a Sym-Ops content block (<<< >>>) for the 'content' parameter
        when writing multi-line files or code.

        Args:
            path: 書き込み先のファイルパス（ワークスペースからの相対パス）
            content: ファイルに書き込む内容

        Returns:
            成功メッセージ "Successfully wrote to {path}"
        """
        full_path = self._get_full_path(path)
        
        # Create parent directories
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        return f"Successfully wrote to {path}"

    async def list_files(self, path: str = ".") -> List[str]:
        """
        List files and directories in a path.
        隠しファイル（.で始まるもの）は除外される。

        Args:
            path: 一覧を取得するディレクトリパス（デフォルト: "."）

        Returns:
            "[DIR] path" または "[FILE] path" 形式の文字列リスト（ソート済み）
        """
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
        """
        Create a directory.
        親ディレクトリも自動的に作成される（mkdir -p相当）。

        Args:
            path: 作成するディレクトリパス

        Returns:
            成功メッセージ "Created directory {path}"
        """
        full_path = self._get_full_path(path)
        full_path.mkdir(parents=True, exist_ok=True)
        return f"Created directory {path}"

    async def replace_in_file(self, path: str, search: str, replace: str) -> str:
        """
        Perform a simple string replacement in a file.
        Replaces ALL occurrences of 'search' with 'replace'.
        Use this for quick fixes when full file rewrite is unnecessary.
        行番号ベースの編集には edit_lines の方が信頼性が高い。

        Args:
            path: 対象ファイルパス
            search: 検索する文字列（完全一致）
            replace: 置換後の文字列

        Returns:
            置換結果メッセージ（置換件数、または一致なしの通知）
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

    async def edit_lines(self, path: str, start: int, end: int, content: str) -> str:
        """
        行番号ベースのファイル編集。指定した行範囲を新しいコンテンツで置換する。
        read_file で表示される行番号を使って編集位置を指定する。
        replace_in_file より信頼性が高い（完全一致検索が不要）。

        Args:
            path: 編集対象のファイルパス
            start: 置換開始行（1-indexed、この行を含む）
            end: 置換終了行（1-indexed、この行を含む）
            content: 置換後の新しいコンテンツ（複数行可）

        Returns:
            編集結果のサマリー
        """
        full_path = self._get_full_path(path)
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        if not full_path.is_file():
            raise IsADirectoryError(f"Path is a directory: {path}")

        # 型変換（パーサーから文字列で渡される場合がある）
        start = int(start)
        end = int(end)

        # バリデーション
        if start < 1:
            return f"Error: start must be >= 1, got {start}"
        if end < start:
            return f"Error: end ({end}) must be >= start ({start})"

        with open(full_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        total_lines = len(lines)
        if start > total_lines:
            return f"Error: start ({start}) exceeds file length ({total_lines} lines)"

        # end がファイル長を超える場合はクランプ
        end = min(end, total_lines)

        # 置換実行: lines[start-1:end] を新しいコンテンツで置き換え
        # content の末尾に改行がなければ追加
        new_lines = content.split('\n')
        new_lines = [line + '\n' for line in new_lines]

        old_section = lines[start - 1:end]
        lines[start - 1:end] = new_lines

        with open(full_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)

        old_count = end - start + 1
        new_count = len(new_lines)
        delta = new_count - old_count
        delta_str = f"+{delta}" if delta > 0 else str(delta)

        return (
            f"Edited {path}: replaced lines {start}-{end} ({old_count} lines) "
            f"with {new_count} lines ({delta_str}). "
            f"File now has {len(lines)} lines."
        )

    async def find_files(self, pattern: str = "*", recursive: bool = True, path: str = ".") -> List[str]:
        """
        Find files matching a pattern.
        Supports wildcards like *.py, test_*.md, etc.

        Args:
            pattern: ファイル名のマッチパターン（デフォルト: "*"、例: *.py, test_*.md）
            recursive: サブディレクトリも再帰的に検索するか（デフォルト: True）
            path: 検索開始ディレクトリ（デフォルト: "."、ワークスペースルートからの相対パス）

        Returns:
            マッチしたファイルの相対パスのリスト（ソート済み）
        """
        from fnmatch import fnmatch

        # 検索開始ディレクトリを決定
        start_dir = (self.workspace_root / path).resolve()
        if not start_dir.is_dir():
            # pathがファイルの場合、その親ディレクトリを検索対象にする
            start_dir = start_dir.parent

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

        search_dir(start_dir)
        return sorted(results)

    async def delete_file(self, path: str) -> str:
        """
        Delete a file. This is a dangerous operation - use with caution.
        実行前にユーザー承認が必要。ディレクトリの削除には対応しない。

        Args:
            path: 削除するファイルパス

        Returns:
            成功メッセージ "Deleted file: {path}"
        """
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
