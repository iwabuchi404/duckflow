### 2026-09-19: Holdout v1 初回フルラン（4課題×3モデル×3回=36試行）
- 結果: **DS 12/12・GLM 8/12・LFM 4/12**。ベースライン `evals/baselines/holdout-v1-main3.json`。
- **一般化判定**: DS は holdout でも全通過 — dev 18/18 は過適合でなく実力。GLM 67%（dev 78%）は妥当な低下幅、LFM 33%（dev 33%）は一致 — 改善が dev 専用パターンへの過適合でなかったことを確認。
- GLM 詳細: `spec-build-stats` 3/3（dev spec-build の timeout 型が消えた）、`recover-trio` 2/3、`move-symbol` 2/3（r1 は1レスポンス814アクション出力の新記録・dedupで808除去）、**`no-change-cache` 1/3** — restraint 失敗が holdout でも再現（「リーク」を2回修正してしまった）。モデル固有の弱点として確定。
- LFM 詳細: `spec-build-stats` 2/3、`move-symbol`/`no-change-cache` 各1/3、`recover-trio` 0/3（収束不能）。
- **新発見のハーネス側ギャップ**: ①`replace_function` は `/workspace` 正規化対象外で File not found（正規化カバレッジの穴）、②`cd /workspace` が run_command のシェル側で解決不能（LFM が繰返し消費する最大コスト要因）、③LFM が find パラメータに `\n`/`\.` をリテラル記述する癖（正規表現エスケープ混同、モデル側起因）。

### 2026-09-19: 停滞ゲート実装（A型メタchurn＋C型空ターン、B型は既存timeoutで十分と結論）
- **背景**: GLM v3 の残り4失敗が全て「エラーなし停滞」型だった — spec-build r2 は propose_plan 連発でtimeout、no-change-hard r2 は空応答でLOOP_EXHAUSTED。既存の停滞検知は propose_plan を「内容が毎回異なりうる」として明示除外し、空応答ターンは `consecutive_errors==0` のため no_progress_count をリセットしていた（根本原因特定）。
- **A型（メタアクションchurn）**: `pacemaker.py` に `META_ACTIONS`（propose_plan/generate_tasks/mark_*/note）連続ストリークを追加。CONTROL（response/exit/duck_call）は中立（増やさずリセットもしない）。3回連続で `no_progress_stall` Correction Guide警告、4回以降は `check_stall_block` が実行前拒否し三択（実アクション/`::response`/`::duck_call`）を提示。ブロックはエラー記録されるため持続churnはERROR_CASCADEに自然接続。
- **C型（空ターン）**: `core_loop_helpers.py` に `turn_was_unproductive()` を追加 — 「スキップされたresponse（empty/auto/premature）のみで実アクションなし」のターンを検出し、`core.py` の既存 no_progress→duck_call 漏斗（3回）に合流。新規カウンタ不要の最小実装。
- **B型（応答が巨大/低速）**: 実装せず。「応答が長い」は故障ではなくモデル速度特性 — 既存の2層timeout（リクエスト`llm_timeout_seconds`＋ラン`timeout_seconds`、共に設定値）で十分。タイムアウトは `status="timeout"` として分類記録済み。ハング検出・ストリーム監視は複雑さに見合わず見送り。
- 設計判断: 「止められるものは構造的に止め、治せないものは分類つきで早期に諦める」— A+Bの連発対策と同思想。propose_plan は正当なアクションなので一律ブロックせず、通知→行動空間制限の2段階。
- テスト: `tests/test_stall_gate.py`（16件）— ストリーク増減・制御アクション中立・warn/block閾値・ブロック持続・turn_was_unproductive全分岐。全スイート **838 passed / 2 skipped**。

### 2026-09-19: ambiguous-spontaneous 再評価（0/9不変）＋ Holdout Gauntlet 4課題新設
- **ambiguous-spontaneous 再評価**（Main3×3回、現行コード）: DS/GLM/LFM いずれも **0/3**。全モデルが「必要な商品」の曖昧さを認識せず全商品を推測出力（GLM r3 は "This is a CLEAR task. No ambiguity" と明確に誤判断）。prematureガード/パス正規化/連発対策は意味判断の欠陥に効かない — ambiguous-gauntlet（明示指示あり、全モデル高パス）と spontaneous（指示なし、全滅）が別物であることが実証され、H-1/Decision Engine 担当の意味判断層の空白を確認。結果 `evals/results/spontaneous-v3/`。
- **Holdout Gauntlet 新設**（`evals/scenarios/holdout/`）: dev gauntlet への過適合を検出するため、同能力軸・別失敗パターンの4課題を凍結セットとして追加（`--all` には含まれず、明示 `--scenario` 指定のみ・マイルストーン時のみ実行）。
  - `move-symbol`（rename-hard軸）: 関数を新モジュールへ移動＋import更新＋新規ファイル作成。罠: calc.py の compute_total が内部で compute_tax を参照（移動後に NameError となる潜在バグ、自発検出を試す）
  - `recover-trio`（recover-quad軸）: 異なるバグクラス — ミュータブルデフォルト引数・`%`/`//` 誤演算子・欠落依存 termcolor（requirements.txt 機構で毎run自動アンインストール）
  - `no-change-cache`（no-change-hard軸）: 「メモリリーク」報告だがTTL無しは文書化された仕様。workspace_unmodified + report_contains
  - `spec-build-stats`（spec-build軸）: summarize() 実装＋USAGE.md 例追記（複数成果物）
- 未カバー軸: 探索効率（needle）— fixture コストが高いため将来課題
- ローカル検証: 全YAMLロード・初期状態でfix/build系は失敗・no-changeは全通過・参照解でverify通過。move-symbol を DS で1回スモーク → 6ループでPASS（移動後に潜在NameErrorを自発検出して修正 — 罠が設計通り機能）
- 採注設計: checks の file_not_contains は**バグ行全体**（シグネチャ/return文）を対象化し、正当な修正形（`items=None`・`math.ceil`・`"\n".join` 等）との衝突を回避。recover-quad の `price *` チューニング教訓を反映。

### 2026-09-19: Gauntlet v3 実行（A+B検証、Main3×6課題×3回）＋ defect-level ブロック拡張
- 結果（v2→v3）: **DS 16/18→18/18・GLM 16/18→14/18・LFM 4/18→6/18**（v2の4件は真空パス3+実質1、v3の6件は全て正当パス）。ベースライン `evals/baselines/gauntlet-v3-main3.json` 保存（無効モデルIDの即失敗36件は除外）。
- premature応答ガードの効果: DS の唯一の失敗型（宣言だけして応答）が消滅し全通過。
- パス正規化の効果: LFM の `/workspace/...`・`/tmp/...` パスが全て正常に workspace 内へ解決し、ambiguous 0/3→2/3・recover 1/3→2/3・spec-build 0/3→1/3。`report_contains` は GLM の無報告ランを正しくfail判定。
- GLM の分析（rename-hard r1）: store/api は edit 成功後に degraded し、cli→worker→reports×3 の**ファイル名を回転させた空body連発**に。エスカレーションガイドは発火（kind=3で強化注入）したが無視され、verbatimブロックは reports.py が3回止まり（4回目必要）で未発火、カスケードは kind=5 に最終ループで到達するも check_health 前に終了。**回転ターゲットは verbatim シグネチャを回避する**ギャップを特定。
- 対応 — defect-level ブロック追加（`pacemaker.py`）: `check_repeat_block` を拡張し、verbatim 未満でも「ツールの dominant contract error kind ≥3 かつ新規呼出しが同じ形の欠陥を持つ」場合は実行前拒否。`_call_has_same_defect` は呼出し自体から検査可能な欠陥のみ判定（現状は edit_file 空body — find パラメータや SEARCH/find: を含む正規形は脱出経路として通す）。「outside workspace」等パラメータ修正で治る kind は対象外（誤ブロック防止）。失敗シナリオのトークンは v2→v3 で25-40%削減（recover 131k→79k, rename 132k→95k）。
- GLM 残課題: v3 の失敗は repeat 機構の適用外の別機序 — recover r1/spec r2 は LLM 応答自体が巨大・低速なタイムアウト、no-change r2 は無報告でのループ枯渇。
- テスト: `test_repeated_failure_block.py` に defect-block 3件追加（回転ターゲット捕捉・正規body/find形式の非ブロック・検査不能kindの非ブロック）。**822 passed / 2 skipped**。

### 2026-09-19: 同一失敗のターン跨ぎ連発への段階エスカレーション（A+B実装）
- 背景: GLM rename-hard で空body edit_file が6連発（142k/93k tokens消費）。Correction Guideはターン限りの助言で、連続エラーカウンタは成功を挟むとリセットされるため捉えられなかった。
- 失敗シグネチャ追跡（`companion/modules/pacemaker.py`）: `_call_failures`（tool+正規化params）と `_kind_failures`（tool+error kind）を新設。`consecutive_errors` と違い成功を挟んでも持続し、成功はそのツールのカウンタのみリセット（read_file成功がedit_file失敗を帳消しにしない）。`_error_kind` は `Reason:` 行またはペイロード先頭から正規化抽出。
- 3段階エスカレーション: (1) 3回目の同一失敗で `repeated_failure` SyntaxErrorInfo を追加し Correction Guide を「STOP: 同じ呼出しは成功しない、read_fileしてから別形式で」と強化、(2) 4回目以降の verbatim 繰返しは `check_repeat_block` が**実行前に拒否**（`[BLOCKED]` メッセージ＋read_file→別形式の回復手順）、(3) 同一シグネチャ失敗5回で ERROR_CASCADE を発火（成功交じりでも検出、従来の連続3回/10回中5回と併存）。
- 安全性設計: ハードブロックは contract エラー（形式/パラメータ/権限の決定的失敗）のみ — `find_not_matched`・pytest exit code 等の状態依存エラーは workspace 変更で成功し得るため絶対ブロックしない。別引数の正当な試行錯誤はシグネチャが異なり誤判定しない。native protocol は `_record_native_event`/`sanitize_tool_references` 経由で中立。
- 実装箇所: `core_action_executor.py`（実行前ブロック＋`_handle_error` 内エスカレーション）、`core_action_results.py`（`build_repeated_failure_syntax_error`）、`builder.py`（symops/native 両 Correction Guide に `repeated_failure` 例）。
- テスト: 新規 `tests/test_repeated_failure_block.py` 12件 — シグネチャ集計・別引数非グループ化・成功交じり持続・同ツール成功リセット・ブロック発火/閾値未満・状態依存エラー非ブロック・エスカレーション3回目・成功交じりカスケード・多様失敗非カスケード・reset・contract分類。
- 検証: `uv run python -X utf8 -m pytest tests/ -q` → **819 passed / 2 skipped**（807から+12）。

### 2026-09-19: Gauntlet v2 詳細分析からの3改善 — 採点の穴修正・premature応答ガード・パス正規化
- 背景: 54試行の詳細分析で3つの製品/採点課題を特定。(1) LFM の no-change-hard 3/3 は偽陽性（パス迷走→不要質問→exit で「無変更」だけが成立）。(2) DS の全失敗は「修正します」と応答だけして編集未実行の premature return。(3) LFM の2課題全滅は `/workspace/...` や `/tmp/...` パスを「拒否だけ」されて回復不能になったのが直接原因。
- no-change-hard 採点の穴修正（`evals/`）:
  - `no-change-hard.yaml` に `expects_question: false` を追加（タスクに結論の材料が全てあるため不要質問は stage-1 miss 化）。
  - `report_contains` check型を `runner.py` に新設（`texts:` のいずれかが最終 assistant プローズに出現すれば pass）。`workspace_unmodified` だけでは「調査も報告もせず exit」が通ってしまう穴を塞ぐ — LFM型の「質問して終了」は最終メッセージが質問なので自動fail、DS/GLM型の「仕様である」報告は pass。
- premature response ガード（`companion/core_loop_helpers.py`）: 「修正します/I will fix/番号付き実行計画」等の**将来実行を宣言する文言**を含む `::response` で、同ターンに成果物アクション（edit/write/delete系・propose_plan等）が無い場合はループ終了とみなさず `premature_response` として Correction Guide に記録して継続。過去形報告（修正しました/Fixed）は終了扱いのまま。`builder.py` の symops/native 両 Correction Guide に `premature_response` 例を追加。
- パス正規化＋実行可能エラー（`companion/tools/file_ops.py`）: `_normalize_model_path()` を追加し、(a) `/workspace/x.py` 等の仮想ルート除去、(b) workspace内を指す真の絶対パスの相対化、(c) `/tmp/.../<ws_dir_name>/file` 形式（pwd出力のecho）から ws 名以降の尾部を相対パスとして復元。正規化後も `_is_safe_path` で検証するため安全性は不変（`../` トラバーサルは従来通り拒否）。拒否時メッセージに「RELATIVE パスを使え・具体例・ルート探索禁止」のガイダンスを追加。
- テスト: `test_core_loop_control.py` に premature応答 10件（宣言文言5件・正当報告4件・実行済み1件）、`test_file_ops_path_safety.py` に 6件（/workspace正規化・絶対パス・POSIX echo復元・エラーガイダンス・トラバーサル拒否2件）、新規 `test_eval_report_contains.py` 7件（正当報告pass・質問終了fail・空履歴fail・マーカーのみfail・text単数形・最終プローズ抽出）。
- 検証: `uv run python -X utf8 -m pytest tests/ -q` → **807 passed / 2 skipped**（785から+22）。
- 残課題（#3 同一エラーターン跨ぎ連発）: GLM rename-hard の空body edit_file 6連発（142k tokens）に対応する連発検出/エスカレーションは設計案を別途提示、未実装。

