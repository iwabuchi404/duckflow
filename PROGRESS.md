# Duckflow 開発進捗記録 (PROGRESS.md)

## 🎯 プロジェクト現状
- **現在のフェーズ**: Phase 1.6 (コード実行機能)
- **全体進捗**: 約 85% (Phase 2 以前)

---

## 📅 更新履歴

### 2026-06-17: emergency_mode 発生時のLLM通知を追加
- 背景: 「`MAX_CONSECUTIVE_ERRORS`緩和」「emergency_mode発生時のLLM通知」の2案を比較検討し、前者は1ターン内（execute_actions一回分）のfail-fastで効果が読みにくく逆効果リスクもあるため見送り、後者のみユーザー承認のうえ実装。
- `companion/modules/memory.py` の `prune_history` は、トークン予算を100%超過し要約を挟まず強制削減した場合 `stats["emergency_mode"] = True` を返すが、呼び出し側2箇所が握り潰していた:
  - `companion/core.py`（自律ループ内pruning、L479-482）: 戻り値の stats を `_` で破棄。
  - `companion/state/agent_state.py`（`add_message_with_pruning`、L191-198）: stats は受け取るが `pass` で何もしていなかった。
  - → 文脈が要約なしで突然削られても、LLMには一切知らされず、Phase 1で追加した推論履歴自体が予告なく消えうる経路が残っていた。
- 修正: 両呼び出し箇所で `stats.get("emergency_mode")` を確認し、True の場合は `[SYSTEM] 緊急メモリ整理を実行しました（要約なしで{removed_count}件の古いメッセージを削除）。直前までの文脈の一部が失われている可能性があります。タスクの前提や対象ファイルの状態を、必要に応じて read_file 等で再確認してから続行してください。` を `"user"` ロールで会話履歴に追加するよう変更。
- テスト新規: `tests/test_emergency_mode_notification.py`（2件）。`add_message_with_pruning` が emergency_mode 時に通知メッセージを追加すること／通常時は追加しないことを検証。
- 検証: `uv run pytest tests/ -v` で 115件パス（既存113+新規2） / 既知の `tests/test_hashline.py` 10件失敗のみ。新規リグレッションなし。
- 見送り: `MAX_CONSECUTIVE_ERRORS=2` の緩和（理由は上記）。

### 2026-06-17: Rich markup によるクラッシュ修正（[TOOL_RESULT] エンベロープ誤判定）
- 症状: 特定の指示でアプリが `rich.errors.MarkupError: closing tag '[/TOOL_RESULT]' at position N doesn't match any open tag` でクラッシュ。
- 原因: `companion/ui/console.py` の `print_error`/`print_warning`/`print_info`/`print_system`/`print_user`/`print_thinking`/`print_action`/`print_result`/`add_log`/`request_confirmation` が、ツール結果やLLM応答など動的な文字列を `console.print(f"[style]{message}[/style]")` のように markup 有効のまま埋め込んでいた。`companion/tools/results.py` の `[TOOL_RESULT]`/`[/TOOL_RESULT]` エンベロープ文字列がエラーメッセージ等に含まれると、Rich がこれを「対応する開始タグの無い閉じタグ」として誤判定し例外を送出していた（内部識別タグがUI表示層で“判定”されてしまう問題）。
- 修正: `rich.markup.escape()` を import し、上記メソッドの動的部分を全て `escape(...)` でラップ。スタイルタグ自体（`[info]` 等の静的部分）はそのまま維持し、ユーザー/ツール由来の可変文字列のみエスケープする方針。
- 追加調査: `Panel(plain_str)` も同様に文字列を markup 解釈することを実機確認（`rich.errors.MarkupError` 再現）。同様のパターンを横断調査し、以下も修正:
  - `companion/ui/console.py`: `print_conversation_message`（セッション復元時の会話表示、および実際のAI応答表示 `core.py:968` で使用。型ヒント表記 `Dict[str, Any]` 等、ツール結果に限らず任意の角括弧でクラッシュしうる経路だったため対応）。
  - `companion/modules/command_handler.py`: `/model current` の `info_text`（`Panel(info_text, ...)` に平文字列を渡しており、provider/model/base_url の値に角括弧が含まれるとクラッシュしうる）。`escape()` 追加。
  - `companion/core.py` (`action_run_command`) / `companion/tools/sub_llm_tools.py`: 呼び出し側で `[bold]...[/bold]` を独自に埋め込んでいた箇所は、`print_*` 側で全文エスケープされるようになり装飾が無効化（表示崩れ）するため、埋め込みタグを除去してクリーンな文字列に整理（クラッシュではなく見た目の整合性のため）。
