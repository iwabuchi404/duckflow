# Duckflow v3 プロンプトシステム設計ドキュメント

## 1. 設計の目的と背景

### 1.1 設計の目的
Duckflow v3のプロンプトシステムは、AIアシスタントが会話の文脈を一貫して理解し、適切な判断と操作を実行できるようにすることを目的としています。従来のシステムで発生していた「文脈の断絶」「突然のファイル操作」「承認プロセスの分離」などの問題を解決し、自然で安全な対話体験を提供します。

### 1.2 背景と課題
- **文脈の断絶**: 各LLM呼び出しで会話履歴が失われ、一貫性が保たれない
- **操作の透明性不足**: なぜその操作を行うのかが不明確
- **承認プロセスの不自然さ**: 承認が会話フローから分離され、ユーザビリティが低下
- **状態管理の複雑性**: ステップとステータスが混在し、管理が困難

### 1.3 解決すべき問題
1. 会話の文脈を継続的に維持する
2. 操作の理由を常に明確にする
3. 承認プロセスを自然な会話フローに統合する
4. 状態管理を明確に分離し、制御可能にする

## 2. 設計思想とアーキテクチャ

### 2.1 設計思想
- **文脈の一貫性**: すべてのLLM呼び出しで会話履歴を共有し、文脈の継続性を保証
- **理由の必須化**: 各操作に必ず理由（rationale）を付与し、透明性を確保
- **軽量な制御**: 必要最小限のルールで制御し、過度に複雑にしない
- **段階的処理**: 軽い処理は軽く、重い処理は段階を踏んで実行
- **最小限から開始**: 基本機能を確実に動作させてから段階的に拡張

### 2.2 アーキテクチャの全体像
```
┌───────────┐      ┌─────────────────┐      ┌──────────────────┐
│  User      │ ──▶ │ Conversation Core│ ──▶ │ Context Assembler │
└───────────┘      └─────────────────┘      └───────┬──────────┘
                                                     │  AgentState（読取）
                                                     ▼
                                            ┌──────────────────┐
                                            │  LLM Main Call   │  ← Base + Main
                                            │  （司令塔）       │
                                            └───────┬──────────┘
                                                    │ JSON 出力
                                                    │ { rationale,
                                                    │   goal_consistency,
                                                    │   constraint_check,
                                                    │   next_step,
                                                    │   step, state_delta }
                                                    ▼
                                  ┌──────────────────────────────┐
                                  │ LLM-Driven Action Dispatch   │
                                  │ （次の行動の振り分け）        │
                                  └──────┬───────────────┬───────┘
                                         │               │
                                         │               │必要時のみ
                                （会話で完結）             ▼
                                         │      ┌──────────────────┐
                                         │      │ Specialized LLM  │  ← Base + 専用
                                         │      │ （PLANNING/EXEC/ │
                                         │      │   REVIEW 用）     │
                                         │      └─────────┬────────┘
                                         │                │
                                         │                ▼
                                         │      ┌──────────────────┐
                                         │      │   Tool Router    │
                                         │      │  list/read/write │
                                         │      └───────┬──────────┘
                                         │              │
                                         │         （書込前は Gate）
                                         │              │
                                         │              ▼
                                         │      ┌──────────────────┐
                                         │      │      Tools       │
                                         │      └───────┬──────────┘
                                         │              │ 実行結果
                                         ▼              ▼
                                ┌─────────────────┐  ┌─────────────────┐
                                │  AgentState 更新 │  │  Audit Log 追加 │
                                └────────┬────────┘  └────────┬────────┘
                                         │                      │
                                         └───────────┬──────────┘
                                                     ▼
                                           ┌─────────────────┐
                                           │ Conversation Core│（応答）
                                           └─────────────────┘
```

## 3. プロンプトシステムの3層構造

### 3.1 Base Prompt（人格・憲法）
**役割**: エージェントの長期的な記憶や人格の核となるプロンプト

**実装要件**:
- **必須フィールド**: エージェントの基本人格、行動原則、安全原則、制約
- **長期的記憶**: 重要な経験（成功・失敗）、学習したパターン、ユーザー設定
- **セッション情報**: セッションID、総会話数、最後の更新時刻
- **会話履歴**: 最新5件の会話要約（各100文字以内）

**具体的な内容例**:
```
あなたはDuckflowのAIアシスタントです。

基本人格:
- 安全第一、正確性重視、継続性を大切にする
- ユーザーの学習レベルに合わせた説明を行う
- エラーが発生した場合は適切に説明し、解決策を提案する

長期的記憶:
- 作成したファイル数: {total_files}
- 成功した操作数: {successful_operations}
- 学習したパターン: {learned_patterns}

現在のセッション:
- セッションID: {session_id}
- 総会話数: {total_conversations}
- 最後の更新: {last_updated}

会話履歴（最新5件）:
{recent_conversation_summary}
```

**実装時の注意点**:
- 文章は短く固定し、一貫性を保つ（最大1000文字）
- 動的データは{placeholder}形式で挿入
- すべてのLLM呼び出しに必ず含める
- エージェントの「憲法」として機能し、変更は最小限に

### 3.2 Main Prompt（司令塔）
**役割**: 現在の対話に集中するためのワーキングメモリ（短期記憶）

**実装要件**:
- **現在の状況**: ステップ、ステータス、進行中のタスク
- **短期記憶**: 直近3件の会話（ユーザー入力と応答）
- **固定5項目**: goal, why_now, constraints, plan_brief, open_questions
- **出力指示**: 期待するJSONフォーマットの明記

