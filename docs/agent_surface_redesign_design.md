# モデル接触面の再設計: Sym-Ops v4・ツール面縮小・Tier運転プロファイル

**ステータス:** Phase 0・Phase 1・Phase 2 完了・Phase 3以降 未実装
**作成日:** 2026-07-02
**根拠:** 2026-07-02 実施のコード調査（4系統並列）＋設計議論。ターゲットモデル定義はユーザー確認済み。

---

## 1. 背景と動機

### 1.1 観測されている問題

強いモデルでは問題なく動作するが、弱いモデルでは自律動作時に以下が発生する:

- 思考ループ（同じ操作・思考の繰り返し）
- 存在しないツール・パラメータの呼び出し
- 幻覚（実在しないファイル内容やツール結果を前提に行動）
- 全般的な動作不安定

### 1.2 ターゲットモデルの定義（本設計の評価基準）

- **ローカルモデル + OpenRouter の安価モデル**
- 想定: Qwen3.6 / GLM4.5-flash / Gemma 4 クラス、**最大 30B 程度**
- 北極星ベンチマーク: **ローカルモデルで実用的なコーディングエージェントを動かすこと**

### 1.3 調査で判明した原因の分解（2026-07-02）

| 症状 | 主原因 | 原因はプロトコル構文か？ |
|---|---|---|
| 存在しないツール名 | ツール25個＋型情報なしの説明＋フィードバック欠損 | **いいえ**（`::action` 構文は正しく、名前が幻覚） |
| 存在しないパラメータ | ツール説明に型・必須/任意が出力されない | ほぼいいえ |
| 思考ループ | 停滞検知の穴（read-only除外等）＋フィードバック欠損 | いいえ |
| 幻覚 | コンテキスト予算の128K前提＋無通知の文脈喪失 | いいえ |
| パース失敗・AutoRepair 発動 | YAML フロントマター等の**周辺構文税** | **はい（ここだけ）** |

**中心的矛盾:** Duckflow は「LLMは間違える」前提を掲げながら、モデルに対して独自プロトコルの厳密出力・16〜18K文字のプロンプト遵守・25ツールからの正確な選択・較正不能な自己評価を要求している。ガードレール層（AutoRepair / Correction Guide / Pacemaker）が分厚いのは、接触面がモデルに負債を押し付けている症状である。

### 1.4 プロトコル選択の経緯（重要な整理）

- 旧 JSON（自由生成の ActionList）→ Sym-Ops 移行でエラーは大幅減（ユーザー実感）。これは「自由生成 JSON はエスケープ地獄＋構造保証なしの最悪の組み合わせ」だったためであり、**テキストプロトコル同士の優劣には何も言っていない**。
- ネイティブ Function Calling は、ターゲット（ローカルランタイム・安価プロバイダ）の対応品質がまちまちであり、**ランタイム機能に依存する設計は北極星と相性が悪い**ため主軸にしない。
- コードペイロードを JSON 文字列に入れるとエスケープ（`\n`, `\"`）が弱いモデルを壊す。Sym-Ops の `<<< >>>` 生テキストブロックはこの点で正しい設計であり、**維持する**。

### 1.5 導かれる方針

**Sym-Ops のフレーム（`::action @target` + `<<< >>>` ブロック）は維持し、周辺の構文税を除去する（Sym-Ops v4）。** 症状の主因である「意味論的負荷」（ツール面・説明・フィードバック・コンテキスト予算）への対処を最優先し、tier 別運転プロファイルで弱いモデルへの要求量を配給制にする。

---

## 2. 設計原則

1. **制御プレーンとペイロードの分離** — アクション選択・引数は構造化しやすい形式で、コード本体は生テキストブロックで。
2. **複雑さはプロンプト（モデルの義務）からハーネス（コードの義務）へ** — モデルが規則を守ることを期待するのではなく、システムが機械的に強制・肩代わりする。
3. **訓練分布への整合** — 独自規則は最小化。既存フォーマットからの軽微な逸脱でも弱いモデルは劣化する（Diff-XYZ 知見）。
4. **明示的な制御信号は維持** — `::response` / `::duck_call` はターン終了の明示信号であり、暗黙化はしない。思考と対話の分離自体は低負荷（推論モデルは `<think>` で同じ分離を訓練済み）。負荷が高いのはチャネルの重複（4→3に削減）。
5. **形式・面・自律性はシステムが決める** — モデルに選ばせない（`edit_format_search_replace_design.md` §7.1 原則のアクション層への拡張）。
6. **階層は「見せる」が「操作させない」** — Plan→Step→Task はハーネスが保持・注入し、モデルの操作は最小ツールに絞る。
7. **自律性はモデルの強さに応じて配給する資源** — 上限（クラッシュバリア）ではなくリード（leash）で制御する。
8. **tier を知るのはプロファイル解決の1箇所だけ** — 他のコードは tier を知らず、プロファイルの具体値のみを参照する。

