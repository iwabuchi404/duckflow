# PromptSmith AI設定ガイド

## 概要

PromptSmithのAI設定システムが改善され、役割別AI設定が可能になりました。これにより、各AI役割（TesterAI、EvaluatorAI、OptimizerAI等）で異なるLLMプロバイダーやモデルを使用できます。

## 設定構造

### config/config.yaml での設定

```yaml
# PromptSmith評価システム設定
promptsmith:
  # 評価モード設定
  evaluation:
    enabled: true
    separate_ai_roles: true  # 役割別AI使用の有効化
    timeout_seconds: 120     # 各シナリオのタイムアウト
    max_retries: 3          # 失敗時の再試行回数
  
  # TesterAI設定（挑戦的シナリオ生成）
  tester_ai:
    provider: "groq"
    model_settings:
      openai:
        model: "gpt-4o-mini"
        temperature: 0.3      # 創造的なシナリオ生成のため少し高め
        max_tokens: 2048
      anthropic:
        model: "claude-3-haiku-20240307"
        temperature: 0.3
        max_tokens: 2048
      groq:
        model: "llama-3.1-8b-instant"
        temperature: 0.3
        max_tokens: 2048
  
  # EvaluatorAI設定（対話品質評価）
  evaluator_ai:
    provider: "anthropic"
    model_settings:
      openai:
        model: "gpt-4-turbo-preview"
        temperature: 0.0      # 一貫した評価のため低温度
        max_tokens: 4096
      anthropic:
        model: "claude-3-5-sonnet-20241022"
        temperature: 0.0
        max_tokens: 4096
      groq:
        model: "llama-3.1-70b-versatile"
        temperature: 0.0
        max_tokens: 4096
```

## AI役割一覧

| 役割 | 目的 | 推奨プロバイダー | 推奨モデル | 温度設定 |
|------|------|-----------------|------------|----------|
| **tester_ai** | 挑戦的シナリオ生成 | groq/openrouter | llama-3.1-8b-instant | 0.3 |
| **evaluator_ai** | 対話品質評価 | anthropic/openrouter | claude-3-5-sonnet | 0.0 |
| **optimizer_ai** | 改善提案生成 | openai/openrouter | gpt-4-turbo-preview | 0.2 |
| **conversation_analyzer** | 対話分析 | anthropic/openrouter | claude-3-5-sonnet | 0.1 |
| **target_ai** | 被評価AI（Duckflow） | メインLLM | メイン設定に従う | メイン設定 |

## 使用方法

### 1. プログラムからの利用

```python
from codecrafter.promptsmith.llm_manager import promptsmith_llm_manager

# AI役割別クライアントの取得
tester_client = promptsmith_llm_manager.get_ai_client("tester_ai")

# 役割別チャット実行
response = promptsmith_llm_manager.chat_with_role(
    "tester_ai", 
    "挑戦的なシナリオを生成してください"
)

# 役割情報の取得
role_info = promptsmith_llm_manager.get_role_info("tester_ai")
print(f"Provider: {role_info['provider']}")
print(f"Has API key: {role_info['has_api_key']}")
```

### 2. TesterAIでの利用

```python
from codecrafter.promptsmith.ai_roles.tester_ai import TesterAI

tester = TesterAI()

# AI生成シナリオの作成
scenario = tester.generate_ai_powered_scenario(
    context="Pythonウェブアプリケーション開発プロジェクト",
    difficulty="medium"
)

# シナリオ難易度の分析
analysis = tester.analyze_scenario_difficulty(scenario)
```

## 環境変数設定

各プロバイダーのAPIキーを設定：

```bash
# .env ファイル
GROQ_API_KEY=your_groq_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
GOOGLE_AI_API_KEY=your_google_ai_api_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here
```

### OpenRouter の特徴

OpenRouter は複数のAIモデルプロバイダーを統一したAPIで提供するサービス：

