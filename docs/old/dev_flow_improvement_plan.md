# 開発フロー改善プラン（Duckflow）

## 背景と課題
- チャット入力→意図評価→応答→ファイル操作の流れが複線化し、暗黙の分岐や暫定対応が混在。
- 機能追加がアドホックに行われ、フローの単一真実源が不在のため不整合が多発。
- レビュー観点が分散し、仕様・実装・テスト・運用ログの整合が取りにくい。

## 目的
- フローの単一真実源を作り、設計→実装→テスト→運用まで一貫性を確保。
- レビュー負荷を下げつつ、失敗時の扱いと安全性（承認/ロールバック）を明確化。
- 変更時は必ずフロー文書も更新する“ドキュメント駆動の開発”を徹底。

## 基本方針
- 単一真実源（Single Source of Truth）: `flowspec/*.yaml` を正とする。
- 人間用ドキュメントは自動生成: `docs/flows/*.md` は FlowSpec から機械生成。
- CI ゲート: FlowSpec 差分がある PR は生成物の更新・契約テスト（Contract Tests）を必須化。
- 実装の境界: router / plan_tool / approval / executor に限定し、責務を明確化。

## 対象フロー（最小セット）
1. Chat→DirectResponse（ガイダンス系）
2. Chat→Clarification（不確実時の聞き返し）
3. Chat→Plan→Approval→Execute（作成/修正要求の標準）
4. Error Recovery（任意ステップの失敗経路）

将来: Import/Export、長時間実行ジョブ、バックグラウンド解析などは別 FlowSpec に分割。

## 開発プロセス（必須手順）
1. Issue 作成
   - 目的/背景、対象 flow_id、影響範囲、ユーザー影響、リスク。
2. FlowSpec 更新（必須）
   - `flowspec/<flow_id>.yaml` を編集（routing/steps/approvals/error）。
   - 変更点は最小に保ち、サブフローは別ファイルへ分割。
3. 設計レビュー
   - FlowSpec の PR をレビュー。分岐・承認・エラー処理・可観測性を確認。
4. 実装
   - FlowSpec と step_id に沿って、router/plan_tool/approval/executor のどこに手を入れるかを明記。
   - 構造化ログに `flow_id/step_id/plan_id` を必ず出力。
5. テスト
   - Contract Tests（pytest）: 代表入力→期待イベント列（flow_id/step_id）一致を検証。
   - E2E: 「未承認実行不可」「preflight 変化で再承認」「approved のみ実行」。
6. ドキュメント生成/同期
   - `python scripts/compile_flows.py` 実行 → `docs/flows/*.md` を再生成しコミット。

## PR テンプレート（例）
```
Title: flow.chat_plan_execute.v1 ルーティング修正（clarification 閾値）

このPRが触る Flow: flow.chat_plan_execute.v1
変更点（Before→After）:
- routing: confidence >= 0.8 → 0.7
- steps: s4 の validation_report に size_limit を追加
- error_handling: preflight_changed → s4 にリダイレクトを明記

ガードレール（変更なし）:
- 未承認は実行不可 / preflight 変化は再承認 / run 系は手動承認必須

影響コード: router / plan_tool（_validate_specs）
テスト: contract 2件更新、e2e 1件追加
生成物: docs/flows/flow.chat_plan_execute.v1.md 再生成済み
```

## ログ/可観測性（Observability）
- 構造化ログの必須キー: `flow_id`, `step_id`, `plan_id`, `correlation_id`。
- 主要イベント: `plan_proposed/specs_set/approval_requested/approved/executed/completed/aborted`。
- 成果物: `logs/plans/<plan_id>/plan.json`、`index.json`。

## ロードマップ（導入段階）
- Phase 1: FlowSpec スキーマ最小版 + 生成スクリプト + Contract Tests（代表1本）。
- Phase 2: 全主要フローの FlowSpec 化、PR テンプレ/CI ゲート適用、図の自動生成。
- Phase 3: フロー依存関係/バージョニング、ダッシュボード連携、メトリクス可視化。

## 付録: 用語集（抜粋）
- FlowSpec: 機械可読のフロー仕様（単一真実源）。
- FlowCard: FlowSpec から生成される、人間用の1〜2ページ要約MD。
- Contract Test: 期待イベント列（flow_id/step_id）を照合するテスト。

