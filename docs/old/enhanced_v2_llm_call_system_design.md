# Enhanced v2.0 LLM呼び出しシステム設計書

## 概要

Enhanced v2.0システムにおけるLLM呼び出しの統一化と効率化を目的とした包括的な設計案です。Base/Main/Specializedの3層プロンプトシステムに加え、BaseSpecialized軽量パターンも含む柔軟なアーキテクチャを提案します。

## 現状分析

### 現在のLLM呼び出し状況

#### 1) EnhancedCompanionCore（主要なLLM呼び出し箇所）
- **応答生成**: `_generate_enhanced_response()` - system_prompt付き
- **ファイル名抽出**: `_extract_file_path_from_llm()` - 単独プロンプト
- **ファイル内容生成**: `_handle_file_write_operation()` - 単独プロンプト  
- **ファイル要約**: `_generate_file_summary()` - 単独プロンプト

#### 2) PlanTool
- **LLM呼び出しなし** - 現在はLLMを使わず、既存のActionSpecとファイル操作のみ

#### 3) その他のツール
- **ToolRouter**: LLM呼び出しなし（決まった操作のみ）
- **LLMCallManager**: 既存実装あり（Phase 2/3）
- **ConversationGate**: LLM呼び出しあり（承認判断）

### 問題点
1. **LLM呼び出しの散在**: EnhancedCompanionCore内で直接`llm_manager.generate`を呼び出し
2. **文脈注入の不統一**: 一部の呼び出しでsystem_promptを使用、他は単独プロンプト
3. **プロンプトパターンの未活用**: 既存の3層システム（Base/Main/Specialized）が活用されていない
4. **要約・抽出処理の非効率**: 軽量処理でも完全なコンテキストを注入している

## 設計目標

### 1) 統一化
- すべてのLLM呼び出しをLLMCallManager経由に統一
- 常時文脈注入（Base/Main/Specialized）の実現
- プロンプト生成の一元化

### 2) 効率化
- 用途に応じた3パターンのプロンプト選択
- BaseSpecialized軽量パターンによる高速処理
- トークン使用量の最適化

### 3) 保守性
- 責務の明確化と分離
- 設定の一元管理
- 監査・テレメトリの統一

## アーキテクチャ設計

### 1) 主要コンポーネント

#### IntentAnalyzerLLM（意図理解器）
- **目的**: ユーザー入力を解析し、上位意図とprompt_patternを決定
- **出力**: JSON形式でaction_type、prompt_pattern、tool_operations、file_target、confidence等
- **特徴**: ファイル名抽出機能を統合（_extract_file_path_from_llmを廃止）

#### PromptContextService（文脈合成サービス）
- **目的**: AgentStateからBase/Main/Specializedを合成してsystem_promptを作成
- **下位要素**: 
  - PromptContextBuilder（会話/固定5項目/短期記憶の集約）
  - PromptCompiler（テンプレート適用）
  - SpecializedPromptGenerator（PLANNING/EXECUTION/REVIEW用専門知識）
- **出力**: 統一されたsystem_prompt

#### PromptRouter（プロンプトパターン選択）
- **目的**: IntentAnalyzerLLMの出力に基づき、適切なプロンプトパターンを選択
- **選択ロジック**: タスクの複雑性・重要性に応じた3パターンの選択

#### LLMCallManager（LLM呼び出しの統一口）
- **目的**: すべてのLLM呼び出しを集約・標準化
- **機能**: system_prompt注入、スキーマ検証、再試行、ログ計測

#### FileOperationPlanner（ファイル操作計画）
- **目的**: 意図分析JSONからファイル操作を計画・承認フローを管理
- **機能**: 信頼度判定、候補提示、承認プロセス、安全性チェック

#### ApprovalManager（承認ゲート）
- **目的**: 書き込み/削除などの操作に対する承認フロー
- **統合**: 既存のConversationGate/simple_approvalを統合

#### ToolRouter（ツール実行ルーター）
- **目的**: 実ツール呼び出しの集約（現行実装を活用）
- **アダプター群**: FileOpsAdapter、PlanToolAdapter、CodeRunnerAdapter等

#### StateSync（状態同期）
- **目的**: 実行完了・エラーをAgentStateに記録・UI表示・StateMachine遷移

### 2) プロンプトパターンの3分類

```
BaseMainSpecialized（完全版）
├── Base: システム設定・制約・安全ルール
├── Main: 会話履歴・固定5項目・短期記憶
└── Specialized: PLANNING/EXECUTION/REVIEW用専門知識・手順書

BaseMain（標準版）
├── Base: システム設定・制約・安全ルール  
└── Main: 会話履歴・固定5項目・短期記憶

BaseSpecialized（軽量版）
├── Base: システム設定・制約・安全ルール
└── Specialized: 特定タスク用の専門知識・手順書
```

