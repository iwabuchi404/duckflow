# Duckflow

**バージョン**: v0.1.0 (ステップ1)  
**ステータス**: ステップ1（最小限実装）完了 100%

Duckflowは、開発者のローカル環境で動作する対話型AIコーディングエージェントです。AIとの対話を通じて、ファイルの作成・編集を支援します。

## 🎯 プロジェクトの目的

- **効率的な文脈管理**: LLMを呼び出すたびに、関連性の高い情報を最小限の形で賢く組み立てる
- **柔軟な実行制御**: 将来的にグラフベースの制御フローで、複雑なタスクやエラーからの自己修正を可能にする
- **開発者中心の体験**: ターミナル上で、キーボード中心のシームレスな操作感を提供する

## 🚀 クイックスタート

### 必要条件

- Python 3.10以降
- uv (推奨) または pip
- 対応するLLMプロバイダーのAPIキー

### インストール

```bash
# リポジトリをクローン
git clone <repository-url>
cd duckflow

# 依存関係をインストール（uv使用）
uv install

# または pip使用
pip install -e .
```

### 設定

1. **LLMプロバイダーの設定**

`config/config.yaml`でLLMプロバイダーを設定:

```yaml
llm:
  provider: "groq"  # openai, anthropic, google, groq, openrouter
```

2. **APIキーの設定**

`.env`ファイルを作成してAPIキーを設定:

```bash
# OpenAI
OPENAI_API_KEY=your_api_key_here

# Anthropic
ANTHROPIC_API_KEY=your_api_key_here

# Google AI
GOOGLE_AI_API_KEY=your_api_key_here

# Groq
GROQ_API_KEY=your_api_key_here

# OpenRouter
OPENROUTER_API_KEY=your_api_key_here
```

### 起動

```bash
# uv使用
uv run python main.py

# または直接実行
python main.py
```

## 📋 基本的な使い方

### 利用可能なコマンド

**基本操作:**
- `help`, `h` - ヘルプを表示
- `quit`, `exit`, `q` - Duckflowを終了
- `status` - エージェントの状態を表示
- `config` - 設定情報を表示
- `history [count]` - 対話履歴を表示 (デフォルト: 10件)
- `test`, `tests` - テストを実行 (オプション: -v, --verbose, [path])

**ファイル操作:**
- `ls`, `list [path]` - ファイル一覧を表示
- `read <file>` - ファイルを読み取り表示
- `write <file>` - ファイルに書き込み (インタラクティブ)
- `info <file>` - ファイル情報を表示
- `mkdir <dir>` - ディレクトリを作成

**AI対話:**
- 上記以外の入力はAIとの対話として処理されます

### 使用例

```bash
# ファイル一覧を確認
Duckflow> ls

# ファイルを読み込み
Duckflow> read example.py

# AIにファイル作成を依頼
Duckflow> example.pyファイルを作成して、Hello Worldを出力する関数を書いて

# テストを実行
Duckflow> test -v

# 対話履歴を確認
Duckflow> history 5
```

## 🧪 テスト

```bash
# 全テストを実行
uv run pytest tests/ -v

# 特定のテストファイルを実行
uv run pytest tests/test_agent_state.py -v

# カバレッジ付きで実行
uv run pytest tests/ --cov=codecrafter
```

## 🏗️ アーキテクチャ（現在：ステップ1）

現在の実装は最小限のアーキテクチャを採用:

- **メインループ**: シンプルな`while`ループベース
- **UI**: `Rich`ライブラリによるターミナルUI
- **状態管理**: `Pydantic`モデルによるエージェント状態管理
- **ツール**: Pythonファンクションベースのファイル操作ツール群
- **LLM統合**: 直接API呼び出しによる複数プロバイダー対応

### 実装済み機能

✅ **ファイル操作ツール群**
- ファイル読み書き（バックアップ機能付き）
- ディレクトリ操作
- ファイル情報取得

✅ **AI対話システム**  
- 複数LLMプロバイダー対応
- 対話履歴管理
- ファイル操作指示の解析・実行

✅ **セキュリティ機能**
- ファイル書き込み前の承認確認
- セキュリティポリシー設定

✅ **テストスイート**
- 包括的な単体テスト
- 統合テスト
- テスト実行ツール (`test` コマンド)

