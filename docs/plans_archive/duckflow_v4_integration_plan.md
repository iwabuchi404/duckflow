# ドキュメント：階層的タスクプランニング導入指示書

## 1. 概要

### 1.1. 目的
本改修の目的は、Duckflowの中核である `EnhancedCompanionCoreV8` を、v4アーキテクチャで定義された**階層的プランニングモデル**へ完全移行させることです。現在のフラットな操作リスト生成方式を廃止し、`Plan` (長期計画) -> `Step` (段落) -> `Task` (具体的作業) の階層で自律的に思考・実行する能力を実装します。

### 1.2. 主な対象ファイル
- `companion/enhanced_core_v8.py`: メインロジックの全面的な改修
- `companion/prompts/prompt_compiler.py`: 階層的思考を促すためのプロンプト改修

### 1.3. 統合対象コンポーネント
- `companion/plan_tool.py`: 長期計画の管理
- `companion/v7_task_tool.py`: `Step`から`TaskList`への分解
- `companion/enhanced/task_loop.py`: `TaskList`の非同期実行
- `companion/state/agent_state.py`: `Plan`, `Step`, `Task`, `Action` のデータモデル

## 2. 実装ステップ

### ステップ1: `EnhancedCompanionCoreV8`の役割変更とディスパッチャの導入

**ファイル:** `companion/enhanced_core_v8.py`

**タスク:**
1.  現在の `_handle_action_execution` メソッドおよび、フラットな `operations` リストを生成する `_generate_llm_plan` メソッドを**廃止**します。
2.  `process_user_message` を起点とし、以下の流れを実装する新しい中心的な処理ループを構築します。
    1.  **`_generate_next_actions()` (新規作成):** 新しいプロンプト（ステップ2で詳述）を用いて、LLMに次に実行すべき高レベルな `Action` のリスト (`List[Action]`) をJSON形式で生成させます。
    2.  **`_dispatch_actions(actions: List[Action])` (新規作成):** `_generate_next_actions` が返した `Action` のリストを順番に処理するディスパッチャを実装します。このメソッドは `action.operation` の文字列を基に、対応するツール（`PlanTool`など）のメソッドを呼び出します。

### ステップ2: プロンプトシステムの刷新による階層的思考の促進

**ファイル:** `companion/enhanced_core_v8.py` または `companion/prompts/` 配下の関連ファイル

**タスク:**
1.  ステップ1で作成する `_generate_next_actions` メソッド内で使用する、**新しいメインプロンプト**を定義します。
2.  このプロンプトには、以下の要素を必ず含めてください。
    -   **役割定義:** 「あなたは、ユーザーの要求を長期的な`Plan`と短期的な`Task`に分解して実行を管理する、優秀なプロジェクトマネージャーです。」
    -   **現在の状態:** `AgentState` からアクティブな`Plan`の進捗状況（例：「プラン『ゲーム開発』の5ステップ中2ステップが完了」）や、直近の会話履歴を要約して提示します。
    -   **ユーザーの要求:** 最新のユーザーメッセージを提示します。
    -   **利用可能な高レベル`Action`:** 実行可能な操作を `plan_tool.propose`, `task_tool.generate_list`, `task_loop.run`, `user_response_tool.generate_response` に限定し、それぞれの役割を明確に説明します。
    -   **思考プロセスと出力形式:** 思考の過程（reasoning）と、最終的な出力（`Action`のリスト）をJSON形式で出力するよう厳密に指示します。

### ステップ3: `PlanTool`、`TaskTool`、`TaskLoop`の統合

**ファイル:** `companion/enhanced_core_v8.py`

**タスク:**
1.  `_dispatch_actions` メソッド内に、`plan_tool.propose` アクションを処理するロジックを追加します。実行結果の `Plan` を `AgentState` に保存し、`active_plan_id` を設定します。
2.  同様に、`task_tool.generate_list` アクションを処理するロジックを追加します。生成された `TaskList` を、`AgentState` 内の対応する `Plan` の `Step` に正しく格納します。
3.  `task_loop.run` アクションを処理するロジックを追加します。この処理は**非同期**でなければなりません。`TaskLoop` の `task_queue` に `TaskList` を投入し、ユーザーには「作業を開始します」といった中間応答を即座に返します。`TaskLoop` の完了報告を待ってはいけません。

## 3. 想定されるデータフロー

改修後のデータフローは以下のようになります。

```mermaid
graph TD
    A[User Input] --> B{EnhancedCompanionCoreV8};
    B -- 1. 状態をプロンプトに含め --> C[Main LLM Call];
    C -- 2. ActionListを生成 --> B;
    B -- 3. Actionを解釈 --> D{Action Dispatcher};
    D -- 'plan_tool.propose' --> E[PlanTool];
    D -- 'task_tool.generate_list' --> F[TaskTool];
    D -- 'task_loop.run' --> G[TaskLoop (非同期)];
    E & F & G -- 4. 実行結果 --> H[AgentState 更新];
    H --> I[Response Generation];
    I --> A;
```

## 4. レビューの観点

実装完了後、私がレビューする際の主要な確認項目は以下の通りです。

1.  `EnhancedCompanionCoreV8` のメインロジックが、LLMの生成した `ActionList` に基づいて処理を正しくディスパッチしているか。
2.  新しいメインプロンプトが、LLMに階層的な思考を促す内容になっているか。
3.  `PlanTool` や `TaskTool` の実行結果が、`AgentState` に正しく反映されているか。特に `TaskList` が `Step` オブジェクト内に保存されているか。
4.  `TaskLoop` への処理委譲が非同期で行われ、UIがブロックされていないか。
5.  古いフラットな `operations` リストを扱うロジックが完全に削除されているか。
