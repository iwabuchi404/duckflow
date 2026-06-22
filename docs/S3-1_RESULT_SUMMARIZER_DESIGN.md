# S3-1: ResultSummarizer 多段要約パイプライン設計

## 概要

ツール実行結果の表示・履歴注入を最適化する多段要約パイプライン。
LLM呼び出しを最小限に抑えつつ、長大な結果をコンパクトに表示し、
必要に応じて元データを取り出せる仕組みを提供する。

### 設計原則

1. **LLM呼び出し最小化**: 大半の結果は機械的要約（Stage 1-3）で完結する
2. **段階的圧縮**: 閾値判定 → 機械的要約 → 再判定 → SubLLM要約の順に適用
3. **取り出し可能性**: 要約で失われた元データは `retrieve_result` で取り出し可能
4. **UI/履歴分離**: UI表示も要約版。ユーザーが原文を見たい場合は `/result` コマンドで取り出し

## 処理フロー

```
ツール実行結果
  ↓
[Stage 1] 閾値判定 (threshold_chars 未満?)
  → YES: そのまま返す（要約不要）
  → NO: ↓
[Stage 2] 機械的要約（ツール別ロジック・LLM不使用）
  ↓
[Stage 3] 再閾値判定 (threshold_chars 未満になった?)
  → YES: 機械要約版を返す
  → NO: ↓
[Stage 4] SubLLM要約（SubLLMManager.summarize 使用）
  → 要約版を返す + 元データを ResultCache に保存
```

### Stage 1: 閾値判定

- 設定 `summarizer.threshold_chars`（デフォルト 2000 文字）
- 結果の文字数が閾値未満なら要約スキップ、原文をそのまま返す
- すべてのツール結果に適用

### Stage 2: 機械的要約（ツール別）

LLM を使わず、ルールベースで結果を圧縮する。
既存の `tool_history_policy.compress_for_history` を拡張・再利用。

| ツール | 機械的要約戦略 |
|---|---|
| `read_file` | 構造抽出: クラス/関数ヘッダ行 + 先頭N行 + 総行数・ファイルサイズ |
| `grep_files` | ファイル別集計 + 上位ヒット（最大10件）+ 総マッチ数 |
| `get_project_tree` | top-level + ディレクトリ数・ファイル数・省略数（既存ロジック） |
| `run_command` | head/tail 各20行 + 総行数・exit code（既存ロジック） |
| `list_symbols` | シンボル種別別集計 + 上位N件 |
| 汎用 | head/tail + 文字数・行数 |

### Stage 3: 再閾値判定

- Stage 2 の機械的要約後、再度閾値判定
- 閾値未満になったら機械要約版を返す（LLM呼び出しなし）
- まだ閾値以上なら Stage 4 へ

### Stage 4: SubLLM要約

- `SubLLMManager.summarize()` を使用（メインLLMではなく SubLLM）
- **デフォルトOFF**（`sub_llm_enabled: false`）。現状 SubLLMManager はメインLLMと同じクライアントを使用するため、コスト削減効果がない。SubLLM の安価モデル切替が実装されてから有効化する
- 有効時の要約プロンプト: 「以下のツール実行結果を重要な情報を保持しつつ簡潔に要約せよ」
- 要約結果 + 元データを ResultCache に保存
- LLM履歴には要約版 + 取り出しヒントを注入
- **実装のみ行い、デフォルト無効**: 機械的要約だけで多くのケースをカバーできるはず。実運用で機械的要約のカバレッジを観察し、SubLLMが必要か判断してから有効化

## 取り出し機構 (ResultCache)

### 要件

- SubLLMで要約した場合、元データがLLMのコンテキストから消失する
- LLMが元データを必要と判断した場合、取り出せる仕組みが必須
- UI表示も要約版でOK（ユーザーが原文を見たい場合は別途コマンド）

### 設計

```
ResultCache
  ├── entries: OrderedDict[str, ResultCacheEntry]  # id → entry
  ├── max_size: int  (デフォルト 10)
  ├── _counter: int   # 連番生成用
  └── put(tool_name, params, full_result) → cache_id
      └── LRU で古いエントリを削除

ResultCacheEntry
  ├── cache_id: str        # 連番（例: "r1", "r2", "r3"）
  ├── tool_name: str
  ├── params: Dict
  ├── full_result: str
  ├── timestamp: float
  └── size_chars: int
```

**ID 方式**: 連番（`r1`, `r2`, ...）。ハッシュ衝突リスクなし、デバッグしやすい。
セッション内のみ有効。セッション終了でキャッシュクリア。

### retrieve_result ツール