### 2026-09-19: Gauntlet v2 初回実行（Main 3×6課題×3回＝54試行）— 16/16/4
- 条件: DS/GLM は symops（前回ベースラインと整合）、LFM は symops 非対応のため native。結果は `evals/results/gauntlet-v2/{ds_symops,glm_symops,lfm_native}/`。ベースラインスナップショット `evals/baselines/gauntlet-v2-main3.json` 保存（コミット・scenario fingerprint・median値を記録、以後 `--compare` で差分検出可能）。
- 総合: **DS 16/18・GLM 16/18・LFM(native) 4/18**。課題別では全シナリオが床〜天井の勾配を持ち、ベースラインとして機能。
- 新規3課題の実測:
  - `ambiguous-gauntlet`: DS 3/3・GLM 3/3・LFM 0/3。DS/GLM は confirmed:3（質問→回答→正解JSON）を完遂。LFM は asked_question:3 ながら artifact 全滅（質問はするが正しく実装できない弱さを分離検出）。
  - `no-change-hard`: 全モデル 3/3。LFM も通過（何もしない系は弱いモデルの得意領域）。GLM は1件 asked_question+duck_call で確認してから無変更判断。no_edit_applied タグで「無変更」自体が可視化される。
  - `spec-build`: DS 3/3・GLM 3/3・LFM 0/3（全件 loops=15 打ち切り・output_echo:3）。生成+継続作業の複合が弱いモデルの天井を正しく示す。
- 失敗機序:
  - DS needle-wide r3: 「修正します」と応答だけして終了（no_edit_applied）。recover-quad r3 も同型。
  - GLM rename-hard r1/r2: 本文なし edit_file 連発＋20 loops 消費で awaiting_user 終了（142k/93k tokens の高コスト失敗）。r3 は19 loops で通過する粘り型。
  - GLM: fabricated_tool_result が needle:3・recover:2・rename:2・spec:1 で検出（504runと同型の残存課題）。
  - LFM spec-build: output_echo:3＋repeated_command で15 loops 使い切り。実行はしているが収束不能。
- コスト実測（median tokens/run）: DS は軽量（19k〜73k）、GLM は2〜3倍（21k〜164k）、LFM は spec-build で 100k+ 消費しつつ収束せず。recover-quad の GLM r1 は 164k tokens・95秒。
- 検証: ライブ54試行完了、analysis.json 3件出力済み。

### 2026-09-19: Gauntlet ベースライン完成 — 新規3課題＋baseline比較ツール＋workspace_unmodified採点
- 背景: Gauntlet を実質ベースラインとするため、能力軸（生成・克制・協業）の欠落を最小コストの3課題で補完。既存3課題（rename-hard=リファクタ、recover-quad=多原因修正+環境、needle-wide=探索効率）と合わせて6課題構成。
- 新規シナリオ（`evals/scenarios/gauntlet/`、すべて小fixture・短ループで低コスト設計）:
  - `no-change-hard`（`nochange_hard_ws` 6ファイル）: 「合計が1-2円ずれる」という報告を調査させるが、per-unit rounding は README 明記の仕様。正解=無変更+報告。504run最大の失敗タグ false_success を直接測る。max_loops 10。
  - `ambiguous-gauntlet`（`ambiguous_g_ws` 6ファイル）: restock.json 生成で stock threshold がタスク文に無い設計（config.py に MIN_STOCK=5/REORDER_POINT=10/SAFETY_STOCK=3 のデコイ）。`expects_question: true` + `user_script` で "stock < 10" を供給。fig=10 の境界値が `<=10` 推測も弾く。正解 {apple,cherry,durian:5}。max_loops 12。
  - `spec-build`（`spec_build_ws` 6ファイル）: SPEC.md 記載の `allocate(stock, request)` を実装＋CHANGELOG.md の Unreleased に1行追記の複合課題（生成+継続作業軸）。エッジケース（部分割当・欠落SKU省略・非正数除外・非破壊）をテストがロック。max_loops 15。
- `workspace_unmodified` check型（`evals/runner.py`）: fixture↔workspace の全ファイルをバイト比較（新規・変更・削除を検出）。`__pycache__`/`.pytest_cache`/`*.pyc` は無視。no-change系の採点に必須で、従来のパス単位 `unmodified` ではカバーできなかった「新規ファイル作成」も検出。
- `evals/baseline.py` 新規（ベースライン比較ツール）: `--save <name> --dir <results>` で `evals/baselines/<name>.json`（git管理可・小サイズ）に集約保存。記録内容: HEADコミット・dirty状態+diff_sha・各run埋め込みコミット一覧・scenario fingerprint（yaml+fixtureのsha）・シナリオ×モデル×プロトコル別の pass数/median tokens・loops・秒。`--compare <name>` で新旧比較表（pass差・median差）＋比較可能性警告（baseline以降のコミット数・dirty差・シナリオ改訂・新規/欠落シナリオ）を出力。
- テスト: `tests/test_eval_workspace_unmodified.py` 6件（一致・編集・新規・削除・生成物無視・fixture無しfail-safe）、`tests/test_eval_baseline.py` 6件（collect・集約・シナリオ変更/欠落/新規警告・整合時no-warning）、`test_gauntlet_scenarios.py` に新3課題を追加。
- 検証（LLMなし・ローカル）: 3課題ともYAMLは重複キー拒否ローダで読込OK。no-change-hard 初期pytest 6/6 pass（正しく無変更が正解）、spec-build 初期3 failed/3 passed・参照実装で6/6 pass、ambiguous-gauntlet の verify は正解JSONで通過。全fixture compileall通過。`uv run python -X utf8 -m pytest tests/ -q` → **785 passed / 2 skipped**（773から12件追加）。
- 未実施: 新3課題のライブ実行（Main 3×両方式）、rename-hard 硬化、needle-wide スリム化、探索規律メトリクス（第一手ツール種別タグ）。

### 2026-09-16: eval 試行条件共有バグ修正＋シナリオスナップショット保存
- 背景: 504run比較の精度向上のための前置修正。`follow_up_inputs` が試行間で共有されており、2試行目以降はfollow-upが供給されない欠陥があった。
- 修正（`evals/runner.py`）:
  - `_make_input_provider` で `follow_ups` を `list(follow_ups or [])` でコピー（`user_script` と同様）。`pop(0)` が scenario dict の共有リストを枯渇させる問題を解消。影響シナリオ: double-bug / find-and-fix / find-needle（`user_script` 型の ambiguous-* は非影響）。
  - `_collect_experiment_meta` に `meta["scenario"]` を追加し、実行時点の解決済みシナリオ設定（follow-ups/checks/verify_command等）を result.json/transcript.json にスナップショット保存。後からYAMLが変わっても実行条件を復元可能。
- テスト: `tests/test_eval_follow_up.py` に `test_follow_ups_not_shared_across_runs` を追加（同一リストから2プロバイダが各々follow-upを受け取り、元リストが不変であることを検証）。
- 検証: `uv run python -X utf8 -m pytest tests/ -q` → 全緑。

### 2026-09-16: native tool-calling レビュー修正（履歴再構成の堅牢化＋Sym-Opsリーク対策＋E2E強化）
- 背景: native tool-calling 経路（Phase A）のレビューで、journal未記録callによる孤児tool_call（API 400）と、タスクリセット・強制実行・pruning での履歴サマリ位置ずれ、nativeプロンプトへのSym-Ops文法リーク、feature-pagination シナリオのテスト改ざん耐性不足を指摘。
- 履歴再構成（`companion/base/native_protocol.py` / `core_action_executor.py` / `llm_client.py` / `agent_state.py`）:
  - 対応付けを位置消費から**ターンID基準**へ変更。`LLMClient` が `{epoch}:{turn}`（epoch=プロセス毎uuid、turn=単調増加・リセット非対象）をログエントリ `_turn` と `Action.native_turn` に付与。executor が履歴サマリへ `_native_turn` をスタンプし、`build_native_messages` がID一致でのみpairing。前タスクのサマリ・強制duck_call・pruning挿入サマリがエントリを食い違わせる問題を解消。
  - journal未記録callへは合成toolメッセージを返しAPI妥当性を担保。executor側は実行前スナップショットで filtered/dropped を記録し、fail-fast・中断残分を終末スイープで `skipped` 記録（全終端点をカバーする二重防御）。
  - テキストのみターンはassistant contentを復元。全件フィルタ時はアンカーサマリ `":: (all proposed actions filtered)"` を挿入。
- Sym-Opsリーク対策（`prompts/builder.py` / `prompts/templates.py` / `core_loop_helpers.py` / executor）:
  - native時はFew-shot不送（全例が `::`/`<<<>>>` 構文を含むため）。Correction Guideのhint・fallback例とジャーナルbodyは `sanitize_tool_references()` で `::name @target` → `name` 変換（`std::vector` 等を壊さない境界条件付き）。`NATIVE_TOOL_PREAMBLE` に「結果内の `::name` 表記は同名ツールへの言及」と明記。`build_intervention_prompt` にprotocol引数追加。
  - スキーマの引数descriptionをツールdocstringの `Args:` 節から生成（`_BLOCK_PARAMS` デッドコード廃止）。
- E2E強化（`evals/scenarios/feature-pagination.yaml` / `evals/runner.py`）:
  - `expects_question: false` を追加（協業段階集計のno-question対照）。`test_api.py`/`app.py` に `unmodified` チェックを追加し、テスト弱化によるパスを封鎖。fixtureコピーで `__pycache__`/`*.pyc` を除外し、コミット済み `__pycache__` を削除。
- テスト: `test_native_protocol.py`（placeholder合成・ターンID対応・stale turn非pairing・sanitize境界・param doc・native build_messages非汚染）、`test_core_execute_actions_minimal.py`（filtered/dropped/skipped journal・`_native_turn` スタンプ）を追加・更新。
- 検証: `uv run python -X utf8 -m pytest tests/ -q` → **765 passed / 2 skipped**（754から11件増）。

### 2026-09-09: ライブモデル評価ハーネス (evals/) + 製品バグ修正
- 背景: 弱いモデルの実挙動を測るE2E評価が存在しなかったため、実LLMでシナリオを実行・対話履歴を蓄積・ヒューリスティック分析する土台を新設。単体テストの重要ギャップ（承認ゲート・ループ制御）も補填。
- 単体テスト追加（Step 0）:
  - `tests/test_core_loop_control.py`（7件）: `should_return_to_user`（空response時のループ継続＋エラー記録を含む）、`build_intervention_prompt`、`check_and_prune_if_needed`（緊急プルーニングの文脈喪失通知）。
  - `tests/test_approval_gate.py`（6件）: `get_approval_request`（編集系無条件ゲート・write_file上書き時のみ）、拒否時の履歴フィードバックを execute_actions レベルで検証。
- evals/ 新設:
  - `evals/runner.py`: 実モデルで `DuckAgent.run()` をフル起動（UI入力差し替え・承認自動yes・ワークスペースは `%TEMP%/duckflow-evals/` にコピー）。トランスクリプト（対話履歴全文＋raw_responses＋syntax_errors）と result.json を `evals/results/`（gitignore・ローカル保持）に保存。`calculate_max_loops` をシナリオ予算にピン留め。
  - `evals/analysis.py`: ヒューリスティックタグ付け（api_error / output_echo / investigation_reentry / blocked_edit / empty_response / repeated_command / duck_call / no_edit_applied）。`uv run python -X utf8 -m evals.analysis` でサマリ出力＋analysis.json 書き出し。`tests/test_eval_analysis.py` 9件。
  - シナリオ5本: fix-typo, create-fizzbuzz, edit-multi-hunk, find-and-fix（最難・pytest実行を含む調査→修正）, hallucination-resist（存在しない関数への耐性）。
  - `llm_client.chat()` が `last_raw_response` を保持するよう変更（evalとデバッグ用）。
- 評価過程で発見・修正した製品バグ:
  - `companion/tools/shell_tool.py`: (1) `run_command` に `cwd` 指定がなく `--dir` ワークスペース外（プロセスCWD）で実行される実バグ → `cwd=str(file_ops.workspace_root)` を指定。(2) 終了コードが握り潰され、pytest失敗（exit 5）も `::status ok` になる → 結果に `exit_code: N` を付与。`tests/test_shell_cwd.py` 4件。
  - `companion/core_action_pipeline.py`: Investigation Mode の編集BLOCKEDメッセージが「re-enter Task mode」と曖昧で、弱いモデルが再調査ループに陥る → finish_investigation で即 Planning モードに切替わる旨を明示。find-and-fix の失敗率が改善（1/3→3/3）。
  - ハーネス側: evalワークスペースをリポジトリ内（gitignore適用パス）に置くと `get_project_tree` が0件を返しモデルが誤認 → temp ディレクトリへ移設。`core.py` が毎ターン `calculate_max_loops` で再計算しシナリオ予算が無効になる問題 → ランナーでピン留め。
