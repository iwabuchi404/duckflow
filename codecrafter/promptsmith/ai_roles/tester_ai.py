"""
Tester AI - 曖昧・複雑な開発指示を生成するAI

プロンプト改善のために意図的に挑戦的なシナリオを生成します。
"""

import json
import random
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from codecrafter.promptsmith.llm_manager import promptsmith_llm_manager


@dataclass
class ChallengeScenario:
    """挑戦的なテストシナリオの定義"""
    scenario_id: str
    name: str
    description: str
    user_request: str
    difficulty: str  # easy, medium, hard, extreme
    challenge_type: str  # ambiguous, incomplete, changing, complex
    expected_challenges: List[str]  # 予想される困難点
    success_criteria: Dict[str, Any]  # 成功基準
    

class TesterAI:
    """曖昧・複雑な開発指示を生成するAI"""
    
    def __init__(self):
        """TesterAIの初期化"""
        self.scenario_templates = self._load_scenario_templates()
        self.difficulty_levels = ["easy", "medium", "hard", "extreme"]
        self.challenge_types = [
            "ambiguous",     # 曖昧な要求
            "incomplete",    # 不完全な情報
            "changing",      # 仕様変更
            "complex",       # 複雑な要求
            "contradictory", # 矛盾した要求
            "vague_domain"   # ドメイン知識が曖昧
        ]
        self.llm_manager = promptsmith_llm_manager
    
    def generate_challenging_scenario(self, difficulty: str = "medium", 
                                    challenge_type: Optional[str] = None) -> ChallengeScenario:
        """
        挑戦的なシナリオ生成
        
        Args:
            difficulty: 難易度レベル
            challenge_type: 挑戦タイプ（Noneで自動選択）
            
        Returns:
            生成されたシナリオ
        """
        if challenge_type is None:
            challenge_type = random.choice(self.challenge_types)
        
        if difficulty not in self.difficulty_levels:
            difficulty = "medium"
        
        # シナリオテンプレートから選択
        template = self._select_template(difficulty, challenge_type)
        
        # 具体的なシナリオに展開
        scenario = self._expand_scenario_template(template, difficulty, challenge_type)
        
        return scenario
    
    def create_ambiguous_request(self, scenario_type: str) -> str:
        """
        意図的に曖昧な要求を生成
        
        Args:
            scenario_type: シナリオタイプ
            
        Returns:
            曖昧な要求文
        """
        ambiguous_patterns = {
            "web_app": [
                "ウェブサイトを作ってください",
                "ユーザーが使いやすいシステムを作ってほしい",
                "モダンな感じのアプリを作成してください",
                "データを管理できるツールが必要です"
            ],
            "data_analysis": [
                "データを分析してください",
                "レポートを作成してほしい", 
                "傾向を調べてください",
                "重要な情報を抽出してください"
            ],
            "automation": [
                "作業を自動化してください",
                "効率的な処理を実装してほしい",
                "手動でやっていることを楽にしたい",
                "繰り返し作業をなくしてください"
            ],
            "api": [
                "APIを作ってください",
                "システム連携を実装してほしい",
                "データのやり取りができるようにしてください",
                "他のサービスと繋げたい"
            ]
        }
        
        if scenario_type not in ambiguous_patterns:
            scenario_type = random.choice(list(ambiguous_patterns.keys()))
        
        return random.choice(ambiguous_patterns[scenario_type])
    
    def simulate_spec_change(self, original_request: str) -> str:
        """
        仕様変更の追加要求を生成
        
        Args:
            original_request: 元の要求
            
        Returns:
            仕様変更要求
        """
        change_patterns = [
            f"すみません、{original_request}について、実は認証機能も必要でした。",
            f"{original_request}に加えて、管理者画面も作ってください。",
            f"要件を確認したところ、{original_request}では足りないことが分かりました。レスポンシブ対応も必要です。",
            f"{original_request}の件で、上司から変更指示がありました。データベース設計も見直してください。",
            f"クライアントから追加要望が来ました。{original_request}にエクスポート機能も追加してください。",
            f"{original_request}について、セキュリティ要件も満たす必要があることが判明しました。"
        ]
        
        return random.choice(change_patterns)
    
    def generate_ai_powered_scenario(self, context: str, difficulty: str = "medium") -> ChallengeScenario:
        """
        AIを使用してコンテキストに応じた挑戦的シナリオを生成
        
        Args:
            context: シナリオのコンテキスト（プロジェクトの内容など）
            difficulty: 難易度
            
        Returns:
            生成されたシナリオ
        """
        prompt = f"""以下のコンテキストに基づいて、挑戦的な開発シナリオを生成してください。

コンテキスト: {context}
難易度: {difficulty}

以下の条件を満たすシナリオを作成してください：
1. 実際の開発現場で起こりうる状況
2. 適度に曖昧で、AI が要件を明確化する必要がある
3. 複数の解決策が考えられる問題

以下のJSON形式で回答してください：
{{
    "name": "シナリオ名",
    "description": "シナリオの説明",
    "user_request": "ユーザーからの要求（意図的に曖昧に）",
    "challenge_type": "ambiguous|incomplete|complex|contradictory",
    "expected_challenges": ["予想される困難点1", "予想される困難点2"],
    "success_criteria": {{"評価観点": "期待される結果"}}
}}
"""
        
        try:
            response = self.llm_manager.chat_with_role("tester_ai", prompt)
            # JSONを解析してシナリオオブジェクトを作成
            scenario_data = json.loads(response)
            
            return ChallengeScenario(
                scenario_id=f"ai_generated_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                name=scenario_data["name"],
                description=scenario_data["description"],
                user_request=scenario_data["user_request"],
                difficulty=difficulty,
                challenge_type=scenario_data["challenge_type"],
                expected_challenges=scenario_data["expected_challenges"],
                success_criteria=scenario_data["success_criteria"]
            )
        except Exception as e:
            print(f"[WARNING] AI-powered scenario generation failed: {e}")
            # フォールバックとして基本的なシナリオを生成
            return self.generate_challenging_scenario(difficulty)
    
    def analyze_scenario_difficulty(self, scenario: ChallengeScenario) -> Dict[str, Any]:
        """
        シナリオの難易度を詳細分析
        
        Args:
            scenario: 分析対象のシナリオ
            
        Returns:
            難易度分析結果
        """
        analysis_prompt = f"""以下のシナリオの難易度と挑戦要素を分析してください：

シナリオ名: {scenario.name}
ユーザー要求: {scenario.user_request}
挑戦タイプ: {scenario.challenge_type}
予想される困難点: {scenario.expected_challenges}

以下の観点で分析し、JSON形式で回答してください：
{{
    "estimated_difficulty": "easy|medium|hard|extreme",
    "complexity_factors": ["要因1", "要因2"],
    "required_skills": ["必要スキル1", "必要スキル2"],
    "estimated_dialogue_rounds": "予想対話回数",
    "success_probability": "成功確率（0-1）",
    "improvement_suggestions": ["改善提案1", "改善提案2"]
}}
"""
        
        try:
            response = self.llm_manager.chat_with_role("tester_ai", analysis_prompt)
            return json.loads(response)
        except Exception as e:
            print(f"[WARNING] Scenario analysis failed: {e}")
            return {
                "estimated_difficulty": scenario.difficulty,
                "complexity_factors": ["分析失敗"],
                "required_skills": ["不明"],
                "estimated_dialogue_rounds": "3-5",
                "success_probability": 0.5,
                "improvement_suggestions": ["AI分析が利用できませんでした"]
            }
    
    def generate_incomplete_scenario(self) -> ChallengeScenario:
        """不完全な情報のシナリオを生成"""
        scenarios = [
            {
                "name": "不完全なEコマース要求",
                "user_request": "オンラインショップを作ってください。商品は色々あります。",
                "expected_challenges": [
                    "商品の種類が不明",
                    "決済方法が未定義",
                    "在庫管理要件が不明",
                    "ユーザー登録仕様が不明"
                ]
            },
            {
                "name": "曖昧なデータ分析要求", 
                "user_request": "売上データを分析して、改善提案をしてください。データはCSVファイルです。",
                "expected_challenges": [
                    "データ形式の詳細不明",
                    "分析期間が不明",
                    "改善の観点が不明確",
                    "出力形式が未指定"
                ]
            },
            {
                "name": "不明確なAPI要求",
                "user_request": "他のシステムと連携するAPIを作ってください。",
                "expected_challenges": [
                    "連携先システムが不明",
                    "データフォーマットが不明",
                    "認証方式が未定義",
                    "エラーハンドリング要件が不明"
                ]
            }
        ]
        
        template = random.choice(scenarios)
        
        return ChallengeScenario(
            scenario_id=f"incomplete_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            name=template["name"],
            description="意図的に情報が不足している挑戦的なシナリオ",
            user_request=template["user_request"],
            difficulty="medium",
            challenge_type="incomplete",
            expected_challenges=template["expected_challenges"],
            success_criteria={
                "clarification_questions": "適切な質問をして要件を明確化",
                "implementation_quality": "明確化後の実装品質",
                "communication_effectiveness": "ユーザーとの効果的なコミュニケーション"
            }
        )
    
    def generate_contradictory_scenario(self) -> ChallengeScenario:
        """矛盾した要求のシナリオを生成"""
        contradictory_requests = [
            "高速で軽量、かつ多機能で豊富な機能を持つアプリを作ってください。",
            "セキュリティを最重視しつつ、ユーザビリティも最優先で設計してください。",
            "シンプルで使いやすい管理画面を作ってください。全ての機能にアクセスできるようにしてください。",
            "低予算で短期間に、高品質で拡張性の高いシステムを構築してください。"
        ]
        
        return ChallengeScenario(
            scenario_id=f"contradictory_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            name="矛盾する要求への対応",
            description="相反する要求を含む挑戦的なシナリオ",
            user_request=random.choice(contradictory_requests),
            difficulty="hard",
            challenge_type="contradictory",
            expected_challenges=[
                "矛盾する要求の識別",
                "優先度の確認",
                "現実的な解決策の提示",
                "トレードオフの説明"
            ],
            success_criteria={
                "contradiction_detection": "矛盾の識別",
                "priority_clarification": "優先度の明確化",
                "solution_feasibility": "現実的な解決策の提示"
            }
        )
    
    def generate_domain_specific_scenario(self, domain: str) -> ChallengeScenario:
        """
        ドメイン特化シナリオの生成
        
        Args:
            domain: 対象ドメイン（finance, healthcare, education, etc.）
            
        Returns:
            ドメイン特化シナリオ
        """
        domain_scenarios = {
            "finance": {
                "name": "金融システム開発",
                "request": "投資ポートフォリオ管理システムを作ってください。リスク計算も必要です。",
                "challenges": ["金融規制への対応", "リスク計算ロジック", "セキュリティ要件"],
                "domain_knowledge": ["金融商品の理解", "リスク管理理論", "規制要件"]
            },
            "healthcare": {
                "name": "医療データ管理",
                "request": "患者データ管理システムを作ってください。分析機能も含めて。", 
                "challenges": ["患者プライバシー保護", "医療データ標準", "法的規制対応"],
                "domain_knowledge": ["医療データ標準", "HIPAA規制", "診断コード"]
            },
            "education": {
                "name": "学習管理システム",
                "request": "オンライン学習プラットフォームを構築してください。進捗管理も必要です。",
                "challenges": ["学習効果測定", "個別最適化", "教師-学生インタラクション"],
                "domain_knowledge": ["教育理論", "学習分析", "評価手法"]
            }
        }
        
        if domain not in domain_scenarios:
            domain = random.choice(list(domain_scenarios.keys()))
        
        scenario_data = domain_scenarios[domain]
        
        return ChallengeScenario(
            scenario_id=f"domain_{domain}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            name=scenario_data["name"],
            description=f"{domain}ドメインの専門知識が必要なシナリオ",
            user_request=scenario_data["request"],
            difficulty="hard",
            challenge_type="vague_domain", 
            expected_challenges=scenario_data["challenges"],
            success_criteria={
                "domain_understanding": "ドメイン知識の適切な活用",
                "requirement_clarification": "専門要件の明確化",
                "solution_appropriateness": "ドメインに適したソリューション"
            }
        )
    
    def _load_scenario_templates(self) -> Dict[str, Any]:
        """シナリオテンプレートの読み込み"""
        # 実際の実装では外部ファイルから読み込み
        return {
            "basic_templates": [
                "simple_crud_app",
                "data_analysis_tool", 
                "api_service",
                "web_scraper"
            ],
            "complex_templates": [
                "microservice_architecture",
                "ml_pipeline",
                "real_time_system", 
                "enterprise_integration"
            ]
        }
    
    def _select_template(self, difficulty: str, challenge_type: str) -> Dict[str, Any]:
        """テンプレート選択ロジック"""
        return {
            "template_id": f"{challenge_type}_{difficulty}",
            "base_type": "web_app" if challenge_type == "ambiguous" else "general"
        }
    
    def _expand_scenario_template(self, template: Dict[str, Any], 
                                difficulty: str, challenge_type: str) -> ChallengeScenario:
        """テンプレートから具体的なシナリオに展開"""
        if challenge_type == "incomplete":
            return self.generate_incomplete_scenario()
        elif challenge_type == "contradictory":
            return self.generate_contradictory_scenario()
        elif challenge_type == "vague_domain":
            return self.generate_domain_specific_scenario("finance")
        else:
            # デフォルトの曖昧シナリオ
            return ChallengeScenario(
                scenario_id=f"ambiguous_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                name="曖昧な要求への対応",
                description="意図的に曖昧な要求を含むシナリオ",
                user_request=self.create_ambiguous_request("web_app"),
                difficulty=difficulty,
                challenge_type=challenge_type,
                expected_challenges=["要求の曖昧さ", "仕様の不明確さ", "優先度の未定義"],
                success_criteria={
                    "clarification_rate": 0.8,
                    "implementation_success": True,
                    "user_satisfaction": 0.7
                }
            )


