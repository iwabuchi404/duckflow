import re
import yaml
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from companion.utils.preprocessor import SymOpsPreprocessor, PlainMarkdownConverter, strip_reasoning_tags, reasoning_to_thought

logger = logging.getLogger(__name__)


@dataclass
class Action:
    type: str
    path: str
    content: str = ""
    depends_on: Optional[str] = None
    confidence: float = 1.0
    params: Dict[str, str] = field(default_factory=dict)


@dataclass
class ParsedResult:
    thoughts: List[str]
    vitals: dict
    actions: List[Action]
    questions: List[str]
    errors: List[str]
    confidence: float = 1.0
    warnings: List[str] = field(default_factory=list)


class ParseError(Exception):
    """Parse error"""

    pass


class AutoRepair:
    """
    Pattern-based auto-repair engine v2.1
    Automatically fixes typical LLM output errors with higher tolerance.
    """

    def repair(self, text: str) -> str:
        """Apply all repair rules"""
        text = self._fix_markdown_blocks(text)
        text = self._fix_missing_symbols(text)
        text = self._fix_vitals_format(text)
        text = self._fix_delimiters(text)
        text = self._fix_indentation(text)
        text = self._fix_unclosed_blocks(text)
        return text

    @staticmethod
    def _apply_outside_blocks(text: str, fix_line) -> str:
        """
        <<< ～ >>> コンテンツブロックの外側の行にのみ行単位の修復関数を適用する。

        ブロック内はファイル内容やコマンド出力などの生データであり、
        修復処理が内容を破壊してはならない（v3.3 ブロック保護）。

        Args:
            text: 処理対象の全文
            fix_line: ブロック外の各行に適用する関数 (str) -> str

        Returns:
            修復適用後の全文
        """
        lines = text.split("\n")
        out: List[str] = []
        in_block = False

        for line in lines:
            if in_block:
                # ブロック内は一切変更しない
                out.append(line)
                # v3.2: column 0 の >>> のみブロック終端（末尾空白は許容）
                if line.rstrip() == ">>>":
                    in_block = False
            elif line.strip() == "<<<":
                in_block = True
                out.append(line)
            else:
                out.append(fix_line(line))

        return "\n".join(out)

    def _fix_unclosed_blocks(self, text: str) -> str:
        """末尾で閉じられていない <<< ブロックを >>> で閉じる（v3.3 行単位判定）。

        v3.2 以前は ``text.count('<<<')`` による部分文字列カウントだったため、
        ``<<<<<<< SEARCH``（7文字）のような SEARCH/REPLACE マーカーや、本文中に
        出現する ``<<<`` を複数の区切りとして誤計上していた。ブロック区切りは
        パーサー本体と同じく「単独行の ``<<<`` / 行頭の ``>>>``」のみを数える。

        Args:
            text: 処理対象の全文

        Returns:
            未閉鎖ブロックを末尾で閉じた全文
        """
        open_count = 0
        close_count = 0
        for line in text.split("\n"):
            if line.strip() == "<<<":
                open_count += 1
            elif line.rstrip() == ">>>":
                close_count += 1

        if open_count > close_count:
            # 不足している終端区切りを追加
            text = text.rstrip() + "\n" + (">>>\n" * (open_count - close_count))
        return text

    def _fix_markdown_blocks(self, text: str) -> str:
        """Convert Markdown code blocks to v2 format (block-aware).

        既存の <<< ～ >>> ブロックの内側にある ``` フェンスは
        ファイル内容（例: README のコードブロック）なので変換しない。
        ブロック外の ``` フェンスのみを <<< / >>> に変換する。

        Args:
            text: 処理対象の全文

        Returns:
            フェンス変換後の全文
        """
        lines = text.split("\n")
        fixed: List[str] = []
        in_symops_block = False  # 既存の <<< ～ >>> の内側
        in_md_fence = False  # 変換中の ``` フェンスの内側

        for line in lines:
            stripped = line.strip()

            if in_symops_block:
                # 既存ブロック内は保護（フェンスもそのまま）
                fixed.append(line)
                if line.rstrip() == ">>>":
                    in_symops_block = False
                continue

            if in_md_fence:
                if stripped.startswith("```"):
                    # 閉じフェンス → ブロック終端に変換
                    fixed.append(">>>")
                    in_md_fence = False
                else:
                    # フェンス内のコードはそのまま保持
                    fixed.append(line)
                continue

            if stripped == "<<<":
                in_symops_block = True
                fixed.append(line)
                continue

            if stripped.startswith("```"):
                # 開きフェンス（言語タグは捨てる）→ ブロック開始に変換
                fixed.append("<<<")
                in_md_fence = True
                continue

            fixed.append(line)

        # 閉じフェンスがないままEOFに達した場合は _fix_unclosed_blocks が補完する
        return "\n".join(fixed)

    # Expanded action verbs with common variants
    ACTION_VERBS = {
        "create",
        "edit",
        "delete",
        "remove",
        "update",
        "write",
        "read",
        "run",
        "execute",
        "test",
        "check",
        "verify",
        "response",
        "propose_plan",
        "duck_call",
        "create_file",
        "write_file",
        "edit_file",
        "delete_file",
        "run_command",
        "read_file",
        "list_directory",
        "get_project_tree",
        "execute_batch",
        "note",
        "search_archives",
    }

    def _fix_missing_symbols(self, text: str) -> str:
        """Complement missing symbols from action lines (block-aware v3.3).

        プロトコル記号（::）を付け忘れたアクション行を補完する。
        <<< ～ >>> ブロック内はファイル内容なので一切変更しない
        （例: `update = 5` のようなコード行を `:: update @ = 5` に
        壊してしまう事故を防ぐ）。

        Args:
            text: 処理対象の全文

        Returns:
            記号補完後の全文
        """
        return self._apply_outside_blocks(text, self._fix_missing_symbols_line)

    def _fix_missing_symbols_line(self, line: str) -> str:
        """
        1行分の記号補完処理（ブロック外の行にのみ適用される）。

        Args:
            line: 処理対象の行

        Returns:
            補完後の行
        """
        stripped = line.strip()

        # Already has protocol prefix
        if (
            stripped.startswith("::")
            or stripped.startswith(">>")
            or stripped.startswith("<<<")
        ):
            return line

        # Support $ as a prefix (common LLM mistake)
        if stripped.startswith("$"):
            indent = line[: len(line) - len(line.lstrip())]
            return indent + ":: " + line.lstrip().replace("$", "", 1).strip()

        # Look for "verb @ path" or "verb path"
        # Support case-insensitive and leading whitespace
        match = re.match(
            r"^(" + "|".join(self.ACTION_VERBS) + r")\b\s*(?:@\s*)?([^\n]+)?",
            stripped,
            re.IGNORECASE,
        )

        if match:
            action, rest = match.groups()
            indent = line[: len(line) - len(line.lstrip())]
            if rest:
                return f"{indent}:: {action.lower()} @ {rest.strip()}"
            return f"{indent}:: {action.lower()}"

        return line

    def _fix_delimiters(self, text: str) -> str:
        """Normalize delimiters to v3.2 format.
        - `>>>` はインデントなし行頭のみをブロック終端として認識する（Python doctest保護）。
        - execute_batch ブロック内の %%% はバッチ区切りとして保護する。
        - `---` は変換せずコンテンツとして pass-through（Markdown水平線保護）。
        """
        lines = text.split("\n")
        fixed = []
        in_batch_block = False  # ::execute_batch の <<< ～ >>> 内かどうか
        in_block = False  # 通常の <<< ～ >>> 内かどうか

        for line in lines:
            stripped = line.strip()

            # execute_batch ブロック追跡
            if stripped == "::execute_batch":
                in_batch_block = True
                fixed.append(line)
                continue

            if stripped == "<<<":
                in_block = True
                fixed.append(line)
                continue

            # v3.2: column 0 の >>> のみブロック終端として認識する（末尾空白は許容）
            if line.rstrip() == ">>>":
                if in_batch_block and in_block:
                    in_batch_block = False
                in_block = False
                fixed.append(line)
                continue

            # execute_batch ブロック内の %%% はバッチ区切りとして保護
            if in_batch_block and in_block and stripped == "%%%":
                fixed.append("%%%")
                continue

            # ブロック外の ``` フェンスは _fix_markdown_blocks が変換済み。
            # この時点で残っている ``` はブロック内のファイル内容なので保護する。
            fixed.append(line)

        return "\n".join(fixed)

    def _fix_indentation(self, text: str) -> str:
        """Remove unnecessary indentation from protocol symbol lines v2.

        コンテンツブロック（<<< ～ >>>）の内側はインデントを保護する。
        LLMがプロトコル記号を誤ってインデントした場合のみ補正する。
        """
        lines = text.split("\n")
        fixed_lines = []
        in_block = False  # <<< ～ >>> 内かどうか

        for line in lines:
            stripped = line.strip()

            # <<< でブロック開始
            if stripped == "<<<":
                in_block = True
                fixed_lines.append(line)
                continue

            # v3.2: column 0 の >>> のみブロック終端として認識（doctest保護、末尾空白は許容）
            if line.rstrip() == ">>>":
                in_block = False
                fixed_lines.append(line)
                continue

            # コンテンツブロック内は一切変更しない（インデント保護）
            if in_block:
                fixed_lines.append(line)
                continue

            # ブロック外のプロトコル記号の不要インデントを除去
            if re.match(r"^\s*[:>@!?<-]", line):
                line = line.lstrip()
            fixed_lines.append(line)

        return "\n".join(fixed_lines)

    def _fix_vitals_format(self, text: str) -> str:
        """Normalize Duck Vitals format (block-aware v3.3).

        自然言語・パーセント表記のバイタルを `::c0.95` 形式に正規化する。
        <<< ～ >>> ブロック内はファイル内容（例: ドキュメント中の
        "confidence: 95%" という記述）なので変換しない。

        Args:
            text: 処理対象の全文

        Returns:
            バイタル正規化後の全文
        """
        return self._apply_outside_blocks(text, self._fix_vitals_line)

    def _fix_vitals_line(self, line: str) -> str:
        """
        1行分のバイタル正規化処理（ブロック外の行にのみ適用される）。

        Args:
            line: 処理対象の行

        Returns:
            正規化後の行
        """

        # 1. Natural language: "Confidence: 95%" -> "::c0.95"
        def norm_percent(match):
            key_map = {"confidence": "c", "safety": "s", "memory": "m", "focus": "f"}
            key = match.group(1).lower()
            val = float(match.group(2)) / 100.0
            return f"::{key_map[key]}{val:.2f}"

        line = re.sub(
            r"\b(confidence|safety|memory|focus):\s*(\d+)%",
            norm_percent,
            line,
            flags=re.IGNORECASE,
        )

        # 2. Natural language: "Confidence: 0.95" -> "::c0.95"
        def norm_plain(match):
            key_map = {"confidence": "c", "safety": "s", "memory": "m", "focus": "f"}
            key = match.group(1).lower()
            val = match.group(2)
            return f"::{key_map[key]}{val}"

        line = re.sub(
            r"\b(confidence|safety|memory|focus):\s*([\d.]+)",
            norm_plain,
            line,
            flags=re.IGNORECASE,
        )

        # 3. Handle #c0.9 style
        line = re.sub(r"#([cmfs])\s*([\d.]+)", r"::\1\2", line)

        # 4. Standardize spacing: "::c 0.9" -> "::c0.9"
        line = re.sub(r"::([cmfs])\s+([\d.]+)", r"::\1\2", line)

        return line


