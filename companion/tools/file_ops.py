import os
import re
import shutil
from typing import List, Optional
from pathlib import Path
import yaml
from .hashline import HashlineHelper

# find_files / grep_files のディレクトリ走査で除外するノイズディレクトリ。
# ドット始まり（.git, .venv 等）以外にも、ビルド成果物やキャッシュ等
# テキスト検索の対象として無意味、かつ .pyc のようなバイナリノイズの
# 発生源になるディレクトリ名を明示的に除外する。
NOISE_DIR_NAMES = frozenset(
    {
        "__pycache__",
        "node_modules",
        "dist",
        "build",
        "egg-info",
    }
)


def _is_noise_dir_name(name: str) -> bool:
    """Return whether a directory name should be skipped during file search.

    Args:
        name: Directory name to check.

    Returns:
        True when the directory is a known cache/build artifact directory.
    """
    return name in NOISE_DIR_NAMES or name.endswith(".egg-info")


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
            return (
                self.workspace_root in target_path.parents
                or target_path == self.workspace_root
                or target_path.parent == self.workspace_root
            )
        except Exception:
            return False

    def _get_full_path(self, path: str) -> Path:
        if not self._is_safe_path(path):
            raise PermissionError(
                f"Duck Keeper Alert: Access denied to {path} (Outside workspace)"
            )
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
                lines_it = itertools.islice(
                    f, start_line - 1, start_line - 1 + max_lines
                )
                content_lines = [line.rstrip("\n") for line in lines_it]

                # Check if there is more content (has_more)
                try:
                    next(f)
                    has_more = True
                except StopIteration:
                    has_more = False

            # 行番号付き形式に変換（ハッシュは除外して読みやすくする）
            if content_lines:
                content = HashlineHelper.format_with_hashlines(
                    "\n".join(content_lines), start_line=start_line, include_hash=False
                )
            else:
                content = "(Empty file)"

            return {
                "path": path,
                "size_bytes": size_bytes,
                "showing_lines": f"{start_line}-{start_line + len(content_lines) - 1}",
                "content": content,
                "has_more": has_more,
            }

        except UnicodeDecodeError:
            return {
                "error": f"File {path} is not a valid UTF-8 text file (encoding error)."
            }

    def _normalize_line(self, line: str) -> str:
        """
        1行の比較用正規化（_find_similar_lines 向け）。
        1. 行番号/ハッシュ接頭辞を除去。
        2. タブをスペース4つに変換。
        3. 連続空白を1つに縮退してトリム。
        """
        import re as _re

        line = _re.sub(r"^\s*\d+(?::[0-9a-fA-F]+)?\|\s*", "", line)
        line = _re.sub(r"\t", "    ", line)
        line = _re.sub(r" +", " ", line).strip()
        return line

    def _normalize_block(self, lines: list[str]) -> list[str]:
        """
        ブロック単位の正規化。相対インデントを保持する。

        1. 行番号/ハッシュ接頭辞を除去。
        2. タブをスペース4つに変換。
        3. ブロック全体の最小インデントを算出して除去
           （絶対インデントの差を吸収しつつ、相対構造は維持）。
        4. 末尾空白を除去。

        例:
            file の「    def foo():\\n        pass」も
            find の「def foo():\\n    pass」も
            どちらも「def foo():\\n    pass」に正規化されてマッチする。
        """
        import re as _re

        # Step 1: ハッシュ接頭辞除去 & タブ変換
        processed = []
        for line in lines:
            line = _re.sub(r"^\s*\d+(?::[0-9a-fA-F]+)?\|\s*", "", line)
            line = line.replace("\t", "    ")
            processed.append(line)

        # Step 2: 非空行の最小インデントを計算
        indents = [len(l) - len(l.lstrip(" ")) for l in processed if l.strip()]
        min_indent = min(indents) if indents else 0

        # Step 3: 最小インデント除去 + 末尾トリム
        normalized = []
        for line in processed:
            if line.strip():
                normalized.append(line[min_indent:].rstrip())
            else:
                normalized.append("")

        return normalized

    def _find_context_match(
        self, file_lines: list[str], find_text: str, occurrence: int = 1
    ) -> tuple[int, int] | None:
        """
        findテキストにマッチする行範囲を返す。

        ブロック単位の相対インデント正規化でマッチングする。
        タブ/スペースの差、絶対インデントの差は吸収するが、
        ブロック内の相対的なインデント構造は保持して比較する。
        """
        find_lines = [l.rstrip("\n") for l in find_text.splitlines()]
        find_len = len(find_lines)
        if find_len == 0:
            return None

        norm_find = self._normalize_block(find_lines)

        match_count = 0
        for i in range(len(file_lines) - find_len + 1):
            window = file_lines[i : i + find_len]
            norm_window = self._normalize_block(window)

            if norm_window == norm_find:
                match_count += 1
                if match_count == occurrence:
                    return (i, i + find_len - 1)

        return None

    def _find_similar_lines(
        self, file_lines: list[str], find_first_line: str, diff_threshold: float = 0.5
    ) -> list[tuple[int, str]]:
        """
        マッチ失敗時に候補を提示するため、findの1行目に似た行を探す。
        """
        import difflib as _difflib

        norm_find = self._normalize_line(find_first_line)
        if not norm_find:
            return []

        candidates = []
        for i, line in enumerate(file_lines):
            norm_line = self._normalize_line(line)
            if not norm_line:
                continue
            ratio = _difflib.SequenceMatcher(None, norm_find, norm_line).ratio()
            if ratio >= diff_threshold:
                candidates.append((i + 1, line))
        return sorted(
            candidates,
            key=lambda x: _difflib.SequenceMatcher(
                None, norm_find, self._normalize_line(x[1])
            ).ratio(),
            reverse=True,
        )[:5]

    def _generate_match_failure_diff(
        self, find_lines: list[str], candidate_lines: list[str]
    ) -> str:
        """
        期待値(find)と実際(candidate)の間の差異を可視化する。
        """
        import difflib as _difflib

        # 各行を正規化して比較しやすくする
        f_norm = [self._normalize_line(l) for l in find_lines]
        c_norm = [self._normalize_line(l) for l in candidate_lines]

        diff = _difflib.ndiff(f_norm, c_norm)
        return "\n".join([line for line in diff if line.startswith(("-", "+", "?"))])

    async def write_file(self, path: str, content: str) -> str:
        """
        Write or overwrite a file with the provided content.
        ⚑ BEFORE CALLING: content must be complete — no '...' or 'TODO' placeholders.
        Creates parent directories automatically.
        """
        # Sanitize content before writing
        clean_content = self._sanitize_content(content)

        full_path = self._get_full_path(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(clean_content)
        return f"Successfully wrote to {path}"

    # --- SEARCH/REPLACE マーカー形式（aider 型）のサポート ---
    # 設計: docs/edit_format_search_replace_design.md
    # アクション層 Sym-Ops の <<< >>> エンベロープの「内側」で使うため、
    # マーカーは4文字以上の連続（git の7文字と互換、かつ厳密 <<<(3) と区別）。

    # 開始: <<<<<<< [SEARCH]  / 区切り: =======  / 終了: >>>>>>> [REPLACE]
    _SR_OPEN_RE = re.compile(r"^\s*<{4,}\s*(?:SEARCH)?\s*:?\s*$", re.IGNORECASE)
    _SR_SEP_RE = re.compile(r"^\s*={4,}\s*$")
    _SR_CLOSE_RE = re.compile(r"^\s*>{4,}\s*(?:REPLACE)?\s*:?\s*$", re.IGNORECASE)

    # git コンフリクトマーカー（未解決コンフリクトの署名）。git は厳密に7文字。
    _GIT_CONFLICT_OPEN_RE = re.compile(r"^<{7} ")
    _GIT_CONFLICT_SEP_RE = re.compile(r"^={7}$")
    _GIT_CONFLICT_CLOSE_RE = re.compile(r"^>{7} ")

    @classmethod
    def _content_uses_markers(cls, content: str) -> bool:
        """
        コンテンツが SEARCH/REPLACE マーカー形式を使っているか判定する。

        Args:
            content: edit_file のコンテンツブロック文字列

        Returns:
            開始マーカー行（<<<<<<< [SEARCH]）が1つでもあれば True
        """
        return any(cls._SR_OPEN_RE.match(line) for line in content.split("\n"))

    @classmethod
    def _has_git_conflict_markers(cls, text: str) -> bool:
        """
        テキストに未解決の git コンフリクトマーカーが含まれるか判定する。

        マーカー形式編集は `=======` を帯域内で区別できないため、対象ファイルが
        コンフリクト中の場合はマーカー形式パースを拒否し write_file へ誘導する
        （docs/edit_format_search_replace_design.md §3.2 / §7）。

        Args:
            text: 検査対象のファイル内容

        Returns:
            開始(<<<<<<< )と区切り(=======)の両方が存在すれば True
        """
        lines = text.split("\n")
        has_open = any(cls._GIT_CONFLICT_OPEN_RE.match(l) for l in lines)
        has_sep = any(cls._GIT_CONFLICT_SEP_RE.match(l) for l in lines)
        return has_open and has_sep

    @classmethod
    def _parse_search_replace_markers(cls, content: str) -> List[dict]:
        """
        SEARCH/REPLACE マーカー形式のコンテンツを find/replace ペアへ変換する。

        寛容文法（docs/edit_format_search_replace_design.md §2.3）:
        - 開始 `<{4,} [SEARCH]` / 区切り `={4,}` / 終了 `>{4,} [REPLACE]`
        - マーカー行のラベル（SEARCH/REPLACE）・コロンは省略可、大文字小文字不問
        - 終端マーカー欠落時は次の開始マーカーまたは EOF までを REPLACE とみなす

        Args:
            content: マーカー形式のコンテンツブロック文字列

        Returns:
            {'find': ..., 'replace': ..., 'occurrence': 1} のリスト。
            区切り `=======` を欠くなど分離不能なブロックはスキップする。
        """
        lines = content.split("\n")
        pairs: List[dict] = []
        i = 0
        n = len(lines)

        while i < n:
            if not cls._SR_OPEN_RE.match(lines[i]):
                i += 1
                continue

            # SEARCH 本文を区切りまで収集
            i += 1
            search_lines: List[str] = []
            found_sep = False
            while i < n:
                if cls._SR_SEP_RE.match(lines[i]):
                    found_sep = True
                    i += 1
                    break
                if cls._SR_OPEN_RE.match(lines[i]):
                    # 区切りなしで次のブロックが始まった → このブロックは破棄
                    break
                search_lines.append(lines[i])
                i += 1

            if not found_sep:
                # 区切り欠落（分離不能）。修復せずスキップ（呼び出し元がエラー提示）
                continue

            # REPLACE 本文を終端まで（終端欠落時は次の開始 or EOF まで）収集
            replace_lines: List[str] = []
            while i < n:
                if cls._SR_CLOSE_RE.match(lines[i]):
                    i += 1
                    break
                if cls._SR_OPEN_RE.match(lines[i]):
                    # 終端欠落のまま次ブロック開始 → ここで打ち切る（i は進めない）
                    break
                replace_lines.append(lines[i])
                i += 1

            pairs.append(
                {
                    "find": "\n".join(search_lines).strip("\n"),
                    "replace": "\n".join(replace_lines).strip("\n"),
                    "occurrence": 1,
                }
            )

        return pairs

    async def edit_file(
        self,
        path: str,
        find: str = "",
        replace: str = "",
        occurrence: int = 1,
        content: str = "",
    ) -> str:
        '''
        Context Match (Fuzzy) based file editing with search-and-replace.
        Whitespace differences (tabs/spaces) are ignored during matching.

        推奨形式: SEARCH/REPLACE マーカー（aider 型）。SEARCH には変更前のコードを
        ファイルに見えるまま逐語で、REPLACE には変更後のコードを書く。
        ::edit_file @utils.py
        <<<
        <<<<<<< SEARCH
        def calc(x):
            return x * 2
        =======
        def calc(x: int) -> int:
            return x * 3
        >>>>>>> REPLACE
        >>>
        複数編集は SEARCH/REPLACE ブロックを並べる。対象ファイルが git コンフリクト中の
        場合はこの形式を使わず ::write_file で領域ごと書き換えること。

        後方互換形式（find:/replace:）も引き続きサポートする。

        Sym-Ops format (single edit):
        ::edit_file @utils.py
        <<<
        find: |
            def calculate_total(items: list[int]) -> int:
                """Original docstring."""
                return sum(items)
        replace: |
            def calculate_total(items: list[int]) -> int:
                """Updated docstring."""
                return sum(items)
        >>>

        Sym-Ops format (multi-edit using %%% separator; applied bottom-to-top):
        ::edit_file @utils.py
        <<<
        find: |
            OLD_CONSTANT = 1
        replace: |
            NEW_CONSTANT = 100
        %%%
        find: |
            return x * OLD_CONSTANT
        replace: |
            return x * NEW_CONSTANT
        >>>

        Args:
            path: 対象ファイルパス
            find: 置換対象のコードスニペット
            replace: 置換後のコード
            occurrence: 同一スニペットが複数ある場合の指定（1始まり）
            content: 複数編集を行う場合の %%% 区切りコンテンツ

        Returns:
            変更成功メッセージ（デフ形式）またはエラーメッセージ（候補提示付き）
        '''
        full_path = self._get_full_path(path)
        if not full_path.exists():
            return f"::status error\nReason: File not found: {path}"
        if not full_path.is_file():
            return f"::status error\nReason: Path is a directory: {path}"

        import re as _re

        # 各セグメントからパース
        edits_params = []

        # 1つ目のアクション（トップレベル引数）を最初に追加（もし存在すれば）
        if find:
            edits_params.append(
                {"find": find, "replace": replace, "occurrence": int(occurrence)}
            )

        # --- SEARCH/REPLACE マーカー形式の分岐（docs/edit_format_search_replace_design.md） ---
        if content and self._content_uses_markers(content):
            # ルーティング: 対象ファイルがコンフリクト中ならマーカー形式は危険 → write_file へ誘導
            try:
                _existing = full_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                _existing = full_path.read_text(encoding="latin-1")
            if self._has_git_conflict_markers(_existing):
                return (
                    f"::status error\n"
                    f"Reason: conflict_markers_in_target\n"
                    f"Message: {path} contains unresolved git conflict markers. "
                    f"SEARCH/REPLACE marker editing is unsafe here because '=======' cannot be "
                    f"disambiguated from the protocol separator.\n"
                    f"Fix: Use ::write_file to rewrite the conflicted region as a whole."
                )

            marker_pairs = self._parse_search_replace_markers(content)
            if not marker_pairs:
                return (
                    f"::status error\n"
                    f"Reason: marker_parse_failed\n"
                    f"Message: Found a SEARCH marker but could not extract a valid "
                    f"SEARCH/REPLACE pair (missing '=======' separator?).\n"
                    f"Fix: Use the exact form:\n"
                    f"<<<<<<< SEARCH\n(old code)\n=======\n(new code)\n>>>>>>> REPLACE"
                )

            # 健全性チェック: REPLACE 側に git マーカーが残る → 誤パースの疑い。適用拒否
            for mp in marker_pairs:
                if self._has_git_conflict_markers(mp["replace"]) or mp[
                    "replace"
                ].lstrip().startswith(("<<<<<<<", ">>>>>>>")):
                    return (
                        f"::status error\n"
                        f"Reason: marker_leak_in_replace\n"
                        f"Message: The REPLACE content still contains conflict/marker lines, "
                        f"which usually means the markers were mis-parsed.\n"
                        f"Fix: Re-issue the edit, or use ::write_file for whole-region rewrites."
                    )

            edits_params.extend(marker_pairs)
            # マーカー形式では従来の find:/replace: セグメント解析は行わない
            return await self._apply_edits(path, full_path, edits_params, content)
        # ----------------------------------------------------------------------------------

        # セグメントの収集（従来の find:/replace: 形式）
        segments_raw = _re.split(r"\n%%%", content)

        # コンテンツブロック内のセグメントをパース
        for seg in segments_raw:
            seg = seg.strip("\n")
            if not seg.strip():
                continue

            # YAMLフロントマター、またはブロックそのものがYAMLの場合を考慮
            found_params = {}
            fm_match = _re.match(r"^---\n(.*?)\n---\n?(.*)", seg, _re.DOTALL)
            if fm_match:
                try:
                    p = yaml.safe_load(fm_match.group(1))
                    if isinstance(p, dict):
                        found_params = p
                except Exception:
                    pass
            else:
                # ブロックそのものをYAMLとしてパースを試みる
                try:
                    p = yaml.safe_load(seg)
                    if isinstance(p, dict) and ("find" in p or "replace" in p):
                        found_params = p
                except Exception:
                    pass

            # フォールバック：正規表現による find/replace 抽出 (Hybrid Parsing)
            if not found_params.get("find"):
                fallback = self._extract_find_replace_fallback(seg)
                if fallback:
                    found_params.update(fallback)

            if "find" in found_params:
                edits_params.append(
                    {
                        "find": found_params.get("find", ""),
                        "replace": found_params.get("replace", ""),
                        "occurrence": int(found_params.get("occurrence", 1)),
                    }
                )

        return await self._apply_edits(path, full_path, edits_params, content)

    async def _apply_edits(
        self, path: str, full_path: Path, edits_params: List[dict], content: str
    ) -> str:
        """
        収集済みの find/replace ペアを対象ファイルに適用する共通処理。

        マーカー形式・従来 find:/replace: 形式の両経路がここに合流する。
        マッチには空白寛容な _find_context_match を用い、複数編集は下から順に
        適用してインデックスズレを防ぐ。

        Args:
            path: 対象ファイルの相対パス（メッセージ表示用）
            full_path: 解決済みの絶対パス
            edits_params: {'find', 'replace', 'occurrence'} の辞書リスト
            content: 元のコンテンツブロック（エラー時のスニペット表示用）

        Returns:
            変更成功メッセージ（更新コンテキスト付き）またはエラーメッセージ
        """
        if not edits_params:
            snippet = content[:100] + "..." if len(content) > 100 else content
            return (
                f"::status error\n"
                f"Reason: No find/replace details found in content block.\n"
                f"Received Content Snippet: [ {snippet} ]\n"
                f"Fix: Ensure 'find:' and 'replace:' keys are clearly defined. Use | for multi-line blocks.\n"
                f"Example:\n"
                f"find: |\n"
                f"    old code\n"
                f"replace: |\n"
                f"    new code"
            )

        # ファイルを読み込み
        try:
            raw_content = full_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raw_content = full_path.read_text(encoding="latin-1")

        file_lines = [l.rstrip("\n") for l in raw_content.split("\n")]

        # すべてのマッチ箇所を特定
        resolved = []
        for i, p in enumerate(edits_params):
            f = p["find"]
            r = p["replace"]
            occ = p["occurrence"]

            match = self._find_context_match(file_lines, f, occ)
            if match is None:
                first_line = f.splitlines()[0] if f.strip() else ""
                candidates = self._find_similar_lines(file_lines, first_line)

                # 差分フィードバックの生成
                diff_hint = ""
                if candidates:
                    best_cand_idx = candidates[0][0] - 1
                    cand_lines = file_lines[
                        best_cand_idx : best_cand_idx + len(f.splitlines())
                    ]
                    diff_hint = f"\nDetailed Diff with closest candidate (Line {candidates[0][0]}):\n"
                    diff_hint += self._generate_match_failure_diff(
                        f.splitlines(), cand_lines
                    )

                cand_str = "\n".join([f'  - line {l}: "{c}"' for l, c in candidates])

                return (
                    f"::status error\n"
                    f"Reason: find_not_matched (Edit {i+1})\n"
                    f"Message: The specified find snippet was not found in {path}.\n"
                    f"Candidates near the first line of 'find':\n{cand_str}\n"
                    f"{diff_hint}\n"
                    f"Hint: Ensure the 'find' block exactly matches the characters in the file, including spaces and punctuation."
                )
            resolved.append((match[0], match[1], r))

        # 下から順に適用（インデックスズレ回避）
        resolved.sort(key=lambda x: x[0], reverse=True)

        # 逐次適用と結果収集
        for start_idx, end_idx, r_text in resolved:
            # 置換後のコードからもハッシュや行番号を除去
            r_lines = [self._strip_hash_from_content(l) for l in r_text.splitlines()]
            file_lines[start_idx : end_idx + 1] = r_lines

        # 書き込み
        final_text = "\n".join(file_lines)
        clean_text = self._sanitize_content(final_text)
        full_path.write_text(clean_text, encoding="utf-8")

        # デフ表示またはコンテキストを返す
        summary = f"Successfully edited {path} ({len(resolved)} match(es))."
        context = HashlineHelper.format_context_after_edit(
            file_lines,
            resolved[-1][0],
            resolved[-1][0] + len(resolved[-1][2].split("\n")) - 1,
            context_lines=5,
        )

        return (
            f"{summary}\n"
            f"--- Updated Context ---\n"
            f"{context}\n"
            f"--- End of Context ---"
        )

    def _extract_find_replace_fallback(self, text: str) -> dict:
        """
        YAMLパースに失敗した場合の正規表現による抽出。
        ブロックの共通インデントを自動で削除する。
        1行形式 (find: old_text) にも対応 (v2.2)。
        """
        import re as _re

        res = {}

        def clean_block(block_text: str) -> str:
            if not block_text:
                return ""
            lines = block_text.splitlines()
            # 空行を除いた各行のインデントを調べる
            indents = [len(l) - len(l.lstrip()) for l in lines if l.strip()]
            if not indents:
                return block_text.strip()
            min_indent = min(indents)
            return "\n".join(
                [l[min_indent:] if l.strip() else "" for l in lines]
            ).rstrip()

        # 1. Multi-line search (find: | または find: > に続くテキスト)
        find_match = _re.search(
            r"find:\s*[|>]?\n(.*?)(?:\n\s*\w+:|$)", text, _re.DOTALL
        )
        if find_match:
            res["find"] = clean_block(find_match.group(1))
        else:
            # 2. Single-line fallback (find: value)
            find_match_sl = _re.search(r"find:\s*(.*?)(?:\n|$)", text)
            if find_match_sl:
                res["find"] = find_match_sl.group(1).strip()

        # 3. Multi-line replace (replace: | または replace: > に続くテキスト)
        replace_match = _re.search(
            r"replace:\s*[|>]?\n(.*?)(?:\n\s*\w+:|$)", text, _re.DOTALL
        )
        if replace_match:
            res["replace"] = clean_block(replace_match.group(1))
        else:
            # 4. Single-line fallback (replace: value)
            replace_match_sl = _re.search(r"replace:\s*(.*?)(?:\n|$)", text)
            if replace_match_sl:
                res["replace"] = replace_match_sl.group(1).strip()

        # occurrence
        occ_match = _re.search(r"occurrence:\s*(\d+)", text)
        if occ_match:
            res["occurrence"] = int(occ_match.group(1))

        return res if res.get("find") else None

    # Sym-Ops の既知アクション動詞（コード中に現れても除去対象とするもの）
    _PROTOCOL_VERB_PATTERN = (
        r"(?:response|edit_file|write_file|read_file|delete_file|delete_lines|"
        r"edit_lines|replace_in_file|run_command|duck_call|note|"
        r"investigate|execute_batch|propose_plan|list_directory|find_files|"
        r"grep_files|generate_code|analyze_structure|submit_hypothesis|"
        r"finish_investigation|generate_tasks|search_archives|recall|"
        r"result|status)"
    )

    def _sanitize_content(self, text: str) -> str:
        """
        プロトコル記号が誤ってコード内に漏洩するのを防ぐガード機能(v2.4)。

        v2.3 からの変更:
        - 以前は本文全体を走査して該当行を削除していたため、doctestの
          区切りや Sym-Ops 自体を解説するドキュメント等、正当なファイル
          内容まで破壊していた。
        - プロトコル漏洩はパーサーのブロック切り出しミスに起因するため、
          コンテンツの「先頭」と「末尾」にのみ現れる。v2.4 では先頭・末尾の
          連続するプロトコル行（と隣接する空行）のみを除去し、
          本文中の行は一切変更しない。

        Args:
            text: 書き込み予定のファイル内容

        Returns:
            先頭・末尾の漏洩プロトコル行を除去した内容
        """
        import re as _re

        lines = text.splitlines()

        # 既知のプロトコルアクション行（::verb ...）
        action_re = _re.compile(rf"^\s*::\s*{self._PROTOCOL_VERB_PATTERN}\b.*$")
        # Vitals 行（::c0.9 ::s1.0 形式）
        vitals_re = _re.compile(r"^\s*(?:::[cmfs][\d.]+\s*)+$")
        # ブロック区切り（単独行のみ）
        block_re = _re.compile(r"^\s*(?:>>>|<<<|%%%+)\s*$")

        def _is_protocol_line(line: str) -> bool:
            """
            行がプロトコル漏洩行（アクション/Vitals/ブロック区切り）か判定する。

            Args:
                line: 判定対象の行

            Returns:
                プロトコル行なら True
            """
            return bool(
                action_re.match(line) or vitals_re.match(line) or block_re.match(line)
            )

        start = 0
        end = len(lines)

        # 先頭の連続するプロトコル行・空行をスキップ
        while start < end and (
            not lines[start].strip() or _is_protocol_line(lines[start])
        ):
            start += 1

        # 末尾の連続するプロトコル行・空行をスキップ
        while end > start and (
            not lines[end - 1].strip() or _is_protocol_line(lines[end - 1])
        ):
            end -= 1

        return "\n".join(lines[start:end])

    def _strip_hash_from_content(self, line: str) -> str:
        """
        コンテンツから行番号/ハッシュの接頭辞を完全に除去。
        normalizeとは異なり、こちらは書き出しの際にも使われる。
        """
        import re as _re

        return _re.sub(r"^\s*\d+(?::[0-9a-fA-F]+)?\|\s*", "", line)

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

        # Sanitize before writing
        clean_new_content = self._sanitize_content(new_content)

        # Write back
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(clean_new_content)

        return f"Replaced {count} occurrence(s) of '{search}' in {path}"

    async def edit_lines(
        self, path: str, start: int, end: int, content: str, dry_run: bool = True
    ) -> str:
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

        dry_run = str(dry_run).lower() == "true"

        start, end = int(start), int(end)
        if start < 1 or end < start:
            return f"Error: Invalid range {start}-{end}"

        with open(full_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if start > len(lines):
            return f"Error: start ({start}) exceeds file length ({len(lines)})"

        # Prepare new content
        new_content_lines = [line + "\n" for line in content.split("\n")]
        old_count = min(end, len(lines)) - start + 1

        # --- 事前プレビュー（Pre-edit Preview） ---
        preview_start = max(1, start - 3)
        preview_end = min(len(lines), end + 3)

        preview_lines = []
        for i in range(preview_start, preview_end + 1):
            prefix = "!!>" if start <= i <= end else "   "
            line_content = lines[i - 1].rstrip("\n")
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
        lines[start - 1 : end] = new_content_lines

        # Sanitize before writing
        clean_final_content = self._sanitize_content("".join(lines))

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(clean_final_content)

        # --- 事後検証プレビュー（Post-edit Preview） ---
        post_preview_start = max(1, start - 5)
        post_preview_end = min(len(lines), start + len(new_content_lines) + 5)

        post_preview_lines = []
        for i in range(post_preview_start, post_preview_end + 1):
            prefix = ">>>" if start <= i < start + len(new_content_lines) else "   "
            line_content = lines[i - 1].rstrip("\n")
            post_preview_lines.append(f"{prefix} {i:4d}| {line_content}")

        post_preview_text = "\n".join(post_preview_lines)

        return (
            f"Successfully edited {path}. Replaced {old_count} lines with {len(new_content_lines)} lines.\n"
            f"--- Post-edit Preview ({post_preview_start}-{post_preview_end}) ---\n"
            f"(Note: line numbers ' N| ' and '>>>' are decorations, do not include them in edits)\n"
            f"{post_preview_text}\n"
            f"--- End of Preview ---"
        )

    async def find_files(
        self, pattern: str = "*", recursive: bool = True, path: str = "."
    ) -> List[str]:
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
                    # Skip hidden files/dirs and known noise directories
                    if item.name.startswith(".") or _is_noise_dir_name(item.name):
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

    async def grep_files(
        self,
        pattern: str,
        path: str = ".",
        include: str = "*",
        recursive: bool = True,
        max_results: int = 50,
    ) -> str:
        """
        ファイルの内容を正規表現パターンで検索する。
        find_files（ファイル名検索）と異なり、ファイルの中身を検索する。

        Sym-Ops format:
        ::grep_files
        <<<
        ---
        pattern: "def .*_handler"
        include: "*.py"
        path: "companion"
        ---
        >>>

        Args:
            pattern: 検索する正規表現パターン（例: "def .*_handler", "TODO:", "import os"）
            path: 検索開始ディレクトリ（デフォルト: "."、ワークスペースルートからの相対パス）
            include: 検索対象ファイルのパターン（デフォルト: "*"、例: "*.py", "*.ts"）
            recursive: サブディレクトリも再帰的に検索するか（デフォルト: True）
            max_results: 最大マッチ件数（デフォルト: 50）

        Returns:
            "filepath:line_num: content" 形式のマッチ行一覧と件数サマリー
        """
        import re as _re
        from fnmatch import fnmatch

        # 正規表現コンパイル
        try:
            regex = _re.compile(pattern)
        except _re.error as e:
            return f"::status error\nReason: Invalid regex pattern '{pattern}': {e}"

        # 検索開始ディレクトリ
        start_dir = (self.workspace_root / path).resolve()
        if not start_dir.exists():
            return f"::status error\nReason: Path not found: {path}"

        # 検索対象ファイルの収集
        if start_dir.is_file():
            files_to_search: List[Path] = [start_dir]
        else:
            files_to_search = []

            def collect_files(directory: Path, depth: int = 0) -> None:
                if depth > 15:
                    return
                try:
                    for item in sorted(directory.iterdir(), key=lambda x: x.name):
                        if item.name.startswith(".") or _is_noise_dir_name(item.name):
                            continue
                        if item.is_file() and fnmatch(item.name, include):
                            try:
                                item.relative_to(self.workspace_root)
                                files_to_search.append(item)
                            except ValueError:
                                pass  # ワークスペース外はスキップ
                        elif item.is_dir() and recursive:
                            collect_files(item, depth + 1)
                except PermissionError:
                    pass

            collect_files(start_dir)

        # 各ファイルを検索
        results: List[str] = []
        total_matches = 0

        for file_path in files_to_search:
            if total_matches >= max_results:
                break
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_num, line in enumerate(f, 1):
                        if regex.search(line):
                            rel_path = file_path.relative_to(self.workspace_root)
                            results.append(f"{rel_path}:{line_num}: {line.rstrip()}")
                            total_matches += 1
                            if total_matches >= max_results:
                                break
            except (OSError, PermissionError):
                pass

        if not results:
            return f"No matches found for pattern '{pattern}' in '{path}' (include='{include}')"

        if total_matches >= max_results:
            results.append(
                f"\n(Results truncated at {max_results}. "
                f"Use a more specific pattern or path to narrow results.)"
            )

        results.append(f"\n{total_matches} match(es) found.")
        return "\n".join(results)

    async def delete_lines(
        self, path: str, find: str = "", occurrence: int = 1, content: str = ""
    ) -> str:
        """
        Context Match (Fuzzy) based line deletion.
        指定したスニペットにマッチする行範囲をファイルから削除する。

        Sym-Ops format:
        ::delete_lines @path/to/file.py
        <<<
        find: |
            def legacy_function():
                pass
        >>>

        Args:
            path: 対象ファイルのパス
            find: 削除対象のコードスニペット
            occurrence: 同一スニペットが複数ある場合の指定
            content: YAMLブロックが含まれるコンテンツ

        Returns:
            成功時メッセージまたはエラーメッセージ
        """
        import re as _re

        full_path = self._get_full_path(path)
        if not full_path.exists():
            return f"::status error\nReason: File not found: {path}"

        # 引数またはコンテンツ内から find を取得
        f_text = find
        occ = occurrence

        if not f_text:
            try:
                p = yaml.safe_load(content)
                if isinstance(p, dict):
                    f_text = p.get("find", "")
                    occ = int(p.get("occurrence", 1))
            except Exception:
                pass

        if not f_text:
            return (
                f"::status error\n"
                f"Reason: No 'find' snippet specified for deletion.\n"
                f"Fix: Use 'find:' key in content block."
            )

        # ファイル読み込み
        try:
            raw_content = full_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raw_content = full_path.read_text(encoding="latin-1")

        file_lines = [l.rstrip("\n") for l in raw_content.split("\n")]

        # マッチング
        match = self._find_context_match(file_lines, f_text, occ)
        if match is None:
            first_line = f_text.splitlines()[0] if f_text.strip() else ""
            candidates = self._find_similar_lines(file_lines, first_line)
            cand_str = "\n".join([f'  - line {l}: "{c}"' for l, c in candidates])
            return (
                f"::status error\n"
                f"Reason: find_not_matched\n"
                f"Candidates:\n{cand_str}"
            )

        start_idx, end_idx = match
        deleted_count = end_idx - start_idx + 1

        del file_lines[start_idx : end_idx + 1]

        # 書き込み
        final_text = "\n".join(file_lines)
        clean_text = self._sanitize_content(final_text)
        full_path.write_text(clean_text, encoding="utf-8")

        # コンテキスト
        context = HashlineHelper.format_context_after_edit(
            file_lines,
            edit_start_idx=start_idx,
            edit_end_idx=max(start_idx - 1, 0),
            context_lines=3,
        )

        return (
            f"Successfully deleted {deleted_count} line(s) from {path}\n\n"
            f"--- Updated Context ---\n"
            f"{context}\n"
            f"--- End of Context ---"
        )

    async def delete_file(self, path: str) -> str:
        """
        Delete a file. This is irreversible.
        ⚑ BEFORE CALLING: set ::s low (e.g. ::s0.3) to trigger user confirmation.
        ディレクトリの削除には対応しない。

        Args:
            path: 削除するファイルパス

        Returns:
            成功メッセージ "Deleted file: {path}"
        """
        full_path = self._get_full_path(path)
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        if full_path.is_dir():
            raise IsADirectoryError(
                f"Path is a directory. Use delete_directory instead: {path}"
            )

        # Delete the file
        full_path.unlink()
        return f"Deleted file: {path}"


# Global instance
file_ops = FileOps()
