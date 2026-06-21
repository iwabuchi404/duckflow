# Duckflow 開発ロードマップ (ROADMAP.md)

> 📌 **本ファイルはミラーです。正は Context Mixer（duckflow コレクション `roadmap`）。** ナレッジの SoT は Context Mixer（2026-06-21 改訂）。

**ステータス:** アクティブ（生き物 — Sprint 完了時や優先度変更時に更新する）
**最終更新:** 2026-06-21
**現在地:** Phase 1.6（コード実行機能）・全体約85%
**直近の検証済み baseline:** 2026-06-21 時点で `uv run pytest tests/ -v` = 179件パス / 1件スキップ

> 本ドキュメントは今後の作業計画を整理したもの。`PROGRESS.md`（作業履歴）と対で運用する。
> 各項目は **重要度** と **優先度** の2軸で評価している。CLAUDE.md §8「既知の課題」との紐付けは末尾。

---

## 評価の2軸

- **重要度（Impact）** = プロダクトの安定性・価値・保守性への影響の大きさ（長期視点）。高 / 中 / 低
- **優先度（Urgency）** = 今どれだけ早く着手すべきか（緊急性・コスト・リスク・依存）。高 / 中 / 低

> 2軸は独立。重要度が高くても優先度が低い（基盤が要先、など）項目がある。

---

## 全体構成

| Sprint | テーマ | ねらい | 状態 |
|---|---|---|---|
| **1** | 即効の安定化・正確性担保 | 小修正群で「設定が効かない」「憲法が古い」実害を消す | 完了 |
| **2** | クリーンアップ ＋ 構造改善 | デッドコード整理・`core.py` 分割 | 完了 |
| **3** | 体験・観測・コンテキスト効率 | Phase 1.6 完了・探索/履歴管理・デバッグコマンド・複数行入力・推論モデル統合 | 未着手 |
| **4** | 中長期の大きな価値 | Vitals 再設計・長期記憶・Phase 3 | 未着手 |
| **5** | 協業ループ（中核コンセプト） | Molt Report/learnings/Duck Debate。**土台（1〜3）安定後** | 設計確定済（`docs/cooperation_loop_design.md`） |

---

## Sprint 1 — 即効の安定化・正確性担保

> リスク低・コスト小。半日〜1日で実害を先に消す。

| ID | 項目 | 重要度 | 優先度 | 内容・理由 |
|---|---|:-:|:-:|---|
| **S1-1** | `duckflow.yaml` の `agent:` ネスト不整合解消 | 高 | **高** | 2026-06-21 対応。`max_loops` / `language` / `auto_approval` をトップレベル `agent` 配下へ移動し、コードが読む `agent.max_loops` と一致させた |
| **S1-2** | AGENTS.md / CLAUDE.md の陳腐化更新 | 中 | **高** | 2026-06-21 対応。`test_hashline.py` 解消済み、planning モードの条件付き編集公開、SEARCH/REPLACE 推奨、設定構造を現状へ反映 |
| **S1-3** | `InvestigationState` 仮説閾値コメント修正（2→5） | 低 | **高** | 2026-06-21 対応。`InvestigationState` の説明と `to_prompt_context()` の表示を 5 回上限へ更新 |
| **S1-4** | テスト空白地帯の埋め | 中 | **高** | 2026-06-21 対応。`execute_actions` の action cap / low-safety cancel / terminal action ordering と、Pacemaker の error-rate cascade / investigation stuck 上限を回帰テスト化 |

---

## Sprint 2 — クリーンアップ ＋ 構造改善

> コードの可読性と拡張性を回復する。S1-4 のテスト整備が前提。

