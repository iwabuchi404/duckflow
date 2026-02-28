# Duckflow

**バージョン**: v0.1.0 (Phase 1.5+)  
**ステータス**: Phase 1.5（基本ファイル操作）完了 100%

Duckflowは、開発者のローカル環境で動作する対話型AIコーディングエージェントです。AIとの対話を通じて、ファイルの作成・編集・実行を支援します。

## 🎯 プロジェクトの目的

- **効率的な文脈管理**: LLMを呼び出すたびに、関連性の高い情報を最小限の形で賢く組み立てる
- **柔軟な実行制御**: グラフベースの制御フローを排し、シンプルかつ明示的なThink-Decide-Executeループで制御する
- **開発者中心の体験**: ターミナル上で、キーボード中心のシームレスな操作感を提供する
- **精神的支柱 (Companion)**: 単なるツールではなく、開発を共演するパートナーとしての振る舞い

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

プロジェクトルートの `duckflow.yaml` でLLMプロバイダーを設定します。環境変数 `DUCKFLOW_*` によるオーバーライドも可能です。

```yaml
llm:
  provider: openrouter
  available_models:
    - name: GPT-4o (OpenAI)
      provider: openai
      model: gpt-4o
    # ...
```

2. **APIキーの設定**

`.env` ファイルを作成してAPIキーを設定します。

```bash
OPENAI_API_KEY=your_api_key_here
ANTHROPIC_API_KEY=your_api_key_here
GOOGLE_AI_API_KEY=your_api_key_here
GROQ_API_KEY=your_api_key_here
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
- `history [count]` - 対話履歴を表示
- `test`, `tests` - テストを実行

**AI対話とアクション:**
- 上記以外の入力はAIへの指示として処理されます。
- エージェントは「思考（Think）」し、一連の「行動（Action）」を決定し、実行します。

### 使用例

```bash
Duckflow> ls
Duckflow> hello.pyファイルを作成して、Hello Worldを出力する関数を書いて。作成したら実行して。
```

## 🏗️ アーキテクチャ (Duckflow v4)

現在の Duckflow は、予測可能性と透明性を重視したアーキテクチャを採用しています。

- **Think-Decide-Execute ループ**: 
  1. **Think**: 現在の状態 (`AgentState`) をコンテキストとして LLM に入力。
  2. **Decide**: LLM が「次に実行すべき行動リスト (`ActionList`)」を JSON で出力。
  3. **Execute**: システムがリストを順次実行し、結果を状態に反映。
- **Hierarchical Planning**: タスクを Plan -> Step -> Task の階層で管理し、着実な進捗を実現。
- **UI**: `Rich` による美しく読みやすいターミナル出力。
- **Pacemaker**: エージェントの健康状態（スタミナ、集中力）やループ回数を監視し、暴走を防止。

## 🗂️ プロジェクト構造

```
duckflow/
├── companion/                # v4 メインパッケージ（旧 codecrafter から移行）
│   ├── core.py               # メインエージェントロジック
│   ├── base/                 # LLMクライアント抽象化
│   ├── state/                # AgentState (Single Source of Truth)
│   ├── tools/                # ツール群 (File, Plan, Task, etc.)
│   ├── orchestration/        # 実行制御
│   ├── modules/              # 記憶管理, Pacemaker
│   └── ui/                   # Rich UI実装
├── codecrafter/              # 以前のコードベース（参考用）
├── config/                   # 設定テンプレート（レガシー）
├── duckflow.yaml             # メイン設定ファイル
├── .env                      # APIキー（git exclude）
├── main.py                   # エントリーポイント
└── PROGRESS.md               # 開発進捗記録
```

## 🚧 開発ロードマップ

詳細は [NEXT_STEPS_ROADMAP.md](NEXT_STEPS_ROADMAP.md) を参照してください。

- **Phase 1: Basic AI Companion** (完了)
- **Phase 1.5: File Operations** (完了)
- **Phase 1.6: Code Execution** (実装中/一部完了)
- **Phase 2: Long-term Memory** (計画中)

## ⚙️ 設定

### llm (duckflow.yaml)

```yaml
llm:
  provider: "openrouter"
  google:
    model: "gemini-1.5-pro-002"
  openai:
    model: "gpt-4o"
  temperature: 0.7
```

### agent (duckflow.yaml)

```yaml
agent:
  max_loops: 10
  language: japanese
  auto_approval:
    - read_file
    - list_files
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

### プロンプトインスペクター

LLM に実際に送られるプロンプトを確認するデバッグツールです。ツール登録漏れやプロンプト設計の問題を素早くキャッチできます。

```bash
# task モードのプロンプトを標準出力に表示
uv run python -X utf8 dump_prompt.py task

# 全モード（planning / investigation / task）を表示
uv run python -X utf8 dump_prompt.py all

# ファイルに出力
uv run python -X utf8 dump_prompt.py all --output prompt_dump.txt

# JSON形式（プログラム処理用）
uv run python -X utf8 dump_prompt.py task --raw
```

出力はメッセージブロック単位で構造化されます。

```text
[1] SYSTEM  (2771 chars)   ← Sym-Ops プロトコル共通定義
[2] SYSTEM  (3xxx chars)   ← ツール説明 + モード固有指示
[3..N] USER/ASSISTANT      ← Few-shot 例
[N+1] SYSTEM               ← 動的コンテキスト（AgentState）
```

特定ツールの存在確認:

```bash
uv run python -X utf8 dump_prompt.py task | grep delete_lines
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