**具体的な内容例**:
```
# 現在の対話状況（ワーキングメモリ）

現在のステップ: {current_step}
現在のステータス: {current_status}
進行中のタスク: {ongoing_task}

# 固定5項目（文脈の核）
目標: {goal}
なぜ今やるのか: {why_now}
制約: {constraints}
直近の計画: {plan_brief}
未解決の問い: {open_questions}

# 直近の会話の流れ（短期記憶）
{recent_conversation_flow}

# 次のステップの指示
必ず以下のJSON形式で出力してください:
{
  "rationale": "操作の理由（1行）",
  "goal_consistency": "目標との整合性（yes/no + 理由）",
  "constraint_check": "制約チェック（yes/no + 理由）",
  "next_step": "次のステップ（done/pending_user/defer/continue）",
  "step": "ステップ（PLANNING/EXECUTION/REVIEW/AWAITING_APPROVAL）",
  "state_delta": "状態変化（あれば）"
}
```

**実装時の注意点**:
- 固定5項目は常に最新の状態を反映
- 短期記憶は最大3件、各100文字以内
- JSONフォーマットは厳密に指定
- 現在の状況はリアルタイムで更新

### 3.3 Specialized Prompt（手順書）
**役割**: 特定の作業に特化した「専門知識」や「手順書」

**実装要件**:
- **PLANNING用**: 計画作成の手順、品質基準、出力形式
- **EXECUTION用**: 実行の手順、安全性チェック、進捗管理
- **REVIEW用**: レビューの観点、評価基準、改善提案
- **AgentState参照**: 必要な情報のみを抽出（ファイル名、制約など）

**具体的な内容例**:

#### PLANNING用
```
# 計画作成の専門知識・手順書

## 計画作成の手順
1. 要求の分析と分解（最大3つのステップ）
2. 必要なリソースの特定
3. リスク評価（低/中/高）
4. 成功基準の設定（具体的で測定可能）

## 出力形式
```
プラン名: [プランの名称]
目的: [達成したいこと]
ステップ:
  1. [ステップ1の詳細]
  2. [ステップ2の詳細]
  3. [ステップ3の詳細]
リスク: [想定されるリスク]
成功基準: [成功の判断基準]
```

## 品質基準
- 各ステップは具体的で実行可能
- リスクは適切に評価されている
- 成功基準は測定可能
```

#### EXECUTION用
```
# 実行の専門知識・手順書

## 実行の手順
1. 計画の確認と準備
2. 安全性チェック（ファイル操作、システム影響）
3. 段階的な実行と進捗確認
4. エラーハンドリングと復旧

## 安全性チェック項目
- ファイル操作の安全性（パス、権限、バックアップ）
- システムへの影響（リソース、依存関係）
- データの整合性（入力値、出力値）

## 進捗管理
- 各ステップの完了確認
- エラー発生時の適切な処理
- ユーザーへの進捗報告
```

#### REVIEW用
```
# レビューの専門知識・手順書

## レビューの観点
1. 内容の正確性（仕様との一致）
2. 安全性（リスクの評価）
3. 品質（パフォーマンス、保守性）
4. 改善点（効率化、最適化）

## 評価基準
- 良い: 仕様を満たし、安全で高品質
- 普通: 基本的な要求は満たしている
- 要改善: 問題があり、修正が必要

## 出力形式
- 評価: [良い/普通/要改善]
- 問題点: [発見された問題]
- 改善提案: [具体的な改善案]
- 承認可否: [承認/要修正/拒否]
```

**実装時の注意点**:
- 各専門分野に特化した具体的な手順
- 出力形式は統一し、一貫性を保つ
- AgentStateから必要な情報のみを参照
- 品質基準は明確で測定可能

## 4. 状態管理システム

### 4.1 Step（行動の種類）
エージェントが今、何をしているかという「行動」を表します。

**実装定義**:
```python
class Step(Enum):
    PLANNING = "PLANNING"                    # 計画作成
    EXECUTION = "EXECUTION"                  # 実行（ツール使用）
    REVIEW = "REVIEW"                        # レビュー（結果確認）
    AWAITING_APPROVAL = "AWAITING_APPROVAL"  # 承認待ち
```

**各ステップの詳細**:
- **PLANNING**: ユーザーの要求を分析し、実行計画を作成する
- **EXECUTION**: 作成された計画に基づいて、実際の操作を実行する
- **REVIEW**: 実行結果を評価し、品質と安全性を確認する
- **AWAITING_APPROVAL**: 高リスクな操作の承認をユーザーに求める

**実装時の注意点**:
- ステップは処理の進行を表し、完了時に更新
- 各ステップは明確に定義され、重複や曖昧さがない
- ステップの変更は許可遷移表に従って制御

### 4.2 Status（結果や状態）
その行動の結果や状態を表します。

**実装定義**:
```python
class Status(Enum):
    IN_PROGRESS = "IN_PROGRESS"              # 処理中
    SUCCESS = "SUCCESS"                      # 成功
    ERROR = "ERROR"                          # 失敗
    REQUIRES_USER_INPUT = "REQUIRES_USER_INPUT"  # ユーザー入力待ち
```

**各ステータスの詳細**:
- **IN_PROGRESS**: 処理が進行中で、完了していない
- **SUCCESS**: 処理が正常に完了し、期待される結果が得られた
- **ERROR**: 処理中にエラーが発生し、期待される結果が得られなかった
- **REQUIRES_USER_INPUT**: 処理を続行するためにユーザーの入力が必要

**実装時の注意点**:
- ステータスは処理の結果を表し、継続的に更新可能
- エラー状態からは適切な復旧処理が必要
- ユーザー入力待ち状態では、明確な指示を提供

### 4.3 状態の分離の理由
**設計上の理由**:
- **関心の分離**: ステップは処理の進行、ステータスは会話の状況
- **更新頻度の違い**: ステップは処理完了時、ステータスは継続的に
- **責任の明確化**: それぞれが独立した責任を持つ

**実装上の利点**:
- 状態の管理が明確で、デバッグが容易
- 各状態の更新タイミングが明確
- 状態の組み合わせによる複雑な状況の表現が可能

**状態の組み合わせ例**:
- `PLANNING + IN_PROGRESS`: 計画作成中
- `EXECUTION + SUCCESS`: 実行完了
- `REVIEW + ERROR`: レビューでエラー発生
- `AWAITING_APPROVAL + REQUIRES_USER_INPUT`: 承認待ちでユーザー入力必要

