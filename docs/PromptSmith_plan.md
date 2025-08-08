# PromptSmith（プロンプトスミス）

「鍛冶職人が金属を鍛えるように、AIプロンプトを磨き上げる」という意味合い

## 概要
PromptSmithは、AIコーディングエージェントのシステムプロンプトを自動で改善し続ける仕組みです。
「ユーザー役」「エージェント本体」「改善役」という3つのAIを対話させ、
実行結果から弱点を抽出 → プロンプトを改善 → 再テストという改善サイクルを回します。

## 目的
AIコーディングエージェントがユーザー意図を正確に理解できるようにする

曖昧な要求や仕様変更にも柔軟に対応できる能力を向上させる

人間が介入しなくても半自動でプロンプト品質を向上

## 構成図
┌───────────────────────────────┐
│        AIユーザー役（Tester AI）         │
│   - 曖昧/複雑な指示を出す                 │
└───────────────────────────────┘
                 │
                 ▼
┌───────────────────────────────┐
│      コーディングエージェント（Target AI）  │
│   - 現行プロンプトで開発タスクを実行         │
└───────────────────────────────┘
                 │
                 ▼
┌───────────────────────────────┐
│   プロンプト改善AI（Optimizer AI）        │
│   - 実行ログを分析し弱点を抽出             │
│   - 新しいプロンプト案を生成               │
└───────────────────────────────┘
                 │
                 ▼
     改善後プロンプトで再テスト（ループ）

## ワークフロー
- シナリオ生成（Tester AI）
  - ユーザー役が曖昧or仕様変更の指示を作成

- タスク実行（Target AI）
  - 現行プロンプトを使って開発作業

- ログ収集
  - 対話ログ＋ファイル操作履歴を保存

- 改善提案（Optimizer AI）
  - 成功/失敗分析
  - プロンプト修正版を生成

- 承認 or 自動適用
  - 改善後プロンプトで再テスト

- 継続学習
  - 効果測定（成功率、意図理解率）

## 改善指標（メトリクス）
意図理解率（要求の正確な解釈率）

コード実行成功率

質問回数（必要な質問が適切だったか）

やり直し回数

実行時間

## 技術スタック候補
フレームワーク: LangChain / LlamaIndex

データ保存: SQLite（ログ＋プロンプト履歴）

実行環境: Python

## 初期バージョンの制約
改善の適用は人間承認モードで開始

改善案は小規模変更に限定（1回につき1〜3項目）

この設計なら、最初はシンプルに回して効果を見つつ、
精度が出てきたら完全自動プロンプト改善モードに移行できます。

---

# PromptSmith 実装詳細プラン

## 現状分析（Duckflow基盤活用）

### 既存資産の活用
- **サンドボックス評価システム** - 安全な実行環境とファイル操作追跡
- **評価エンジン** - 品質・完成度・効率性の多角的評価
- **メトリクス収集システム** - 評価履歴の蓄積とトレンド分析
- **5つのテストシナリオ** - 基本的な開発タスクのベンチマーク

### 追加が必要な要素
1. **3つのAI役割システム**
2. **プロンプト管理・バージョニング**
3. **対話ログ詳細分析**
4. **自動改善提案生成**

## アーキテクチャ設計

### システム構成図
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Tester AI     │    │   Target AI     │    │  Optimizer AI   │
│ (シナリオ生成)   │────│ (実際の開発)     │────│ (プロンプト改善) │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                        │                        │
         └────────────────────────┼────────────────────────┘
                                  │
                      ┌─────────────────┐
                      │  PromptSmith    │
                      │  オーケストレーター │
                      └─────────────────┘
                                  │
         ┌────────────────────────┼────────────────────────┐
         │                       │                        │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Duckflow       │    │  Prompt         │    │  Conversation   │
