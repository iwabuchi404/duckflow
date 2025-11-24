# Duckflow E2Eテストシステム設計ドキュメント

**バージョン:** 1.1  
**作成日:** 2025年1月  
**最終更新:** 2025年1月  
**ステータス:** 設計確定（シンプル実装方針）

## 1. 概要

### 1.1 目的
Duckflow v4.0システムの品質保証と継続的な動作確認を目的とした、AI駆動のEnd-to-End（E2E）テストシステムの設計と実装指針を定義します。

### 1.2 背景と課題
従来のソフトウェアテストとは異なり、LLMを核とするAIシステムには以下の特徴があります：

- **非決定性**: 同じ入力でも毎回異なる出力が生成される
- **文脈依存**: 会話の流れや状態によって適切な応答が変化する
- **評価の主観性**: 「良い応答」の判定が機械的に困難

これらの課題に対し、LLMの柔軟性を活用したシンプルで実用的な評価システムを構築します。

### 1.3 設計思想
- **シンプル性**: 複雑な仕組みを避け、実装・保守が容易な設計
- **柔軟性**: LLMの非決定性を受け入れた評価基準
- **実用性**: 継続的テストに組み込み可能な軽量システム
- **段階的実装**: 基本機能から段階的に拡張可能な構造
- **新規実装**: 既存システム（PromptSmith等）の複雑さを避け、必要最小限の機能に特化

## 2. システムアーキテクチャ

### 2.1 全体フロー

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Test LLM    │───▶│ Duckflow    │───▶│ Log         │
│ (ユーザー役) │◀───│ System      │    │ Recorder    │
└─────────────┘    └─────────────┘    └─────────────┘
                                              │
                                              ▼
                                    ┌─────────────┐
                                    │ Evaluation  │
                                    │ LLM         │
                                    └─────────────┘
```

### 2.2 主要コンポーネント

#### 2.2.1 Test LLM（対話実行エンジン）
**役割**: ユーザー役としてシナリオに沿った自然な対話を実行

**機能**:
- シナリオに基づく対話の進行
- Duckflowの応答に応じた適切な反応
- 承認プロセスでの自動応答
- 終了条件の判定

**実装要件**:
```python
class ConversationTestLLM:
    def __init__(self, scenario: str, evaluation_criteria: str)
    def get_system_prompt(self) -> str
    def generate_next_input(self, conversation_history: List) -> str
    def should_terminate(self, last_response: str) -> bool
```

#### 2.2.2 Log Recorder（ログ記録システム）
**役割**: 対話全体のログを構造化して記録

**記録内容**:
- 対話の各ターン（ユーザー入力、Duckflow応答）
- システム内部状態の変化
- ファイル操作の履歴
- タイムスタンプと実行時間
- エラーや警告メッセージ

**データ構造**:
```json
{
    "session_id": "uuid",
    "scenario": "シナリオ名",
    "start_time": "2025-01-01T10:00:00",
    "exchanges": [
        {
            "timestamp": "2025-01-01T10:00:01",
            "user": "ユーザー入力",
            "duckflow": "Duckflow応答",
            "system_state": {...}
        }
    ],
    "files_created": [...],
    "completion_status": "completed|failed|timeout"
}
```

#### 2.2.3 Evaluation LLM（評価エンジン）
**役割**: 対話ログを分析して品質を評価

**評価観点**:
1. **シナリオ達成度**: 設定された目的が達成されているか
2. **対話の自然さ**: Duckflowの応答が自然で適切か  
3. **技術的正確性**: 生成されたファイルやコードが適切か
4. **エラーハンドリング**: 問題発生時の対応が適切か
5. **総合評価**: 全体的な品質とユーザビリティ

**評価スコア**: 各項目1-5点（3点以上で合格）

#### 2.2.4 Test Runner（テスト実行制御）
**役割**: テスト全体の制御と結果の統合

**機能**:
- シナリオファイルの読み込み
- Test LLMとDuckflowシステムの連携
- ログ記録の管理
- 評価の実行と結果保存
- バッチ実行とレポート生成

## 3. テストシナリオ設計

### 3.1 複雑度レベル

**レベル1（簡単）**: 単発要求、1-2往復で完了
- 基本的な機能確認
- 単純なファイル操作
- 基本的な説明要求

**レベル2（中程度）**: 2-3ステップ、文脈継続が重要
- 複数段階のタスク
- 文脈を必要とする対話
- 中程度の技術的複雑さ

**レベル3（複雑）**: 4-5ステップ以上、複雑な判断・エラー対応が必要
- 包括的なシステム操作
- 高度な分析・判断
- エラー対応・リカバリ

### 3.2 ジャンル分類

#### 3.2.1 レビュー系
- コード品質の評価
- 設計の分析
- 改善提案の生成

#### 3.2.2 ファイル作成系
- 単一ファイル作成
- マルチファイルプロジェクト
- テンプレート生成

#### 3.2.3 プランニング系
- 機能追加計画
- システム設計
- 移行戦略

#### 3.2.4 説明・教育系
- 技術概念の説明
- 比較分析
- 学習ガイダンス

#### 3.2.5 エラー調査・デバッグ系
- エラー解析
- ログ調査
- パフォーマンス問題

#### 3.2.6 その他
- リファクタリング
- ドキュメント作成
- テスト作成
- 環境構築

### 3.3 シナリオファイル形式

```yaml
# scenarios/simple_file_creation.yaml
name: "単純ファイル作成"
level: 1
genre: "ファイル作成"
description: "基本的なPythonファイル作成の動作確認"