### 4.4. Dual Loopアーキテクチャにおける状態同期

#### 4.4.1. 課題: 状態の分断
本システムは、ユーザーとの対話を担う`ChatLoop`と、時間のかかる処理を担う`TaskLoop`からなる非同期のDual Loopアーキテクチャを採用している。この設計により、重いタスクの実行中もユーザーは対話を続けることができる。

しかし、実装の過程で、それぞれのループが独自のタイミングで状態を更新しようとすることにより、**状態の同期不全**が発生するという問題が明らかになった。

具体的には、`TaskLoop`がタスクを完了し、`StateMachine`の状態を`COMPLETED`に更新しても、その変更がユーザーの次の入力を待っている`ChatLoop`側の`AgentState`に即座に伝わらない。結果として、`ChatLoop`は古い状態（例: `IDLE`）を基に行動を開始してしまい、不正な状態遷移エラーや文脈の喪失を引き起こしていた。

#### 4.4.2. 解決策: 状態の一元管理とコールバックによる同期
この問題を解決するため、状態管理を以下の原則に基づいて修正する。

1.  **状態所有者の一元化**: `AgentState`と`StateMachine`のインスタンスは、親である`EnhancedDualLoopSystem`が唯一の所有者（Single Source of Truth）となる。
2.  **ループからの参照**: `ChatLoop`と`TaskLoop`は状態を自身で保持せず、常に親システムのインスタンス（`self.dual_loop_system.state_machine`など）を参照する。
3.  **コールバックによる同期**: `StateMachine`の状態が変更されるたびに、コールバック関数が自動的に呼び出される。このコールバックは`EnhancedDualLoopSystem`内に実装され、`StateMachine`の最新の状態を即座に中央の`AgentState`に書き戻す責務を負う。

これにより、システムのどの部分から状態を参照しても、常に最新かつ一貫した状態が保証される。

#### 4.4.3. 実装イメージ
```python
class EnhancedDualLoopSystem:
    def __init__(self):
        # ...
        self.state_machine = StateMachine()
        self.enhanced_companion = EnhancedCompanionCore() # AgentStateを保持

        # コールバックを登録して、StateMachineの変更をAgentStateに同期
        self.state_machine.add_state_change_callback(self._sync_state_to_agent_state)

    def _sync_state_to_agent_state(self, new_step: Step, new_status: Status, trigger: str):
        """StateMachineの変更をAgentStateに書き戻す"""
        self.logger.debug(f"State Sync Fired: {new_step.value}.{new_status.value}")
        self.enhanced_companion.state.step = new_step
        self.enhanced_companion.state.status = new_status
```

## 5. AgentStateの固定5項目

### 5.1 固定5項目の目的
文脈の一貫性を保つため、常に以下の5項目を維持します。

**実装定義**:
```python
class AgentState:
    # 固定5項目（文脈の核）
    goal: str                    # 目的（1行、最大200文字）
    why_now: str                # なぜ今やるのか（1行、最大200文字）
    constraints: List[str]       # 制約（最大2個、各100文字以内）
    plan_brief: List[str]       # 直近の短い計画（最大3手、各100文字以内）
    open_questions: List[str]   # 未解決の問い（最大2個、各100文字以内）
    
    # 追加フィールド
    context_refs: List[str]     # 関連ファイルや会話番号の参照
    decision_log: List[str]     # 採択済みの方針（1行ずつ、各100文字以内）
    pending_gate: bool          # 承認待ちの有無
    last_delta: str             # 直近の変更の要約（1行、最大200文字）
```

### 5.2 固定5項目の詳細仕様

#### goal（目的）
- **形式**: 1行の文字列
- **内容**: 現在の会話やタスクの目的を明確に表現
- **例**: "ユーザーのファイル操作要求を安全に実行する"
- **制約**: 最大200文字、具体的で測定可能

#### why_now（なぜ今やるのか）
- **形式**: 1行の文字列
- **内容**: 現在のタイミングでこの操作を行う理由
- **例**: "ユーザーが即座にファイル作成を要求しているため"
- **制約**: 最大200文字、時機の妥当性を説明

#### constraints（制約）
- **形式**: 最大2個の文字列リスト
- **内容**: 操作を実行する際の制限や条件
- **例**: ["システムファイルは変更しない", "ファイルサイズは1MB以下"]
- **制約**: 各100文字以内、具体的で検証可能

#### plan_brief（直近の短い計画）
- **形式**: 最大3手の文字列リスト
- **内容**: 現在実行中の計画の概要
- **例**: ["ファイル名を抽出", "内容を生成", "ファイルを作成"]
- **制約**: 各100文字以内、実行可能で順序が明確

#### open_questions（未解決の問い）
- **形式**: 最大2個の文字列リスト
- **内容**: 解決が必要な質問や不明点
- **例**: ["ファイルの拡張子は何にするか", "内容の詳細レベルはどの程度か"]
- **制約**: 各100文字以内、具体的で回答可能

### 5.3 固定5項目の利点
- **文脈の安定性**: 常に同じ項目で文脈を管理
- **一貫性の保証**: 会話の流れが途切れない
- **透明性の向上**: 現在の状況が常に明確
- **実装の一貫性**: 開発者が常に同じ構造でアクセス

### 5.4 追加フィールドの詳細

#### context_refs（関連参照）
- **用途**: 関連ファイルや会話番号への参照
- **形式**: 文字列リスト
- **例**: ["file:config.json", "conversation:15", "plan:20250101_001"]

#### decision_log（決定ログ）
- **用途**: 採択済みの方針の記録
- **形式**: 文字列リスト（時系列順）
- **例**: ["ファイル作成を承認", "Pythonファイルとして作成", "バックアップを作成"]

#### pending_gate（承認待ち）
- **用途**: 承認待ちの状態管理
- **形式**: ブール値
- **動作**: Trueの場合は承認プロセスを開始