│  評価エンジン     │    │  Management     │    │  Log Analyzer   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### ディレクトリ構造（追加分）
```
codecrafter/
├── promptsmith/              # 新規追加
│   ├── __init__.py
│   ├── orchestrator.py       # メインオーケストレーター
│   ├── ai_roles/
│   │   ├── __init__.py
│   │   ├── tester_ai.py      # ユーザー役AI
│   │   ├── optimizer_ai.py   # プロンプト改善AI
│   │   └── conversation_analyzer.py
│   ├── prompt_manager.py     # プロンプト管理・バージョニング
│   └── improvement_engine.py # 改善提案生成
└── prompts/                  # 既存拡張
    ├── system_prompts/
    │   ├── current.yaml      # 現行プロンプト
    │   ├── versions/         # バージョン履歴
    │   └── templates/        # プロンプト構成要素
    └── __init__.py
```

## 実装フェーズ

### Phase 1: 基盤システム構築（2-3日）
**目標**: 3つのAI役割システムとプロンプト管理機能

#### 1.1 プロンプト管理システム
```python
# codecrafter/promptsmith/prompt_manager.py
class PromptManager:
    """システムプロンプトのバージョン管理と適用"""
    
    def __init__(self, prompt_dir: str = "prompts/system_prompts"):
        self.prompt_dir = Path(prompt_dir)
        self.current_version = self.load_current_version()
    
    def load_current_prompt(self) -> Dict[str, str]:
        """現行プロンプトの読み込み"""
        
    def save_new_version(self, improved_prompt: Dict[str, str], 
                        changes: List[str]) -> str:
        """改善されたプロンプトを新バージョンとして保存"""
        
    def apply_version(self, version_id: str) -> bool:
        """指定バージョンを現行に適用"""
        
    def get_version_history(self) -> List[Dict]:
        """バージョン履歴の取得"""
```

#### 1.2 AI役割システム基盤
```python
# codecrafter/promptsmith/ai_roles/tester_ai.py
class TesterAI:
    """曖昧・複雑な開発指示を生成するAI"""
    
    def generate_challenging_scenario(self, difficulty: str = "medium") -> Dict:
        """挑戦的なシナリオ生成"""
        
    def create_ambiguous_request(self, scenario_type: str) -> str:
        """意図的に曖昧な要求を生成"""
        
    def simulate_spec_change(self, original_request: str) -> str:
        """仕様変更の追加要求を生成"""
```

```python
# codecrafter/promptsmith/ai_roles/optimizer_ai.py
class OptimizerAI:
    """対話ログからプロンプト改善案を生成するAI"""
    
    def analyze_conversation_log(self, conversation: List[Dict]) -> Dict:
        """対話ログの詳細分析"""
        
    def identify_weakness_patterns(self, evaluation_results: Dict) -> List[str]:
        """弱点パターンの抽出"""
        
    def generate_improvement_suggestions(self, analysis: Dict) -> List[Dict]:
        """具体的改善提案の生成"""
```

#### 1.3 メインオーケストレーター
```python
# codecrafter/promptsmith/orchestrator.py
class PromptSmithOrchestrator:
    """3つのAIを協調させる改善サイクル制御"""
    
    def __init__(self):
        self.tester_ai = TesterAI()
        self.optimizer_ai = OptimizerAI()
        self.prompt_manager = PromptManager()
        self.sandbox_runner = SandboxTestRunner()  # 既存活用
        
    def run_improvement_cycle(self, iterations: int = 3) -> Dict:
        """1サイクルの改善プロセス実行"""
        
    def evaluate_prompt_performance(self, prompt_version: str) -> Dict:
        """プロンプトバージョンの性能評価"""
```

### Phase 2: 対話分析・改善生成機能（2-3日）
**目標**: 詳細な対話分析と自動改善提案

#### 2.1 対話ログ詳細分析
```python
# codecrafter/promptsmith/ai_roles/conversation_analyzer.py
class ConversationAnalyzer:
    """対話ログの詳細分析と改善ポイント抽出"""
    
    def analyze_intent_understanding(self, conversation: List[Dict]) -> float:
        """意図理解率の算出"""
        
    def detect_confusion_points(self, conversation: List[Dict]) -> List[Dict]:
        """混乱・誤解ポイントの検出"""
        
    def measure_question_quality(self, questions: List[str]) -> Dict:
        """質問品質の評価"""
        
    def track_task_completion_flow(self, conversation: List[Dict]) -> Dict:
        """タスク完了までのフロー分析"""
```

