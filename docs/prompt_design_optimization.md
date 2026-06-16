# プロンプト設計とコンテキスト構築（Context Mixer）設計書

**バージョン:** 2.0（2026-06-16 更新）
**ステータス:** 実装完了

## 1. 概要

Duckflow v4 では、LLMに送信するプロンプトを動的に構築する「Context Mixer」アーキテクチャを採用しています。これにより、以下を実現しています：

1. **プロンプトキャッシュの最大化**: 静的部分を前半に配置し、キャッシュヒット率を向上
2. **モード別ツールの動的切替**: 状況に応じて必要なツールのみを提示
3. **エラーフィードバックの動的注入**: 直前ターンのエラーに基づく修正ガイドの挿入
4. **メモリ効率の最適化**: MemoryManagerによる履歴の適切な整理

---

## 2. アーキテクチャ構成

### 2.1 コンポーネント図

```
┌─────────────────────────────────────────────────────────────┐
│                     DuckAgent (core.py)                      │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              PromptBuilder (builder.py)               │  │
│  │  ┌──────────────────────────────────────────────────┐  │  │
│  │  │  1. Static Protocol (SYMOPS_SYSTEM_PROMPT)      │  │  │
│  │  │  2. Mode Instructions + Tool Descriptions       │  │  │
│  │  │  3. Few-shot Examples (mode-specific)           │  │  │
│  │  │  4. Dynamic State Context (+ Correction Guide)  │  │  │
│  │  └──────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │           MemoryManager (memory.py)                   │  │
│  │  - Token budget 管理                                   │  │
│  │  - Pruning (重要度スコアリング)                       │  │
│  │  - Archive への保存                                   │  │  │
│  └────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │               AgentState (agent_state.py)            │  │
│  │  - conversation_history                              │  │
│  │  - last_syntax_errors (Correction Guide 用)         │  │
│  │  - vitals, current_plan, etc.                        │  │
│  └────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 プロンプトの階層構造

`PromptBuilder.build_messages()` が生成するメッセージリストの構造：

```python
messages = [
    # 1. 静的なプロトコル指示（常にキャッシュされる）
    {"role": "system", "content": SYMOPS_SYSTEM_PROMPT},
    
    # 2. モード固有の指示とツール説明（同一モード内でキャッシュ）
    {"role": "system", "content": mode_instruction},
    
    # 3. モード固有の Few-shot 例（同一モード内でキャッシュ）
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "...", "cache_control": {"type": "ephemeral"}},
    
    # 4. 動的なコンテキスト（ターンごとに変化・キャッシュされない）
    {"role": "system", "content": "Current State & Context\n..."},
]
```

---

## 3. 各レイヤーの詳細

### 3.1 Static Protocol Layer

**ファイル:** `companion/utils/response_format.py` (`SYMOPS_SYSTEM_PROMPT`)

Sym-Ops v3.2 プロトコルの構文規則を定義します。

- **特徴**: 完全に静的。どのモードでも共通
- **内容**: `::action @target`、`<<< >>>` コンテンツブロック、YAMLフロントマター、バイタル表記
- **キャッシュ戦略**: 常にキャッシュヒット

### 3.2 Mode Instructions Layer

**ファイル:** `companion/prompts/templates.py`

モード（planning / investigation / task）に応じた動作指針とツール説明を構築します。

```python
SYSTEM_PROMPT_TEMPLATE = """
...哲学とプロトコル...
<available_tools>
{tool_descriptions}
</available_tools>

{mode_specific_instructions}
"""
```

**モード別指示:**
- **INVESTIGATION_MODE**: OODAループ、仮説検証、read-only 制約
- **PLANNING_MODE**: 計画立案、タスク複雑度評価
- **TASK_MODE**: タスク実行、Fast Path (`execute_batch`) の使用

### 3.3 Few-shot Examples Layer

**ファイル:** `companion/prompts/few_shot.py`

モード固有の成功例を提供します。最後のメッセージに `cache_control` マーカーを付与し、Anthropic/OpenRouter のキャッシュ機能を活用します。

### 3.4 Dynamic Context Layer

**ファイル:** `companion/state/agent_state.py` (`to_prompt_context()`)

ターンごとに変化する情報を注入します。

```python
def to_prompt_context(self) -> str:
    """プロンプトに埋め込むためのコンテキスト情報を生成"""
    # Phase, Mode, Vitals
    # Investigation 状態
    # Current Plan (goal, current_step, tasks progress)
    # Last Action Result
```

### 3.5 Correction Guide Layer

**ファイル:** `companion/prompts/builder.py` (`_build_error_feedback()`)

直前ターンで発生した構文エラーに対する修正ガイドを動的に生成します。

```python
def _build_error_feedback(self) -> str:
    """直前ターンの構文エラーから Correction Guide セクションを生成"""
    # 例:
    # - **unknown_tool**: ツール名が認識されませんでした
    #   Good: `::note @Done. Moving to next step.`
    # - **edit_find_mismatch**: SEARCH ブロックがファイル内容と一致しません
    #   Step 1: `::read_file @path/to/file.py` — confirm content
    #   Step 2: retry with exact match