class FuzzyParser:
    """Tolerant parser v2.1"""

    def strict_parse(self, text: str) -> ParsedResult:
        """Strict parse v3.1 format. execute_batch ブロックを認識する。"""
        result = ParsedResult(
            thoughts=[], vitals={}, actions=[], questions=[], errors=[]
        )
        current_action = None
        in_content = False
        content_buffer = []
        lines = text.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            if stripped == "<<<":
                if not current_action:
                    # Robustness: Create a default action if content starts without one
                    current_action = Action(type="response", path="")
                in_content = True
                i += 1
                continue

            # v3.2: >>> は行頭（column 0）のみブロック終端として認識する（doctest保護）
            if line.rstrip() == ">>>":
                if not in_content:
                    i += 1
                    continue  # Ignore orphan >>>

                if current_action:
                    if current_action.type == "execute_batch":
                        # バッチブロックを %%% で分割してサブアクションに展開
                        batch_actions = self._split_batch_content(
                            "\n".join(content_buffer)
                        )
                        result.actions.extend(batch_actions)
                    else:
                        raw_content = "\n".join(content_buffer)
                        yaml_params, body = self._extract_yaml_frontmatter(raw_content)
                        current_action.content = body
                        # YAML フロントマターのパラメーターをインライン params にマージ（YAML優先）
                        current_action.params = {**current_action.params, **yaml_params}
                        result.actions.append(current_action)
                    current_action = None
                content_buffer = []
                in_content = False
                i += 1
                continue

            if in_content:
                content_buffer.append(line)
                i += 1
                continue

            if stripped.startswith(">>"):
                result.thoughts.append(stripped[2:].strip())
            elif stripped.startswith("::"):
                if self._is_vitals(stripped):
                    self._parse_vitals(stripped, result.vitals)
                else:
                    if current_action:
                        # 前のアクションにコンテンツブロックがなかった
                        # コンテンツなしの単体アクションとして追加する
                        result.actions.append(current_action)
                    current_action = self._parse_action(stripped)
            elif stripped.startswith("?"):
                result.questions.append(stripped[1:].strip())
            elif stripped.startswith("!"):
                result.errors.append(stripped[1:].strip())
            i += 1

        # ループ終了時に未追加のアクションがあれば追加（コンテンツブロックなしの単体アクション）
        if current_action:
            result.actions.append(current_action)

        # 連続する同一アクションを圧縮（LLMの反復出力バグ対策）
        result.actions = self._dedup_consecutive_actions(result.actions)

        return result

    @staticmethod
    def _dedup_consecutive_actions(actions: List[Action]) -> List[Action]:
        """連続する同一アクション（type, path, params, content が同じ）を1つに圧縮する。

        LLMが反復出力バグを起こした場合、同じアクションが何十回も並ぶ。
        これを1つに圧縮して無意味な重複実行を防ぐ。
        """
        if not actions:
            return actions
        deduped: List[Action] = []
        for action in actions:
            if deduped:
                prev = deduped[-1]
                if (
                    prev.type == action.type
                    and prev.path == action.path
                    and prev.params == action.params
                    and prev.content == action.content
                ):
                    continue
            deduped.append(action)
        if len(deduped) < len(actions):
            logger.warning(
                f"Dedup: {len(actions)} actions → {len(deduped)} "
                f"(removed {len(actions) - len(deduped)} consecutive duplicates)"
            )
        return deduped

    def _extract_yaml_frontmatter(self, content: str) -> tuple[dict, str]:
        """
        コンテンツブロックの先頭に YAML フロントマター（--- ブロック）がある場合、
        それを引数辞書としてパースし、残りのコンテンツ文字列を返す。

        入力例:
            ---
            anchors: "42:a3f 43:f10"
            mode: strict
            ---
            def foo(): pass

        戻り値:
            ({"anchors": "42:a3f 43:f10", "mode": "strict"}, "def foo(): pass")

        フロントマターがない場合は ({}, original_content)。
        """
        lines = content.split("\n")
        # 先頭の空行をスキップしてフロントマターを検出
        start = 0
        while start < len(lines) and lines[start].strip() == "":
            start += 1

        if start >= len(lines) or lines[start].strip() != "---":
            return {}, content

        # 終端 --- を探す
        end = start + 1
        while end < len(lines) and lines[end].strip() != "---":
            end += 1

        if end >= len(lines):
            # 終端 --- が見つからない場合はフロントマターなし扱い
            return {}, content

        yaml_text = "\n".join(lines[start + 1 : end])
        remaining = "\n".join(lines[end + 1 :]).lstrip("\n")

        # よくあるミス: include: *.py のように glob パターンを引用符なしで書くと、
        # YAML は先頭の '*' をエイリアス参照（&anchor の再利用）構文と誤解釈し、
        # フロントマター全体のパースが失敗してしまう。値が '*' で始まる未クォート行を
        # 事前にクォートしてから渡すことで、この典型ミスだけは救済する。
        yaml_text = self._quote_unquoted_glob_values(yaml_text)

        try:
            parsed = yaml.safe_load(yaml_text)
            if not isinstance(parsed, dict):
                return {}, content
            # 全値を文字列に正規化（None → '' など）
            params = {k: str(v) if v is not None else "" for k, v in parsed.items()}
            return params, remaining
        except yaml.YAMLError:
            # 上記の事前修正でも解決しない未知のYAML構文エラーの場合、従来は
            # 全パラメータを握りつぶしていたが、それだと "include: *.py" のような
            # 1行のミスでパス指定や検索パターンまで丸ごと失われてしまう。
            # 行単位の "key: value" 抽出によるフォールバックで部分的にでも救済する。
            fallback_params = self._fallback_parse_key_value_lines(yaml_text)
            if fallback_params:
                return fallback_params, remaining
            return {}, content

    def _quote_unquoted_glob_values(self, yaml_text: str) -> str:
        """
        YAMLフロントマターの各行を調べ、値が '*' から始まり引用符で
        囲まれていないものを自動的にダブルクォートで囲む。

        Args:
            yaml_text: フロントマターのYAML本文

        Returns:
            '*' 始まりの未クォート値をクォートしたYAML本文
        """
        pattern = re.compile(r"^(\s*[\w\-]+\s*:\s*)\*(\S.*)$")
        fixed_lines = []
        for line in yaml_text.split("\n"):
            m = pattern.match(line)
            fixed_lines.append(f'{m.group(1)}"*{m.group(2)}"' if m else line)
        return "\n".join(fixed_lines)

    def _fallback_parse_key_value_lines(self, yaml_text: str) -> dict:
        """
        YAML全体としてのパースに失敗した場合の最終手段。
        単純な "key: value" 形式の行のみを正規表現で抽出する。

        Args:
            yaml_text: フロントマターのYAML本文

        Returns:
            抽出できた key-value のみを含む辞書（不正な行は無視される）
        """
        params: Dict[str, str] = {}
        line_pattern = re.compile(r"^\s*([\w\-]+)\s*:\s*(.+?)\s*$")
        for line in yaml_text.split("\n"):
            m = line_pattern.match(line)
            if not m:
                continue
            key, value = m.groups()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            params[key] = value
        return params

    def _extract_line_params(self, raw_path: str) -> tuple[str, dict]:
        """
        Enhanced parameter extraction supporting quoted values and mixed content.
        Uses a greedy approach to capture the last parameter's full content even without quotes.
        """
        if not raw_path:
            return "", {}

        params = {}
        # Identify all potential "key=" start positions
        # Pattern: space followed by word followed by =
        # Special case: first parameter might not have a leading space if it follows @ immediately
        # (though @ logic usually strips leading/trailing space)

        raw_path = raw_path.strip()

        # Regex to find all key=val occurrences.
        # We look for key= and then match values carefully.
        # This regex handles: key="quoted val", key='quoted val', key=unquoted_val
        # The key must be at the start or preceded by a space.
        param_regex = r'(?:^|\s)(\w+)=((?:"[^"]*")|(?:\'[^\']*\')|(?:\S+))'

        matches = list(re.finditer(param_regex, raw_path))
        if not matches:
            return raw_path.strip(), {}

        # Path is everything before the first parameter match
        first_match = matches[0]
        # Calculate where the first key= starts (excluding the potential leading space in regex)
        first_key_start = first_match.start()
        if raw_path[first_key_start].isspace():
            first_key_start += 1

        clean_path = raw_path[:first_key_start].strip()

        # Iterate and extract. To handle the "greedy last parameter" issue:
        # Each parameter value goes from '=' to the start of the NEXT parameter.
        for i, match in enumerate(matches):
            key = match.group(1)

            # Start position of value is after '='
            # match.group(0) is the whole " key=val"
            # match.start(2) is the exact start of the value part
            val_start = match.start(2)

            if i < len(matches) - 1:
                # Value ends before the next key starts
                val_end = matches[i + 1].start()
                # If there's a space before next key, strip it
                value = raw_path[val_start:val_end].strip()
            else:
                # Last parameter takes everything until end of string
                value = raw_path[val_start:].strip()

            # Strip outer quotes if present
            if (value.startswith('"') and value.endswith('"')) or (
                value.startswith("'") and value.endswith("'")
            ):
                value = value[1:-1]

            params[key] = value

        return clean_path, params

    def _split_batch_content(self, content: str) -> List[Action]:
        """
        execute_batch ブロックのコンテンツを %%% 区切りで分割し、
        各セグメントを個別のActionに変換する（Sym-Ops v3.2）。

        Args:
            content: <<< と >>> の間のテキスト（%%% 区切りで複数アクション）

        Returns:
            パース済みアクションのリスト
        """
        # v3.2: バッチ区切り文字は %%% （--- はMarkdown水平線のため変更）
        segments = re.split(r"\n%%%", content.strip())
        actions = []
        for segment in segments:
            segment = segment.strip()
            if not segment:
                continue
            action = self._parse_batch_segment(segment)
            if action:
                actions.append(action)
        return actions

    def _parse_batch_segment(self, segment: str) -> Optional[Action]:
        """
        バッチセグメント1件をActionに変換する。
        1行目: "action_name @path" または "action_name"
        2行目以降: content

        Args:
            segment: バッチの1セグメント文字列

        Returns:
            変換されたActionオブジェクト、または None
        """
        seg_lines = segment.split("\n")
        if not seg_lines:
            return None

        first_line = seg_lines[0].strip()
        content_lines = seg_lines[1:]

        # "action_name @path" または "action_name" を解析
        if "@" in first_line:
            parts = first_line.split("@", 1)
            action_type = parts[0].strip()
            path_part = parts[1].strip()
        else:
            # @なし: 最初のスペースで分割（run_command は引数が2行目）
            tokens = first_line.split(None, 1)
            action_type = tokens[0]
            path_part = tokens[1] if len(tokens) > 1 else ""

        # Extract parameters from path_part
        path, params = self._extract_line_params(path_part)

        content = "\n".join(content_lines).strip()

        # run_command の場合、pathがなければcontentをcommandとして扱う
        if action_type == "run_command" and not path and content:
            path = content
            content = ""

        return Action(
            type=action_type,
            path=path,
            content=content,
            params=params,
            confidence=0.95,  # バッチは明示的な構文なので高信頼度
        )

    def fuzzy_parse(self, text: str) -> ParsedResult:
        """Tolerant parse"""
        result = ParsedResult(
            thoughts=[], vitals={}, actions=[], questions=[], errors=[], warnings=[]
        )
        result.thoughts = self._extract_thoughts(text)
        result.vitals = self._extract_vitals(text)
        result.actions = self._extract_actions_fuzzy(text)
        result.questions = self._extract_questions(text)
        result.errors = self._extract_errors(text)
        result.confidence = self._calculate_confidence(result)
        return result

    def _extract_actions_fuzzy(self, text: str) -> List[Action]:
        """Extract actions using v3.1 format. execute_batch を認識する。"""
        actions = []
        pattern = r"^::\s*(\w+)(?:\s*@\s*([^\n]+))?"
        lines = text.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i]
            match = re.match(pattern, line.strip())
            if match:
                # Vitals行はスキップ
                if self._is_vitals(line.strip()):
                    i += 1
                    continue

                action_type = match.group(1)
                path = match.group(2) if match.group(2) else ""
                depends_on = None

                if path and ">" in path:
                    path, depends_on = path.split(">", 1)
                    path = path.strip()
                    depends_on = depends_on.strip()

                # execute_batch の特別処理
                if action_type == "execute_batch":
                    j = i + 1
                    while j < len(lines) and not lines[j].strip():
                        j += 1
                    if j < len(lines) and lines[j].strip() == "<<<":
                        j += 1
                        block_lines = []
                        while j < len(lines):
                            # v3.2: >>> は行頭のみブロック終端（doctest保護）
                            if lines[j].rstrip() == ">>>":
                                j += 1
                                break
                            block_lines.append(lines[j])
                            j += 1
                        batch_actions = self._split_batch_content(
                            "\n".join(block_lines)
                        )
                        actions.extend(batch_actions)
                        i = j
                        continue

                content = ""
                j = i + 1
                has_delimiters = False
                content_lines = []

                while j < len(lines) and not lines[j].strip():
                    j += 1

                if j < len(lines) and lines[j].strip() == "<<<":
                    has_delimiters = True
                    j += 1
                    while j < len(lines):
                        # v3.2: >>> は行頭のみブロック終端（doctest保護）
                        if lines[j].rstrip() == ">>>":
                            j += 1
                            break
                        content_lines.append(lines[j])
                        j += 1
                else:
                    # Fuzzy mode: <<< なし
                    while j < len(lines):
                        # v3.2: >>> は行頭のみブロック終端（doctest保護）
                        if lines[j].rstrip() == ">>>":
                            j += 1
                            break
                        next_line = lines[j].strip()
                        if next_line.startswith("::") or next_line.startswith(">>"):
                            break
                        content_lines.append(lines[j])
                        j += 1

                raw_content = "\n".join(content_lines)

                # Extract parameters from path
                clean_path, params = self._extract_line_params(path)

                # Extract YAML frontmatter from content block (Option B)
                yaml_params, body = self._extract_yaml_frontmatter(raw_content)
                merged_params = {**params, **yaml_params}  # YAML 優先

                actions.append(
                    Action(
                        type=action_type.strip(),
                        path=clean_path,
                        content=body,
                        depends_on=depends_on,
                        params=merged_params,
                        confidence=0.95 if has_delimiters else 0.7,
                    )
                )
                i = j
            else:
                i += 1

        return self._dedup_consecutive_actions(actions)

    def _parse_vitals(self, line: str, vitals: dict) -> None:
        """Parse multiple vitals from a single line."""
        patterns = {
            "confidence": r"::c([\d.]+)",
            "safety": r"::s([\d.]+)",
            "memory": r"::m([\d.]+)",
            "focus": r"::f([\d.]+)",
        }
        for key, pattern in patterns.items():
            matches = re.finditer(pattern, line)
            for match in matches:
                try:
                    vitals[key] = float(match.group(1))
                except ValueError:
                    pass

    def _is_vitals(self, line: str) -> bool:
        """Robust vitals line check."""
        # Check if line contains mostly vitals markers
        v_matches = re.findall(r"::[cmfs][\d.]+", line)
        if not v_matches:
            return False
        # If the line starts with vitals and doesn't look like an action verb
        return True

    def _parse_action(self, line: str) -> Action:
        """Parse action line v2"""
        # Better parsing for actions without @ (like run_command python script.py)
        # If no @, try to split by space for the action type
        parts = line[2:].strip().split("@", 1)

        if len(parts) == 2:
            # Has @
            action_type = parts[0].strip()
            path_part = parts[1].strip()
        else:
            # No @, split by first space
            # e.g. "::run_command python script.py" -> type="run_command", path="python script.py"
            # e.g. "::finish_investigation" -> type="finish_investigation", path=""
            content = parts[0].strip()
            if " " in content:
                action_type, path_part = content.split(" ", 1)
            else:
                action_type = content
                path_part = ""

        depends_on = None

        if ">" in path_part:
            path_val, depends_on = path_part.split(">", 1)
            path_val = path_val.strip()
            depends_on = depends_on.strip()
        else:
            path_val = path_part

        # Extract parameters
        path, params = self._extract_line_params(path_val)

        return Action(type=action_type, path=path, depends_on=depends_on, params=params)

    def _calculate_confidence(self, result: ParsedResult) -> float:
        """Calculate confidence of parse result"""
        score = 1.0
        if not result.actions:
            score *= 0.5
        low_conf = [a for a in result.actions if a.confidence < 0.8]
        if low_conf:
            score *= 0.8 ** len(low_conf)
        return max(0.0, min(1.0, score))

    def _extract_thoughts(self, text: str) -> List[str]:
        """Extract thought lines v2.

        Lines inside <<< >>> content blocks are raw data (file contents,
        command output, etc.) and must NOT be treated as thoughts.
        """
        thoughts = []
        in_block = False
        for line in text.split("\n"):
            if in_block:
                if line.rstrip() == ">>>":
                    in_block = False
                continue
            if line.strip() == "<<<":
                in_block = True
                continue
            if line.strip().startswith(">>"):
                thoughts.append(line.strip()[2:].strip())
        return thoughts

    def _extract_vitals(self, text: str) -> dict:
        """Extract Duck Vitals v3.1: c=confidence, s=safety, m=memory, f=focus"""
        vitals = {}
        patterns = {
            "confidence": r"::c([\d.]+)",
            "safety": r"::s([\d.]+)",
            "memory": r"::m([\d.]+)",
            "focus": r"::f([\d.]+)",
        }
        for key, pattern in patterns.items():
            match = re.search(pattern, text)
            if match:
                try:
                    vitals[key] = float(match.group(1))
                except ValueError:
                    pass
        return vitals

    def _extract_questions(self, text: str) -> List[str]:
        """Extract questions"""
        return [
            line.strip()[1:].strip()
            for line in text.split("\n")
            if line.strip().startswith("?")
        ]

    def _extract_errors(self, text: str) -> List[str]:
        """Extract errors"""
        return [
            line.strip()[1:].strip()
            for line in text.split("\n")
            if line.strip().startswith("!")
        ]