---

## 3. 設計1: Sym-Ops v4（プロトコルの周辺税除去）

### 3.1 変更点

| 項目 | 現行 v3.2 | v4 | 根拠 |
|---|---|---|---|
| フレーム | `::action @target` | **維持** | 症状の主因ではない。ユーザー実感でも JSON より良好 |
| コンテンツブロック | `<<< ... >>>`（列0終端） | **維持** | エスケープ不要はテキスト形式最大の利点。列0規則も doctest 保護に必要 |
| 引数 | インライン key=value / YAML フロントマターの二択（判断規則が曖昧） | **YAML フロントマター廃止。** インライン `key=value`（値に空白があれば引用符）に一本化。大きなペイロードはブロック1個 | **最大の構文税。** `include: *.py` の YAML エイリアス誤解釈で全パラメータ消失（2026-06-18 実バグ）等、パーサー修正が延々続いている領域。`yaml.safe_load` 依存が消え、バグクラスごと消滅 |
| Vitals 記法（`::c/s/m/f`） | 応答時に申告（V-A3 で頻度削減済み） | **プロトコル仕様から完全削除** | 較正不能と結論済み（vitals_redesign）。UX の受け皿は V-B 実測表示 |
| `::note` | あり | **廃止**（`>>` 思考に統合） | note と `>>` の境界曖昧さが note-only ループを生んでいる（調査確認済み）。チャネルは思考(`>>`)/報告(`::response`)/相談(`::duck_call`)の3つに |
| `execute_batch`（`%%%` 区切り） | ツールとして公開 | **非表示化（機能は維持）** | パーサーの展開機能・テストは維持し、ツール説明・few-shot・プロンプトから完全撤去。強いモデルが習慣で出しても壊れない。トークン節約はネイティブ複数 `::action` が既に提供 |
| edit_file ペイロード | SEARCH/REPLACE マーカー | **維持** | 設計済み・実証済み（edit_format_search_replace_design.md） |

### 3.2 v4 の正規形（例）

```
>> auth.py の session 処理を分離する。まず現状を確認済み、編集に移る。

::edit_file @src/auth.py
<<<
<<<<<<< SEARCH
def login(user):
    session = create_session(user)
=======
def login(user):
    session = SessionManager.create(user)
>>>>>>> REPLACE
>>>

::run_command command="uv run pytest tests/test_auth.py -v"
```

- 引数はすべて1行の `key=value`。フロントマターなし。
- 思考は `>>`。ユーザーへの発話は `::response`、相談は `::duck_call` のみ。

### 3.3 後方互換

- 移行期間中、パーサーは旧形式（YAML フロントマター・`::note`・Vitals 記法）を**受理はするが文書化しない**（受理時に warning を記録し repair_load に計上）。
- 旧セッションの復元は影響なし（履歴はテキストのまま保存されている）。

### 3.4 対抗馬（案B: Cline/Roo 型 XML）の扱い

Qwen 系等は Cline/Roo の利用トレースで訓練されており XML ツール形式は分布内という利点がある。**v4 vs XML vs 現行 v3.2 は §7 のアクション層ベンチで決着する。** v4 が XML と同等以上なら移行コストの小さい v4 を採用。XML が有意に勝つ場合のみ案Bへ（その場合も本設計の他章はそのまま適用可能 — 外部プロトコルは LLMClient の変換層で交換可能なため）。

---

## 4. 設計2: ツール面の縮小（25 → 14/15/11）

### 4.1 仕分け表

