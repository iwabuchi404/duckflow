### **設計ドキュメント3：`The Pecking Order` - 階層的タスク管理システム**

**バージョン:** 2.0
**システム名:** `The Pecking Order`
**目的:** 鳥の社会の「階層序列（Pecking Order）」をメタファーとし、親タスクとサブタスクの厳格な階層関係と実行順序を管理する、プロジェクトの設計図となるシステムを定義する。

#### **1. コンセプト：タスクの階層序列**

`Duckflow`が扱う複雑なタスクは、一つの親タスク（つつきの順位が最も高いリーダー）と、それに従属する複数のサブタスク（フォロワー）からなる階層構造として表現される。この「つつきの順序」に従ってタスクを一つずつ処理していくことで、エージェントは最終的なゴールに向かって着実に進んでいく。

#### **2. アーキテクチャ上の位置づけ**

*   `The Pecking Order`は、`Golden Fish Memory Protocol`の短期記憶層`The Bubble`の実体であり、`Atlas`システムの正式名称である。
*   その実体は、`AgentState`内に保持される、**`Task`クラスの木構造（ツリー）**である。

#### **3. データ構造 (`state.py`)**

```python
class TaskStatus(Enum):
    PENDING = "PENDING"; IN_PROGRESS = "IN_PROGRESS"; COMPLETED = "COMPLETED"; FAILED = "FAILED"

class Task(BaseModel):
    id: str = Field(default_factory=lambda: f"task_{uuid.uuid4().hex[:8]}")
    description: str # "JWTライブラリをインストールする"
    status: TaskStatus = TaskStatus.PENDING
    parent_id: Optional[str] = None # 親タスク（つついた鳥）のID
    sub_tasks: List['Task'] = Field(default_factory=list) # 子タスク（つつかれる鳥）のリスト
    result: Optional[str] = None

class AgentState(BaseModel):
    # ...
    # The Pecking Order
    main_goal: str
    task_tree: Task # タスク全体の階層序列
    current_task_id: Optional[str] # 現在つついているタスクのID
```

#### **4. 処理フローへの統合**

1.  **序列の決定:** `1️⃣理解・計画ノード`は、ユーザーの要求を分析し、`Task`オブジェクトの木構造、すなわち`The Pecking Order`を構築する。
2.  **序列の可視化:** `PromptCompiler`は、プロンプトを生成する際に`The Pecking Order`を参照する。AIには、常に「最終目標」「現在のサブタスク」「完了済みの兄弟タスク」といった、階層内での現在地が知らされる。
3.  **序列の更新:** `4️⃣評価・継続ノード`は、実行結果に基づき、`The Pecking Order`内の対応するタスクの`status`を更新する。
4.  **次の序列へ:** `評価・継続ノード`は、現在のタスクが完了した場合、`The Pecking Order`を見て次に実行すべきタスク（次の兄弟タスク or 親タスクの完了判定）を決定する。