import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from companion.utils.preprocessor import SymOpsPreprocessor, PlainMarkdownConverter

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
    Pattern-based auto-repair engine v2
    Automatically fixes typical LLM output errors
    """
    
    def repair(self, text: str) -> str:
        """Apply all repair rules"""
        text = self._fix_markdown_blocks(text)
        text = self._fix_missing_symbols(text)
        text = self._fix_delimiters(text)
        text = self._fix_indentation(text)
        text = self._fix_vitals_format(text)
        return text
    
    def _fix_markdown_blocks(self, text: str) -> str:
        """Convert Markdown code blocks to v2 format"""
        pattern = r'```(?:python|py|javascript|js|bash|sh|json|yaml|sql|markdown|md)?\n(.*?)```'
        
        def replace_block(match):
            content = match.group(1).rstrip('\n')
            return f'<<<\n{content}\n>>>'
        
        return re.sub(pattern, replace_block, text, flags=re.DOTALL | re.MULTILINE)
    
    def _fix_missing_symbols(self, text: str) -> str:
        """Complement missing symbols from action lines v2"""
        lines = text.split('\n')
        fixed_lines = []
        
        action_verbs = {
            'create', 'edit', 'delete', 'remove', 'update',
            'run', 'execute', 'test', 'check', 'verify', 'finish', 'response',
            'propose_plan', 'duck_call', 'create_file', 'edit_file', 'delete_file',
            'run_command', 'read_file', 'list_directory',
            'execute_batch',  # Sym-Ops v3.2
        }
        
        for line in lines:
            stripped = line.strip()
            
            if stripped.startswith('::'):
                fixed_lines.append(line)
                continue
            
            if stripped.startswith('$'):
                indent = line[:len(line) - len(line.lstrip())]
                line = indent + line.lstrip().replace('$', '::', 1)
                fixed_lines.append(line)
                continue
            
            match = re.match(r'^(' + '|'.join(action_verbs) + r')\s+(.+)', stripped, re.IGNORECASE)
            
            if match:
                action, rest = match.groups()
                if '@' not in rest:
                    indent = line[:len(line) - len(line.lstrip())]
                    line = f'{indent}:: {action} @ {rest}'
            
            fixed_lines.append(line)
        
        return '\n'.join(fixed_lines)
    
    def _fix_delimiters(self, text: str) -> str:
        """Normalize delimiters to v3.2 format.
        - `>>>` はインデントなし行頭のみをブロック終端として認識する（Python doctest保護）。
        - execute_batch ブロック内の %%% はバッチ区切りとして保護する。
        - `---` は変換せずコンテンツとして pass-through（Markdown水平線保護）。
        """
        lines = text.split('\n')
        fixed = []
        in_batch_block = False   # ::execute_batch の <<< ～ >>> 内かどうか
        in_block = False          # 通常の <<< ～ >>> 内かどうか

        for line in lines:
            stripped = line.strip()

            # execute_batch ブロック追跡
            if stripped == '::execute_batch':
                in_batch_block = True
                fixed.append(line)
                continue

            if stripped == '<<<':
                in_block = True
                fixed.append(line)
                continue

            # v3.2: >>> は行頭（column 0）のみブロック終端として認識する
            if line.rstrip() == '>>>':
                if in_batch_block and in_block:
                    in_batch_block = False
                in_block = False
                fixed.append(line)
                continue

            # execute_batch ブロック内の %%% はバッチ区切りとして保護
            if in_batch_block and in_block and stripped == '%%%':
                fixed.append('%%%')
                continue

            # バッククォートのコードブロックは <<< >>> に変換
            if stripped.startswith('```'):
                fixed.append('<<<')
            else:
                fixed.append(line)

        return '\n'.join(fixed)
    
    def _fix_indentation(self, text: str) -> str:
        """Remove unnecessary indentation from protocol symbol lines v2.

        コンテンツブロック（<<< ～ >>>）の内側はインデントを保護する。
        LLMがプロトコル記号を誤ってインデントした場合のみ補正する。
        """
        lines = text.split('\n')
        fixed_lines = []
        in_block = False  # <<< ～ >>> 内かどうか

        for line in lines:
            stripped = line.strip()

            # <<< でブロック開始
            if stripped == '<<<':
                in_block = True
                fixed_lines.append(line)
                continue

            # v3.2: >>> は行頭のみブロック終端として認識（doctest保護）
            if line.rstrip() == '>>>':
                in_block = False
                fixed_lines.append(line)
                continue

            # コンテンツブロック内は一切変更しない（インデント保護）
            if in_block:
                fixed_lines.append(line)
                continue

            # ブロック外のプロトコル記号の不要インデントを除去
            if re.match(r'^\s*[:>@!?<-]', line):
                line = line.lstrip()
            fixed_lines.append(line)

        return '\n'.join(fixed_lines)
    
    def _fix_vitals_format(self, text: str) -> str:
        """Normalize Duck Vitals format to v3.1.
        c=confidence, s=safety, m=memory, f=focus
        """
        text = re.sub(r'#([cmfs])', r'::\1', text)
        text = re.sub(r'\bconfidence:\s*([\d.]+)', r'::c\1', text, flags=re.IGNORECASE)
        text = re.sub(r'\bsafety:\s*([\d.]+)', r'::s\1', text, flags=re.IGNORECASE)
        text = re.sub(r'\bmemory:\s*([\d.]+)', r'::m\1', text, flags=re.IGNORECASE)
        text = re.sub(r'\bfocus:\s*([\d.]+)', r'::f\1', text, flags=re.IGNORECASE)
        return text

class FuzzyParser:
    """Tolerant parser v2"""
    
    def strict_parse(self, text: str) -> ParsedResult:
        """Strict parse v3.1 format. execute_batch ブロックを認識する。"""
        result = ParsedResult(thoughts=[], vitals={}, actions=[], questions=[], errors=[])
        current_action = None
        in_content = False
        content_buffer = []
        lines = text.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            if stripped == '<<<':
                if not current_action:
                    raise ParseError("Content block without action")
                in_content = True
                i += 1
                continue

            # v3.2: >>> は行頭（column 0）のみブロック終端として認識する（doctest保護）
            if line.rstrip() == '>>>':
                if not in_content:
                    raise ParseError("Unexpected closing delimiter >>>")
                if current_action:
                    if current_action.type == 'execute_batch':
                        # バッチブロックを --- で分割してサブアクションに展開
                        batch_actions = self._split_batch_content('\n'.join(content_buffer))
                        result.actions.extend(batch_actions)
                    else:
                        current_action.content = '\n'.join(content_buffer)
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

            if stripped.startswith('>>'):
                result.thoughts.append(stripped[2:].strip())
            elif stripped.startswith('::'):
                if self._is_vitals(stripped):
                    self._parse_vitals(stripped, result.vitals)
                else:
                    if current_action:
                        raise ParseError("Action without content block")
                    current_action = self._parse_action(stripped)
            elif stripped.startswith('?'):
                result.questions.append(stripped[1:].strip())
            elif stripped.startswith('!'):
                result.errors.append(stripped[1:].strip())
            i += 1

        if current_action:
            raise ParseError("Unclosed action block or missing content")

        return result

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
        segments = re.split(r'\n%%%', content.strip())
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
        seg_lines = segment.split('\n')
        if not seg_lines:
            return None

        first_line = seg_lines[0].strip()
        content_lines = seg_lines[1:]

        # "action_name @path" または "action_name" を解析
        if '@' in first_line:
            parts = first_line.split('@', 1)
            action_type = parts[0].strip()
            path = parts[1].strip()
        else:
            # @なし: 最初のスペースで分割（run_command は引数が2行目）
            tokens = first_line.split(None, 1)
            action_type = tokens[0]
            path = tokens[1] if len(tokens) > 1 else ""

        content = '\n'.join(content_lines).strip()

        # run_command の場合、pathがなければcontentをcommandとして扱う
        if action_type == 'run_command' and not path and content:
            path = content
            content = ""

        return Action(
            type=action_type,
            path=path,
            content=content,
            confidence=0.95  # バッチは明示的な構文なので高信頼度
        )
    
    def fuzzy_parse(self, text: str) -> ParsedResult:
        """Tolerant parse"""
        result = ParsedResult(thoughts=[], vitals={}, actions=[], questions=[], errors=[], warnings=[])
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
        pattern = r'^::\s*(\w+)(?:\s*@\s*([^\n]+))?'
        lines = text.split('\n')
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

                if path and '>' in path:
                    path, depends_on = path.split('>', 1)
                    path = path.strip()
                    depends_on = depends_on.strip()

                # execute_batch の特別処理
                if action_type == 'execute_batch':
                    j = i + 1
                    while j < len(lines) and not lines[j].strip():
                        j += 1
                    if j < len(lines) and lines[j].strip() == '<<<':
                        j += 1
                        block_lines = []
                        while j < len(lines):
                            # v3.2: >>> は行頭のみブロック終端（doctest保護）
                            if lines[j].rstrip() == '>>>':
                                j += 1
                                break
                            block_lines.append(lines[j])
                            j += 1
                        batch_actions = self._split_batch_content('\n'.join(block_lines))
                        actions.extend(batch_actions)
                        i = j
                        continue

                content = ""
                j = i + 1
                has_delimiters = False
                content_lines = []

                while j < len(lines) and not lines[j].strip():
                    j += 1

                if j < len(lines) and lines[j].strip() == '<<<':
                    has_delimiters = True
                    j += 1
                    while j < len(lines):
                        # v3.2: >>> は行頭のみブロック終端（doctest保護）
                        if lines[j].rstrip() == '>>>':
                            j += 1
                            break
                        content_lines.append(lines[j])
                        j += 1
                else:
                    # Fuzzy mode: <<< なし
                    while j < len(lines):
                        # v3.2: >>> は行頭のみブロック終端（doctest保護）
                        if lines[j].rstrip() == '>>>':
                            j += 1
                            break
                        next_line = lines[j].strip()
                        if next_line.startswith('::') or next_line.startswith('>>'):
                            break
                        content_lines.append(lines[j])
                        j += 1

                content = '\n'.join(content_lines)
                actions.append(Action(
                    type=action_type.strip(),
                    path=path.strip() if path else "",
                    content=content,
                    depends_on=depends_on,
                    confidence=0.95 if has_delimiters else 0.7
                ))
                i = j
            else:
                i += 1

        return actions
    
    def _parse_vitals(self, line: str, vitals: dict) -> None:
        """Parse Duck Vitals v3.1: c=confidence, s=safety, m=memory, f=focus"""
        patterns = {
            'confidence': r'::c([\d.]+)',
            'safety':     r'::s([\d.]+)',
            'memory':     r'::m([\d.]+)',
            'focus':      r'::f([\d.]+)',
        }
        for key, pattern in patterns.items():
            match = re.search(pattern, line)
            if match:
                try:
                    vitals[key] = float(match.group(1))
                except ValueError:
                    pass
    
    def _is_vitals(self, line: str) -> bool:
        """Check if line contains vitals v2"""
        return bool(re.search(r'::[cmfs]\d+\.', line))
    
    def _parse_action(self, line: str) -> Action:
        """Parse action line v2"""
        # Better parsing for actions without @ (like run_command python script.py)
        # If no @, try to split by space for the action type
        parts = line[2:].strip().split('@', 1)
        
        if len(parts) == 2:
            # Has @
            action_type = parts[0].strip()
            path_part = parts[1].strip()
        else:
            # No @, split by first space
            # e.g. "::run_command python script.py" -> type="run_command", path="python script.py"
            # e.g. "::finish" -> type="finish", path=""
            content = parts[0].strip()
            if ' ' in content:
                action_type, path_part = content.split(' ', 1)
            else:
                action_type = content
                path_part = ""
        
        depends_on = None
        
        if '>' in path_part:
            path, depends_on = path_part.split('>', 1)
            path = path.strip()
            depends_on = depends_on.strip()
        else:
            path = path_part
        
        return Action(type=action_type, path=path, depends_on=depends_on)
    
    def _calculate_confidence(self, result: ParsedResult) -> float:
        """Calculate confidence of parse result"""
        score = 1.0
        if not result.actions:
            score *= 0.5
        low_conf = [a for a in result.actions if a.confidence < 0.8]
        if low_conf:
            score *= (0.8 ** len(low_conf))
        return max(0.0, min(1.0, score))
    
    def _extract_thoughts(self, text: str) -> List[str]:
        """Extract thought lines v2"""
        return [line.strip()[2:].strip() for line in text.split('\n') if line.strip().startswith('>>')]
    
    def _extract_vitals(self, text: str) -> dict:
        """Extract Duck Vitals v3.1: c=confidence, s=safety, m=memory, f=focus"""
        vitals = {}
        patterns = {
            'confidence': r'::c([\d.]+)',
            'safety':     r'::s([\d.]+)',
            'memory':     r'::m([\d.]+)',
            'focus':      r'::f([\d.]+)',
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
        return [line.strip()[1:].strip() for line in text.split('\n') if line.strip().startswith('?')]
    
    def _extract_errors(self, text: str) -> List[str]:
        """Extract errors"""
        return [line.strip()[1:].strip() for line in text.split('\n') if line.strip().startswith('!')]

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
    
    def process(self, raw_output: str) -> ParsedResult:
        """
        Main processing pipeline with preprocessing
        """
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
        if was_converted:
            partial.warnings.append("Converted from plain markdown/text")
        if corrections:
            partial.warnings.append(f"Preprocessing: {', '.join(corrections)}")
        
        return partial
