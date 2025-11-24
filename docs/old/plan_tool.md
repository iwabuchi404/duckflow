**PlanTool 設計ドキュメント v1**

**概要**
- **目的:** プランの生成/保存/承認/実行を明示的なツールAPIとして提供し、承認済み
の ActionSpec 群のみ実行する。
- **適用範囲:** Companion 層（EnhancedCore/DualLoop）からの明示呼び出し、Approva
lSystem/Rich UI 連携、PlanExecutor/FileOps 統合。
- **非目標:** LLM 自動抽出の高精度化（Phase 2 以降）、複数プランの高度な差分マー
ジ。

**設計原則**
- **単一真実源:** プラン状態は `PlanTool` のみが正とする（他は参照/表示用）。
- **明示性:** プランの保存・承認・実行はすべてAPI経由でログ・可監査。
- **承認必須:** 実行は承認済み ActionSpec のみに限定。
- **安全性:** リスク評価・プレフライト・差分プレビューを標準化。

**ドメインモデル**
- `Plan`:
  - **id:** 文字列（UUID）
  - **title:** 短い説明
  - **content:** プラン本文（LLM出力のロードマップ等）
  - **sources:** `[{message_id, timestamp}]`
  - **rationale:** 目的/前提
  - **tags:** 任意の分類
  - **created_at/version:** 監査用
- `PlanState`:
  - **status:** `proposed|pending_review|approved|scheduled|executing|completed|
aborted`
  - **action_specs:** `ActionSpecExt[]`
  - **selection:** 実行対象（全件/部分）
  - **approvals:** `[{approver, timestamp, selection}]`
  - **previews:** diff 集計/リスクスコア/対象ファイル一覧
- `ActionSpecExt`:
  - **base:** 既存 `ActionSpec {kind, path, content, description, optional}`
  - **id/risk:** `low|medium|high`
  - **validated:** bool（バリデーション通過）
  - **preflight:** `{exists, overwrite, diff_summary}`
  - **notes:** 任意

**API 仕様（最小核/Phase 1）**
- `plan.propose(content: str, sources: list[MessageRef], rationale: str, tags: l
ist[str]) -> PlanId`
- `plan.set_action_specs(plan_id: str, specs: list[ActionSpec]) -> ValidationRep
ort`
- `plan.preview(plan_id: str) -> PlanPreview`
- `plan.request_approval(plan_id: str, selection: SpecSelection) -> ApprovalRequ
estId`
- `plan.approve(plan_id: str, approver: str, selection: SpecSelection) -> Approv
edPlan`
- `plan.execute(plan_id: str) -> ExecutionResult`
- `plan.get_state(plan_id: str) -> PlanState`
- `plan.get_current() -> Optional[PlanRef]`
- `plan.list() -> list[PlanRef]`
- `plan.mark_pending(plan_id: str, pending: bool) -> PlanState`
- `plan.clear_current() -> None`

補助型
- `MessageRef: {message_id: str, timestamp: str}`
- `SpecSelection: {"all": bool, "ids": list[str]}`
- `ValidationReport: {ok: bool, issues: list[str], normalized: list[ActionSpecEx
t]}`
- `PlanPreview: {files: list[str], diffs: list[DiffSummary], risk_score: float}`
- `ExecutionResult: {overall_success: bool, results: list[FileOpOutcome], starte
d_at, finished_at}`

**状態遷移（ライフサイクル）**
- `proposed`（提案）→ `pending_review`（ActionSpec 設定/検証）→ `approved`（承認
）→ `scheduled`（実行待ち）→ `executing` → `completed|aborted`
- 例外分岐: バリデーション失敗→`pending_review`維持、ユーザー差し戻し→`proposed`
 へ。

**バリデーション/プレフライト**
- **パス正規化:** `pathlib` による相対/外部参照阻止（`..`/シンボリックリンク対策
）。
- **危険種別:** `delete` や `overwrite large` は `risk=high` 付与。
- **サイズ/拡張子:** 大容量/禁止拡張子は弾くまたは `high`。
- **差分:** 既存ファイルは短い diff 概要を `preflight.diff_summary` に付与。