## 🗂️ プロジェクト構造

```
duckflow/
├── codecrafter/              # メインパッケージ
│   ├── main.py              # メインアプリケーション
│   ├── base/                # 基盤モジュール
│   │   ├── config.py        # 設定管理
│   │   └── llm_client.py    # LLMクライアント抽象化
│   ├── state/               # 状態管理
│   │   └── agent_state.py   # エージェント状態Pydanticモデル
│   ├── tools/               # ツール群
│   │   └── file_tools.py    # ファイル操作ツール
│   ├── ui/                  # ユーザーインターフェース
│   │   └── rich_ui.py       # Rich UI実装
│   ├── prompts/             # プロンプト管理（構造のみ）
│   └── security/            # セキュリティ（構造のみ）
├── tests/                   # テストスイート
├── config/                  # 設定ファイル
│   └── config.yaml
├── main.py                  # エントリーポイント
├── PROGRESS.md              # 開発進捗記録
└── CLAUDE.md               # プロジェクト指示書
```

## 🚧 開発ロードマップ

### ✅ ステップ1: 最小限実装 (100% 完了)
- AIとの対話で単一ファイル編集
- 基本的なファイル操作
- セキュリティ承認機能

### 🔄 ステップ2: MVP（計画中）
- `LangGraph`への移行
- `Textual`ベースの高機能UI
- コード検索(RAG)機能
- 複数ファイル対応

### 🔮 ステップ3: 実用的ツール（将来）
- LSP/Tree-sitter連携
- 高度なコード解析
- 評価システム

## ⚙️ 設定

### LLMプロバイダー設定

`config/config.yaml`:

```yaml
llm:
  provider: "groq"  # 使用するプロバイダー
  
  openai:
    model: "gpt-4-turbo-preview"
    temperature: 0.1
    max_tokens: 4096
  
  anthropic:
    model: "claude-3-5-sonnet-20241022"
    temperature: 0.1
    max_tokens: 4096
  
  groq:
    model: "llama-3.1-8b-instant"
    temperature: 0.1
    max_tokens: 8192
```

### セキュリティ設定

```yaml
security:
  require_approval:
    file_write: true        # ファイル書き込み時の承認
    file_delete: true       # ファイル削除時の承認
    shell_execution: true   # シェル実行時の承認
    directory_creation: true # ディレクトリ作成時の承認
```

### ツール設定

```yaml
tools:
  file_operations:
    max_file_size_mb: 10    # 最大ファイルサイズ
    backup_enabled: true    # バックアップ機能
    allowed_extensions:     # 許可する拡張子
      - ".py"
      - ".js"
      - ".ts"
      - ".yaml"
      - ".md"
```

## 🐛 トラブルシューティング

### よくある問題

**1. pytest が見つからない**
```bash
uv add --dev pytest
```

**2. LLM APIキーエラー**
- `.env`ファイルにAPIキーが正しく設定されているか確認
- 使用するプロバイダーが`config.yaml`で正しく指定されているか確認

**3. ファイル書き込み権限エラー**
- セキュリティ設定で承認が必要になっている可能性があります
- `config/config.yaml`の`security.require_approval.file_write`を確認

### デバッグモード

```bash
# 環境変数でデバッグモードを有効化
export DUCKFLOW_DEBUG=true
uv run python main.py
```

## 🤝 貢献

このプロジェクトへの貢献を歓迎します！

### 開発環境のセットアップ

```bash
# 開発用依存関係をインストール
uv add --dev pytest pytest-cov black ruff mypy

# テストを実行
uv run pytest tests/ -v

# コードフォーマット
uv run black codecrafter/
uv run ruff check codecrafter/
```

### 貢献ガイドライン

1. すべての新機能にはテストを含めてください
2. 既存のテストが通ることを確認してください
3. `black`でコードをフォーマットしてください
4. `ruff`でlintエラーがないことを確認してください

## 📝 ライセンス

[ライセンス情報を記載]

## 📞 サポート

- **Issues**: [GitHub Issues](repository-url/issues)
- **Discussions**: [GitHub Discussions](repository-url/discussions)
- **Documentation**: [プロジェクトドキュメント](CLAUDE.md)

---

**Duckflow** - AI-powered coding agent for local development environments