### 3) 各パターンの用途と選択基準

#### BaseMainSpecialized（完全版）
- **用途**: 複雑な計画立案、多段階タスク実行、レビュー・承認プロセス
- **選択条件**: `prompt_pattern = "base_main_specialized"`
- **適用例**: 
  - プロジェクト計画作成
  - コードリファクタリング計画
  - 複数ファイルの一括処理
  - リスク評価が必要な操作

#### BaseMain（標準版）  
- **用途**: 通常の対話応答、単純なファイル操作、基本的なタスク実行
- **選択条件**: `prompt_pattern = "base_main"`
- **適用例**: 
  - ファイル読み込み・要約
  - 単発の質問回答
  - 基本的なファイル作成
  - 一般的な対話処理

#### BaseSpecialized（軽量版）
- **用途**: 軽量な専門処理、高速な要約・抽出、単一機能に特化
- **選択条件**: `prompt_pattern = "base_specialized"`
- **適用例**: 
  - ファイル要約
  - コード要約
  - エラーメッセージ解析
  - 単純な抽出処理
  - 高速応答が必要な処理

## データ契約

### IntentAnalyzerLLM出力スキーマ

```json
{
  "action_type": "file_operation | plan_generation | direct_response | code_execution | summary_generation | content_extraction",
  "prompt_pattern": "base_main_specialized | base_main | base_specialized",
  "tool_operations": [
    {
      "operation": "read|write|create|delete|list|exists|summarize|extract|run",
      "args": {
        "file_target": "game_doc.md",
        "content": "...",
        "options": {...}
      }
    }
  ],
  "file_target": "game_doc.md",
  "require_approval": false,
  "confidence": 0.87,
  "reasoning": "ユーザーの要求と直近文脈に基づく判断。",
  "specialized_domain": "file_analysis | code_review | planning | execution | review"
}
```

### プロンプトパターン選択ロジック

```python
def select_prompt_pattern(action_type: str, complexity: str, confidence: float) -> str:
    """プロンプトパターンを選択"""
    
    # 高信頼度・軽量処理
    if confidence > 0.9 and complexity == "simple":
        return "base_specialized"
    
    # 複雑な計画・実行・レビュー
    if action_type in ["plan_generation", "code_execution"] or complexity == "complex":
        return "base_main_specialized"
    
    # 標準的な処理
    return "base_main"
```

## 実装フロー

### 1) メインチャットループの正しいLLM呼び出しフロー

```
1. 入力受付
   └── AgentState.add_message("user", user_input)

2. 意図理解（LLM）
   └── IntentAnalyzerLLM.analyze(user_input, agent_state, context=PromptContextService.build())
   └── 返却: { action_type, prompt_pattern, tool_operations[], file_target?, require_approval?, confidence, reasoning }

3. プロンプト生成（常時）
   └── system_prompt = PromptContextService.compose(Base/Main[/Specialized], by PromptRouter)
   └── 以降のLLM呼び出しはすべてLLMCallManager.call(user_input, system_prompt, mode=...)経由

4. 分岐実行
   ├── DIRECT_RESPONSE:
   │   └── LLMCallManager.call(..., mode="respond") → 応答を表示
   ├── PLAN_GENERATION:
   │   └── LLMCallManager.call(..., mode="plan") → 画面表示→承認→PlanToolAdapterで保存
   ├── FILE_OPERATION:
   │   └── plan = FileOperationPlanner.plan(intent_json, agent_state)
   │   └── plan.require_approval or low_confidence なら画面で確認→承認後ToolRouter実行
   │   ├── read: 読み込み→要約はLLMCallManager.call(content, system_prompt, mode="summarize")
   │   ├── write/create: LLMで内容生成→画面表示→承認→保存
   │   ├── delete: 常に承認→ToolRouter.delete
   │   └── list/exists: 直接ToolRouter実行（LLM不要）
   └── CODE_EXECUTION:
       └── 内容/引数/安全性の提示→承認→CodeRunnerAdapter実行

5. 結果反映
   └── AgentState.add_message("assistant", result)
   └── AgentState.last_task_resultにサマリ保存、UI表示、StateMachine遷移

6. フォールバック
   └── LLM失敗/低信頼→Clarifying Question→ユーザー回答を待つ
```

### 2) ツール呼び出しフロー（各ツールごと）

#### File: read
```
起点: 意図分析でoperation="read", file_targetとconfidence
フロー:
1. FileOperationPlanner: confidence < 閾値→候補提示or明確化質問
2. 承認不要（閲覧）: ToolRouter.read(file_path)
3. 要約が必要なら: LLMCallManager.call(mode="summarize", input=content, system_prompt=常時)
4. UI表示→AgentState更新
```