- ベースライン（z-ai/glm-4.5-air, --runs 3）: fix-typo 3/3, create-fizzbuzz 3/3, edit-multi-hunk 3/3, hallucination-resist 3/3, find-and-fix 3/3（BLOCKEDメッセージ修正後）。find-and-fix の旧失敗は repeated_command(10/15)・output_echo(8/15) が主因と定量確認。
- 検証: `uv run python -X utf8 -m pytest tests/ -q` → **612 passed / 2 skipped**（開始時587から25件追加）。

### 2026-08-02: Sym-Ops パーサー境界の堅牢化
- `companion/utils/parser.py`: 独自の旧文法実装を廃止し、実運用と同じ `SymOpsProcessor` へ委譲する後方互換アダプターへ変更。旧APIでも `@target` を失わず返すようにした。
- `companion/utils/sym_ops.py`: vitals を小数桁数ではなく数値範囲 `0.0 <= value <= 1.0` で検証。範囲外・不正値は警告付きで無視し、コンテンツブロック内の vitals 文字列は解析対象外とした。単独の列0 `>>>` は `\>>>` でエスケープでき、先頭バックスラッシュ1文字を解析時に外す。本文中の単独 `<<<` はブロック再開始として扱わず保持する。
- strict/fuzzy 境界: orphan `>>>`、未閉鎖ブロック、不正アクション名を行番号・期待形式・実入力付き `ParseError` にし、fuzzy fallback の警告へ具体的な失敗理由を保持。fuzzyでも回復不能な場合は `LLMClient` から次ターンの Correction Guide へ詳細を渡す。
- `companion/core_loop_helpers.py`: パーサー以外から渡された範囲外・非有限 vitals も状態へ反映しない二重防御を追加。
- プロンプト・設計文書: `@` をパス専用ではなく「ツールの主引数」と明文化し、`\>>>` エスケープ規則と vitals 範囲表記を同期。
- テスト: `tests/test_sym_ops_protocol_hardening.py` を追加（主引数マッピング、空白入りパス、引用値、旧API委譲、vitals検証、終端エスケープ、本文内開始マーカー、strict/fuzzy診断、Correction Guide連携）。`uv run pytest tests/ -v` → **587 passed / 2 skipped**。

### 2026-06-28: ツール返り値の統一（ToolResult 化）
- 目的: プロンプト・ツール回りの改善案「1. ツール返り値の統一」に対応。`file_ops`/`symbols`/`sub_llm_tools`/`shell_tool`/`core_actions` が返していた `::status error` 形式の事前整形文字列を廃止し、すべて `ToolResult` オブジェクトで返すようにした。`normalize_tool_result()` という事後正規化を削除。
- 修正:
  - `companion/tools/file_ops.py`: `edit_file`/`_apply_edits`/`grep_files`/`delete_lines` のエラーを `ToolResult.error` に変更。`ToolResult` インポートと返り値型注釈を追加。
  - `companion/tools/symbols.py`: `list_symbols`/`find_definition`/`replace_function` のエラーを `ToolResult.error` に変更。返り値型注釈を追加。
  - `companion/tools/sub_llm_tools.py`: `analyze_structure`/`generate_code` の成功・エラー・キャンセルを `ToolResult` に変更。返り値型注釈を追加。
  - `companion/tools/shell_tool.py`: タイムアウト・実行例外時を `ToolResult.error` に変更。返り値型注釈を追加。
  - `companion/core_actions.py`: `action_run_command` のユーザー拒否時を `ToolResult.error` に変更。返り値型注釈を追加。
  - `companion/core_action_invocation.py`: `invoke_tool` に `tool_name` 引数を追加。必須パラメータ欠損・タイムアウト時も `ToolResult` を返すように変更。
  - `companion/core_action_executor.py`: `normalize_tool_result` インポートを削除。`invoke_tool` に登録ツール名を渡し、戻り値が `ToolResult` の場合はその `status`/`content` を直接使用するよう変更。
  - `companion/core_action_results.py`: `normalize_tool_result()` を削除。未使用の `re` インポートを削除。
  - `tests/`: 上記変更に伴い `test_tool_timeout.py`/`test_symbols.py`/`test_replace_function.py`/`test_hashline.py`/`test_edit_marker_format.py`/`test_core_action_results.py`/`test_core_execute_actions_minimal.py` を更新。`normalize_tool_result` 関連テストを削除。
- 検証: `uv run python -X utf8 -m pytest tests/` → 534 passed / 2 skipped / 1 failed（失敗 1 件は pacemaker stagnation 検知の既存問題）。

# Duckflow 開発進捗記録 (PROGRESS.md)

## 🎯 プロジェクト現状
- **現在のフェーズ**: Phase 1.6 (コード実行機能)
- **全体進捗**: 約 85% (Phase 2 以前)

---

## 📅 更新履歴

### 2026-07-02: Phase 1残タスク（TierProfile の実配線）実装完了
- 背景: `docs/agent_surface_redesign_design.md` §8 Phase 1 の残課題。TierProfile 自体（tier別デフォルト・`resolve_tier_profile()`・`LLMClient.tier_profile`）は Phase 1 で骨格のみ実装済みだったが、`unknown_model_context_length` 以外の数値は実際の挙動に反映されていなかった。今回、Pacemaker・repo map・履歴圧縮の3箇所を配線し、tier ごとの数値が実際にコードパスへ効くようにした。数値そのもの（10/18/35 等）の較正は §7 ベンチ待ちのため変更していない。
- 配線内容:
  - `companion/modules/pacemaker.py`: `calculate_max_loops()` に `tier_profile: Optional[TierProfile] = None` を追加。ハードコードされていた上限 35 を `tier_profile.max_loops`（省略時は従来どおり35）に置き換え、base_loops の算出（プラン有無・タスク数に応じた値）もこの ceiling でクランプするよう変更。`companion/core.py` の呼び出し箇所で `self.llm.tier_profile` を渡すよう変更。
  - `companion/modules/repo_map.py`: `generate_repo_map_text()` に `token_budget: Optional[int] = None` を追加し、渡された場合はシングルトン `RepoMapGenerator` の `token_budget` を上書きしてから生成する。
  - `companion/prompts/builder.py`: `PromptBuilder.__init__` に `tier_profile: Optional[TierProfile] = None` を追加し、repo map 生成時に `tier_profile.repo_map_token_budget` を渡すよう変更。呼び出し箇所（`core.py`、`command_handler.py` の `_build_current_messages`/`_build_mode_messages`、`dump_prompt.py`）を `self.llm.tier_profile` を渡す形に更新。
  - `companion/tool_history_policy.py`: モード別定数（`_GREP_MAX_EXCERPTS` 等）を廃止し、`_COMPRESSION_PROFILES = {"standard": {...}, "strong": {...}}` の辞書に置き換え。`compress_for_history()` に `strength: str = "standard"` を追加し、各内部コンプレッサー（grep/project_tree/run_command/list_symbols/generic）にプロファイル辞書を渡す形に変更。未知の strength は "standard" にフォールバック。`companion/execution/result_pipeline.py::summarize_result()` から `agent.llm.tier_profile.history_compression` を渡すよう配線。
  - 上記いずれも「tier を知るのはプロファイル解決の1箇所だけ」の原則（設計 §2-8）を維持: 各モジュールは tier 文字列を知らず、`TierProfile` の具体値または `strength`/`token_budget` 等の文字列・数値のみを受け取る。
- テスト: `tests/test_pacemaker_minimal.py`（tier 別 ceiling の効果・省略時の後方互換）、`tests/test_repo_map.py`（`token_budget` 上書き・0 での抑制)、`tests/test_tool_history_policy.py`（strong/standard の圧縮強度差・未知 strength のフォールバック）に追加。既存 `tests/test_history_policy_ext.py`・`tests/test_result_pipeline.py` は新シグネチャに合わせて更新（`FakeAgent` に `llm.tier_profile.history_compression` のスタブを追加）。
- 検証: `python -X utf8 -m pytest tests/ -q` → **578 passed / 2 skipped**（Phase 2 完了時の572から6件追加）。
- 未実施（Phase 5 で対応予定）: プロファイル数値自体の較正（§7 ベンチ後）、`checkin_interval`/`escalation_threshold` の実配線（Phase 4/5 の機能自体が未実装のため配線先がまだない）。

### 2026-07-02: Phase 2（ツール面縮小 + 説明強化）実装完了
- 背景: `docs/agent_surface_redesign_design.md` §8 Phase 2。25個のツールから14/15/11個（task/planning/investigation）へ縮小し、選択の曖昧さ・幻覚ツール呼び出しのリスクを削減。
- 新規統合ツール:
  - `list_files`（`companion/tools/file_ops.py`）: `list_directory`/`find_files`/`get_project_tree` を統合。`glob` 未指定時はツリー表示（内部で `get_project_tree()` に委譲）、指定時は再帰検索（内部で既存 `find_files()` に委譲）。旧 `FileOps.list_files`（フラット単層リスト、他に直接呼び出し箇所なしと確認済み）は新シグネチャで置き換え。
  - `find_symbol`（`companion/tools/symbols.py`）: `list_symbols`/`find_definition` を統合。`name` 指定時は `find_definition` に、`path` 指定時は `list_symbols` に委譲。両方未指定はエラー。既存の `list_symbols`/`find_definition` 関数自体は変更せず内部実装として維持（直接呼び出す既存テスト群はそのまま通過）。
  - `complete_step`（`companion/tools/plan_tool.py`）: `mark_step_complete`/`mark_task_complete` を統合。現在のステップに未完了タスクがあれば先頭の1件を完了（残数を報告）、全タスク完了または元々タスクがなければ即座にステップを閉じる（`mark_step_complete()` に委譲、同一呼び出し内でステップ完了まで進む）。カーソル位置（どのタスク/ステップが対象か）はハーネス側が判定し、モデルはパラメータ不要。
- ツール面からの撤去（`core_tools.py` の `UNIVERSAL_TOOLS`/`MODE_TOOL_MAPPING` から除外）:
  - **統合により完全に登録解除**（`register_default_tools()` から旧アクション名を削除、代わりに新ツール名で登録）: `list_directory`, `find_files`, `get_project_tree`, `list_symbols`, `find_definition`, `mark_step_complete`, `mark_task_complete`。`/scan` コマンドは `get_project_tree()` 関数を直接インポートして使用しており影響なし。
  - **登録は維持したままモード面のみ非表示**（内部的には引き続き呼び出し可能。安全判定セット `EDIT_ACTIONS`/`MUTATING_ACTIONS` 等は登録維持のため変更不要と確認）: `note`, `delete_lines`, `append_file`, `search_archives`, `analyze_structure`, `generate_code`, `generate_tasks`, `execute_tasks`, `execute_batch`。
- **スコープの判断（意図的、設計ドキュメントの厳密な対象外）**: `generate_tasks`/`execute_tasks` は設計の最終形（14ツール表）では完全撤去対象だが、Phase 4（ハーネス駆動タスク分解）が未実装のため今回はモード面から外すのみとし、Sub-LLMベースのタスク自動生成・バッチ実行というFast Pathの手動起動能力が失われることを許容した（`complete_step` はタスク階層の有無に関わらず動作するため、Step完了という中核機能に欠落はない）。
- 型・必須/任意情報の付加（§4.3）: `core_tools.py::get_tool_descriptions()` を拡張し、各パラメータに型（`inspect.Parameter.annotation` 由来）と、任意パラメータには `[name:type=default]` 形式でデフォルト値を表示するよう変更（例: `pattern:str`（必須） vs `[include:str="*"]`（任意））。`Optional[X]`/`X | None` は Python 3.10+ で `__name__` が `"Union"` という非直感的な文字列になるため、`typing.get_origin`/`get_args` でアンラップして内側の型 `X` のみを表示する変換を追加。
- プロンプト・文書更新: `companion/prompts/templates.py`（Edit/Search/Communicationツール節・TASK_MODE_INSTRUCTIONS を新ツール面に全面書き換え）、`companion/utils/response_format.py`（静的Sym-Opsプロトコルから execute_batch の `%%%` 教材セクションを削除、セクション番号を振り直し、`delete_lines`/`list_directory` の例示を更新）、`companion/prompts/few_shot.py`（`list_directory`→`list_files`）、`companion/utils/sym_ops.py`（`ACTION_VERBS` の `list_directory`/`get_project_tree`→`list_files`）、`companion/base/llm_client.py`（`_TARGET_PARAM` に `find_symbol`→`name` を追加、`mark_task_complete` 専用の `@index`→`task_index` 変換ロジックを削除）、`companion/tool_history_policy.py`（履歴圧縮ディスパッチキーを `get_project_tree`→`list_files`、`list_symbols`→`find_symbol` にリネーム）、`companion/tools/plan_tool.py`/`companion/core_action_invocation.py`/`companion/core_actions.py`（`::note` を勧める旧ガイダンス文言を `>>` Thought ベースの案内に更新）。
- テスト: 既存テスト13ファイルを新ツール面に合わせて更新（`test_core_mode_mapping.py`: `delete_lines` を edit_tools 期待集合から除外、`test_llm_action_mapping_minimal.py`: `mark_task_complete` の @target テストを `find_symbol` の同等テストに置換、`test_tool_history_policy.py`/`test_history_policy_ext.py`: ディスパッチキー変更に追従、`test_config_status.py`/`test_core_actions.py`: フェイクデータ・アサーション文言を更新）。新規 `tests/test_agent_surface_phase2.py`（20件）: `list_files`/`find_symbol`/`complete_step` の単体テスト、旧アクション名が完全に登録解除されていることの確認、hidden系ツールが登録は維持されつつモード面から漏れていないことの確認、task/planning/investigation 各モードのツール数が設計値（14/15/11）と一致することの確認、型注釈表示の確認。
- 検証: `python -X utf8 -m pytest tests/ -q` → **572 passed / 2 skipped**（Phase 1 の554から18件追加）。`python -X utf8 -c "import main"` で起動健全性確認。実際の `get_tool_descriptions()` 出力を目視確認し、型注釈・ツール数が意図通りであることを確認。
- 未実施（Phase 4 で対応予定）: `generate_tasks`/`execute_tasks` の完全撤去とハーネス駆動タスク分解への置き換え、`propose_plan` 承認時の `TaskListProposal` 自動発火。

