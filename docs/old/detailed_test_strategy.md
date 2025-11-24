# 詳細設計 – 新テスト戦略と PromptSmith 連携

## 1. 全体概要
| フェーズ | 目的 | 主なアウトプット |
|---|---|---|
| A. 基礎テスト基盤構築 | ツール・ユーティリティの自動テスト基盤を整備 | `tests/unit/`, `tests/integration/` ディレクトリ、CI パイプライン |
| B. 認知性能テスト追加 | プロンプト品質・ハルシネーション・コンテキスト保持の検証 | `tests/e2e/`, メトリクス収集スクリプト |
| C. PromptSmith 連携 | テスト結果を PromptSmith にフィードしプロンプト自動改善 | 改善サイクル実装、CI で自動実行 |
| D. ダッシュボード & レポート | テスト・改善結果を可視化 | 評価ダッシュボード、レポート自動生成 |

## 2. ステップ別実装タスク

### 2.1 基礎テスト基盤構築 (2 週間)
1. **テストフレームワーク選定**  
   - `pytest` + `pytest-cov` を採用。  
2. **ユニットテスト作成** (`tests/unit/`)  
   - `codecrafter/tools/file_tools.py` → `test_file_tools.py`  
   - `codecrafter/tools/shell_tools.py` → `test_shell_tools.py`  
   - `codecrafter/base/llm_client.py` → `test_llm_client.py`  
3. **統合テスト作成** (`tests/integration/`)  
   - `graph_orchestrator.py` のフロー検証。  
   - `run_duckflow_v2.py` のエンドツーエンド実行テスト。  
4. **CI 設定**  
   - `.github/workflows/ci.yml` にテストジョブ追加。  
   - 失敗時は PR をブロック。

### 2.2 認知性能テスト追加 (3 週間)
1. **評価指標定義**  
   - **ハルシネーション率**: 不正確な回答の割合  
   - **コンテキスト保持率**: 複数ターンでの意図保持率  
   - **プロンプト最適化指数**: PromptSmith が提案した改善の効果量  
2. **E2E テスト作成** (`tests/e2e/`)  
   - `tests/e2e/hallucination_test.py`  
   - `tests/e2e/context_retention_test.py`  
   - `tests/e2e/prompt_quality_test.py`  
3. **メトリクス収集スクリプト** (`scripts/metrics.py`)  
   - テスト実行後に JSON 出力。  
   - `pytest --json-report` と組み合わせて自動集計。  
4. **結果レポート生成** (`scripts/report.py`)  
   - HTML/Markdown レポート生成。  
   - GitHub Pages にデプロイ。

### 2.3 PromptSmith 連携 (4 週間)
1. **改善サイクル実装** (`promptsmith/orchestrator.py`)  
   - `run_improvement_cycle()` がテスト結果 JSON を読み込み、改善提案を生成。  
2. **CI での自動フィード**  
   - `ci.yml` のテストステップ後に `python -m promptsmith.orchestrator` を呼び出す。  
   - 改善提案は `promptsmith/updates/` に出力。  
3. **改善プロンプト自動適用** (`promptsmith/prompt_compiler.py`)  
   - `apply_improved_prompt()` が自動で `PromptContext` に反映。  
4. **フィードバックループ**  
   - 次回テスト実行時に新プロンプトで再評価し、メトリクスで効果測定。

### 2.4 ダッシュボード & レポート (2 週間)
1. **評価ダッシュボード** (`dashboard/`)  
   - `streamlit` または `dash` で以下タブを作成  
     - **テスト概要**（カバレッジ、成功率）  
     - **認知性能**（ハルシネーション、コンテキスト保持）  
     - **改善サイクル**（提案数、効果率）  
2. **自動レポート**  
   - `ci.yml` の最後に `python scripts/report.py` を実行し、GitHub Pages に自動デプロイ。

## 3. マイルストーン & スケジュール
| 週 | マイルストーン | 完了条件 |
|---|---|---|
| 1‑2 | 基礎テスト基盤完成 | 全ユニット・統合テストが CI で成功 |
| 3‑5 | 認知性能テスト実装 | ハルシネーション・コンテキストテストが 80% 以上のカバレッジ |
| 6‑9 | PromptSmith 連携実装 | 改善サイクルが CI で自動実行、改善提案が生成 |
| 10‑11 | ダッシュボード構築 | ダッシュボードがローカル・GitHub Pages で閲覧可能 |
| 12 | 完全統合テスト | すべてのテストが CI で 100% パス、レポート自動生成 |

## 4. 役割分担（例）
| ロール | 担当範囲 |
|-------|----------|
| Architect (Roo) | 全体設計、タスク分割、進捗管理 |
| Developer | テストコード実装、CI 設定、メトリクス収集 |
| Prompt Engineer | PromptSmith 改善ロジック実装、プロンプト最適化 |
| DevOps | CI/CD パイプライン構築、ダッシュボードデプロイ |
| QA | テストシナリオレビュー、メトリクス検証 |

## 5. 成功指標 (KPIs)
| KPI | 目標値 |
|-----|------|
| テストカバレッジ | 80% 以上（ユニット） |
| ハルシネーション率 | 5% 以下 |
| コンテキスト保持率 | 90% 以上 |
| 改善提案採用率 | 70% 以上 |
| CI 成功率 | 100%（マージ時） |

## 6. リスクと対策
| リスク | 対策 |
|------|------|
| テスト作成工数 | テンプレート化、共通ユーティリティで再利用 |
| PromptSmith の改善速度 | 2 週間ごとにレビュー、必要なら手動調整 |
| CI の遅延 | 並列実行、キャッシュ利用で最適化 |
| メトリクスの信頼性 | 複数回実行し統計的に安定した指標を採用 |

## 7. 次のアクション
1. `docs/` に `detailed_test_strategy.md` を作成し、上記内容を保存。  
2. `tests/` ディレクトリ構造を作成 (`mkdir -p tests/unit tests/integration tests/e2e`)。  
3. `pytest` と `pytest-cov` をインストール (`pip install pytest pytest-cov`)。  
4. CI 設定テンプレート (`.github/workflows/ci.yml`) を作成。  

---

このドキュメントは `docs/detailed_test_strategy.md` に保存され、開発チームが参照できるようになります。