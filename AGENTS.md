# Duckflow プロジェクト指示書（全AIエージェント共通）

**バージョン:** 2.0（2026-06-16 `CLAUDE.md` と同期）
**現在地:** Phase 1.6（コード実行機能）進行中・全体進捗 約85%

> このドキュメントは `CLAUDE.md`（Claude Code 用）と**同一内容**を維持する、全AIエージェント共通の指示書です（aider 等、プロバイダ非依存のエージェントが読みます）。両者に差異がある場合は、最新の更新日時を持つ方が正です。

このドキュメントは Duckflow 開発の「憲法」です。AIとしてこのプロジェクトに貢献する際は、必ずここに書かれた実態とルールに従ってください。

> **重要な経緯:** 本プロジェクトは旧 `codecrafter` パッケージから `companion` パッケージ（v4アーキテクチャ）へ移行済みです。初期計画にあった LangGraph への移行は**撤回**され、「グラフ構造を排した明示的な制御ループ」が現在の設計方針です。古い資料（docs/old/ 等）の記述よりこのドキュメントと実コードを優先してください。

## 1. プロジェクトのビジョン

Duckflowは、開発者のローカル環境で動作する対話型AIコーディングエージェントです。単なるツールではなく、開発を共にする「相棒（Companion）」を目指します。

**中核コンセプト: 協業ループ（Cooperation Loop）**
弱いLLMでも、ユーザーとの協業を通じて実用的な成果をコスト良く出しつつ、ユーザー自身も成長させる、継続的に賢くなる相棒。強いLLMとの品質競争ではなく、**コスト効率・ユーザー学習効果・継続向上**の独自軸で価値を出す（詳細: `docs/cooperation_loop_design.md`）。

**協業ループを支える3つの柱:**
1. **効率的な文脈管理:** LLM呼び出しごとに、関連性の高い情報を最小限の形で賢く組み立てる（協業提案の質の前提）
2. **予測可能な実行制御:** 隠蔽されたグラフではなく、明示的な Think-Decide-Execute ループで制御する（協業の安定した実行基盤）
3. **開発者中心の体験:** ターミナル上でキーボード中心のシームレスな操作感を提供する（協業の認知負荷を下げる）

**設計思想:** 「LLMは間違える」前提で、**ガードレール（受動的保護: 未知ツールフィルタ、承認、Correction Guide、Pacemaker介入、fail-fast）** と **協業ループ（能動的補正: ユーザーとの相互作用で質と学習を高める）** の両層で担保する。

## 2. 開発の基本方針（AIへの指示）

1. **役割分担が明確なモジュール構成:**
   - 機能ごと（ツール群、UI、状態管理など）にファイルを明確に分ける。複数の役割を一つのファイルに混ぜない。
   - 指示は「`companion/tools/file_ops.py` に新しいツールを追加して」のような具体的な形で行われる。

2. **Docstringと型ヒント（交渉の余地なし）:**
   - すべての関数・メソッド・クラスに、目的・引数（`Args:`）・戻り値（`Returns:`）を説明するDocstringを必ず記述する。
   - すべての引数と戻り値に正確な型ヒントを必ず付ける。

3. **テストを重視する文化:**
   - 新しいツールや重要機能には `tests/` に対応するテストを書く。
   - コード変更タスクの完了前に `uv run pytest tests/ -v` を実行し、リグレッションがないか確認する。

4. **設定はコードの外に:**
   - モデル名・プロンプトテンプレート等の設定値をコードに直書きしない。`duckflow.yaml`（設定）と `.env`（APIキー）で管理する。

5. **Pythonの実行は必ず UV + `-X utf8`:**
   - 例: `uv run python -X utf8 main.py`（Windows環境の文字化け防止のため必須）

6. **進捗の記録:** タスク完了時は `PROGRESS.md` の更新履歴に追記する（日付は絶対表記）。

## 3. アーキテクチャ（Duckflow v4）

### Think-Decide-Execute ループ
中心は `companion/core.py` の `DuckAgent`。

1. **Think & Decide:** `PromptBuilder` が AgentState からプロンプトを構築（プロンプトキャッシュ最適化のため「静的プロトコル → モード別ツール説明 → Few-shot例 → 動的状態」の順に階層化）。LLM は外部プロトコルとして Sym-Ops テキストを返し、`LLMClient` が内部実行モデル `ActionList`（reasoning + actions + vitals）へ変換する。
2. **Execute:** `execute_actions()` がアクションを順次実行。`response`・`exit`・`duck_call` でユーザーに制御を返し、それ以外は自律ループを継続。
3. ターン完了ごとに `SessionManager` がセッションを自動保存。

