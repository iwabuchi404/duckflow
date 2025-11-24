# Duckflow v4 アーキテクチャ設計ドキュメント (v7プラン)

## 1. はじめに

### 1.1. 背景と課題
旧アーキテクチャでは、`action_type`や固定コマンドによる処理分岐が、システムの柔軟性を損ない、AIの自律的な判断を阻害するという課題が明らかになった。また、長期的な計画と短期的なタスクの区別が曖昧であり、複雑なユーザー要求に対応できない問題があった。

### 1.2. 設計目標
本ドキュメントで定義するv4アーキテクチャは、以下の実現を目標とする。
- **柔軟性の向上:** 固定的なコマンドやタイプ分岐を撤廃し、AIが状況に応じて利用可能なツールを自由に組み合わせられるようにする。
- **責務の明確化:** 各コンポーネントの役割を明確に分離し、見通しが良く、拡張性の高いコードベースを構築する。
- **階層的プランニング:** ユーザーの長期的な目標と、それを達成するための具体的な短期タスクを階層的に管理し、複雑な要求に対応する。
- **予測可能性と安定性:** `TaskLoop`の役割を明確化し、システムの動作をより確実で制御可能なものにする。

## 2. 設計思想：統一ツールコールモデル

v4アーキテクチャの核心は、**統一ツールコールモデル**にある。これは、AI（メインLLM）の思考結果を、常に**「次に実行すべきツール操作のリスト」**という単一の形式で出力させる設計思想である。

- **脱コマンド、ツールコールへの統一:** `propose_plan`や`execute_step`のような事前定義されたコマンドは存在しない。全てのAIの行動は、`plan_tool.propose(...)`や`file_ops.write(...)`といった、特定のツールへの具体的な呼び出し指示(`Action`)として表現される。
- **`ActionList`による行動計画:** メインLLMは、ユーザーの要求と現在の状態を分析し、次に実行すべき一連の`Action`をリスト化した`ActionList`を生成する。これがAIの短期的な行動計画となる。

このモデルにより、AIは固定観念に縛られず、利用可能なツールセットの中から最適な組み合わせを自律的に選択できるようになる。

## 3. アーキテクチャ全体像 (v7)

```mermaid
graph TD
    A[User Input] --> B[ChatLoop];
    
    subgraph ChatLoop
        B -- ユーザー入力 + AgentState --> C{Main LLM Call};
        C -- "次に実行すべきActionList" --> D{Action Dispatcher};
    end

    subgraph "High-level Tools"
        F[PlanTool]
        G[TaskTool]
    end

    subgraph TaskLoop (Background Worker)
        I[TaskListの非同期実行と<br/>LLMによる結果報告]
    end

    D -- ActionListを解釈 --> E{For each Action in ActionList};
    E -- "plan_tool.propose"など --> F;
    E -- "task_tool.generate_list" --> G;
    G -- TaskListを生成 --> J[AgentState Update];
    
    E -- "task_loop.run(task_list)" --> I;

    F & I -- 実行結果 --> J;
    J --> K[Response Generation];
    K --> A;
```

## 4. 主要コンポーネントの責務

### 4.1. ChatLoop と メインLLMコール
- **役割:** システムの「中央指令室」。
- **動作:** ユーザー入力と`AgentState`の全コンテキストを基に、次に実行すべき`ActionList`を生成する。システムの全ての動作は、この`ActionList`が起点となる。

### 4.2. Action Dispatcher (in ChatLoop)
- **役割:** `ActionList`の実行管理者。
- **動作:** `ActionList`内の各`Action`を順番に解釈し、適切なツールに処理を振り分ける。`Action`が軽量な場合は直接ツールを呼び出し、重い処理（`task_loop.run`など）の場合は`TaskLoop`に実行を委譲する。