| 現行ツール | 判定 | 移行先・理由 |
|---|---|---|
| `read_file` | ✅ 維持 | 中核 |
| `grep_files` | ✅ 維持 | 検索の主力 |
| `list_directory` / `find_files` / `get_project_tree` | 🔀 **`list_files` に統合** | 「ファイル構造を見る」の3変種。`path` + 任意 `glob` + 任意 `depth` で被覆。repo map 自動注入後の get_project_tree はユーザーコマンド（/scan）として存続 |
| `list_symbols` / `find_definition` | 🔀 **`find_symbol` に統合** | `name` 指定→定義位置+シグネチャ、`path` 指定→ファイルのシンボル一覧 |
| `search_archives` / `recall` | ❌ ツール面から撤去 | 「昔の記憶を探そう」という能動判断は弱いモデルに期待できない。ArchiveStorage と検索実装は維持し、長期記憶 L-c の自動注入の受け皿にする |
| `retrieve_result` | ✅ 維持 | **幻覚対策として重要**（圧縮で消えた全文の再取得 = 「見たつもり」の解毒剤）。説明文に「結果が切り詰められていたらこれを使う」と明記 |
| `edit_file` | ✅ 維持 | 主力 |
| `write_file` | ✅ 維持 | 弱いモデルでは whole-file が最良フォーマットという知見あり。弱 tier では推奨編集手段に昇格 |
| `replace_function` | ✅ 維持 | ast 検証付き関数単位置換は弱モデル向け本命（edit §7） |
| `delete_lines` | ❌ **廃止** | 実装が既に「REPLACE 空の edit_file」を強制 = 劣化コピー。edit_file の説明に「削除は REPLACE を空に」と1行で足りる |
| `append_file` | ❌ 廃止 | 使用頻度低。edit_file / write_file で代替。選択肢削減の価値が上回る |
| `delete_file` | ✅ 維持 | 破壊的操作の明示は安全設計上必要（承認ゲート） |
| `note` | ❌ 廃止 | §3.1 参照（`>>` に統合） |
| `response` / `duck_call` / `exit` | ✅ 維持 | 明示的なターン終了・制御信号（設計原則4） |
| `run_command` | ✅ 維持 | 中核 |
| `execute_batch` | ❌ 非表示化 | §3.1 参照（機能維持） |
| `propose_plan` | ✅ 維持 | 計画の言語化は協業ループの核 |
| `generate_tasks` / `execute_tasks` | ❌ **ハーネス移管** | plan 承認後にシステムが補助LLM（既存 `TaskListProposal` JSON 経路）を自動発火。モデルが「分解しよう」と選択する必要をなくす |
| `mark_step_complete` / `mark_task_complete` | 🔀 **`complete_step` に統合** | カーソル（現在の step/task）はハーネスが知っているため、モデルは「終わった」とだけ言えばよい。どの粒度が閉じるかはハーネスが判定 |
| `investigate` / `submit_hypothesis` / `finish_investigation` | ✅ 維持 | investigation モード限定で他モードの面を圧迫しない。仮説5回→duck_call の制御に使用。ただし「investigate 直後は観察必須」等のプロンプト規則はハーネス強制へ移す |
| `analyze_structure` / `generate_code` | ❌ **ツール面から撤去（システム駆動エスカレーションへ）** | 「自分より賢いLLMに聞くべきか」というメタ判断を弱いモデルにさせない。編集失敗 N 回で自動的に中モデルへ委譲（N は TierProfile が決定）。SubLLMManager 基盤は維持 |

### 4.2 整理後のモード別ツール面

| モード | 現行 | 整理後 | 内訳 |
|---|---:|---:|---|
| **task** | 25 | **14** | response, duck_call, exit / read_file, grep_files, list_files, find_symbol, retrieve_result / edit_file, write_file, replace_function, delete_file / run_command / complete_step |
| **planning** | 24 | **15** | task の編集・実行系 + propose_plan + investigate（complete_step の代わり） |
| **investigation** | 17 | **11** | 対話3 + 読取5 + run_command + submit_hypothesis + finish_investigation |

- **全 tier 共通の面から開始する**（面の分岐は保守コストが高い）。ベンチで tier 差が実証された場合のみ、弱 tier の追加絞り込み（find_symbol / retrieve_result の状況公開等）を検討する。

### 4.3 ツール説明の型付き出力

