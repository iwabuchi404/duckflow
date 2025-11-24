# LLMベースTaskProfile分類システム 設計ドキュメント

**バージョン:** 1.0  
**作成日:** 2025-08-13  
**ステータス:** 設計段階  
**目的:** 現在のルールベース分類からLLM＋ガードレールのハイブリッド分類への進化

---

## 1. 問題の背景と現状分析

### 1.1 現在のルールベース分類の限界

**現在のシステム:**
```python
# 現在のTaskProfileClassifier
class TaskProfileClassifier:
    def classify(self, user_request: str) -> ClassificationResult:
        # キーワードマッチングとスコアリングによる決定論的分類
        # 12種類のTaskProfileTypeに分類
```

**具体的な限界事例:**

| ユーザー入力 | 期待されるインテント | 現在の分類結果 | 問題 |
|------------|-------------------|---------------|------|
| "README.mdを見て" | READ (情報参照) | INFORMATION_REQUEST | ✅ 正しい |
| "README.mdをレビューして" | EVALUATE (評価・分析) | INFORMATION_REQUEST | ❌ 誤分類 |
| "README.mdを良くして" | WRITE (改善・修正) | INFORMATION_REQUEST | ❌ 誤分類 |
| "2つのファイルを比較して違いを教えて" | ANALYSIS (比較分析) | INFORMATION_REQUEST | ❌ 誤分類 |

### 1.2 自然言語の曖昧さへの対応不足

**問題1: 動詞の微妙な違い**
- 「見て」「確認して」「レビューして」「評価して」→ 全て異なる意図だが現在は同じ分類

**問題2: 文脈依存の意図**
- 「このコードについて教えて」→ 説明要求 vs. 分析要求の境界が曖昧
- 「問題を見つけて」→ バグ検出 vs. 一般的な調査の区別が困難

**問題3: 複合的な要求**
- 「コードを分析して、問題があれば修正して」→ ANALYSIS + MODIFICATION の組み合わせ

### 1.3 メンテナンス性の問題

**新しいパターンへの対応:**
```python
# 新しい要求パターンが出るたびに...
if "compare" in user_request or "比較" in user_request:
    if "差分" in user_request or "違い" in user_request:
        if "ファイル" in user_request and len(detected_files) >= 2:
            # 複雑な条件分岐が無限に増える...
```

**現在の問題:**
- 400行を超えるパターン定義
- 新しいユースケースのたびにコード修正が必要
- パターン間の相互作用が複雑で予測困難

---

## 2. LLMベース分類システムの設計

### 2.1 アーキテクチャ概要

```
📊 ユーザー入力
    ↓
🧠 LLM分類エンジン (Few-Shot Learning)
    ↓
🛡️ ガードレール検証システム
    ↓
📋 最終TaskProfile + 信頼度
```

### 2.2 LLM分類エンジンの設計

#### 2.2.1 専用LLMサービスメソッド

```python
class LLMService:
    def classify_task_profile(
        self, 
        user_request: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        LLMを使用したTaskProfile分類
        
        Args:
            user_request: ユーザーの要求文
            context: 追加コンテキスト（ファイル情報、履歴等）
            
        Returns:
            {
                "profile_type": TaskProfileType,
                "confidence": float,  # 0.0-1.0
                "reasoning": str,     # 分類理由
                "detected_intent": str,  # 詳細な意図
                "complexity_assessment": str,
                "suggested_approach": str
            }
        """
```

#### 2.2.2 Few-Shot Learning プロンプト設計

