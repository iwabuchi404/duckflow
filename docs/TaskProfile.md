### **設計ドキュメント：`TaskProfile` - タスク属性システム**

**バージョン:** 1.0
**目的:** エージェントが扱う各タスクの「性質」を、複数の直交する属性（意図、範囲、複雑度）で構造化して定義する。これにより、`Duckflow`の各ノード（計画、評価など）が、タスクの文脈に応じた、一貫性のある、インテリジェントな意思決定を行えるようにする。

#### **1. コンセプト：タスクの「DNA」を定義する**

`TaskProfile`は、`The Pecking Order`で管理される各`Task`オブジェクトに付与される、そのタスクの根源的な性質（DNA）を記述したデータ構造です。
`Duckflow`は、この`TaskProfile`を読み解くことで、単にタスクの`description`（説明）を読むだけでなく、そのタスクが**「なぜ（Why）」**存在し、**「どのように（How）」**扱われるべきかを深く理解します。

#### **2. アーキテクチャ上の位置づけ**

*   `TaskProfile`は、`1️⃣理解・計画ノード`によって生成され、`The Pecking Order`の各`Task`オブジェクトに**付与**されます。
*   一度付与された`TaskProfile`は、原則としてそのタスクが完了するまで**不変**です。
*   後続の全てのノード（情報収集、実行、評価）は、現在実行中のタスクの`TaskProfile`を**参照**し、自らの振る舞いを動的に調整します。

#### **3. データ構造 (`state.py`)**

`TaskProfile`は、3つの主要な属性（Enum）で構成されます。これにより、「状態空間の爆発」を防ぎつつ、タスクの性質を柔軟に表現します。

```python
# duckflow/state/task_profile.py (新規作成または state.py 内に定義)

from enum import Enum
from pydantic import BaseModel

class TaskIntent(Enum):
    """タスクの最終的な意図"""
    READ = "READ"          # 情報を知りたい、取得したい
    WRITE = "WRITE"        # 何かを作成・変更したい
    EXECUTE = "EXECUTE"      # コマンドなどを実行したい
    EVALUATE = "EVALUATE"    # 何かを評価・比較してほしい

class TaskScope(Enum):
    """タスクが対象とする範囲"""
    SINGLE_FILE = "SINGLE_FILE"
    MULTI_FILE = "MULTI_FILE"
    PROJECT_WIDE = "PROJECT_WIDE"

class TaskComplexity(Enum):
    """求められる思考の深さ・複雑度"""
    SIMPLE = "SIMPLE"          # 単純な操作 (表示、インストールなど)
    ANALYTICAL = "ANALYTICAL"    # 分析・要約が必要
    COMPARATIVE = "COMPARATIVE"   # 複数の要素の比較が必要
    CREATIVE = "CREATIVE"        # 新しいコードや文章の生成が必要

class TaskProfile(BaseModel):
    """タスクの性質を多角的に定義するプロファイル (タスクのDNA)"""
    intent: TaskIntent
    scope: TaskScope
    complexity: TaskComplexity
```

#### **4. 各ノードとの連携仕様**

##### **`1️⃣理解・計画ノード` (プロファイルの生成者)**
*   **責務:** ユーザーの要求を分析し、`Task`オブジェクトを生成する際に、**最も重要な責務として、そのタスクに適切な`TaskProfile`を付与する。**
*   **実装:**
    *   `LLMService`に`create_task_profile(user_input: str) -> TaskProfile`というサブタスクLLMを実装する。
    *   このLLMは、ユーザーの自然言語を解釈し、3つのEnumの最も適切な組み合わせを決定して、`TaskProfile`オブジェクトとして返す。

##### **`2️⃣情報収集ノード` (プロファイルに基づく戦略家)**
*   **責務:** 現在のタスクの`TaskProfile.scope`を参照し、情報収集の戦略を決定する。
*   **実装:**
    *   `if task.profile.scope == TaskScope.PROJECT_WIDE:` → RAG検索と`list_files(recursive=True)`を優先する。
    *   `if task.profile.scope == TaskScope.SINGLE_FILE:` → 指定されたファイルの`read_file`に集中する。

##### **`3️⃣安全実行ノード` (プロファイルに基づくリスク管理者)**
*   **責務:** `TaskProfile.intent`を参照し、リスクレベルを判断し、`Duck Call`（人間承認）を発動するかを決定する。
*   **実装:**
    *   `if task.profile.intent == TaskIntent.WRITE:` → `Duck Call`の発動閾値を下げる（より頻繁に承認を求める）。
    *   `if task.profile.intent == TaskIntent.EXECUTE:` → ホワイトリストに含まれるコマンドか、より厳密にチェックする。

##### **`4️⃣評価・継続ノード` (プロファイルに基づく品質保証)**
*   **責務:** `TaskProfile`を**「評価のための採点基準書」**として使用し、タスクの完了を判断する。
*   **実装:**
    *   `PromptCompiler`は、評価用プロンプトを生成する際に、`TaskProfile`の全属性をコンテキストに含める。
    *   プロンプトには、属性の組み合わせに応じた**動的な評価基準（`evaluation_criteria`）**を注入する。
        *   **例:** `if task.profile.intent == TaskIntent.READ and task.profile.complexity == TaskComplexity.SIMPLE:`
            *   評価基準は「要求されたファイルが正常に読み込まれたか」。
        *   **例:** `if task.profile.intent == TaskIntent.READ and task.profile.complexity == TaskComplexity.ANALYTICAL:`
            *   評価基準は「ファイルが読み込まれた上で、その内容に基づいた質の高い分析や要約が生成されているか」。

#### **5. `The Pecking Order`との統合**

*   `Task`クラスに`profile: TaskProfile`フィールドを追加することで、`The Pecking Order`と`TaskProfile`システムは完全に統合される。
*   これにより、親タスクは**大局的な性質**（例: `WRITE/PROJECT_WIDE/CREATIVE`）を持ち、その子タスクは、より**具体的で、多様な性質**（`READ/ANALYTICAL`, `EXECUTE/SIMPLE`など）を持つ、というリッチで構造化された計画が実現する。