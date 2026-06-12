# プロンプト改善提案書 v1

**作成日:** 2026-03-01
**対象バージョン:** Sym-Ops v3.2 / Duckflow v4
**ステータス:** 一部実装済み（提案1完了）

---

## 背景

今セッションで実施した改善（エラーフィードバック強化・investigate 後の空 response 防止・ダミーツール登録など）の後、残る改善余地として以下3つの提案を検討した。本ドキュメントはその整理と実装プランを記録する。

---

## 今セッションで実施済みの改善（参考）

| 改善内容 | ファイル |
|---------|---------|
| `unknown_tool` ヒントを現在モードのツールに絞る + 近似候補提示 | `core.py` |
| `edit_file` / `delete_lines` の `ValueError` を `anchor_mismatch` として専用処理 | `core.py` |
| `::status` / `::result` をダミーツールとして登録し即座にフィードバック | `core.py` |
| Correction Guide にエラータイプ別「正しい例」を追加、snippet 300文字に拡張 | `builder.py` |
| `action_investigate` のリターン値に "NEXT ACTION REQUIRED" を追加 | `core.py` |
| 空の `::response` をループ終了ではなく `empty_response` 構文エラーとして処理 | `core.py` |
| Critical Rule 7 追加（investigate 後は必ず observe） | `response_format.py` |
| Investigation few-shot を完全なパターンに拡張 | `few_shot.py` |
| `grep_files` ツール追加 | `file_ops.py`, `core.py`, `templates.py` |

---

## 提案 1: チェックリストのツール埋め込み（実装済み: 2026-03-01）

### 概要

グローバルなチェックリストはそのまま維持した上で、各ツールの docstring に**そのツール固有の注意事項を 1〜2 行埋め込む**（⚑ BEFORE CALLING 形式）。これにより、LLM がツールを選択する瞬間に重要な制約を再認識させる。

### 期待効果（実装後の観察）

- **anchor mismatch エラーの減少**: `edit_file` の docstring 内で anchors の正確性を強調。
- **TODO 混入防止**: `write_file` の docstring 内で content の完全性を強調。
- **安全性の確保**: `delete_file`, `run_command` で ::s 低設定を推奨。

### 実装プラン

#### 変更ファイル: `companion/tools/file_ops.py`

以下の3ツールの docstring 冒頭に注意行を追加:

```python
async def edit_file(self, path, anchors="", content=""):
    """
    Hashline-based file editing with precise line identification.
    ⚑ BEFORE CALLING: anchors must match your LATEST read_file output exactly.
       If the file may have changed, re-run read_file first to get fresh hashes.
    ...（既存 docstring）...
    """
```

```python
async def write_file(self, path, content=""):
    """
    Write or overwrite a file with the provided content.
    ⚑ BEFORE CALLING: content must be complete — no '...' or 'TODO' placeholders.
    ...（既存 docstring）...
    """
```

```python
async def delete_file(self, path):
    """
    Delete a file. This is irreversible.
    ⚑ BEFORE CALLING: set ::s low (e.g. ::s0.3) to trigger user confirmation.
    ...（既存 docstring）...
    """
```

#### 変更ファイル: `companion/tools/shell_tool.py` または `core.py` の `action_run_command`

```python
async def action_run_command(self, command=""):
    """
    Execute a shell command.
    ⚑ BEFORE CALLING: set ::s0.3 or lower for destructive commands (rm, drop, reset).
    ...
    """
```

#### Correction Guide との連携（既実装のため変更不要）

`anchor_mismatch` → `builder.py` の `_CORRECTION_EXAMPLES` に登録済み。エラー発生後の次ターンで具体的な修正手順が自動注入される。

### リスク・注意点

- docstring が長くなりすぎると `get_tool_descriptions()` で生成されるツール説明のトークン数が増える
- `⚑` 記号が一部モデルのトークナイザーで分割される可能性 → `NOTE:` や `IMPORTANT:` に変更してもよい
- 各ツールの注意を 1〜2 行に厳密に抑えること

---

## 提案 2: チェックリストのモード別分岐

### 概要

現在の `SYMOPS_SYSTEM_PROMPT` に含まれる Critical Rules（チェックリスト）はすべてのモードで同一内容が提示される。Investigation モード中に「anchors 一致確認」が出ても無関係なノイズになる。モードごとに関連するチェック項目のみを提示する。

### 優先度: ★★（中）

### 期待効果

- Investigation 中: ファイル変更系のチェックが消え、"path 正確性・コマンド安全性" に集中できる
- Task 中: anchor・完全性チェックが前面に出る
- 認知ノイズの削減（効果は大きくないが悪影響もない）

### 実装プラン

#### 変更ファイル: `companion/utils/response_format.py`

`SYMOPS_SYSTEM_PROMPT` の Critical Rules を「全モード共通」と「モード別追記」に分割:

```python
# グローバル（常に表示）
SYMOPS_CHECKLIST_GLOBAL = """
## Critical Rules (ALL MODES)
1. **Path**: Is the target path correct?
2. **Block Syntax**: `<<< >>>` — raw text only, no Markdown fences inside.
3. **Symbol Syntax**: All actions use `::action @path` format only.
4. **Batch separators**: `%%%` in `::execute_batch`.
5. **Block end `>>>`**: Column 0 only.
6. **Short messages**: `@` for inline, `<<< >>>` for long content.
7. **After `::investigate`**: MUST observe next (read_file / grep_files / run_command).
"""

# Task モード専用チェック
SYMOPS_CHECKLIST_TASK = """
## Additional Checks (Task Mode)
- **anchors** (edit_file): Do they match the LATEST read_file output exactly?
- **completeness**: No `...` or `TODO` in generated code.
- **safety** (edit/delete/run): Set `::s` low for irreversible actions.
"""

# Investigation モード専用チェック
SYMOPS_CHECKLIST_INVESTIGATION = """
## Additional Checks (Investigation Mode)
- **No file edits**: Do NOT call edit_file / write_file / delete_file during investigation.
- **Confidence**: Keep `::s` ≥ 0.7 — investigation is read-only.
- **Evidence before hypothesis**: Call read_file or run_command before submit_hypothesis.
"""
```