#### last_delta（最後の変更）
- **用途**: 直近の状態変化の要約
- **形式**: 1行の文字列
- **例**: "ステップをPLANNINGからEXECUTIONに変更"

### 5.5 実装時の注意点
- **文字数制限**: 各フィールドの文字数制限を厳密に守る
- **更新タイミング**: 状態変化時に適切なタイミングで更新
- **整合性チェック**: 5項目間の整合性を定期的にチェック
- **永続化**: セッション終了時に状態を保存、次回セッションで復元

## 6. 許可遷移表による制御

### 6.1 遷移制御の目的
遷移の暴走を防ぎ、1発話あたり遷移は最大1回にします。

**制御の必要性**:
- **無限ループの防止**: 同じ状態間を無限に遷移することを防ぐ
- **状態の一貫性**: 論理的に不可能な状態遷移を防ぐ
- **パフォーマンスの向上**: 不要な状態変更による処理の重複を防ぐ

### 6.2 許可遷移表

**遷移表の定義**:
| From Step | To Step | 条件 | 理由 |
|-----------|---------|------|------|
| PLANNING | EXECUTION | 計画が完了 | 計画に基づいて実行開始 |
| PLANNING | REVIEW | 計画の検証が必要 | 計画の品質確認 |
| PLANNING | AWAITING_APPROVAL | 高リスクな計画 | ユーザーの承認が必要 |
| EXECUTION | REVIEW | 実行完了 | 結果の評価が必要 |
| EXECUTION | AWAITING_APPROVAL | 高リスクな操作 | ユーザーの承認が必要 |
| EXECUTION | PLANNING | エラー発生 | エラーからの復旧 |
| REVIEW | EXECUTION | 修正が必要 | 修正後の再実行 |
| REVIEW | AWAITING_APPROVAL | 承認が必要 | 結果の承認 |
| REVIEW | DONE | 完了 | タスク完了 |
| AWAITING_APPROVAL | EXECUTION | 承認済み | 承認後の実行 |
| AWAITING_APPROVAL | PLANNING | 承認拒否 | 計画の見直し |

**実装定義**:
```python
class TransitionController:
    def __init__(self):
        self.allowed_transitions = {
            Step.PLANNING: [
                Step.EXECUTION,
                Step.REVIEW,
                Step.AWAITING_APPROVAL
            ],
            Step.EXECUTION: [
                Step.REVIEW,
                Step.AWAITING_APPROVAL
            ],
            Step.REVIEW: [
                Step.EXECUTION,
                Step.AWAITING_APPROVAL,
                "DONE"
            ],
            Step.AWAITING_APPROVAL: [
                Step.EXECUTION,
                Step.PLANNING
            ]
        }
        
        # エラー時の特別遷移
        self.error_transitions = {
            Step.EXECUTION: Step.PLANNING,  # 実行エラー時は計画に戻る
            Step.REVIEW: Step.PLANNING      # レビューエラー時は計画に戻る
        }
    
    def is_transition_allowed(self, from_step: Step, to_step: Step) -> bool:
        """遷移が許可されているかをチェック"""
        if from_step not in self.allowed_transitions:
            return False
        
        return to_step in self.allowed_transitions[from_step]
    
    def get_error_recovery_step(self, current_step: Step) -> Step:
        """エラー時の復旧ステップを取得"""
        return self.error_transitions.get(current_step, Step.PLANNING)
```

### 6.3 遷移制御の特徴

#### 1発話あたり最大1回の制限
**実装要件**:
```python
class TransitionLimiter:
    def __init__(self):
        self.last_transition_time = None
        self.transition_count = 0
        self.max_transitions_per_utterance = 1
        self.reset_interval = 60  # 60秒でリセット
    
    def can_transition(self) -> bool:
        """遷移が可能かチェック"""
        current_time = datetime.now()
        
        # 時間リセットチェック
        if (self.last_transition_time and 
            (current_time - self.last_transition_time).seconds > self.reset_interval):
            self.transition_count = 0
        
        return self.transition_count < self.max_transitions_per_utterance
    
    def record_transition(self):
        """遷移を記録"""
        self.transition_count += 1
        self.last_transition_time = datetime.now()
```

#### 許可された遷移のみ
**実装要件**:
- 遷移表に定義されていない遷移は拒否
- 不正な遷移試行時はログに記録
- エラー状態からの復旧は特別ルールで処理

#### エラー時の復旧
**実装要件**:
- EXECUTIONでERRORのとき、自動的にPLANNINGに戻る
- エラーの詳細をログに記録
- 復旧後の再試行回数を制限

### 6.4 実装時の注意点

**遷移制御の実装**:
- 遷移表は設定ファイルで管理し、変更可能にする
- 遷移の履歴を記録し、デバッグに活用する
- 不正な遷移試行時は適切なエラーメッセージを表示する

**パフォーマンスの考慮**:
- 遷移チェックは軽量な処理にする
- 遷移履歴は適切なサイズで制限する
- 頻繁な遷移チェックによるオーバーヘッドを最小化する

**エラーハンドリング**:
- 予期しない状態遷移時の適切な処理
- 復旧不可能な状態からの脱出方法
- ユーザーへの適切なフィードバック

## 7. LLM出力フォーマットの統一

### 7.1 Main LLMの出力フォーマット
```json
{
  "rationale": "操作の理由（1行）",
  "goal_consistency": "目標との整合性（yes/no + 理由）",
  "constraint_check": "制約チェック（yes/no + 理由）",
  "next_step": "次のステップ（done/pending_user/defer/continue）",
  "step": "ステップ（PLANNING/EXECUTION/REVIEW/AWAITING_APPROVAL）",
  "prompt_pattern": "次に使用すべきプロンプトのパターン（base_main / base_main_specialized）",
  "state_delta": "状態変化（あれば）"
}
```

### 7.2 出力フォーマットの特徴
- **理由の必須化**: rationaleフィールドで操作の理由を明確化
- **整合性チェック**: goal_consistencyとconstraint_checkで暴走を防止
- **状態変化の追跡**: state_deltaで状態の変化を記録