scenario: |
  calculator.pyファイルを作って、足し算と引き算ができる関数を作ってください

evaluation_criteria: |
  1. ユーザーの要求を正しく理解しているか
  2. 適切な関数が実装されているか
  3. Pythonの構文が正しいか
  4. 承認プロセスが適切に機能しているか

expected_outcomes:
  - file_creation: "calculator.py"
  - functions: ["add", "subtract"]
  - approval_required: true

test_config:
  max_exchanges: 6
  timeout_minutes: 5
  min_score: 3.0
  
priority: "high"  # high/medium/low
frequency: "daily"  # daily/weekly/release
```

## 4. 設計方針の確定

### 4.1 既存システムとの関係

#### 4.1.1 PromptSmithとの比較
既存のPromptSmithシステム（codecrafter/promptsmith/）は以下の特徴を持ちますが、今回のE2Eテストシステムには**採用しません**：

**PromptSmithの特徴（複雑すぎるため不採用）**：
- 3つのAI役割システム（Tester AI、Target AI、Optimizer AI）
- 自動改善サイクル（プロンプト分析→改善→検証→適用）
- 高度な分析機能（意図理解率、混乱ポイント検出、A/Bテスト）
- バージョン管理システム（プロンプト履歴管理と段階的適用）

**不採用の理由**：
1. **複雑すぎる**: 基本的な動作確認が目的なのに、高度な自動改善機能は不要
2. **システム構造の違い**: 旧codecrafterベース vs 現在のcompanionベース
3. **実装コストが高い**: 複雑なシステムの理解・修正・統合に時間がかかる
4. **保守性の低下**: 不要な複雑さが将来的な保守を困難にする

#### 4.1.2 新規実装の方針
**完全新規実装**を採用し、以下の要素のみに特化します：

**採用する要素**：
- ✅ シンプルな対話テスト（Test LLM ↔ Duckflow）
- ✅ 基本的な評価（Evaluation LLM）
- ✅ ログ記録と結果保存
- ✅ YAMLベースのシナリオ管理

**排除する要素**：
- ❌ 自動改善機能
- ❌ 複雑な分析エンジン
- ❌ プロンプトバージョン管理
- ❌ A/Bテスト機能

## 5. 実装仕様

### 5.1 ディレクトリ構造

```
duckflow/
├── tests/
│   ├── e2e/
│   │   ├── __init__.py
│   │   ├── test_runner.py           # テスト実行制御
│   │   ├── conversation_llm.py      # Test LLM実装
│   │   ├── evaluator.py            # Evaluation LLM実装
│   │   ├── logger.py               # ログ記録システム
│   │   └── utils.py                # ユーティリティ
│   ├── scenarios/                  # シナリオ定義
│   │   ├── level1/
│   │   │   ├── file_creation_simple.yaml
│   │   │   ├── review_simple.yaml
│   │   │   └── explanation_simple.yaml
│   │   ├── level2/
│   │   │   └── ...
│   │   └── level3/
│   │       └── ...
│   └── results/                    # テスト結果
│       ├── daily/
│       ├── weekly/
│       └── archives/
└── docs/
    └── e2e_test_system_design.md   # このドキュメント