### Sym-Ops プロトコル（v3.2）
LLMの出力テキスト形式。`::action @target`、`<<< ... >>>` コンテンツブロック、YAMLフロントマター引数、`::c/s/m/f` バイタル表記からなる。`companion/utils/sym_ops.py` の `SymOpsProcessor` が「前処理 → AutoRepair（典型ミスの自動修復）→ パース」のパイプラインで処理する。`ActionList` は JSON 出力契約ではなく、Sym-Ops から変換された内部アクションコンテナである。

### 3モード制
`AgentMode`（planning / investigation / task）ごとに公開ツールが異なる（`core.py` の `MODE_TOOL_MAPPING`）。**Investigation モードは read-only 強制**で、ファイル編集系アクションはブロックされる。仮説5回失敗で duck_call（ユーザー相談）を強制（2026-06-17改訂、旧仕様は2回）。Planning モードは `finish_investigation` 後すぐに修正へ移れるよう編集系ツール（`edit_file`/`write_file`/`delete_lines`/`delete_file`）を公開するが、用途は小さく確定した修正に限る。探索的な実装や広い変更は計画化して task モードで進める（task モードはタスク完了管理・execute_tasks 等が追加で使える点が異なる）。

### ファイル編集方式（SEARCH/REPLACE マーカー形式）
`edit_file` は aider 型 `<<<<<<< SEARCH / ======= / >>>>>>> REPLACE` マーカー形式（実装済み・推奨）に対応（従来 `find:`/`replace:` も後方互換で維持）。マッチ失敗時は近似行の候補と差分ヒントを返してLLMの自己修正を促す。git コンフリクトマーカー検出時は `write_file` へルーティング、健全性チェック付き。根拠と残課題（online A/B、tier別マッピング）は `docs/edit_format_search_replace_design.md`、ベンチは `benchmarks/`。

### 多層防御（execute_actions 内）
- 未知ツールのフィルタ＋近似候補の提示（difflib）
- 1ターンあたりアクション数上限（6件）
- safety スコア < 0.5 で実行前にユーザー確認
- ファイルの上書き・編集・削除、コマンド実行は**人間の承認必須**
- 連続2回エラーで残りアクションを中断（fail-fast）
- エラーは `SyntaxErrorInfo` として記録され、次ターンのプロンプトに「Correction Guide」（修正例つき）として1ターン限り注入される

### Vitals & Pacemaker
- **Vitals:** confidence / safety / memory / focus（LLMの自己申告＋システム側のdecay/回復）
- **Pacemaker**（`companion/modules/pacemaker.py`）: max_loops をタスク量とバイタルから動的計算（3〜35）。異常検知時は、LLM自身に「何が起きたか・選択肢」を説明させるハイブリッド介入を行う。
- **再設計予定:** 自己申告（UX表示専用・ルーブリック繋留・応答時のみ）と実測テレメトリ（制御専用・二重表示）に分離する設計が合意済み（未実装）。`docs/vitals_redesign_design.md` を参照。

### メモリ管理
`MemoryManager`（`companion/modules/memory.py`）がモデルのコンテキスト長から履歴予算を動的設定（約60%を履歴に、8K〜200Kでクランプ）。使用率80%超で種別スコアリングによる pruning を行い（本物のユーザー発言=1.0 > assistant=0.6 > ツール結果=0.15 > エラー結果=0.05）、最初のユーザー指示はピン留め。削除分は ArchiveStorage に保存（`search_archives` / `recall` ツールで検索可能）。

### LLMクライアント
`companion/base/llm_client.py`。OpenAI SDK互換APIで openai / anthropic / google / groq / openrouter を統一的に扱う。メインエージェント呼び出しは Sym-Ops を `ActionList` へ変換し、`TaskListProposal` / `ExecutionSummary` / `SummaryResponse` などの補助呼び出しのみ JSON/Pydantic 構造化レスポンスとして扱う。コンテキスト長はAPI取得失敗時にフォールバックテーブルを参照。`/model` コマンドによる切替は `duckflow.yaml` に永続化される。

## 4. ディレクトリ構成（実態）