現状 `core_tools.py` は `inspect.signature()` で取得済みの型・デフォルト値を**捨てて**説明を生成している。整理後の全ツールについて、パラメータの**型・必須/任意・簡潔な意味**を説明に含める。存在しないパラメータ幻覚への最直接の対策。

```
- ::grep_files pattern="<regex>" [glob="*.py"] [path="."]: Search file contents.
  pattern (str, required), glob (str, optional, default "*"), path (str, optional, default ".")
```

### 4.4 計画系のハーネス移管: 「見せるが操作させない」

3階層（Plan→Step→Task）は **AgentState の SSoT としてそのまま維持**し、モデル接触面だけを平坦化する。長期目的の保持はモデルの記憶ではなく**プロンプトへの常時掲示**で解く（弱いモデルほどこちらが効く）。

```
┌─ AgentState（ハーネス側・不変）────────────────────┐
│ Plan → Step → Task の3階層 + カーソルをハーネスが管理    │
└──────────────────────────────────────────────┘
        ↓ 毎ターン、状態カードとして注入（読み取り専用・数十トークン）
┌─ モデルが見るもの ─────────────────────────────┐
│ Goal: 認証機能のリファクタリング                        │
│ Plan: ✓1. 調査  ▶2. AuthService分離  3. テスト          │ ← 全体地図（1行/step）
│ Now:  Task 2/4 — auth.py から session 処理を抽出        │ ← 今やること1つ
└──────────────────────────────────────────────┘
        ↑ モデルの操作は complete_step 1つだけ
```

- タスク分解: `propose_plan` 承認時にハーネスが `TaskListProposal`（補助 JSON 経路）を自動発火。
- `complete_step`: カーソル位置から task / step / plan のどれが閉じるかをハーネスが判定。虚偽完了への防御として、直近の実行結果（テスト結果等）を completion 時の状態カードに併記し、破壊的完了（plan 全体）はユーザー承認を挟む。

---

## 5. 設計3: Tier 運転プロファイル

### 5.1 アーキテクチャ

```
duckflow.yaml (available_models[].tier: low|mid|high)   ← ROADMAP T-1
        ↓ モデル選択時に解決（/model 切替で入れ替わる）
TierProfile（Pydantic・単一オブジェクト）
        ↓ 各コンポーネントは定数の代わりにプロファイル値を参照
PromptBuilder / core_tools / Pacemaker / MemoryManager / エスカレーション
```

- **tier を知るのはプロファイル解決の1箇所だけ。** 他のコードは `profile.max_loops` 等の具体値のみを見る（if-tier 分岐の散在を禁止）。
- tier 未指定のモデルは **low にフォールバック**（保守的既定。DEFAULT_CONTEXT_LENGTH=128K 過大既定と同じ轍を踏まない）。
- モデル個別の上書きを yaml で許す（tier はデフォルト束、モデルは個別調整可）。

### 5.2 プロファイルの次元

| 次元 | low（〜30B ローカル） | mid | high | 根拠 |
|---|---|---|---|---|
| ツール面 | コア面（§4.2） | コア面 | コア面（execute_batch 黙認） | 全 tier 共通から開始 |
| ツール説明 | 型+必須のみの簡潔版 | 標準 | 標準 | 認知負荷 vs 情報量 |
| few-shot | 回復例中心の短縮版 | 標準 | 最小（キャッシュ効率優先） | 弱モデルは例が必須、量は絞る |
| repo map 注入 | 0〜500 tokens | 1500 | 1500 | 履歴予算の保護 |
| 編集フォーマット推奨 | replace_function / write_file 優先 | SEARCH/REPLACE | SEARCH/REPLACE | edit §7 + Diff-XYZ（小型は whole-file/関数単位） |
| max_loops | 8〜10 | 15〜20 | 35 | 暴走許容量は信頼度に比例 |
| チェックイン間隔（§5.3） | 4〜5 アクション | 10 | なし（PC-1 解禁） | 自律性の配給 |
| エスカレーション閾値 | 編集1失敗で中モデル委譲 | 2失敗 | なし | §4.1 Sub-LLM 移管の受け皿 |
| 履歴圧縮の強度 | 強（grep 5件、head/tail 10行） | 標準 | 標準 | 弱モデルの予算保護 |
| コンテキスト長不明時の既定 | 16K | 32K | — | 128K 過大既定の是正 |

数値はすべて初期値であり、§7 ベンチで較正する。

