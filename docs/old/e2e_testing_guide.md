# E2Eテストシステムの概要と使用方法

## 1. 目的

このE2E（End-to-End）テストシステムは、単なる機能の単体テストではなく、ユーザーが実際にDuckflowと対話するシナリオを模擬し、AIの応答品質やタスク達成度を総合的に評価することを目的とします。

LLM（大規模言語モデル）の持つ不確実性を受け入れつつ、AIが期待通りに振る舞うかを継続的に確認するための仕組みです。

## 2. システム構成

E2Eテストは、主に以下のコンポーネントで構成されています。

- **テストランナー (`tests/e2e/run_test.py`)**
  - テスト実行の起点となるスクリプトです。

- **シナリオ定義 (`tests/scenarios/**/*.yaml`)**
  - テストしたい内容（最初のプロンプト、評価基準など）を定義するYAMLファイルです。

- **ユーザー役AI (`tests/e2e/conversation_llm.py`)**
  - シナリオに基づき、ユーザーとしてDuckflowと対話を進めるAIです。

- **評価役AI (`tests/e2e/evaluator.py`)**
  - ユーザー役AIとDuckflowの対話ログ全体を読み、シナリオの評価基準に沿って結果を採点するAIです。

- **Duckflow本体 (`companion/`配下)**
  - `test_runner.py` の内部で呼び出される、テスト対象のアプリケーションです。

## 3. 使用方法

### 3.1 既存のテストシナリオを実行する

1. `tests/scenarios/` の中から実行したいテストの `.yaml` ファイルを探します。
2. 以下のコマンド形式で `run_test.py` を実行します。

```bash
# uv run python [テストランナーのパス] [シナリオファイルのパス]
uv run python tests/e2e/run_test.py tests/scenarios/level1/file_creation_simple.yaml
```

### 3.2 新しいテストシナリオを作成して実行する

1. **シナリオファイルを作成する**
   - `tests/scenarios/` 配下に、テストしたい内容を記述した新しい `.yaml` ファイルを作成します。
   - 例えば、`review_code.yaml` のような名前で作成します。

2. **シナリオを定義する**
   - ファイル内に、以下の必須項目を記述します。
     - `name`: テストの名前（日本語可）
     - `description`: テスト内容の説明
     - `scenario`: ユーザー役AIが最初に発するプロンプト
     - `evaluation_criteria`: 評価役AIが使用する評価基準

   **記述例:**
   ```yaml
   name: "コードレビュー"
   level: 1
   genre: "レビュー系"
   description: "簡単なPythonコードをレビューできるか"
   
   scenario: |
     `hello.py` というファイルの内容をレビューして、改善点を教えてください。
   
   evaluation_criteria: |
     1. `hello.py` の内容を正しく理解しているか。
     2. コードの改善点を具体的に指摘できているか。
   ```

3. **テストを実行する**
   - 作成したシナリオファイルを指定して、`run_test.py` を実行します。

   ```bash
   uv run python tests/e2e/run_test.py tests/scenarios/level1/review_code.yaml
   ```

## 4. テスト結果の確認

テストを実行すると、コンソールにテストの成否、総合スコア、各評価項目のスコアが表示されます。

また、詳細な対話ログが `tests/e2e/logs/` ディレクトリの中にJSONファイルとして保存されるため、後から詳細なやり取りを確認することも可能です。
