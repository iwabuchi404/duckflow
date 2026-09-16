# ツール呼び出し方式の差し替え設計: Sym-Ops / Native

**ステータス:** Phase A 実装済み（2026-09-14）。既定はSym-Opsのまま、nativeは実験経路。
**作成日:** 2026-09-13
**前提:** 検証プローブ（`evals/tool_probe/`）でM2.1の往復能力を確認済み。主ループのnative分岐（`_chat_native`）は実装済み。

**Phase A からの設計差分:**
- プロンプトはツール説明ブロック置換に加え、§6・reasoning行・`<tools>`節・モード指示のSym-Ops文法除去まで実施（併送は実験を無効化するため）。
- `duck_call` はAPI定義に含めない。nativeの文末 `?` は内部 `duck_call` アクションへ変換する（LLM呼び出し追加なし）。
- 履歴再構成は実行ジャーナル（turn_id/tool_call_id/tool_name/action_index/status/executed/result）のID基準。順序zipはjournalなし時のフォールバック。
- API例外は `parse_error_type="api_error"` で完了応答にしない（Sym-Ops側の同種経路は凍結・不変）。

**2026-09-16 レビュー修正（Phase A 堅牢化）:**
- 履歴再構成の対応付けを位置消費から**ターンID基準**へ変更。`LLMClient` が `{epoch}:{turn}` をログエントリの `_turn` と `Action.native_turn` に付与し、executor が履歴サマリへ `_native_turn` をスタンプする。`reset_native_log()` 後の旧タスクサマリ・強制実行（pacemaker/parse-failure duck_call）・pruning挿入サマリによるずれを解消。`_native_turn` は単調増加（リセットしない）＋プロセス毎epochで、セッション復元や前タスクのサマリと衝突しない。
- **孤児tool_callの解消**: journalに記録のないcallへは合成toolメッセージ（"[tool call produced no recorded result: ...]"）を返す。assistantにtool_callsがあり結果が無いメッセージはAPIが400で拒否するため。executor側でも全終端点（ok/error/denied/blocked/filtered/dropped/skipped）をjournal記録する二重防御——`filter_known_actions`・`limit_actions_per_turn` はリストを破壊的に変更するため、実行前スナップショット `proposed_actions` で照合し、fail-fast中断・KeyboardInterrupt残分は終末スイープで `skipped` 記録。
- テキストのみのターン（response/duck_call）はassistant contentをそのまま復元。全件フィルタでサマリが空のターンは `":: (all proposed actions filtered)"` アンカーを挿入して結果を失わない。
- **Sym-Ops文法リーク対策**: native時はFew-shot不送（全例が `::`/`<<<>>>` を含むため）。Correction Guideのhint・fallback例とジャーナルbodyは `sanitize_tool_references` で `::name @target` → `name` に変換（`std::vector` 等を壊さないよう `::` 直前に単語文字/コロンを許可しない境界条件付き）。`NATIVE_TOOL_PREAMBLE` に「結果内の `::name` 表記は同名ツールへの言及」と明記。`build_intervention_prompt` はprotocol引数を取り、native時はプレーンテキスト返答を指示。
- スキーマの引数descriptionをツールdocstringの `Args:` 節から生成（従来のプレースホルダ廃止）。
- 既知の非対称: journal bodyは12,000文字でキャップ（Sym-Ops側エンベロープは圧縮済み全文）。大きいread_file結果で入力差が出るためA/B解釈時に留意。

---

## 1. 背景と目的

- 現行メインループはSym-Opsテキストを `ActionList` へ変換する（`LLMClient.chat()` → `_parse_response`）。API native の tools 送受信は未実装。
- research（`docs/research/tool-calling-support-2026-09-13.md`）でE2E対象4モデルの掲載対応を確認し、M2.1を最初のA/B対象に指名済み。
- 目的は「Sym-Opsとnativeを簡単に差し替えられる仕組み」を作り、同一課題・同一条件で比較できること。**どちらが正解かの事前断定はしない。**

## 2. 現状の接合点（コード実態）

| 層 | 現状 | 差し替えとの関係 |
|---|---|---|
| `LLMClient.chat(messages, response_model=ActionList)` | Sym-Opsテキスト取得→`_parse_response`で変換 | **差し替え点**。ここだけを分岐させ、呼び出し側は `ActionList` 受領のまま変えない |
| `agent.tools: Dict[str, Callable]`＋`MODE_TOOL_MAPPING` | モード別公開制御 | 両方式で共通利用。native用JSON Schemaは `inspect.signature` から自動生成（`core_tools._format_type_name` の流用） |
| `execute_actions(ActionList)` | 承認・fail-fast・履歴注入 | **方式非依存**。両経路が `ActionList` を出せばそのまま使える |
| `conversation_history: List[{role, content}]` | テキストのみ | **最大の設計点**（§4）。nativeは tool_calls／tool-role メッセージの保持が必要 |
| Correction Guide／AutoRepair | Sym-Ops専用 | native側は tool結果による引数誤りフィードバックで代替（§5） |
| 実験スイッチ | `DUCKFLOW_FEW_SHOT_FRAMING` の前例あり | `DUCKFLOW_TOOL_PROTOCOL=symops \| native` で同様に切替 |