### 5.3 自律性: 「上限」ではなく「リード（leash）」

現状の自律制御は max_loops というクラッシュバリアのみ。手前に**ソフトなチェックイン**を導入する:

- `loop_count` が `profile.checkin_interval` に達する、または step が完了したら、ハーネスが「ここまでの進捗を `::response` で報告してターンを終える」指示を注入する。
- モデルが従わない場合（弱いモデルで想定される）、次のループでハーネスが**強制的にターンを終了**し、実行済みアクションの要約を表示する（二段構え。モデルの遵守に依存しない — 設計原則2）。
- ユーザーは Enter 一発で続行できる（摩擦は最小）。

効果: 暴走・思考ループの被害半径が構造的に K アクションに制限され、Pacemaker の検知漏れがあっても実害が小さくなる。これは制限ではなく**協業ループの実装そのもの**（弱いモデルは長く独走させず、こまめに肩を並べる）。PC-1（Proactive Continuation, max_loops 50）は high tier 専用フラグとして本プロファイルに収容する。

### 5.4 設定スキーマ（イメージ）

```yaml
llm:
  available_models:
    - name: qwen3.6-32b
      provider: ollama
      tier: low
    - name: glm-4.5-flash
      provider: openrouter
      tier: low
      max_loops: 12          # モデル個別上書き
    - name: claude-sonnet-5
      provider: anthropic
      tier: high

agent:
  tier_defaults:             # 省略可。コード内デフォルトの上書き用
    low:
      checkin_interval: 5
```

---

## 6. 前提修正（Phase 0 止血 — 本設計と独立に必要）

2026-07-02 調査で判明したバグ・欠損。本設計の効果測定を歪めるため先行して修正する:

| # | 修正 | 対象 |
|---|---|---|
| 6-1 | 停滞検知の修復: read-only ツールも「同一パラメータ+同一結果」なら検知対象に。パラメータ比較を正規化（sorted dict） | `pacemaker.py` `_detect_stagnation()`。失敗中の `test_pacemaker_detects_repeated_action_stagnation` もこれで解消 |
| 6-2 | フィードバック3穴: (a) パラメータドロップ、(b) パース失敗理由、(c) 完全空パース を `SyntaxErrorInfo` に記録し既存 Correction Guide 経路へ | `core_action_executor.py` / `llm_client.py` |
| 6-3 | `DEFAULT_CONTEXT_LENGTH` 128K → 32K + 不明モデル警告表示（§5.2 で tier 別化するまでの暫定） | `llm_client.py` |
| 6-4 | AutoRepair 誤修復抑制: 行頭動詞のアクション化を「`@` や引数らしき構造を伴う場合のみ」に厳格化 | `sym_ops.py` `_fix_missing_symbols_line()` |

---

## 7. アクション層ベンチマーク計画

`benchmarks/`（編集形式ベンチ）の資産・流儀を流用し、**プロトコル×モデルの2次元**で実測する。議論で決めるのは候補の絞り込みまで、最終決定はベンチで（edit format と同じ作法）。

- **比較軸1（プロトコル）:** 現行 v3.2 / v4（§3） / XML（Cline型・案B）
- **比較軸2（モデル）:** Qwen3.6 / GLM4.5-flash / Gemma 4（+対照として高 tier 1モデル）
- **指標:**
  - repair_load（AutoRepair・寛容パースの発動率）
  - アクション認識率（意図したツールが正しく呼ばれる率）
  - パラメータ幻覚率（存在しないパラメータ・欠損必須パラメータ）
  - マルチターンタスク完走率（読み→編集→検証の一連タスク）
- **判断基準:** v4 が XML と同等以上なら v4 採用（移行コスト最小）。XML が有意勝ちの場合のみ案Bへ。
- ツール面縮小（§4）とチェックイン（§5.3）の効果も、before/after のマルチターン完走率で測る。

---

## 8. 実装計画（フェーズ分割）

> 依存: Phase 0 → 1 → 2 は順次。Phase 3 は §7 ベンチの決着後。Phase 4/5 は Phase 1 のプロファイル基盤に載る。

