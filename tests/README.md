# Duckflow テスト構成

## ディレクトリ構造

```
tests/
├── __init__.py                 # メインテストパッケージ
├── conftest.py                 # pytest設定・共通フィクスチャ
├── README.md                   # このファイル
├── 
├── # 単体テスト (Unit Tests)
├── test_agent_state.py         # AgentState モデル
├── test_config.py              # 設定管理
├── test_file_tools.py          # ファイル操作ツール
├── test_main_integration.py    # メイン統合テスト
├── test_run_tests.py           # テスト実行機能
│
├── step_tests/                 # ステップ別開発テスト
│   ├── __init__.py
│   ├── test_step2c_memory.py   # ステップ2c: 記憶管理
│   ├── test_step2d_graph.py    # ステップ2d: グラフ構造
│   └── test_graph_structure.py # グラフ構造単体テスト
│
├── integration/                # 統合テスト
│   ├── __init__.py
│   ├── test_error_handling.py          # エラーハンドリング統合
│   ├── test_error_handling_simple.py   # エラーハンドリング簡易版
│   └── test_shell_tools.py             # シェルツール統合
│
├── experimental/               # 実験的・デバッグテスト
│   ├── __init__.py
│   ├── test_ai_execution.py        # AI実行テスト
│   ├── test_file.py               # ファイル操作実験
│   ├── test_fixed_access.py       # アクセス修正テスト
│   ├── test_windows_shell.py      # Windows環境シェルテスト
│   └── test_workspace_debug.py    # ワークスペースデバッグ
│
└── sandbox/                    # サンドボックス評価システム
    └── __init__.py             # (今後実装予定)
```

## テスト実行方法

### 全テスト実行
```bash
uv run pytest tests/
```

### カテゴリ別実行
```bash
# 単体テスト
uv run pytest tests/test_*.py

# ステップ別テスト  
uv run pytest tests/step_tests/

# 統合テスト
uv run pytest tests/integration/

# 実験的テスト
uv run pytest tests/experimental/
```

### 特定テスト実行
```bash
uv run pytest tests/test_config.py -v
uv run pytest tests/step_tests/test_step2d_graph.py::test_graph_structure -v
```

## テストカテゴリの詳細

### 🧪 単体テスト (Unit Tests)
- 各クラス・関数の個別機能テスト
- モックを使用した依存関係分離
- 高速実行、高カバレッジを目標

### 🏗️ ステップ別テスト (Step Tests) 
- 開発フェーズごとの機能検証
- Step2c: 記憶管理機能
- Step2d: グラフ構造・自律実行機能
- 各ステップの完成度評価

### 🔗 統合テスト (Integration Tests)
- 複数コンポーネント間の連携確認
- エンドツーエンドのワークフロー検証
- エラーハンドリング・回復機能テスト

### 🧪 実験的テスト (Experimental Tests)
- 開発中機能の検証
- デバッグ・トラブルシューティング用
- 一時的な検証コード
- **注意**: 不安定・実験段階の機能

### 🏖️ サンドボックステスト (Sandbox Tests)
- 安全な分離環境でのテスト実行
- 実環境に影響しない評価システム
- **計画中**: 詳細は `docs/SANDBOX_EVALUATION_PLAN.md` 参照

## テスト品質ガイドライン

### ✅ 良いテスト
- 明確な目的・説明
- 独立した実行可能性
- 適切なアサーション
- エラーメッセージの分かりやすさ

### ❌ 避けるべきテスト
- 実環境への副作用
- 外部依存関係（API等）への直接アクセス
- 時間依存・順序依存のテスト
- 不明確な期待値

## 継続的インテグレーション

現在の自動実行対象:
- ✅ 単体テスト: 全PRで実行
- ✅ 統合テスト: メインブランチマージ時
- 🚧 ステップテスト: 手動実行
- 🚧 サンドボックステスト: 計画中

## 貢献ガイド

新しいテストを追加する場合:

1. **適切なカテゴリの選択**
   - 単一機能 → 単体テスト
   - 開発フェーズ検証 → ステップ別テスト  
   - 複合機能 → 統合テスト
   - 実験・デバッグ → 実験的テスト

2. **ファイル命名規則**
   - `test_<機能名>.py`
   - `test_<ステップ名>_<機能>.py`

3. **必須要素**
   - docstring での機能説明
   - 適切なsetup/teardown
   - エラーケースのカバー

詳細は各テストファイルの実装例を参考にしてください。