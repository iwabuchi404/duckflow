# Duckflow 開発進捗記録 (PROGRESS.md)

## 🎯 プロジェクト現状
- **現在のフェーズ**: Phase 1.6 (コード実行機能)
- **全体進捗**: 約 85% (Phase 2 以前)

---

## 📅 更新履歴

### 2026-06-14: SEARCH/REPLACE マーカー形式の実装 (現在)
- `companion/utils/sym_ops.py`: `_fix_unclosed_blocks` を行単位カウントに修正（`<<<<<<< SEARCH` 等のマーカーを誤計上する前提バグ）。
- `companion/tools/file_ops.py`: `edit_file` に SEARCH/REPLACE マーカー形式の抽出を追加（`_parse_search_replace_markers`・寛容文法）。git コンフリクトマーカー検査＋ write_file へのルーティング（`_has_git_conflict_markers`）、REPLACE への漏洩を検出する健全性チェック、共通適用ロジックの `_apply_edits` 抽出。従来 find:/replace: は後方互換で維持。
- `companion/prompts/{few_shot,templates,builder}.py` / `utils/response_format.py`: 例示・ツール説明・Correction Guide・自己検証チェックをマーカー形式へ更新。
- テスト新規: `tests/test_edit_marker_format.py`（8件）、`tests/test_unclosed_blocks_fix.py`（4件）。全99件パス（残失敗は test_hashline.py の既知10件のみ）。
- ベンチ新規: `benchmarks/`（edit_tasks.py / edit_format_bench.py）。オフライン適用層で marker 6/6・legacy 3/5。legacy は共通インデント領域・フォーマットエコーで失敗し、マーカー形式の構造的優位を実証。
- 未了: online（実モデル × tier）A/B（要API鍵）、§7 tier 静的マッピング（config）。

### 2026-06-13: 編集形式ドキュメントにマルチモデル対応(§7)を追記
- `docs/edit_format_search_replace_design.md` に §7「マルチモデル対応（tier別フォーマット選択）」を追加。
- 原則: 形式はシステムが決定しモデルに結びつける（LLMに選ばせない）。モデルは常に1形式のみ見る。
- tier→形式マッピング（強/中=マーカー、弱=replace_function/全体書き換え）をフォールバック階段に統合。tier選択と失敗時降格を単一メカニズム化。
- 入力源は静的config（available_modelsにtierフィールド）→ テレメトリ適応(repair_load)の段階導入。
- 「弱＋中の使い分け」の本命として役割分割（ループ=弱、編集生成=中、SubLLMManager活用）を提示。
- §5ベンチを「形式 × モデルtier」の2次元に拡張し、tier境界を実測で確定する計画に更新。

### 2026-06-13: コード探索とコンテキスト戦略の設計ドキュメント作成
- `docs/code_navigation_context_design.md` 新規。「検索させない」設計（弱いモデルに探索戦略を要求せず、システム側が先回りでコンテキストを組み立てる）を策定。
- 内容: 検索ツールのrg慣習への標準化＋結果整形強化（Phase A）、ast ベースのシンボル層 `list_symbols`/`find_definition`（Phase B）、aider 方式の repo map を状態カードへ先回り注入（Phase C・本命）、`replace_function`（ast 構文検証付き関数単位書き換え、Phase D）。
- 埋め込み RAG ロードマップを正式に廃止（chromadb / faiss-cpu / sentence-transformers のレガシー依存削除を付随タスク化）。
- 実装は未着手。設計合意済みドキュメントはこれで3本（編集形式・Vitals・探索/コンテキスト）。

### 2026-06-13: Vitals 再設計の設計ドキュメント作成
- `docs/vitals_redesign_design.md` 新規。自己申告（UXチャネルとして維持）と実測テレメトリ（制御専用）の二系統に分離する設計を策定。
- 核心: 申告は表示専用＋二重表示（申告/実績の並置でミスマッチを可視化）＋ルーブリック繋留＋応答時のみに頻度削減。制御（Pacemaker・ループ予算）は実測値（success_rate / error_rate / repair_load / progress）ベースへ。decay 廃止、「停滞のない反復は制限しない」原則を採用。
- 実装は Phase A（機能分離）→ B（実測＋二重表示）→ C（ルーブリック）→ D（較正学習・任意）の4段階。未着手。

