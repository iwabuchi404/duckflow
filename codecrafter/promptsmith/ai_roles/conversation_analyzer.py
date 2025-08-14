"""
Conversation Analyzer - 対話ログの詳細分析と改善ポイント抽出

対話の流れ、意図理解、コミュニケーション品質を詳細に分析し、
PromptSmithの改善に活用する情報を提供します。
"""

import re
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import statistics
from collections import Counter


@dataclass
class IntentAnalysis:
    """意図分析結果"""
    understood_correctly: bool
    confidence_score: float  # 0.0-1.0
    ambiguity_level: str    # low, medium, high
    clarification_needed: List[str]
    misunderstanding_points: List[str]


@dataclass
class ConfusionPoint:
    """混乱・誤解ポイント"""
    message_index: int
    confusion_type: str     # misunderstanding, ambiguity, technical_gap
    description: str
    context: str
    severity: str          # low, medium, high


@dataclass
class FlowAnalysis:
    """タスク完了フロー分析"""
    stages_completed: List[str]
    missing_stages: List[str]
    stage_transitions: List[Tuple[str, str]]  # (from_stage, to_stage)
    efficiency_score: float  # 0.0-1.0
    bottlenecks: List[str]


class ConversationAnalyzer:
    """対話ログの詳細分析と改善ポイント抽出"""
    
    def __init__(self):
        """ConversationAnalyzerの初期化"""
        self.intent_keywords = self._load_intent_keywords()
        self.confusion_patterns = self._load_confusion_patterns()
        self.flow_stages = self._define_flow_stages()
        self.quality_indicators = self._define_quality_indicators()
        
        # 高度な分析用の新しい属性
        self.sentiment_patterns = self._load_sentiment_patterns()
        self.task_complexity_indicators = self._load_task_complexity_indicators()
        self.communication_efficiency_patterns = self._load_communication_efficiency_patterns()
    
    def analyze_intent_understanding(self, conversation: List[Dict]) -> float:
        """
        意図理解率の算出
        
        Args:
            conversation: 対話ログ
            
        Returns:
            意図理解率 (0.0-1.0)
        """
        if not conversation:
            return 0.0
        
        intent_analysis = self._perform_intent_analysis(conversation)
        
        # 複数の指標から総合的な理解率を算出
        understanding_indicators = {
            "correct_initial_response": 0.3,      # 初期応答の適切性
            "clarification_quality": 0.25,        # 明確化質問の品質
            "requirement_coverage": 0.25,          # 要求事項のカバー率
            "misunderstanding_penalty": -0.2      # 誤解によるペナルティ
        }
        
        scores = self._calculate_understanding_scores(conversation, intent_analysis)
        
        total_score = sum(scores[indicator] * weight 
                         for indicator, weight in understanding_indicators.items()
                         if indicator in scores)
        
        return max(0.0, min(1.0, total_score))
    
    def detect_confusion_points(self, conversation: List[Dict]) -> List[ConfusionPoint]:
        """
        混乱・誤解ポイントの検出
        
        Args:
            conversation: 対話ログ
            
        Returns:
            検出された混乱ポイントのリスト
        """
        confusion_points = []
        
        for i, message in enumerate(conversation):
            content = message.get("content", "")
            role = message.get("role", "")
            
            # ユーザーからの混乱・不満の兆候
            if role == "user":
                confusion_points.extend(
                    self._detect_user_confusion(content, i)
                )
            
            # アシスタントの曖昧・不適切な応答
            elif role == "assistant":
                confusion_points.extend(
                    self._detect_assistant_issues(content, i)
                )
        
        # 重要度順でソート
        confusion_points.sort(key=lambda x: {"high": 3, "medium": 2, "low": 1}[x.severity], reverse=True)
        
        return confusion_points
    
    def measure_question_quality(self, questions: List[str]) -> Dict[str, Any]:
        """
        質問品質の評価
        
        Args:
            questions: 質問のリスト
            
        Returns:
            質問品質の分析結果
        """
        if not questions:
            return {
                "overall_quality": 0.0,
                "question_types": {},
                "effectiveness_score": 0.0,
                "recommendations": ["明確化のための質問を増やしてください"]
            }
        
        # 質問タイプの分類
        question_types = self._classify_questions(questions)
        
        # 品質指標の計算
        quality_metrics = {
            "specificity": self._measure_question_specificity(questions),
            "relevance": self._measure_question_relevance(questions),
            "completeness": self._measure_question_completeness(questions, question_types),
            "clarity": self._measure_question_clarity(questions)
        }
        
        # 総合品質スコア
        overall_quality = statistics.mean(quality_metrics.values())
        
        # 効果性スコア（質問タイプの多様性も考慮）
        type_diversity = len(question_types) / len(self._get_expected_question_types())
        effectiveness_score = (overall_quality * 0.7 + type_diversity * 0.3)
        
        recommendations = self._generate_question_recommendations(quality_metrics, question_types)
        
        return {
            "overall_quality": overall_quality,
            "quality_metrics": quality_metrics,
            "question_types": question_types,
            "type_diversity": type_diversity,
            "effectiveness_score": effectiveness_score,
            "recommendations": recommendations
        }
    
    def track_task_completion_flow(self, conversation: List[Dict]) -> FlowAnalysis:
        """
        タスク完了までのフロー分析
        
        Args:
            conversation: 対話ログ
            
        Returns:
            フロー分析結果
        """
        # 各ステージの検出
        detected_stages = self._detect_conversation_stages(conversation)
        
        # 期待されるフローとの比較
        expected_stages = ["understanding", "clarification", "planning", "implementation", "validation"]
        completed_stages = list(detected_stages.keys())
        missing_stages = [stage for stage in expected_stages if stage not in completed_stages]
        
        # ステージ遷移の分析
        stage_transitions = self._analyze_stage_transitions(detected_stages)
        
        # 効率性の評価
        efficiency_score = self._calculate_flow_efficiency(detected_stages, expected_stages)
        
        # ボトルネックの特定
        bottlenecks = self._identify_bottlenecks(detected_stages, conversation)
        
        return FlowAnalysis(
            stages_completed=completed_stages,
            missing_stages=missing_stages,
            stage_transitions=stage_transitions,
            efficiency_score=efficiency_score,
            bottlenecks=bottlenecks
        )
    
    def _perform_intent_analysis(self, conversation: List[Dict]) -> IntentAnalysis:
        """意図分析の実行"""
        if not conversation:
            return IntentAnalysis(False, 0.0, "high", [], ["対話データなし"])
        
        # 最初のユーザーメッセージから意図を抽出
        first_user_msg = None
        for msg in conversation:
            if msg.get("role") == "user":
                first_user_msg = msg.get("content", "")
                break
        
        if not first_user_msg:
            return IntentAnalysis(False, 0.0, "high", [], ["ユーザー要求が不明"])
        
        # 意図の明確性を評価
        ambiguity_level = self._assess_ambiguity_level(first_user_msg)
        
        # アシスタントの初期応答が適切かチェック
        first_response = None
        for msg in conversation[1:]:
            if msg.get("role") == "assistant":
                first_response = msg.get("content", "")
                break
        
        understood_correctly = self._check_initial_understanding(first_user_msg, first_response)
        
        # 信頼度スコアの計算
        confidence_score = self._calculate_confidence_score(
            understood_correctly, ambiguity_level, len(conversation)
        )
        
        # 明確化が必要な項目
        clarification_needed = self._identify_clarification_needs(first_user_msg)
        
        # 誤解ポイント
        misunderstanding_points = self._identify_misunderstandings(conversation)
        
        return IntentAnalysis(
            understood_correctly=understood_correctly,
            confidence_score=confidence_score,
            ambiguity_level=ambiguity_level,
            clarification_needed=clarification_needed,
            misunderstanding_points=misunderstanding_points
        )
    
    def _calculate_understanding_scores(self, conversation: List[Dict], 
                                      intent_analysis: IntentAnalysis) -> Dict[str, float]:
        """理解度スコアの計算"""
        scores = {}
        
        # 初期応答の適切性
        scores["correct_initial_response"] = 1.0 if intent_analysis.understood_correctly else 0.0
        
        # 明確化質問の品質
        questions = self._extract_questions_from_conversation(conversation)
        question_quality = self.measure_question_quality(questions)
        scores["clarification_quality"] = question_quality["effectiveness_score"]
        
        # 要求事項のカバー率
        scores["requirement_coverage"] = self._calculate_requirement_coverage(conversation)
        
        # 誤解によるペナルティ
        misunderstanding_count = len(intent_analysis.misunderstanding_points)
        scores["misunderstanding_penalty"] = min(0.0, -0.1 * misunderstanding_count)
        
        return scores
    
    def _detect_user_confusion(self, content: str, message_index: int) -> List[ConfusionPoint]:
        """ユーザーの混乱検出"""
        confusion_points = []
        
        # 混乱を示すパターン
        confusion_indicators = {
            "direct_confusion": [
                r"分からない", r"理解できない", r"混乱", r"よく分からない",
                r"何を意味", r"どういう意味", r"説明がよく分からない"
            ],
            "dissatisfaction": [
                r"違います", r"そうじゃない", r"期待していたのと違う",
                r"思っていたのと違う", r"求めているものと違う"
            ],
            "request_clarification": [
                r"もう一度", r"再度説明", r"詳しく教えて",
                r"もっと具体的に", r"例を", r"サンプル"
            ]
        }
        
        for confusion_type, patterns in confusion_indicators.items():
            for pattern in patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    confusion_points.append(ConfusionPoint(
                        message_index=message_index,
                        confusion_type=confusion_type,
                        description=f"ユーザーが{confusion_type}を示している",
                        context=content[:100] + "..." if len(content) > 100 else content,
                        severity="high" if confusion_type == "direct_confusion" else "medium"
                    ))
                    break  # 同じタイプは1つだけカウント
        
        return confusion_points
    
    def _detect_assistant_issues(self, content: str, message_index: int) -> List[ConfusionPoint]:
        """アシスタントの問題検出"""
        issues = []
        
        # 問題のあるパターン
        issue_patterns = {
            "vague_response": [
                r"^.{0,50}$",  # 短すぎる応答
                r"よくわからない", r"難しいです", r"できません"
            ],
            "technical_jargon": [
                r"(?:API|SDK|HTTP|JSON|SQL|CSS|HTML){3,}",  # 専門用語の連続
            ],
            "assumption_without_confirmation": [
                r"だと思います", r"たぶん", r"おそらく", r"推測ですが"
            ]
        }
        
        # 短すぎる応答
        if len(content.strip()) < 50:
            issues.append(ConfusionPoint(
                message_index=message_index,
                confusion_type="vague_response",
                description="応答が短すぎて詳細が不足",
                context=content,
                severity="medium"
            ))
        
        # 専門用語の多用（説明不足）
        technical_terms = re.findall(r'\b(?:API|SDK|HTTP|JSON|SQL|CSS|HTML|JavaScript|Python|React|Vue|Angular)\b', content, re.IGNORECASE)
        if len(technical_terms) > 5:
            issues.append(ConfusionPoint(
                message_index=message_index,
                confusion_type="technical_jargon",
                description="専門用語が多く、説明が不足している可能性",
                context=f"検出された専門用語: {', '.join(set(technical_terms))}",
                severity="low"
            ))
        
        return issues
    
    def _classify_questions(self, questions: List[str]) -> Dict[str, int]:
        """質問の分類"""
        question_types = {
            "requirement_clarification": 0,  # 要求明確化
            "technical_specification": 0,    # 技術仕様確認
            "preference_inquiry": 0,         # 好み・選択肢の確認
            "confirmation": 0,               # 確認質問
            "constraint_verification": 0     # 制約条件の確認
        }
        
        type_patterns = {
            "requirement_clarification": [
                r"どのような機能", r"何を", r"どんな", r"具体的には",
                r"要件", r"仕様", r"どういった"
            ],
            "technical_specification": [
                r"どの技術", r"どの言語", r"どのフレームワーク",
                r"データベース", r"サーバー", r"環境"
            ],
            "preference_inquiry": [
                r"お好み", r"希望", r"どちらが良い", r"選択",
                r"どのスタイル", r"どのデザイン"
            ],
            "confirmation": [
                r"よろしいでしょうか", r"で合っています", r"確認ですが",
                r"理解は正しい", r"これで良い"
            ],
            "constraint_verification": [
                r"制約", r"制限", r"予算", r"期限", r"リソース",
                r"制限事項", r"条件"
            ]
        }
        
        for question in questions:
            for q_type, patterns in type_patterns.items():
                if any(re.search(pattern, question, re.IGNORECASE) for pattern in patterns):
                    question_types[q_type] += 1
                    break  # 最初にマッチしたタイプのみ
        
        return question_types
    
    def _measure_question_specificity(self, questions: List[str]) -> float:
        """質問の具体性を測定"""
        if not questions:
            return 0.0
        
        specific_indicators = [
            r"具体的に", r"詳しく", r"例えば", r"サンプル",
            r"どのような", r"いくつ", r"どれくらい"
        ]
        
        specific_count = 0
        for question in questions:
            if any(re.search(indicator, question, re.IGNORECASE) for indicator in specific_indicators):
                specific_count += 1
        
        return specific_count / len(questions)
    
    def _measure_question_relevance(self, questions: List[str]) -> float:
        """質問の関連性を測定"""
        # 簡単な実装：開発・実装関連のキーワードの存在率
        relevant_keywords = [
            "機能", "仕様", "要件", "設計", "実装", "テスト",
            "データ", "画面", "処理", "システム", "ユーザー"
        ]
        
        if not questions:
            return 0.0
        
        relevant_count = 0
        for question in questions:
            if any(keyword in question for keyword in relevant_keywords):
                relevant_count += 1
        
        return relevant_count / len(questions)
    
    def _measure_question_completeness(self, questions: List[str], 
                                     question_types: Dict[str, int]) -> float:
        """質問の完全性を測定"""
        expected_types = ["requirement_clarification", "technical_specification", "confirmation"]
        covered_types = [q_type for q_type, count in question_types.items() if count > 0]
        
        completeness = len([t for t in expected_types if t in covered_types]) / len(expected_types)
        
        # 質問数によるボーナス（適度な数の質問）
        question_count_bonus = min(1.0, len(questions) / 5.0)  # 5問で最大ボーナス
        
        return (completeness * 0.7 + question_count_bonus * 0.3)
    
    def _measure_question_clarity(self, questions: List[str]) -> float:
        """質問の明確性を測定"""
        if not questions:
            return 0.0
        
        clarity_indicators = {
            "clear_structure": [r"^.+？$", r"でしょうか$", r"ですか$"],  # 明確な疑問文
            "specific_terms": [r"どの", r"何", r"いつ", r"どこ", r"なぜ", r"どのように"],
            "context_provided": [r"について", r"に関して", r"の件で"]
        }
        
        total_score = 0.0
        for question in questions:
            question_score = 0.0
            for category, patterns in clarity_indicators.items():
                if any(re.search(pattern, question) for pattern in patterns):
                    question_score += 1.0
            
            # 文の長さも考慮（短すぎず長すぎず）
            length_score = 1.0 if 10 <= len(question) <= 100 else 0.5
            question_score += length_score
            
            total_score += min(1.0, question_score / len(clarity_indicators))
        
        return total_score / len(questions)
    
    def _get_expected_question_types(self) -> List[str]:
        """期待される質問タイプのリスト"""
        return [
            "requirement_clarification",
            "technical_specification", 
            "preference_inquiry",
            "confirmation",
            "constraint_verification"
        ]
    
    def _generate_question_recommendations(self, quality_metrics: Dict[str, float],
                                         question_types: Dict[str, int]) -> List[str]:
        """質問改善の推奨事項生成"""
        recommendations = []
        
        if quality_metrics["specificity"] < 0.5:
            recommendations.append("より具体的な質問を心がけてください")
        
        if quality_metrics["relevance"] < 0.7:
            recommendations.append("開発要件により関連した質問を増やしてください")
        
        if quality_metrics["completeness"] < 0.6:
            recommendations.append("要件明確化、技術仕様、確認質問をバランスよく行ってください")
        
        if sum(question_types.values()) < 2:
            recommendations.append("明確化のための質問を増やしてください")
        
        if not recommendations:
            recommendations.append("質問品質は良好です。現在のアプローチを継続してください")
        
        return recommendations
    
    def _extract_questions_from_conversation(self, conversation: List[Dict]) -> List[str]:
        """対話から質問を抽出"""
        questions = []
        
        for message in conversation:
            if message.get("role") == "assistant":
                content = message.get("content", "")
                # 日本語の疑問文を抽出
                question_patterns = [
                    r'[^。]*？',
                    r'[^。]*でしょうか[。？]?',
                    r'[^。]*ですか[。？]?',
                    r'[^。]*ませんか[。？]?'
                ]
                
                for pattern in question_patterns:
                    matches = re.findall(pattern, content)
                    questions.extend([match.strip() for match in matches if len(match.strip()) > 5])
        
        return list(set(questions))  # 重複削除
    
    def _calculate_requirement_coverage(self, conversation: List[Dict]) -> float:
        """要求事項カバー率の計算"""
        # 簡単な実装：重要な要素の言及率
        important_aspects = [
            "機能", "仕様", "デザイン", "データ", "ユーザー",
            "パフォーマンス", "セキュリティ", "テスト"
        ]
        
        all_content = " ".join([msg.get("content", "") for msg in conversation])
        covered_aspects = [aspect for aspect in important_aspects if aspect in all_content]
        
        return len(covered_aspects) / len(important_aspects)
    
    def _identify_misunderstandings(self, conversation: List[Dict]) -> List[str]:
        """誤解ポイントの特定"""
        misunderstandings = []
        
        # ユーザーからの修正・否定的反応を検出
        correction_patterns = [
            r"違います", r"そうじゃない", r"間違っています",
            r"期待していたのと違う", r"そんなことは言っていない"
        ]
        
        for message in conversation:
            if message.get("role") == "user":
                content = message.get("content", "")
                for pattern in correction_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        misunderstandings.append(f"ユーザー修正: {content[:50]}...")
        
        return misunderstandings
    
    def _assess_ambiguity_level(self, user_request: str) -> str:
        """要求の曖昧さレベルを評価"""
        # 曖昧さを示す指標
        ambiguity_indicators = [
            r"なんか", r"よくある", r"普通の", r"適当に",
            r"よろしく", r"お任せ", r"簡単な", r"基本的な"
        ]
        
        specific_indicators = [
            r"具体的に", r"詳細", r"仕様書", r"要件定義",
            r"\d+", r"色：", r"サイズ：", r"機能："
        ]
        
        ambiguous_count = sum(1 for pattern in ambiguity_indicators 
                            if re.search(pattern, user_request, re.IGNORECASE))
        specific_count = sum(1 for pattern in specific_indicators 
                           if re.search(pattern, user_request, re.IGNORECASE))
        
        if specific_count >= 2:
            return "low"
        elif ambiguous_count >= 2:
            return "high"
        else:
            return "medium"
    
    def _check_initial_understanding(self, user_request: str, assistant_response: str) -> bool:
        """初期理解の正確性をチェック"""
        if not assistant_response:
            return False
        
        # 簡単な実装：キーワードの一致度
        user_keywords = re.findall(r'\w+', user_request.lower())
        response_keywords = re.findall(r'\w+', assistant_response.lower())
        
        common_keywords = set(user_keywords) & set(response_keywords)
        
        # 適切な応答の兆候
        good_response_indicators = [
            "理解しました", "確認", "質問", "詳しく", "具体的"
        ]
        
        has_good_indicators = any(indicator in assistant_response 
                                for indicator in good_response_indicators)
        
        return len(common_keywords) >= 2 or has_good_indicators
    
    def _calculate_confidence_score(self, understood_correctly: bool, 
                                  ambiguity_level: str, conversation_length: int) -> float:
        """信頼度スコアの計算"""
        base_score = 0.8 if understood_correctly else 0.3
        
        # 曖昧さによる調整
        ambiguity_penalty = {"low": 0.0, "medium": -0.1, "high": -0.2}[ambiguity_level]
        
        # 対話長による調整（長い対話は複雑さを示唆）
        length_factor = max(0.0, 1.0 - (conversation_length - 10) * 0.02)
        
        return max(0.0, min(1.0, (base_score + ambiguity_penalty) * length_factor))
    
    def _identify_clarification_needs(self, user_request: str) -> List[str]:
        """明確化が必要な項目の特定"""
        needs = []
        
        # 技術的詳細が不足している場合
        if not re.search(r'言語|フレームワーク|技術|環境', user_request):
            needs.append("使用技術・環境の確認")
        
        # 機能詳細が不足している場合
        if re.search(r'システム|アプリ|ツール', user_request) and not re.search(r'機能|できる', user_request):
            needs.append("具体的な機能要件の確認")
        
        # デザイン・UI要件が不明
        if re.search(r'ウェブ|サイト|画面', user_request) and not re.search(r'デザイン|色|レイアウト', user_request):
            needs.append("デザイン・UI要件の確認")
        
        return needs
    
    def _detect_conversation_stages(self, conversation: List[Dict]) -> Dict[str, List[int]]:
        """対話ステージの検出"""
        stages = {
            "understanding": [],
            "clarification": [], 
            "planning": [],
            "implementation": [],
            "validation": [],
            "completion": []
        }
        
        stage_keywords = {
            "understanding": ["理解", "把握", "確認", "了解"],
            "clarification": ["質問", "詳しく", "具体的", "明確"],
            "planning": ["計画", "設計", "構成", "アプローチ", "手順"],
            "implementation": ["実装", "作成", "開発", "コード", "ファイル"],
            "validation": ["テスト", "確認", "検証", "動作", "チェック"],
            "completion": ["完了", "終了", "完成", "納品", "提供"]
        }
        
        for i, message in enumerate(conversation):
            content = message.get("content", "").lower()
            for stage, keywords in stage_keywords.items():
                if any(keyword in content for keyword in keywords):
                    stages[stage].append(i)
        
        return {stage: indices for stage, indices in stages.items() if indices}
    
    def _analyze_stage_transitions(self, detected_stages: Dict[str, List[int]]) -> List[Tuple[str, str]]:
        """ステージ遷移の分析"""
        # 各ステージの最初の出現位置を取得
        stage_first_appearance = {stage: min(indices) for stage, indices in detected_stages.items()}
        
        # 時系列順にソート
        sorted_stages = sorted(stage_first_appearance.items(), key=lambda x: x[1])
        
        # 遷移のペアを作成
        transitions = []
        for i in range(len(sorted_stages) - 1):
            current_stage = sorted_stages[i][0]
            next_stage = sorted_stages[i + 1][0]
            transitions.append((current_stage, next_stage))
        
        return transitions
    
    def _calculate_flow_efficiency(self, detected_stages: Dict[str, List[int]], 
                                 expected_stages: List[str]) -> float:
        """フロー効率性の計算"""
        completed_expected = len([stage for stage in expected_stages if stage in detected_stages])
        stage_coverage = completed_expected / len(expected_stages)
        
        # 理想的な順序との比較
        actual_order = [stage for stage in expected_stages if stage in detected_stages]
        order_penalty = 0
        for i in range(len(actual_order) - 1):
            current_idx = expected_stages.index(actual_order[i])
            next_idx = expected_stages.index(actual_order[i + 1])
            if next_idx < current_idx:  # 逆順の場合
                order_penalty += 0.1
        
        efficiency = max(0.0, stage_coverage - order_penalty)
        return efficiency
    
    def _identify_bottlenecks(self, detected_stages: Dict[str, List[int]], 
                            conversation: List[Dict]) -> List[str]:
        """ボトルネックの特定"""
        bottlenecks = []
        
        # 長時間同じステージに留まっている
        for stage, indices in detected_stages.items():
            if len(indices) > len(conversation) * 0.3:  # 30%以上を占める
                bottlenecks.append(f"{stage}ステージが長期化")
        
        # 期待されるステージが欠けている
        expected_stages = ["understanding", "planning", "implementation"]
        for stage in expected_stages:
            if stage not in detected_stages:
                bottlenecks.append(f"{stage}ステージが欠如")
        
        return bottlenecks
    
    def _load_intent_keywords(self) -> Dict[str, List[str]]:
        """意図キーワードのロード"""
        return {
            "create": ["作る", "作成", "構築", "開発", "実装"],
            "modify": ["修正", "変更", "改善", "更新", "調整"],
            "analyze": ["分析", "解析", "調査", "検証", "確認"],
            "explain": ["説明", "教える", "解説", "詳細", "方法"]
        }
    
    def _load_confusion_patterns(self) -> Dict[str, List[str]]:
        """混乱パターンのロード"""
        return {
            "direct": ["分からない", "理解できない", "混乱"],
            "indirect": ["違う", "そうじゃない", "期待と違う"],
            "request_help": ["助けて", "どうすれば", "サポート"]
        }
    
    def _define_flow_stages(self) -> List[str]:
        """フローステージの定義"""
        return [
            "understanding",    # 理解・把握
            "clarification",   # 明確化・質問
            "planning",        # 計画・設計
            "implementation",  # 実装・開発
            "validation",      # 検証・テスト
            "completion"       # 完了・納品
        ]
    
    def _define_quality_indicators(self) -> Dict[str, List[str]]:
        """品質指標の定義"""
        return {
            "positive": ["良い", "素晴らしい", "完璧", "期待通り"],
            "negative": ["悪い", "問題", "エラー", "失敗"],
            "neutral": ["普通", "まあまあ", "それなり"]
        }
    
    # ====== Phase 2: 高度な対話分析メソッド ======
    
    def analyze_sentiment_progression(self, conversation: List[Dict]) -> Dict[str, Any]:
        """
        対話中のセンチメント変化を分析
        
        Args:
            conversation: 対話ログ
            
        Returns:
            センチメント分析結果
        """
        if not conversation:
            return {"sentiment_trend": "neutral", "satisfaction_score": 0.5, "frustration_points": []}
        
        sentiment_scores = []
        frustration_points = []
        
        for i, message in enumerate(conversation):
            if message.get("role") == "user":
                content = message.get("content", "").lower()
                score = self._calculate_message_sentiment(content)
                sentiment_scores.append(score)
                
                # フラストレーション検出
                if score < 0.3:
                    frustration_points.append({
                        "message_index": i,
                        "content_preview": content[:100],
                        "sentiment_score": score,
                        "detected_frustration_type": self._detect_frustration_type(content)
                    })
        
        # トレンド分析
        if len(sentiment_scores) >= 3:
            early_avg = statistics.mean(sentiment_scores[:len(sentiment_scores)//3])
            late_avg = statistics.mean(sentiment_scores[-len(sentiment_scores)//3:])
            
            if late_avg > early_avg + 0.1:
                trend = "improving"
            elif late_avg < early_avg - 0.1:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"
        
        overall_satisfaction = statistics.mean(sentiment_scores) if sentiment_scores else 0.5
        
        return {
            "sentiment_trend": trend,
            "satisfaction_score": overall_satisfaction,
            "frustration_points": frustration_points,
            "sentiment_progression": sentiment_scores,
            "early_late_comparison": {
                "early_avg": statistics.mean(sentiment_scores[:3]) if len(sentiment_scores) >= 3 else None,
                "late_avg": statistics.mean(sentiment_scores[-3:]) if len(sentiment_scores) >= 3 else None
            }
        }
    
    def analyze_task_complexity_handling(self, conversation: List[Dict]) -> Dict[str, Any]:
        """
        タスクの複雑さと対応能力を分析
        
        Args:
            conversation: 対話ログ
            
        Returns:
            タスク複雑さ処理分析結果
        """
        if not conversation:
            return {"complexity_level": "unknown", "handling_quality": 0.0, "breakdown_indicators": []}
        
        # タスクの複雑さを評価
        complexity_indicators = {
            "multi_step": 0,  # 複数ステップ
            "domain_specific": 0,  # ドメイン固有
            "ambiguous_requirements": 0,  # 曖昧な要求
            "changing_requirements": 0,  # 要求変更
            "technical_depth": 0  # 技術的深度
        }
        
        all_content = " ".join([msg.get("content", "") for msg in conversation])
        
        # 複雑さ指標の検出
        complexity_patterns = {
            "multi_step": [r"まず.*次に", r"ステップ", r"段階的", r"順番に"],
            "domain_specific": [r"法的", r"医療", r"金融", r"セキュリティ", r"規制"],
            "ambiguous_requirements": [r"よろしく", r"適当に", r"なんか", r"よくある"],
            "changing_requirements": [r"やっぱり", r"変更", r"追加で", r"実は"],
            "technical_depth": [r"アルゴリズム", r"アーキテクチャ", r"最適化", r"パフォーマンス"]
        }
        
        for category, patterns in complexity_patterns.items():
            for pattern in patterns:
                matches = len(re.findall(pattern, all_content, re.IGNORECASE))
                complexity_indicators[category] += matches
        
        # 複雑さレベルの算出
        total_complexity = sum(complexity_indicators.values())
        if total_complexity >= 8:
            complexity_level = "high"
        elif total_complexity >= 4:
            complexity_level = "medium"
        else:
            complexity_level = "low"
        
        # 処理品質の評価
        handling_quality = self._evaluate_complexity_handling_quality(conversation, complexity_indicators)
        
        # 破綻指標の検出
        breakdown_indicators = self._detect_task_breakdown_indicators(conversation)
        
        return {
            "complexity_level": complexity_level,
            "complexity_score": total_complexity,
            "complexity_breakdown": complexity_indicators,
            "handling_quality": handling_quality,
            "breakdown_indicators": breakdown_indicators,
            "recommendations": self._generate_complexity_recommendations(complexity_level, handling_quality)
        }
    
    def measure_communication_efficiency(self, conversation: List[Dict]) -> Dict[str, Any]:
        """
        コミュニケーション効率性を測定
        
        Args:
            conversation: 対話ログ
            
        Returns:
            コミュニケーション効率性分析結果
        """
        if not conversation:
            return {"efficiency_score": 0.0, "waste_indicators": [], "optimization_suggestions": []}
        
        assistant_messages = [msg for msg in conversation if msg.get("role") == "assistant"]
        user_messages = [msg for msg in conversation if msg.get("role") == "user"]
        
        # 効率性指標の計算
        efficiency_metrics = {
            "redundancy_rate": self._calculate_redundancy_rate(assistant_messages),
            "clarification_ratio": len([msg for msg in assistant_messages 
                                      if self._contains_clarification(msg.get("content", ""))]) / max(len(assistant_messages), 1),
            "response_relevance": self._calculate_response_relevance(conversation),
            "information_density": self._calculate_information_density(assistant_messages)
        }
        
        # 無駄な要素の特定
        waste_indicators = []
        
        # 冗長性チェック
        if efficiency_metrics["redundancy_rate"] > 0.3:
            waste_indicators.append({
                "type": "high_redundancy",
                "severity": "medium",
                "description": f"応答の{efficiency_metrics['redundancy_rate']*100:.1f}%が重複内容",
                "suggestion": "類似表現を避け、簡潔な表現を心がける"
            })
        
        # 不適切な質問頻度
        if efficiency_metrics["clarification_ratio"] > 0.6:
            waste_indicators.append({
                "type": "excessive_clarification",
                "severity": "high", 
                "description": "明確化のための質問が多すぎる",
                "suggestion": "初回で包括的な質問をして効率化"
            })
        
        # 総合効率性スコア
        efficiency_score = statistics.mean(efficiency_metrics.values())
        
        # 最適化提案
        optimization_suggestions = self._generate_efficiency_optimization_suggestions(efficiency_metrics, waste_indicators)
        
        return {
            "efficiency_score": efficiency_score,
            "detailed_metrics": efficiency_metrics,
            "waste_indicators": waste_indicators,
            "optimization_suggestions": optimization_suggestions,
            "message_statistics": {
                "total_messages": len(conversation),
                "assistant_messages": len(assistant_messages), 
                "user_messages": len(user_messages),
                "avg_message_length": statistics.mean([len(msg.get("content", "")) for msg in conversation]) if conversation else 0
            }
        }
    
    def detect_misalignment_patterns(self, conversation: List[Dict]) -> Dict[str, Any]:
        """
        ユーザー期待とAI応答のミスアライメント検出
        
        Args:
            conversation: 対話ログ
            
        Returns:
            ミスアライメント分析結果
        """
        if not conversation:
            return {"misalignment_score": 0.0, "detected_patterns": [], "severity": "none"}
        
        misalignment_patterns = []
        severity_scores = []
        
        # ユーザーの不満や修正要求を検出
        correction_patterns = [
            r"違う", r"そうじゃない", r"期待していた.*違う", r"間違っている",
            r"理解していない", r"的外れ", r"見当違い"
        ]
        
        expectation_mismatch_patterns = [
            r"もっと.*欲しい", r"そんなことは言っていない", r"求めているのは",
            r"実際には", r"本当は", r"想定していた.*違う"
        ]
        
        for i, message in enumerate(conversation):
            if message.get("role") == "user":
                content = message.get("content", "")
                
                # 修正要求の検出
                for pattern in correction_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        misalignment_patterns.append({
                            "type": "correction_request",
                            "message_index": i,
                            "pattern": pattern,
                            "context": content[:100],
                            "severity": "high"
                        })
                        severity_scores.append(0.8)
                
                # 期待値不一致の検出
                for pattern in expectation_mismatch_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        misalignment_patterns.append({
                            "type": "expectation_mismatch", 
                            "message_index": i,
                            "pattern": pattern,
                            "context": content[:100],
                            "severity": "medium"
                        })
                        severity_scores.append(0.6)
        
        # ミスアライメントスコア計算
        if severity_scores:
            misalignment_score = statistics.mean(severity_scores)
            if misalignment_score >= 0.7:
                severity = "high"
            elif misalignment_score >= 0.4:
                severity = "medium"
            else:
                severity = "low"
        else:
            misalignment_score = 0.0
            severity = "none"
        
        return {
            "misalignment_score": misalignment_score,
            "detected_patterns": misalignment_patterns,
            "severity": severity,
            "pattern_summary": {
                "correction_requests": len([p for p in misalignment_patterns if p["type"] == "correction_request"]),
                "expectation_mismatches": len([p for p in misalignment_patterns if p["type"] == "expectation_mismatch"])
            },
            "improvement_suggestions": self._generate_alignment_improvement_suggestions(misalignment_patterns, severity)
        }
    
    # ====== Phase 2: ヘルパーメソッド ======
    
    def _calculate_message_sentiment(self, content: str) -> float:
        """メッセージのセンチメントスコアを計算"""
        positive_indicators = ["ありがとう", "素晴らしい", "完璧", "良い", "期待通り", "助かった"]
        negative_indicators = ["困った", "分からない", "エラー", "問題", "失敗", "うまくいかない"]
        frustration_indicators = ["イライラ", "時間がかかる", "遅い", "なぜ", "またか"]
        
        positive_score = sum(1 for indicator in positive_indicators if indicator in content)
        negative_score = sum(1 for indicator in negative_indicators if indicator in content)
        frustration_score = sum(1 for indicator in frustration_indicators if indicator in content)
        
        # 0.0 (very negative) to 1.0 (very positive)
        total_indicators = positive_score + negative_score + frustration_score
        if total_indicators == 0:
            return 0.5  # neutral
        
        sentiment_score = (positive_score - negative_score - frustration_score * 1.5) / total_indicators
        return max(0.0, min(1.0, (sentiment_score + 1.0) / 2.0))
    
    def _detect_frustration_type(self, content: str) -> str:
        """フラストレーションの種類を検出"""
        frustration_types = {
            "confusion": ["分からない", "理解できない", "混乱"],
            "impatience": ["遅い", "時間がかかる", "まだか"],
            "dissatisfaction": ["期待と違う", "そうじゃない", "不満"],
            "technical": ["エラー", "動かない", "バグ"]
        }
        
        for ftype, indicators in frustration_types.items():
            if any(indicator in content for indicator in indicators):
                return ftype
        return "general"
    
    def _evaluate_complexity_handling_quality(self, conversation: List[Dict], 
                                            complexity_indicators: Dict[str, int]) -> float:
        """複雑さに対する処理品質を評価"""
        total_complexity = sum(complexity_indicators.values())
        if total_complexity == 0:
            return 1.0  # 複雑でないタスクは完璧に処理できたと仮定
        
        # アシスタントの応答品質指標
        assistant_messages = [msg for msg in conversation if msg.get("role") == "assistant"]
        
        quality_indicators = {
            "detailed_responses": sum(1 for msg in assistant_messages if len(msg.get("content", "")) > 200),
            "structured_responses": sum(1 for msg in assistant_messages 
                                     if any(pattern in msg.get("content", "") 
                                           for pattern in ["1.", "まず", "次に", "最後に"])),
            "clarifying_questions": sum(1 for msg in assistant_messages 
                                     if "?" in msg.get("content", "") or "でしょうか" in msg.get("content", ""))
        }
        
        quality_score = sum(quality_indicators.values()) / max(len(assistant_messages), 1)
        complexity_adjustment = 1.0 - (total_complexity * 0.05)  # 複雑さが高いほど期待値を下げる
        
        return min(1.0, quality_score * complexity_adjustment)
    
    def _detect_task_breakdown_indicators(self, conversation: List[Dict]) -> List[Dict[str, Any]]:
        """タスク破綻の指標を検出"""
        breakdown_indicators = []
        
        breakdown_patterns = {
            "abandonment": [r"諦め", r"無理", r"できない", r"不可能"],
            "confusion_cascade": [r"もうわからない", r"混乱している", r"何をすれば"],
            "scope_creep": [r"こんなに複雑だとは", r"思ったより大変", r"予想以上"],
            "technical_debt": [r"とりあえず", r"後で直す", r"暫定的", r"応急処置"]
        }
        
        for i, message in enumerate(conversation):
            content = message.get("content", "")
            for breakdown_type, patterns in breakdown_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        breakdown_indicators.append({
                            "type": breakdown_type,
                            "message_index": i,
                            "pattern": pattern,
                            "context": content[:100]
                        })
        
        return breakdown_indicators
    
    def _generate_complexity_recommendations(self, complexity_level: str, handling_quality: float) -> List[str]:
        """複雑さレベルに基づく推奨事項を生成"""
        recommendations = []
        
        if complexity_level == "high" and handling_quality < 0.6:
            recommendations.extend([
                "複雑なタスクを小さなステップに分解することを明示する",
                "各ステップの完了確認を求める指示を追加する",
                "ドメイン固有の知識が必要な場合の対応方法を明確化する"
            ])
        elif complexity_level == "medium" and handling_quality < 0.7:
            recommendations.extend([
                "曖昧な要求に対する質問テンプレートを提供する",
                "仕様変更時の対応手順を明確化する"
            ])
        else:
            recommendations.append("現在の複雑さ処理能力は適切です")
        
        return recommendations
    
    def _calculate_redundancy_rate(self, messages: List[Dict]) -> float:
        """メッセージ間の冗長性を計算"""
        if len(messages) < 2:
            return 0.0
        
        contents = [msg.get("content", "") for msg in messages]
        redundancy_count = 0
        total_comparisons = 0
        
        for i in range(len(contents)):
            for j in range(i + 1, len(contents)):
                total_comparisons += 1
                # シンプルな類似度計算（共通単語数）
                words_i = set(contents[i].split())
                words_j = set(contents[j].split())
                
                if len(words_i.union(words_j)) > 0:
                    similarity = len(words_i.intersection(words_j)) / len(words_i.union(words_j))
                    if similarity > 0.5:  # 50%以上類似
                        redundancy_count += 1
        
        return redundancy_count / max(total_comparisons, 1)
    
    def _contains_clarification(self, content: str) -> bool:
        """明確化を含むかどうかを判定"""
        clarification_patterns = [
            r"どのような", r"具体的には", r"詳しく", r"教えて", 
            r"確認", r"でしょうか", r"\?"
        ]
        return any(re.search(pattern, content, re.IGNORECASE) for pattern in clarification_patterns)
    
    def _calculate_response_relevance(self, conversation: List[Dict]) -> float:
        """応答の関連性を計算"""
        if len(conversation) < 2:
            return 1.0
        
        relevance_scores = []
        
        for i in range(1, len(conversation)):
            if conversation[i].get("role") == "assistant" and i > 0:
                prev_msg = conversation[i-1]
                current_msg = conversation[i]
                
                if prev_msg.get("role") == "user":
                    # ユーザーメッセージとアシスタント応答の関連性
                    user_words = set(prev_msg.get("content", "").split())
                    assistant_words = set(current_msg.get("content", "").split())
                    
                    if len(user_words) > 0:
                        relevance = len(user_words.intersection(assistant_words)) / len(user_words)
                        relevance_scores.append(relevance)
        
        return statistics.mean(relevance_scores) if relevance_scores else 0.5
    
    def _calculate_information_density(self, messages: List[Dict]) -> float:
        """情報密度を計算"""
        if not messages:
            return 0.0
        
        # 情報価値のある単語パターン
        information_patterns = [
            r"\b[A-Za-z]+\.[A-Za-z]+\b",  # ファイル名
            r"\b\d+\b",  # 数値
            r"[A-Z][a-z]+",  # 固有名詞らしきもの
            r"function|class|variable|method",  # 技術用語
        ]
        
        total_chars = 0
        information_chars = 0
        
        for msg in messages:
            content = msg.get("content", "")
            total_chars += len(content)
            
            for pattern in information_patterns:
                matches = re.findall(pattern, content)
                information_chars += sum(len(match) for match in matches)
        
        return information_chars / max(total_chars, 1)
    
    def _generate_efficiency_optimization_suggestions(self, efficiency_metrics: Dict[str, float], 
                                                    waste_indicators: List[Dict]) -> List[str]:
        """効率化最適化の提案を生成"""
        suggestions = []
        
        if efficiency_metrics["redundancy_rate"] > 0.3:
            suggestions.append("重複表現を避け、より簡潔な応答を心がける")
        
        if efficiency_metrics["clarification_ratio"] > 0.6:
            suggestions.append("初回応答でより包括的な情報を提供し、後続の質問を削減する")
        
        if efficiency_metrics["response_relevance"] < 0.5:
            suggestions.append("ユーザーの質問により直接的に応答し、関連性を高める")
        
        if efficiency_metrics["information_density"] < 0.2:
            suggestions.append("具体的な情報（ファイル名、数値、技術用語等）を含む応答を増やす")
        
        return suggestions if suggestions else ["コミュニケーション効率は良好です"]
    
    def _generate_alignment_improvement_suggestions(self, misalignment_patterns: List[Dict], 
                                                  severity: str) -> List[str]:
        """アライメント改善の提案を生成"""
        suggestions = []
        
        if severity in ["high", "medium"]:
            if any(p["type"] == "correction_request" for p in misalignment_patterns):
                suggestions.append("ユーザーの初期要求をより慎重に分析し、推測を避ける")
            
            if any(p["type"] == "expectation_mismatch" for p in misalignment_patterns):
                suggestions.append("実装前にユーザーの期待を明確に確認する手順を追加")
            
            suggestions.append("要求に対する理解を確認するための確認メッセージを含める")
        else:
            suggestions.append("ユーザー期待とのアライメントは良好です")
        
        return suggestions
    
    def _load_sentiment_patterns(self) -> Dict[str, List[str]]:
        """センチメント分析用パターンのロード"""
        return {
            "positive": ["ありがとう", "素晴らしい", "完璧", "良い", "助かる"],
            "negative": ["困る", "問題", "エラー", "失敗", "うまくいかない"],
            "frustration": ["イライラ", "遅い", "時間がかかる", "なぜ"]
        }
    
    def _load_task_complexity_indicators(self) -> Dict[str, List[str]]:
        """タスク複雑さ指標のロード"""
        return {
            "multi_step": ["ステップ", "段階", "順番", "まず", "次に"],
            "domain_specific": ["法的", "医療", "金融", "規制", "セキュリティ"],
            "technical": ["アルゴリズム", "アーキテクチャ", "最適化", "パフォーマンス"]
        }
    
    def _load_communication_efficiency_patterns(self) -> Dict[str, List[str]]:
        """コミュニケーション効率パターンのロード"""
        return {
            "redundant": ["同じ", "重複", "繰り返し"],
            "clarifying": ["確認", "詳しく", "具体的に"],
            "efficient": ["要約", "簡潔", "ポイント"]
        }


# デモ実行用関数
def demo_conversation_analyzer():
    """ConversationAnalyzerのデモ実行"""
    print("=== ConversationAnalyzer デモ実行 ===")
    
    analyzer = ConversationAnalyzer()
    
    # サンプル対話データ
    sample_conversation = [
        {"role": "user", "content": "ウェブサイトを作ってください"},
        {"role": "assistant", "content": "ウェブサイトの作成を承りました。どのような機能が必要でしょうか？どのような目的のサイトですか？"},
        {"role": "user", "content": "ユーザー登録とログイン機能があるサイトです"},
        {"role": "assistant", "content": "理解しました。ユーザー登録・ログイン機能を持つウェブサイトを作成します。使用する技術スタックはいかがしましょうか？"},
        {"role": "user", "content": "すみません、よく分からないんですが、動作しないです"},
        {"role": "assistant", "content": "申し訳ございません。どのような問題が発生していますか？エラーメッセージは表示されていますか？"}
    ]
    
    # 意図理解率の分析
    print("\n1. 意図理解率分析:")
    intent_rate = analyzer.analyze_intent_understanding(sample_conversation)
    print(f"意図理解率: {intent_rate:.2f}")
    
    # 混乱ポイントの検出
    print("\n2. 混乱ポイント検出:")
    confusion_points = analyzer.detect_confusion_points(sample_conversation)
    for point in confusion_points:
        print(f"  - {point.description} (重要度: {point.severity})")
        print(f"    位置: メッセージ{point.message_index} - {point.context}")
    
    # 質問品質の評価
    print("\n3. 質問品質評価:")
    questions = ["どのような機能が必要でしょうか？", "使用する技術スタックはいかがしましょうか？", "どのような問題が発生していますか？"]
    quality_analysis = analyzer.measure_question_quality(questions)
    print(f"総合品質: {quality_analysis['overall_quality']:.2f}")
    print(f"効果性スコア: {quality_analysis['effectiveness_score']:.2f}")
    print(f"推奨事項: {quality_analysis['recommendations']}")
    
    # タスク完了フロー分析
    print("\n4. タスク完了フロー分析:")
    flow_analysis = analyzer.track_task_completion_flow(sample_conversation)
    print(f"完了ステージ: {flow_analysis.stages_completed}")
    print(f"不足ステージ: {flow_analysis.missing_stages}")
    print(f"効率性スコア: {flow_analysis.efficiency_score:.2f}")
    if flow_analysis.bottlenecks:
        print(f"ボトルネック: {flow_analysis.bottlenecks}")
    
    print("\n=== デモ完了 ===")


if __name__ == "__main__":
    demo_conversation_analyzer()