- テスト新規: `tests/test_console_markup_escape.py`（6件）。`[TOOL_RESULT]`/`[/TOOL_RESULT]` を含む文字列を各表示メソッドに渡しても例外が出ないことを検証。
- 検証: `uv run pytest tests/ -v` で 113件パス（既存107+新規6） / 既知の `tests/test_hashline.py` 10件失敗のみ。新規リグレッションなし。

### 2026-06-17: モード遷移修正の再適用（ドキュメント連動）
- 経緯: 2026-06-16付「Duckflow自己修正差分の仕上げ」で、仮説上限5回化・planningモードでの編集ツール開放が「現行仕様に戻す」として元の挙動（仮説2回・編集はtaskモードのみ）にリバートされていた。原因は `CLAUDE.md` 側（§3 3モード制）の記述がコード変更時に未更新のままだったこと（仕様書を正として参照する自己修正により、コード側が仕様書に合わせて巻き戻された）と判断。ユーザー確認の上、コードとドキュメントを揃えて再修正。
- `companion/core.py`:
  - `MODE_TOOL_MAPPING["planning"]` に `edit_file` / `write_file` / `delete_lines` / `delete_file` を再度追加。
  - `action_submit_hypothesis` の `MAX_HYPOTHESIS_ATTEMPTS` を 2 → 5 に再変更。ステータス表示（`Hypotheses: n/5`）も追従。
  - `action_finish_investigation` の戻りメッセージを「`propose_plan` のみ示唆」から「`edit_file`/`write_file` で直接修正可、複数手順が必要なら `propose_plan`」に再変更。
- `D:\work\duckflow\CLAUDE.md`（§3 3モード制）: 「仮説2回失敗」→「仮説5回失敗（2026-06-17改訂、旧仕様は2回）」に更新。Planningモードが編集系ツールを公開する旨を明記し、taskモードとの違い（タスク完了管理・execute_tasks等）を補足。**今後同様の自己修正リバートを防ぐため、コード変更時は本ドキュメントも必ず同時更新すること。**
- `tests/test_core_mode_mapping.py`: `test_planning_mode_does_not_expose_edit_tools`（旧仕様固定用に追加されていたテスト）を `test_planning_mode_exposes_edit_tools` に書き換え、新仕様（planningモードが編集ツールのスーパーセットを含むこと）を検証するよう変更。
- 検証: `uv run pytest tests/ -v` で 107件パス / 10件失敗（すべて既知の `tests/test_hashline.py`）。新規リグレッションなし。

### 2026-06-17: マルチターン文脈維持 Phase 1（推論・アクション履歴の保存）
- 背景: `docs/plans/multi_turn_context_fix_plan.md` をレビュー（Phase2/3は前提が現状と食い違い・既に解消済みのため見送り、Phase5は対象箇所が計画記載の4件ではなく9件あることを確認、Phase4は範囲を過大記載と判定）。今回はユーザー承認のもと最優先の Phase 1 のみ実装。
- `companion/core.py`: `execute_actions` の末尾（`return results` 直前）で、LLMの `reasoning` と実行したアクション一覧を `"assistant"` ロールとして会話履歴に追加するよう変更。新規メソッド `_build_action_summary(action_list: ActionList) -> str` を追加（`>> {reasoning}` と `:: {action.name} @{target}` 形式で整形）。
  - 目的: 従来はツール結果のみ履歴に残り、LLMが前ターンで「何を考え、なぜそのアクションを選んだか」を次ターンで参照できず、複数ターンタスクで一貫性を失っていた問題への対処。