| ID | 項目 | 重要度 | 優先度 | 内容・理由 |
|---|---|:-:|:-:|---|
| **S2-1** | 未使用 Phase 1 遺物の整理 | 低 | 中 | 2026-06-21 対応。未使用の `state/enums.py`, `state/transition*.py`, `state/action_result.py` と、それに依存する旧 `validators/llm_output.py` を削除 |
| **S2-2** | `pyproject.toml` 実態化 | 中 | 中 | 2026-06-21 対応。名前を `duckflow`、package include を `companion*`、console script を `duckflow = main:cli` へ更新し、未使用依存（langchain/langgraph/chromadb/faiss/sentence-transformers/textual）を削除 |
| **S2-3** | `core.py` 肥大化解消 | 高 | 中 | 2026-06-21 完了。ツール登録・モード別公開マッピング・ツール説明生成を `companion/core_tools.py` へ分離。さらに未知ツール除外・アクション数上限・terminal action 並べ替え・低 safety 判定・編集アクション判定を `companion/core_action_pipeline.py`、承認判定・denial context・ツール結果履歴メッセージ生成を `companion/core_action_results.py`、ツール呼び出し引数フィルタを `companion/core_action_invocation.py` へ分離。アクションメソッド群を companion/core_actions.py、アクション実行ディスパッチャを companion/core_action_executor.py、run()ヘルパーを companion/core_loop_helpers.py へ分離し、core.py を1000行→400行へ縮小 |

---

## Sprint 3 — 体験・観測・コンテキスト効率

> 直近マイルストーンを閉じ、探索とツール結果履歴を「長く動いても壊れにくい」形へ寄せるとともに、**開発者体験・観測性**（デバッグコマンド・複数行入力）を強化する。協業ループの認知負荷を下げる土台。

| ID | 項目 | 重要度 | 優先度 | 内容・理由 |
|---|---|:-:|:-:|---|
| **S3-1** | Phase 1.6 残：実行結果の高度な要約表示 | 中 | 中 | `ResultSummarizer` の骨格あり。フェーズ完遂・UX 向上 |
| **S3-2** | 探索/コンテキスト設計の実装 | 高 | 中 | 2026-06-22 対応（Phase A+B）。Phase A: grep_files に case_sensitive(-i相当)・シンボルヘッダ付与・ファイルグループ化・切り捨て明示を追加。Phase B: companion/tools/symbols.py 新規作成。list_symbols（ast で関数/クラス一覧・シグネチャ・行範囲・docstring）・find_definition（シンボル名→定義位置特定・候補列挙）を実装。core_tools.py にツール登録・UNIVERSAL_TOOLS に追加。Phase C（repo map 注入）・Phase D（replace_function）は後続。431 passed |
| **S3-3** | ツール結果の履歴注入ポリシー | 高 | 中 | 2026-06-21 対応（Phase 1）。`companion/tool_history_policy.py` 新規作成: `grep_files`（50件→10件+ファイル別集計）、`get_project_tree`（深階層省略+top-level+件数）、`run_command`成功時（head/tail各20行）の3ツール圧縮。`build_tool_result_message` に `history_content` パラメータ追加でUI表示（原文）とLLM履歴注入（圧縮版）を分離。`read_file`・編集失敗結果は後回し。395 passed |
| **S3-4** | `/prompt` コマンド（システムプロンプトダンプ） | 中 | **高** | 2026-06-21 対応。`/prompt`（現ターン preview）/`all`（3モード）/`raw`（JSON）/`file` を追加。`--debug-context`（宛先 `ui.print_debug_context` 未実装のデッドパス）は廃止して `/prompt` に集約 |
| **S3-5** | `/tokens` コマンド | 中 | **高** | 2026-06-21 対応。system/履歴の概算トークン・max_tokens 使用率・pruning 閾値・API usage を一覧表示。`MemoryManager.estimate_history_tokens` 公開メソッドを追加 |
| **S3-6** | `/config` 強化 | 低 | 中 | 現在のモード・公開ツール一覧・モデル・max_loops を実行状態に基づき一覧出力（既存 `/config show` の拡張） |
| **S3-7** | 複数行入力（Shift+Enter） | 中 | **高** | 2026-06-21 対応。`prompt_toolkit` キーバインド追加: Enter=送信（1行目）/ 改行（複数行化後）、`Ctrl+J`=改行（Shift+Enter 相当）、`Esc→Enter`=複数行送信。`/clear` の補完漏れも修正 |
| **S3-8** | 推論モデル統合（OpenRouter reasoning → Thought） | 中 | 中 | 2026-06-22 対応。`_extract_reasoning()` で OpenRouter API の `reasoning`/`reasoning_content` フィールドを抽出し `reasoning_to_thought()` で `>>` Thought に変換して content 先頭に prepend。本文埋め込み型 imd ブロックも `strip_reasoning_tags` が3値返却に拡張され、推論内容を Thought として活用しつつタグ除去。408 passed |
| **S3-9** | APIリトライ（指数バックオフ） | 高 | 中 | 2026-06-22 対応。`_call_with_retry()` を新設、`chat()` の API 呼び出しをラップ。指数バックオフ + jitter、429 は Retry-After ヘッダー尊重。対象: 429/500/502/503・タイムアウト・接続エラー。最大3回、`llm.retry.*` で設定可能。`usage_stats` に `retry_count`/`retry_successes` 追加。414 passed |
| **S3-10** | 全ツール統一タイムアウト | 高 | 中 | `invoke_tool()` に `asyncio.wait_for` ラッパを追加し全ツールに設定ベースのタイムアウトを適用。`ShellTool`/`CodeRunner` の 30s ハードコードを設定化へ |
| **S3-11** | 観測性強化（`/timeline`・イベントログ・`/tokens`拡張） | 中 | 中 | 3機能を1セットで実装: (1) アクション実行時間計測 + `/timeline` コマンド (2) `EventLogger` による JSONL イベントログ (3) `/tokens` にレイテンシ・リトライ回数追加表示。S3-9/S3-10 の計測基盤になる |

