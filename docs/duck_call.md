### **設計ドキュメント1：`Duck Call` - 汎用ヒューマン・イン・ザ・ループ システム**

**バージョン:** 2.0
**システム名:** `Duck Call`
**目的:** AIがタスク遂行中に自律的な判断が困難になった際、ユーザー（司令官）に助けを求め、最終的な意思決定を仰ぐための、統一されたコミュニケーション・チャネルを定義する。

#### **1. コンセプト：助けを求める特別な「呼び声」**

`Duck Call`は、狩猟で仲間を呼ぶ鳥笛のように、`Duckflow`がユーザーに助けを求めるために送る、特別な信号（Call）です。この信号が発せられたとき、エージェントの自律的なループは一時停止し、人間の介入を待ちます。これは、AIの弱さを認め、人間との協調を促す、`Duckflow`の哲学を象徴するシステムです。

#### **2. アーキテクチャ上の位置づけ**

*   `Duck Call`は、`LangGraph`における**専用のターミナルノード（`duck_call_node`）**として実装される。
*   このノードは**LLMを呼び出さず**、`AgentState`に格納された情報を基に、UI表示とユーザー入力の受付という機械的な処理に徹する。

#### **3. データ構造 (`state.py`)**

```python
class DuckCallChoice(BaseModel):
    """ユーザーに提示する選択肢"""
    id: str  # 例: "1", "A"
    description: str # 例: "詳細指示を与える"

class DuckCallQuery(BaseModel):
    """Duck Callがユーザーに提示する問い合わせ全体"""
    query_id: str = Field(default_factory=lambda: f"query_{uuid.uuid4().hex[:8]}")
    title: str # 例: "⚠️ 作戦会議の時間です！"
    message: str  # ユーザーに表示するメインメッセージ
    choices: Optional[List[DuckCallChoice]] = None # 選択肢
    expects_free_text: bool = True # 自由テキスト入力を期待するか

class AgentState(BaseModel):
    # ...
    # Duck Callシステム用のフィールド
    duck_call_query: Optional[DuckCallQuery] = None
    duck_call_response: Optional[str] = None # ユーザーの応答
```

#### **4. 処理フロー**

1.  **発信 (Calling):** プランナーAIまたはエバリュエーターAIが、次のアクションとして`ASK_USER`を決定し、`DuckCallQuery`オブジェクトを生成して`state.duck_call_query`にセットする。
2.  **転送 (Routing):** オーケストレーターの分岐ロジックがこれを検知し、`duck_call_node`に遷移させる。
3.  **`duck_call_node`の実行 (Interaction):**
    *   `state.duck_call_query`の内容を`Duck Roleplay Converter`に渡し、キャラクター性のある対話文を生成させる。
    *   生成されたメッセージと選択肢をUIに表示する。
    *   ユーザーからの応答を待機し、`state.duck_call_response`に保存する。
4.  **再始動 (Resuming):** `duck_call_node`の次は、常に`1️⃣理解・計画ノード`に遷移する。計画AIは、`state.duck_call_response`を最優先のコンテキストとして新しい計画を立案する。

---