```yaml
# プロンプトテンプレート（分類特化）
task_classification_template: |
  あなたはTaskProfile分類の専門家です。ユーザーの要求を分析し、
  最適なTaskProfileを特定してください。

  【TaskProfile種別】
  1. INFORMATION_REQUEST: 情報の参照・確認・表示
  2. ANALYSIS_REQUEST: 分析・評価・調査・比較
  3. CREATION_REQUEST: 新規作成・実装・構築
  4. MODIFICATION_REQUEST: 修正・変更・改善・更新
  5. SEARCH_REQUEST: 検索・探索・発見
  6. GUIDANCE_REQUEST: 手順・方法・操作の指導

  【分類例 - Few-Shot Examples】
  
  例1:
  入力: "README.mdの内容を教えて"
  分類: INFORMATION_REQUEST
  理由: ファイル内容の確認・表示を求めている
  意図: 情報参照
  
  例2:
  入力: "README.mdをレビューして品質を評価して"
  分類: ANALYSIS_REQUEST  
  理由: レビューと評価は分析的作業
  意図: 品質分析
  
  例3:
  入力: "README.mdを改善して読みやすくして"
  分類: MODIFICATION_REQUEST
  理由: 既存ファイルの改善・修正を求めている
  意図: ファイル修正
  
  例4:
  入力: "main.pyとconfig.pyを比較して違いを教えて"
  分類: ANALYSIS_REQUEST
  理由: 2ファイルの比較分析を求めている
  意図: 比較分析
  
  例5:
  入力: "Pythonでログ機能を実装して"
  分類: CREATION_REQUEST
  理由: 新しい機能の作成を求めている
  意図: 機能実装
  
  【ユーザーの要求】
  {user_request}
  
  【分析結果をJSON形式で出力】
  {{
    "profile_type": "選択したTaskProfile",
    "confidence": 0.0から1.0の信頼度,
    "reasoning": "分類した理由の詳細説明",
    "detected_intent": "検出した具体的な意図",
    "complexity_assessment": "SIMPLE/MODERATE/COMPLEX",
    "suggested_approach": "推奨する実行アプローチ"
  }}
```

#### 2.2.3 コンテキスト拡張版プロンプト

```python
def _build_context_aware_classification_prompt(
    self, 
    user_request: str, 
    context: Dict[str, Any]
) -> str:
    """コンテキストを考慮した分類プロンプトを構築"""
    
    # 検出されたファイル情報
    detected_files = context.get("detected_files", [])
    file_context = ""
    if detected_files:
        file_context = f"検出されたファイル: {', '.join(detected_files[:5])}"
    
    # 対話履歴コンテキスト
    conversation_history = context.get("recent_messages", [])
    history_context = ""
    if conversation_history:
        recent = conversation_history[-2:]  # 直近2件
        history_context = f"直前の対話: {[msg['content'][:50] for msg in recent]}"
    
    # プロジェクト情報
    project_info = context.get("workspace_manifest", {})
    project_context = f"プロジェクト種別: {project_info.get('project_type', 'Unknown')}"
    
    return f"""
{base_prompt}

【追加コンテキスト情報】
{file_context}
{history_context}  
{project_context}

この文脈情報を考慮して、より正確な分類を行ってください。
"""
```

### 2.3 ガードレールシステムの設計

#### 2.3.1 事後検証ルール

