# [提案] 自己修正ループの導入

**ID:** `PROPOSAL-002`  
**ステータス:** `提案`  
**作成日:** `2025-08-17`

---

## 1. 概要

コーディングタスクの完遂率を向上させるため、計画の実行が失敗した際に、その結果を自ら評価・分析し、計画を修正して再試行する**自己修正ループ**の仕組みを導入することを提案します。

## 2. 関連フロー

- `flow.file_operation.v1.yaml`
- `flow.code_execution.v1.yaml`

## 3. 現状の課題

現在のフローでは、`plan_tool.execute` ステップが失敗した場合（例: コンパイルエラー、テスト失敗）、フローは終了するか、ユーザーに判断を仰ぐだけで停止してしまいます。

これでは、エージェントは一度の失敗で諦めてしまい、自律的な問題解決ができません。開発で一般的な「試行錯誤」のプロセスを実行できないため、単純なタスクしか完遂できません。

## 4. 提案内容

計画実行ステップの後に、**評価**と**診断**のステップを追加し、失敗時に計画立案ステップへ戻るループ構造を定義します。

1.  **結果評価ステップの追加:**
    - **ステップ名:** `evaluator.assess_result`
    - **役割:** `execute`ステップの出力（標準出力、エラー、終了コード）を評価し、「成功」か「失敗」かを判定します。
2.  **失敗診断ステップの追加:**
    - **ステップ名:** `analyzer.diagnose_failure`
    - **役割:** 失敗と判定された場合、エラーログなどを分析し、失敗原因（例: `SyntaxError`, `DependencyError`）を特定します。
3.  **ループ構造の定義:**
    - 失敗原因の診断結果を、次の計画立案ステップ (`plan_tool.propose`) の入力として渡します。
    - `plan_tool`は、前回の失敗原因を考慮して、修正された新しい計画を立案します。

## 5. 期待される効果

- **タスク完遂率の向上:** 一度の失敗で諦めず、エージェントが自律的に問題解決を試みるため、より複雑なタスクも完遂できるようになります。
- **問題解決能力の向上:** エラー分析と計画修正のサイクルを通じて、エージェントがより高度な問題解決能力を獲得します。
- **ユーザー体験の向上:** ユーザーが介入せずとも、エージェントが粘り強くタスクに取り組むため、信頼性が向上します。

## 6. 擬似的なFlowSpecの変更案

`flow.file_operation.v1.yaml` に以下のような変更を加えます。

```yaml
# ... (approvalsなど)

error_handling:
  - when: execution_failed # << NEW: 実行失敗時の専用ハンドリング
    action: analyze_and_replan
    redirect: s5 # 評価ステップへ
  # ...

steps:
  # ...
  - id: s4
    name: plan_tool.execute
    actor: executor
    outputs: [result, exit_code, logs]

  - id: s5 # << NEW STEP
    name: evaluator.assess_result
    actor: evaluator_tool
    inputs: [result, exit_code, logs]
    outputs: [is_success, failure_context]
    hint: 実行結果を評価。成功なら完了、失敗ならs6へリダイレクト。

  - id: s6 # << NEW STEP
    name: analyzer.diagnose_failure
    actor: analyzer_tool
    inputs: [failure_context]
    outputs: [diagnosis_report]
    hint: 失敗原因を分析し、次の計画のための診断レポートを作成。このレポートを持ってs1(plan_tool.propose)へ戻る。
```