### S3-3 ツール結果履歴管理の初期方針

一律圧縮は禁止。**UI表示** と **LLM履歴注入** を分け、履歴側だけ tool 別ポリシーで短くする。

| 対象 | 履歴に残すもの | 圧縮してよいもの | 圧縮してはいけないもの |
|---|---|---|---|
| `read_file` | 要求範囲の行番号付き exact excerpt、`has_more`、再取得ヒント | 大きいファイルの未読範囲、編集対象外の周辺説明 | SEARCH に使う可能性がある対象行、ユーザーが明示した範囲 |
| `grep_files` | 件数、ファイル別集計、上位ヒットの exact excerpt、再検索ヒント | 大量ヒットの全列挙 | 次の判断根拠になるヒット本文 |
| `get_project_tree` | top-level、重要ファイル候補、除外/省略数 | 深い階層・ノイズディレクトリ | ユーザーが指定した path 配下の実在性 |
| `run_command` | command、exit code、duration、stdout/stderr の head/tail、失敗核心 | 成功時の長大ログ、進捗バー | traceback の原因行、assertion、stderr の核心 |
| `edit_file` / `delete_lines` | 成功概要、更新コンテキストの短い excerpt | 成功時の長い全文表示 | 失敗時 diff、候補行、`find_not_matched` の根拠 |
| `execute_batch` | 成功/失敗集計、失敗アクションの詳細 | 成功アクションの冗長ログ | 失敗した sub-action の入力とエラー |

実装の最小単位:
1. `ToolResult` に `history_content` または `history_policy` を追加し、UI表示用 `content` と分離する。
2. まず `grep_files` / `get_project_tree` / 成功した長大 `run_command` だけを対象にする。
3. `read_file` と編集失敗結果は後回し。ここを雑に圧縮すると編集精度が落ちる。
4. 将来 `raw_ref`（例: `tool-result://session/id`）で全文再取得できるようにする。

---

## Sprint 4 — 中長期の大きな価値

> 設計合意済みの大規模変更と、プロダクト中核の新機能。サブタスクまで具体化済み。
> 推奨着手順: **T-1（tier 整備）→ V-A → V-B → L-a/L-b → V-C → L-c → L-d/L-e → P系 → V-D**

### #9 モデル tier 整備（V系・edit §7 の共通前提）

| ID | 項目 | 重要度 | 優先度 | 内容 |
|---|---|:-:|:-:|---|
| **T-1** | `available_models` に tier（高/中/低）追加 ＋ `/model` tier 選択 | 中 | 中 | ユーザーが UI でモデルを高/中/低 で選べる。tier 概念は **V-B（repair_load×tier）・edit_format §7（tier別フォーマット）・V-D（モデル別較正）の共通前提**。これらの前に整備する |