### 2026-07-02: Phase 1（TierProfile 骨格 + T-1）実装完了
- 背景: `docs/agent_surface_redesign_design.md` §8 Phase 1。弱いモデル向けの運転プロファイルを配給するための単一解決点を新設。
- 新規: `companion/config/tier_profile.py`。`TierProfile`（Pydantic, frozen）を新設し、§5.2 のtier別デフォルト値（max_loops/checkin_interval/repo_map_token_budget/escalation_threshold/unknown_model_context_length/history_compression/few_shot_variant/tool_description_variant/edit_format_hint）を low/mid/high で定義。`resolve_tier_profile(model_name, provider, cfg)` が `llm.available_models[].tier` を解決し、未指定・未一致モデルは "low" にフォールバック（DEFAULT_CONTEXT_LENGTH是正と同じ保守的既定の哲学）。`available_models` エントリに `_OVERRIDABLE_FIELDS` の値を直接書けばモデル個別上書きも可能。**設計原則: tierを知るのはこのモジュールだけ。他コンポーネントはif-tier分岐を持たず具体値のみ参照する。**
- `companion/base/llm_client.py`: `LLMClient.__init__` と `reinitialize()`（モデル切替）成功時に `_refresh_tier_profile()` を呼び出し、`self.tier_profile` を保持するよう変更。`get_context_length()` のステップ3（フォールバックテーブルにも載らない未知モデル）を、固定値 `DEFAULT_CONTEXT_LENGTH` ではなく `self.tier_profile.unknown_model_context_length` を返すよう変更（low tier=16,000、mid/high=32,000）。これに伴い `DEFAULT_CONTEXT_LENGTH` モジュール定数は未使用になったため削除。
- `companion/modules/command_handler.py`: `/model current` に `Tier: <tier> (未指定は保守的に"low"として扱われます)` を追加。`/model list` のテーブルに Tier 列を追加（`available_models` に `tier` フィールドがなければ "low" 表示）。
- **スコープの判断（意図的）**: Phase 1 は「既存挙動を変えず配線」が原則だが、Pacemakerのmax_loops・MemoryManagerの予算・repo map注入量など数値に実影響する箇所への配線は見送った。理由: 現状 `duckflow.yaml` の `available_models` には tier が1件も設定されておらず、全モデルが "low" にフォールバックする設計上、もしこれらの数値をこの時点で配線すると Claude Sonnet 等の現行の強いモデルの挙動（max_loops上限35等）が意図せず後退する。これらの較正はロードマップ通りPhase 5（プロファイル較正）に委ねる。今回配線したのは「フォールバックテーブルにない未知モデルのコンテキスト長既定値」のみ — これはPhase 0で導入したばかりの安全機構の自然な精緻化であり、CONTEXT_LENGTH_FALLBACKに載っている既知モデル（Claude/GPT-4o等）は一切影響を受けない。
- テスト新規: `tests/test_tier_profile.py`（8件: 未指定→low・明示tier解決・tierフィールド欠如時のlow維持・個別フィールド上書き・不正tier値のlowフォールバック・tier間の値の順序整合性・LLMClient初期化時のtier_profile保持・モデル切替時の再解決)。`tests/test_context_length_fallback.py` を新しい tier 連動の既定値に合わせて更新。
- 検証: `python -X utf8 -m pytest tests/ -q` → **554 passed / 2 skipped**（Phase 0 の546から8件追加）。`python -X utf8 -c "import main"` で起動健全性確認。
- 未実施（今後）: `available_models` への実際のtier付与はユーザー判断に委ねる（今回は編集していない）。`/model` によるインタラクティブなtier選択UIはT-1の残タスク。

### 2026-07-02: Phase 0 止血（agent_surface_redesign_design.md §6）実装完了
- 背景: `docs/agent_surface_redesign_design.md` §6 の Phase 0（止血4件）を実装。弱いモデルの思考ループ・幻覚ツール/パラメータ・幻覚の直接原因を修正。
- 修正:
  - `companion/modules/pacemaker.py`: `_detect_stagnation()` を全面書き直し。read-only ツール（read_file等10種）を検知対象から除外していた仕組みを廃止し、「同一アクション名＋同一パラメータ（`json.dumps(sort_keys=True)`で正規化）＋同一結果」を統一条件として判定するよう変更。パラメータの辞書順の揺れによる誤判定も解消。失敗し続けていた `test_pacemaker_detects_repeated_action_stagnation` が解消。
  - `companion/base/llm_client.py`: `DEFAULT_CONTEXT_LENGTH` を128,000→32,000に変更（フォールバックテーブルにない未知モデルを弱いモデルとして保守的に扱う）。`LLMClient.context_length_source`（"api"/"fallback"/"default"）を追加し、`get_context_length()` の各分岐で設定。`companion/core.py` の2箇所の呼び出し元で `context_length_source == "default"` の場合に `ui.print_warning` でユーザーに可視化。
  - `companion/state/agent_state.py`: `ActionList` に `parse_error_type` / `parse_error_detail` フィールドを追加（Sym-Ops完全パース失敗・空応答をLLMにフィードバックするための輸送経路）。
  - `companion/base/llm_client.py`: `_parse_response()` の完全パース失敗時（except節）に `parse_error_type="parse_failed"` を設定。actions/thoughts/reasoning が全て空の場合（旧: 無フィードバックで黙って終了）に `parse_error_type="empty_actions"` を新設し記録。
  - `companion/core_loop_helpers.py`: `record_parse_error_if_any()` を新規追加。`parse_error_type` が設定されていれば `SyntaxErrorInfo` として `last_syntax_errors` に記録し、既存の Correction Guide 経路（builder.py）へ合流させる。`companion/core.py` の自律ループ内2箇所（通常/Pacemaker介入）の `llm.chat()` 呼び出し後に呼び出すよう配線。
  - `companion/prompts/builder.py`: `_CORRECTION_EXAMPLES` に `unexpected_params` / `parse_failed` / `empty_actions` の修正例を追加。
  - `companion/core_action_results.py`: `build_dropped_params_syntax_error()` を新規追加。ツールが受け付けないパラメータをモデルが渡した際、従来はログにのみ記録し黙って握りつぶしていたのを `SyntaxErrorInfo`（`unexpected_params`）として次ターンにフィードバックするよう変更。
  - `companion/core_action_executor.py`: `dropped_params` 検出時に上記関数を呼び出し `agent.state.last_syntax_errors` に追記するよう変更。
  - `companion/utils/sym_ops.py`: `AutoRepair._fix_missing_symbols_line()` の行頭動詞アクション化を厳格化。`_looks_like_action_target()` を新設し、明示的な `@` がない場合は「文末の `.!?`」「先頭語が冠詞/前置詞等（a/the/of/for等）」「7語超」のいずれかに該当すると自然言語の説明文とみなしてアクション化をスキップするよう変更。"Create a summary of the file structure." のような自然文が存在しないアクション `create` へ誤変換される事故を防止。`@` 明示時は従来通り常に補完（正規表現を `(@)?` で捕捉するよう変更）。
- テスト新規: `tests/test_context_length_fallback.py`（2件）、`tests/test_parse_error_feedback.py`（4件）、`tests/test_core_execute_actions_minimal.py` に1件追加（dropped params フィードバック）、`tests/test_autorepair_block_protection.py` に4件追加（自然文の誤変換防止・`@`明示時は従来通り・短いコマンド様対象は引き続き補完）。
- 検証: `python -X utf8 -m pytest tests/ -q` → **546 passed / 2 skipped**（直近ベースライン 2026-06-28: 540 passed / 1 failed から、既知失敗だった pacemaker stagnation テストが解消し、新規19件を追加）。
- 次: `docs/agent_surface_redesign_design.md` Phase 1（TierProfile 骨格 + T-1）へ。

### 2026-07-02: モデル接触面の再設計ドキュメント作成
- 背景: 弱いモデル（ローカル/OpenRouter安価、〜30B: Qwen3.6 / GLM4.5-flash / Gemma 4 想定）で自律動作が不安定（思考ループ・幻覚ツール/パラメータ・幻覚）という問題に対し、4系統の並列コード調査（プロンプト構造 / パーサー・フィードバック / ループ制御 / 履歴・コンテキスト管理）を実施。
- 主な発見: (1) 停滞検知が read-only ツールを除外しており実質無効（失敗中の pacemaker テストの原因）、(2) パラメータドロップ・パース失敗理由・空パースがLLMにフィードバックされない3穴、(3) コンテキスト長のデフォルト128K過大既定と emergency pruning による無通知の文脈喪失、(4) モードあたり16〜18K文字のプロンプト＋25ツール＋型情報なしの説明という認知負荷。症状の主因はプロトコル構文（フレーム）ではなく意味論的負荷と判定。
- `docs/agent_surface_redesign_design.md` 新規: Sym-Ops v4（フレーム維持・YAMLフロントマター廃止・Vitals記法削除・note統合・execute_batch非表示化）、ツール面縮小（task 25→14: list_files/find_symbol/complete_step 統合、delete_lines/append_file 廃止、計画系ハーネス移管「見せるが操作させない」、Sub-LLM のシステム駆動エスカレーション化）、Tier運転プロファイル（単一オブジェクトでツール説明・few-shot・repo map・max_loops・チェックイン間隔・エスカレーション閾値を tier 別配給、リード型自律制御）を策定。Phase 0（止血4件）〜Phase 5 の実装計画とアクション層ベンチ計画（v3.2 vs v4 vs XML × 実ターゲット3モデル）を収録。
- 実装は未着手。プロトコル最終形（v4 vs XML）はベンチで決着する方針（edit format と同じ作法）。
- 目的: ツール失敗時に LLM に返されるメッセージが正しい `[TOOL_RESULT]` / `::status error` 形式になっているか、また二重ラッピングや無言スキップなどの不具合がないかを検証。
- 修正:
  - `companion/core_action_results.py`: `normalize_tool_result()` を追加。`file_ops`/`sub_llm_tools` が返す事前整形 Sym-Ops 文字列と `task_tool` が返す `ToolResult` から実際の status/body を抽出し、executor が 1 回だけ `[TOOL_RESULT]` で包むようにした。`build_tool_result_message()` も `ToolResult` オブジェクトを直接扱えるように修正。
  - `companion/core_action_executor.py`: 無言で必須パラメータ欠損アクションをスキップしていた処理を削除。`invoke_tool()` の明示的なエラーメッセージを LLM 履歴に返すようにした。共有ヘルパ `_handle_error()` を導入し、ツールエラー・例外・未知ツールの 3 経路で一貫したエラー履歴注入と fail-fast 制御を行うようにした。`invoke_tool()` 経由の `::status error` 結果を `::status ok` で誤包みしないようにした。
  - `companion/tools/shell_tool.py`: タイムアウト・実行例外時に `::status error` 形式の文字列を返すように変更。
  - `companion/tools/sub_llm_tools.py`: `analyze_structure` のファイル読み込み失敗・解析失敗時に `::status error` 形式を返すように変更。
  - `companion/core_actions.py`: `action_run_command` でユーザー拒否時に `::status error` 形式を返すように変更。
  - `tests/test_core_action_results.py`: `normalize_tool_result` と `build_tool_result_message` の回帰テストを追加。`build_action_summary` のテストを実装（reasoning 除外）に合わせて修正。
  - `tests/test_core_execute_actions_minimal.py`: ツールエラー文字列の正しい包みと、必須パラメータ欠損時のフィードバックを検証するテストを追加。
