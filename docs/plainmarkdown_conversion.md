# プレーンMarkdown → Sym-Ops v2 変換前処理

## 問題: LLMがプロトコルを完全無視

### 典型的なパターン

```markdown
LLMの出力(プレーンMarkdown):

# Authentication Implementation

Here's how to implement user authentication:

## Step 1: Create auth module

```python
import bcrypt

def hash_password(password: str):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt())
```

## Step 2: Create tests

```python
def test_hash_password():
    result = hash_password("test")
    assert result is not None
```

## Usage

Run the tests with `pytest test_auth.py`
```

**問題**: Sym-Opsプロトコルを一切使っていない

---

## 前処理戦略

### 戦略1: Markdown → Sym-Ops 変換

#### パターンA: ヘッダー → 思考

```python
def convert_headers_to_thoughts(text: str) -> str:
    """
    Markdownヘッダーを思考(>>)に変換
    """
    lines = text.split('\n')
    result = []
    
    for line in lines:
        # # Heading → >> Heading
        if re.match(r'^#{1,6}\s+', line):
            level = len(line) - len(line.lstrip('#'))
            content = line.lstrip('#').strip()
            result.append(f'>> {content}')
        else:
            result.append(line)
    
    return '\n'.join(result)
```

**例**:
```
Before: # Authentication Implementation
After:  >> Authentication Implementation
```

---

#### パターンB: コードブロック → アクション