- **豊富なモデル選択**: OpenAI, Anthropic, Meta, Google等のモデルを単一APIで利用
- **コスト効率**: 競争的な価格設定
- **統一インターフェース**: OpenAI互換APIで簡単統合
- **モデル比較**: 同じAPIで異なるモデルを簡単比較

#### 推奨OpenRouterモデル

| 用途 | 推奨モデル | 理由 |
|------|------------|------|
| **コスト重視** | `meta-llama/llama-3.1-8b-instruct` | 安価で高性能 |
| **品質重視** | `anthropic/claude-3-5-sonnet-20241022` | 最高品質の分析能力 |
| **バランス** | `openai/gpt-4o-mini` | コストと性能のバランス |
| **最新機能** | `openai/gpt-4-turbo-preview` | 最新機能とコード理解 |

## フォールバック動作

- APIキーが設定されていない場合、自動的にメインLLMクライアントを使用
- `separate_ai_roles: false` の場合、全AI役割でメインLLM設定を使用
- プロバイダーが利用できない場合、グレースフルにメインクライアントにフォールバック

## テスト方法

設定システムのテスト実行：

```bash
uv run python -X utf8 test_promptsmith_config.py
```

テスト項目：
- 設定読み込み
- 環境変数確認  
- LLM管理システム
- AI役割別クライアント
- TesterAI統合

## 設定のカスタマイズ

### プロバイダーの変更

特定の役割のプロバイダーを変更：

```yaml
promptsmith:
  tester_ai:
    provider: "openrouter"  # groq から openrouter に変更
    model_settings:
      openrouter:
        model: "meta-llama/llama-3.1-8b-instruct"  # コスト効率重視
        temperature: 0.3
        max_tokens: 2048

  evaluator_ai:
    provider: "openrouter"  # 高品質評価用
    model_settings:
      openrouter:
        model: "anthropic/claude-3-5-sonnet-20241022"  # 最高品質
        temperature: 0.0
        max_tokens: 4096
```

### 温度設定の調整

創造性や一貫性の調整：

```yaml
promptsmith:
  tester_ai:
    model_settings:
      groq:
        temperature: 0.5  # より創造的に
```

### 被評価AIの設定

Duckflowエージェント自体の設定上書き：

```yaml
promptsmith:
  target_ai:
    use_main_llm: true
    override_provider: "anthropic"  # 評価時のみClaude使用
    override_model: "claude-3-5-sonnet-20241022"
```

## ベストプラクティス

1. **役割に応じた設定**
   - 評価用AI（evaluator_ai）: 一貫性重視（temperature: 0.0）
   - シナリオ生成AI（tester_ai）: 創造性重視（temperature: 0.3）

2. **コスト最適化**
   - 高頻度使用の役割: 安価なモデル（groq, gpt-4o-mini）
   - 高精度要求の役割: 高性能モデル（claude-3-5-sonnet, gpt-4-turbo）

3. **フォールバック対策**
   - 複数プロバイダーのAPIキーを設定
   - メインLLMは安定性の高いプロバイダーを選択

## トラブルシューティング

### よくある問題

1. **APIキー未設定**
   ```
   [WARNING] anthropic API key not found for evaluator_ai, using main LLM client
   ```
   → `.env` ファイルに対応するAPIキーを追加

2. **設定読み込みエラー**
   ```
   ConfigurationError: PromptSmith設定が見つかりません
   ```
   → `config/config.yaml` に `promptsmith:` セクションを追加

3. **クライアント作成エラー**
   ```
   [ERROR] Failed to create anthropic client
   ```
   → APIキーの有効性を確認、またはプロバイダー設定を変更

### 設定確認コマンド

```python
# 設定の確認
from codecrafter.promptsmith.llm_manager import promptsmith_llm_manager

# 全AI役割の情報表示
info = promptsmith_llm_manager.get_all_roles_info()
for role, data in info.items():
    print(f"{role}: {data['provider']} - {data['has_api_key']}")
```

## 今後の拡張計画

- AI役割の動的追加機能
- 設定のホットリロード
- パフォーマンスメトリクス収集
- 自動プロバイダー切り替え機能