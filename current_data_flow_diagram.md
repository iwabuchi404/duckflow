# 現在のDuckflowデータフロー図解

## 全体フロー概観

```
👤 ユーザー入力: "game_doc.mdを参照してプロジェクトの概要を把握してください"
    ↓
🧠 LLM ActionList生成
    ↓
🔄 ActionList実行ループ (4つのAction)
    ↓
📱 UI表示
```

## 詳細フロー分析

### Phase 1: ActionList生成
```
[ユーザー入力] → [LLMプロンプト構築] → [LLM API呼び出し] → [JSON解析]
                                                              ↓
生成されたActionList:
┌─────────────────────────────────────────────────────────────┐
│ 1. file_ops.analyze_file_structure                         │
│ 2. file_ops.search_content                                 │
│ 3. llm_service.synthesize_insights_from_files              │
│ 4. response.echo (テンプレート: {@act_000}, {@act_001}...) │
└─────────────────────────────────────────────────────────────┘
```

### Phase 2: Action実行ループ (複雑な部分)

```
┌─ Action 1: file_ops.analyze_file_structure ─┐
│                                              │
│ 1. ActionID生成: "act_000_file_ops_analyze_file_structure"
│    ↓                                         │
│ 2. 参照解決: なし (最初のAction)              │
│    ↓                                         │
│ 3. ツール実行: file_ops.analyze_file_structure("game_doc.md")
│    ├─ 実際のファイル読み込み・解析           │
│    ├─ 578行/12729文字の詳細データ生成        │
│    └─ 結果: 9091文字の辞書データ             │
│    ↓                                         │
│ 4. AgentState.add_action_result保存          │
│    └─ short_term_memory['action_results']に追加
│                                              │
└──────────────────────────────────────────────┘
                        ↓
┌─ Action 2: file_ops.search_content ─────────┐
│                                              │
│ 1. ActionID生成: "act_001_file_ops_search_content"
│    ↓                                         │
│ 2. 参照解決: なし                            │
│    ↓                                         │
│ 3. ツール実行: search_content("game_doc.md", "概要|プロジェクト")
│    ├─ フォールバック検索実行                 │
│    ├─ 2件マッチ発見                         │
│    └─ 結果: 563文字の辞書データ             │
│    ↓                                         │
│ 4. AgentState.add_action_result保存          │
│                                              │
└──────────────────────────────────────────────┘
                        ↓
┌─ Action 3: llm_service.synthesize_insights ─┐
│                                              │
│ 1. ActionID生成: "act_002_llm_service_synthesize_insights_from_files"
│    ↓                                         │
│ 2. 参照解決: なし                            │
│    ↓                                         │
│ 3. ツール実行: _synthesize_insights(...)     │
│    ├─ file_contents: {} (空辞書)            │
│    ├─ 条件判定: if not file_contents → True │
│    ├─ 結果: "分析対象のファイル内容が見つかりませんでした。"
│    └─ AgentState情報収集処理は実行されない   │
│    ↓                                         │
│ 4. AgentState.add_action_result保存          │
│                                              │
└──────────────────────────────────────────────┘
                        ↓
┌─ Action 4: response.echo (最も複雑) ─────────┐
│                                              │
│ 1. ActionID生成: "act_003_response_echo"     │
│    ↓                                         │
│ 2. 参照解決: _resolve_action_references      │
│    ┌─────────────────────────────────────────┐│
│    │ テンプレート文字列:                     ││
│    │ "📋 構造: {@act_000_file_ops_analyze_file_structure}
│    │  🔍 重要情報: {@act_001_file_ops_search_content}
│    │  🧠 分析結果: {@act_002_llm_service_synthesize_insights_from_files}"
│    │                                         ││
│    │ ↓ 正規表現パターンマッチング               ││
│    │                                         ││
│    │ {@act_000...} 検出:                     ││
│    │ ├─ AgentState.get_action_result_by_id() ││
│    │ ├─ 結果取得: 9091文字の辞書データ        ││
│    │ ├─ _apply_smart_content_proxy実行★      ││
│    │ │   ├─ _is_large_data_dict(9091文字) → True
│    │ │   └─ _summarize_file_structure_result() → コンパクト表示
│    │ └─ テンプレート変数置換                  ││
│    │                                         ││
│    │ {@act_001...} 検出:                     ││
│    │ ├─ AgentState.get_action_result_by_id() ││
│    │ ├─ 結果取得: 563文字の辞書データ         ││
│    │ ├─ _apply_smart_content_proxy実行★      ││
│    │ │   ├─ _is_large_data_dict(563文字) → False (2000文字未満)
│    │ │   ├─ 辞書データなので生表示             ││
│    │ │   └─ 問題: 読みにくい技術データ表示    ││
│    │ └─ テンプレート変数置換                  ││
│    │                                         ││
│    │ {@act_002...} 検出:                     ││
│    │ └─ 同様の処理...                        ││
│    └─────────────────────────────────────────┘│
│    ↓                                         │
│ 3. 最終メッセージ構築完了                    │
│    ↓                                         │
│ 4. _echo_response実行                        │
│    ├─ 大容量メッセージ検出 (1000文字超)       │
│    ├─ _apply_smart_content_proxy再実行★      │
│    │   └─ 既に処理済みなので変更なし         │
│    └─ UI表示: print(f"🦆 {result}")          │
│                                              │
└──────────────────────────────────────────────┘
```

## 問題点の可視化

### 🚨 スマートプロキシの多重適用
```
データ → [プロキシ1: 参照解決時] → [プロキシ2: echo時] → 表示
          ↑                      ↑
          9091文字辞書→要約        変更なし(処理済み)
          563文字辞書→生表示       変更なし
```

### 🔄 データ変換の複雑さ
```
生データ(file_ops) → AgentState保存 → ActionID参照 → プロキシ判定 → UI表示
     ↑                    ↑              ↑           ↑
   9091文字             辞書として      参照成功    条件分岐複雑
   563文字              保存           参照成功    閾値判定失敗
```

### ❌ 失敗ポイント
1. **563文字辞書**: `_is_large_data_dict(563) → False` なので生表示
2. **洞察合成**: `file_contents: {}` で条件分岐が誤判定
3. **情報統合**: 各Actionの結果が統合されない