### 7.3 実装時の注意点
- **JSONスキーマの厳格化**: 必須フィールドの検証
- **バリデーション**: 出力形式の整合性チェック
- **エラー時の復旧**: JSON解析失敗時の適切な処理

## 8. 会話内Gate（承認システム）

### 8.1 Gateの目的
承認プロセスを会話フローに自然に統合し、ユーザビリティを向上させます。

### 8.2 Gateの特徴
- **会話内での承認**: 別フローではなく、自然な会話の中で承認
- **5点の情報提供**: 意図、根拠、影響、代替、差分プレビュー
- **定型化された承認**: 一貫性のある承認プロセス

### 8.3 Gateが必要な場合
- 高リスクな操作（ファイル削除、システムファイル変更）
- 大量データの処理
- 機密情報の取り扱い
- 影響範囲が大きい操作

### 8.4 実装時の注意点
- **初期段階**: 作業フォルダ外の操作のみ保護
- **段階的拡張**: 安全性が確認できてから本格実装
- **ユーザビリティ**: 承認プロセスが自然な会話フローを妨げない

### 8.5 段階的な実装アプローチ
**Phase 1**: 作業フォルダ外の基本保護のみ
```python
class SimpleFileProtector:
    def __init__(self):
        self.work_dir = "./work"  # 作業フォルダ
    
    def is_safe_path(self, file_path: str) -> bool:
        # 作業フォルダ内のみ許可
        return file_path.startswith(self.work_dir)
    
    def check_operation(self, operation: str, file_path: str) -> bool:
        if not self.is_safe_path(file_path):
            return False  # 作業フォルダ外は拒否
        return True  # 作業フォルダ内は許可
```

**Phase 3**: 簡単な承認プロセス
```python
class BasicConversationGate:
    def __init__(self):
        self.file_protector = SimpleFileProtector()
    
    def is_gate_required(self, operation: str, file_path: str) -> bool:
        # 作業フォルダ外の操作のみGateが必要
        return not self.file_protector.is_safe_path(file_path)
    
    def generate_gate_message(self, operation: str, file_path: str) -> str:
        return f"""
        以下の操作の承認が必要です：
        操作: {operation}
        対象: {file_path}
        理由: 作業フォルダ外のファイルを操作しようとしています
        
        承認しますか？ (yes/no)
        """
```

**Phase 4**: 本格的なGateシステム
- 5点の情報提供（意図、根拠、影響、代替、差分プレビュー）
- リスクレベルの自動判定
- 承認履歴の記録と分析

## 9. Dialog Policy（最小ルール）

### 9.1 最小ルールの目的
必要最小限のルールで制御し、過度に複雑にしない。

### 9.2 主要ルール
- **Clarify**: 自信が低い、または影響が大きいときだけ、質問は最大1つ
- **Propose**: 現実的な案が2つ以上のときだけ、A/Bを提示
- **Gate**: 書き込み、削除、実行の前は必ず同意を取る
- **Summarize → Next**: 返答が長いときだけ、最後に短い要約と次の一手
- **Nudge**: ユーザーが明確に困っていると書いたときだけ、末尾に1行の最初の一歩

### 9.3 ルールの特徴
- **最小限**: 必要最小限のルールのみ
- **自然性**: 自然な会話フローを妨げない
- **一貫性**: 一貫した動作を保証

## 10. LLMによる動的なプロンプト選択

### 10.1 設計思想の進化
当初、プロンプトの呼び分けは、キーワードや現在のステップに基づくルールベースの「PromptRouter」で行うことを想定していました。しかし、この方法では「実装プランを提案して」のような、キーワードだけでは複雑さが判断しにくい曖昧な指示に対応できないという課題が明らかになりました。

そこで、システムの「賢さ」と「効率」を両立させるため、より洗練された以下の方式を採用します。

### 10.2 新しいアーキテクチャ：要求理解と統合した動的選択

新しいアーキテクチャでは、**最初の「司令塔」であるMain LLMが、ユーザーの要求理解と同時に、次に実行すべきタスクに最適なプロンプトパターンを判断**します。

1.  **Main LLMの複合的役割**: ユーザーからの入力を受けたMain LLMは、意図分析を行うだけでなく、そのタスクの性質（単純な応答で十分か、専門的な手順書が必要か）を評価します。
2.  **JSONに出力**: Main LLMは、その判断結果を「7.1 LLM出力フォーマットの統一」で定義したJSON内の`prompt_pattern`フィールドに出力します。
3.  **ディスパッチャによる実行**: 後続の「Action Dispatch」層がこの`prompt_pattern`を読み取り、指定された通りのプロンプト（例: `base_main_specialized`）を構築して、次のLLM呼び出し（またはツール実行）を実行します。

### 10.3 この設計の利点

- **インテリジェンスの向上**: LLMが会話全体の文脈を理解してパターンを選択するため、キーワードに頼るルールベース方式よりもはるかに高精度で柔軟な判断が可能です。
- **パフォーマンスの維持**: 「どのプロンプトを使うか」を判断するための余分なLLM呼び出しが不要です。要求理解のプロセスに「相乗り」させることで、応答速度とコストを悪化させません。
- **保守性の向上**: 複雑で壊れやすいキーワード判定のルールを管理する必要がなくなり、システムの保守性が向上します。

### 10.4 呼び出しパターンの定義

Main LLMによって選択されるプロンプトパターンは以下の通りです。

- **`base_main`**: 軽い会話、質疑応答、単純な情報提供など、専門的な手順書が不要な場合に使用されます。
- **`base_main_specialized`**: 計画作成（PLANNING）、ツール実行（EXECUTION）、結果の検証（REVIEW）など、特定の専門知識や手順書を必要とする複雑なタスクを実行する場合に使用されます。

## 11. トークン予算とプロンプト最適化