#### 2.2 改善提案エンジン
```python
# codecrafter/promptsmith/improvement_engine.py
class ImprovementEngine:
    """分析結果から具体的なプロンプト改善案を生成"""
    
    def generate_targeted_improvements(self, analysis: Dict) -> List[Dict]:
        """分析結果に基づく改善提案"""
        
    def create_prompt_variations(self, base_prompt: str, 
                               improvements: List[str]) -> List[str]:
        """複数の改善バリエーション生成"""
        
    def validate_improvement_safety(self, new_prompt: str) -> bool:
        """改善案の安全性検証"""
```

### Phase 3: 統合・自動化機能（1-2日）
**目標**: 全システム統合とA/Bテスト機能

#### 3.1 A/Bテスト機能
```python
class PromptABTester:
    """複数プロンプトバージョンの性能比較"""
    
    def run_ab_test(self, prompt_versions: List[str], 
                   test_scenarios: List[Dict]) -> Dict:
        """A/Bテスト実行"""
        
    def statistical_significance_test(self, results_a: List[float], 
                                    results_b: List[float]) -> Dict:
        """統計的有意性の検証"""
```

#### 3.2 自動適用システム
```python
class AutoApplySystem:
    """改善効果が確認されたプロンプトの自動適用"""
    
    def evaluate_safety_threshold(self, improvement_results: Dict) -> bool:
        """自動適用の安全性判定"""
        
    def gradual_rollout(self, new_prompt: str) -> None:
        """段階的なプロンプト適用"""
```

## 品質保証戦略

### テスト戦略
1. **ユニットテスト**: 各AI役割の個別機能
2. **統合テスト**: 3つのAI協調動作
3. **安全性テスト**: 悪いプロンプト変更の検出
4. **パフォーマンステスト**: 改善サイクルの実行時間

### 評価指標の拡張
既存メトリクスに以下を追加：

```python
@dataclass
class PromptSmithMetrics:
    # 既存メトリクス継承
    base_metrics: EvaluationMetrics
    
    # PromptSmith固有メトリクス
    intent_understanding_rate: float    # 意図理解率
    question_appropriateness: float     # 質問の適切性
    clarification_efficiency: float     # 明確化の効率性
    spec_change_adaptability: float     # 仕様変更への適応性
    improvement_iteration_count: int    # 改善イテレーション数
    prompt_version: str                 # 使用プロンプトバージョン
```

## 実装優先度

### 高優先度（必須機能）
1. ✅ **プロンプト管理システム** - バージョン管理・適用機能
2. ✅ **基本的なTester AI** - 簡単な曖昧シナリオ生成
3. ✅ **基本的なOptimizer AI** - ログ分析・改善提案
4. ✅ **メインオーケストレーター** - 改善サイクル制御

### 中優先度（機能強化）
1. 🔶 **詳細対話分析** - 意図理解率・混乱ポイント検出
2. 🔶 **A/Bテスト機能** - 複数バージョン性能比較
3. 🔶 **安全性検証** - 悪化防止メカニズム

### 低優先度（将来機能）
1. 🔸 **完全自動適用** - 人間確認不要モード
2. 🔸 **学習データ蓄積** - 長期的パターン学習
3. 🔸 **UI/Dashboard** - Web管理インターフェース

## 技術的考慮事項

### セキュリティ
- プロンプトインジェクション攻撃の防止
- 改善案の検証・サニタイゼーション
- バックアップとロールバック機能

### スケーラビリティ  
- 大量の改善サイクル実行に対応
- メトリクス収集の効率化
- 並列テスト実行機能

### 運用性
- ログレベル設定（改善プロセスの詳細追跡）
- 設定ファイルによるパラメータ調整
- エラー回復機能

## 成功指標（3ヶ月目標）

### 定量的指標
- **意図理解率**: 70% → 85%の向上
- **コード実行成功率**: 80% → 90%の向上  
- **やり直し回数**: 平均2回 → 1回以下に削減
- **プロンプト改善サイクル**: 週1回の自動実行

### 定性的指標
- 曖昧な要求への対応能力向上
- 仕様変更時の柔軟な適応
- ユーザー満足度の向上

この実装プランに基づき、既存のDuckflow評価システムを最大限活用しながら、
段階的にPromptSmithの自己改善機能を構築していきます。