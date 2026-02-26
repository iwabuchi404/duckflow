import os
import shutil
from typing import List, Optional
from pathlib import Path
from .hashline import HashlineHelper

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
            return ( self.workspace_root in target_path.parents or target_path == self.workspace_root or target_path.parent == self.workspace_root  ) 
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

    async def read_file(self, path: str, start: int = 1, end: int = 300) -> dict:
        """
        Read file content with hashline format for precise editing.

        Each line is prefixed with "line_number:hash|" where hash is a 3-char
        hex value computed from the line content. This enables precise, line-number-
        independent edits via edit_file.

        For large files, use start/end to paginate.

        Args:
            path: ファイルパス
            start: 開始行番号（1始まり、デフォルト: 1）
            end: 読み込む最大行数（デフォルト: 300）

        Returns:
            {
                "path": str,
                "size_bytes": int,
                "showing_lines": str,
                "content": str,  # hashline 形式
                "has_more": bool
            }
        """
        import itertools

        start_line = max(1, int(start))
        max_lines = max(1, int(end))

        full_path = self._get_full_path(path)
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        if not full_path.is_file():
            raise IsADirectoryError(f"Path is a directory: {path}")

        size_bytes = os.path.getsize(full_path)

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                # 1-indexed to 0-indexed slice
                # islice(iterable, start, stop)
                # To read lines from start_line, we skip start_line - 1 lines.
                lines_it = itertools.islice(f, start_line - 1, start_line - 1 + max_lines)
                content_lines = [line.rstrip('\n') for line in lines_it]

                # Check if there is more content (has_more)
                try:
                    next(f)
                    has_more = True
                except StopIteration:
                    has_more = False

            # hashline 形式に変換
            if content_lines:
                content = HashlineHelper.format_with_hashlines('\n'.join(content_lines))
            else:
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
        """

        full_path = self._get_full_path(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote to {path}"

    async def edit_file(self, path: str, anchors: str = "", content: str = "") -> str:
        '''
        Hashline-based file editing with precise line identification.
        Supports multi-edit via %%% segment separators.

        Uses hashline anchors (line_number:hash) to identify and replace content.
        The hash ensures the file hasn't changed since read_file was called.

        Sym-Ops format (single edit):
        ::edit_file @utils.py
        <<<
        ---
        anchors: "42:a3f 43:f10"
        ---
        def calculate_total(items: list[int]) -> int:
            """Calculate the total sum."""
            return sum(items)
        >>>

        Sym-Ops format (multi-edit using %%% separator; applied bottom-to-top):
        ::edit_file @utils.py
        <<<
        ---
        anchors: "3:abc 3:abc"
        ---
        TAX_RATE = 0.10
        %%%
        ---
        anchors: "10:def 12:ghe"
        ---
        def calculate(x):
            return x * TAX_RATE
        >>>

        Args:
            path: 対象ファイルパス
            anchors: アンカー文字列（例: "42:a3f 43:f10"）。YAML フロントマター方式の場合は省略可。
            content: 置換する新しい内容。YAML フロントマターで anchors を渡す場合はその後に本文。

        Returns:
            変更成功メッセージと、各変更箇所の更新済み hashline コンテキスト

        Raises:
            ValueError: アンカーが見つからない、またはハッシュが不一致の場合
        '''
        full_path = self._get_full_path(path)
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        if not full_path.is_file():
            raise IsADirectoryError(f"Path is a directory: {path}")

        # %%% でセグメントに分割（マルチエディットサポート）
        import re as _re
        segments_raw = _re.split(r'\n%%%', content)

        # 各セグメントから (anchors_str, body) を抽出
        # セグメント内の YAML フロントマターを解釈する
        edits: list[tuple[str, str]] = []
        for seg in segments_raw:
            seg = seg.strip('\n')
            if not seg.strip():
                continue

            # YAML フロントマター検出
            fm_match = _re.match(r'^---\n(.*?)\n---\n?(.*)', seg, _re.DOTALL)
            if fm_match:
                import yaml as _yaml
                try:
                    fm = _yaml.safe_load(fm_match.group(1))
                    seg_anchors = str(fm.get('anchors', anchors)).strip()
                    seg_body = fm_match.group(2).strip('\n')
                except Exception:
                    seg_anchors = anchors
                    seg_body = seg
            else:
                # フロントマターなし: グローバル anchors 引数を使う
                seg_anchors = anchors
                seg_body = seg.strip('\n')

            if not seg_anchors:
                raise ValueError(
                    f"No anchors provided for edit segment. "
                    f"Please specify anchors via YAML frontmatter (---\\nanchors: \"start:hash end:hash\"\\n---) "
                    f"or via the anchors= parameter."
                )
            edits.append((seg_anchors, seg_body))

        # ファイルを読み込み
        with open(full_path, "r", encoding="utf-8") as f:
            file_lines = [line.rstrip('\n') for line in f.readlines()]

        # 逆順に適用（下から上）することで行番号のズレを防ぐ
        # まず全セグメントの位置を解決し、開始行で降順ソートする
        resolved = []
        for seg_anchors, seg_body in edits:
            anchor_parts = seg_anchors.strip().split()
            if len(anchor_parts) != 2:
                raise ValueError(
                    f"Invalid anchors format: '{seg_anchors}'. "
                    f"Expected: 'start_anchor end_anchor' (e.g., '42:a3f 43:f10')"
                )
            start_anchor, end_anchor = anchor_parts
            start_idx, end_idx, _ = HashlineHelper.extract_content_block(
                file_lines, start_anchor, end_anchor
            )
            resolved.append((start_idx, end_idx, seg_body))

        # 開始行の降順（ファイル下部 → 上部）でソート
        resolved.sort(key=lambda x: x[0], reverse=True)

        # 逐次適用
        results_info = []
        for start_idx, end_idx, seg_body in resolved:
            new_lines = seg_body.split('\n')
            old_count = end_idx - start_idx + 1
            file_lines[start_idx:end_idx + 1] = new_lines
            results_info.append((start_idx, start_idx + len(new_lines) - 1, old_count, len(new_lines)))

        # 書き込み
        with open(full_path, "w", encoding="utf-8") as f:
            f.write('\n'.join(file_lines))

        # 結果サマリーと最終コンテキストを生成
        if len(results_info) == 1:
            s, e, old, new = results_info[0]
            context = HashlineHelper.format_context_after_edit(file_lines, s, e, context_lines=5)
            return (
                f"Successfully edited {path}.\n"
                f"Replaced {old} line(s) with {new} line(s).\n"
                f"--- Updated Context (for reference in next edit) ---\n"
                f"{context}\n"
                f"--- End of Context ---"
            )
        else:
            # 逆順に記録されているので表示用に正順に戻す
            results_info_asc = sorted(results_info, key=lambda x: x[0])
            summary_lines = [f"Successfully applied {len(results_info)} edits to {path}."]
            for i, (s, e, old, new) in enumerate(results_info_asc, 1):
                summary_lines.append(f"  Edit {i}: lines {s+1}-{e+1} ({old} → {new} line(s))")
            context = HashlineHelper.format_context_after_edit(
                file_lines, results_info_asc[0][0], results_info_asc[-1][1], context_lines=3
            )
            return (
                '\n'.join(summary_lines) + "\n"
                f"--- Updated Context ---\n"
                f"{context}\n"
                f"--- End of Context ---"
            )

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
            if item.name.startswith("."):
                continue
            prefix = "[DIR] " if item.is_dir() else "[FILE]"
            rel_path = item.relative_to(self.workspace_root)
            results.append(f"{prefix} {rel_path}")
        return sorted(results)

    async def mkdir(self, path: str) -> str:
        """Create a directory (mkdir -p)."""
        full_path = self._get_full_path(path)
        full_path.mkdir(parents=True, exist_ok=True)
        return f"Created directory {path}"

    async def replace_in_file(self, path: str, search: str, replace: str) -> str:
        """
        Perform a simple string replacement in a file.
        Replaces ALL occurrences of 'search' with 'replace'.
        Use this for quick fixes when full file rewrite is unnecessary.
        行番号ベースの編集には edit_file の方が信頼性が高い。

        Sym-Ops format:
        ::replace_in_file @utils.py
        <<<
        ---
        search: "old_function_name"
        replace: "new_function_name"
        ---
        >>>

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

    async def edit_lines(self, path: str, start: int, end: int, content: str, dry_run: bool = True) -> str:
        """ 
        行番号ベースのファイル編集（事前・事後検証プレビュー付き）。

        Sym-Ops format:
        ::edit_lines @utils.py
        <<<
        ---
        start: 10
        end: 12
        dry_run: false
        ---
        def new_function():
            return 42
        >>>

        Args:
            path: 編集対象ファイルパス
            start: 開始行番号（1始まり）
            end: 終了行番号（1始まり）
            content: 置換する新しい内容（複数行可）
            dry_run: Trueの場合、ファイルを変更せずプレビューのみ返す（デフォルト: True）

        Returns:
            dry_run=True: 事前プレビュー（変更予定内容）
            dry_run=False: 編集結果と事後プレビュー
        """ 
        full_path = self._get_full_path(path) 
        if not full_path.exists(): 
            raise FileNotFoundError(f"File not found: {path}")

        dry_run = str(dry_run).lower() == 'true'

        start, end = int(start), int(end)
        if start < 1 or end < start: 
            return f"Error: Invalid range {start}-{end}"
        
        with open(full_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        if start > len(lines):
            return f"Error: start ({start}) exceeds file length ({len(lines)})"
        
        # Prepare new content
        new_content_lines = [line + '\n' for line in content.split('\n')]
        old_count = min(end, len(lines)) - start + 1
        
        # --- 事前プレビュー（Pre-edit Preview） ---
        preview_start = max(1, start - 3)
        preview_end = min(len(lines), end + 3)
        
        preview_lines = []
        for i in range(preview_start, preview_end + 1):
            prefix = "!!>" if start <= i <= end else "   "
            line_content = lines[i-1].rstrip('\n')
            preview_lines.append(f"{prefix} {i:4d}| {line_content}")
        
        pre_edit_preview = "\n".join(preview_lines)
        warning_header = (
            "編集後のプレビュー (Post-edit Preview) ---\n"
            "⚠️ 注意: 行頭の ' N| ' (行番号) および '>>>' (変更箇所) は、ツールの表示用装飾です。\n"
            "実際のファイルには含まれません。次順の edit_lines や write_file では、\n"
            "これらの装飾を除去した【生データのみ】をコンテンツブロックに記述してください。\n"
        )

        if dry_run:
            # Dry run: show what would change without modifying file
            return (
                f"[DRY RUN] No changes made to {path}\n"
                f"{pre_edit_preview}\n"
                f"--- Pre-edit Preview ({preview_start}-{preview_end}) ---\n"
                f"{pre_edit_preview}\n"
                f"--- Would replace lines {start}-{end} with ---\n"
                f"{content}\n"
                f"--- End of Dry Run ---\n"
                f"To execute: edit_lines(path='{path}', start={start}, end={end}, content='...', dry_run=False)"
            )
        
        # Execute the edit
        lines[start - 1:end] = new_content_lines
        
        with open(full_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        
        # --- 事後検証プレビュー（Post-edit Preview） ---
        post_preview_start = max(1, start - 5)
        post_preview_end = min(len(lines), start + len(new_content_lines) + 5)
        
        post_preview_lines = []
        for i in range(post_preview_start, post_preview_end + 1):
            prefix = ">>>" if start <= i < start + len(new_content_lines) else "   "
            line_content = lines[i-1].rstrip('\n')
            post_preview_lines.append(f"{prefix} {i:4d}| {line_content}")
        
        post_preview_text = "\n".join(post_preview_lines)
       
        
        return (
            f"Successfully edited {path}. Replaced {old_count} lines with {len(new_content_lines)} lines.\n"
            f"--- Post-edit Preview ({post_preview_start}-{post_preview_end}) ---\n"
            f"(Note: line numbers ' N| ' and '>>>' are decorations, do not include them in edits)\n"
            f"{post_preview_text}\n"
            f"--- End of Preview ---"
        )


    async def find_files(self, pattern: str = "*", recursive: bool = True, path: str = ".") -> List[str]:
        """
        Find files matching a pattern.
        Supports wildcards like *.py, test_*.md, etc.

        Sym-Ops format (with YAML frontmatter for multiple args):
        ::find_files
        <<<
        ---
        pattern: "*.py"
        path: "companion/tools"
        recursive: true
        ---
        >>>

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
