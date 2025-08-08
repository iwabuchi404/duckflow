"""
Optimizer AI - 対話ログからプロンプト改善案を生成するAI

実行結果と対話ログを分析して、プロンプトの弱点を特定し、
具体的な改善提案を生成します。
"""

import json
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import statistics

# Import PromptImprovement from improvement_engine
from ..improvement_engine import PromptImprovement


@dataclass
class WeaknessPattern:
    """発見された弱点パターン"""
    pattern_id: str
    category: str  # understanding, communication, implementation, error_handling
    description: str
    frequency: int  # 発生頻度
    severity: str  # low, medium, high, critical
    examples: List[str]  # 具体例
    

@dataclass
class ImprovementSuggestion:
    """プロンプト改善提案"""
    suggestion_id: str
    target_weakness: str  # 対象となる弱点
    improvement_type: str  # addition, modification, deletion, restructure
    current_section: str  # 現在のプロンプトセクション
    proposed_change: str  # 提案する変更
    rationale: str  # 改善理由
    expected_impact: Dict[str, float]  # 予想される効果
    priority: str  # high, medium, low


class OptimizerAI:
    """対話ログからプロンプト改善案を生成するAI"""
    
    def __init__(self):
        """OptimizerAIの初期化"""
        self.weakness_categories = {
            "understanding": "ユーザー意図の理解",
            "communication": "コミュニケーション",
            "implementation": "実装品質",
            "error_handling": "エラー対応",
            "clarification": "明確化・質問",
            "planning": "計画・設計"
        }
        
        self.improvement_patterns = self._load_improvement_patterns()
    
    def analyze_conversation_log(self, conversation: List[Dict]) -> Dict[str, Any]:
        """
        対話ログの詳細分析
        
        Args:
            conversation: 対話ログのリスト
            
        Returns:
            分析結果
        """
        analysis_result = {
            "conversation_metadata": self._extract_metadata(conversation),
            "weakness_patterns": self._identify_weakness_patterns(conversation),
            "communication_analysis": self._analyze_communication_quality(conversation),
            "task_completion_flow": self._analyze_task_flow(conversation),
            "error_analysis": self._analyze_errors(conversation),
            "question_quality": self._analyze_question_quality(conversation)
        }
        
        return analysis_result
    
    def identify_weakness_patterns(self, evaluation_results: Dict) -> List[WeaknessPattern]:
        """
        弱点パターンの抽出
        
        Args:
            evaluation_results: 評価結果
            
        Returns:
            発見された弱点パターンのリスト
        """
        weaknesses = []
        
        # 品質スコアから弱点を特定
        if evaluation_results.get("quality_score", 0) < 70:
            weaknesses.append(WeaknessPattern(
                pattern_id="low_quality_code",
                category="implementation",
                description="生成されるコードの品質が低い",
                frequency=1,
                severity="high",
                examples=["構文エラーの存在", "スタイル違反", "セキュリティ問題"]
            ))
        
        # 完成度から弱点を特定
        if evaluation_results.get("completeness_score", 0) < 60:
            weaknesses.append(WeaknessPattern(
                pattern_id="incomplete_implementation",
                category="understanding",
                description="要求仕様の実装が不完全",
                frequency=1,
                severity="high",
                examples=["必要なファイルの未作成", "機能の実装漏れ"]
            ))
        
        # 効率性から弱点を特定
        if evaluation_results.get("efficiency_score", 0) < 70:
            weaknesses.append(WeaknessPattern(
                pattern_id="low_efficiency",
                category="planning",
                description="実装効率が低い",
                frequency=1,
                severity="medium",
                examples=["実行時間が長い", "不要な処理の存在"]
            ))
        
        return weaknesses
    
    def generate_improvement_suggestions(self, analysis: Dict) -> List[PromptImprovement]:
        """
        具体的改善提案の生成
        
        Args:
            analysis: 分析結果
            
        Returns:
            改善提案のリスト
        """
        suggestions = []
        weakness_patterns = analysis.get("weakness_patterns", [])
        
        for weakness in weakness_patterns:
            # 弱点に応じた改善提案を生成
            if weakness.category == "understanding":
                suggestion = self._generate_understanding_improvement(weakness)
            elif weakness.category == "communication":
                suggestion = self._generate_communication_improvement(weakness)
            elif weakness.category == "implementation":
                suggestion = self._generate_implementation_improvement(weakness)
            elif weakness.category == "error_handling":
                suggestion = self._generate_error_handling_improvement(weakness)
            elif weakness.category == "clarification":
                suggestion = self._generate_clarification_improvement(weakness)
            elif weakness.category == "planning":
                suggestion = self._generate_planning_improvement(weakness)
            else:
                continue
            
            if suggestion:
                suggestions.append(suggestion)
        
        # 優先度順でソート
        suggestions.sort(key=lambda x: {"high": 3, "medium": 2, "low": 1}[x.priority], reverse=True)
        
        return suggestions
    
    def _extract_metadata(self, conversation: List[Dict]) -> Dict[str, Any]:
        """対話のメタデータを抽出"""
        if not conversation:
            return {}
        
        # 基本統計
        total_messages = len(conversation)
        user_messages = len([msg for msg in conversation if msg.get("role") == "user"])
        assistant_messages = len([msg for msg in conversation if msg.get("role") == "assistant"])
        
        # 時間分析（可能な場合）
        timestamps = [msg.get("timestamp") for msg in conversation if msg.get("timestamp")]
        duration = None
        if len(timestamps) >= 2:
            try:
                start_time = datetime.fromisoformat(timestamps[0])
                end_time = datetime.fromisoformat(timestamps[-1])
                duration = (end_time - start_time).total_seconds()
            except:
                pass
        
        return {
            "total_messages": total_messages,
            "user_messages": user_messages,
            "assistant_messages": assistant_messages,
            "conversation_duration": duration,
            "avg_message_length": statistics.mean([len(msg.get("content", "")) for msg in conversation])
        }
    
    def _identify_weakness_patterns(self, conversation: List[Dict]) -> List[WeaknessPattern]:
        """対話から弱点パターンを特定"""
        weaknesses = []
        
        # テキスト分析による弱点検出
        all_text = " ".join([msg.get("content", "") for msg in conversation])
        
        # 混乱や誤解を示すパターン
        confusion_patterns = [
            r"すみません、よく分からない",
            r"理解できませんでした",
            r"混乱しています",
            r"何を意味しているのか",
            r"もう一度説明"
        ]
        
        confusion_count = sum([len(re.findall(pattern, all_text, re.IGNORECASE)) for pattern in confusion_patterns])
        
        if confusion_count > 0:
            weaknesses.append(WeaknessPattern(
                pattern_id="user_confusion",
                category="communication",
                description="ユーザーが混乱している兆候",
                frequency=confusion_count,
                severity="high" if confusion_count > 2 else "medium",
                examples=[f"{confusion_count}回の混乱表現を検出"]
            ))
        
        # 質問の品質分析
        questions = self._extract_questions(conversation)
        if len(questions) == 0:
            weaknesses.append(WeaknessPattern(
                pattern_id="no_clarification",
                category="clarification",
                description="明確化のための質問が不足",
                frequency=1,
                severity="high",
                examples=["要求に対して質問せずに実装を開始"]
            ))
        
        # エラーパターンの検出
        error_patterns = [
            r"エラーが発生",
            r"失敗しました",
            r"動作しません",
            r"問題があります"
        ]
        
        error_count = sum([len(re.findall(pattern, all_text, re.IGNORECASE)) for pattern in error_patterns])
        
        if error_count > 2:
            weaknesses.append(WeaknessPattern(
                pattern_id="frequent_errors",
                category="error_handling",
                description="エラーが頻繁に発生",
                frequency=error_count,
                severity="high",
                examples=[f"{error_count}回のエラー関連言及を検出"]
            ))
        
        return weaknesses
    
    def _analyze_communication_quality(self, conversation: List[Dict]) -> Dict[str, Any]:
        """コミュニケーション品質の分析"""
        assistant_messages = [msg for msg in conversation if msg.get("role") == "assistant"]
        
        # メッセージの明確性分析
        clarity_indicators = {
            "explanatory_phrases": ["つまり", "具体的には", "例えば", "要するに"],
            "confirmation_requests": ["よろしいでしょうか", "確認させて", "理解は正しいでしょうか"],
            "step_indicators": ["まず", "次に", "最後に", "ステップ1", "1."]
        }
        
        clarity_scores = {}
        for category, phrases in clarity_indicators.items():
            count = 0
            for msg in assistant_messages:
                content = msg.get("content", "")
                count += sum([content.count(phrase) for phrase in phrases])
            clarity_scores[category] = count
        
        return {
            "clarity_scores": clarity_scores,
            "avg_message_length": statistics.mean([len(msg.get("content", "")) for msg in assistant_messages]) if assistant_messages else 0,
            "total_assistant_messages": len(assistant_messages)
        }
    
    def _analyze_task_flow(self, conversation: List[Dict]) -> Dict[str, Any]:
        """タスク完了フローの分析"""
        # タスクの進行段階を特定
        stages = {
            "understanding": ["理解しました", "確認します", "要件は"],
            "planning": ["計画", "設計", "構成", "アプローチ"],
            "implementation": ["実装", "作成", "コード", "ファイル"],
            "testing": ["テスト", "確認", "動作", "検証"],
            "completion": ["完了", "終了", "完成", "仕上がり"]
        }
        
        stage_detection = {}
        for stage, keywords in stages.items():
            count = 0
            for msg in conversation:
                content = msg.get("content", "").lower()
                count += sum([content.count(keyword) for keyword in keywords])
            stage_detection[stage] = count > 0
        
        # フロー完整性の評価
        expected_flow = ["understanding", "planning", "implementation"]
        flow_completeness = sum([stage_detection.get(stage, False) for stage in expected_flow]) / len(expected_flow)
        
        return {
            "detected_stages": stage_detection,
            "flow_completeness": flow_completeness,
            "missing_stages": [stage for stage in expected_flow if not stage_detection.get(stage, False)]
        }
    
    def _analyze_errors(self, conversation: List[Dict]) -> Dict[str, Any]:
        """エラー分析"""
        error_types = {
            "syntax_error": ["構文エラー", "SyntaxError", "invalid syntax"],
            "runtime_error": ["実行エラー", "RuntimeError", "Exception"],
            "logic_error": ["論理エラー", "期待通りに動作しない", "結果が間違っている"],
            "import_error": ["ImportError", "ModuleNotFoundError", "インポートできません"]
        }
        
        detected_errors = {}
        for error_type, patterns in error_types.items():
            count = 0
            for msg in conversation:
                content = msg.get("content", "")
                count += sum([len(re.findall(pattern, content, re.IGNORECASE)) for pattern in patterns])
            detected_errors[error_type] = count
        
        total_errors = sum(detected_errors.values())
        
        return {
            "error_counts": detected_errors,
            "total_errors": total_errors,
            "error_density": total_errors / len(conversation) if conversation else 0
        }
    
    def _analyze_question_quality(self, conversation: List[Dict]) -> Dict[str, Any]:
        """質問品質の分析"""
        questions = self._extract_questions(conversation)
        
        if not questions:
            return {
                "question_count": 0,
                "quality_score": 0,
                "question_types": {}
            }
        
        # 質問タイプの分類
        question_types = {
            "clarification": ["どういう意味", "具体的には", "詳しく教えて"],
            "requirement": ["どのような", "何を", "どんな機能"],
            "technical": ["どの技術", "どの言語", "どのフレームワーク"],
            "confirmation": ["よろしいでしょうか", "これで合っていますか", "確認ですが"]
        }
        
        type_counts = {}
        for q_type, patterns in question_types.items():
            count = 0
            for question in questions:
                count += sum([len(re.findall(pattern, question, re.IGNORECASE)) for pattern in patterns])
            type_counts[q_type] = count
        
        # 質問品質スコア（多様性と適切性）
        quality_score = min(100, len(set(type_counts.keys())) * 25 + len(questions) * 5)
        
        return {
            "question_count": len(questions),
            "quality_score": quality_score,
            "question_types": type_counts,
            "questions": questions[:5]  # サンプルとして最初の5つ
        }
    
    def _extract_questions(self, conversation: List[Dict]) -> List[str]:
        """対話から質問を抽出"""
        questions = []
        for msg in conversation:
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                # 日本語の疑問文パターン
                question_patterns = [
                    r'[^。]*？',  # ？で終わる文
                    r'[^。]*でしょうか[。？]?',  # でしょうかで終わる文
                    r'[^。]*ですか[。？]?',     # ですかで終わる文
                    r'[^。]*ませんか[。？]?'    # ませんかで終わる文
                ]
                
                for pattern in question_patterns:
                    matches = re.findall(pattern, content)
                    questions.extend([match.strip() for match in matches])
        
        return list(set(questions))  # 重複削除
    
    def _generate_understanding_improvement(self, weakness: WeaknessPattern) -> PromptImprovement:
        """理解力改善の提案生成"""
        return PromptImprovement(
            improvement_id=f"understanding_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            target_section="task_understanding",
            improvement_type="addition",
            current_content="",
            proposed_content="ユーザーの要求を受け取ったら、まず要求の核心を理解し、不明な点がないか確認してください。必要に応じて具体的な質問をして、要件を明確化してから実装に取りかかってください。",
            rationale="要求理解の精度向上により、実装の完成度が向上します",
            expected_impact={
                "completeness_score": 15.0,
                "user_satisfaction": 10.0
            },
            risk_level="low",
            validation_status="pending"
        )
    
    def _generate_communication_improvement(self, weakness: WeaknessPattern) -> PromptImprovement:
        """コミュニケーション改善の提案生成"""
        return PromptImprovement(
            improvement_id=f"communication_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            target_section="communication",
            improvement_type="addition",
            current_content="",
            proposed_content="作業内容を分かりやすく説明し、進捗を定期的に報告してください。専門用語を使う際は、必要に応じて説明を添えてください。",
            rationale="明確なコミュニケーションにより、ユーザーの混乱を減らします",
            expected_impact={
                "communication_clarity": 20.0,
                "user_satisfaction": 15.0
            },
            risk_level="low",
            validation_status="pending"
        )
    
    def _generate_implementation_improvement(self, weakness: WeaknessPattern) -> PromptImprovement:
        """実装品質改善の提案生成"""
        return PromptImprovement(
            improvement_id=f"implementation_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            target_section="code_quality",
            improvement_type="modification",
            current_content="",
            proposed_content="コードを書く前に設計を検討し、テスト可能で保守性の高いコードを心がけてください。構文エラーやセキュリティ問題がないか、コード生成後に必ず確認してください。",
            rationale="コード品質の向上により、エラーの発生を減らし、保守性を高めます",
            expected_impact={
                "quality_score": 25.0,
                "error_rate": -30.0
            },
            risk_level="low",
            validation_status="pending"
        )
    
    def _generate_error_handling_improvement(self, weakness: WeaknessPattern) -> PromptImprovement:
        """エラー対応改善の提案生成"""
        return PromptImprovement(
            improvement_id=f"error_handling_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            target_section="error_handling",
            improvement_type="addition",
            current_content="",
            proposed_content="エラーが発生した場合は、まず原因を詳しく分析し、具体的な解決策を提示してください。同じエラーを繰り返さないよう、根本原因に対処してください。",
            rationale="適切なエラー対応により、問題解決の効率が向上します",
            expected_impact={
                "error_resolution_rate": 40.0,
                "user_frustration": -25.0
            },
            risk_level="low",
            validation_status="pending"
        )
    
    def _generate_clarification_improvement(self, weakness: WeaknessPattern) -> PromptImprovement:
        """明確化改善の提案生成"""
        return PromptImprovement(
            improvement_id=f"clarification_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            target_section="task_understanding",
            improvement_type="addition",
            current_content="",
            proposed_content="曖昧や不完全な要求を受けた場合は、推測で進めずに必ず確認を取ってください。「具体的にはどのような機能が必要ですか？」「どのような形式で出力が必要ですか？」など、具体的な質問をしてください。",
            rationale="適切な質問により、要求の理解精度が向上し、やり直しを減らせます",
            expected_impact={
                "requirement_clarity": 30.0,
                "rework_rate": -40.0
            },
            risk_level="low",
            validation_status="pending"
        )
    
    def _generate_planning_improvement(self, weakness: WeaknessPattern) -> PromptImprovement:
        """計画改善の提案生成"""
        return PromptImprovement(
            improvement_id=f"planning_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            target_section="task_understanding",
            improvement_type="addition",
            current_content="",
            proposed_content="複雑なタスクの場合は、実装前に全体の構成や手順を整理し、段階的なアプローチを提示してください。「まず○○を作成し、次に○○を実装します」といった具体的な計画を共有してください。",
            rationale="適切な計画により、効率的な実装と品質向上が可能になります",
            expected_impact={
                "efficiency_score": 20.0,
                "planning_quality": 35.0
            },
            risk_level="low",
            validation_status="pending"
        )
    
    def _load_improvement_patterns(self) -> Dict[str, Any]:
        """改善パターンのロード（将来的に外部ファイル化）"""
        return {
            "understanding_patterns": [
                "要求の明確化を優先する",
                "前提条件を確認する",
                "成功基準を定義する"
            ],
            "communication_patterns": [
                "段階的に説明する",
                "専門用語の説明を添える",
                "進捗を報告する"
            ],
            "implementation_patterns": [
                "設計を事前に検討する",
                "テスタブルなコードを書く",
                "セキュリティを考慮する"
            ]
        }