```python
def convert_code_blocks_to_actions(text: str) -> str:
    """
    ```python コードブロックを ::create_file アクションに変換
    """
    # ヒューリスティック: 直前のヘッダーからファイル名を推測
    lines = text.split('\n')
    result = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # コードブロック開始を検出
        if line.strip().startswith('```'):
            lang = line.strip()[3:].strip()
            
            # 直前のコンテキストからファイル名を推測
            filename = infer_filename_from_context(
                result[-10:] if len(result) >= 10 else result,
                lang
            )
            
            # コード収集
            i += 1
            code_lines = []
            while i < len(lines) and not lines[i].strip().startswith('```'):
                code_lines.append(lines[i])
                i += 1
            
            # Sym-Ops形式に変換
            if filename:
                result.append(f'::create_file @{filename}')
            else:
                result.append(f'::create_file @untitled.{lang or "txt"}')
            result.append('<<<')
            result.extend(code_lines)
            result.append('>>>')
        else:
            result.append(line)
        
        i += 1
    
    return '\n'.join(result)

def infer_filename_from_context(prev_lines: list, lang: str) -> str:
    """
    直前のコンテキストからファイル名を推測
    """
    # 直前10行から "auth", "test" などのキーワードを探す
    context = ' '.join(prev_lines).lower()
    
    # パターンマッチング
    patterns = {
        r'auth(?:entication)?': 'auth',
        r'test': 'test',
        r'config': 'config',
        r'util': 'util',
        r'helper': 'helper',
        r'main': 'main',
    }
    
    for pattern, name in patterns.items():
        if re.search(pattern, context):
            ext = {'python': 'py', 'javascript': 'js'}.get(lang, lang or 'txt')
            return f'{name}.{ext}'
    
    return None
```

**例**:
```
Before:
## Create auth module
```python
def hash_password():
    pass
```

After:
>> Create auth module
::create_file @auth.py
<<<
def hash_password():
    pass
>>>
```

---

#### パターンC: インラインコード → コマンド

```python
def convert_inline_commands(text: str) -> str:
    """
    `コマンド` を ::run_command に変換
    """
    # パターン: Run ... with `command`
    pattern = r'[Rr]un.*?`([^`]+)`'
    
    def replace_command(match):
        cmd = match.group(1)
        return f'::run_command @{cmd}'
    
    # 行単位で処理
    lines = text.split('\n')
    result = []
    
    for line in lines:
        if re.search(pattern, line):
            match = re.search(pattern, line)
            if match:
                result.append(f'>> {line}')
                result.append(f'::run_command @{match.group(1)}')
        else:
            result.append(line)
    
    return '\n'.join(result)
```

**例**:
```
Before: Run the tests with `pytest test.py`
After:  >> Run the tests with pytest test.py
        ::run_command @pytest test.py
```

---

### 戦略2: プレーンテキスト → response

```python
def wrap_remaining_text_in_response(text: str) -> str:
    """
    Sym-Opsマーカーがない残りのテキストを::responseで包む
    """
    lines = text.split('\n')
    
    # プロトコルマーカーの存在チェック
    has_protocol = any(
        line.strip().startswith(marker) 
        for line in lines 
        for marker in ['>>', '::', '<<<', '>>>']
    )
    
    if not has_protocol:
        # 完全にプレーンテキスト → responseで包む
        return '::response\n<<<\n' + text + '\n>>>'
    
    return text
```

---

## 統合前処理クラス

```python
class PlainMarkdownConverter:
    """
    プレーンMarkdown → Sym-Ops v2 変換
    """
    
    def convert(self, text: str) -> tuple[str, bool]:
        """
        Returns:
            (converted_text, was_plain_markdown)
        """
        # プロトコル存在チェック
        if self._has_symops_markers(text):
            return text, False  # 既にSym-Ops形式
        
        # Markdown検出
        if self._looks_like_markdown(text):
            text = self._convert_markdown_to_symops(text)
            return text, True
        
        # 完全なプレーンテキスト
        text = self._wrap_in_response(text)
        return text, True
    
    def _has_symops_markers(self, text: str) -> bool:
        """Sym-Opsマーカーの存在チェック"""
        markers = ['>>', '::', '<<<', '>>>']
        return any(marker in text for marker in markers)
    
    def _looks_like_markdown(self, text: str) -> bool:
        """Markdown形式かチェック"""
        markdown_patterns = [
            r'^#{1,6}\s+',      # ヘッダー
            r'```',             # コードブロック
            r'^\*\*.*?\*\*',    # 太字
            r'^\* ',            # リスト
            r'^\d+\. ',         # 番号付きリスト
        ]
        
        return any(
            re.search(pattern, text, re.MULTILINE) 
            for pattern in markdown_patterns
        )
    
    def _convert_markdown_to_symops(self, text: str) -> str:
        """Markdown → Sym-Ops変換"""
        # Phase 1: ヘッダー → 思考
        text = convert_headers_to_thoughts(text)
        
        # Phase 2: コードブロック → アクション
        text = convert_code_blocks_to_actions(text)
        
        # Phase 3: インラインコマンド → run_command
        text = convert_inline_commands(text)
        
        # Phase 4: Vitals追加(推定値)
        text = self._add_estimated_vitals(text)
        
        return text
    
    def _add_estimated_vitals(self, text: str) -> str:
        """推定Vitalsを追加"""
        # 最初にVitalsがなければ追加
        if not re.search(r'::c\d', text):
            # 最初の>>の後に挿入
            lines = text.split('\n')
            for i, line in enumerate(lines):
                if line.strip().startswith('>>'):
                    lines.insert(i + 1, '')
                    lines.insert(i + 2, '::c0.60 ::m0.70 ::f0.80 ::s0.75')
                    lines.insert(i + 3, '')
                    break
            text = '\n'.join(lines)
        
        return text
    
    def _wrap_in_response(self, text: str) -> str:
        """完全プレーンテキストをresponseで包む"""
        return f'>> Providing response\n\n::c0.50 ::m0.60 ::f0.70 ::s0.60\n\n::response\n<<<\n{text}\n>>>'
```

---

## 実装優先度

### ⭐⭐⭐ 優先度: 高

**理由**:
- プレーンMarkdown出力が頻発(30-40%)
- 変換失敗でタスク完全崩壊
- **プロトコル遵守率向上の鍵**

### 実装コスト: 中 (3-4h)

**内訳**:
- ヘッダー変換: 30分
- コードブロック変換: 2h (ファイル名推測が複雑)
- インラインコマンド: 30分
- テスト: 1h

### 期待効果: +20-25%

プレーンMarkdown出力がSym-Ops形式に変換されることで:
- パース成功率: +20%
- アクション抽出率: +25%
- **プロトコル完全無視ケースを救済**

---

## 統合順序

```
LLM出力
  ↓
【NEW】PlainMarkdownConverter ← プレーンMarkdown検出・変換
  ↓
SymOpsPreprocessor ← 既存前処理(Phase 1)
  ↓
AutoRepair ← 記号補正
  ↓
FuzzyParser ← 最終パース
```

---

## 限界とフォールバック

### 限界
1. **ファイル名推測の精度**: 60-70%
2. **複雑なMarkdown構造**: ネストリストなど
3. **コンテキスト依存**: 前後関係が不明瞭な場合

### フォールバック戦略

```python
# ファイル名推測失敗時
if not filename:
    # タイムスタンプ付きファイル名
    filename = f'generated_{timestamp}.{ext}'

# または
if not filename:
    # ::responseで全体をラップ
    return wrap_in_response(code_block)
```

---

## テストケース

```python
TEST_CASES = [
    # Case 1: シンプルなヘッダー+コード
    (
        """# Auth Module
```python
def auth():
    pass
```""",
        """>> Auth Module

::create_file @auth.py
<<<
def auth():
    pass
>>>"""
    ),
    
    # Case 2: 複数コードブロック
    (
        """## Step 1: Create auth
```python
def auth():
    pass
```

## Step 2: Test
```python
def test():
    assert True
```""",
        """>> Step 1: Create auth

::create_file @auth.py
<<<
def auth():
    pass
>>>

>> Step 2: Test

::create_file @test.py
<<<
def test():
    assert True
>>>"""
    ),
    
    # Case 3: コマンド含む
    (
        """Run tests with `pytest test.py`""",
        """>> Run tests with pytest test.py

::run_command @pytest test.py"""
    ),
]
```

---

## 推奨実装判断

| 要素 | 評価 |
|:---|:---|
| 実装コスト | 中 (3-4h) |
| 効果 | **高** (+20-25%) |
| 頻出度 | **高** (30-40%) |
| 優先度 | **Phase 1.5** (Phase 1の次) |

**結論**: **Phase 1完了後、すぐに実装すべき**

完全なプロトコル無視は致命的なので、この変換は必須です。