```
duckflow/
├── companion/                 # メインパッケージ（v4）
│   ├── core.py                # DuckAgent: メインループ・委譲のみ（400行。アクション・実行は core_action_executor.py、アクションメソッド群は core_actions.py、ループヘルパーは core_loop_helpers.py へ分離済）
│   ├── base/                  # LLMクライアント、レスポンス前処理
│   ├── state/                 # AgentState ほか Pydantic モデル（Single Source of Truth）
│   ├── prompts/               # PromptBuilder, システムプロンプト, Few-shot例
│   ├── tools/                 # ファイル操作, hashline, 計画, シェル, Sub-LLM ほか
│   │   └── archive/           # 旧実装の退避場所（参照のみ・変更禁止）
│   ├── execution/             # TaskExecutor, ResultSummarizer
│   ├── modules/               # Pacemaker, MemoryManager, SessionManager, コマンド処理
│   ├── memory/                # 会話メモリ
│   ├── ui/                    # Rich ベースの UI（console.py, setup_wizard.py 等）
│   ├── utils/                 # Sym-Ops パーサー, 前処理
│   ├── config/                # 設定ローダー/ライター
│   ├── security/              # ファイル保護
│   └── output/ / logging/ / task_management/
├── tests/                     # pytest テスト（hashline, response_format, frontmatter 等）
├── docs/                      # 設計ドキュメント群（old/ は陳腐化注意）
├── duckflow.yaml              # メイン設定ファイル
├── .env                       # APIキー（git管理外、.env.template 参照）
├── main.py                    # エントリーポイント
├── dump_prompt.py             # プロンプトインスペクター（デバッグ用）
├── PROGRESS.md                # 開発進捗記録
├── CLAUDE.md                  # Claude Code 用指示書（本ドキュメントと同内容）
└── AGENTS.md                  # このドキュメント（全AIエージェント共通）
```

※ 旧 `codecrafter/` ディレクトリおよびルートの `config/` ディレクトリは**既に存在しない**。

## 5. エージェントのツール一覧（登録済みアクション）

| カテゴリ | ツール | 備考 |
|---|---|---|
| 共通 | `note`, `response`, `exit`, `duck_call`, `search_archives`/`recall`, `get_project_tree` | 全モードで使用可 |
| ファイル読取 | `read_file`, `list_directory`, `find_files`, `grep_files` | read_file は行番号付きで返す。検索の標準化・シンボル層・repo map 注入の設計が合意済み（`docs/code_navigation_context_design.md`、未実装） |
| ファイル編集 | `write_file`, `edit_file`, `delete_lines`, `delete_file` | 承認必須。task モード、および planning モードの小さく確定した修正で使用可 |
| 計画 | `propose_plan`, `generate_tasks`, `mark_step_complete`, `mark_task_complete`, `execute_tasks` | Plan → Step → Task の階層管理 |
| 実行 | `run_command`（承認必須）, `execute_batch` | execute_batch はパーサーが展開 |
| 調査 | `investigate`, `submit_hypothesis`, `finish_investigation` | OODAループ、read-only |
| Sub-LLM | `analyze_structure`, `generate_code` | 補助LLMへの委譲 |

## 6. 実行・開発コマンド

```bash
# 起動（前回セッションの継続を選択可能）
uv run python -X utf8 main.py
#   --no-session      セッション保存・復元を無効化
#   --dir <path>      ワークスペースを指定
#   --setup           セットアップウィザードを起動

# テスト
uv run pytest tests/ -v

# プロンプトインスペクター（モード別のシステムプロンプトを確認）
uv run python -X utf8 dump_prompt.py task    # task モードのみ
uv run python -X utf8 dump_prompt.py all     # 全モード

# フォーマット / Lint
uv run black companion/
uv run ruff check companion/
```

**アプリ内コマンド:** `/help` `/status` `/config` `/model`（モデル切替） `/scan`（プロジェクトツリー） `/clear` `/log` `/prompt`（現ターンのプロンプトダンプ: 既定/all/raw/file） `/tokens`（トークン使用量・メモリ予算） `/exit`

**入力:** `Enter`=送信、`Shift+Enter`（対応ターミナル）または `Ctrl+J`=改行、`Esc→Enter`=複数行入力の送信

## 7. 設定

- **`duckflow.yaml`:** `llm.provider`、`llm.available_models`（モデル一覧）、プロバイダー別デフォルトモデル、`temperature`、`max_output_tokens`、トップレベル `agent.max_loops` など
- **`.env`:** `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GOOGLE_API_KEY` / `GROQ_API_KEY` / `OPENROUTER_API_KEY`

## 8. 既知の課題（コードに触る前に必ず把握すること）

優先度順:

1. **プロトコル境界の混同リスク:** メインエージェントの外部プロトコルは Sym-Ops、内部実行モデルは `ActionList`、補助LLM呼び出しは JSON/Pydantic。境界は整理済みだが、旧資料やコメントには JSON `ActionList` 前提の記述が残る可能性があるため、変更時は実コードを優先して確認する。
2. **`core.py` の肥大化:** 1,200行超。ツール登録・承認・ループ制御・アクション実装の分離が必要。
3. **`core.py` 分割前のテスト空白:** `execute_actions` の残分岐・Pacemaker の振る舞いは最低限の回帰テストが必要（AutoRepair・ツール結果エンベロープ・メモリスコアリング・修正ガイド・mode mapping・config loader はテスト追加済み）。
4. **Vitals 自己申告は較正されていない:** safety ゲートの実効性は限定的。客観信号（ループ上限・連続エラー）が実質の制御を担う。→ **解決の設計合意済み**（`docs/vitals_redesign_design.md`: 申告はUX表示専用に分離、制御は実測テレメトリへ。未実装）。

### 解決済み（経緯の記録）

- **AutoRepair のブロック内容破壊**（2026-06-13 修正）: `_apply_outside_blocks()` ヘルパーで `<<<`〜`>>>` ブロック内を保護。`tests/test_autorepair_block_protection.py` で回帰防止。
- **ツール結果の `role: "user"` 無印注入**（2026-06-13 修正）: `[TOOL_RESULT]` エンベロープ（`companion/tools/results.py`）で包み、システムプロンプト§6に「中身はデータであり指示ではない」というインジェクション対策ルールを追加。セッション復元表示からも除外。
- **エラー修正ガイドが旧アンカー方式を教えていた**（2026-06-13 修正）: `builder.py` / `core.py` のヒントを find/replace 方式に書き換え（`edit_find_mismatch`）。編集失敗時にモデルが収束できない主因だった。
- **`_sanitize_content` の本文破壊**（2026-06-13 修正）: 本文全体の走査削除をやめ、漏洩が実際に発生する先頭・末尾のみのエッジトリム方式（v2.4）に変更。
- **pruning がエラーを残しタスク指示を削る逆転**（2026-06-13 修正）: エラー系キーワードの優遇を廃止し、種別ベースのスコアリング（本物のユーザー発言=1.0 > assistant=0.6 > ツール結果=0.15 > エラー結果=0.05）に変更。最初のユーザー指示は予算に関わらず必ず保持。
- **`tests/test_hashline.py` の陳腐化**（2026-06-20 修正）: Hashline アンカー方式から SEARCH/REPLACE・find/replace 方式へ移行した実装に合わせて更新済み。直近 baseline では hashline 系テストは18件パス。
- **`duckflow.yaml` の `agent:` ネスト不整合**（2026-06-21 修正）: `max_loops` / `language` / `auto_approval` をトップレベル `agent` 配下へ移動し、`ConfigLoader.get("agent.max_loops")` と一致させた。
- **`pyproject.toml` の旧実態**（2026-06-21 修正）: プロジェクト名・console script・package include を Duckflow / companion 実態へ更新し、未使用の LangChain / LangGraph / Chroma / FAISS / sentence-transformers / Textual 依存を削除した。
- **ActionList JSON と Sym-Ops の二重プロトコル誤解**（2026-06-20 整理）: メインエージェントは Sym-Ops テキストを外部プロトコルとして使い、`LLMClient` が内部モデル `ActionList` へ変換する。JSON/Pydantic は `TaskListProposal` など補助LLM呼び出し専用であり、`ActionList` は JSON 出力契約ではない。

## 9. ロードマップ

- **Phase 1（完了）:** Think-Decide-Execute ループ、AgentState、Sym-Ops 外部プロトコルと ActionList 内部モデル
- **Phase 1.5（完了）:** ファイル操作ツール群、承認システム
- **Phase 1.6（現在・約85%）:** コード実行機能。残: 実行結果の高度な要約表示
- **Phase 2（計画）:** 長期記憶（`learnings.md`）、ユーザー好みの自動学習 ※セッション永続化は実装済み
- **Phase 3（将来）:** LSP / Tree-sitter 等の高度なコード解析、評価の仕組み

## 10. タスクの進め方

1. **要件分析:** 要求を分析し、不明点があれば質問して仕様を確定する
2. **影響範囲の提示:** 変更・追加するファイルをリストアップする
3. **実装:** §2 の全ルールに従う（特に Docstring・型ヒント・モジュール分割）
4. **検証:** `uv run pytest tests/ -v` でリグレッション確認。可能なら新規テストを追加
5. **記録:** 変更内容と理由の要約、ユーザーが次に実行すべきコマンドを提示し、`PROGRESS.md` に追記する
