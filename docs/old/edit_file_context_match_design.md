# edit_file (Context Match方式) 設計ドキュメント

**バージョン:** 1.0  
**ステータス:** 提案

---

## 1. 概要

### 1.1 背景と課題

現行のハッシュベース方式における主な問題点：

| 問題 | 原因 |
|------|------|
| ハッシュの転記ミス | 意味のない文字列はLLMが幻覚を起こしやすい |
| 連続編集時のハッシュ無効化 | 編集後にハッシュが変わるが通知されない |
| リトライコストが高い | read → hash取得 → editの3ステップが崩れると全やり直し |

### 1.2 解決方針

**コンテキストマッチ方式**：意味のあるコードスニペットをアンカーとして使用する。
LLMはコードの意味を理解して対象を指定できるため、ハッシュ転記より認知負荷が低い。

空白・タブの差異は正規化処理で吸収し、エラー率を下げる。

---

## 2. ツール仕様

### 2.1 シグネチャ

```
::edit_file @<path>
<<<
find: |
    <対象コード（複数行可）>
replace: |
    <置換コード>
>>>
```

### 2.2 パラメーター

| パラメーター | 必須 | 説明 |
|------------|------|------|
| `find` | ✅ | 置換対象のコードスニペット。部分一致でOK |
| `replace` | ✅ | 置換後のコード |
| `occurrence` | ❌ | 同一スニペットが複数ある場合の指定（1始まり、デフォルト: 1） |

### 2.3 呼び出し例

**基本的な関数変更:**
```
::edit_file @src/auth.py
<<<
find: |
    def authenticate(user, password):
        return check_db(user, password)
replace: |
    def authenticate(user, password):
        """Authenticate user against database."""
        if not user or not password:
            raise ValueError("Credentials required")
        return check_db(user, password)
>>>
```

**1行の変更:**
```
::edit_file @config.py
<<<
find: |
    DEBUG = True
replace: |
    DEBUG = False
>>>
```

**同一パターンが複数ある場合:**
```
::edit_file @src/utils.py
<<<
find: |
    return None
replace: |
    return []
occurrence: 2
>>>
```

### 2.4 レスポンス形式

**成功時 — 変更差分を返す:**
```
::result ok
--- src/auth.py
+++ src/auth.py
@@ -12,6 +12,10 @@
 def authenticate(user, password):
+    """Authenticate user against database."""
+    if not user or not password:
+        raise ValueError("Credentials required")
     return check_db(user, password)
```

**失敗時 — 原因と候補を返す:**
```
::result error
reason: find_not_matched
message: 指定スニペットが見つかりませんでした。

candidates:
  - line 12: "def authenticate(user, pw):"
  - line 34: "def authenticate(token):"

hint: findの内容を候補に合わせて修正してください。
```

---

## 3. 正規化マッチングの仕様

### 3.1 正規化ルール

マッチング時に以下を正規化して比較する（ファイルへの書き込み時は元の形式を維持）：

| 正規化対象 | 処理 |
|-----------|------|
| タブ / スペース混在 | すべての空白文字を統一して比較 |
| 行末スペース | 除去して比較 |
| 連続空白 | 単一スペースに畳んで比較 |
| 空行の数 | 正規化対象外（構造の一部として保持） |

### 3.2 マッチングアルゴリズム

```python
import re

def normalize(text: str) -> str:
    """比較用の正規化。ファイル書き込みには使わない。"""
    lines = text.splitlines()
    normalized = []
    for line in lines:
        # タブをスペースに統一し、連続空白を圧縮、行末トリム
        line = re.sub(r'\t', '    ', line)
        line = re.sub(r' +', ' ', line).rstrip()
        normalized.append(line)
    return '\n'.join(normalized)

def find_context_match(
    file_lines: list[str],
    find_text: str,
    occurrence: int = 1
) -> tuple[int, int] | None:
    """
    findテキストにマッチする行範囲を返す。
    
    Returns:
        (start_line, end_line) 0-indexed、見つからない場合はNone
    """
    find_lines = find_text.splitlines()
    find_len = len(find_lines)
    norm_find = [normalize(l) for l in find_lines]
    
    match_count = 0
    for i in range(len(file_lines) - find_len + 1):
        window = file_lines[i:i + find_len]
        norm_window = [normalize(l) for l in window]
        
        if norm_window == norm_find:
            match_count += 1
            if match_count == occurrence:
                return (i, i + find_len)
    
    return None
```