### #10 Vitals 再設計（`docs/vitals_redesign_design.md` 準拠）

| ID | 項目 | 重要度 | 優先度 | 内容 |
|---|---|:-:|:-:|---|
| **V-A1** | Safety Score Interceptor 削除 | 高 | 高 | 申告 `safety` によるゲート廃止。破壊的操作の承認は既存機構に一本化 |
| **V-A2** | Pacemaker を実測値ベース化 | 高 | 高 | `check_health` / `calculate_max_loops` を execution_history 由来へ。`decay()` 廃止 |
| **V-A3** | 申告頻度ルール変更 | 中 | 高 | 「全アクション前の申告」→ `::response` / `::duck_call` / 破壊的編集提案時のみ |
| **V-B1** | MeasuredVitals / ReportedVitals 再編 | 高 | 高 | 実測（success_rate/error_rate/repair_load/progress）と申告（confidence/risk_note）に分離 |
| **V-B2** | 実測算出ロジック | 高 | 高 | 移動窓 N=10。repair_load は SymOpsProcessor の warnings を集計 |
| **V-B3** | 二重表示 UI | 中 | 中 | 申告/実績を並置、乖離時に注記（「自信過剰気味」等） |
| **V-B4** | warnings → repair_load 配線 | 中 | 中 | `ParsedResult.warnings` を core 経由で Pacemaker へ |
| **V-C1** | ルーブリック繋留をプロンプトへ | 中 | 中 | 「read_file していない編集は confidence ≤0.6」等の申告規則 |
| **V-C2** | 低confidence + risk_note の few-shot 例 | 中 | 中 | 弱モデルは例がないと低値を申告しないため必須 |
| **V-D1** | 較正学習モジュール | 低 | 低 | モデル別 JSON で申告バケット×実成功を記録、自信過剰係数を算出 |
| **V-D2** | 実績側表示へ較正係数反映 | 低 | 低 | 二重表示の実績値を較正で補正 |

> 依存: **A → B → C → D**。A/B は safety ゲート形骸の実害解消なので最優先。

### #11 Phase 2 長期記憶（PROPOSAL-004 を現行アーキテクチャに翻訳）

> 旧 FlowSpec 前提のため、companion / Think-Decide-Execute 実態に合わせて再構成。

| ID | 項目 | 重要度 | 優先度 | 内容 |
|---|---|:-:|:-:|---|
| **L-a** | learnings.md スキーマ設計 | 高 | 中 | 記録内容（タスク要約/計画/結果/エラー/フィードバック）の構造定義 |
| **L-b** | 記録モジュール実装 | 高 | 中 | タスク完了時・エラー回復時にエピソード記録。SessionManager と連携 |
| **L-c** | 検索・想起モジュール | 高 | 低 | 類似過去経験の検索 → プロンプトコンテキスト注入（`[TOOL_RESULT]` エンベロープ思想を継承）。ベクトルDB化判断を含む |
| **L-d** | ユーザー好みの自動学習 | 高 | 低 | コーディング規約・修正パターンの抽出と自動適応 |
| **L-e** | 永続化とプライバシー | 中 | 低 | learnings.md の保存先、ユーザー承認ゲート、編集・削除可能性 |

> 依存: **a → b → c**。L-d は c の上、L-e は横断。

### #12 Phase 3 高度なコード解析（S3-2 の発展形）

> S3-2（code_navigation 設計）の Phase B「ast シンボル層」と被る部分は S3-2 に寄せ、Phase 3 はその先。

| ID | 項目 | 重要度 | 優先度 | 内容 |
|---|---|:-:|:-:|---|
| **P-a** | LSP 統合（定義/参照/診断） | 中 | 低 | Tree-sitter を超えた、型付きジャンプ・ホバー・診断の取得 |
| **P-b** | repo map の高度化とキャッシュ | 中 | 低 | aider 型のシンボルツリーキャッシュ、状態カードへの先回り注入（S3-2 Phase C の完成形） |
| **P-c** | 評価の仕組み | 中 | 低 | タスク成功率・品質メトリクスの自動計測。V-D 較正データとも連携可能 |

