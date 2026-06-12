# モデル切り替え機能ガイド

## 概要

Duckflow v4では、実行中にLLMモデルを動的に切り替えることができます。この機能により、タスクに応じて最適なモデルを選択し、コストとパフォーマンスのバランスを調整できます。

## 使用方法

### 1. 対話的なモデル選択（推奨）

```
/model
```

引数なしで `/model` を実行すると、利用可能なモデルの番号付きリストが表示されます。
数字を入力するだけで簡単にモデルを切り替えられます。

**例：**
```
/model

利用可能なモデル
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#    利用可能なモデル
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1    GPT-4o (OpenAI)
     最新のGPT-4 Optimized。高性能で複雑なタスクに最適

2    Llama 3.3 70B (Groq)
     高速推論。Groqの専用ハードウェアで動作

3    GLM-4.5 Air Free (OpenRouter)
     無料で使える高性能モデル
     ✓ 現在使用中
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

選択してください (1-3, またはキャンセルするには 'c'): 1
```

### 2. 利用可能なモデルの確認

```
/model list
```

設定ファイル（`duckflow.yaml`）に登録されているすべてのモデルと、現在アクティブなモデルを表示します。

### 3. 現在のモデルの確認

```
/model current
```

現在使用中のプロバイダー、モデル名、ベースURLを表示します。

### 4. 直接モデルを指定して切り替え

```
/model <provider>/<model>
```

**例：**
```
/model openai/gpt-4o
/model groq/llama-3.3-70b-versatile
/model openrouter/anthropic/claude-3-5-sonnet-20241022
```

## モデルリストの設定

利用可能なモデルは `duckflow.yaml` の `llm.available_models` セクションで管理されます。

### モデルの追加方法

```yaml
llm:
  available_models:
    - name: "モデルの表示名"
      provider: "プロバイダー名"
      model: "モデルID"
      description: "モデルの説明（オプション）"
```

**例：**
```yaml
llm:
  available_models:
    - name: "GPT-4o (OpenAI)"
      provider: "openai"
      model: "gpt-4o"
      description: "最新のGPT-4 Optimized。高性能で複雑なタスクに最適"
      
    - name: "Claude 3.5 Sonnet (Anthropic via OpenRouter)"
      provider: "openrouter"
      model: "anthropic/claude-3-5-sonnet-20241022"
      description: "最新のClaude。高度な推論能力"
```

### サポートされているプロバイダー

- **openai** - OpenAI models (GPT-4, GPT-4o, etc.)
- **anthropic** - Anthropic Claude models
- **groq** - Groq models (高速推論)
- **openrouter** - OpenRouter models (複数のプロバイダーを統合)
- **google** - Google models (Gemini, etc.)

## 設定の永続化

モデルを切り替えると、以下の設定が `duckflow.yaml` に自動的に保存されます：

- `llm.provider` - 選択されたプロバイダー
- `llm.<provider>.model` - 選択されたモデル名

次回起動時も、この設定が維持されます。

## 環境変数の設定

各プロバイダーには対応するAPIキーが必要です：

- `OPENAI_API_KEY` - OpenAI用
- `ANTHROPIC_API_KEY` - Anthropic用
- `GROQ_API_KEY` - Groq用
- `OPENROUTER_API_KEY` - OpenRouter用
- `GOOGLE_API_KEY` - Google用

## 技術的な詳細

### アーキテクチャ

モデル切り替え機能は以下のコンポーネントで構成されています：

1. **ConfigLoader** (`companion/config/config_loader.py`)
   - `update_config()` - YAMLファイルへの設定の永続化

2. **LLMClient** (`companion/base/llm_client.py`)
   - `reinitialize()` - 新しいプロバイダー/モデルでの再初期化
   - `test_connection()` - 接続テスト

3. **CommandHandler** (`companion/modules/command_handler.py`)
   - `/model` コマンドの処理

4. **DuckAgent** (`companion/core.py`)
   - `switch_model()` - モデル切り替えのオーケストレーション
   - 依存コンポーネント（TaskTool, ResultSummarizer, MemoryManager）の更新

### エラーハンドリング

- APIキーが見つからない場合、切り替えは失敗し、元の設定が維持されます
- 接続テストが失敗した場合、ロールバックが実行されます
- すべてのエラーはログに記録され、ユーザーに通知されます

### 制限事項

- 現在、メインLLMのみが切り替え対象です
- 切り替え中の会話履歴は保持されます
- 切り替え後、新しいモデルで会話が継続されます

## トラブルシューティング

### APIキーが見つからない

**症状：** `/model` コマンドでモデルを切り替えようとすると、「API key not found」エラーが発生する

**解決策：**
1. 環境変数が正しく設定されているか確認
2. `.env` ファイルを使用している場合、ファイルが読み込まれているか確認
3. シェルを再起動して環境変数を再読み込み

### 接続テストが失敗する

**症状：** モデルの切り替えは試みられるが、接続テストで失敗する

**解決策：**
1. インターネット接続を確認
2. APIキーが有効か確認
3. プロバイダーのステータスページで障害がないか確認
4. ベースURLが正しいか確認（カスタムベースURLを使用している場合）

### 設定が保存されない

**症状：** モデルを切り替えても、再起動後に元に戻る

**解決策：**
1. `duckflow.yaml` ファイルの書き込み権限を確認
2. ファイルが読み取り専用になっていないか確認
3. ログを確認して、設定の保存中にエラーが発生していないか確認

## 例

### シナリオ1: 対話的にモデルを切り替え（最も簡単）

```
# モデル選択メニューを表示
/model

# 表示されたリストから数字を選択
選択してください (1-3, またはキャンセルするには 'c'): 2

# 切り替え完了
✅ groq/llama-3.3-70b-versatile に切り替えました
```

### シナリオ2: コスト削減のため高速モデルに切り替え

```
# 現在のモデルを確認
/model current

# 高速で安価なモデルに切り替え
/model groq/llama-3.3-70b-versatile

# 切り替えを確認
/model current
```

### シナリオ3: 複雑なタスクのため高性能モデルに切り替え

```
# 対話的に選択
/model

# GPT-4oを選択（例：番号1）
選択してください: 1

# タスクを実行...

# 完了後、対話的に元のモデルに戻す
/model
選択してください: 3
```

## まとめ

モデル切り替え機能により、Duckflowはより柔軟で効率的なワークフローを実現します。タスクの性質に応じて最適なモデルを選択し、コストとパフォーマンスのバランスを調整できます。

