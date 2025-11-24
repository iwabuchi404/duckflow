# [提案] 動的な承認プロセスの導入

**ID:** `PROPOSAL-003`  
**ステータス:** `提案`  
**作成日:** `2025-08-17`

---

## 1. 概要

ユーザーの操作負担を軽減し、エージェントの自律性を向上させるため、計画のリスクレベルを動的に評価し、低リスクな操作については**ユーザーの承認を自動化（スキップ）**する仕組みを導入することを提案します。

## 2. 関連フロー

- `flow.file_operation.v1.yaml`

## 3. 現状の課題

現在のフローでは、安全性を重視するあまり、すべてのファイル変更操作でユーザーの承認が必要となっています。

これは、例えば「コメントの追加」「不要なimport文の削除」といった、明らかにリスクが低く定型的な修正であっても、ユーザーが毎回承認操作をしなければならないことを意味します。この煩雑さが、スムーズな開発体験を阻害する可能性があります。

## 4. 提案内容

ユーザー承認ステップの前に、**リスク評価ステップ**を追加し、承認ポリシーを拡張します。

1.  **リスク評価ステップの追加:**
    - **ステップ名:** `risk_assessor.evaluate_plan`
    - **役割:** 実行計画の内容を分析し、リスクレベルを動的に判定します。
    - **評価基準（例）:**
        - 変更対象のファイル（設定ファイルなど重要なファイルは高リスク）
        - 変更行数（大規模な変更は高リスク）
        - 操作の種類（ファイルの削除は高リスク、追加は低リスク）
2.  **承認ポリシーの拡張:**
    - `approvals`セクションに、新しいポリシー `auto_approve_on_low_risk` を追加します。
3.  **条件付き承認ステップ:**
    - `approval_ui.request_and_approve` ステップを、リスク評価ステップの結果に基づいて条件付きで実行します。リスクが「低」と判定された場合は、このステップをスキップして自動的に承認されたものと見なします。

## 5. 期待される効果

- **ユーザー負担の軽減:** 明白で安全な変更に対する承認操作が不要になり、開発がスピードアップします。
- **コンテキストスイッチの削減:** 頻繁な承認要求による思考の中断が減り、ユーザーは開発作業に集中できます。
- **エージェントの自律性向上:** エージェントが自らの判断でタスクを進める範囲が広がり、よりパートナーらしい振る舞いになります。

## 6. 擬似的なFlowSpecの変更案

`flow.file_operation.v1.yaml` に以下のような変更を加えます。

```yaml
# ...
approvals:
  low: auto_approve # << NEW POLICY
  medium: policy_default
  high: manual_required

# ...
steps:
  # ...
  - id: s2
    name: plan_tool.set_action_specs
    actor: plan_tool
    outputs: [validation_report, plan_details]

  - id: s3 # << NEW STEP
    name: risk_assessor.evaluate_plan
    actor: risk_assessor_tool
    inputs: [plan_details]
    outputs: [risk_level]
    hint: 計画内容を分析し、リスクレベルをLow/Medium/Highで判定する。

  - id: s4 # 旧s3
    name: approval_ui.request_and_approve
    actor: approval_ui
    outputs: [approved]
    hint: risk_levelがLowでない場合にのみ実行される。

  - id: s5 # 旧s4
    name: plan_tool.execute
    # ... 以下続く
```
