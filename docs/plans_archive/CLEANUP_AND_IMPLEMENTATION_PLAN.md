# Duckflow クリーンアップ & 実装プラン

## 🗑️ 削除対象（大胆なクリーンアップ）

### 削除するディレクトリ
```
codecrafter/orchestration/     # 複雑なオーケストレーター群
codecrafter/pacemaker/         # Duck Pacemaker関連
codecrafter/promptsmith/       # PromptSmith自己改善
codecrafter/rag/              # 複雑なRAG実装
codecrafter/schemas/          # 複雑なスキーマ定義
codecrafter/security/         # 過度なセキュリティ機能
codecrafter/templates/        # TaskProfileテンプレート
codecrafter/memory/           # 複雑な記憶システム
codecrafter/keeper/           # Duck FS等
```

### 削除するファイル
```
codecrafter/main_v2.py        # 複雑なメイン実装
codecrafter/services/task_classifier.py  # TaskProfile分類
codecrafter/services/llm_service.py      # 複雑なLLMサービス
```

### 保持するもの（活用）
```
codecrafter/base/             # 基本設定とLLMクライアント
codecrafter/tools/            # 基本ツール（簡素化して活用）
codecrafter/ui/               # Rich UI（活用）
codecrafter/state/            # 状態管理（簡素化して活用）
```

## 🏗️ 新しい構造

```
duckflow/
├── companion/
│   ├── __init__.py
│   ├── core.py              # CompanionCore（司令塔AI）
│   ├── actions.py           # ActionSubsystem
│   ├── memory.py            # MemoryStream（シンプル）
│   └── personality.py       # NaturalPersonality
├── tools/
│   ├── __init__.py
│   ├── file_ops.py          # 基本ファイル操作（既存から簡素化）
│   └── code_runner.py       # コード実行
├── ui/
│   ├── __init__.py
│   └── terminal.py          # Rich-based UI（既存活用）
├── config/
│   ├── __init__.py
│   └── settings.py          # 設定管理（既存活用）
├── main.py                  # 新しいシンプルなエントリーポイント
└── learnings.md             # プロジェクト学習ノート
```

## 🚀 実装ステップ

### Step 1: クリーンアップ実行
1. 不要ディレクトリの削除
2. 不要ファイルの削除
3. 新しいディレクトリ構造の作成

### Step 2: 基盤実装
1. `companion/core.py` - 司令塔AI
2. `tools/file_ops.py` - 基本ファイル操作
3. `main.py` - シンプルなエントリーポイント

### Step 3: UI統合
1. 既存のrich_uiを活用
2. 疑似思考過程表示の実装

### Step 4: 基本機能テスト
1. 簡単な対話テスト
2. ファイル操作テスト
3. 基本的な相棒らしさテスト