### 2026-06-13: SEARCH/REPLACE マーカー形式の設計ドキュメント作成
- `docs/edit_format_search_replace_design.md` 新規。deep-research（検証済み16件）の知見に基づき、edit_file の編集ペイロードを aider 型 SEARCH/REPLACE マーカー形式へ移行する設計を策定。
- 核心: 現行 `find: |` 形式の構造的欠陥（共通インデント領域でバイト一致が壊れる）の解消＋学習分布との一致。アクション層 Sym-Ops は変更しない。
- git コンフリクトマーカーとの帯域内衝突（fail-open リスク）に対し、事前検出＋決定的ルーティング（write_file へ誘導）＋健全性チェックの三段防御を設計。
- 実装は未着手。A/B ベンチマーク（コンフリクトタスク必須）で効果量を実測してから全面切り替えを判断する。

### 2026-06-13: マルチターン崩壊・編集失敗の根本原因3点を修正
- `companion/prompts/builder.py` / `companion/core.py`: エラー時の修正ガイドが廃止済みのアンカー方式を教えていた問題を修正。`anchor_mismatch` → `edit_find_mismatch` とし、find/replace 方式（read_file から正確にコピー）のガイドに書き換え。
- `companion/tools/file_ops.py`: `_sanitize_content` を v2.4 エッジトリム方式に変更。本文全体からプロトコル風の行（単独 `>>>` 等）を削除する破壊的動作をやめ、漏洩が実際に発生するコンテンツ先頭・末尾のみを除去。
- `companion/modules/memory.py`: pruning スコアリングを種別ベースに刷新。エラー系キーワード（error/failed等）の優遇を廃止し、本物のユーザー発言(1.0) > assistant(0.6) > ツール結果(0.15) > エラー結果(0.05) の順で保持。`_is_genuine_user_message()` 追加。最初のユーザー指示は予算に関わらず必ず保持（ピン留め）。
- テスト: `tests/test_memory_scoring.py`（19件）、`tests/test_correction_guide.py`（7件）新規。`tests/test_robust_file_ops.py` の sanitize 系3件を v2.4 仕様に書き直し。**87件パス**（残る失敗は test_hashline.py の既知陳腐化10件のみ）。