- 検証: `uv run python -X utf8 -m pytest tests/` → 540 passed / 2 skipped / 1 failed（失敗 1 件は pacemaker stagnation 検知の既存問題）。

### 2026-06-21: プロンプト・ツール・state 整合性検証と修正
- 目的: LLM へ渡すプロンプト（templates.py / few_shot.py）と実際のツール登録・パラメータ・state モデルが一致しているかを詳細に検証。
- 修正:
  - `companion/core_tools.py`: モード別公開ツールマッピングを整備。Investigation Mode に `run_command` を追加し、Planning Mode から `submit_hypothesis`/`finish_investigation` を削除、Investigation Mode から `propose_plan`/`generate_tasks` を削除。
  - `companion/core_tools.py`: ツール説明生成で content-block パラメータ（edit_file の find/replace/occurrence 等）と `**kwargs` をインライン表示から除外。`@target` 対象パラメータに `query`/`task_index`/`name`/`conclusion`/`cache_id` を追加。
  - `companion/base/llm_client.py`: `@target` 特殊マッピングに `find_definition`→`name`、`mark_task_complete`→`task_index`、`retrieve_result`→`cache_id` を追加。
  - `companion/prompts/templates.py`: Investigation Mode の仮説上限を 2 回表記から 5 回（`MAX_HYPOTHESIS_ATTEMPTS`）へ修正。
  - `companion/prompts/few_shot.py`: 仮説例の残り試行回数を 1 回から 4 回へ修正。
  - `companion/tools/task_tool.py`: サブ LLM タスク生成プロンプトで存在しない `edit_lines` を `edit_file` に修正。
  - `companion/core_action_executor.py`: Investigation Mode 中の編集アクションを自動終了ではなくブロックするよう修正（プロンプト「Investigation Mode は read-only」と整合）。
  - `companion/core_action_executor.py` / `companion/core_action_invocation.py`: 必須パラメータ判定で 0 など falsy 値を「欠損」と誤判定しないよう修正。
- 検証: `uv run python -X utf8 -m pytest tests/` → 531 passed / 2 skipped / 2 failed（失敗 2 件は本件と無関係な既存問題: action_summary の reasoning 出力方針・pacemaker stagnation 検知）。

### 2026-06-21: Sprint 2 完了 (S2-3 core.py 詳細分割)
- companion/core_actions.py (新規): action_* メソッド群（note/response/run_command/exit/execute_tasks/investigate/submit_hypothesis/finish_investigation/execute_batch/noop）を CoreActions クラスとして抽出。DuckAgent は self._actions で保持。
- companion/core_action_executor.py (新規): execute_actions() をスタンドアロン関数として抽出。DuckAgent.execute_actions は薄い委譲メソッドのみ残置。
- companion/core_loop_helpers.py (新規): run() から update_vitals_from_response / build_intervention_prompt / check_and_prune_if_needed / should_return_to_user を抽出。
- companion/core_tools.py: register_default_tools の登録先を agent.action_* → agent._actions.action_* へ更新。
- companion/core.py: 1000行→400行へ縮小（__init__ + switch_model + get_tool_descriptions + run + execute_actions委譲）。
- テスト: 	ests/test_core_actions.py (新規、10件) 追加。	ests/test_core_execute_actions_minimal.py の monkeypatch 対象を companion.core_action_executor.ui へ更新。	ests/test_core_mode_mapping.py の hasattr チェックを agent._actions へ更新。
- 検証: uv run pytest tests/ -v = 383 passed / 2 skipped。


### 2026-06-21: Sprint 3 小粒DX群（S3-4 / S3-5 / S3-7）を実装
- `companion/modules/command_handler.py`: `/prompt` ハンドラを追加（既定=現ターン preview 表 / `all`=3モード / `raw`=JSON / `file [path]`=ファイル書き出し）。メッセージ構築ヘルパ `_build_current_messages` / `_build_mode_messages` / `_preview_content` / `_messages_to_table` を分離。`/tokens` ハンドラを追加（system/履歴の概算トークン・max_tokens 使用率・pruning 閾値・API usage を Table 表示）。`self.commands` 辞書の `/config` 重複を解消し `/prompt` `/tokens` を登録。`/help` に新コマンドと入力案内を追記。
- `companion/modules/memory.py`: `estimate_history_tokens(messages)` 公開メソッドを追加（`_estimate_tokens` と同じ概算式 chars×0.5 を任意メッセージ群に適用）。pruning ロジックは不変更。
- `companion/ui/console.py`: `get_user_input` に複数行入力のキーバインドを追加（Enter=1行目送信 / 改行済みなら改行挿入、`Ctrl+J`=改行=Shift+Enter 相当、`Esc→Enter`=複数行送信）。`NestedCompleter` に `/prompt` `/tokens` `/clear` を追加。
- `companion/core.py` / `main.py`: `--debug-context console|file` オプションと `DuckAgent.debug_context_mode` を廃止（宛先 `ui.print_debug_context` が未実装のデッドパスだったため）。`/prompt` に機能を集約。
- テスト追加: `tests/test_command_prompt.py`（9件）、`tests/test_command_tokens.py`（7件）、`tests/test_multiline_input.py`（3件）。合計19件。
- ドキュメント: `AGENTS.md` / `CLAUDE.md` §6 のコマンド一覧と入力案内を更新、`docs/ROADMAP.md` の S3-4/S3-5/S3-7 を対応済みへ。
- 検証: 新規3テスト19件パス。`uv run python -X utf8 -c "import main"` で起動健全性確認。

### 2026-06-21: 推論モデルの <think> タグ生漏れを Hotfix
- 現象: 推論系モデル（Kimi K2.7 等）使用時、LLM 出力の `<think>...</think>` が除去されず、response メッセージ等に `</think>` が生漏れして表示が崩れていた（リファクタリングとは無関係の潜伏バグ）。
- 原因: `companion/` 全体で `<think>` 処理が未実装。DeepSeek-R1 由来の推論タグ（Kimi K2/Qwen3/GLM/GPT-OSS 等）が本文埋め込み型で出力するのを Duckflow が想定外だった。
- `companion/utils/preprocessor.py`: `strip_reasoning_tags()` を追加。完全な `<think>...</think>` ブロックと孤立タグ（`<think>`/`</think>`）を除去（大文字小文字問わない）。
- `companion/utils/sym_ops.py`: `SymOpsProcessor.process` の入口（Phase -1）で `strip_reasoning_tags` を呼び出し、strict/fuzzy 両方で `Reasoning tags stripped (<think>)` 警告を記録。
- `tests/test_reasoning_tag_strip.py` 新規（6件）: 完全ブロック除去・孤立タグ除去・ケース非依存・パイプライン統合（response content への漏洩がないこと）を検証。
- 検証: `uv run pytest tests/` で **347件パス / 2件スキップ**。リグレッションなし。
- ※推論内容を Thought として活かす設計（OpenRouter `reasoning` フィールド対応）は ROADMAP **S3-8** に追加。

### 2026-06-21: Sprint 2 S2-3 core.py 分割の第一段階
- `companion/core_tools.py` を新規追加し、DuckAgent のツール登録、モード別公開マッピング、Sym-Ops ツール説明生成を分離。
- `companion/core.py` は `register_default_tools()` と `get_tool_descriptions()` への委譲に変更し、`DuckAgent.MODE_TOOL_MAPPING` / `UNIVERSAL_TOOLS` は後方互換 alias として維持。
- `tests/test_core_mode_mapping.py` に core_tools への分離とモード別説明フィルタの回帰テストを追加。
- `companion/core_action_pipeline.py` を新規追加し、`execute_actions()` の前処理（未知ツール除外、1ターン上限、terminal action 並べ替え）を純粋関数として分離。
- `tests/test_core_action_pipeline.py` を追加し、前処理仕様を `execute_actions()` 本体から独立して回帰テスト化。
- `companion/core_action_results.py` を新規追加し、承認要否判定、denial context、ツール結果履歴メッセージ生成を純粋関数として分離。
- `tests/test_core_action_results.py` を追加し、承認判定と `[TOOL_RESULT]` 履歴メッセージ生成を回帰テスト化。
- `companion/core_action_invocation.py` を新規追加し、ツール呼び出し前のシグネチャベース引数フィルタを分離。
- `tests/test_core_action_invocation.py` を追加し、未対応引数の drop と `**kwargs` 関数の全引数保持を回帰テスト化。
- 旧 Phase 1 前提の `tests/test_llm_output_validator.py` / `tests/test_transition_controller.py` を削除し、Windows symlink 権限がない環境では `test_file_protector.py` の symlink テストを skip するよう修正。検証: `uv run pytest tests/ -v` で339件パス / 2件スキップ。
- `core_action_pipeline.py` に低 safety 判定・キャンセルメッセージ生成・編集アクション判定を追加し、`execute_actions()` の前処理責務をさらに分離。関連テストを追加。

### 2026-06-21: Sprint 2 S2-1 未使用 Phase 1 遺物を削除
- `companion/state/enums.py`, `companion/state/transition.py`, `companion/state/transition_controller.py`, `companion/state/action_result.py` を削除。現行 `core.py` / `agent_state.py` 経路から未参照で、旧 Step/Status 前提の Phase 1 遺物だった。
- `companion/validators/llm_output.py` を削除。旧 `state/enums.py` のみに依存する未使用 validator で、現行 Sym-Ops → `ActionList` 経路とは別物。
- `AGENTS.md` / `CLAUDE.md`: 空になる `validators/` ディレクトリ記述を削除。
- `docs/ROADMAP.md`: S2-1 を対応済みに更新。
- 検証: 削除対象への参照を `rg` で確認し、全体 `uv run pytest tests/ -v` で188件パス / 1件スキップ。

### 2026-06-21: Sprint 2 S2-2 pyproject.toml を実態化
- `pyproject.toml`: プロジェクト名を `codecrafter` から `duckflow` に変更し、author / URL / package include / console script を現行 `companion` 実装に合わせた。
- 未使用依存として実コード参照がなかった LangChain / LangGraph / Chroma / FAISS / sentence-transformers / Textual を通常依存から削除。Tree-sitter / LSP は将来機能用の optional dependency として維持。
- `main.py`: console script 用の同期ラッパー `cli()` を追加し、`duckflow = "main:cli"` で起動できる形にした。
- `companion/config/config_loader.py`: セットアップ後の `config.reload()` 呼び出しが成立するよう `reload()` を追加。
- `tests/test_config_loader_minimal.py`: `reload()` がキャッシュを捨てて `duckflow.yaml` を再読込することを回帰テスト化。
- `AGENTS.md` / `CLAUDE.md` / `docs/ROADMAP.md`: pyproject 旧実態の既知課題を解決済みとして更新。
- 検証: `uv run pytest tests/test_config_loader_minimal.py -v` で3件パス。`uv run python -X utf8 -c "import main; assert callable(main.cli); print('cli-ok')"` で console script 参照先を確認。全体 `uv run pytest tests/ -v` で188件パス / 1件スキップ。

### 2026-06-21: Sprint 1 S1-4 テスト空白地帯の補強
- `companion/state/agent_state.py`: Investigation の仮説上限を `MAX_HYPOTHESIS_ATTEMPTS = 5` として共有定数化。
- `companion/core.py` / `companion/modules/pacemaker.py`: 仮説上限判定を共有定数へ寄せ、Pacemaker が古い 2 回上限で `INVESTIGATION_STUCK` を出す不整合を修正。
- `tests/test_core_execute_actions_minimal.py`: `execute_actions()` の action cap（6件上限）、低 safety 時のユーザー拒否による全アクションキャンセル、terminal action の末尾実行を追加検証。
- `tests/test_pacemaker_minimal.py`: 直近10件中5件エラーの cascade 検知、Investigation stuck が共有上限直前では発火せず上限到達で発火することを追加検証。
- `docs/ROADMAP.md`: Sprint 1 を完了に更新。S2-3 `core.py` 分割は S1-4 の最低限テストが入ったため着手可能に整理。
- 検証: `uv run pytest tests/test_core_execute_actions_minimal.py tests/test_pacemaker_minimal.py tests/test_agent_state_minimal.py -v` で12件パス。全体 `uv run pytest tests/ -v` で187件パス / 1件スキップ。

### 2026-06-21: Sprint 1 即効安定化の S1-1〜S1-3 を実施
- `duckflow.yaml`: `max_loops` / `language` / `auto_approval` を `llm.agent` 配下からトップレベル `agent` 配下へ移動し、`ConfigLoader.get("agent.max_loops")` と一致させた。既存の OpenRouter モデル変更は維持。
- `companion/state/agent_state.py`: `InvestigationState` の説明と `to_prompt_context()` の表示を仮説上限 5 回へ更新。
- `tests/test_agent_state_minimal.py` 新規: Investigation prompt context が `hypothesis_attempts=3/5` を出すことを回帰テスト化。
- `AGENTS.md` / `CLAUDE.md`: 協業ループ・planning モード条件付き編集・SEARCH/REPLACE 推奨・設定構造・解決済み課題を現状へ同期。
- `docs/ROADMAP.md`: Sprint 1 を進行中へ更新し、S1-1〜S1-3 を対応済み、S1-4 を残タスクとして整理。
- 検証: `uv run pytest tests/test_config_loader_minimal.py tests/test_agent_state_minimal.py tests/test_core_mode_mapping.py -v` で8件パス。全体 `uv run pytest tests/ -v` で182件パス / 1件スキップ。