### Phase 0: 止血 + ベンチ整備
- ✅ **完了（2026-07-02）**: §6 の4修正を実装（各修正に回帰テスト付き、`python -X utf8 -m pytest tests/ -q` で 546 passed / 2 skipped）。詳細は PROGRESS.md 2026-07-02 参照。
- ❌ 未着手: アクション層ベンチの実装（オフライン層: プロンプト→期待アクションの採点。オンライン層: 実モデル接続）

### Phase 1: TierProfile 骨格 + T-1
- ✅ **完了（2026-07-02）**: `companion/config/tier_profile.py` 新規（`TierProfile` Pydanticモデル・tier別デフォルト・`resolve_tier_profile()` によるyaml解決・モデル個別上書き）。`available_models[].tier` フィールドに対応、`/model current`・`/model list` に tier 表示を追加。`LLMClient` に `tier_profile` を配線（init・モデル切替時に再解決）。コンテキスト長の未知モデル既定値のみ `TierProfile.unknown_model_context_length` 経由に配線（Phase 0 の安全機構の精緻化、既知モデルには無影響）。詳細と「数値に実影響する箇所への配線をPhase 5に委ねた」判断理由は PROGRESS.md 2026-07-02 参照。
- ✅ **完了（2026-07-02・残タスク解消）**: Pacemaker（`max_loops` の tier 別 ceiling）・repo_map（`repo_map_token_budget`）・履歴圧縮（`history_compression` の strong/standard プロファイル）への配線を実装。数値自体（10/18/35 等）はまだ初期値のままで、較正は引き続き Phase 5（§7 ベンチ後）で行う。詳細は PROGRESS.md 2026-07-02 参照。
- ❌ 未着手: `checkin_interval`/`escalation_threshold` の実配線（Phase 4/5 の機能自体が未実装のため配線先がまだない）。`/model` によるインタラクティブなtier選択UI。

### Phase 2: ツール面縮小 + 説明強化
- ✅ **完了（2026-07-02）**: `list_files` / `find_symbol` / `complete_step` 統合ツールを実装。`note` / `delete_lines` / `append_file` / `search_archives` / `analyze_structure` / `generate_code` / `execute_batch` はモード面から撤去しつつ内部登録は維持。`list_directory`/`find_files`/`get_project_tree`/`list_symbols`/`find_definition`/`mark_step_complete`/`mark_task_complete` は統合先へ完全移行のため登録解除。ツール説明に型・必須/任意を出力（Optional型はアンラップして表示）。few-shot・静的Sym-Opsプロトコル文書・エラーガイダンス文言を新ツール面に更新。task/planning/investigation の公開ツール数はそれぞれ14/15/11で設計値と一致（テストで固定）。詳細は PROGRESS.md 2026-07-02 参照。
- ⚠️ **スコープ縮小**: `generate_tasks`/`execute_tasks` は Phase 4（ハーネス駆動タスク分解）が未実装のため、今回はモード面から外していない（設計上は撤去対象だが、代替の自動発火機構ができるまで維持）。

### Phase 3: Sym-Ops v4（ベンチ決着後）
- パーサー: インライン key=value 一本化（`yaml.safe_load` 依存の除去）、旧形式は受理+warning
- プロンプト・few-shot から YAML フロントマター・Vitals 記法・note を撤去
- Vitals 申告のプロトコル削除（V-B 実測表示への引き継ぎは vitals_redesign_design.md に従う）

### Phase 4: 計画系ハーネス移管 + エスカレーション
- 状態カード（Goal + 全体地図 + Now）の注入
- `propose_plan` 承認 → `TaskListProposal` 自動発火
- `complete_step` のカーソル判定・虚偽完了防御
- 編集失敗 N 回 → SubLLMManager 自動委譲（N = profile.escalation_threshold）

### Phase 5: チェックイン自律制御 + プロファイル較正
- §5.3 の二段構えチェックイン実装
- PC-1 を high tier 専用フラグとして統合
- §7 ベンチでプロファイル数値（max_loops / checkin_interval / repo map 予算等）を較正

### テスト（各フェーズに付随）
- Phase 1: プロファイル解決（tier 別デフォルト・yaml 上書き・未指定→low）、配線後の挙動同一性
- Phase 2: 統合ツールの単体テスト、モード別公開面の回帰テスト（`test_core_mode_mapping.py` 改修）
- Phase 3: v4 パース・旧形式受理+warning・repair_load 計上
- Phase 4: complete_step のカーソル判定、自動タスク分解、エスカレーション発火
- Phase 5: チェックイン強制終了、tier 別 max_loops

