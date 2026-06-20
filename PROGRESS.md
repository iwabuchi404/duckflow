# Duckflow 開発進捗記録 (PROGRESS.md)

## 🎯 プロジェクト現状
- **現在のフェーズ**: Phase 1.6 (コード実行機能)
- **全体進捗**: 約 85% (Phase 2 以前)

---

## 📅 更新履歴

### 2026-06-20: pytest テスト配置と import 初期化の整理
- `tests/test_generate_code.py` は pytest に収集されない一方、外部LLM接続を使う手動評価スクリプトだったため、`scripts/manual/generate_code_eval.py` へ移動。`tests/` 配下は自動テスト専用に近づけた。
- `tests/conftest.py` を追加し、repo root の `sys.path` 初期化を一箇所へ集約。各テストファイルに散っていた `sys.path.append(os.getcwd())` と不要な `os` / `sys` import を削除。
- `tests/test_response_format.py` から print ベースの手動実行表示と `if __name__ == "__main__"` ブロックを削除し、assertion ベースの通常 pytest テストに整理。
- 複数テストファイルに残っていた `if __name__ == "__main__": pytest.main(...)` ブロックを削除し、pytest 実行前提に統一。
- 検証: `uv run pytest tests/test_response_format.py tests/test_priority_fixes.py -v` で8件パス。`uv run pytest tests/ -v` で144件パス / 1件スキップ。

### 2026-06-20: ActionList/Sym-Ops プロトコル境界の命名整理
- `companion/base/llm_client.py`: `LLMClient` の docstring と `_parse_response()` 説明を更新。メインエージェント呼び出しは Sym-Ops テキストを外部プロトコルとして受け取り、内部実行モデル `ActionList` へ変換すること、`TaskListProposal` / `ExecutionSummary` / `SummaryResponse` など非 `ActionList` の `response_model` だけが JSON/Pydantic 構造化レスポンスであることを明記。
- `companion/state/agent_state.py`: `ActionList` を「LLM JSON 出力」ではなく「Sym-Ops parse 後の内部アクションコンテナ」として説明を更新。
- `companion/tools/task_tool.py`: `generate_tasks()` の補助LLMプロンプトから Sym-Ops 出力を連想させる文言を削り、JSON task proposal としての境界を明確化。
- `AGENTS.md` / `CLAUDE.md`: 「JSON `ActionList` と Sym-Ops の二重プロトコル併存」という古い表現を、外部 Sym-Ops / 内部 `ActionList` / 補助 JSON の境界説明へ更新。旧資料に残る JSON `ActionList` 前提は実コード優先で確認する注意に差し替え。
- 未収集だった `tests/verify_task_tool_symops.py` を `tests/test_task_tool_symops.py` に変換し、`TaskTool.generate_tasks()` が補助 JSON 経路を使い、戻り値を Sym-Ops tool result として整形できることを assertion ベースで検証。
- `tests/test_priority_fixes.py`: `response_model=ActionList` が JSON ではなく Sym-Ops を parse する境界テストを追加。
- 検証: `uv run pytest tests/test_priority_fixes.py tests/test_task_tool_symops.py -v` で6件パス。`uv run pytest tests/ -v` で144件パス / 1件スキップ。

### 2026-06-20: get_project_tree の workspace safety 修正
- `companion/tools/get_project_tree.py`: `os.path.abspath(path)` で任意パスを探索できていた実装を、`workspace_root` 基準の `_resolve_within_workspace()` に変更。`..` や絶対パスで workspace 外へ出る指定は `Duck Keeper Alert` として拒否する。
- symlink などの探索中エントリも `resolve()` 後に workspace 内か確認し、外部を指すものはスキップ。`__pycache__` / `node_modules` / `dist` / `build` / `*.egg-info` 等のノイズディレクトリも非表示に統一。
- `respect_gitignore` が文字列で渡された場合に `"false"` が truthy になる問題を `_coerce_bool()` で修正。
- テスト新規: `tests/test_get_project_tree_safety.py`（通常ツリー取得、`..` escape、絶対パス escape、外部 symlink、ノイズディレクトリ除外、`respect_gitignore="false"`）。
- 検証: `uv run pytest tests/test_get_project_tree_safety.py tests/test_file_ops_noise_dirs.py -v` で12件パス / 1件スキップ（Windows symlink availability）。`uv run pytest tests/ -v` で142件パス / 1件スキップ。