#### File: write/create
```
起点: operation in {write, create}
フロー:
1. 文脈注入でLLMが内容生成（mode="generate_content"）
2. 生成内容を画面で提示→承認→ToolRouter.write/create
3. 上書き/拡張子/サイズ/作業外PATHはToolRouter安全チェック（承認orブロック）
4. UI表示→AgentState更新
```

#### File: delete
```
常に承認必須→承認後ToolRouter.delete
```

#### File: list/exists
```
LLM不要→ToolRouter.list/exists→UI表示
```

#### PlanTool
```
起点: PLAN_GENERATION or FILE_OPERATIONで「計画化」示唆
フロー:
1. LLMCallManager.call(mode="plan")→画面提示→承認
2. PlanToolAdapter.propose(...), set_action_specs(...), request_approval(...)
3. 保存結果をUI/AgentStateへ
```

#### CodeRunner
```
起点: CODE_EXECUTION
フロー:
1. 実行計画をLLMで整形（入出力/副作用/制限）→提示→承認→実行
2. 標準出力/エラーを要約（LLM）→UI表示→AgentState更新
```

#### 新規要約ツール（ConversationSummaryTool）
```
起点: 会話履歴の要約要求
フロー:
1. 意図分析: prompt_pattern="base_specialized"（軽量版）
2. プロンプト生成: Base + Specialized（SUMMARY用）
3. LLM呼び出し: LLMCallManager.call(mode="conversation_summarize", pattern="base_specialized")
4. 軽量要約: 会話履歴の簡潔な要約生成
```

#### 新規抽出ツール（ContentExtractionTool）
```
起点: コンテンツからの抽出要求
フロー:
1. 意図分析: prompt_pattern="base_specialized"（軽量版）
2. プロンプト生成: Base + Specialized（EXTRACTION用）
3. LLM呼び出し: LLMCallManager.call(mode="extract", pattern="base_specialized")
4. 軽量抽出: キーワード・構造・メタデータの高速抽出
```

## 実装詳細

### 1) PromptContextServiceの実装（3パターン対応）

```python
class PromptContextService:
    def compose(self, pattern: str, agent_state: AgentState) -> str:
        """3パターンのプロンプトを合成"""
        base = self._build_base_context()
        
        if pattern == "base_specialized":
            # 軽量版: Base + Specializedのみ
            specialized = self._build_specialized_context(agent_state)
            return f"{base}\n\n{specialized}"
            
        elif pattern == "base_main":
            # 標準版: Base + Main
            main = self._build_main_context(agent_state)
            return f"{base}\n\n{main}"
            
        elif pattern == "base_main_specialized":
            # 完全版: Base + Main + Specialized
            main = self._build_main_context(agent_state)
            specialized = self._build_specialized_context(agent_state)
            return f"{base}\n\n{main}\n\n{specialized}"
            
        else:
            # デフォルト: Base + Main
            main = self._build_main_context(agent_state)
            return f"{base}\n\n{main}"
    
    def _build_specialized_context(self, agent_state: AgentState) -> str:
        """Specializedコンテキスト（軽量版用）"""
        # 現在のStep/Statusに応じた専門知識・手順書
        step = agent_state.current_step
        if step == Step.EXECUTION:
            return self._get_execution_guidelines()
        elif step == Step.REVIEW:
            return self._get_review_guidelines()
        else:
            return self._get_general_guidelines()
```

### 2) LLMCallManagerの統一呼び出し

```python
class LLMCallManager:
    async def call(self, mode: str, input_text: str, system_prompt: str, 
                   pattern: str = "base_main", **kwargs) -> str:
        """統一されたLLM呼び出し"""
        
        # プロンプト合成
        full_prompt = self._compose_prompt(mode, input_text, system_prompt, pattern)
        
        # LLM呼び出し
        response = await self._call_llm(full_prompt, mode, **kwargs)
        
        # 結果検証・後処理
        processed_response = self._post_process(response, mode)
        
        # ログ記録
        self._log_call(mode, pattern, len(full_prompt), len(response))
        
        return processed_response
    
    def _compose_prompt(self, mode: str, input_text: str, system_prompt: str, pattern: str) -> str:
        """モード別プロンプト合成"""
        if mode == "summarize":
            return f"{system_prompt}\n\n以下の内容を要約してください:\n{input_text}"
        elif mode == "extract":
            return f"{system_prompt}\n\n以下の内容から指定された情報を抽出してください:\n{input_text}"
        elif mode == "generate_content":
            return f"{system_prompt}\n\n以下の要求に基づいて内容を生成してください:\n{input_text}"
        else:
            return f"{system_prompt}\n\n{input_text}"
```

