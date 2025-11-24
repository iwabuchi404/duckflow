# 実行阻害の改善プラン（計画は立つが実行に進まない問題への対処）

最終更新: 2025-08-16
対象範囲: companion/intent_understanding/intent_integration.py, companion/enhanced_dual_loop.py, companion/collaborative_planner.py, companion/task_loop.py, companion/file_ops.py, codecrafter/ui/rich_ui.py

---

## 1. 背景
- 現状、エージェントは実行プランの提示までは到達するが、実際のアクション（ファイル作成・更新）に移行せず質問ループに戻る。
- ユーザーの「１で」「OKです実装してください」等の選択・承諾入力が、実行ルートにマッピングされていない。

---

## 2. 観測された挙動（ログ要約）
- プラン提示後に「実行プランの選択」カードへ戻り、固定質問（ファイル名/操作内容）を再表示。
- 選択入力に対して `analysis_request` / `guidance_request` と誤分類し、DirectResponseで完了。
- 一部で LLM 400 Bad Request が発生し、要約/解釈が崩れて安全側に倒れる。

---

## 3. 根本原因の仮説
1) 意図解釈の誤分類: 「1/１/デフォルト/推奨」を選択として扱えず guidance/analysis に分類。
2) プラン→アクションのブリッジ欠如: プランが自由文で、ファイル操作の ActionSpec（path/op/content）が欠落。
3) コンテキスト非考慮のルーティング: 実装合意済み・未実行プランの存在をルーティングが参照しない。
4) アンチスタール不在: 進展のない質問が連続しても停止・方針転換しない。
5) 実行器の未接続/未有効: 安全実行 API（file_ops v2）がDualLoopから呼ばれていない/無効。
6) LLM 400の影響: 失敗時のフォールバックがDirectResponseに偏り、ローカル実行継続ができていない。

---

## 4. 改善方針（優先度順）
1) 選択入力リゾルバ（OptionResolver）の実装
- 「1」「１」「デフォルト」「推奨」「一番上」などを正規化し、現在提示中のプラン選択にマップ。
- 選択検出時は ActionType を `execute_selected_plan` に上書きして Execution へ。

2) プランの ActionSpec 化（構造化）
- Planner 出力を `List[ActionSpec]` に変更（例: `{kind: 'create', path, content}`）。
- 欠落項目はテンプレ（デフォルト）で充足し、再質問を最小化。

3) PlanContext-aware ルーティング
- ルート決定: `route = f(profile, confidence, risk, prerequisites, plan_state)`。
- `plan_state.pending=True` かつ前提充足なら Execution を強制選択（guidanceへ倒れない）。

4) Anti-stall ガード（アンチスタール）
- 進展メトリクス（files_created/updated）が連続0、かつ質問類似度が閾値超え → デフォルト最小実装で前進提案→承認→実行。
- 質問キャッシュで同一/類似質問の再出力を抑止。

5) 実行器の確実な呼び出し
- ActionSpec→`file_ops.apply_with_approval_write` を使用（PREVIEW→承認→検証済RESULT）。
- 既定で `FILE_OPS_V2=1` を有効（設定で切替可能）。

6) LLM 400時のフォールバック
- 1回再試行→失敗時は直前の PlanContext を用いてローカル実行継続（DirectResponseに倒さない）。

---

## 5. 実装詳細（コンポーネント別）
- intent_integration.py
  - OptionResolver: `parse_selection(utterance) -> Optional[Selection]` を追加。
  - 選択検出時は `TaskProfile=execution_request` 相当へ上書き、`execute_selected_plan` を返す。

- collaborative_planner.py
  - `ActionSpec` dataclass を導入: `kind: Literal['create','write','mkdir','run']`, `path: str|None`, `content: str|None`, `optional: bool=False`。
  - Planner出力を `List[ActionSpec]` に変更。欠落はテンプレ充足。

- enhanced_dual_loop.py / task_loop.py
  - PlanContext（pending/planned/attempted/verified）を管理。
  - Anti-stall: 進展検知・質問キャッシュ・方針転換（最小実装）を実装。
  - PlanExecutor: `execute(specs)`→各 ActionSpec を順次 `file_ops.v2` に委譲し、検証ログを記録。

- file_ops.py（済の一部を活用）
  - `FileOpOutcome` / `create_or_write_file_v2` / `apply_with_approval_write` を利用。

- rich_ui.py
  - PREVIEW/RESULT の区別明確化（PREVIEWは実行前、RESULTは検証後）。

---

## 6. 最小実装パッチ案（疑似）
```python
# intent_integration.py
def parse_selection(text: str) -> Optional[int]:
    t = normalize(text)  # 全角半角/空白/句読点除去
    mapping = {"1": 1, "一": 1, "デフォルト": 1, "既定": 1, "推奨": 1, "上": 1}
    return mapping.get(t)

route = base_route(profile, confidence)
sel = parse_selection(user_text)
if sel is not None and plan_ctx.pending:
    route = "execute_selected_plan"

# collaborative_planner.py
@dataclass
class ActionSpec:
    kind: Literal['create','write','mkdir','run']
    path: Optional[str] = None
    content: Optional[str] = None
    optional: bool = False

# enhanced_dual_loop.py
if route == "execute_selected_plan":
    specs = planner.to_action_specs(current_plan, selection=sel)
    result = executor.execute(specs)
    log_progress(result)
    if anti_stall.detect_no_progress():
        specs = planner.minimal_default_specs(current_plan)
        executor.execute(specs)
```

---

## 7. テスト計画
- ユニット
  - OptionResolver: 「1/１/デフォルト/推奨/一番上」を正しく選択解釈。
  - Planner: 欠落項目にテンプレ充足→完全な ActionSpec が出力。
- 統合
  - 「デフォルトで進めますか？→ １で」→ Execution に遷移し、想定ファイルが作成される（存在/ハッシュ検証）。
  - 同型質問が2回続くと Anti-stall が作動し、最小実装で前進。
- E2E
  - 「OKです実装してください」→ PREVIEW→承認→RESULT→実ファイル存在/内容ハッシュ一致まで到達。

---

## 8. メトリクス/ログ
- action_attempted / action_succeeded / files_created_count / files_updated_count
- approvals_requested / approvals_granted / post_condition_verified
- clarification_turns / clarification_progress_delta（Δ情報量）/ anti_stall_triggered

---

## 9. ロードマップ（小PR分割）
1) OptionResolver 追加 + ルーティング上書き（選択→実行）
2) Planner を ActionSpec 化（欠落テンプレ充足）
3) PlanExecutor + Anti-stall（最小）
4) UI PREVIEW/RESULT 明確化 + メトリクス出力
5) LLM 400 フォールバック（ローカル実行継続）

---

## 10. 成果の定義（Doneの条件）
- 「１で」「OK実装」で Execution に遷移し、少なくとも1つの新規/更新ファイルが生成され、ポスト条件検証ログが残る。
- 進展がない Clarification の反復が自動停止され、最小実装で前進する。
- 回帰として guidance 専用シナリオは DirectResponse のまま維持される。