### 2026-06-21: 協業ループを中核コンセプトに採用・連鎖更新
- Duckflow の中核コンセプトを「協業ループ（Cooperation Loop）」に据えることを合意。弱いLLM × 協業で、コスト効率・ユーザー学習効果・継続向上の独自軸で価値を出す（強いLLMとの品質競争は明示的に放棄）。
- `docs/cooperation_loop_design.md` 新規: 北極星・価値軸（V1/V2/V3）・筋の良い協業の4原則・ループ構造・土台への示唆・効果測定方針（3層指標・Goodhart 回避・V2 は定性観察）。
- 連鎖更新: `CLAUDE.md` §1 ビジョン書き直し（協業ループを頂点・3柱を支える基盤に再構成）、`docs/ROADMAP.md` に Sprint 5「協業ループ」新設、Context Mixer の spec/context/decisions/ideas を反映。
- 実装は土台（Sprint 1〜3）安定後。コンセプト確定のみ「今」済ませ、土台の方向付けに使用。

### 2026-06-21: Context Mixer（duckflow コレクション）を現状に同期
- context / spec / decisions / notes の4ドキュメントを 2026-06-17〜06-21 の進捗に更新（前回同期は 2026-06-16）。
- **context**: 直近の完了事項追記・既知の課題の現状化（`test_hashline.py` 解消済み・プロトコル境界整理済み）・`docs/ROADMAP.md` 参照を追加。
- **spec**: プロトコル境界（外部Sym-Ops / 内部`ActionList` / 補助JSON）・3モード（仮説5回・planning編集ツール条件付き公開）・`delete_lines` マーカー対応を反映。
- **decisions**: 新規判断3件を追記（仮説上限 2→5 化 / プロトコル境界の明文化 / `delete_lines` の SEARCH/REPLACE 対応）。過去分は保持。
- **notes**: 旧実装前提記述（LangGraph / Pacemaker 3指標 / テスト67件）をセクション分割して注記 + 現行実装のクセ（PyYAML glob誤解釈・Rich markup/単独サロゲートクラッシュ・doctest保護・sanitize v2.4 等）を追記。
- ※コレクション説明文（「Python + LangGraph 5ノード」）は Context Mixer MCP の制約で更新不可のため、引き続き context 冒頭の注記で代替。

### 2026-06-21: 開発ロードマップドキュメントを新規作成
- `docs/ROADMAP.md` 新規: 今後の作業を Sprint 1〜4 に整理。各項目を重要度（Impact）と優先度（Urgency）の2軸で評価。Sprint 4 は Vitals再設計（V-A〜D）・長期記憶（L-a〜e）・Phase 3（P-a〜c）のサブタスクまで具体化。
- アクティブな全体ロードマップが存在しなかったため新規作成（`docs/old/NEXT_STEPS_ROADMAP.md` は5ノード LangGraph 時代に陳腐化移動済み）。
- 既知の課題（CLAUDE.md §8）と各 Sprint 項目の紐付け表、依存関係図を収録。本ドキュメントは PROGRESS.md（履歴）と対で運用。

### 2026-06-21: delete_lines を SEARCH/REPLACE マーカー形式に対応
- `companion/tools/file_ops.py`: `delete_lines` が `edit_file` と同じ SEARCH/REPLACE マーカー形式を受け付けるように変更。削除専用のため、`REPLACE` 側は空であることを要求し、内容がある場合は `delete_lines_replace_not_empty` エラーで `edit_file` 利用へ誘導する。
- 既存の `find:` 形式は後方互換として維持。複数削除ブロックは今回サポートせず、複数箇所は複数 `delete_lines` アクションまたは `edit_file` に寄せる方針。
- `companion/prompts/templates.py`: `delete_lines` の説明を `find:` DSL から SEARCH/REPLACE マーカー形式推奨へ更新し、旧 `find: |` は後方互換として記載。
- `tests/test_hashline.py`: マーカー形式で削除できること、非空 REPLACE を拒否することの回帰テストを追加。
- 検証: `uv run pytest tests/test_hashline.py tests/test_edit_marker_format.py -v` を実行しようとしたが、環境側の使用上限エラーでブロックされたため未完了。

### 2026-06-21: planning モード境界と旧アクション残骸を整理
- `companion/core.py`: `note` の実装メソッド名を `action_note_` から `action_note` に統一。未登録のまま残っていた旧 `action_report` / `action_finish` / `action_status` を削除し、terminal action 判定から未登録の `finish` を除外。`::status` / `::result` は引き続きツール結果マーカー用 no-op として維持。
- `companion/base/llm_client.py`: Sym-Ops → `Action.parameters` の特殊マッピングから廃止済み `report` / `finish` を削除。`::report` / `::finish` が出ても `response` 相当として扱わず、未知ツールフィードバックへ流れるよう整理。
- `companion/utils/sym_ops.py` / `companion/tools/file_ops.py`: AutoRepair と protocol leak 判定から廃止済み `report` / `finish` の扱いを外し、`finish_investigation` は維持。
- `companion/prompts/templates.py` / `companion/prompts/system_v1.py`: planning モードで編集ツールが公開される理由と条件を明記。`finish_investigation` 後の小さく確定した修正に限り、探索的・広範な実装は plan 作成後 task モードへ進める方針を追加。
- `AGENTS.md` / `CLAUDE.md`: planning モードの編集ツール公開は条件付きであることを追記。
- テスト追加: `tests/test_core_mode_mapping.py`（planning 境界文言、旧 report/finish 未登録、`status` no-op 維持）、`tests/test_llm_action_mapping_minimal.py`（report/finish の特殊マッピング削除）、`tests/test_autorepair_block_protection.py`（AutoRepair が report/finish を補完しない）。
- 検証: 関連 `uv run pytest tests/test_core_mode_mapping.py tests/test_llm_action_mapping_minimal.py tests/test_autorepair_block_protection.py -v` で35件パス。全体 `uv run pytest tests/ -v` で179件パス / 1件スキップ。

### 2026-06-20: Rich 出力時の単独サロゲートによるクラッシュを修正
- ユーザー報告: 動作確認中に Rich の `Console._write_buffer()` で `UnicodeEncodeError: 'utf-8' codec can't encode characters ... surrogates not allowed` が発生。`PYTHONIOENCODING=utf-8` だけでは解決せず、Duckflow 側が単独サロゲートを含む文字列を Rich に渡していたことが原因。
- `companion/ui/console.py` に `_safe_text()` / `_safe_escape()` を追加。UI 表示直前に単独サロゲートを `\udcff` 形式の可視テキストへ変換し、Rich markup escaping と組み合わせて適用。
- 通常ログ、エラー/警告/情報、ユーザー/会話表示、アクション表示、結果表示、Live ステータス、spinner、Markdown、Syntax 表示を同じ正規化経路に通すよう変更。
- `tests/test_console_markup_escape.py` に単独サロゲートを含む出力の回帰テストを追加。Rich の markup タグ風文字列と invalid Unicode が同時に含まれても落ちないこと、status text が sanitize 済みになることを検証。
- 検証: `uv run pytest tests/test_console_markup_escape.py -v` で9件パス。

### 2026-06-20: パーサー/ツール層の最低限テストを追加
- `tests/test_llm_action_mapping_minimal.py` を追加。Sym-Ops から `Action.parameters` への重要マッピング（`run_command.command`、`note`/`response`/`duck_call.message`、`propose_plan.goal`、`mark_task_complete.task_index`、`search_archives`/`recall.query`）を検証。
- `tests/test_file_ops_path_safety.py` を追加。`read_file` / `write_file` / `edit_file` / `delete_file` が `..` による workspace 外アクセスを拒否し、通常の nested workspace path は書き込めることを検証。
- `tests/test_delete_file_minimal.py` を追加。`delete_file` の通常削除、存在しないファイル、ディレクトリ削除拒否を検証。
- `tests/test_plan_tool_minimal.py` を追加。`PlanTool.propose_plan()` の Markdown step parse、`mark_step_complete()` の step advance / plan complete / planなしエラーを検証。
- 検証: 追加分 `uv run pytest tests/test_llm_action_mapping_minimal.py tests/test_file_ops_path_safety.py tests/test_delete_file_minimal.py tests/test_plan_tool_minimal.py -v` で17件パス。全体 `uv run pytest tests/ -v` で171件パス / 1件スキップ。

### 2026-06-20: 最重要制御系の最低限テストを追加
- 旧実装・手動評価用途だった `scripts/manual/generate_code_eval.py` を削除。実LLM接続と `.env` に依存する品質評価スクリプトであり、自動テスト基盤としては扱わない方針に整理。
- `tests/test_core_execute_actions_minimal.py` を追加。`DuckAgent.execute_actions()` の最低限の安全制御として、未知ツールの事前フィルタ、Investigation mode の編集ブロック、連続2エラー時の fail-fast 中断を検証。
- `tests/test_pacemaker_minimal.py` を追加。Pacemaker の停滞検知、3連続エラーによる error cascade、動的 max_loops が 3〜35 に収まることを検証。
- `tests/test_session_manager_minimal.py` を追加。`SessionManager` の AgentState 保存/復元 roundtrip と、壊れたセッションファイルを読んでも `load()` が落ちず `None` を返すことを検証。
- `tests/test_config_loader_minimal.py` を追加。既知課題である `agent.max_loops` のトップレベル読み取りと、`DUCKFLOW_AGENT_MAX_LOOPS` 環境変数 override を検証。
- 検証: 追加分 `uv run pytest tests/test_config_loader_minimal.py tests/test_core_execute_actions_minimal.py tests/test_pacemaker_minimal.py tests/test_session_manager_minimal.py -v` で10件パス。全体 `uv run pytest tests/ -v` で154件パス / 1件スキップ。

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
### 2026-09-11: 比較評価用モデルの追加
- `duckflow.yaml` の選択候補に `minimax/minimax-m2.5` を追加。既定モデルは変更せず、評価時に明示指定する。
- OpenRouter公開モデルAPIでM2.1と同じ入力/出力単価を確認。公開ベンチマーク値はハーネス条件が異なるため、Duckflowでの性能保証とは扱わない。
- 計画反復の調査で、Pacemakerが `propose_plan` を停滞検知から明示除外していることを確認。制御変更とモデル変更を同時に比較しない方針で、今回の制御コードは変更なし。

### 2026-09-13: 評価仕様の確定・編集回復ガイド・自発的確認の拡張（施策1〜3）
- 施策1（評価仕様の確定）: `ambiguous-explicit`/`ambiguous-spontaneous` の依頼にトップレベル形式と階層禁止を明記し、verifyの `summary` 特例を廃止して厳密一致化。`no-change` の依頼に入力前提（整数・low <= high）と範囲外拡張の禁止を明記。以後は構造と協業を混ぜずに測れる。
- 施策2（編集回復ガイドの具体化）: MiniMaxのmulti-file失敗（本文欠落の反復・SEARCH不一致後の立て直し失敗）を受け、`file_ops.py` の本文欠落・find不一致エラーを「::read_file→逐語コピー→同一文再送禁止」の次手順付きに変更。`core_action_results.py` のhintと`builder.py` のCorrection例示もSEARCH/REPLACE表現へ統一。
- 施策3（自発的確認の拡張）: 不足情報の別種3課題（`ambiguous-period`/`ambiguous-output`/`ambiguous-unit`）と対照課題（`complete-no-question`）を追加。period用fixture（`fixtures/period_ws/sales.csv`）は月絞り込み可能。シナリオは13→17件。
- テスト: `tests/test_eval_spec_narrowing.py`（13件）・`tests/test_edit_recovery_guide.py`（4件）を追加。`uv run python -X utf8 -m pytest tests/ -q` → **709 passed / 2 skipped**。
- 次は MiniMax + DeepSeek で新4課題の各5試行比較（質問実施率・不要質問率・回答後完遂率）。

### 2026-09-13: 新4課題×2モデル×9回＝72試行の比較結果
- 条件: commit `d0f423a`（dirty: 施策1〜3の未commit分あり）＋厳密化後の採点。framed既定。
- 結果: MiniMax 35/36、DeepSeek 35/36。内訳は period 9/9・output 8/9・unit 9/9・complete 9/9 で両モデル同一。
- periodは推測不能な設計が機能: 両モデルとも質問が必須で、MiniMax 8/9・DeepSeek 9/9 が編集前に質問。MiniMaxの1件（`ambiguous-period/20260913-095505-r4`）は先に全期間集計を書き込んでから質問し直して上書き成功。成果物は正しいが無駄手間で、`asked_question` タグ（編集前質問のみ計上）は正しくFalseを付けた。
- output/unitは正解の推測が可能: 出力先report.json・合計金額は例示から自明なため、質問なし完遂（DeepSeek output asked 1/9・unit 6/9、MiniMax output 4/9）が合理的行動として混在。「質問しなかった＝失敗」ではない。質問行動を測るにはperiod型の推測不能設計が必要という設計知見。
- 両モデルの失敗は共にoutputの早期終了（ファイル未生成）で、機序は異なる: MiniMaxは `<minimax:tool_call>` XMLを通常応答として表示して終了（`ambiguous-output/20260913-095244-r6`、2loops）、DeepSeekはread後に空の `:: response` で終了（`ambiguous-output/20260913-100243-r4`、2loops）。採点起因ではなく実失敗。
- 対照課題は両モデルとも質問0/9で全完遂。情報が揃えば質問過多にならない。
- トークン中央値は period で MiniMax 30,553 / DeepSeek 27,986、complete で 19,525 / 20,942。今回の軽量課題では multi-file のような効率差は出ない。
- 次: output/unitを推測不能化（例: 出力先・集計種別を自明でない選択肢にする）し、質問必須性をperiod並みに引き上げる。「編集してから質問」の検出タグ（asked-late）を検討。