```

### 5.2 主要クラス設計

#### 5.2.1 ConversationTestLLM
```python
class ConversationTestLLM:
    """シナリオに沿って対話を実行するLLM"""
    
    def __init__(self, scenario: str, evaluation_criteria: str):
        self.scenario = scenario
        self.evaluation_criteria = evaluation_criteria
        self.conversation_log = []
        self.min_score_threshold = 3.0
    
    def get_system_prompt(self) -> str:
        """対話実行用のシステムプロンプトを生成"""
        
    def generate_next_input(self, conversation_history: List[Dict]) -> str:
        """次のユーザー入力を生成"""
        
    def should_terminate(self, last_response: str) -> bool:
        """対話終了条件を判定"""
```

#### 5.2.2 ConversationLogger
```python
class ConversationLogger:
    """対話ログの記録と管理"""
    
    def __init__(self, scenario_name: str):
        self.log = {...}
    
    def log_exchange(self, user_input: str, duckflow_response: str, 
                    system_state: dict = None):
        """1回の対話をログに記録"""
        
    def log_file_operation(self, operation: str, file_path: str, content: str = ""):
        """ファイル操作をログに記録"""
        
    def save_log(self, filepath: str):
        """ログをファイルに保存"""
```

#### 5.2.3 ConversationEvaluator
```python
class ConversationEvaluator:
    """対話ログを評価するLLM"""
    
    def evaluate_conversation(self, log: dict, scenario: str, 
                            evaluation_criteria: str) -> dict:
        """対話全体を評価"""
        
    def _build_evaluation_prompt(self, log: dict, scenario: str, 
                               criteria: str) -> str:
        """評価用プロンプトを構築"""
        
    def _parse_evaluation_result(self, llm_response: str) -> dict:
        """評価結果をパース"""
```

#### 5.2.4 E2ETestRunner
```python
class E2ETestRunner:
    """E2Eテストの実行制御"""
    
    def __init__(self, duckflow_system):
        self.duckflow_system = duckflow_system
        self.test_llm = None
        self.evaluator = ConversationEvaluator()
        self.logger = None
    
    async def run_single_test(self, scenario_file: str) -> dict:
        """単一テストを実行"""
        
    async def run_test_suite(self, scenario_pattern: str = "*") -> dict:
        """テストスイートを実行"""
        
    def generate_report(self, results: List[dict]) -> str:
        """テスト結果レポートを生成"""
```

### 5.3 統合ポイント

#### 5.3.1 Duckflowシステムとの連携
```python
# DuckflowCompanionクラスにテストモード追加
class DuckflowCompanion:
    def __init__(self, test_mode: bool = False):
        self.test_mode = test_mode
        if test_mode:
            self.setup_test_hooks()
    
    def setup_test_hooks(self):
        """テスト用フックを設定"""
        # ログ出力の詳細化
        # 状態変化の記録
        # 承認プロセスの自動化オプション