---

## 9. 影響ファイル（主要）

| 領域 | ファイル |
|---|---|
| プロファイル | `companion/config/tier_profile.py`（新規）, `config_loader.py`, `duckflow.yaml` |
| プロトコル | `companion/utils/sym_ops.py`, `utils/response_format.py`, `base/llm_client.py` |
| ツール面 | `companion/core_tools.py`, `tools/file_ops.py`, `tools/symbols.py`, `tools/plan_tool.py`, `tools/task_tool.py`, `tools/sub_llm_tools.py` |
| プロンプト | `companion/prompts/templates.py`, `prompts/few_shot.py`, `prompts/builder.py` |
| ループ制御 | `companion/core.py`, `core_loop_helpers.py`, `core_action_executor.py`, `modules/pacemaker.py` |
| メモリ | `companion/modules/memory.py`, `tool_history_policy.py` |
| ベンチ | `benchmarks/`（アクション層追加） |

---

## 10. リスクとオープンな問題

1. **統合ツールのパラメータ肥大** — `list_files` が3ツール分の引数を抱えて逆に複雑化するリスク。引数は `path` / `glob` / `depth` の3つまでに制限し、超える要求は仕様側を疑う。
2. **complete_step の虚偽完了** — モデルが作業せずに完了を主張する。§4.4 の防御（実行結果併記・plan 完了の承認）で緩和するが、検証の自動化（テスト実行の強制）は将来課題。
3. **プロンプトキャッシュへの影響** — tier×モードでプロンプト変種が増えるが、tier はモデルに固定されるため同一セッション内は1変種。キャッシュヒット率への実害はない見込み。
4. **XML 案が勝った場合の追加コスト** — Phase 3 の作業がパーサー置換に拡大する。他フェーズは外部プロトコル非依存のため影響なし（LLMClient の変換層が吸収）。
5. **チェックイン UX の摩擦** — low tier で4〜5アクションごとの停止が煩わしい可能性。Enter 継続の摩擦を最小化し、間隔はベンチと dogfooding で調整。
6. **search_archives 撤去による recall 喪失** — 自動注入（L-c）実装までの間、過去文脈の能動検索手段が消える。実害が出る場合はユーザーコマンド（/recall）として先行提供。
7. **旧形式の受理期間** — 無期限受理は「文書化されない仕様」を生む。ベンチで v4 定着を確認後、メジャーバージョンで受理終了を判断。

---

## 11. 既存ドキュメント・ロードマップとの関係

| ドキュメント | 関係 |
|---|---|
| `edit_format_search_replace_design.md` §7 | tier 概念の共通前提を本設計 §5 が実装（形式選択は §7 のマッピングを TierProfile のフィールドとして収容） |
| `vitals_redesign_design.md` | V-A（完了）の延長として Vitals 記法をプロトコルから削除（§3.1）。V-B 実測テレメトリは repair_load の供給元として §7 ベンチと連携 |
| `code_navigation_context_design.md` | 「検索させない」思想をツール面（§4.1 統合・撤去）と repo map 注入の tier 配給（§5.2）で完成させる |
| `cooperation_loop_design.md` | チェックイン（§5.3）は協業ループの実装。「弱いモデルは長く独走させず、こまめに肩を並べる」 |
| `docs/ROADMAP.md` | T-1（tier 整備）= Phase 1。PC-1 = Phase 5 に統合（high tier 専用化）。V-B2 の実測算出は §7 の repair_load と共有。本設計採用時は ROADMAP への反映（Sprint 再編）が必要 |

---

## 12. 参考

- 2026-07-02 コード調査（4系統: プロンプト構造 / パーサー・フィードバック / ループ制御 / 履歴・コンテキスト管理）
- 2026-06-13 deep-research（編集フォーマット・検証済み16件）: 独自記法は弱モデルに不利 / モデル規模依存（小型= whole-file・冗長形式）/ 寛容パッチ適用で9倍改善
- JetBrains Diff-XYZ (https://arxiv.org/html/2510.12487v1) / Meta 実運用評価 (https://arxiv.org/pdf/2507.18755) / aider unified-diffs (https://aider.chat/docs/unified-diffs.html)
