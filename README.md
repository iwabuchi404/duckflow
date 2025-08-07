# CodeCrafter

AI-powered coding agent for local development environments

## 概要

CodeCrafterは、ローカル開発環境で動作し、ユーザーとの対話を通じてコードの生成、編集、リファクタリング、プロジェクト全体の管理を自律的に支援するAIコーディングエージェントです。

現在は**ステップ1（最小限実装）**の段階で、基本的なファイル操作とユーザーインターフェースを提供しています。

## 機能

### ステップ1（現在の実装）
- 基本的なファイル操作（読み取り、書き込み、一覧表示）
- ディレクトリ作成
- Rich UIによる美しいターミナル表示
- 設定ファイルによる柔軟な設定管理
- セキュリティ機能（操作の承認確認）
- 対話履歴の管理

### 将来の実装予定
- **ステップ2**: RAGによるプロジェクト横断検索、複数ツール連携、LangGraphによるオーケストレーション
- **ステップ3**: LSP/Tree-sitterによる高度なコード解析、テスト自動実行、CI/CD統合

## 要件

- Python 3.10以上
- UV（Pythonパッケージマネージャー）

## インストール

1. リポジトリをクローン:
```bash
git clone <repository-url>
cd codecrafter
```

2. UVで依存関係をインストール:
```bash
uv sync
```

3. 設定ファイルを作成:
```bash
cp .env.template .env
```

4. `.env`ファイルに必要なAPIキーを設定

## 使用方法

### 基本実行

```bash
# UVを使用して実行
uv run python main.py

# または、仮想環境をアクティベートして実行
uv shell
python main.py
```

### 利用可能なコマンド

**基本操作:**
- `help`, `h` - ヘルプを表示
- `quit`, `exit`, `q` - 終了
- `status` - エージェントの状態を表示
- `config` - 設定情報を表示
- `history [count]` - 対話履歴を表示

**ファイル操作:**
- `ls`, `list [path]` - ファイル一覧を表示
- `read <file>` - ファイルを読み取り表示
- `write <file>` - ファイルに書き込み
- `info <file>` - ファイル情報を表示
- `mkdir <dir>` - ディレクトリを作成

## 設定

### config.yaml

メインの設定ファイルです。LLMプロバイダー、UI設定、セキュリティ設定などを管理します。

### .env

APIキーなどの秘密情報を管理します。

## 開発

### 開発環境のセットアップ

```bash
# 開発用依存関係を含めてインストール
uv sync --extra dev

# コード品質チェック
uv run ruff check .
uv run black --check .
uv run mypy .

# テスト実行
uv run pytest
```

### プロジェクト構造

```
codecrafter/
├── codecrafter/          # メインパッケージ
│   ├── base/             # 基盤機能（設定管理など）
│   ├── state/            # 状態管理
│   ├── tools/            # ツール（ファイル操作など）
│   ├── ui/               # ユーザーインターフェース
│   ├── prompts/          # プロンプト管理（将来実装）
│   └── security/         # セキュリティ機能（将来実装）
├── config/               # 設定ファイル
├── tests/                # テスト
└── logs/                 # ログファイル
```

## ライセンス

MIT License

## 貢献

プルリクエストやイシューを歓迎します。

## ロードマップ

- [x] **ステップ1**: 基本的なファイル操作とUI
- [ ] **ステップ2**: RAGとLangGraphの統合
- [ ] **ステップ3**: 高度なコード解析と評価システム