#### 変更ファイル: `companion/prompts/builder.py`

`_build_mode_static()` でモードに応じたチェックリストを組み合わせる:

```python
def _build_mode_static(self, tool_descriptions: str) -> str:
    mode = self.state.get_context_mode()

    # モード別チェックリストを選択
    from companion.utils.response_format import (
        SYMOPS_CHECKLIST_GLOBAL,
        SYMOPS_CHECKLIST_TASK,
        SYMOPS_CHECKLIST_INVESTIGATION,
    )
    mode_checklist = {
        'task': SYMOPS_CHECKLIST_TASK,
        'investigation': SYMOPS_CHECKLIST_INVESTIGATION,
    }.get(mode, '')

    # SYMOPS_SYSTEM_PROMPT に組み込む or 別 system メッセージとして追加
    ...
```

### リスク・注意点

- `SYMOPS_SYSTEM_PROMPT` の構造変更を伴うため、既存のプロンプトキャッシュ（`few_shot.py` の `cache_control`）に影響する可能性
- チェックが「モード別」になると、モード遷移直後（例: task → investigation）に古いチェックが一時的に残るターンが生じる
- 実装前に「グローバル部分を静的キャッシュ対象、モード別部分を動的に追加」という分離設計を確認すること

---

## 提案 3: `::m`（Memory）のシステム注入

### 概要

Vitals の4値のうち `::m`（メモリ使用率）のみ、LLM に計算させずにシステム側で実際のコンテキスト使用率から計算して注入する。LLM は `::c`, `::s`, `::f` の3値だけを考えればよくなる。

### 優先度: ★（低）

### 期待効果

- `::m` の値精度向上（LLM の推測より実際のトークン数に基づく）
- LLM の計算コストをわずかに削減（効果は小さい）
- Pacemaker がより正確なメモリ状態を持てる

### 期待効果の評価

効果は限定的。Vitals の中で実際に機能的な役割を持つのは `::s`（安全インターセプト）のみで、`::m` は主に表示・ログ用途。ただし Pacemaker の介入判定（`memory` が高い場合のサマリー生成トリガー等）を強化する際には有用になる可能性がある。

### 実装プラン

#### 変更ファイル: `companion/prompts/builder.py`

`build_messages()` 内でコンテキスト使用率を計算し、動的コンテキストに注入:

```python
def _calculate_memory_score(self) -> float:
    """現在のコンテキスト使用率を 0.0〜1.0 で返す。"""
    from companion.base.llm_client import default_client
    used = sum(
        len(str(m.get('content', ''))) // 4  # 簡易トークン推定
        for m in self.state.conversation_history
    )
    max_tokens = getattr(default_client, 'context_length', 128_000)
    return min(1.0, used / max_tokens)
```

`to_prompt_context()` 内に `::m_system={score:.1f}` として追加、または次ターンの LLM 出力に上書きマージする仕組みを `execute_actions` 側で実装。

#### 変更ファイル: `companion/state/agent_state.py`

`AgentState.vitals` に `memory_override: Optional[float]` フィールドを追加し、システム側からの上書きフラグとして使用。

### リスク・注意点

- **プロトコル非対称性の問題**: Vitals の3値は LLM 生成、1値はシステム注入という非対称が few-shot 例との整合性を乱す可能性
- **実装複雑度が高い割に効果が低い**: 他の2提案より ROI が低い
- **将来の Pacemaker 強化時に再検討**が適切なタイミング

---

## 優先度サマリー

| 優先度 | 提案 | 変更ファイル | 実装コスト | 期待効果 |
|--------|------|------------|---------|--------|
| ★★★ | チェックリストのツール docstring 埋め込み | `file_ops.py`, `core.py` | 低 | 高（anchor ミス・TODO 混入防止） |
| ★★ | チェックリストのモード別分岐 | `response_format.py`, `builder.py` | 中 | 中（Investigation 中のノイズ削減） |
| ★ | `::m` システム注入 | `builder.py`, `agent_state.py` | 中〜高 | 低（Pacemaker 強化時に再検討） |

---

## 実装順序の推奨

```
Phase 1（低コスト・高効果）
  └── 提案1: ツール docstring へのチェック埋め込み
       edit_file / write_file / delete_file / run_command の4ツール

Phase 2（中コスト・中効果）
  └── 提案2: モード別チェックリスト分岐
       response_format.py の分割 → builder.py の組み合わせロジック

Phase 3（保留）
  └── 提案3: ::m システム注入
       Pacemaker の介入判定強化と合わせて検討
```

---

## 除外した提案とその理由

| 提案 | 除外理由 |
|------|--------|
| シンボル提示の書き換え | 現状で多モデルが機能しており ROI が低い |
| Vitals `::ok` 圧縮構文 | 新構文の混乱リスク・ユーザーへの状態提示価値を維持したい |
| Vitals をアクション種別でトリガー | カテゴリ判断コストが残り、効果が限定的 |
| モード自動切り替え | 透明性・制御性を下げる。明示的宣言の価値が高い |
| 自然言語インターフェース層 | AutoRepair + FuzzyParser が既に担っている |