### 2026-06-20: test_hashline.py の陳腐化解消
- `tests/test_hashline.py` を現行仕様に合わせて全面整理。`HashlineHelper` の低レベルな hash anchor 単体テストは維持しつつ、`FileOps` 統合テストは廃止済みの anchor edit 前提から、現在の `read_file` 行番号表示（`行番号|内容`）、`edit_file` SEARCH/REPLACE マーカー形式、`delete_lines` find スニペット指定へ更新。
- 旧期待値（`Successfully edited` + anchor context / `Hash mismatch` / `anchors` エラー等）を、現行実装の `find_not_matched`、`No 'find' snippet`、`--- Updated Context ---` に合わせて修正。
- 検証: `uv run pytest tests/test_hashline.py -v` で18件パス。`uv run pytest tests/ -v` で137件すべてパス。既知失敗なし。

### 2026-06-18: grep_files の不安定さ（YAML誤判定・.pycノイズ）を修正
- ユーザー報告: 「grepツールの不安定さ: パラメータエラーや.pycノイズで検証ループが止まらなくなった。`include="*.py"`」「検証ループの暴走: grep結果が期待と違う時に同じアクションを繰り返してしまった」。
- 根本原因（パラメータエラー）: `companion/utils/sym_ops.py` の `_extract_yaml_frontmatter()` は、YAMLフロントマターを `yaml.safe_load()` でパースしている。`include: *.py` のように glob パターンを引用符なしで書くと、PyYAML が先頭の `*` を**エイリアス参照**（`&anchor` の再利用）構文と誤解釈し `yaml.YAMLError` を送出する。実機検証で確認:
  ```
  yaml.safe_load("pattern: \"TODO\"\ninclude: *.py\npath: \"companion\"")
  → YAMLError: while scanning an alias ... expected alphabetic or numeric character, but found '.'
  ```
  さらに従来の例外処理は `except yaml.YAMLError: return {}, content` と**全パラメータを握りつぶす**実装だったため、`include` だけでなく `pattern`/`path` まで丸ごと消失し、`grep_files` がデフォルト引数（`include='*'`, `path='.'` 等）で実行されていた。
- 根本原因（.pycノイズ）: 上記によりパラメータが消失すると `include` がデフォルトの `'*'` にフォールバックし全ファイルが対象になる。`find_files`/`grep_files`（`companion/tools/file_ops.py`）のディレクトリ走査は従来ドット始まり（`.git` 等）のみを除外しており、`__pycache__` や `node_modules` は除外対象外だったため、`.pyc` バイナリが `errors='ignore'` でテキストとして開かれ文字化けノイズがマッチ結果に混入していた。
- 修正:
  1. `_extract_yaml_frontmatter()` に `_quote_unquoted_glob_values()` を追加し、`yaml.safe_load()` に渡す前に `*` で始まる未クォート値を自動的にダブルクォートで囲んで事前修正（典型ミスの救済）。
  2. それでも未知のYAML構文エラーが残る場合に備え、全損ではなく `_fallback_parse_key_value_lines()` による行単位の `key: value` 抽出フォールバックを追加（部分的にでもパラメータを救済）。
  3. `companion/tools/file_ops.py` に `NOISE_DIR_NAMES`（`__pycache__`, `node_modules`, `dist`, `build`, `egg-info`）と `*.egg-info` の suffix 判定を追加し、`find_files`/`grep_files` 両方のディレクトリ走査で除外（`include` のパース結果に関わらない多層防御）。
- 検証ループの暴走について: `companion/modules/pacemaker.py` の `DuckPacemaker._detect_stagnation()` に、直近4アクションの完全一致（アクション名＋パラメータ、または結果文字列）を検知して `STAGNATION` 介入（LLMに状況説明をさせ `::response` でユーザーに選択肢を提示）を行う仕組みが既に実装されており、`core.py` の自律ループからも正しく呼び出されている（`check_health()` を毎ループLLM呼び出し前に実行）。今回のYAMLバグにより `grep_files` 呼び出しのたびに実際に渡る `parameters` が「成功時はそのまま／失敗時はデフォルトにフォールバック」と**揺れていた**ため、`_detect_stagnation()` の厳密な完全一致判定が同一試行とみなせず、既存の暴走防止機構が機能していなかった可能性が高いと判断。新規のコード追加はせず、まずは根本原因（パラメータの不安定なパース）の修正で様子を見る方針（過剰実装回避）。再発する場合は別途相談。
- テスト新規: `tests/test_yaml_frontmatter_glob.py`（5件: 未クォートglob救済、クォート済み回帰防止、別拡張子、フォールバック部分救済、フロントマターなし回帰防止）、`tests/test_file_ops_noise_dirs.py`（7件: `__pycache__`/`node_modules`/`*.egg-info` 除外、通常ファイルは引き続き検出される回帰防止）。
- 検証: 関連39件パス。`uv run pytest tests/ -v` で127件パス / 既知の `tests/test_hashline.py` 10件失敗のみ。

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
