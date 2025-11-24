# Duckflow 統合タスクループアーキテクチャ設計ドキュメント

**バージョン:** 1.0  
**作成日:** 2025-01-10  
**ステータス:** 設計完了・実装待ち

## 1. 概要 (Overview)

本ドキュメントでは、`LLM Services`と`Self-Correcting Loop`の設計思想を統合し、Duckflowの根本的な問題を解決するための包括的なアーキテクチャを定義します。

### 解決すべき根本問題
- **技術的成功 ≠ ユーザー要求満足**: ファイル読み取りに成功してもユーザーの要求（例：シナリオの説明）が満たされていない
- **単発実行の限界**: 1回のループで完了しないタスクへの対応不足
- **汎用性の欠如**: 特定問題に対する局所的修正で根本解決に至らない

## 2. アーキテクチャ原則

### A. **LLMサービス層の専門化**
各タスクに最適なLLMを割り当て、再利用可能なサービスとして提供

### B. **客観的タスク評価**
技術的実行の成否ではなく、**ユーザー要求の満足度**を基準とした評価

### C. **自己修正型継続ループ**
不完全な結果に対して自動的に改善計画を立案し、再実行する汎用メカニズム

### D. **構造化された要求追跡**
ユーザー要求を分解・追跡し、各要件の達成度を定量的に管理

## 3. 統合アーキテクチャ設計

### 3.1 LLMService層 (専門化されたLLMアクセス)

```python
class LLMService:
    """タスク別に最適化されたLLMサービス"""
    
    def __init__(self):
        # 3層LLM構成（既存LLM Services設計に準拠）
        self.creative_llm: BaseChatModel    # 複雑な計画立案・創造的思考
        self.fast_llm: BaseChatModel        # 高速評価・分類・要約  
        self.evaluator_llm: BaseChatModel   # 深い分析・客観的判定
    
    # === 計画立案サービス ===
    def plan_initial_execution(self, user_request: str, context: TaskContext) -> ExecutionPlan:
        """初回実行計画の立案（創造的LLM使用）"""
        
    def plan_continuation_execution(self, user_request: str, 
                                  previous_attempts: List[AttemptResult],
                                  missing_info: MissingInfoAnalysis) -> ExecutionPlan:
        """継続実行計画の立案（前回結果を踏まえた改良計画）"""
    
    # === 評価サービス ===
    def evaluate_task_satisfaction(self, original_request: str, 
                                 accumulated_results: Dict[str, Any]) -> SatisfactionEvaluation:
        """ユーザー要求満足度の客観的評価（評価専用LLM使用）"""
        
    def extract_missing_information(self, original_request: str,
                                   current_results: Dict[str, Any]) -> MissingInfoAnalysis:
        """不足情報の特定と優先順位付け（高速LLM使用）"""
    
    # === 分析サービス ===
    def analyze_execution_failure(self, execution_result: ExecutionResult,
                                context: TaskContext) -> FailureAnalysis:
        """実行失敗の原因分析と修正提案（評価LLM使用）"""
        
    def extract_task_requirements(self, user_request: str) -> List[RequirementItem]:
        """ユーザー要求からの要件抽出（高速LLM使用）"""
```

### 3.2 TaskObjective層 (構造化要求追跡)

```python
class TaskObjective:
    """ユーザー要求の構造化された追跡オブジェクト"""
    
    # 基本情報
    original_query: str                           # 元のユーザー要求
    extracted_requirements: List[RequirementItem] # LLMが抽出した要件リスト
    created_at: datetime
    
    # 進捗追跡
    iteration_count: int = 0                      # 実行回数
    max_iterations: int = 3                       # 最大試行回数
    current_satisfaction: float = 0.0             # 現在の満足度 (0.0-1.0)
    
    # 情報蓄積
    accumulated_results: Dict[str, Any] = {}      # 蓄積された実行結果
    learned_constraints: List[str] = []           # 学習した制約・教訓
    attempted_strategies: List[str] = []          # 試行済み戦略

class RequirementItem:
    """個別要件の追跡"""
    requirement: str                    # 要件内容 ("PromptSmithのシナリオ情報を提供")  
    satisfaction_level: float = 0.0    # 達成度 (0.0-1.0)
    evidence: List[str] = []           # 満たす証拠情報
    priority: int = 1                  # 優先度 (1=高, 2=中, 3=低)
    
class SatisfactionEvaluation:
    """満足度評価結果"""
    overall_score: float                    # 全体満足度 (0.0-1.0)
    requirement_scores: Dict[str, float]    # 要件別満足度
    missing_aspects: List[str]              # 不足している側面
    quality_assessment: str                 # 品質評価コメント
    completion_recommendation: bool         # 完了推奨フラグ
```

### 3.3 継続コンテキスト管理