- `tests/test_tool_result_envelope.py`: 上記変更により `test_execute_actions_wraps_result_in_envelope` が破損（ツール結果メッセージが履歴の最後ではなく最後から2番目になったため）。`conversation_history[-2]`（ツール結果・role="user"・エンベロープ確認）と `conversation_history[-1]`（新規アクション概要・role="assistant"・アクション名を含むこと）を検証するよう修正。
- 検証: `uv run pytest tests/ -v` で 107件パス / 10件失敗（すべて既知の `tests/test_hashline.py`、find/replace方式への移行未追従によるもの・リグレッションではない）。新規リグレッションなし。
- 未着手（計画書 Phase 2〜5、今回は見送り）: ツール結果ロールの "system" 化（Phase 2、既存のエンベロープ機構で実質解消済みと判断）、`::note` の履歴追加（Phase 3、`add_message` の汎用機構で既に対応済みと判断）、fail-fast 中断時の構造化エラーメッセージ（Phase 4）、`sym_ops.py` 内 `rstrip() == '>>>'` 残存9箇所の統一（Phase 5）。

### 2026-06-16: Duckflow自己修正差分の仕上げ
- `companion/execution/runner.py`: `CodeRunner.run_python_file()` を shell 文字列直渡しから `asyncio.create_subprocess_exec()` に変更。スペース入りパスでも壊れないようにし、`-X utf8` 付きで現在の Python 実行環境を使う。実行結果は `summarize_result(stdout, stderr, exit_code)` で要約して返す。
- `companion/utils/sym_ops.py`: Duckflow が厳格化したブロック終端判定を既存 parser / テストと整合する形へ修正。インデント付き `>>>` は終端にせず、列0の `>>>` は末尾空白付きでも終端として扱う。
- `companion/core.py`: Duckflow が追加した自律ループ中 pruning と Investigation ブロック結果の履歴フィードバックは維持。planning モードでの編集ツール開放と仮説上限5回化は、現行仕様（編集は task モード、仮説2回で duck_call）に戻した。
- テスト新規: `tests/test_code_runner.py`（2件）。スペース入りパスの Python 実行と失敗時 stderr 要約を検証。
- 検証: 関連31件パス。全体は107件パス / 既知の `tests/test_hashline.py` 10件失敗のみ。

### 2026-06-16: ドキュメント整理・Context Mixer ナレッジの全面更新 (現在)
- **Context Mixer (duckflow コレクション)**: `context` / `spec` / `decisions` の3ドキュメントが全て 2025-08-13（5ノード LangGraph 時代）で凍結していた問題を解消。
  - `context`: Phase 1.6 現状に全面書き直し（直近の完了事項・未解決3本・既知の課題・次の目標）。コレクション説明文が「Python + LangGraph 5ノード」のまま更新できない（Context Mixer MCP の制約）ため、冒頭で現状を明記して代替。
  - `spec`: v4 実態（companion / Think-Decide-Execute / Sym-Ops v3.2 / 3モード / SEARCH/REPLACE マーカー形式 / 多層防御 / Vitals & Pacemaker / ツール一覧 / 技術スタック / ディレクトリ構成）に全面書き直し。
  - `decisions`: 過去3件（LangGraph 時代）を保持しつつ、v4 移行の決定7件（LangGraph 撤回 / companion 移行 / Sym-Ops v3.2 採用 / edit marker 形式採用 / Vitals 再設計合意 / 埋め込み RAG 廃止 / セッション永続化）を追記。
- **ローカル docs/ 整理**: 陳腐化ドキュメント16件（docs/直下12件 + ルート4件）を `docs/old/` へ移動（**削除せず保持**）。Sym-Ops v1/v2・duckflow_format・design-docs_v6・前処理パターン補正・codecrafter_design_review・DUCKFLOW_IMPLEMENTATION_DETAILS・NEXT_STEPS_ROADMAP・OBSOLETE_FILES_REPORT 等。docs/直下は現行6件のみ残存、docs/old/ は71件へ。既存の reports/ / proposals/ / plans_archive/ はそのまま。
- **AGENTS.md**: v1.2（ステップ1・LangGraph 7ノード計画・`codecrafter/` 前提）から CLAUDE.md(v2.0) の v4 実態に同期して全面書き直し。全AIエージェント共通指示書（aider 等）として CLAUDE.md と同一内容を維持する運用に。
- ※本作業はドキュメントのみ（プロダクトコード・テスト不変更）。

### 2026-06-14: SEARCH/REPLACE マーカー形式の実装
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