```python
class TaskProfileGuardrail:
    """LLM分類結果の検証と修正"""
    
    def validate_and_correct(
        self, 
        user_request: str, 
        llm_result: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """LLM分類結果を検証し、必要に応じて修正"""
        
        corrected_result = llm_result.copy()
        corrections_made = []
        
        # ガードレール1: 明確な動詞パターンチェック
        corrections_made.extend(
            self._check_explicit_verb_patterns(user_request, corrected_result)
        )
        
        # ガードレール2: ファイル数と範囲の整合性
        corrections_made.extend(
            self._check_file_scope_consistency(user_request, context, corrected_result)
        )
        
        # ガードレール3: 否定的キーワードの強制修正
        corrections_made.extend(
            self._check_negative_keyword_override(user_request, corrected_result)
        )
        
        # ガードレール4: 信頼度調整
        if corrections_made:
            corrected_result["confidence"] *= 0.8  # ガードレール適用で信頼度下げ
            corrected_result["guardrail_corrections"] = corrections_made
        
        return corrected_result

    def _check_explicit_verb_patterns(self, user_request: str, result: Dict) -> List[str]:
        """明確な動詞パターンの検証"""
        corrections = []
        request_lower = user_request.lower()
        
        # 作成・実装の明確な指示
        creation_verbs = ["作成", "作って", "実装", "開発", "構築", "書いて", "生成"]
        if any(verb in request_lower for verb in creation_verbs):
            if result["profile_type"] != "CREATION_REQUEST":
                result["profile_type"] = "CREATION_REQUEST"
                corrections.append("明確な作成動詞を検出したため、CREATION_REQUESTに修正")
        
        # 修正・変更の明確な指示  
        modification_verbs = ["修正", "変更", "直して", "改修", "更新", "編集"]
        if any(verb in request_lower for verb in modification_verbs):
            if result["profile_type"] not in ["MODIFICATION_REQUEST", "CREATION_REQUEST"]:
                result["profile_type"] = "MODIFICATION_REQUEST"
                corrections.append("明確な修正動詞を検出したため、MODIFICATION_REQUESTに修正")
        
        return corrections

    def _check_file_scope_consistency(self, user_request: str, context: Dict, result: Dict) -> List[str]:
        """ファイル範囲の整合性チェック"""
        corrections = []
        detected_files = context.get("detected_files", [])
        
        # 複数ファイルが検出されているのに単一ファイル処理の場合
        if len(detected_files) >= 2:
            if "比較" in user_request or "違い" in user_request or "差分" in user_request:
                if result["profile_type"] == "INFORMATION_REQUEST":
                    result["profile_type"] = "ANALYSIS_REQUEST"
                    corrections.append("複数ファイルの比較要求のため、ANALYSIS_REQUESTに修正")
        
        return corrections

    def _check_negative_keyword_override(self, user_request: str, result: Dict) -> List[str]:
        """否定的キーワードによる修正"""
        corrections = []
        request_lower = user_request.lower()
        
        # 「見るだけ」「表示だけ」「確認だけ」の場合
        read_only_patterns = ["見るだけ", "表示だけ", "確認だけ", "内容だけ"]
        if any(pattern in request_lower for pattern in read_only_patterns):
            if result["profile_type"] != "INFORMATION_REQUEST":
                result["profile_type"] = "INFORMATION_REQUEST"
                corrections.append("読み取り専用パターンを検出したため、INFORMATION_REQUESTに修正")
        
        return corrections
```

#### 2.3.2 信頼度調整システム

```python
class ConfidenceAdjustment:
    """信頼度の動的調整"""
    
    def adjust_confidence(
        self, 
        base_confidence: float, 
        user_request: str, 
        context: Dict[str, Any]
    ) -> float:
        """様々な要因を考慮して信頼度を調整"""
        
        adjusted = base_confidence
        
        # 要因1: 要求の明確度
        clarity_score = self._assess_request_clarity(user_request)
        adjusted *= clarity_score
        
        # 要因2: コンテキスト情報の豊富さ
        context_score = self._assess_context_richness(context)
        adjusted *= context_score
        
        # 要因3: Few-Shot例との類似度
        similarity_score = self._assess_similarity_to_examples(user_request)
        adjusted *= similarity_score
        
        return max(0.1, min(1.0, adjusted))  # 0.1-1.0の範囲に制限

    def _assess_request_clarity(self, user_request: str) -> float:
        """要求の明確度評価"""
        # 長さによる評価
        if len(user_request) < 10:
            return 0.7  # 短すぎる要求は不明確
        elif len(user_request) > 200:
            return 0.9  # 詳細な要求は明確
        
        # 具体的な動詞の存在
        specific_verbs = ["作成", "修正", "分析", "比較", "実装", "説明"]
        if any(verb in user_request for verb in specific_verbs):
            return 1.0
        
        return 0.8  # 標準的な明確度

    def _assess_context_richness(self, context: Dict[str, Any]) -> float:
        """コンテキスト情報の豊富さ評価"""
        score = 0.5  # ベーススコア
        
        if context.get("detected_files"):
            score += 0.2
        if context.get("recent_messages"):
            score += 0.2
        if context.get("workspace_manifest"):
            score += 0.1
        
        return min(1.0, score)
```

---

## 3. ハイブリッドアプローチの実装

### 3.1 統合分類システム