### 4.3. PlanTool
- **役割:** 長期計画の状態管理（CRUD）を担当する。
- **メソッド例:**
    - `propose(goal: str) -> Plan`: 新規`Plan`を生成し、`AgentState`に追加。
    - `update_step(step_id: str, status: str, ...)`: `Step`の状態を更新。
    - `get(plan_id: str) -> Plan`: `Plan`情報を取得。

### 4.4. TaskTool
- **役割:** 短期的な作業リスト(`TaskList`)の**生成のみ**を担当する「計画者」。
- **メソッド例:**
    - `generate_list(step_id: str) -> List[Task]`: 特定の`Step`を達成するための具体的な`TaskList`を生成し、`AgentState`に保存する。

### 4.5. TaskLoop
- **役割:** 重い`TaskList`の非同期実行と、LLMによる結果報告を担当する「非同期ワーカー兼報告者」。
- **動作:**
    1. `ChatLoop`から`TaskList`の実行を委譲されると起動。
    2. `TaskList`内の各`Task`（`file_ops.write`など）を順番に実行する。
    3. 全て完了後、実行結果（ログ、成否など）を基にLLMにサマリーを生成させ、`ChatLoop`に報告する。

## 5. データ構造：階層的プランニングモデル

`companion/state/agent_state.py`に、以下の階層的データモデルを定義する。

```python
import uuid
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field

# Action: メインLLMが生成する高レベルの行動計画
class Action(BaseModel):
    operation: str  # e.g., "plan_tool.propose", "task_tool.generate_list"
    args: Dict[str, Any] = Field(default_factory=dict)
    reasoning: Optional[str] = None

# Task: TaskToolが生成する低レベルの具体的な作業
class Task(BaseModel):
    task_id: str = Field(default_factory=lambda: f"task_{uuid.uuid4().hex[:8]}")
    operation: str  # e.g., "file_ops.write_file"
    args: Dict[str, Any] = Field(default_factory=dict)
    status: Literal["pending", "in_progress", "completed", "failed"] = "pending"
    result: Optional[Any] = None

class Step(BaseModel):
    step_id: str = Field(default_factory=lambda: f"step_{uuid.uuid4().hex[:8]}")
    name: str
    description: str
    status: Literal["pending", "in_progress", "completed", "failed"] = "pending"
    depends_on: List[str] = Field(default_factory=list)
    task_list: List[Task] = Field(default_factory=list)

class Plan(BaseModel):
    plan_id: str = Field(default_factory=lambda: f"plan_{uuid.uuid4().hex[:8]}")
    name: str
    goal: str
    status: Literal["draft", "approved", "in_progress", "completed", "failed"] = "draft"
    steps: List[Step] = Field(default_factory=list)

class AgentState(BaseModel):
    # ...
    plans: List[Plan] = Field(default_factory=list)
    active_plan_id: Optional[str] = None
    # ...
```

## 6. プロンプトシステム

### 6.1. メインLLMコール用プロンプト (ActionList生成)
- **役割:** 司令塔として、次に実行すべき`ActionList`を決定する。
- **コンテキスト:** このプロンプトには、ユーザーの最新の要求に加え、`AgentState`から取得した**プラン全体の進捗状況**（例：「プラン『ゲーム実装』の5ステップ中2ステップが完了」といったサマリー）がコンテキストとして注入されます。これにより、LLMはプロジェクトの全体像と現在地を把握した上で、次の最適な`Action`を判断します。
- **指示例:** 「あなたはAIアシスタントの司令塔です。以下の`AgentState`とユーザーの最新の要求を分析し、次に実行すべき一連のツール呼び出し(`ActionList`)をJSON形式で出力してください。ユーザーの要求が複雑な場合は、まず`plan_tool.propose`で計画を立てることを検討してください。」

### 6.2. PlanTool用プロンプト (Plan生成)
- **役割:** `Specialized Prompt`として、長期的・抽象的な`Plan`と`Step`を生成する。
- **指示例:** 「ユーザーの目標『{user_goal}』を達成するための長期計画を、複数の`Step`に分解してJSON形式で提案してください。各`Step`には`name`, `description`, `depends_on`（依存するステップID）を含めてください。」