### 11.1 段階的なトークン管理
**Phase 1**: 手動テストで調整可能な設定
```python
class PromptBudgetManager:
    def __init__(self):
        # 初期値は設定可能、後で自動化
        self.base_max_tokens = 500  # 設定ファイルで調整可能
        self.main_max_tokens = 800
        self.specialized_max_tokens = 1200
    
    def truncate_if_needed(self, prompt: str, max_tokens: int) -> str:
        # 簡易的な切り詰め（後でLLMトークンカウントに置換）
        if len(prompt) > max_tokens * 4:  # 概算
            return prompt[:max_tokens * 4] + "..."
        return prompt
```

**Phase 4**: 自動化されたトークン管理
```python
class AutoPromptBudgetManager:
    def __init__(self):
        self.llm_tokenizer = AutoTokenizer.from_pretrained("gpt2")  # 例
    
    def count_tokens(self, text: str) -> int:
        return len(self.llm_tokenizer.encode(text))
    
    def optimize_prompt(self, prompt: str, max_tokens: int) -> str:
        current_tokens = self.count_tokens(prompt)
        if current_tokens <= max_tokens:
            return prompt
        
        # 削り順序を固定
        # 1. Evidence（証拠）
        # 2. 会話要約
        # 3. open_questions
        # 4. plan_brief手数
        return self._truncate_by_priority(prompt, max_tokens)
```

### 11.2 プロンプトの段階的最適化
**Phase 1**: テンプレート化のみ
```python
class PromptTemplate:
    def __init__(self):
        # テンプレートの構造は固定、内容は後で最適化
        self.base_template = """
        あなたはDuckflowのAIアシスタントです。
        基本人格: {personality}
        制約: {constraints}
        """
        
        self.main_template = """
        現在の状況: {current_situation}
        固定5項目: {fixed_five_items}
        """
```

**Phase 4**: 自動最適化
- トークン数の自動監視
- 超過時の自動調整
- パフォーマンスメトリクスの収集

### 11.3 実装時の注意点
- **初期段階**: 手動調整で適切な長さを見つける
- **段階的改善**: 動作確認後に自動化を検討
- **パフォーマンス**: トークンカウントのオーバーヘッドを最小化
- **柔軟性**: 設定ファイルで調整可能にする

## 12. ファイル操作の安全性

### 11.1 作業フォルダの保護
**実装要件**:
```python
class FileProtector:
    def __init__(self):
        self.work_dir = "./work"  # 作業フォルダ
        self.safe_extensions = [".txt", ".md", ".py", ".json", ".yaml"]
    
    def is_safe_path(self, file_path: str) -> bool:
        """安全なパスかチェック"""
        # 作業フォルダ内のみ許可
        if not file_path.startswith(self.work_dir):
            return False
        
        # 危険な拡張子をチェック
        for ext in [".exe", ".bat", ".sh", ".ps1"]:
            if file_path.endswith(ext):
                return False
        
        return True
    
    def check_operation(self, operation: str, file_path: str) -> bool:
        """操作の安全性をチェック"""
        if operation in ["write", "create", "delete"]:
            return self.is_safe_path(file_path)
        return True  # 読み取りは常に許可
```

### 11.2 段階的な安全性強化
- **Phase 1**: 作業フォルダ外の保護のみ
- **Phase 2**: 危険な拡張子のチェック
- **Phase 3**: ファイルサイズと内容の検証
- **Phase 4**: 本格的なGateシステム

### 11.3 Tool Routerの段階的統合
**Phase 1**: 直接呼び出しで開始
```python
class SimpleFileOps:
    def __init__(self):
        self.file_protector = FileProtector()
    
    def read_file(self, file_path: str) -> str:
        if not self.file_protector.is_safe_path(file_path):
            raise ValueError("作業フォルダ外のファイルは読み取れません")
        # 実装
    
    def write_file(self, file_path: str, content: str) -> bool:
        if not self.file_protector.is_safe_path(file_path):
            raise ValueError("作業フォルダ外のファイルは書き込めません")
        # 実装
```

**Phase 3**: Router化（後で追加）
```python
class ToolRouter:
    def __init__(self):
        self.file_ops = SimpleFileOps()
        self.conversation_gate = BasicConversationGate()
    
    def route_operation(self, operation: str, **kwargs):
        # 安全性チェック
        if operation in ["write", "create", "delete"]:
            file_path = kwargs.get("file_path")
            if self.conversation_gate.is_gate_required(operation, file_path):
                return self.conversation_gate.generate_gate_message(operation, file_path)
        
        # 操作の実行
        if operation == "read":
            return self.file_ops.read_file(kwargs["file_path"])
        elif operation == "write":
            return self.file_ops.write_file(kwargs["file_path"], kwargs["content"])
        # 他の操作も同様に
```

### 11.4 安全性の段階的向上
**Phase 1**: 基本保護
- 作業フォルダ外の操作を拒否
- 基本的なファイル読み取りのみ許可

**Phase 2**: 拡張子チェック
- 危険な拡張子のファイル操作を拒否
- 安全な拡張子のリストを管理

**Phase 3**: 内容検証
- ファイルサイズの制限
- 基本的な内容チェック

**Phase 4**: 本格的なGate
- リスクレベルの自動判定
- 承認プロセスの完全統合

## 13. 実装の優先順位

### 12.1 Phase 1: 基盤システム（1-2週間）
**目標**: 最小限の制御基盤を構築し、基本的な動作を確認

**実装内容**:
- **EnhancedAgentState**: 固定5項目の基本実装
- **StatusManager**: Step/Status分離の基本動作
- **TransitionController**: 許可遷移表と1発話1遷移
- **FileProtector**: 作業フォルダ外の基本保護
- **LLMOutputFormatter**: 最小限のJSON出力

**完了条件**:
- 正常系: PLANNING→EXECUTION→REVIEW→done が通る
- 異常系: EXECUTION(ERROR)→PLANNING に戻る
- 基本的なファイル読み取りが動作する