---

## Sprint 5 — 協業ループ（中核コンセプトの実装）

> Duckflow の中核コンセプト。設計は `docs/cooperation_loop_design.md` に確定済み。
> **重要度は最高だが、本格実装は土台（Sprint 1〜3）安定後。** ただし各 Sprint は「協業ループを支える」という北極星の下で進める（同ドキュメント §5 の土台→協業再解釈表を参照）。

| ID | 項目 | 重要度 | 優先度 | 内容 |
|---|---|:-:|:-:|---|
| **C-1** | 観測インフラ先行 | 高 | 中 | 発動精度・流され率・recall ヒット率・再質問率をログから取る仕組み。**機能より先に**（効果測定の前提） |
| **C-2** | 最小ループ（Molt Report + learnings.md + recall） | 高 | 低 | 協業ループが回る最小構成。V-A/B（テレメトリ）＋ L-a（スキーマ）に依存 |
| **C-3** | Duck Debate | 中 | 低 | 判断時の立ち止まり。原則3（提案質の底上げ）の試験場。最小ループの後に乗せる |
| **C-4** | Rubber Duck Mode（ブランディング） | 低 | 中 | planning モードの UI 名変更＋プロンプト微調整。即効・低リスク・効果測定不能と割り切り |

**価値軸（品質競争ではなく）:** V1 コスト効率 / V2 ユーザー学習効果 / V3 継続向上。**「強いLLMに勝つ」ことが目的ではない。**

**効果測定:** 3層指標（L1 直接 / L2 proxy / L3 定性）。V2（学習効果）は定量で追わず dogfooding の行動シグナル観察で受け入れる。Goodhart 回避（測りやすい指標への過最適を避ける）。

**依存:** C-1（観測）だけは早期に着手可。C-2 は S2-3（core 分割）＋ V-A/B（テレメトリ）＋ L-a/b/c（長期記憶）の後に。コンセプト確定のみ「今」済ませ、土台の方向付けに使用。

---

## 依存関係

```
S1-4（テスト）─┐
              ├─→ S2-3（core 分割）─→ S3-2（探索/コンテキスト）─→ P系
              │                          ↑
              ├─→ S3-3（ツール結果履歴管理）
Sprint 4 V系 ←─┘（core 分割後に着手しやすい）─┘
```

- **S2-3**（core 分割）は S1-4（テスト）が安全網。テスト無しの大規模リファクタは禁止。
- **S3-2**（探索）は S2-3 完了後が望ましい。core へのフックが多い。
- **S3-3**（ツール結果履歴管理）は S2-3 前でも小さく始められるが、`execute_actions` の履歴注入経路に触るため S1-4 のテストが前提。
- **Sprint 4 V系** は core.py（A1/B4）と Pacemaker（A2/B2）に触れるため、S2-3 の後が安全。
- **P系** は S3-2（シンボル層）の完了が前提。

---

## 既知の課題（CLAUDE.md §8）との紐付け

| CLAUDE.md §8 課題 | 対応するロードマップ項目 | 備考 |
|---|---|---|
| §8-2 `core.py` 肥大化 | **S2-3** | |
| §8-3 `core.py` 分割前のテスト空白 | **S1-4** | AutoRepair/エンベロープ/メモリ/修正ガイド/mode mapping/config loader は追加済み、execute_actions 残分岐と Pacemaker 残を埋める |
| §8-4 Vitals 自己申告は較正されていない | **Sprint 4 V-A〜D** | 設計合意済み |
| §8-1 プロトコル境界の混同リスク | （継続的注意） | 実コード優先で確認。特定タスクではなく運用ルール |
| ツール結果による履歴圧迫 | **S3-3** | 既知課題として §8 には未収録。圧縮ではなく履歴注入ポリシーとして扱う |
| 協業ループの効果測定（計測困難） | **Sprint 5 C-1** | 3層指標・Goodhart 回避で扱う（`cooperation_loop_design.md` §6.2） |