**承認・安全**
- **承認単位:** プラン全件/部分選択に対応（SpecSelection）。
- **UI:** `rich_ui` でプレビュー（ファイル一覧/差分集計/リスク一覧）。
- **ポリシー:** `risk=high` は必ず手動承認、`low/medium` は設定によりまとめ承認
可。
- **記録:** `logs/plans/<id>/approval.json` に承認履歴を保存。

**UI/UX（操作フロー）**
- **プラン提示:** AIがプラン本文を提示後に `plan.propose()` をコール。
- **明細化:** AIが `plan.set_action_specs()` で ActionSpec を設定（まずは手動/LL
M補助）。
- **プレビュー/承認:** `plan.preview()` → `plan.request_approval()` → ユーザー承
認 → `plan.approve()`
- **実装開始:** ユーザー「実装を進めてください」→ 承認済みプランがあれば `plan.e
xecute()` を呼ぶ。無ければガイダンス提示。

**永続化**
- **格納:** `logs/plans/<plan_id>/plan.json`（Plan/PlanState/ActionSpec/承認/結
果リンク）
- **インデックス:** `logs/plans/index.json`（最近/履歴）
- **差分:** 任意で `logs/plans/<plan_id>/preview/*.diff` 保存

**統合ポイント**
- `EnhancedCore`:
  - プラン生成後に必ず `plan.propose()`。
  - 明細化は `plan.set_action_specs()`（AIがActionSpecを構築）。
- `EnhancedDualLoop`:
  - 実行ルート判定は `PlanTool.get_current()/get_state()` のみ参照。
  - `force_execution`/選択入力は PlanTool 未承認なら無効。
- `PlanExecutor/FileOps`:
  - すべて `plan.execute()` 経由で呼び出し、`apply_with_approval_*` を内部利用。

**ログ/テレメトリ**
- **イベント:** `plan_proposed/specs_set/approval_requested/approved/executed/co
mpleted/aborted`
- **属性:** `actor(ai|user|system)`, `reason`, `counts(files/specs)`, `risk_scor
e`
- **出力:** 構造化ログ（JSON）＋コンソール（人可読）

**エラーハンドリング/リカバリ**
- **検証失敗:** `ValidationReport.issues` を提示、編集を促す。
- **競合:** 実行直前に `preflight` 再評価。差分が変われば再承認要求。
- **中断:** 実行途中エラーは `aborted`、成功分/失敗分を分離記録。残件のみ再実行
可能。

**マイグレーション（現行からの移行）**
- **置換:** `PlanContext` 直操作/最小実装フォールバックを廃止し、PlanTool経由に
置換。
- **同期削除:** 暗黙のプラン検出・pending 同期は削除（明示APIのみ）。
- **ガード:** 「実装を進めてください」で承認チェックし、無ければ作成/承認を促す
。

**テスト計画**
  - propose/set_action_specs/preview/approve/execute 正常・異常系
  - パス正規化/禁止拡張子/大容量/上書き警告
- 統合:
  - プラン提示→承認→実装開始→実行、承認無し→実行不可
  - 競合検出→再承認要求
- 回帰:
  - 暗黙フォールバック（`minimal_implementation.txt`）が発生しない

**今後の拡張（Phase 2 以降）**
- **ActionSpec 抽出支援:** プラン本文→ActionSpec の半自動生成（軽量パーサ/LLM補
助）。
- **バージョニング:** fork/revert/差分比較の強化。
- **CI 連携:** 実行前後に `format/test/build` の dry-run/実行。

**型定義例（参考・擬似）**
- `ActionSpec` は既存を流用:
  - `{"kind": "create|write|mkdir|read|analyze|run", "path": str, "content": str
|None, "description": str, "optional": bool}`
- `ActionSpecExt`:
  - `{"id": str, "risk": "low|medium|high", "validated": bool, "preflight": {"ex
ists": bool, "overwrite": bool, "diff_summary": str}, "base": ActionSpec}`