**実装完了**: ✅ Phase 1完了（2025-08-19）

### 12.1.1 Phase 1完了後の設計簡略化

**設計の根本問題と解決策**:
- **複数パスの統一**: プラン生成を統一メソッドに集約
- **ルーティング概念の削除**: 状態ベースの設計に統一
- **レガシー互換の削除**: PlanContextを削除し、PlanToolのみに統一
- **フォールバック処理の削除**: エラー時は例外を正しく投げる
- **分離の不要性**: ファイル操作ベースと対話ベースの統一

**簡略化後の設計**:
```python
class EnhancedCompanionCore:
    def __init__(self):
        # PlanToolのみ（レガシー削除）
        self.plan_tool = PlanTool()
        
    def _generate_plan_unified(self, content: str):
        """統一プラン生成（全パスで使用）"""
        plan_id = self.plan_tool.propose(content)
        self._ensure_action_specs(plan_id)  # エラー時は例外
        return plan_id
    
    def _ensure_action_specs(self, plan_id: str):
        """ActionSpec保証（フォールバックなし）"""
        action_spec = ActionSpec(
            kind='implement',
            path='game_doc.md',
            description='実装計画に基づく最小限の安全な実装',
            optional=False
        )
        self.plan_tool.set_action_specs(plan_id, [action_spec])
```

**削除・簡略化された機能**:
- ❌ ルーティングロジック（`_handle_routing_based_processing`）
- ❌ 詳細確認フロー（`_handle_enhanced_clarification`）
- ❌ レガシー互換（PlanContext関連）
- ❌ フォールバック処理
- ❌ 複雑な状態管理

**統一された処理フロー**:
```
ユーザー入力 → 状態確認 → プラン生成（統一） → 実行 → 結果表示
```

### 12.2 Phase 2: 基本的なLLM統合（1-2週間）
**目標**: Base + Main プロンプトの基本動作を確立

**実装内容**:
- **BasePromptGenerator**: 基本人格と制約の生成
- **MainPromptGenerator**: 固定5項目と会話状況の生成
- **LLMCallManager**: 基本的なLLM呼び出し
- **ContextAssembler**: AgentStateからの文脈構築

**完了条件**:
- Base + Main プロンプトが正常に生成される
- 固定5項目が適切に更新される
- 基本的な会話が文脈を保持する

### 12.3 Phase 3: 機能拡張（2-3週間）
**目標**: Specialized プロンプトと3パターンの呼び分けを実装

**実装内容**:
- **SpecializedPromptGenerator**: PLANNING/EXECUTION/REVIEW用
- **PromptRouter**: 3パターンの適切な選択
- **ToolRouter**: 基本的なツール統合
- **ConversationGate**: 簡単な承認プロセス

**完了条件**:
- 3パターンのプロンプトが適切に選択される
- Specialized プロンプトが特定のタスクに特化する
- 基本的な承認プロセスが動作する

### 12.4 Phase 4: 最適化と安全性強化（2-3週間）
**目標**: パフォーマンス最適化と本格的な安全性を実現

**実装内容**:
- **トークン予算の自動化**: プロンプト長の最適化
- **ConversationGate**: 本格的な承認システム
- **パフォーマンス最適化**: キャッシュとレイテンシ改善
- **包括的なテスト**: 回帰・負荷・耐障害テスト

**完了条件**:
- トークン予算が自動で管理される
- 承認プロセスが自然な会話フローに統合される
- パフォーマンス目標を達成する

## 14. 期待される効果

### 13.1 技術的効果
- **文脈の一貫性**: 会話の流れが途切れない
- **操作の透明性**: 各操作の理由が明確
- **状態管理の明確化**: ステップとステータスの分離
- **制御の向上**: 許可遷移表による適切な制御

### 13.2 ユーザビリティの向上
- **自然な会話**: 承認プロセスが自然に統合
- **理解しやすさ**: 操作の理由が常に明確
- **一貫性**: 予測可能な動作

### 13.3 保守性の向上
- **明確な責任分離**: 各コンポーネントの役割が明確
- **設定による制御**: ルールの調整が容易
- **包括的なテスト**: 各層でのテストが可能

## 15. 今後の拡張性

### 14.1 学習機能
- ユーザーの会話パターンの学習
- 操作の成功率の追跡
- 自動的な改善提案

### 14.2 外部連携
- 長時間作業の外付けランナー
- 他のAIシステムとの連携
- コミュニティ機能

### 14.3 カスタマイズ
- ユーザーごとの設定
- プロジェクトごとのルール
- プラグインシステム

## 16. まとめ

Duckflow v3のプロンプトシステムは、3層構造のプロンプト、明確に分離された状態管理、許可遷移表による制御、会話内Gate、最小限の対話ポリシーを組み合わせることで、文脈の一貫性を保ちながら、自然で安全な対話体験を提供します。

**実装の特徴**:
- **段階的アプローチ**: 最小限から開始し、動作確認後に拡張
- **安全性の優先**: 作業フォルダ外の保護から段階的に強化
- **実用性の重視**: 早期に基本動作を確認し、有用性を実証

**段階的実装の利点**:
- **早期の動作確認**: Phase 1で基本的な制御基盤を確立
- **リスクの最小化**: 複雑な機能は動作確認後に段階的に追加
- **開発効率の向上**: 手戻りを最小化し、継続的な改善が可能
- **ユーザー価値の早期提供**: 基本機能でも有用性を実証

**各Phaseの重点**:
- **Phase 1**: 制御の背骨（Step/Status、遷移制御、基本保護）
- **Phase 2**: LLM統合（Base+Main、文脈保持、基本対話）
- **Phase 3**: 機能拡張（Specialized、3パターン、Tool Router）
- **Phase 4**: 最適化（パフォーマンス、安全性、本格運用）

この設計により、AIアシスタントが会話の流れを正しく理解し、適切な判断と処理を実行できるようになり、ユーザーにとって使いやすく、開発者にとって保守しやすいシステムが実現されます。


---

