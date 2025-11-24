### ゴール
- ref解決と型整合を徹底し、LLM計画どおりにアクション間データ連携が成立すること
- プラン→ステップ→タスクの流れが実行できること
- `prompt_override`/`action_results`/`step_id`の取り扱いを堅牢化し、400系や型例外を撲滅
- 会話履歴がターン間で保持され、「会話履歴が存在しません」警告が消えること
- LLMプロンプトの実例/ガイダンスが実在ツールと一致すること

---

### 対象ファイル
- `companion/enhanced_core_v8.py`
- `companion/plan_tool.py`
- `companion/tools/user_response_tool.py`（呼び出し側の引数も確認）
- `companion/prompts/prompt_compiler.py`（型ガードは導入済だが追補）
- `debug_dual_loop.py`（ライフサイクル修正は導入済）

---

### 変更サマリ（実装項目一覧）
- ref解決の「キー別・型別正規化」ルールを導入（`_preprocess_action_args`）
- 実行直前の「軽量型ガード」（`_execute_action_v8`前）を強化
- プラン作成の本来フローへ復帰（`_handle_plan_propose`→`PlanTool.propose`を委譲）
- `PlanTool.propose`の戻り値に`first_step_id`を含める（なければ`get`で抽出）
- 会話履歴保存の共通化（`process_user_message`末尾で一括保存）
- プロンプト例の整合性（存在しない`file_ops.read_file_section`を排除、実在ツール名に統一）
- ログ強化（ref解決と正規化の経路をINFO/DEBUGで記録）

---

### 実装手順（詳細）

#### 1) ref解決のキー別・型別正規化（最重要）
対象: `companion/enhanced_core_v8.py` の `def _preprocess_action_args(self, args, turn_results)`

- 方針: 参照元の実行結果（`turn_results[ref_id]`）をキーの意味に応じて「期待型」に正規化する
  - `action_results`:
    - 入力が `"ref:xxx"` の場合 → `turn_results['xxx']` を取り出す
    - 取り出し結果が dict の場合 → `[that_dict]` に包む
    - 既に list[dict] の場合 → そのまま
    - それ以外（str/None等）→ フォールバック: `[{ "raw": value }]` としてLLM整形側に渡せる最低限の形にする（ログWARN）
  - `prompt_override`:
    - 入力が `"ref:xxx"` の場合 → `turn_results['xxx']` から以下優先で文字列抽出
      1. もし`operation`が`structured_file_ops.read_file_chunk`/`read_file`っぽい → `data.get('content') or content`
      2. `response`キーがあればそれを文字列化
      3. 最後に`str(参照結果)`で文字列化
    - 最終的に str を保証（非文字列は`str(...)`）
  - `step_id`:
    - 入力が `"ref:xxx"` の場合 → `turn_results['xxx']`から「プラン/ステップ関連」の値を抽出
      - まず `result.get('plan_id')` があれば、`PlanTool.get(plan_id)`の結果から先頭ステップIDを抽出して使用（この抽出は「2)」の実装後は`first_step_id`を返すので簡略化可）
      - 直接 `result.get('step_id')` があればそれを採用
      - 見つからなければ「未解決ref」として上位にエラー返却（後続中断）
  - その他のキー:
    - 参照が見つかったらそのまま代入
    - 見つからなければ従来どおりWARNログ＋そのまま（上位の未解決チェックで中断）

- 付随修正（すでに一部導入済のため確認）:
  - `_dispatch_actions`内で`processed_args`を`action.args`に再代入して実行
  - 未解決refの残骸（`"ref:..."`文字列）がある場合は当該アクションを`success=False`で確定し、中断

- ログ:
  - 正規化結果をDEBUGで、未解決や型フォールバックをWARNで記録

#### 2) 実行直前の型ガード（軽量）
対象: `companion/enhanced_core_v8.py` の `_execute_action_v8` 呼出前または内部直前

- 以下をチェックし、違反なら「わかりやすいエラー」を返す
  - `user_response_tool.generate_response`:
    - `action_results` は list であること（要素は dict 想定だが JSON化可能なら許容）
    - `prompt_override` は str
  - `task_tool.generate_list`:
    - `step_id` は str
  - 失敗時: `{"success": False, "error": "引数'<name>'の型が不正: 期待<type> 実際<type>", "operation": ...}` を返却

#### 3) 本来フローへの復帰：`plan_tool.propose`委譲
対象: `companion/enhanced_core_v8.py` の `_handle_plan_propose`

- 変更前: コアが手製で`Plan(steps=[])`を生成
- 変更後: `await self.plan_tool.propose(goal)`を呼び、その戻りをそのまま返す（`success/plan_id/steps/first_step_id?`）
- 以降の`task_tool.generate_list(step_id="ref:plan_core_engine")`は、1)と4)の対応により`step_id`が適切に解決される

#### 4) `PlanTool.propose`の拡張（first_step_idを返す）
対象: `companion/plan_tool.py`

- 既存: LLMが利用可能な場合はステップを自動生成して`plan.steps`へ格納
- 追加:
  - 生成直後に `first_step_id = plan.steps[0].step_id if plan.steps else None` を算出
  - `propose`の戻り値に`"first_step_id": first_step_id` を含める
- これにより 1) `step_id`正規化ルールが簡略化でき、`ref:plan_*` → 直接 `first_step_id` を採用

#### 5) 会話履歴保存を共通化
対象: `companion/enhanced_core_v8.py` の `process_user_message`

