"""
PromptSmith ファイル内容解析評価システム
AIの分析結果を自動的に評価し、スコアを算出する
"""

import re
import json
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime
import ast

@dataclass
class AnalysisEvaluationResult:
    """分析結果の評価データクラス"""
    
    scenario_id: str
    total_score: float
    category_scores: Dict[str, float]
    detailed_feedback: Dict[str, Any]
    strengths: List[str]
    weaknesses: List[str]
    improvement_suggestions: List[str]
    evaluation_timestamp: str

class FileAnalysisEvaluator:
    """ファイル内容解析の評価システム"""
    
    def __init__(self):
        """初期化"""
        self.evaluation_patterns = self._load_evaluation_patterns()
        self.keyword_weights = self._load_keyword_weights()
    
    def _load_evaluation_patterns(self) -> Dict:
        """評価パターンを定義"""
        return {
            # コード構造分析の評価パターン
            "code_structure": {
                "function_identification": {
                    "patterns": [
                        r"関数.*?(\w+)",
                        r"function.*?(\w+)",
                        r"def\s+(\w+)",
                        r"メソッド.*?(\w+)"
                    ],
                    "weight": 0.3
                },
                "class_identification": {
                    "patterns": [
                        r"クラス.*?(\w+)",
                        r"class.*?(\w+)",
                        r"オブジェクト.*?(\w+)"
                    ],
                    "weight": 0.25
                },
                "parameter_explanation": {
                    "patterns": [
                        r"引数",
                        r"パラメータ",
                        r"parameter",
                        r"argument"
                    ],
                    "weight": 0.2
                },
                "return_value_explanation": {
                    "patterns": [
                        r"戻り値",
                        r"返す",
                        r"return",
                        r"結果"
                    ],
                    "weight": 0.15
                },
                "functionality_description": {
                    "patterns": [
                        r"機能",
                        r"処理",
                        r"目的",
                        r"役割"
                    ],
                    "weight": 0.1
                }
            },
            
            # バグ検出の評価パターン
            "bug_detection": {
                "exception_handling": {
                    "keywords": [
                        "例外", "エラーハンドリング", "try-catch", "exception",
                        "error handling", "エラー処理"
                    ],
                    "weight": 0.25
                },
                "null_pointer_issues": {
                    "keywords": [
                        "null", "None", "undefined", "空の値", "未初期化"
                    ],
                    "weight": 0.2
                },
                "logic_errors": {
                    "keywords": [
                        "ロジック", "条件分岐", "ループ", "logic error",
                        "conditional", "論理エラー"
                    ],
                    "weight": 0.2
                },
                "security_issues": {
                    "keywords": [
                        "セキュリティ", "脆弱性", "SQLインジェクション", "XSS",
                        "security", "vulnerability", "injection"
                    ],
                    "weight": 0.2
                },
                "fix_suggestions": {
                    "keywords": [
                        "修正", "改善", "解決", "fix", "solution", "修正案"
                    ],
                    "weight": 0.15
                }
            },
            
            # パフォーマンス分析の評価パターン
            "performance": {
                "complexity_analysis": {
                    "patterns": [
                        r"O\([^)]+\)",  # Big O記法
                        r"計算量",
                        r"時間計算量",
                        r"complexity"
                    ],
                    "weight": 0.3
                },
                "bottleneck_identification": {
                    "keywords": [
                        "ボトルネック", "性能問題", "遅い", "非効率",
                        "bottleneck", "inefficient", "slow"
                    ],
                    "weight": 0.25
                },
                "optimization_suggestions": {
                    "keywords": [
                        "最適化", "改善", "高速化", "optimization",
                        "improve", "faster", "efficient"
                    ],
                    "weight": 0.25
                },
                "memory_usage": {
                    "keywords": [
                        "メモリ", "memory", "メモリリーク", "memory leak",
                        "リソース", "resource"
                    ],
                    "weight": 0.2
                }
            },
            
            # 曖昧な要求への対応評価パターン
            "ambiguous_analysis": {
                "clarification_questions": {
                    "patterns": [
                        r"何.*?について",
                        r"どの.*?について",
                        r"どのような.*?",
                        r"\?",
                        r"確認.*?です"
                    ],
                    "weight": 0.4
                },
                "comprehensive_coverage": {
                    "keywords": [
                        "全体的", "包括的", "一般的", "overall", "comprehensive",
                        "multiple", "様々", "各種"
                    ],
                    "weight": 0.3
                },
                "prioritization": {
                    "keywords": [
                        "優先", "重要", "priority", "important", "urgent",
                        "まず", "最初", "first"
                    ],
                    "weight": 0.3
                }
            }
        }
    
    def _load_keyword_weights(self) -> Dict:
        """キーワード重みを定義"""
        return {
            # 品質を示すキーワード（高評価）
            "high_quality": {
                "keywords": [
                    "詳細", "具体的", "正確", "適切", "効率的",
                    "detailed", "specific", "accurate", "appropriate", "efficient"
                ],
                "weight": 1.2
            },
            
            # 問題を示すキーワード（分析力を示す）
            "problem_identification": {
                "keywords": [
                    "問題", "課題", "リスク", "危険", "注意",
                    "problem", "issue", "risk", "danger", "caution"
                ],
                "weight": 1.1
            },
            
            # 曖昧・不明確なキーワード（低評価）
            "vague_terms": {
                "keywords": [
                    "なんとなく", "たぶん", "おそらく", "かもしれない",
                    "maybe", "perhaps", "possibly", "might"
                ],
                "weight": 0.8
            }
        }
    
    def evaluate_analysis(self, scenario, ai_response: str) -> AnalysisEvaluationResult:
        """AI分析結果を評価"""
        
        category_scores = {}
        detailed_feedback = {}
        strengths = []
        weaknesses = []
        suggestions = []
        
        # カテゴリ別評価
        if scenario.category in self.evaluation_patterns:
            category_score, feedback, category_strengths, category_weaknesses = \
                self._evaluate_category(scenario.category, ai_response, scenario)
            
            category_scores[scenario.category] = category_score
            detailed_feedback[scenario.category] = feedback
            strengths.extend(category_strengths)
            weaknesses.extend(category_weaknesses)
        
        # 共通品質評価
        quality_score, quality_feedback = self._evaluate_response_quality(ai_response)
        category_scores["response_quality"] = quality_score
        detailed_feedback["response_quality"] = quality_feedback
        
        # 期待分析ポイントの網羅度評価
        coverage_score, coverage_feedback = self._evaluate_coverage(
            scenario.expected_analysis_points, ai_response
        )
        category_scores["coverage"] = coverage_score
        detailed_feedback["coverage"] = coverage_feedback
        
        # 総合スコア計算
        weights = scenario.evaluation_criteria
        total_score = 0
        
        for criterion, weight in weights.items():
            if criterion in category_scores:
                total_score += category_scores[criterion] * weight
        
        # 品質調整
        total_score = min(total_score * quality_score, 1.0)
        
        # 改善提案生成
        suggestions = self._generate_improvement_suggestions(
            category_scores, detailed_feedback, scenario
        )
        
        return AnalysisEvaluationResult(
            scenario_id=scenario.scenario_id,
            total_score=total_score,
            category_scores=category_scores,
            detailed_feedback=detailed_feedback,
            strengths=strengths,
            weaknesses=weaknesses,
            improvement_suggestions=suggestions,
            evaluation_timestamp=datetime.now().isoformat()
        )
    
    def _evaluate_category(self, category: str, response: str, scenario) -> Tuple[float, Dict, List[str], List[str]]:
        """カテゴリ別評価"""
        
        patterns = self.evaluation_patterns[category]
        score = 0
        feedback = {}
        strengths = []
        weaknesses = []
        
        for aspect, config in patterns.items():
            aspect_score = 0
            
            if "patterns" in config:
                # 正規表現パターンマッチング
                matches = 0
                for pattern in config["patterns"]:
                    if re.search(pattern, response, re.IGNORECASE):
                        matches += 1
                
                aspect_score = min(matches / len(config["patterns"]), 1.0)
                
            elif "keywords" in config:
                # キーワードマッチング
                keyword_count = 0
                for keyword in config["keywords"]:
                    if keyword.lower() in response.lower():
                        keyword_count += 1
                
                aspect_score = min(keyword_count / len(config["keywords"]) * 2, 1.0)
            
            # 重み付きスコア追加
            weighted_score = aspect_score * config["weight"]
            score += weighted_score
            
            feedback[aspect] = {
                "score": aspect_score,
                "weighted_score": weighted_score,
                "weight": config["weight"]
            }
            
            # 強み・弱み判定
            if aspect_score >= 0.7:
                strengths.append(f"{aspect}の分析が優秀")
            elif aspect_score <= 0.3:
                weaknesses.append(f"{aspect}の分析が不足")
        
        return score, feedback, strengths, weaknesses
    
    def _evaluate_response_quality(self, response: str) -> Tuple[float, Dict]:
        """回答品質の評価"""
        
        quality_score = 1.0
        feedback = {}
        
        # 長さ評価
        length = len(response)
        if length < 50:
            length_score = 0.3
            feedback["length"] = "回答が短すぎます"
        elif length > 2000:
            length_score = 0.8
            feedback["length"] = "回答が長すぎる可能性があります"
        else:
            length_score = 1.0
            feedback["length"] = "適切な長さです"
        
        # 構造化評価
        structure_score = 1.0
        structure_indicators = ["1.", "2.", "・", "-", "##", "**"]
        structure_count = sum(1 for indicator in structure_indicators 
                            if indicator in response)
        
        if structure_count >= 3:
            structure_score = 1.0
            feedback["structure"] = "よく構造化されています"
        elif structure_count >= 1:
            structure_score = 0.8
            feedback["structure"] = "ある程度構造化されています"
        else:
            structure_score = 0.6
            feedback["structure"] = "構造化が不十分です"
        
        # キーワード品質評価
        keyword_quality = 1.0
        for quality_type, config in self.keyword_weights.items():
            count = sum(1 for keyword in config["keywords"] 
                       if keyword.lower() in response.lower())
            
            if count > 0:
                if quality_type == "vague_terms":
                    keyword_quality *= config["weight"]
                    feedback["vague_terms"] = f"曖昧な表現が{count}個検出されました"
                else:
                    keyword_quality *= (1 + (count * (config["weight"] - 1) * 0.1))
        
        # 総合品質スコア
        quality_score = (length_score * 0.3 + structure_score * 0.4 + 
                        keyword_quality * 0.3)
        
        feedback["overall_quality"] = quality_score
        
        return quality_score, feedback
    
    def _evaluate_coverage(self, expected_points: List[str], response: str) -> Tuple[float, Dict]:
        """期待分析ポイントの網羅度評価"""
        
        covered_points = 0
        coverage_details = {}
        
        for point in expected_points:
            # キーワード抽出
            point_keywords = re.findall(r'\w+', point.lower())
            
            # レスポンス内での該当キーワード検索
            matches = 0
            for keyword in point_keywords:
                if keyword in response.lower():
                    matches += 1
            
            # カバレッジ判定（50%以上のキーワードがマッチ）
            coverage_ratio = matches / len(point_keywords) if point_keywords else 0
            is_covered = coverage_ratio >= 0.5
            
            if is_covered:
                covered_points += 1
            
            coverage_details[point] = {
                "covered": is_covered,
                "coverage_ratio": coverage_ratio,
                "matched_keywords": matches,
                "total_keywords": len(point_keywords)
            }
        
        coverage_score = covered_points / len(expected_points) if expected_points else 1.0
        
        feedback = {
            "coverage_score": coverage_score,
            "covered_points": covered_points,
            "total_expected": len(expected_points),
            "details": coverage_details
        }
        
        return coverage_score, feedback
    
    def _generate_improvement_suggestions(self, category_scores: Dict[str, float], 
                                        detailed_feedback: Dict, scenario) -> List[str]:
        """改善提案生成"""
        
        suggestions = []
        
        # 低スコア領域の改善提案
        for category, score in category_scores.items():
            if score < 0.5:
                if category == "response_quality":
                    suggestions.append("回答の構造化と詳細度を向上させてください")
                elif category == "coverage":
                    suggestions.append("期待される分析ポイントをより網羅的にカバーしてください")
                elif category in self.evaluation_patterns:
                    suggestions.append(f"{category}関連の分析をより詳細に行ってください")
        
        # レベル別改善提案
        if scenario.level >= 3:
            if category_scores.get("ambiguous_analysis", 0) < 0.6:
                suggestions.append("曖昧な要求に対してより適切な質問で明確化を行ってください")
        
        # 汎用改善提案
        if not suggestions:
            suggestions.append("全体的に良い分析です。専門的な観点をより深く掘り下げてみてください")
        
        return suggestions
    
    def batch_evaluate(self, scenarios_and_responses: List[Tuple]) -> Dict:
        """バッチ評価実行"""
        
        results = []
        scores = []
        
        for scenario, response in scenarios_and_responses:
            evaluation = self.evaluate_analysis(scenario, response)
            results.append(evaluation)
            scores.append(evaluation.total_score)
        
        # 統計情報計算
        statistics = {
            "total_evaluations": len(results),
            "average_score": np.mean(scores),
            "median_score": np.median(scores),
            "std_deviation": np.std(scores),
            "min_score": np.min(scores),
            "max_score": np.max(scores),
            "score_distribution": {
                "excellent (>0.8)": sum(1 for s in scores if s > 0.8),
                "good (0.6-0.8)": sum(1 for s in scores if 0.6 <= s <= 0.8),
                "fair (0.4-0.6)": sum(1 for s in scores if 0.4 <= s < 0.6),
                "poor (<0.4)": sum(1 for s in scores if s < 0.4)
            }
        }
        
        # カテゴリ別統計
        category_stats = {}
        for result in results:
            for category, score in result.category_scores.items():
                if category not in category_stats:
                    category_stats[category] = []
                category_stats[category].append(score)
        
        for category, scores_list in category_stats.items():
            category_stats[category] = {
                "average": np.mean(scores_list),
                "std": np.std(scores_list),
                "count": len(scores_list)
            }
        
        return {
            "batch_id": f"eval_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "statistics": statistics,
            "category_statistics": category_stats,
            "individual_results": results
        }