## 機能別流用可能性分類
現在のシステム状況と既存実装を詳しく調査した結果、以下のように機能ごとに流用可能性を分類いたします。
1. 状態管理システム（Step/Status分離）
完全流用可能 ✅
- AgentState: codecrafter/state/agent_state.py - 既存の高度な状態管理システム
- Vitals System: D.U.C.K. Vitals System（気分・集中力・体力の監視）
- ConversationMemory: codecrafter/memory/conversation_memory.py
一部流用可能 🔄
- Step/Status分離: 既存のAgentStateを拡張して実装
- 遷移制御: 既存のPeckingOrderManagerを参考に実装
新規実装が必要 🆕
- TransitionController: 許可遷移表の実装
- TransitionLimiter: 1発話1遷移の制御
2. プロンプトシステム（3層構造）
完全流用可能 ✅
- PromptCompiler: codecrafter/prompts/prompt_compiler.py - 高度なテンプレート管理
- PromptContextBuilder: codecrafter/prompts/context_builder.py - コンテキスト構築
- システムプロンプト: 既存の3つのテンプレート（system_base, system_rag_enhanced, system_error_recovery）
一部流用可能 ��
- Base Prompt: 既存のsystem_baseを拡張
- Main Prompt: 既存のテンプレート構造を活用
- Specialized Prompt: 既存のテンプレートシステムを拡張
新規実装が必要 🆕
3パターンの呼び分け: Base+Main, Base+Main+Specialized, Base+Specialized
- パターン選択ロジック: 状況に応じた適切な選択
3. ファイル操作と安全性
完全流用可能 ✅
- SimpleFileOps: companion/file_ops.py - 承認機能付きファイル操作
- 承認システム: companion/approval_system.py - 包括的な承認システム
- リスク評価: 既存のRiskLevel判定ロジック
一部流用可能 🔄
- FileProtector: 既存の承認システムを拡張
- 作業フォルダ保護: 既存のリスク評価を活用
新規実装が必要 🆕
- 段階的な安全性強化: Phase 1-4の段階的実装
- Tool Router: 既存のSimpleFileOpsをRouter化
4. 承認システム（ConversationGate）
完全流用可能 ✅
- SimpleApprovalGate: companion/simple_approval.py - 基本承認ゲート
- 承認UI: companion/approval_ui.py - ユーザーインターフェース
- リスク評価: 既存のRiskLevel判定
一部流用可能 ��
- 会話内Gate: 既存の承認システムを会話フローに統合
5点情報提供: 既存のOperationInfoを拡張
- 新規実装が必要 🆕
- 会話フロー統合: 承認プロセスを自然な会話に埋め込み
- 段階的実装: 作業フォルダ保護から本格Gateまで
5. LLM出力フォーマット統一
完全流用可能 ✅
- JSON出力: 既存のPromptCompilerの出力形式管理
- バリデーション: 既存のPydanticモデル検証
新規実装が必要 🆕
- 統一フォーマット: rationale, goal_consistency, constraint_check等
- LLMOutputFormatter: 出力形式の標準化
- エラー時の復旧: JSON解析失敗時の処理
6. トークン予算とプロンプト最適化
完全流用可能 ✅
- PromptCompiler: 既存のトークン管理機能
- テンプレート最適化: 既存の動的最適化システム
新規実装が必要 ��
- 段階的トークン管理: 手動調整から自動化まで
- 削り順序: Evidence→会話要約→open_questions→plan_brief
7. 統合システム（EnhancedCompanionCore）
完全流用可能 ✅
- CompanionCore: companion/core.py - 基本対話機能
- DualLoop: companion/enhanced_dual_loop.py - 非同期処理
- SharedContextManager: companion/shared_context_manager.py - コンテキスト共有
一部流用可能 ��
- EnhancedCompanionCore: 既存の統合版を拡張
- LLM統合: 既存のllm_managerを活用
新規実装が必要 ��
- 3層プロンプト統合: 既存システムとの統合
- 状態管理統合: AgentStateとCompanionCoreの統合

#### 実装戦略の推奨
Phase 1: 基盤システム（1-2週間）
- AgentStateの拡張: 既存のcodecrafter/state/agent_state.pyをコピーして拡張
- Step/Status分離: 既存の状態管理を基盤として実装
- TransitionController: 新規実装（既存のPeckingOrderManagerを参考）
Phase 2: LLM統合（1-2週間）
- PromptCompiler活用: 既存のcodecrafter/prompts/prompt_compiler.pyをコピーして活用
- 3層構造実装: 既存のテンプレートシステムを拡張
- ContextBuilder統合: 既存のcodecrafter/prompts/context_builder.pyを活用
Phase 3: 機能拡張（2-3週間）
- 承認システム統合: 既存のcompanion/approval_system.pyを会話フローに統合
- Tool Router: 既存のcompanion/file_ops.pyをRouter化
- 3パターン実装: 既存のPromptCompilerを拡張
Phase 4: 最適化（2-3週間）
- トークン管理: 既存のPromptCompilerの最適化機能を活用
- パフォーマンス: 既存のDualLoopシステムの最適化
- 包括的テスト: 既存のテスト基盤を活用

#### 流用時の注意点
codecrafterフォルダ: 直接呼び出しではなく、必要なファイルをコピー
依存関係: 既存の依存関係を新しいシステムに適応
段階的統合: 既存機能を段階的に統合し、動作確認を逐次実施
設計ドキュメント: docs/proposals/duckflow_v3_prompt_system_design.mdの詳細設計を活用


---


**次のステップ**:
1. Phase 1の基盤システムの実装開始
2. 最小限の動作確認とテスト
3. 段階的な機能追加と改善
4. 継続的なユーザーフィードバックの収集

---




**文書情報**
- 作成日: 2025年1月
- バージョン: 2.0
- 作成者: Duckflow開発チーム
- 最終更新: 2025年1月
- 実装方針: 段階的アプローチ、最小限から開始、動作確認後に拡張