```python
class HybridTaskProfileClassifier:
    """LLM + ガードレールのハイブリッド分類システム"""
    
    def __init__(self):
        self.llm_service = llm_service
        self.guardrail = TaskProfileGuardrail()
        self.confidence_adjuster = ConfidenceAdjustment()
        self.fallback_classifier = TaskProfileClassifier()  # 既存のルールベース
    
    def classify(self, user_request: str, context: Optional[Dict[str, Any]] = None) -> ClassificationResult:
        """ハイブリッド分類の実行"""
        
        try:
            # Step 1: LLM分類の実行
            llm_result = self.llm_service.classify_task_profile(user_request, context or {})
            
            # Step 2: ガードレール検証・修正
            validated_result = self.guardrail.validate_and_correct(
                user_request, llm_result, context or {}
            )
            
            # Step 3: 信頼度の動的調整
            adjusted_confidence = self.confidence_adjuster.adjust_confidence(
                validated_result["confidence"], user_request, context or {}
            )
            
            # Step 4: 低信頼度の場合はルールベースフォールバック
            if adjusted_confidence < 0.6:
                fallback_result = self.fallback_classifier.classify(user_request)
                return self._merge_llm_and_rule_results(validated_result, fallback_result)
            
            # Step 5: 最終結果の構築
            return ClassificationResult(
                profile_type=TaskProfileType(validated_result["profile_type"]),
                confidence=adjusted_confidence,
                detected_patterns=validated_result.get("guardrail_corrections", []),
                extracted_targets=self._extract_targets_from_llm(validated_result),
                reasoning=self._build_hybrid_reasoning(validated_result, adjusted_confidence)
            )
            
        except Exception as e:
            # エラー時は完全にルールベースにフォールバック
            logger.warning(f"LLM分類エラー、ルールベースにフォールバック: {e}")
            return self.fallback_classifier.classify(user_request)

    def _merge_llm_and_rule_results(
        self, 
        llm_result: Dict[str, Any], 
        rule_result: ClassificationResult
    ) -> ClassificationResult:
        """LLMとルールベースの結果をマージ"""
        
        # より高い信頼度の結果を採用
        if llm_result["confidence"] >= rule_result.confidence:
            final_profile = TaskProfileType(llm_result["profile_type"])
            final_confidence = llm_result["confidence"]
            reasoning = f"LLM分類採用: {llm_result.get('reasoning', '')}"
        else:
            final_profile = rule_result.profile_type
            final_confidence = rule_result.confidence
            reasoning = f"ルールベース採用: {rule_result.reasoning}"
        
        return ClassificationResult(
            profile_type=final_profile,
            confidence=final_confidence,
            detected_patterns=[f"hybrid_merge: LLM={llm_result['confidence']:.2f}, Rule={rule_result.confidence:.2f}"],
            extracted_targets=rule_result.extracted_targets,
            reasoning=reasoning
        )
```

### 3.2 段階的移行戦略

#### Phase 1: LLM分類システムの基盤構築
```python
# 1. LLMServiceへの分類メソッド追加
def classify_task_profile(self, user_request: str, context: Optional[Dict] = None) -> Dict[str, Any]

# 2. Few-Shot プロンプトテンプレート作成
# config/prompts/task_classification.yaml

# 3. 基本的なPydanticOutputParser統合
```

#### Phase 2: ガードレールシステム実装
```python
# 1. TaskProfileGuardrailクラス作成
# 2. 事後検証ルールの実装
# 3. 信頼度調整システム実装
```

#### Phase 3: ハイブリッドシステム統合
```python
# 1. HybridTaskProfileClassifier実装
# 2. 既存システムとの互換性確保
# 3. フォールバック機能の実装
```

#### Phase 4: 段階的置き換え
```python
# 設定フラグによる段階的移行
class TaskProfileConfig:
    USE_LLM_CLASSIFICATION: bool = True      # LLM分類の有効化
    LLM_CONFIDENCE_THRESHOLD: float = 0.6   # フォールバック閾値
    ENABLE_GUARDRAILS: bool = True          # ガードレールの有効化
    FALLBACK_TO_RULES: bool = True          # ルールベースフォールバックの有効化
```

---

## 4. 期待される改善効果

### 4.1 分類精度の向上

**Before (ルールベース)**
```
"README.mdをレビューして" → INFORMATION_REQUEST (誤分類)
"2ファイルを比較して" → INFORMATION_REQUEST (誤分類)
```