```

---

## 4. メモリ管理（MemoryManager）

**ファイル:** `companion/modules/memory.py`

### 4.1 役割

- トークン予算の管理
- 履歴の Pruning（整理）
- ArchiveStorage への保存

### 4.2 重要度スコアリング

メッセージを以下の基準でスコアリング（0.0-1.0）：

| 要素 | 重み | 説明 |
|------|------|------|
| Recency（新しさ） | 30% | 新しいメッセージほど重要 |
| Kind（種別） | 40% | ユーザー発言 > アシスタント > ツール結果 |
| Content（内容） | 30% | タスク文脈キーワード（plan, task 等） |

**重要な設計判断:**
- ユーザーの本物の発言（`_is_genuine_user_message()`）を最優先で保持
- ツール結果は「再取得可能なデータ」として優先的に削る
- エラーメッセージを過度に優先しない（文脈逆転防止）

### 4.3 Pruning 戦略

| トークン使用率 | アクション |
|---------------|-----------|
| 0-80% | 何もしない |
| 80%+ | Pruning 開始（目標70%） |
| 100%+ | 緊急モード（要約スキップ） |

### 4.4 セッション復元時の圧縮

`restore_with_summary()` により、長い履歴を「要約 + 最近N件」に圧縮します。

---

## 5. モード別ツールマッピング

**ファイル:** `companion/core.py` (`MODE_TOOL_MAPPING`)

各モードで利用可能なツールを制限します。

| ツールカテゴリ | Planning | Investigation | Task |
|--------------|----------|---------------|------|
| 共通（note, response, duck_call） | ✅ | ✅ | ✅ |
| ファイル読取（read_file, list_directory） | ✅ | ✅ | ✅ |
| ファイル編集（write_file, edit_file, delete） | ✅ | ❌ | ✅ |
| 計画（propose_plan, generate_tasks） | ✅ | ❌ | ✅ |
| 実行（run_command, execute_batch） | ❌ | ❌ | ✅ |
| 調査（investigate, submit_hypothesis） | ❌ | ✅ | ❌ |
| Sub-LLM（analyze_structure, generate_code） | ✅ | ✅ | ✅ |

**Investigation モードの制約:**
- ファイル編集系アクションはブロックされる
- 仮説2回失敗で `duck_call`（ユーザー相談）を強制

---

## 6. プロンプトキャッシュ戦略

Anthropic / OpenRouter のキャッシュ機能を活用する構造：

```python
# 最後の Few-shot メッセージにキャッシュマーカーを付与
few_shots[-1]["cache_control"] = {"type": "ephemeral"}
```

**キャッシュ境界:**
1. Static Protocol — 全ターン共通でキャッシュ
2. Mode Instructions — 同一モード内でキャッシュ
3. Few-shot Examples — 同一モード内でキャッシュ
4. Dynamic Context — キャッシュしない（毎ターン変化）

---

## 7. エラー修正ガイド

**ファイル:** `companion/prompts/builder.py`

直前ターンの構文エラーに基づき、次ターンのプロンプトに修正例を注入します。

| エラー種別 | 修正例 |
|----------|--------|
| `unknown_tool` | 存在するツール名の例を提示 |
| `edit_find_mismatch` | `read_file` で内容確認 → 再試行の手順 |
| `missing_param` | 必要パラメータの例 |
| `empty_response` | `note` / `response` の正しい使用例 |
| `investigation_edit_blocked` | `finish_investigation` → モード切替の手順 |

---

## 8. 設計の原則

1. **静的と動的分離**: 変化しない部分を前半に固定し、キャッシュを最大化
2. **モード別制限**: 状況に応じてツールを制限し、モデルの注意力を集中
3. **文脈優先度**: ユーザーの指示・合意を守り、ツール結果から削る
4. **エラー適応**: 直前のエラーに基づき、修正ガイドを動的に注入
5. **トークン効率**: MemoryManager で予算内に収める

---

## 9. 実装ファイル

| コンポーネント | ファイル |
|--------------|---------|
| PromptBuilder | `companion/prompts/builder.py` |
| Templates | `companion/prompts/templates.py` |
| Few-shot Examples | `companion/prompts/few_shot.py` |
| AgentState | `companion/state/agent_state.py` |
| MemoryManager | `companion/modules/memory.py` |
| ArchiveStorage | `companion/modules/archive.py` |
| Sym-Ops Protocol | `companion/utils/response_format.py` |
| Tool Registration | `companion/core.py` (`DuckAgent.__init__`) |

---

## 10. 参考文献

- `docs/Sym-Ops Protocol .md` — Sym-Ops v3.2 形式の詳細
- `docs/memory_manager_design.md` — MemoryManager の詳細設計
- `docs/vitals_redesign_design.md` — Vitals システムの再設計
- `CLAUDE.md` — プロジェクト全体の指示書

---

## 11. 更新履歴

| 日付 | バージョン | 内容 |
|------|----------|------|
| 2026-06-16 | 2.0 | 実装完了状態に合わせて全面改訂。階層構造、MemoryManager、Correction Guide の詳細を追加 |
| (初期版) | 1.0 | プロンプト設計の最適化ガイドラインとして作成 |
