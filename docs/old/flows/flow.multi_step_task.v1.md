# Flow: 複数ステップタスク（計画→選択→分岐） (`flow.multi_step_task.v1`)

| 属性 | 値 |
|---|---|
| バージョン | 1 |
| ステータス | approved |
| オーナー | team/companion |
| 目的 | 抽象度の高い要求に対して計画提示→選択→分岐で安全に進める |
| 概要 | A: 実行（下位フローへ委譲）/ B: 明確化 / C: 代替案 提示の三択で進行 |

---

## メインパス（代表）
1. create_task_plan（core）: TaskPlan を生成（micro/light）
2. present_plan_and_options（core）: A/B/C を提示
3a. execute_selected（core）: file_operation / code_execution へ委譲
3b. request_clarification（core）: 具体化の質問を返す
3c. suggest_alternatives（core）: 代替案を提示

---

## 分岐とガードレール
- ルーティング: action_type==multi_step_task → plan_and_decide
- 承認: 実行は下位フローに委譲（本フローでは承認しない）
- エラー: plan 生成失敗→micro_plan へフォールバック、選択が不正→再入力を促す

---

## 可観測性
- Events: plan_created, options_presented, choice_received, delegated, completed
- Log Keys: flow_id, step_id, correlation_id
- Artifacts: logs/sessions/<correlation_id>/multi_step.json