### 2026-09-13: 施策1〜3の実装（不足情報の隠蔽・3段階集計・編集回復の前後比較）
- 施策1（不足情報を本当に隠す）: `ambiguous-output` の依頼文から `report.json` を除去し、回答で初めて `summary.json` を伝える構成へ（checks/verifyも追従）。回答複数パターンとして `ambiguous-output-alt`（回答totals.json）・`ambiguous-period-feb`（回答2月分: apple 50/cherry 500）・`ambiguous-unit-count`（回答行数: apple 2/banana 1/cherry 1）を追加。シナリオは17→20件。全variantのverifyは正誤両方向の動作確認済み。
- 施策2（合格の3段階集計）: シナリオに `expects_question`（協業8種+変種=true、対照=false）を宣言し、`evals/analysis.py` に `load_question_expectations()`・`stage_summary()`（confirmed/artifact_ok/natural_completion）を追加。`analyze_dir` は各runに `stages` を付与し `stage_counts` を集計、`print_report` に段階表を表示。`tests/test_eval_stages.py`（7件）で回帰化。
- 施策3（編集回復の前後比較）: MiniMax `multi-file-rename` ×9を新ガイドで実行し、旧ガイド時の4/9と比較 → **6/9**。ただしn=9ずつのため改善断定は不可。失敗3件の内訳: r3/r7は本文欠落の反復（新ガイド文面は到達したが同一の空編集を再送）、r9は未読でのSEARCH推測→mismatch→fail-fast後に1ループで終了（再試行なし）。本文欠落は文面理解ではなくプロトコル遵守の問題で、文面改善だけでは反復が止まらないことを確認。なお本文欠落エラーはToolResult経路のみで `last_syntax_errors`（Correction Guide）には載らない非対称も残る。
- テスト: `uv run python -X utf8 -m pytest tests/ -q` → **716 passed / 2 skipped**（709から7件追加）。
- 次（施策4）: XML要求の完了応答化と途中経過responseの対策を別々に比較。response継続化は正常な質問を壊すため一括変更しない。

### 2026-09-13: variant3件＋隠蔽後output×2モデル×9回＝72試行（3段階集計の初適用）
- 条件: 施策1・2の未commit分あり。outputは回答をsummary.jsonへ変更後の再測定。
- 成果物合格: MiniMax 32/36、DeepSeek 35/36。3段階（confirmed/artifact/natural）は以下。
  - output（隠蔽後）: 両モデルとも9/9かつconfirmed 9/9。隠蔽が機能し、推測完遂は消滅。
  - output-alt: 両モデルとも9/9・3段階完全。回答違い（totals.json）への追従を確認。
  - period-feb: DeepSeekは9/9・3段階完全。MiniMaxは質問9/9だが成果物7/9。失敗2件は質問後に正しい内容の初回書き込み→空本文の再送反復→ファイル未生成（multi-fileのr3/r7と同型）。
  - unit-count: MiniMaxは質問8/9・成果物7/9（r9は金額推測のまま終了）。DeepSeekは成果物8/9だが質問は4/9。残り4件の合格は「金額で先書き→質問→件数で上書き」の事後修正で、r1は完了報告で自己違反を自認（「本来は集計方法を先に確認すべき」）。r8は金額のまま終了し不合格。
- 自然な完了報告: 72/72でXML漏れ・空終了なし。今回の範囲では終了処理の問題は再現せず。
- 知見: (1) 推測不能化は質問必須化に有効（output隠蔽で確認）。(2) 成果物合格は事後修正で水増しされるため、confirmed分離が必須（DeepSeek unit-countが典型）。(3) MiniMaxの空本文反復は文面到達後も継続し、ガイド文面の限界を再確認。
- 次（施策4）: XML要求の完了応答化と途中経過responseの対策を別々に比較。加えて空本文反復への対策（ToolResult経路のCorrection Guide化など）を検討。

### 2026-09-13: 終了判定修正・write_file回復例・例示中立化＋MiniMax 3課題の再評価（優先1〜4）
- 優先1（終了判定の修正）: `evals/analysis.py` に `classify_end_state()`（reported/awaiting_user/timeout/empty/unknown）を追加。stage3は報告あり＋漏れなしのときのみTrue、報告なしはNone（従来は空履歴・相談終了もTrueだった）。`analyze_dir` は各runに `end_state` を付与し `end_counts` を集計・表示。`evals/runner.py` のexperiment記録に `expects_question` を保存し、分析は試行時値を優先（現行ファイルへの retroactive 適用を解消）。`tests/test_eval_stages.py` に6件追加。
- 優先2（write_file本文欠落の回復例）: `companion/core_action_invocation.py` の必須引数欠落エラーで、対象がwrite_fileの場合に `<<< >>>` 複数行形式の再送例を返す。他ツールは汎用文のまま。`tests/test_core_action_invocation.py` に2件追加。
- 優先3（例示の中立化）: `ambiguous-unit`/`ambiguous-unit-count` の例示を `{"apple": 300}` から `{"商品名": 集計値}` へ変更。`tests/test_eval_spec_narrowing.py` に1件追加。
- 優先4（変更部分のみ再評価・MiniMax×3課題×9＝27試行）: period-feb 7/9（前回同値）、unit-count 8/9（前回7/9）、multi-file 7/9（前回6/9）。r1/r3（feb）は質問なしの全期間推測、unit r2は質問後にシングルクォートJSONを書き込み（形式隣接失敗）、multi r4はXML漏れ表示つき未完、r9は相談終了。unit-countは質問9/9（前回8/9）で中立化が質問率に寄与した可能性。新write_file案内はfeb r2で2回到達し、その後本文付き再送で完遂（回復の直接証拠1件）。unit r4は成果物合格ながら相談終了でstage3=Noneとなり、新判定が機能。
- テスト: `uv run python -X utf8 -m pytest tests/ -q` → **725 passed / 2 skipped**（716から9件追加）。
- 次（施策4）: XML漏れ完了応答と途中経過responseの個別対策を別々に比較。multi r4でXML漏れパターンが再現したため素材あり。

### 2026-09-13: Tool Calling検証プローブの実装（research §4の能力確認）
- `evals/tool_probe/fetch_catalog.py`: 公開モデルAPIの取得→抽出→保存を再現可能化。yaml登録ID＋E2E明示3件＋既知extras＋対照2件を対象化。再取得で既存スナップショットとID・フラグ完全一致を確認。実装中に検出・修正した落とし穴: yamlだけではE2E主力（M2.1/GLM有料/V4.1F）が対象外になるため `EVAL_IDS` で明示（初版は10件に縮小していた）。
- `evals/tool_probe/probe.py`: 副作用なし `probe_echo` ツールの送受信→tool_call_id付き結果返送→通常応答までの往復を記録。no_callは所見、API失敗はerror（非対応に分類しない）。主ループ不変。
- 実機確認: MiniMax-M2.1で `round_trip_ok`（名前・引数・ID受信→結果返送→追従応答）。結果は `evals/tool_probe/results/` に保存。
- テスト: `tests/test_tool_probe.py`（10件、実APIなし・fake注入）。`uv run python -X utf8 -m pytest tests/ -q` → **735 passed / 2 skipped**（725から10件追加）。
- 次: 他モデル（DeepSeek等）の往復確認、M2.1のSym-Ops対native A/Bは別途設計合意が必要。

### 2026-09-14: 差し替え機構の実装（Phase A）＋初回A/B（M2.1・output/multifile各9）
- 機構: `companion/base/native_protocol.py` 新設（スキーマ自動生成・tool_calls→ActionList変換・履歴のターンごと再構成・環境切替）。`LLMClient.chat()` にnative分岐（`native_tools` 引数、共通kwargs/usage化のため `_build_request_kwargs`・`_record_usage` を抽出、verbatim応答ログ＋`reset_native_log()`）。`PromptBuilder.build_messages()` にprotocol指定（native時はツール説明ブロックを `NATIVE_TOOL_PREAMBLE` へ置換・Few-shotはminimal固定）。`core.py` で配線（2経路＋新規タスク時リセット）。`evals/runner.py --tool-protocol`＋experiment記録、分析は試行時値を優先・段階表をprotocol別表示。
- 設計からの逸脱1件: プロンプトのツール説明ブロック置換は「本文変更なし」に反するが、Sym-Ops指示とnative定義の併送は実験を無効化するため最小置換を実施（§6の「入力差はツール説明の形式に限定」と整合）。
- テスト: `tests/test_native_protocol.py`（10件）。`uv run python -X utf8 -m pytest tests/ -q` → **745 passed / 2 skipped**。
- A/B結果（M2.1）: outputはsymops 9/9・native 6/9、multifileは両方式9/9。native outputの失敗3件は散文での質問（表＋「ファイル名を指定してください」）に `?` がなく、ハーネスの回答供給条件（duck_call待機または `?`）に掛からず回答なし終了。機構の不具合ではなく、質問検出の方式差。nativeはトークン中央値がoutput 15,232（symops 24,800）・multifile 22,186（27,534）と軽量。
- symops outputの2件は成果物合格後にPacemaker STAGNATION介入のduck_callで待機終了し、stage3=Noneが完了認定を正しく保留（新終了判定の動作確認）。
- 注意: multifileのsymops 9/9は過去6〜7/9とのばらつき範囲（n=9）。方式の優劣断定はしない。
- 次（Phase C判断材料）: native質問文への `?` 付与（preamble強化）か、ハーネス側の散文質問検出のいずれかを単独比較。併せて他モデルでの再現確認。

### 2026-09-14: レビュー指摘の優先1〜4を実装（native完成度の引き上げ）
- 優先1（プロンプト分離）: `templates.py` にNATIVE版テンプレート要素（Unified Action・reasoning行・tools節・3モード指示）を追加。`builder._native_template()` はアンカー不一致で loudly 失敗。`_build_mode_static`・`_build_error_feedback` にprotocol指定（native例示はSym-Ops文法なし）。テストで静的部分のマーカー漏れを回帰化。
- 優先2（質問待ちの内部明示）: `native_text_to_action()` が文末 `?` を内部 `duck_call` アクションへ変換（API定義に含めない、LLM呼び出し追加なし）。`tag_asked_question`/runner検出と同基準。
- 優先3（ID基準化）: `Action.tool_call_id` 追加、`LLMClient` に実行ジャーナル（turn/tool_name/status/executed/body）＋`record_native_event()`、`execute_actions` の5終端点（filter/block/deny/error/success＋investigate skip）で記録。`build_native_messages` はjournal優先・順序zipはフォールバック。純粋エンベロープ文はnative再構成で除去（重複防止）。
- 優先4（APIエラー分離）: `_chat_native` の例外は actions空＋`parse_error_type="api_error"`（完了応答にしない）。引数JSON破損は `tool_call_parse_error` を付与しつつ実行継続。`_PARSE_ERROR_HINTS`・Correction例示にnative文言を追加（Sym-Ops側の同種経路は凍結・不変）。
- テスト: `uv run python -X utf8 -m pytest tests/ -q` → **754 passed / 2 skipped**（745から9件追加）。
- 制限: nativeを既定化しない（実験経路のまま）。項目5・6の実機比較はクレジット不足（402）のため未実施、追加後に再開。

### 2026-09-16: 全21シナリオ×4モデル×3回×2protocol計504run比較（クレジット追加後）
- 条件: `evals/results/full/<モデル>_<protocol>/` に8条件を逐次実行（01:46〜06:03、EXIT=0）。モデルはyaml登録のOpenRouter 4件（minimax-m2.5 / deepseek-v4-flash-0731 / z-ai/glm-4.5-air / gemini-2.5-flash）。スモークで `:free` 版が404提供終了を確認し有料版に置換。
- 総合: **439/504（87%）**。条件別: DS-native 60/63・GLM-symops 58・DS-symops 56・M2.5-symops 56・M2.5-native 54・Gemini-symops 52・GLM-native 52・Gemini-native 51。3段階はconfirmed 200 / artifact 439 / natural 468。
- 最大の発見: **ambiguous-spontaneous が全条件で 1/24**。モデル・方式を問わず壊滅のため、シナリオ/採点側の問題が濃厚（要調査）。
- 新規 feature-pagination は 22/24。no-change / create-fizzbuzz / find-needle / ambiguous-unit-count は 24/24。
- 次: spontaneous失敗の原因切り分け、Phase C判断材料として本結果を使用。