class SymOpsProcessor:
    """
    Hybrid Processor v2 with preprocessing
    Generation -> Preprocess -> Markdown Convert -> Repair -> Parse -> Fallback
    """

    def __init__(self):
        self.preprocessor = SymOpsPreprocessor()
        self.markdown_converter = PlainMarkdownConverter()
        self.repairer = AutoRepair()
        self.parser = FuzzyParser()

    @staticmethod
    def _truncate_repetition(text: str, threshold: int = 5) -> str:
        """同じ行の異常な連続繰り返しを検知し、最初の threshold 回だけ保持して残りを切り詰める。

        LLM（特に推論系モデル）がデジェネレートループに陥ると、同じ思考行や
        アクション行を何十回も繰り返す。これをそのままパーサーに渡すと
        無意味なアクションが大量生成される。

        Args:
            text: LLM生出力テキスト
            threshold: 同一行の連続出現を許容する上限（これを超えると切り詰める）

        Returns:
            切り詰め後のテキスト
        """
        lines = text.split("\n")
        if len(lines) < threshold * 2:
            return text

        result: List[str] = []
        repeat_count = 0
        prev_line: Optional[str] = None

        for line in lines:
            if line == prev_line:
                repeat_count += 1
                if repeat_count >= threshold:
                    continue  # threshold 回以降はスキップ
            else:
                repeat_count = 0
            result.append(line)
            prev_line = line

        if len(result) < len(lines):
            removed = len(lines) - len(result)
            logger.warning(
                f"Repetition detected: truncated {removed} repeated lines "
                f"(threshold={threshold})"
            )
            result.append(
                f"\n[SYSTEM] {removed} repeated lines truncated (degenerate loop detection)"
            )

        return "\n".join(result)

    def process(self, raw_output: str) -> ParsedResult:
        """
        Main processing pipeline with preprocessing
        """
        # Phase -1: 推論系モデルの <think> ブロック除去（DeepSeek-R1 / Kimi K2 / Qwen3 / GLM 等）
        raw_output, reasoning_stripped, reasoning_content = strip_reasoning_tags(raw_output)

        # If reasoning was extracted from imd blocks, prepend as >> Thought lines
        if reasoning_content:
            thought_block = reasoning_to_thought(reasoning_content)
            raw_output = f"{thought_block}\n\n{raw_output}"
            logger.info(f"Extracted reasoning from imd blocks ({len(reasoning_content)} chars), prepended as >> Thought")

        # Phase -0.5: Repetition detection — LLMが同じ行を異常に繰り返している場合、
        # 最初の数回だけ保持して残りを切り詰める（パーサーの負荷と無意味なアクション実行を防ぐ）
        raw_output = self._truncate_repetition(raw_output)

        # Phase 0: Plain Markdown/Text Detection & Conversion
        converted, was_converted = self.markdown_converter.convert(raw_output)
        if was_converted:
            raw_output = converted

        # Phase 1: Preprocessing (remove preamble, unwrap markdown)
        preprocessed, corrections = self.preprocessor.preprocess(raw_output)

        # Phase 2: Auto Repair
        repaired = self.repairer.repair(preprocessed)

        # Phase 3: Strict Parse Attempt
        try:
            parsed = self.parser.strict_parse(repaired)
            if reasoning_stripped:
                parsed.warnings.append("Reasoning tags stripped (<think>)")
            if was_converted:
                parsed.warnings.append("Converted from plain markdown/text")
            if corrections:
                parsed.warnings.append(f"Preprocessing: {', '.join(corrections)}")
            return parsed
        except ParseError:
            pass

        # Phase 4: Fuzz Parse (Fallback)
        partial = self.parser.fuzzy_parse(repaired)
        partial.warnings.append("Partial parse used")
        if reasoning_stripped:
            partial.warnings.append("Reasoning tags stripped (<think>)")
        if was_converted:
            partial.warnings.append("Converted from plain markdown/text")
        if corrections:
            partial.warnings.append(f"Preprocessing: {', '.join(corrections)}")

        return partial