- ツール名: `retrieve_result`
- パラメータ: `@cache_id` + オプション行範囲指定（例: `::retrieve_result @r3 L120-180`）
- 戻り値: キャッシュされた元データ（行範囲指定時は該当行のみ）
- 行範囲指定なしの場合: 取り出し結果にも **Stage 2 機械的要約を適用**（トークン爆発防止）
- 行範囲指定ありの場合: 指定行のみをそのまま返す（ピンポイント参照）
- 登録: `UNIVERSAL_TOOLS` に追加（全モードで利用可能）
- 履歴注入: 要約結果に `[Full data: retrieve_result @r3]` ヒントを付記
- **期限切れ対応**: LRU削除されたエントリを参照した場合は `「Cache entry r5 has expired. Re-run the original tool to get fresh data.」` を返す

### 履歴メッセージ形式

```
[Tool: read_file @src/main.py]
要約: 3クラス定義、総450行。Mainクラス（L1-120）、Configクラス（L121-280）、
Utilsクラス（L281-450）。import文5件。
[Full data: retrieve_result @r3]
```

### ユーザー向け取り出しコマンド

- コマンド: `/result <cache_id>` または `/result <cache_id> <start>-<end>`
- ユーザーがキャッシュから全文（または指定行範囲）をUIに表示
- LLM用ツール（`retrieve_result`）とは別経路。ユーザーが「今のread_file結果、全文見たい」と思った時の手段
- 例: `/result r3` → 全文表示、`/result r3 120-180` → L120-180のみ表示

## 設定項目

```yaml
summarizer:
  threshold_chars: 2000    # 要約開始閾値（文字数）
  cache_size: 10            # ResultCache 最大件数
  sub_llm_enabled: false    # SubLLM 要約（デフォルトOFF・安価モデル切替後に有効化）
```

## 既存コードとの統合

| 既存モジュール | 統合方法 |
|---|---|
| `tool_history_policy.compress_for_history` | Stage 2 機械的要約として拡張・再利用 |
| `SubLLMManager.summarize` | Stage 4 で使用 |
| `core_action_executor.execute_actions` | 各アクション結果にパイプライン適用 |
| `ResultSummarizer.summarize_execution` | execute_tasks の全体サマリとして維持（個別要約とは別軸） |
| `core_tools.register_default_tools` | `retrieve_result` ツールを登録 |

## 適用範囲

- **対象**: `execute_actions` 内の個別ツール結果
- **除外**: `response`（ユーザー向けテキスト）、`note`（メモ）、`exit`、`duck_call`
- **execute_tasks**: 個別要約とは別に、全体サマリ（既存のResultSummarizer）を維持

## フェーズ分け（実装計画）

### Phase 1: ResultCache + retrieve_result + /result コマンド
- `companion/modules/result_cache.py` 新規作成（連番ID・LRU・期限切れメッセージ）
- `retrieve_result` ツール実装・登録（行範囲指定・機械要約適用付き）
- `/result` ユーザーコマンド実装（`command_handler.py`）
- DuckAgent に `result_cache` プロパティ追加

### Phase 2: 機械的要約の拡張
- `tool_history_policy` を拡張: ツール別機械要約ロジック強化
- 汎用 head/tail 要約関数追加
- `read_file` 構造抽出（クラス/関数ヘッダ）
- `list_symbols` シンボル種別別集計

### Phase 3: 多段パイプライン統合
- `companion/execution/result_pipeline.py` 新規作成
- Stage 1-4 のフロー実装（Stage 4 は `sub_llm_enabled: false` で実装のみ）
- `core_action_executor` に統合
- 履歴注入メッセージに取り出しヒントを付記

### Phase 4: テスト・検証
- 各 Stage の単体テスト
- ResultCache の LRU・連番ID・期限切れテスト
- `retrieve_result` 行範囲指定テスト
- `/result` コマンドテスト
- 統合テスト（パイプライン全体）
- リグレッション確認

## 性能上の考慮

- Stage 1-3 は LLM 呼び出しなし（高速・無料）
- Stage 4 の SubLLM 呼び出しは閾値を超えた場合のみ発火（デフォルトOFF）
- `retrieve_result` 取り出し結果にも機械要約を適用し、トークン爆発を防止
- 行範囲指定時はピンポイントで取得できるため、全文取り出しの必要性を削減
- ResultCache はメモリのみ（ディスク I/O なし）
- キャッシュサイズ上限でメモリ消費を制限
- 連番IDでハッシュ計算コストなし
- 既存の `compress_for_history` と統合することで二重処理を回避

## 懸念点と対応

| 懸念 | 対応 |
|---|---|
| `retrieve_result` のトークン爆発 | 取り出し結果に Stage 2 機械要約を適用 + 行範囲指定パラメータ追加 |
| キャッシュID衝突 | 連番ID（`r1`, `r2`, ...）で衝突なし |
| LRU削除後の参照 | 期限切れメッセージを返し、再実行を促す |
| SubLLM の実コスト | デフォルトOFF。機械的要約だけでカバーし、観察後に有効化判断 |
| ユーザーが原文を見たい場合 | `/result` コマンドでユーザー向け取り出し経路を提供 |