**After (LLM+ガードレール)**
```
"README.mdをレビューして" → ANALYSIS_REQUEST ✅
"2ファイルを比較して" → ANALYSIS_REQUEST ✅
```

### 4.2 メンテナンス性の向上

**新しいパターンへの対応**
```yaml
# プロンプトに新しい例を1行追加するだけ
- 例N: "ファイルAとBを比較してマージして" → MODIFICATION_REQUEST
```

**既存のコード変更不要**

### 4.3 柔軟性の向上

- **文脈理解**: 対話履歴やプロジェクト情報を考慮した分類
- **複合要求対応**: 複数の意図が混在する要求の適切な処理
- **自然な表現対応**: より人間らしい自然な要求文の理解

### 4.4 安全性の確保

- **ガードレール**: 致命的な誤分類の防止
- **フォールバック**: LLMエラー時のルールベース代替
- **信頼度調整**: 不確実な分類の検出と対応

---

## 5. 実装スケジュールと優先度

### 5.1 優先度 High - 即座実装

**1. LLMService拡張 (1日)**
- `classify_task_profile()` メソッド追加
- Few-Shot プロンプトテンプレート作成
- 基本的なJSON出力パーサー実装

**2. 基本ガードレール (1日)** 
- 明確な動詞パターンチェック
- ファイル範囲整合性チェック
- 否定キーワード修正

### 5.2 優先度 Medium - 1週間以内

**3. ハイブリッドシステム統合**
- HybridTaskProfileClassifier実装
- 既存システムとの互換性確保
- 設定ベースの段階的移行機能

**4. 高度なガードレール**
- 信頼度動的調整システム
- コンテキスト拡張プロンプト
- LLM-ルール結果マージ機能

### 5.3 優先度 Low - 将来実装

**5. 学習・改善システム**
- 分類結果のフィードバック収集
- Few-Shot例の動的更新
- A/Bテストフレームワーク

---

## 6. リスク分析と対策

### 6.1 潜在的リスク

**1. LLMレスポンス時間**
- リスク: 分類に時間がかかりUX低下
- 対策: fast_llm使用、キャッシュ機能、並列処理

**2. LLM出力の不安定性**
- リスク: JSON解析エラー、予期しない出力
- 対策: 強力なガードレール、フォールバック機能

**3. コスト増加**
- リスク: LLM API呼び出しによるコスト上昇
- 対策: 軽量モデル使用、結果キャッシュ、バッチ処理

### 6.2 対策の詳細

**フォールバック戦略:**
```python
try:
    llm_result = self.llm_service.classify_task_profile(user_request)
except (APIError, TimeoutError, ParseError) as e:
    logger.warning(f"LLM分類失敗、ルールベースで代替: {e}")
    return self.fallback_classifier.classify(user_request)
```

**結果検証:**
```python
if not self._is_valid_classification_result(llm_result):
    logger.warning("無効なLLM分類結果を検出")
    return self.fallback_classifier.classify(user_request)
```

---

## 7. 成功指標と評価方法

### 7.1 定量的指標

**分類精度**
- 目標: 現在の75% → 90%以上
- 測定方法: テストケースセットによる自動評価

**レスポンス時間**
- 目標: 平均1秒以内
- 測定方法: パフォーマンステスト

**システム可用性**
- 目標: 99.5%以上 (フォールバック含む)
- 測定方法: 監視・ログ分析

### 7.2 定性的評価

**ユーザビリティ**
- より自然な言語での要求が可能
- 複雑な要求の適切な理解

**保守性**
- 新しいパターンへの対応工数削減
- コードベースの複雑度改善

---

## 8. まとめ

このLLMベースTaskProfile分類システムは、**AIの知性とプログラムの信頼性を両立**する革新的なアプローチです。

**核心的価値:**
1. **柔軟性**: 自然言語の微妙なニュアンスを理解
2. **安全性**: ガードレールによる誤分類防止
3. **拡張性**: 新しいパターンへの簡単な対応
4. **信頼性**: フォールバック機能による高い可用性

この設計により、Duckflowはより人間らしく、より正確で、より保守しやすいAIアシスタントへと進化します。

---

*本ドキュメントは、実装の進捗に応じて継続的に更新されます。*