# テスト・デモ用関数
def demo_evaluation():
    """評価システムのデモ"""
    from datetime import datetime
    from ..ai_roles.file_analysis_scenarios import FileAnalysisScenarioGenerator
    
    print("=== ファイル分析評価システムデモ ===\n")
    
    # サンプルシナリオ生成
    generator = FileAnalysisScenarioGenerator()
    scenario = generator.generate_scenario(level=2)
    
    # サンプル回答（良い例）
    good_response = """
    このPythonファイルを分析した結果、以下の点が確認できます：

    ## コード構造
    1. **DataProcessor基底クラス**: データ処理の抽象基盤クラス
       - process()抽象メソッド: サブクラスでの具体実装が必要
       - validate_data()メソッド: データ妥当性検証機能
    
    2. **TextProcessor継承クラス**: テキスト処理特化実装
       - 引数: name(str), max_length(int)
       - 戻り値: 処理済みデータ辞書
    
    ## 検出された問題点
    - エラーハンドリング: ValueError例外のみで他の例外に対応不足
    - パフォーマンス: _clean_text()メソッドでO(n)の文字列処理
    
    ## 改善提案
    1. より包括的な例外処理の実装
    2. テキスト処理のメモリ効率改善
    3. ログ設定の外部化
    """
    
    # サンプル回答（悪い例）
    bad_response = "このファイルはデータ処理をするクラスです。何か問題があるかもしれません。"
    
    # 評価実行
    evaluator = FileAnalysisEvaluator()
    
    print("【良い回答の評価】")
    good_eval = evaluator.evaluate_analysis(scenario, good_response)
    print(f"総合スコア: {good_eval.total_score:.3f}")
    print(f"カテゴリ別スコア: {good_eval.category_scores}")
    print(f"強み: {good_eval.strengths}")
    print(f"弱み: {good_eval.weaknesses}")
    print()
    
    print("【悪い回答の評価】")
    bad_eval = evaluator.evaluate_analysis(scenario, bad_response)
    print(f"総合スコア: {bad_eval.total_score:.3f}")
    print(f"カテゴリ別スコア: {bad_eval.category_scores}")
    print(f"改善提案: {bad_eval.improvement_suggestions}")

if __name__ == "__main__":
    demo_evaluation()