```

#### 5.3.2 ログ統合
- Duckflowの内部ログとテストログの統合
- AgentStateの変化追跡
- PromptCompilerの出力記録
- ファイル操作の詳細記録

## 6. 実装フェーズ

### 6.1 Phase 1: 基本システム構築（1-2週間）
**目標**: 基本的なE2Eテストフレームワークの構築

**実装内容**:
- ConversationTestLLM（基本版）
- ConversationLogger
- ConversationEvaluator（基本版）
- E2ETestRunner（基本版）
- レベル1シナリオ 3-5個

**完了条件**:
- 単純なファイル作成テストが動作する
- 評価結果がJSON形式で出力される
- ログが適切に記録される

### 6.2 Phase 2: シナリオ拡充（1-2週間）
**目標**: テストシナリオの体系的整備

**実装内容**:
- レベル1シナリオ 全ジャンル（10-15個）
- レベル2シナリオ 主要ジャンル（5-8個）
- バッチ実行機能
- 結果レポート機能

**完了条件**:
- 主要機能の基本テストが網羅される
- 継続的テストに組み込み可能

### 6.3 Phase 3: 高度な評価（2-3週間）
**目標**: 評価精度の向上と複雑シナリオ対応

**実装内容**:
- レベル3シナリオ（3-5個）
- 文脈を考慮した高度な評価
- パフォーマンス測定
- 品質劣化検出

**完了条件**:
- 複雑なシナリオが安定動作
- 品質の定量的測定が可能
- リグレッション検出機能

## 7. 運用方針

### 7.1 テスト実行頻度
- **Daily**: レベル1シナリオ（基本動作確認）
- **Weekly**: レベル1-2シナリオ（包括的テスト）
- **Release**: 全レベル（リリース前確認）

### 7.2 合格基準
- **個別テスト**: 総合評価3.0点以上
- **テストスイート**: 80%以上のテストが合格
- **リグレッション**: 前回比で品質スコア低下なし

### 7.3 継続的改善
- テスト結果の分析と傾向把握
- 失敗パターンの分析とシナリオ改善
- 評価基準の継続的調整
- 新機能追加時のシナリオ拡張

## 8. 期待される効果

### 8.1 品質保証
- 基本機能の継続的動作確認
- リグレッションの早期発見
- 品質劣化の定量的把握

### 8.2 開発効率向上
- 手動テストの自動化
- 問題箇所の迅速な特定
- 安心できるリファクタリング環境

### 8.3 ユーザビリティ向上
- 実際の使用パターンでのテスト
- 自然な対話フローの検証
- ユーザー体験の継続的監視

## 9. 技術的考慮事項

### 9.1 LLM選択
- **Test LLM**: GPT-4o mini（コスト効率）
- **Evaluation LLM**: GPT-4o（高精度評価）
- **代替案**: Claude 3.5 Sonnet（バックアップ）

### 9.2 コスト管理
- トークン使用量の監視
- 評価頻度の最適化
- 効率的なプロンプト設計

### 9.3 信頼性確保
- LLM評価の一貫性検証
- 評価基準のキャリブレーション
- 人間による評価との比較検証

## 10. リスクと対策

### 10.1 技術リスク
**リスク**: LLM評価の不安定性  
**対策**: 複数回実行による平均化、人間によるスポットチェック

**リスク**: テスト実行時間の長期化  
**対策**: 並列実行、シナリオの優先度付け

### 10.2 運用リスク
**リスク**: 偽陽性（問題ないのに失敗判定）  
**対策**: 評価基準の継続的調整、閾値の見直し

**リスク**: テスト保守の負担  
**対策**: シナリオの標準化、自動化の徹底

## 11. まとめ

このE2Eテストシステムは、Duckflowの非決定的な特性を受け入れながら、実用的な品質保証を実現するために設計されました。LLMの柔軟性を活用することで、従来の機械的テストでは困難だった「自然さ」「適切さ」「文脈整合性」といった観点での評価を可能にします。

段階的な実装により、早期から継続的テストに組み込むことができ、Duckflowの品質向上と開発効率の向上に寄与することが期待されます。

**重要な設計決定**：
既存のPromptSmithシステムは高度すぎるため採用せず、**シンプルで実用的な新規実装**により、必要最小限の機能に特化したE2Eテストシステムを構築します。

---

**文書情報**
- 作成者: Duckflow開発チーム
- 最終更新: 2025年1月
- バージョン: 1.1
- ステータス: 設計確定（シンプル実装方針）
- 承認者: [未設定]
- 次回レビュー: Phase 1実装完了後