```python
class ContinuationContext:
    """継続実行のためのコンテキスト情報"""
    
    # 前回実行情報
    previous_attempts: List[AttemptResult]      # 過去の試行結果
    execution_errors: List[ExecutionError]     # 発生したエラー
    partial_successes: List[PartialResult]     # 部分的成功結果
    
    # 改善指針
    identified_problems: List[str]              # 特定された問題
    suggested_improvements: List[str]           # 改善提案
    alternative_strategies: List[str]           # 代替戦略
    
    # 制約情報
    unavailable_resources: List[str]            # 利用不可リソース
    failed_approaches: List[str]                # 失敗したアプローチ
    learned_limitations: List[str]              # 学習した限界

class AttemptResult:
    """個別試行の結果"""
    attempt_number: int
    strategy: str                               # 使用した戦略
    execution_plan: ExecutionPlan              # 実行計画  
    results: Dict[str, Any]                    # 実行結果
    satisfaction_score: float                  # 満足度スコア
    errors: List[str]                          # 発生エラー
    lessons_learned: List[str]                 # 学んだ教訓
```

## 4. 改良された4ノードフロー

### 4.1 理解・計画ノード (継続対応)

```python
def _understanding_planning_node(self, state: AgentState) -> AgentState:
    """継続コンテキスト対応の包括的計画立案"""
    
    if state.continuation_context:
        # === 継続計画立案 ===
        rich_ui.print_step("🔄 継続計画立案フェーズ")
        
        execution_plan = self.llm_service.plan_continuation_execution(
            user_request=self.task_objective.original_query,
            previous_attempts=state.continuation_context.previous_attempts,
            missing_info=state.continuation_context.missing_info
        )
        
        # 学習した制約を計画に反映
        execution_plan.constraints = state.continuation_context.learned_limitations
        execution_plan.avoid_strategies = state.continuation_context.failed_approaches
        
        rich_ui.print_message(f"継続戦略: {execution_plan.strategy}", "info")
        
    else:
        # === 初回計画立案 ===  
        rich_ui.print_step("🧠 初回計画立案フェーズ")
        
        # ユーザー要求から要件を抽出
        self.task_objective.extracted_requirements = \
            self.llm_service.extract_task_requirements(self.task_objective.original_query)
        
        execution_plan = self.llm_service.plan_initial_execution(
            user_request=self.task_objective.original_query,
            context=TaskContext(
                workspace_info=state.workspace_info,
                available_tools=state.available_tools
            )
        )
        
        rich_ui.print_message(f"抽出要件: {len(self.task_objective.extracted_requirements)}件", "info")
    
    # 計画をコンテキストに保存
    self.four_node_context.understanding = UnderstandingResult(
        execution_plan=execution_plan,
        task_objective=self.task_objective
    )
    
    return state
```

### 4.2 評価・継続ノード (満足度ベース)

```python
def _evaluation_continuation_node(self, state: AgentState) -> AgentState:
    """LLMベース満足度評価と継続判定"""
    
    rich_ui.print_step("🔍 満足度評価フェーズ")
    
    # === 1. ユーザー要求満足度の客観的評価 ===
    satisfaction = self.llm_service.evaluate_task_satisfaction(
        original_request=self.task_objective.original_query,
        accumulated_results=self.task_objective.accumulated_results
    )
    
    rich_ui.print_message(f"満足度評価: {satisfaction.overall_score:.2f}/1.0", "info")
    
    # TaskObjectiveの更新
    self.task_objective.current_satisfaction = satisfaction.overall_score
    self.task_objective.iteration_count += 1
    
    # === 2. 完了判定 ===
    if satisfaction.overall_score >= 0.8:
        rich_ui.print_success(f"✅ タスク完了 (満足度: {satisfaction.overall_score:.2f})")
        return self._complete_task_successfully(satisfaction)
    
    # === 3. 継続限界チェック ===
    elif self.task_objective.iteration_count >= self.task_objective.max_iterations:
        rich_ui.print_warning(f"⏱️ 最大試行回数に到達 ({self.task_objective.iteration_count}回)")
        return self._escalate_to_user_guidance(satisfaction)
    
    # === 4. 継続判定と改善計画 ===
    else:
        rich_ui.print_message(f"🔄 継続実行 ({self.task_objective.iteration_count}回目)", "info")
        
        # 不足情報の詳細分析
        missing_info = self.llm_service.extract_missing_information(
            self.task_objective.original_query,
            self.task_objective.accumulated_results
        )
        
        # 継続コンテキストの構築
        continuation_context = self._build_continuation_context(satisfaction, missing_info)
        state.continuation_context = continuation_context
        
        # 学習した情報をTaskObjectiveに追加
        self.task_objective.learned_constraints.extend(missing_info.constraints)
        
        return state  # 理解・計画ノードに戻る
```

### 4.3 ユーザーエスカレーション (汎用対話)