# デモ実行用関数
def demo_optimizer_ai():
    """OptimizerAIのデモ実行"""
    print("=== OptimizerAI デモ実行 ===")
    
    optimizer = OptimizerAI()
    
    # サンプル対話データ
    sample_conversation = [
        {"role": "user", "content": "ウェブサイトを作ってください"},
        {"role": "assistant", "content": "ウェブサイトを作成します。HTML、CSS、JavaScriptで作成しましょう。"},
        {"role": "user", "content": "すみません、よく分からないんですが、どんなウェブサイトになるんですか？"},
        {"role": "assistant", "content": "基本的なウェブページを作成しました。"},
        {"role": "user", "content": "エラーが発生しているようです。動作しません。"}
    ]
    
    # 対話ログ分析
    print("\n1. 対話ログ分析:")
    analysis = optimizer.analyze_conversation_log(sample_conversation)
    print(f"メタデータ: {analysis['conversation_metadata']}")
    print(f"発見された弱点: {len(analysis['weakness_patterns'])}個")
    
    # 弱点パターン分析
    print("\n2. 弱点パターン:")
    for weakness in analysis['weakness_patterns']:
        print(f"  - {weakness.description} (重要度: {weakness.severity})")
    
    # サンプル評価結果での改善提案
    print("\n3. 改善提案生成:")
    sample_evaluation = {
        "quality_score": 65,
        "completeness_score": 45,
        "efficiency_score": 60
    }
    
    weaknesses = optimizer.identify_weakness_patterns(sample_evaluation)
    suggestions = optimizer.generate_improvement_suggestions({"weakness_patterns": weaknesses})
    
    for suggestion in suggestions[:3]:  # 上位3つを表示
        print(f"\n提案: {suggestion.improvement_type} - {suggestion.current_section}")
        print(f"内容: {suggestion.proposed_change[:100]}...")
        print(f"理由: {suggestion.rationale}")
        print(f"優先度: {suggestion.priority}")
    
    print("\n=== デモ完了 ===")


if __name__ == "__main__":
    demo_optimizer_ai()