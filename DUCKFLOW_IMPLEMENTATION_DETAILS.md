# Duckflow 実装詳細: v4 アーキテクチャ

## 🦆 1. 統一アクションプロトコル (Action Protocol)

Duckflow v4 の核心は、LLMが「ツール実行」と「ユーザーへの応答」を同一の出力形式で決定することにあります。

### ActionList 構造
LLMは常に以下の JSON 構造を出力するように指示されます（JSON Mode 使用）。

```json
{
  "reasoning": "現在のユーザーの要望は〇〇であり、そのためにはまず××を実行する必要があります...",
  "actions": [
    {
      "name": "read_file",
      "parameters": {"path": "main.py"},
      "thought": "既存のコード構造を確認するため"
    },
    {
      "name": "write_file",
      "parameters": {"path": "new_feature.py", "content": "..."},
      "thought": "新機能を実装するため"
    }
  ],
  "vitals": {
    "mood": 0.9,
    "focus": 0.8
  }
}
```

## 🧠 2. Think-Decide-Execute ループ

エージェントの動作は、隠蔽された複雑なグラフ構造（LangGraph等）ではなく、明示的な `while` ループで制御されます。

### ループの各フェーズ
1. **Think & Decide**:
   - `AgentState` からコンテキスト（履歴、計画、バイタル、最後の実行結果）を動的に組み立て、プロンプトを生成。
   - LLM を呼び出し、`ActionList` を取得。
2. **Execute**:
   - `ActionList.actions` を上から順に実行。
   - 各アクションの実行結果を `AgentState` に記録。
   - `response` アクションや `exit` アクションが含まれる場合、自律ループを抜けてユーザーに入力を促す。

## 📋 3. Hierarchical Planning (階層的計画)

複雑なタスクを確実に遂行するため、3つの階層で管理します。

- **Plan (長期目標)**: 最終的なゴール（例：「Webアプリをデプロイする」）。
- **Step (中期目標)**: Plan を分割した一連のフェーズ（例：「環境設定」「API実装」「フロントエンド実装」）。
- **Task (短期作業)**: Step を構成する具体的なアクション（例：「requirements.txtの作成」「main.pyの編集」）。

エージェントは `propose_plan` で計画を立て、`generate_tasks` でタスクを詳細化してから実行に移ります。

## 💓 4. Vitals & Pacemaker (生存管理)

エージェントには「スタミナ」「集中力」などの概念があり、行動によって変化します。

- **Vitals**: `AgentState` に保持される数値。
- **Pacemaker**: ループ回数やエラーの連続発生、スタミナ切れを監視。異常を検知すると `duck_call`（ユーザーへの相談）を強制的に発生させ、暴走や無限ループを防止します。

## 🗂️ 5. 記憶とコンテキストの整理

- **Conversation History**: 全ての対話を記録。
- **Memory Manager (Pruning)**: コンテキストウィンドウを超えないよう、重要度の低い履歴を要約・削除し、常に最適なプロンプトサイズを維持します。
- **Working Memory**: 現在の作業ディレクトリや既知のファイル一覧を保持。

## 🛠️ 6. ツール統合

すべての機能（ファイル操作、計画管理、コマンド実行）は、`DuckAgent.register_tool` によって統一的に管理されます。これにより、将来的な機能拡張が容易になっています。
