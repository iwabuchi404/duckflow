# Flow: コード実行（承認付き） (`flow.code_execution.v1`)

| 属性 | 値 |
|---|---|
| バージョン | 1 |
| ステータス | approved |
| オーナー | team/companion |
| 目的 | 実行系の安全制御（承認を必須化、未実装は明確に失敗） |
| 概要 | 実行は高リスクのため承認 UI を挟み、未実装はエラーメッセージで返す |

---

## メインパス（3ステップ）
1. request_execution_approval（approval_ui）: 実行の承認を取得
2. execute_command（core）: 実行（現状は未実装）
3. post_report（system）: 実行結果の記録

---

## 分岐とガードレール
- ルーティング: action_type==code_execution → code_execute
- 承認: 常に手動承認 required（high/medium/low 全て）
- エラー: 未承認→block、未実装→fail_with_message

---

## 可観測性
- Events: execution_requested, approved, executed, completed
- Log Keys: flow_id, step_id, correlation_id, session_id
- Artifacts: logs/executions/<correlation_id>.json