### 2026-09-16: 504run全分析（モデル×方式×シナリオ横断）
- モデル別: DeepSeek 116/126（92%）・M2.5 110/126（87%）・GLM 110/126（87%）・Gemini 103/126（82%）。方式別: native 217/252（86%）・symops 222/252（88%）でほぼ互角。
- コスト: 中央値トークン native < symops（M2.5で14k vs 25k）。全消費 約1250万トークン。loops中央値は3〜6。
- 失敗タグ全体: false_success 36・verified_edit 36が双璧（編集して検証したつもりで報告する型）。fabricated_tool_result 10はsymopsのみ・nativeゼロ。
- false_successの内訳はspontaneous 15・explicit 5と協業系に集中。方式断定はn=3のため不可。

### 2026-09-16: spontaneous全滅と捏造偏在の切り分け（追加課金なし・現物確認）
- spontaneous 1/24の機序: 設問が「必要な商品」を指定しないため全モデルが推測で全3商品を書き込み、banana混入でverify不一致。唯一のpassは質問したDeepSeek native。period系（「必ず先に確認」を明示）の高質問率と対照。自発的質問は明示指示なしにほぼ発生しないという実測として有効。シナリオ欠陥ではない。
- fabricated_tool_resultの機序: 定義は生応答内の `[TOOL_RESULT]`/`::status` 混入。現物ではGemini等がツール往復の模擬ターンを丸ごとエコー（実行は後続の本物アクションで行われるため多くはpass）。nativeは結果がtool-roleで返りテキストに現れないため免疫。対策案: プロンプト§6に自己記述禁止を追加、またはパーサー警告→Correction Guide化（実装は未着手）。

### 2026-09-16: 捏造ツール結果のパーサー警告→Correction Guide化を実装
- 経緯: Phase -0.7で除去のみ行い警告が残らず、次ターンへの注意喚起がなかった。`FABRICATED_RESULT_WARNING` マーカーを新設し、strict/fuzzy両経路で `parsed.warnings` へ追加。
- 配線: `llm_client.py` がマーカー検出時に `parse_error_type="fabricated_tool_result"` を設定（残存アクションは真正のため実行継続、vague_actionの全消去とは別扱い）。`core_loop_helpers._PARSE_ERROR_HINTS` と `builder._CORRECTION_EXAMPLES` に文言追加。
- テスト: `tests/test_fabricated_result_warning.py` 新規4件（除去・`::status` 単独・正常系無警告・Guide収録）。全 `770 passed / 2 skipped`。
- black差分は repo全体の既存ドリフト（未編集ファイルも同様）のため周辺様式維持。

### 2026-09-16: Main 3 Quick初回（126run）とLFMの方式非対応の発見
- 結果: 84/126。DS 19・20、GLM 17・17、LFM symops 2・native 9。
- LFM symops全滅の機序: 1ループ・no_edit×19。現物では `<|tool_call_start|>[replace_function(...)]<|tool_call_end|>` という独自形式を出力し、Sym-Opsとして解釈不能。弱さではなく方式非対応。nativeは9/21で下限対照として機能。
- 運用影響: weak controlは方式別に適否を判定すること（LFMはnativeのみ有効）。候補対応: protocol probeゲート（N回不発でincompatible扱い）、またはAutoRepairで当該マーカーを `::action` へ変換。

### 2026-09-16: Quick詳細分析（DS明示・GLM期間・LFM形状）
- DS explicit失敗: 質問なしの直接全量書き込み＋完了報告（spontaneousと同型。自分のasked heuristicは設問文中のduck_callに汚染されていたため無効、正はtags）。
- GLM period symops: 質問→回答→編集まで到達したが、periodは正しいキーながらJSON不正（Extra data）、febは `{}` の空書き込み。Serialize層の失敗。
- GLM period native: `::response` 文での質問は回答取得に成功したが、直後に無内容の `::duck_call` を発行して停止、ファイル未作成。空duck_callの扱いが課題候補。
- LFM native: 過剰質問（duck_call多発・awaiting_user×7）しつつ9/21。no-change等の無編集系は拾う。下限対照として成立。
### 2026-09-16: テスト運用ルール確定（Main 3 / Full 7・変更トリガー）
- `docs/eval_operation_rules.md` 新規。Main 3＝DeepSeek V4 Flash＋GLM-4.5-Air＋LFM（安さ＋対照群の識別力）、Full 7＝＋M2.5/Gemini/Qwen/GLM-5.3（外部検証専用）。
- カタログ検証で2件修正: LFMは `lfm-2.5-1.2b-instruct:free` 不在→ `lfm-2.5-2.6b:free`（無料・64K）、Qwenは `qwen3.8-27b` が正ID。GLM-5.3 Flash は $0.09/$0.30 で4.5-Airより安いことを確認。
- 変更トリガー表・fingerprint・provider昇格・Quick/Regression/Full/Agent Evalの4層を規定。Calibration 4ターンは設計中につき現行evalへの読み替えを併記。

### 2026-09-17: Gauntlet試作（G1/G2/G6）— 都度手動の高難易度枠
- 背景: Quick 21件が上位モデルで飽和（DS 19〜20/21）。ambiguous 8件がsales.csv一族に偏り、単一原因・短loopsに集中。普段回さない高難易度枠を別Tierとして新設。
- G1 `rename-hard`（`fixtures/rename_hard_ws` 10ファイル）: fetch_records→load_entries。定義＋呼出4件（api/cli/worker/reports、別名import・モジュール参照混じり）をgrepで探索。`legacy.py` は監査記録としてunmodified拘束（触ってはいけない罠）。テストが新名をimportするため初期はcollection error。
- G2 `recover-quad`（`fixtures/recover_quad_ws` 9ファイル）: 失敗原因4つ＝コード3（orders割引式・shipping境界 `<`→`<=`・reportsのsummary階層化）＋依存不足1（`tabulate` がrequirements.txtのみ・venv未導入、READMEにpip手順）。テスト3件はunmodified拘束。max_loops 25・timeout 900。
- G6 `needle-wide`（`fixtures/needle_wide_ws` 37ファイル）: find-needleの広域版。pricingバグ＋35ノイズ＋`archive.py` のdiscount言及デコイ。全部読みはloops/tokenが吹き飛ぶ配置。max_loops 20。
- 検証（LLMなし・ローカル）: YAMLは重複キー拒否ローダで読込OK。3件とも初期pytestが非ゼロ終了、参照修正を適用したtempコピーでverify通過＋全checks通過（G1 12/12・G2 9/9・G6 2/2）。G2のtabulateはvenvを汚さないようtemp側にstub配置で検証（venvは未導入のまま維持）。全fixtureをcompileall通過（exporter.pyの `\n` エスケープ不備を1件修正）。`uv run pytest tests/ -q` → **770 passed / 2 skipped**（回帰なし）。
- 運用: `evals/results/gauntlet/` 分離・都度手動のみ。並列起動禁止（workspace秒ID衝突の既知不具合）。シナリオは `evals/scenarios/gauntlet/` に分離し、`--all` は従来の21件のまま（`runner.py` は `--scenario` 指定時のみrglob探索、`analysis.py` の期待値読込もrglob化）。`tests/test_gauntlet_scenarios.py` 3件で分離とorders採点の緩和を回帰化。

### 2026-09-17: Gauntlet初回（Main 3×symops×3課題×3回＝27試行）
- 条件: framed。結果は `evals/results/gauntlet/<モデル>_symops/`。各モデルのrecover-quad初回前にvenvのtabulateを除去し依存不足条件を復元（試行中にpip導入されるため。終了後も除去済み）。
- 総合（採点修正後の再採点）: **14/27**。DS 7/9・GLM 7/9・LFM 0/9。課題別: rename-hard 6/9・recover-quad 4/9・needle-wide 4/9。Quick（DS 19〜20/21）より明確に分離。
- モデルの得手不得手が相補的: DSはrecover 3/3・needle 1/3、GLMはneedle 3/3・recover 1/3。rename-hardは両者3/3でウォームアップ級（将来硬化の候補）。
- 失敗機序:
  - DS needle r1: 探索後にPacemaker介入のduck_callで待機終了（awaiting_user）。r2: output_echo＋wall timeout 600秒（6 loops）。r3のみ通過。
  - GLM recover r1: pip導入の試行錯誤＋本文なしedit×12で18 loopsを空費し無修正のまま終了。r2: orders/reportsは修正もshipping境界が残り失敗。r3は正解 `price - (price * rate)` も旧採点で弾かれていた。
  - LFM 0/9: 全件1ループ・`<|tool_call_start|>` 独自形式。Gauntletでもsymops非対応を確認。
- 採点バグ修正: orders.pyのcontainsが `price * (1 - rate)` の一字一句一致で、正しい別解 `price * (1.0 - rate)`（DS r3）・`price - (price * rate)`（GLM r3）を不合格にしていた。`price *` に緩和（`tests/test_gauntlet_scenarios.py` で3別解の受理と旧バグの拒否を固定）。verify_commandが正否の本門である点は不変。
- コスト注意: GLM recover r1は163k tokens・312秒。Gauntletは1試行が重く、都度手動・逐次実行を維持する。
- 検証: `uv run pytest tests/ -q` → **773 passed / 2 skipped**（770から3件追加）。

### 2026-09-17: Gauntlet初回の深掘り分析（27試行・追加課金なし）
- 定量: DS 7/9・GLM 7/9（再採点後）。成功率は同点だが中央値tokensはGLMが約2倍（rename 97k vs 26k、recover 109k vs 54k）。コスト効率軸ではDS圧勝。
- 機序の対比: GLM needle r1は5手直行（test→import先→修正、エラー0）。DS needle r3は25手迷走（存在しないpackage.json・`/workspace`等の幻覚を追いshell16連発、381秒）。DS r1/r2は未回復。needleの差は解能ではなく最短路の問題。
- DS recover r1はpip一発＋失敗1回から即手法切替。GLM recover r1はpip亜種10回以上空打ち＋本文なしedit×12で18ループ空費。Correction Guideがターン跨ぎで効かない実例。
- GLM rename r2は32アクション・299秒で通す粘り型。rename-hardは両者3/3でウォームアップ化（次弾硬化候補）。
- 運用の歪み: recoverの依存は同一モデル内r2/r3で易化（初回のみ真の4原因）。次回から毎run前uninstallを手順化。needleのtimeout 600秒は900秒へ引上げ候補。
- 開発示唆の優先度: (1)探索第一手の指針化（失敗テストのimportを辿れ）、(2)同一エラーのターン跨ぎ連発へのエスカレーション、(3)rename硬化。いずれも未着手。
- 限界: n=3のため優劣断定不可。LFM 0/9は床対照として正常。

### 2026-09-17: Qwen3-30B-A3B のツール方式スモーク比較
- OpenRouter `qwen/qwen3-30b-a3b`、framed、既存設定で fix-typo / create-fizzbuzz / edit-multi-hunk を Sym-Ops・Native 各1回。結果は `evals/results/qwen3-protocol-20260917-{symops,native}/`。
- 並列起動時に create-fizzbuzz の一時ワークスペースが同じ秒のIDで衝突したため、その2件は比較から除外。逐次再実行し `qwen3-protocol-20260917-recheck-{symops,native}/` に保存。計8試行、採用6試行。
- 採用結果は両方式とも成果物3/3合格。Sym-Opsは実際にwrite_file/edit_fileが実行され、LFMのような独自形式出力による実行不能は今回再現せず。モデル全体への一般化は不可。
- Nativeはedit-multi-hunkで編集本文に不正な `%%%` 区切りを送り、エラー後にSEARCH/REPLACEで回復。fix-typoも短いfind指定の失敗後に全文行指定で回復。外側のtool callingではなく編集引数の問題。
- Nativeのedit-multi-hunkは完了後の追加質問がduck_call扱いになり待機終了。再実行FizzBuzzの完了文に `<task_complete>` が残った。成果物合格と終了品質は別。
- 製品コード・設定変更なし。並列評価はresults-dirを分けても一時workspaceが衝突し得るため、修正までは同一シナリオを逐次実行する。

### 2026-09-19: E-3 run 手順の歪み除去
- `evals/runner.py`: `_ensure_clean_env()` を追加。fixture の `requirements.txt` に宣言されたパッケージを各 run 前に `pip show` / `pip uninstall -y` で除去。recover-quad の `tabulate` が前 run でインストールされた状態を残し、r2/r3 が依存不足条件を bypass するのを防ぐ。
- `evals/scenarios/gauntlet/needle-wide.yaml`: `timeout_seconds` を 600 → 900 に引上げ。DS needle r2 が 600 秒 wall timeout で打ち切られていたため、探索迷走時の余裕を確保。
- 検証: `uv run python -X utf8 -m pytest tests/test_gauntlet_scenarios.py tests/test_eval_analysis.py tests/test_eval_follow_up.py tests/test_eval_stages.py -q` → 29 passed / 1 warning。