```python
def _escalate_to_user_guidance(self, satisfaction: SatisfactionEvaluation) -> AgentState:
    """汎用的なユーザー確認・指導要請"""
    
    rich_ui.print_warning("⚠️ ユーザー指導が必要です")
    
    # 状況レポートの生成
    situation_report = self._generate_situation_report(satisfaction)
    rich_ui.print_panel(situation_report, "現在の状況", "warning")
    
    # 選択肢の提示
    options = self._generate_user_options(satisfaction)
    rich_ui.print_panel(options, "対応選択肢", "info")
    
    # ユーザー選択の取得
    while True:
        user_choice = rich_ui.get_user_input("選択 (1-5)").strip()
        
        if user_choice == "1":
            # より詳細な指示を要求
            additional_info = rich_ui.get_user_input("より詳しい要求をお聞かせください")
            return self._restart_with_additional_context(additional_info)
            
        elif user_choice == "2":
            # 代替アプローチを試行
            rich_ui.print_message("代替アプローチで再試行します", "info")
            return self._try_alternative_approach()
            
        elif user_choice == "3":
            # 部分結果で満足
            rich_ui.print_message("現在の結果で完了とします", "info")
            return self._complete_with_partial_results(satisfaction)
            
        elif user_choice == "4":
            # 専門的支援の提供
            return self._provide_technical_assistance(satisfaction)
            
        elif user_choice == "5":
            # タスクキャンセル
            rich_ui.print_message("タスクをキャンセルします", "warning")
            return self._cancel_task()
            
        else:
            rich_ui.print_warning("1-5の数字を選択してください")

def _generate_situation_report(self, satisfaction: SatisfactionEvaluation) -> str:
    """現在の状況レポート生成"""
    
    return f"""
[bold yellow]タスク実行状況レポート[/]

[bold]元の要求:[/] {self.task_objective.original_query}
[bold]試行回数:[/] {self.task_objective.iteration_count}/{self.task_objective.max_iterations}
[bold]現在の満足度:[/] {satisfaction.overall_score:.2f}/1.0

[bold red]不足している要素:[/]
{chr(10).join([f"  • {aspect}" for aspect in satisfaction.missing_aspects])}

[bold green]収集済み情報:[/]
{chr(10).join([f"  • {key}: {str(value)[:100]}..." for key, value in self.task_objective.accumulated_results.items()])}

[bold blue]品質評価:[/]
{satisfaction.quality_assessment}
"""

def _generate_user_options(self, satisfaction: SatisfactionEvaluation) -> str:
    """ユーザー選択肢の生成"""
    
    return """
[bold cyan]次の対応を選択してください:[/]

1. **詳細指示** - より具体的な要求を教えてください
2. **代替手法** - 別のアプローチで再試行します  
3. **部分完了** - 現在の結果で満足します
4. **技術支援** - 問題の詳細分析と解決策を提示します
5. **中断** - このタスクを終了します
"""
```

## 5. 実装フェーズ計画

### Phase 1: 基盤構築 (Week 1-2)
1. **LLMService基盤クラス**の実装
   - 3層LLM構成 (creative/fast/evaluator)
   - 基本サービスメソッド (plan/evaluate/analyze)
   
2. **TaskObjective構造**の導入
   - TaskObjective/RequirementItem クラス
   - SatisfactionEvaluation 構造
   
3. **既存評価ノード**の LLMService 対応
   - 技術的成功判定 → 満足度評価への変更

### Phase 2: 継続ループ機能 (Week 3-4)
1. **ContinuationContext管理**
   - 継続コンテキスト構造
   - 学習・制約管理機能
   
2. **理解・計画ノード**の継続対応
   - 初回 vs 継続の処理分岐
   - 継続計画立案ロジック
   
3. **汎用ユーザーエスカレーション**
   - 状況レポート生成
   - 選択肢提示・処理

### Phase 3: 高度化・最適化 (Week 5-6)  
1. **動的モデル選択**
   - タスク複雑度に応じたLLM選択
   - コスト・性能の最適化
   
2. **学習機能強化**
   - 成功パターンの学習
   - 失敗要因の蓄積・活用
   
3. **性能・品質向上**
   - レスポンス時間最適化
   - 評価精度向上

## 6. 期待効果

### A. **根本問題の解決**
- ✅ ユーザー要求満足度ベースの真の完了判定
- ✅ 複雑タスクに対する自動継続・改良機能
- ✅ 汎用的で拡張可能なアーキテクチャ

### B. **ユーザー体験向上**  
- ✅ 一度の指示で複雑タスクの完全遂行
- ✅ 透明性の高い進捗・状況レポート
- ✅ 適切なタイミングでの対話・確認

### C. **システム成長性**
- ✅ 経験からの自動学習・改善
- ✅ 新しいタスクタイプへの適応性
- ✅ モジュール化による保守・拡張の容易性

## 7. 成功指標

### 定量指標
- **タスク完了率**: 85% → 95% (一度の指示での完了)
- **ユーザー満足度**: 6.5/10 → 8.5/10 (評価ベース)
- **平均試行回数**: 2.3回 → 1.6回 (効率化)

### 定性指標
- **「シナリオを教えて」類の要求**: 適切な詳細情報を提供できる
- **複雑な多段階タスク**: 自動分解・継続実行できる
- **エラー時の復旧**: ユーザー介入なしで自律修正できる

---

**次のステップ**: Phase 1の実装開始
- LLMService クラスの基盤実装
- 既存システムとの統合テスト
- TaskObjective 構造の導入検証