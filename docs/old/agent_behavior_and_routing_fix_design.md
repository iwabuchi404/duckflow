# エージェント挙動/ルーティング/プロンプト 改修設計（現実適応版）

最終更新: 2025-08-16
対象範囲: companion/intent_understanding/intent_integration.py, companion/enhanced_dual_loop.py, companion/enhanced_core.py, companion/collaborative_planner.py, codecrafter/ui/rich_ui.py, companion/integration_bridge.py

---

## 1. 背景と課題の要約
- 高抽象度（象徴度）の要求で、実行に入らず「詳細確認テンプレ」でループ。
- creation/modification と判定されても `ActionType: direct_response` や質問で完了扱いになる逸脱。
- 同一内容の再質問（ファイル名/操作内容）を繰り返し、状態引き継ぎが破綻。

根本原因の仮説（再検討）:
- 抽象度ゲートの設計が過剰で、低リスクの自律実行を阻害。
- ルーティング規則が曖昧で、DirectResponse に倒れやすい。
- 状態の二重化（AgentState と Legacy）が競合し、最新意図が失われる。
- 象徴度の高い要求に対して意図理解が不十分で、詳細な実行プランや正しいタスク分割ができていない。
- 要求を詳細化するための質問設計が不適切（固定テンプレ依存）で、文脈差分に基づく段階的深掘りができていない。

---

## 2. 改修目標（受け入れ基準）
- creation/modification 系は必ず Execution 層（file_ops/approval 経由）に到達する（信頼度・リスクに応じたガード付き）。
- Clarification は複数回を許容し、段階的に詳細度を上げる。ただし進展のない質問の反復は検知し停止（アンチスタール）。
- タスク完了条件は「実行結果の検証/確認ログ」まで（DirectResponse完了は guidance のみ）。
- 状態のソース・オブ・トゥルースを AgentState に統一。Legacy は読み取り専用。

---

## 3. 設計方針

### 3.1 ActionType → ルーティング規則（汎用ポリシー）
- ルーティングは「Profile × 信頼度 × リスク × 実行可能性（副作用/依存情報の有無）」で決定する。
- 基本ポリシー（例）:
  - guidance_request → DirectResponse（テキスト応答）。
  - creation_request / modification_request → Execution（approval→実行→検証）。
  - unknown/high-abstract → Safe-Default 提案（低リスク最小操作）→ 承認。
- ガード:
  - 信頼度が閾値未満、または依存情報不足の場合は DirectResponse ではなく Clarification にフェイルバック。
  - 他シナリオへの影響を避けるため、各ルートはフィーチャーフラグ/閾値で調整可能（汎用化）。

実装: `intent_integration.py` に `route = f(profile, confidence, risk, prerequisites)` を実装。抽象度が high でも profile が creation/modification かつ前提が満たせる場合は Execution、満たせない場合は Clarification を選択。

### 3.2 Multi-turn Clarification（段階的詳細化 + アンチスタール）
- 複数回のClarificationを許容し、質問の粒度を段階的に上げる（設計→仕様→ファイル/操作→最終選択）。
- 固定テンプレは禁止。直前ターンとの差分と未充足前提に基づいて質問を生成。
- アンチスタール: 情報増分（Δ情報量）がしきい値未満の質問を連続で検知したら、
  - 方針転換（デフォルト提案 or 安全な最小実行）を提示
  - 明示的に「進展がないため仮決めします」と通知の上で進める
  - 同一質問の再出力を抑止（質問キャッシュ/類似度判定）

### 3.3 完了条件の見直し
- `enhanced_dual_loop.py` の完了判定を「結果イベント（検証済み）」まで延長。
- 応答生成のみ（DirectResponse）で完了できるのは guidance_request のみ。

### 3.4 状態管理の単一化
- AgentState を書き込み可能、Legacy は読み取り専用のミラーに限定。
- 同期方向: AgentState → Legacy（必要時のみ、明示ログ）。逆同期は禁止。

### 3.5 プロンプト・ポリシー更新
- 固定テンプレ「ご要求をより理解するために…」を廃止。
- 文脈差分を抽出し、選択肢とデフォルトの短文で提示。
- 実行可能な最小計画を先に出し、不可欠な1点のみを聞く。

（削除）

---

## 4. 変更点（モジュール別）

- companion/intent_understanding/intent_integration.py
  - `task_profile -> action_route` の決定表実装。
  - 抽象度ハイでも profile が creation/modification なら Execution を強制ルート。

- companion/enhanced_dual_loop.py
  - 完了条件を「検証済み結果イベント」まで延長。質問のみ完了を禁止。
  - One-shot Clarification フローを実装（選択肢+デフォルト、最大1回）。

- companion/enhanced_core.py / collaborative_planner.py
  - プロンプト更新（最小計画提示→1点確認→即実行）。

- codecrafter/ui/rich_ui.py
  - Clarification カードを短文化（選択肢/デフォルト表示）。

---

## 5. 実装手順（小さなPR単位）
1) ルーティング決定表の導入とテスト（unit: 意図→アクション）。
2) DualLoop の完了条件延長 + One-shot Clarification 実装。
3) プロンプト/テンプレの置換（固定テンプレ撤廃）。
4) Clarification アンチスタールの導入（質問キャッシュ/Δ情報量評価）。
5) 回帰修正と結合テスト。

---

## 6. テスト計画
- ユニット: intent→route
  - creation/modification が必ず Execution に流れること。
  - guidance のみが DirectResponse で完了すること。
- 統合: DualLoop
  - Clarification が段階的に詳細化され、一定回数以内に収束すること（進展検知で打ち切り/方針転換）。
  - 質問のみで完了にならないことの確認。
- E2E: design-doc.md ワークフロー
  - 「日本語で書き直して」→ PREVIEW → 承認 → RESULT まで到達。

---

## 7. リスクと対策
- Clarification 短文化により情報不足の恐れ → PREVIEW に必要情報を過不足なく含める。
- Execution 強制により誤操作の可能性 → 低リスク最小操作 + ロールバック標準化で緩和。

---

## 8. 運用・移行
- 旧 Clarification テンプレの段階的廃止（フィーチャーフラグ `ONE_SHOT_CLARIFY=1`）。
- Provider バッジ表示の導入により、利用先の可視化とトラブルシュート容易化。

---

## 9. 付録：状態遷移（簡易）
```
User Input
  → Intent/TaskProfile
    → Route: guidance → DirectResponse(完了)
    → Route: creation/modification → Clarify(複数回, 段階的詳細化, アンチスタール) → Approval → Execute → Verify → Result(完了)
    → Route: unknown/high-abstract → Safe-Default 提案 → Approval → Execute → Verify → Result(完了)
```