# デモ実行用関数
def demo_tester_ai():
    """TesterAIのデモ実行"""
    print("=== TesterAI デモ実行 ===")
    
    tester = TesterAI()
    
    # 基本シナリオ生成
    print("\n1. 基本シナリオ生成:")
    scenario = tester.generate_challenging_scenario(difficulty="medium")
    print(f"シナリオ名: {scenario.name}")
    print(f"難易度: {scenario.difficulty}")
    print(f"挑戦タイプ: {scenario.challenge_type}")
    print(f"ユーザー要求: {scenario.user_request}")
    print(f"予想される困難: {scenario.expected_challenges}")
    
    # 曖昧な要求生成
    print("\n2. 曖昧な要求生成:")
    for scenario_type in ["web_app", "data_analysis", "automation"]:
        ambiguous_request = tester.create_ambiguous_request(scenario_type)
        print(f"{scenario_type}: {ambiguous_request}")
    
    # 仕様変更シミュレーション
    print("\n3. 仕様変更シミュレーション:")
    original = "ユーザー管理システムを作ってください"
    change_request = tester.simulate_spec_change(original)
    print(f"元の要求: {original}")
    print(f"変更要求: {change_request}")
    
    # 特殊シナリオ
    print("\n4. 矛盾シナリオ:")
    contradictory = tester.generate_contradictory_scenario()
    print(f"要求: {contradictory.user_request}")
    print(f"予想される困難: {contradictory.expected_challenges}")
    
    print("\n=== デモ完了 ===")


if __name__ == "__main__":
    demo_tester_ai()