### 3) 軽量パターンの利点と適用場面

#### BaseSpecialized（軽量版）の利点
- **高速性**: Main（会話履歴）を省略することでトークン削減・応答速度向上
- **特化性**: 特定タスクに特化した専門知識のみ注入
- **コスト効率**: 不要なコンテキストを排除してLLM APIコスト削減

#### 適用場面
- **ファイル要約**: 内容のみに特化、会話履歴は不要
- **コード解析**: コード構造・品質チェックに特化
- **エラー解析**: エラーメッセージ・ログ解析に特化
- **単純抽出**: キーワード・パターン抽出に特化

## 実装優先順位

### Phase 1: 基盤整備（1-2週間）
1. **PromptContextService**（3パターン対応）
   - Base/Main/Specializedの合成ロジック
   - パターン選択アルゴリズム
   - トークン制限管理

2. **IntentAnalyzerLLM**（prompt_pattern出力）
   - 既存のintent_understanding/llm_intent_analyzer.pyを拡張
   - ファイル名抽出機能の統合
   - 信頼度判定ロジック

3. **LLMCallManager**（統一呼び出し）
   - 既存実装の拡張
   - system_prompt注入の標準化
   - モード別プロンプト合成

### Phase 2: ツール統合（2-3週間）
1. **EnhancedCompanionCore**（要約・抽出・内容生成）
   - 直接LLM呼び出しをLLMCallManager経由に変更
   - プロンプトパターンの適用
   - エラーハンドリングの統一

2. **PlanTool**（計画立案）
   - LLM呼び出しの追加
   - BaseMainSpecializedパターンの適用
   - 計画生成の品質向上

3. **新規要約ツール**（ConversationSummaryTool）
   - BaseSpecialized軽量パターンの実装
   - 会話履歴要約の高速化

### Phase 3: 最適化（1-2週間）
1. **パターン選択ロジック**の最適化
   - 信頼度・複雑性に基づく自動選択
   - パフォーマンス測定・調整

2. **トークン使用量**の監視・制御
   - 使用量の可視化
   - 制限値の設定・管理

3. **パフォーマンス測定・改善**
   - 応答時間の測定
   - キャッシュ戦略の実装

## 移行戦略

### 1) 段階的移行
- **Phase 1**: 基盤コンポーネントの実装・テスト
- **Phase 2**: 既存ツールの段階的移行
- **Phase 3**: 新規ツールの追加・最適化

### 2) 後方互換性
- 既存のLLM呼び出しは動作継続
- 新しいパターンは段階的に適用
- 設定による有効/無効切り替え

### 3) テスト戦略
- 単体テスト: 各コンポーネントの動作確認
- 統合テスト: ツール間の連携確認
- パフォーマンステスト: 応答時間・トークン使用量の測定

## 監査・テレメトリ

### 1) 統一ログ
- すべてのLLM呼び出しでtiming/token/失敗率/再試行を記録
- プロンプトパターンの使用統計
- ツール別の実行統計

### 2) パフォーマンス監視
- 応答時間の測定・可視化
- トークン使用量の追跡
- エラー率・成功率の監視

### 3) コスト管理
- LLM API使用量の追跡
- パターン別のコスト分析
- 最適化提案の自動生成

## リスクと対策

### 1) 技術的リスク
- **LLM API制限**: レート制限・トークン制限への対応
- **応答品質**: 軽量パターンでの品質低下リスク
- **依存関係**: 外部APIへの依存リスク

### 2) 対策
- **フォールバック**: 軽量パターン失敗時の標準パターンへの切り替え
- **品質監視**: 応答品質の自動評価・フィードバック
- **冗長性**: 複数LLMプロバイダーのサポート

### 3) 運用リスク
- **設定ミス**: プロンプトパターンの誤設定
- **パフォーマンス劣化**: 過度なコンテキスト注入
- **コスト増大**: 非効率なプロンプトパターンの使用

### 4) 対策
- **設定検証**: プロンプトパターンの自動検証
- **パフォーマンス監視**: 定期的な性能測定・警告
- **コスト監視**: 予算制限・アラート設定

## 結論

この設計により、Enhanced v2.0システムにおけるLLM呼び出しの統一化と効率化を実現できます。3パターンのプロンプトシステムにより、用途に応じた最適なコンテキスト注入が可能になり、BaseSpecialized軽量パターンにより高速処理とコスト効率の両立を図れます。

実装は段階的に進め、既存システムへの影響を最小限に抑えながら、新しいアーキテクチャへの移行を完了させることができます。