### 3.3 置換処理

```python
def apply_edit(
    file_path: str,
    find_text: str,
    replace_text: str,
    occurrence: int = 1
) -> EditResult:
    with open(file_path, 'r', encoding='utf-8') as f:
        file_lines = f.readlines()
    
    match = find_context_match(
        [l.rstrip('\n') for l in file_lines],
        find_text,
        occurrence
    )
    
    if match is None:
        return EditResult(
            success=False,
            error="find_not_matched",
            candidates=find_similar_lines(file_lines, find_text)
        )
    
    start, end = match
    replace_lines = [l + '\n' for l in replace_text.splitlines()]
    
    new_lines = file_lines[:start] + replace_lines + file_lines[end:]
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    return EditResult(
        success=True,
        diff=generate_diff(file_lines, new_lines, file_path)
    )
```

---

## 4. エラーハンドリング

### 4.1 エラー種別と対応

| エラー | 原因 | LLMへの返却内容 |
|--------|------|----------------|
| `find_not_matched` | findが見つからない | 類似行の候補リスト |
| `multiple_matches` | occurrenceなしで複数一致 | 一致箇所の行番号一覧 |
| `ambiguous_find` | findが短すぎて誤マッチリスク | 警告 + 実行結果 |
| `file_not_found` | パス誤り | 正しいパスの候補 |

### 4.2 類似候補の提示

`find_not_matched`時は、findの最初の行に近い行を候補として返す：

```
::result error
reason: find_not_matched
message: "def authenticate(user, password):" が見つかりませんでした。

candidates:
  - line 12: "def authenticate(user, pw):"
  - line 34: "def authenticate(token, secret):"

hint: findの1行目をいずれかに修正してください。
```

---

## 5. LLMへの使用ガイドライン（プロンプト記載内容）

```
### edit_file — コンテキストマッチ方式

::edit_file @<path>
<<<
find: |
    <置換したいコード。read_fileで確認した実際のコードをそのままコピー>
replace: |
    <置換後のコード>
>>>

ルール:
- find には read_file で確認した実際のコードを使う（推測で書かない）
- 変更箇所の前後1〜2行を含めると一意に特定しやすい
- インデントは実際のファイルに合わせる（正規化で吸収されるが揃えた方が安全）
- 同じパターンが複数ある場合は occurrence: <番号> を追加する

NG例:
  find: |
      def foo():  ← 実際は def foo(self): かもしれない
      
OK例:
  find: |
      def foo(self):
          return self.bar
```

---

## 6. ハッシュ方式との比較

| 項目 | ハッシュ方式 | コンテキストマッチ方式 |
|------|------------|-------------------|
| LLMの認知負荷 | 高（意味のない文字列を転記） | 低（意味のあるコードを指定） |
| 連続編集 | ❌ ハッシュが無効化される | ✅ コードが正しければ常に有効 |
| 空白の差異 | ✅ ハッシュで検出 | ✅ 正規化で吸収 |
| 誤マッチリスク | ほぼなし | 短いfindだと発生しうる（occurrenceで対処） |
| 実装コスト | 低 | 中（正規化 + 候補提示） |
| エラーリカバリー | 再read必須 | 候補提示でその場で修正可能 |

---

## 7. 移行計画

### Phase 1: コンテキストマッチ単独で試験運用
- ハッシュ方式を廃止してコンテキストマッチのみ実装
- エラー率を計測（目標: 20%以下）

### Phase 2: エラー率に応じて判断
- 20%以下 → そのまま運用
- 20%超 → findの長さ制約やoccurrenceのデフォルト動作を調整

### Phase 3: write_fileフォールバック
- 複数箇所の大規模変更はwrite_fileを推奨するガイドラインを追加

---

## 8. 未解決の課題

- **findの最小長**: 短いfind（1行）は誤マッチリスクが高い。警告を出す閾値をどこに設定するか。
- **インデントが大きく異なる場合**: 正規化でタブ/スペース混在は吸収できるが、インデントレベル自体が違う場合の扱い。
- **バイナリファイル**: 現行と同様に非対応。
