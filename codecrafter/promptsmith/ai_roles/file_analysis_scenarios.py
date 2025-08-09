"""
PromptSmith ファイル内容解析シナリオ
TesterAIが使用するファイル解析タスクの生成システム
"""

import random
import os
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime

@dataclass
class FileAnalysisScenario:
    """ファイル解析シナリオのデータクラス"""
    
    scenario_id: str
    level: int  # 1:基本, 2:中級, 3:高級
    category: str  # "code_structure", "bug_detection", "performance", "security", etc.
    title: str
    description: str
    file_path: str
    user_request: str  # ユーザーからの要求（故意に曖昧にする場合も）
    expected_analysis_points: List[str]  # 期待される分析ポイント
    evaluation_criteria: Dict[str, float]  # 評価基準（重み付き）
    difficulty_factors: List[str]  # 困難要因
    context_info: Optional[str] = None  # 追加の文脈情報

class FileAnalysisScenarioGenerator:
    """ファイル解析シナリオジェネレーター"""
    
    def __init__(self, samples_dir: str = "tests/promptsmith/file_analysis_samples"):
        self.samples_dir = Path(samples_dir)
        self.scenario_templates = self._load_scenario_templates()
        
    def _load_scenario_templates(self) -> Dict:
        """シナリオテンプレートを定義"""
        return {
            # レベル1: 基本シナリオ
            "level1_simple_analysis": {
                "category": "code_structure",
                "request_templates": [
                    "このファイルの内容を説明してください",
                    "このコードが何をしているか教えて",
                    "ファイルの構造を分析して",
                    "主要な機能を説明してください",
                ],
                "expected_points": [
                    "関数・クラスの識別",
                    "引数・戻り値の説明",
                    "処理内容の要約",
                    "主要な機能の説明"
                ],
                "evaluation_criteria": {
                    "accuracy": 0.4,      # 正確性
                    "completeness": 0.3,  # 完全性
                    "clarity": 0.2,       # 明確性
                    "efficiency": 0.1     # 効率性
                }
            },
            
            # レベル2: 中級シナリオ  
            "level2_problem_detection": {
                "category": "bug_detection",
                "request_templates": [
                    "このコードに問題がないかチェックして",
                    "バグがありそうな箇所を見つけて",
                    "改善できる点を教えて",
                    "品質に問題がないか確認して",
                ],
                "expected_points": [
                    "バグの特定",
                    "エラーハンドリングの問題",
                    "ロジックの不備",
                    "修正案の提示"
                ],
                "evaluation_criteria": {
                    "bug_detection_rate": 0.4,
                    "false_positive_rate": 0.2,
                    "fix_quality": 0.3,
                    "explanation_quality": 0.1
                }
            },
            
            "level2_performance_analysis": {
                "category": "performance",
                "request_templates": [
                    "パフォーマンスの問題を見つけて",
                    "最適化できる箇所はある？",
                    "実行効率を改善するには？",
                    "ボトルネックを特定して",
                ],
                "expected_points": [
                    "計算量の分析",
                    "非効率な処理の特定",
                    "最適化提案",
                    "メモリ使用量の問題"
                ],
                "evaluation_criteria": {
                    "bottleneck_identification": 0.4,
                    "optimization_quality": 0.3,
                    "feasibility": 0.2,
                    "performance_impact": 0.1
                }
            },
            
            # レベル3: 高級シナリオ
            "level3_ambiguous_request": {
                "category": "ambiguous_analysis",
                "request_templates": [
                    "このファイルをよくして",
                    "改善して",
                    "問題を解決して",
                    "最適化して",
                    "何か問題がないかチェック",
                ],
                "expected_points": [
                    "要求の明確化質問",
                    "包括的な分析",
                    "優先度付きの改善提案",
                    "段階的な実装計画"
                ],
                "evaluation_criteria": {
                    "clarification_questions": 0.3,
                    "comprehensive_analysis": 0.3,
                    "prioritization": 0.2,
                    "actionability": 0.2
                }
            },
            
            "level3_context_dependent": {
                "category": "context_analysis",
                "request_templates": [
                    "このファイルの設計が適切か評価して",
                    "現代的なベストプラクティスに合っているか？",
                    "アーキテクチャの観点から分析して",
                    "保守性を向上させるには？",
                ],
                "expected_points": [
                    "設計パターンの特定",
                    "アーキテクチャ評価",
                    "モダンな実装手法の提案",
                    "保守性・拡張性の改善案"
                ],
                "evaluation_criteria": {
                    "design_understanding": 0.3,
                    "modern_practices": 0.3,
                    "maintainability": 0.2,
                    "scalability": 0.2
                }
            }
        }
    
    def generate_scenario(self, level: Optional[int] = None, category: Optional[str] = None) -> FileAnalysisScenario:
        """ランダムまたは指定条件でシナリオを生成"""
        
        # 利用可能なファイルをスキャン
        available_files = self._scan_test_files()
        
        if not available_files:
            raise ValueError(f"No test files found in {self.samples_dir}")
        
        # レベルによるファイルフィルタリング
        if level:
            available_files = [f for f in available_files if f.get('level') == level]
        
        if not available_files:
            # フォールバック: レベル指定なしで選択
            available_files = self._scan_test_files()
        
        # ランダムにファイルを選択
        selected_file = random.choice(available_files)
        file_level = selected_file.get('level', 1)
        
        # レベルに応じたテンプレート選択
        template_key = self._select_template_by_level(file_level, category)
        template = self.scenario_templates[template_key]
        
        # ユーザー要求をランダム生成
        user_request = random.choice(template["request_templates"])
        
        # 曖昧性を追加（レベル3の場合）
        if file_level >= 3:
            user_request = self._add_ambiguity(user_request)
        
        # シナリオ生成
        scenario_id = f"{template_key}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{random.randint(1000,9999)}"
        
        scenario = FileAnalysisScenario(
            scenario_id=scenario_id,
            level=file_level,
            category=template["category"],
            title=f"Level {file_level} - {template['category'].replace('_', ' ').title()}",
            description=self._generate_scenario_description(template, selected_file),
            file_path=str(selected_file['path']),
            user_request=user_request,
            expected_analysis_points=template["expected_points"],
            evaluation_criteria=template["evaluation_criteria"],
            difficulty_factors=selected_file.get('challenges', []),
            context_info=selected_file.get('context')
        )
        
        return scenario
    
    def generate_challenge_scenarios(self, count: int = 5) -> List[FileAnalysisScenario]:
        """挑戦的なシナリオを複数生成"""
        scenarios = []
        
        # レベル別に生成
        level_distribution = [1, 1, 2, 2, 3]  # レベル1:2個、レベル2:2個、レベル3:1個
        
        for i in range(count):
            level = level_distribution[i] if i < len(level_distribution) else random.randint(1, 3)
            scenario = self.generate_scenario(level=level)
            scenarios.append(scenario)
        
        return scenarios
    
    def _scan_test_files(self) -> List[Dict]:
        """テストファイルをスキャンしてメタデータ付きで返す"""
        files = []
        
        file_metadata = {
            "level1_simple_python.py": {
                "level": 1,
                "type": "python",
                "challenges": ["基本的な関数解析"],
                "context": "単純な数学計算関数"
            },
            "level1_config.json": {
                "level": 1,
                "type": "json",
                "challenges": ["設定ファイル構造理解"],
                "context": "アプリケーション設定"
            },
            "level1_readme.md": {
                "level": 1,
                "type": "markdown",
                "challenges": ["ドキュメント要約"],
                "context": "プロジェクト説明書"
            },
            "level2_complex_class.py": {
                "level": 2,
                "type": "python",
                "challenges": ["クラス継承", "抽象化", "デザインパターン"],
                "context": "データ処理フレームワーク"
            },
            "level2_buggy_code.py": {
                "level": 2,
                "type": "python", 
                "challenges": ["バグ検出", "セキュリティ問題", "エラーハンドリング"],
                "context": "バグを含む本番コード"
            },
            "level2_performance_issues.py": {
                "level": 2,
                "type": "python",
                "challenges": ["パフォーマンス分析", "計算量改善", "メモリ効率"],
                "context": "非効率なアルゴリズム実装"
            },
            "level3_legacy_code.py": {
                "level": 3,
                "type": "python",
                "challenges": ["レガシーコード分析", "現代化提案", "技術的負債"],
                "context": "Python 2時代の古いコード"
            },
            "level3_incomplete_code.js": {
                "level": 3,
                "type": "javascript",
                "challenges": ["不完全コード分析", "要求明確化", "設計推測"],
                "context": "開発途中のJavaScriptアプリケーション"
            },
            "level3_microservice_config.yaml": {
                "level": 3,
                "type": "yaml",
                "challenges": ["複雑な設定分析", "セキュリティ評価", "運用考慮"],
                "context": "マイクロサービス構成ファイル"
            },
            "specialized_ml_model.py": {
                "level": 3,
                "type": "python",
                "challenges": ["機械学習知識", "専門的評価", "ハイパーパラメータ"],
                "context": "TensorFlow CNN実装"
            }
        }
        
        for filename, metadata in file_metadata.items():
            file_path = self.samples_dir / filename
            if file_path.exists():
                files.append({
                    "path": file_path,
                    **metadata
                })
        
        return files
    
    def _select_template_by_level(self, level: int, category: Optional[str] = None) -> str:
        """レベルとカテゴリに基づいてテンプレートを選択"""
        
        level_templates = {
            1: ["level1_simple_analysis"],
            2: ["level2_problem_detection", "level2_performance_analysis"],
            3: ["level3_ambiguous_request", "level3_context_dependent"]
        }
        
        candidates = level_templates.get(level, level_templates[1])
        
        # カテゴリ指定がある場合はフィルタリング
        if category:
            filtered = [t for t in candidates 
                       if self.scenario_templates[t]["category"] == category]
            candidates = filtered if filtered else candidates
        
        return random.choice(candidates)
    
    def _add_ambiguity(self, request: str) -> str:
        """要求に曖昧さを追加（レベル3用）"""
        ambiguous_modifiers = [
            "なんか", "ちょっと", "もう少し", "いい感じに", "適切に"
        ]
        
        vague_endings = [
            "してください", "して", "してもらえる？", "できる？", "お願いします"
        ]
        
        if random.random() < 0.3:  # 30%の確率で曖昧な修飾語を追加
            modifier = random.choice(ambiguous_modifiers)
            request = f"{modifier}{request}"
        
        if random.random() < 0.2:  # 20%の確率で曖昧な結びに変更
            ending = random.choice(vague_endings)
            # 既存の結びを置換
            for old_ending in ["してください", "して", "してもらえる？", "できる？"]:
                if request.endswith(old_ending):
                    request = request.replace(old_ending, ending)
                    break
        
        return request
    
    def _generate_scenario_description(self, template: Dict, file_info: Dict) -> str:
        """シナリオの説明を生成"""
        
        descriptions = {
            "code_structure": f"{file_info['type']}ファイルの構造分析タスク。{file_info.get('context', '')}の理解が求められる。",
            "bug_detection": f"バグ検出タスク。{file_info.get('context', '')}に含まれる問題を特定する必要がある。",
            "performance": f"パフォーマンス分析タスク。{file_info.get('context', '')}の効率性を評価し改善提案を行う。",
            "ambiguous_analysis": f"曖昧な要求に対する分析タスク。適切な質問で要求を明確化する必要がある。",
            "context_analysis": f"文脈を考慮した高度な分析タスク。{file_info.get('context', '')}の設計思想を理解する。"
        }
        
        return descriptions.get(template["category"], "ファイル内容の分析タスク")
    
    def create_scenario_batch(self, batch_size: int = 10) -> Dict:
        """評価用のシナリオバッチを作成"""
        
        scenarios = []
        
        # レベル別に分散させて生成
        level_counts = {1: batch_size // 3, 2: batch_size // 3, 3: batch_size - (batch_size // 3) * 2}
        
        for level, count in level_counts.items():
            for _ in range(count):
                scenario = self.generate_scenario(level=level)
                scenarios.append(scenario)
        
        # バッチ情報
        batch_info = {
            "batch_id": f"file_analysis_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "created_at": datetime.now().isoformat(),
            "total_scenarios": len(scenarios),
            "level_distribution": level_counts,
            "scenarios": scenarios
        }
        
        return batch_info

# テスト用関数
def demo_scenario_generation():
    """シナリオ生成のデモ"""
    
    generator = FileAnalysisScenarioGenerator()
    
    print("=== ファイル解析シナリオ生成デモ ===\n")
    
    # 各レベルのシナリオを生成
    for level in [1, 2, 3]:
        print(f"【レベル {level} シナリオ】")
        scenario = generator.generate_scenario(level=level)
        
        print(f"ID: {scenario.scenario_id}")
        print(f"タイトル: {scenario.title}")
        print(f"カテゴリ: {scenario.category}")
        print(f"ファイル: {Path(scenario.file_path).name}")
        print(f"ユーザー要求: {scenario.user_request}")
        print(f"期待分析ポイント: {', '.join(scenario.expected_analysis_points[:3])}")
        print(f"困難要因: {', '.join(scenario.difficulty_factors)}")
        print(f"説明: {scenario.description}")
        print("-" * 50)
    
    # バッチ生成デモ
    print("\n【バッチ生成デモ】")
    batch = generator.create_scenario_batch(batch_size=5)
    print(f"バッチID: {batch['batch_id']}")
    print(f"総シナリオ数: {batch['total_scenarios']}")
    print(f"レベル分布: {batch['level_distribution']}")

if __name__ == "__main__":
    demo_scenario_generation()