### 2026-06-13: AutoRepair ブロック保護 + ツール結果エンベロープ実装
- `companion/utils/sym_ops.py`: AutoRepair が `<<<`～`>>>` ブロック内のファイル内容を書き換えるバグを修正。`_apply_outside_blocks()` ヘルパーを追加し、`_fix_missing_symbols` / `_fix_markdown_blocks` / `_fix_vitals_format` をブロック保護対応に。`_fix_delimiters` の無条件 ``` 変換を除去。`ACTION_VERBS` に欠落していた `write_file` を追加。
- `companion/tools/results.py`: `[TOOL_RESULT]` エンベロープ（`wrap_tool_result()` / `is_tool_result_message()`）を追加。
- `companion/core.py`: ツール結果（成功・エラー）をエンベロープで包んで履歴注入するよう変更。セッション復元時の会話表示からツール結果・システム通知を除外。
- `companion/utils/response_format.py`: システムプロンプトに §6 Tool Results（エンベロープの意味とプロンプトインジェクション対策）を追加。
- テスト新規: `tests/test_autorepair_block_protection.py`（23件）、`tests/test_tool_result_envelope.py`（17件）。全64件パス。
- 既知: `test_hashline.py` / `test_robust_file_ops.py` の12件失敗は edit_file の find/replace 方式移行に未追従の既存問題（今回のリグレッションではない）。

### 2026-06-13: ドキュメント一斉更新
- `CLAUDE.md` を v4 実態（companion パッケージ / Think-Decide-Execute ループ / Sym-Ops）に合わせて全面改訂。旧 codecrafter / LangGraph 前提の記述を撤廃し、既知の課題リストを追加。
- `README.md` を修正: バージョン表記を Phase 1.6 に更新、存在しない `codecrafter/`・`config/` ディレクトリへの言及を削除、`config.yaml` 参照を `duckflow.yaml` に修正、起動コマンドに `-X utf8` を付与。

### 2026-02-23: セッション永続化 実装完了
- `companion/modules/session_manager.py` 新規: SessionManager クラス（保存・復元・一覧）
- `companion/state/agent_state.py`: `session_id`, `created_at`, `last_active`, `turn_count` フィールド追加。`to_session_dict()`, `from_session_dict()`, `touch()` メソッド追加。
- `companion/modules/memory.py`: `restore_with_summary()` + `_summarize_session()` 追加。大きなセッション復元時にLLMが古い履歴を一括要約して先頭に挿入。
- `companion/core.py`: `DuckAgent.__init__` に `session_manager`, `resume_state` パラメータ追加。ターン完了後に自動保存。復元時に MemoryManager で圧縮。
- `main.py`: 起動時セッション選択UI（`--no-session` フラグも追加）。
- **使い方:** `uv run python -X utf8 main.py` → 前回セッション継続を選択可能。`--no-session` で常に新規起動。

### 2026-02-23: Sym-Ops v3.2 実装完了
- `companion/state/agent_state.py`: AgentMode enum, InvestigationState, Vitals v3.1 (confidence/safety/memory/focus) を実装。
- `companion/utils/sym_ops.py`: Sym-Ops v3.2 全対応
  - `execute_batch` アクション（%%% 区切り）の追加
  - `>>>` の行頭（column 0）のみブロック終端として認識（Python doctest 保護）
  - `_fix_indentation()` をブロック内インデント保護対応に修正
  - `---` の AutoRepair 変換を削除（Markdown 水平線との衝突回避）
  - `execute_batch` を `action_verbs` に追加
- `companion/ui/console.py`: Vitals v3.1 表示（4項目）, Safety Warning 追加。
- `companion/modules/pacemaker.py`: Vitals v3.1 対応, InvestigationStuck 検知。
- `companion/core.py`: Safety Score Interceptor, Investigation ツール登録。
- `companion/prompts/system.py`: INVESTIGATION_MODE_INSTRUCTIONS, 3モード分離。
- `companion/utils/response_format.py`: SYMOPS_SYSTEM_PROMPT を v3.2 仕様に更新。

### 2026-02-22: ドキュメントの一斉アップデート
- `README.md` を Duckflow v4 Architecture に合わせて更新。
- `DUCKFLOW_IMPLEMENTATION_DETAILS.md` を最新のプロトコル (ActionList) に合わせて刷新。
- `duckflow.yaml` を中心とした設定系ドキュメントの整理。
- `PROGRESS.md` の新規作成。

### 2026-02-xx: Phase 1.5 完了
- 基本的なファイル操作（read, write, list, mkdir, delete）の統合。
- `companion/tools/file_ops.py` の実装。
- 承認システム（Overwrite確認など）の基本実装。

### 2026-02-xx: Duckflow v4 始動 (Phase 1 完了)
- 旧 `codecrafter` から `companion` パッケージへの移行を開始。
- シンプルな `Think-Decide-Execute` ループの実装。
- Pydantic による `AgentState` の定義。
- `ActionList` ベースのアクションプロトコル採用。

---

## 📝 進行中のタスク (Phase 1.6)
- [x] Pythonファイルの実行機能 (`run_command` 経由)
- [ ] 実行結果のより高度な要約表示
- [ ] インタラクティブな実行環境（将来）

## 🚀 次の目標 (Phase 2)
- [ ] `learnings.md` 実装（長期記憶）
- [ ] セッション間履歴の永続化
- [ ] ユーザーの好みの自動学習