### 6.3. TaskTool用プロンプト (TaskList生成)
- **役割:** `Specialized Prompt`として、特定の`Step`を達成するための具体的な`TaskList`を生成する。
- **指示例 (案B: リッチコンテキスト):** 「以下の情報に基づき、ステップ『{step.name}』を達成するための具体的な作業リスト(`TaskList`)をJSONで生成してください。

### 長期計画の全体目標:
{plan.goal}

### 現在のステップ詳細:
{step.description}

### 関連する会話の要約:
{conversation_summary}」

### 6.4. TaskLoop用プロンプト (結果報告サマリー生成)
- **役割:** `Specialized Prompt`として、`TaskLoop`の実行結果を人間や次のLLMが理解しやすい形に要約する。
- **指示例:** 「以下の`TaskList`の実行結果を分析し、結果を報告するJSONを生成してください。報告には、全体の成否(`status`)、成功したタスクと失敗したタスクの数、失敗した場合はその原因と推奨される次のアクションを含めてください。

### 実行結果ログ:
{execution_log}」

## 7. 処理フローの例

1.  **User:** 「ゲームを実装して」
2.  **Main LLM** -> `ActionList: [ Action(operation='plan_tool.propose', args={'goal': 'ゲームを実装する'}) ]`
3.  **Dispatcher** -> `PlanTool.propose()` を実行。
4.  **PlanTool** -> LLMを呼び出し、`Plan`オブジェクトを生成。`AgentState`を更新。
5.  **Response:** 「ゲーム実装の計画を提案します...（中略）...この計画で進めますか？」
6.  **User:** 「はい、お願いします」
7.  **Main LLM** -> `ActionList: [ Action(operation='task_tool.generate_list', args={'step_id': 'step_001'}) ]` (ステップ1: 環境構築)
8.  **Dispatcher** -> `TaskTool.generate_list()` を実行。
9.  **TaskTool** -> LLMを呼び出し、`TaskList`（`file_ops.write('package.json', ...)`など）を生成。`AgentState`を更新。
10. **Main LLM** -> `ActionList: [ Action(operation='task_loop.run', args={'task_list': [...]}) ]`
11. **Dispatcher** -> `task_loop.run`を検知し、`TaskLoop`に処理を委譲。
12. **TaskLoop** -> `TaskList`を実行。完了後、結果をLLMで要約して`ChatLoop`に報告。
13. **Response:** 「ステップ1『環境構築』が完了しました。`package.json`を作成し、依存関係をインストールしました。次にステップ2『コア実装』に進みますか？」

## 8. 実装ステップ

このv7アーキテクチャを実現するため、以下の順序で実装を進めます。

### ステップ1: `AgentState`のデータ構造強化
`companion/state/agent_state.py`に、本ドキュメントのセクション5で定義された`Plan`, `Step`, `Task`の階層的データモデルを実装します。これは、全ての新機能の基礎となる最優先タスクです。

### ステップ2: `PlanTool`と`TaskTool`の定義
`companion/plan_tool.py`を計画のCRUDツールとして、`companion/task_tool.py`をタスクリスト生成ツールとしてそれぞれ新規に作成、または既存のものを拡張して実装します。

### ステップ3: `TaskLoop`の処理フロー修正
`companion/enhanced/task_loop.py`のロジックを、`TaskList`を非同期で実行し、完了後に結果をLLMで要約報告するシンプルなワーカーとして再実装します。

### ステップ4: `EnhancedCompanionCore`とディスパッチャの実装
`companion/enhanced_core.py`に、メインLLMコールから返された`ActionList`を解釈し、各`Action`を適切なツールや`TaskLoop`に振り分けるディスパッチャロジックを実装します。これは、システムの挙動を決定する最も中心的な変更となります。