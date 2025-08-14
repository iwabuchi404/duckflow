### ドキュメント1：サブタスクLLM (LLM Services) 設計ドキュメント

#### 1. 概要 (Overview)

本ドキュメントでは、`Duckflow`におけるLLM（Large Language Model）の利用を効率化・モジュール化するための、`LLMService`アーキテクチャについて解説します。このアーキテクチャは、各タスクの性質に応じて最適なLLMを選択し、再利用可能な形で提供することを目的とします。

#### 2. なぜLLMサービスが必要なのか？ (Motivation)

*   **多様なタスク:** `Duckflow`は、計画立案、コード生成、レビュー、要約など、様々な性質のタスクを実行する必要があります。
*   **異なるモデルの特性:** 各LLMは、得意とするタスクや、速度、コストなどの特性が異なります。
*   **一元管理の必要性:** LLMへのアクセスを一箇所に集約することで、設定変更、APIキーの管理、ロギングなどを効率的に行うことができます。

#### 3. アーキテクチャ (Architecture)

`LLMService`は、以下の要素で構成されます。

*   **LLMクライアント:** `LangChain`などのライブラリでラップされた、個々のLLMへの接続オブジェクト。
*   **サービスメソッド:** 各タスクに対応したメソッド。プロンプトの構築、LLMの呼び出し、結果の解析などの処理をカプセル化します。
*   **設定:** 使用するLLMの種類、APIキー、プロンプトのテンプレートなどを外部ファイル（`config.yaml`）で管理します。

#### 4. 主要コンポーネントの詳細

*   **`LLMService`クラス (`llm_services.py`):**
    ```python
    class LLMService:
        def __init__(self, model_provider):
            self.creative_llm: BaseChatModel = model_provider.get_llm("opus") # 例: Claude 3 Opus
            self.fast_llm: BaseChatModel = model_provider.get_llm("haiku")   # 例: Claude 3 Haiku
            self.evaluator_llm: BaseChatModel = model_provider.get_llm("sonnet")# 例: Claude 3 Sonnet
        
        def generate_plan(self, user_request: str, context: str) -> str:
            """ユーザー要求から実行計画を立案する"""
            # ...
        
        def evaluate_execution_result(self, plan: str, result: str, user_goal: str) -> dict:
            """ツールの実行結果を評価し、次の行動を決定する"""
            # ...

        def summarize_text(self, long_text: str, max_length: int = 200) -> str:
            """長いテキストを要約する (高速モデルを使用)"""
            # ...
    ```

*   **設定ファイル (`config.yaml`):**
    ```yaml
    llm_providers:
      openai:
        api_key_env: "OPENAI_API_KEY"
        models:
          opus: "gpt-4o"
          haiku: "gpt-4o-mini"
          sonnet: "gpt-3.5-turbo"
      anthropic:
        api_key_env: "ANTHROPIC_API_KEY"
        models:
          opus: "claude-3-opus-20240229"
          haiku: "claude-3-haiku-20240229"
          sonnet: "claude-3-sonnet-20240229"
    ```

#### 5. 実装手順

1.  `llm_services.py`ファイルを作成し、`LLMService`クラスを定義する。
2.  `config.yaml`に、利用するLLMプロバイダとモデルを設定する。
3.  `LLMService`の各メソッド（`generate_plan`など）を実装する。
    *   各メソッドは、適切なプロンプトテンプレートを選択し、LLMを呼び出し、結果を解析して返す。
4.  `LangGraph`の各ノードから、`LLMService`のメソッドを呼び出すように変更する。

#### 6. ベストプラクティス

*   **明確な役割分担:** 各サービスメソッドは、**一つの明確なタスク**に特化させる。
*   **設定の活用:** プロンプトのテンプレートやモデル名などを、コードにハードコードせず、設定ファイルから読み込む。
*   **エラーハンドリング:** LLM呼び出し時に発生する可能性のあるエラー（API制限、ネットワークエラーなど）を適切に処理する。
*   **ロギング:** LLMとのやり取り（プロンプト、応答、エラー）を詳細に記録する。

#### 7. 将来の展望

*   **動的なモデル選択:** タスクの複雑さや、利用可能なAPIの状況に応じて、LLMをリアルタイムで切り替える。
*   **キャッシュ:** LLMからの応答をキャッシュし、同じタスクが繰り返し実行される場合にAPI呼び出しをスキップする。
*   **ファインチューニング:** 特定のタスク（例: コードレビュー）に特化したカスタムモデルをファインチューニングし、`LLMService`から利用する。

---