- 現状: `action_execution`分岐内のみ保存される構造
- 変更: `response`を得た後、分岐に関係なく共通で
  - `AgentState.add_conversation_message('user', user_message)`
  - `AgentState.add_conversation_message('assistant', response)`
- 例外時も既に同様の保存実装あり（`current_agent_state`参照を採用）

#### 6) プロンプト・ガイダンスの整合性
対象: `companion/enhanced_core_v8.py` の `_generate_hierarchical_plan` のプロンプト文

- 変更:
  - 存在しない`file_ops.read_file_section`の文言が出ないよう、例とガイドラインを「`structured_file_ops.read_file_chunk`で読み、結果を`user_response_tool.generate_response`へ渡す」に統一
  - 「存在しないツール名は使わない」「refはaction_idにしか参照してはならない（任意の文字列を参照しない）」を明記

#### 7) 呼び出し側の引数整合（最終確認）
対象: `companion/enhanced_core_v8.py` の `_format_final_response`

- 呼び出し: `await self.user_response_tool.generate_response(action_results=..., user_input=user_message, agent_state=self.agent_state)`
- 既にキーワード指定のため新シグネチャに整合（順序差分の影響なし）。このままでOK

#### 8) 追加ログ（観測可能性の強化）
- `ref:`正規化の各分岐でDEBUG/WARN
- 400系発生時に、`prompt_override`の実際の型・長さ（先頭100文字）をINFOで記録（秘匿情報に配慮しつつ）
- `plan_tool.propose`実行後の`steps`件数/`first_step_id`記録

---

### 動作確認（手順）

#### シナリオA：ファイル要約（B: 指針・例示）
1. 入力: 「game_doc.mdを読んで、その概要を教えて」
2. 期待:
   - LLM計画に `read_file_chunk(action_id=read_game_doc)` → `user_response_tool.generate_response(action_results="ref:read_game_doc", user_input=...)`
   - 実行時に `action_results` が list[dict] に正規化
   - 応答生成成功。400なし
   - プロンプト内注記に「切り詰め/総文字数」が出力される

#### シナリオB：prompt_overrideでのref参照
1. 入力: 「ドキュメントの内容をもとに実装プランを作成」
2. 期待:
   - `prompt_override: "ref:read_game_doc"` が来ても、正規化で文字列（content）抽出
   - Groq 400が発生しない
   - `prompt_override: True` ログ、`prompt_length`が妥当な範囲

#### シナリオC：実装開始（A: 実装・変更）プラン→ステップ→タスク
1. 入力: 「コアエンジンの実装から始めて」
2. 期待:
   - `plan_tool.propose` → 戻りに `plan_id` と `first_step_id`
   - `task_tool.generate_list(step_id="ref:plan_core_engine")` が `first_step_id` を正しく受け取る
   - 「ステップが見つかりません」消滅
   - `task_loop.run`まで到達し、委譲/簡易実行のいずれかが成功

#### シナリオD：会話履歴の持続確認
1. 連続で3ターン以上やり取り
2. 期待:
   - `prompt_compiler`の「会話履歴が存在しません」WARNINGが消滅
   - 各ターンで `AgentState`に履歴が蓄積

---

### 受入基準（ログ観点）
- 400 Bad Request（messages.0.content…）が再発しない（prompt_override 正規化）
- `AttributeError: 'str' object has no attribute 'get'` が発生しない（action_results 正規化）
- `ステップが見つかりません` が「計画→生成→実行」シナリオで発生しない
- `WARNING - 会話履歴が存在しません` が出ない（ターン継続時）
- `ref:`未解決は、該当アクションでエラー化し中断（その旨の明確なログ出力）
- 主要イベント（正規化結果、first_step_id、prompt_overrideの型/長さ）がINFO/DEBUGで追跡可能

---

### リスクと回避策
- 既存のLLM計画が「未知キー」をparametersへ渡す可能性:
  - 未知キーは素通し（ログのみ）。ツール側に影響なし
- `PlanTool.propose`の非同期失敗:
  - 失敗時は従来のフォールバックを維持（メッセージで案内）
- `prompt_override`に巨大コンテンツが渡る:
  - 先頭N文字に抑制してログ、安全のため最大長でトリム（ツール呼び出しはフル送信でも可）

---

### 作業見積と順序
1) `_preprocess_action_args` 正規化（3-4h）
2) `_execute_action_v8` 型ガード追加（1h）
3) `_handle_plan_propose` → `PlanTool.propose`委譲（1h）
4) `PlanTool.propose`の`first_step_id`返却対応（1-2h）
5) `process_user_message` 履歴保存の共通化（0.5h）
6) プロンプト整合（0.5h）
7) ログ改善（0.5h）
8) 動作確認（A-D）（2-3h）

---

### ロールバック
- 各変更はコミット分割（1: ref正規化、2: 型ガード、3: plan委譲、4: first_step_id、5: 履歴、6: プロンプト、7: ログ）
- 不具合時は該当コミットのみをrevert可能

---

### 補足メモ（実装のポイント）
- 「正規化」は「意図された引数型に合わせる」ことが目的。refの「中身を丸ごと横流し」しない
- `prompt_override`は常にstrにする（ファイル読み込み結果は`content`を使う）
- `action_results`は必ずlistに揃える（1件でも配列化）
- `step_id`は文字列ID（`first_step_id` 推奨）に確実に落とす

この手順に従えば、提示ログで観測された全ての不具合（400/型例外/未連携/履歴欠落）は解消され、v4アーキテクチャのデータ連携パイプラインが安定稼働します。