## 3. 設計方針

1. **呼び出し側は `ActionList` のまま**。差し替えは `LLMClient` 内部の「取得→変換」部分に閉じる。`core.py` のループ、`execute_actions`、承認ゲートに手を入れない。
2. **ツール定義は単一出所**。登録済みCallableのシグネチャ＋Docstringから両方式の説明を生成する。native専用の手書きスキーマを増やさない（ドリフト防止）。
3. **モード別公開は共通**。`UNIVERSAL_TOOLS`／`MODE_TOOL_MAPPING` の集合をそのままnative送信ツール集合にする。`response`／`exit`／`duck_call` 等の制御系は関数呼び出しではなく「終了シグナル」として扱う（§4.2）。
4. **履歴は二重化しない**。テキスト履歴（表示・セッション・プロンプト用）を正とし、native用メッセージはターンごとに再構築する（§4.1）。

## 4. 詳細設計

### 4.1 履歴戦略（採用案: ターンごと再構築）

- `conversation_history` は現行のテキスト形式を維持（UI表示・セッション復元・Token概算への影響ゼロ）。
- nativeターンでは、直近の `[TOOL_RESULT]` エンベロープ付き履歴から tool-role メッセージを再構成し、assistant側の tool_calls は `raw_responses`（既にverbatim保存あり）から復元する。
- 比較の公平性：Sym-Ops側も同じテキスト履歴を見るため、両方式の入力差は「ツール説明の形式」と「当ターンのtool定義の有無」に限定される。差の帰属が明確。
- 代替案（履歴にtool_callsを混載）は不採用。プロンプト構築・表示・セッション復元の全経路に分岐が漏れ、差し替えの局所性が崩れる。

### 4.2 制御系アクションの扱い

`response`／`exit`／`duck_call` はLLMへのtool定義に含めない。native応答の通常テキストを Sym-Ops の `::response @...` 相当として扱い、`duck_call` 相当（質問文＋停止）は「tool呼び出しなし＋`?` 終端テキスト」の検出で `tag_asked_question` と同じ基準に寄せる。`finish_investigation` 等のモード遷移系は通常toolとして定義する。

### 4.3 スキーマ生成規則

- 必須引数＝デフォルトなし、`content`／`body` 等のブロック系引数は `type: string` の通常引数として定義する（nativeには `<<< >>>` がないため。モデルは全文を文字列で渡す）。
- `**kwargs` は展開しない（現行のツール説明と同様に除外）。
- 生成スキーマの単体テストを必須化（全登録ツールが有効JSON Schemaになること、requiredの一致）。

### 4.4 切替方法

- `DUCKFLOW_TOOL_PROTOCOL` 環境変数（既定 `symops`）。`evals/runner.py` に `--tool-protocol` を追加し、experiment記録（`expects_question` と同様）に保存する。分析は試行時値を優先する。
- `use_mock` 時はsymops固定（モックはテキスト応答のため）。

## 5. フィードバック経路の対応表

| Sym-Ops側 | native側 |
|---|---|
| AutoRepair（構文修復） | 不要（APIが形式を保証）。ただし意味的誤り（存在しない引数等）はAPIエラーとして返る |
| Correction Guide（次ターン注入） | tool結果メッセージとして即時返却（`is_error` 相当）。`last_syntax_errors` 経路は使わない |
| 空応答リトライ | そのまま共通利用 |
| fail-fast／承認ゲート | `ActionList` 以降のため共通利用 |

## 6. 比較方法（A/B）

- 対象課題：`ambiguous-output`（協業）＋`multi-file-rename`（編集）の各9試行 ×2方式 ×M2.1。出力課題は現行の良好条件のため、差が出るのは編集・回復側と想定。
- 指標：既存の3段階（confirmed／artifact_ok／natural_completion）＋end_state分布に加え、トークン中央値・呼び出し数中央値を比較する。`stage_counts`／`end_counts` は試行時protocolで分けて集計できるよう、分析側は `experiment.tool_protocol` を見る（実装時に追加）。
- 判定基準の事前固定：方式の優劣ではなく「どの段階・どの失敗型に差が出たか」を報告する。n=9ずつのため効果の断定はしない（従来通りの注意書き）。

## 7. 実装Phase

- **Phase A（機構）**: スキーマ生成＋`chat()` 内分岐＋runner記録＋単体テスト。プロンプト本文の変更なし。
- **Phase B（計測）**: 上記A/Bを各9試行で実行し、3段階で報告。
- **Phase C（判断）**: 結果を見て、native恒常化／Sym-Ops維持／併用（tier別等）を判断。判断はdecisions確認後に記録する。

## 8. リスクと非目標

- モデル・経路依存：掲載対応でも実動作は別（research §4の注意）。`require_parameters` 等の経路限定はPhase Aに含めない。失敗時は error 記録に留める。
- 補助LLM呼び出し（JSON/Pydantic）は対象外。主ループのみ。
- プロンプトキャッシュ最適化の再測定はしない（入力形式が変わるため単純比較不可。トークン量のみ記録）。
- Vitals・Pacemaker・Memoryの変更なし。
