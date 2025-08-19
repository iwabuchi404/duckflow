"""
PromptRouter - Phase 3: 3パターンの適切な選択
DuckFlowのプロンプトルーティングシステムを実装する
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from .base_prompt_generator import BasePromptGenerator
from .main_prompt_generator import MainPromptGenerator
from .specialized_prompt_generator import SpecializedPromptGenerator


class PromptRouter:
    """3パターンのプロンプトルーティング"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # 各コンポーネントの初期化
        self.base_generator = BasePromptGenerator()
        self.main_generator = MainPromptGenerator()
        self.specialized_generator = SpecializedPromptGenerator()
        
        # ルーティングルール
        self.routing_rules = self._initialize_routing_rules()
        
        # 使用統計
        self.usage_statistics = {
            'base_main': 0,
            'base_main_specialized': 0,
            'base_specialized': 0
        }
    
    def _initialize_routing_rules(self) -> Dict[str, Dict[str, Any]]:
        """ルーティングルールを初期化"""
        return {
            "base_main": {
                "description": "軽い会話、基本的な応答",
                "conditions": [
                    "軽い会話や質問",
                    "ファイル読み取り",
                    "状況確認",
                    "基本的な応答"
                ],
                "priority": 1
            },
            "base_main_specialized": {
                "description": "ツールの前後や精度が必要な場面",
                "conditions": [
                    "計画作成",
                    "実行処理",
                    "レビュー作業",
                    "複雑なファイル操作",
                    "エラー処理と復旧"
                ],
                "priority": 2
            },
            "base_specialized": {
                "description": "方針が決まっていて細い作業だけ",
                "conditions": [
                    "特定のタスクに特化した処理",
                    "バッチ処理",
                    "自動化作業",
                    "専門的な作業"
                ],
                "priority": 3
            }
        }
    
    def select_prompt_pattern(self, 
                            agent_state: Optional[Dict[str, Any]] = None,
                            user_input: Optional[str] = None,
                            current_step: Optional[str] = None,
                            conversation_context: Optional[Dict[str, Any]] = None) -> str:
        """適切なプロンプトパターンを選択"""
        try:
            self.logger.info("プロンプトパターン選択開始")
            
            # 選択ロジック
            selected_pattern = self._determine_pattern(agent_state, user_input, current_step, conversation_context)
            
            # 統計更新
            self.usage_statistics[selected_pattern] += 1
            
            self.logger.info(f"プロンプトパターン選択完了: {selected_pattern}")
            return selected_pattern
            
        except Exception as e:
            self.logger.error(f"プロンプトパターン選択エラー: {e}")
            # エラー時はデフォルトパターンを返す
            return "base_main"
    
    def _determine_pattern(self, agent_state: Optional[Dict[str, Any]], 
                          user_input: Optional[str], 
                          current_step: Optional[str],
                          conversation_context: Optional[Dict[str, Any]]) -> str:
        """パターンを決定"""
        
        # 1. 現在のステップによる判定
        if current_step:
            step_based_pattern = self._get_pattern_by_step(current_step)
            if step_based_pattern:
                return step_based_pattern
        
        # 2. ユーザー入力の内容による判定
        if user_input:
            input_based_pattern = self._get_pattern_by_input(user_input)
            if input_based_pattern:
                return input_based_pattern
        
        # 3. AgentStateの状態による判定
        if agent_state:
            state_based_pattern = self._get_pattern_by_state(agent_state)
            if state_based_pattern:
                return state_based_pattern
        
        # 4. 会話コンテキストによる判定
        if conversation_context:
            context_based_pattern = self._get_pattern_by_context(conversation_context)
            if context_based_pattern:
                return context_based_pattern
        
        # デフォルトは base_main
        return "base_main"
    
    def _get_pattern_by_step(self, step: str) -> Optional[str]:
        """ステップによるパターン判定"""
        step_patterns = {
            "PLANNING": "base_main_specialized",
            "EXECUTION": "base_main_specialized",
            "REVIEW": "base_main_specialized",
            "AWAITING_APPROVAL": "base_main"
        }
        
        return step_patterns.get(step)
    
    def _get_pattern_by_input(self, user_input: str) -> Optional[str]:
        """ユーザー入力によるパターン判定"""
        input_lower = user_input.lower()
        
        # 複雑な処理のキーワード
        complex_keywords = [
            "計画", "プラン", "実装", "実行", "レビュー", "設計", "アーキテクチャ",
            "作成", "構築", "開発", "テスト", "検証", "最適化", "改善"
        ]
        
        # 軽い処理のキーワード
        light_keywords = [
            "確認", "説明", "教えて", "何", "どう", "なぜ", "いつ", "どこ",
            "読み取り", "表示", "見る", "調べる", "ファイル", "確認"
        ]
        
        # 専門的な処理のキーワード
        specialized_keywords = [
            "バッチ", "自動化", "スクリプト", "ツール", "ユーティリティ",
            "変換", "フォーマット", "検証", "チェック"
        ]
        
        # 判定ロジック（優先順位を明確化）
        # 1. 専門的な処理を最初にチェック
        if any(keyword in input_lower for keyword in specialized_keywords):
            return "base_specialized"
        # 2. 複雑な処理をチェック
        elif any(keyword in input_lower for keyword in complex_keywords):
            return "base_main_specialized"
        # 3. 軽い処理をチェック
        elif any(keyword in input_lower for keyword in light_keywords):
            return "base_main"
        
        return None
    
    def _get_pattern_by_state(self, agent_state: Dict[str, Any]) -> Optional[str]:
        """AgentStateによるパターン判定"""
        
        # 進行中のタスクの複雑さ
        ongoing_task = agent_state.get('ongoing_task', '')
        if ongoing_task:
            if any(keyword in ongoing_task.lower() for keyword in ["実装", "実行", "開発", "構築"]):
                return "base_main_specialized"
        
        # 固定5項目の内容
        goal = agent_state.get('goal', '')
        if goal:
            if any(keyword in goal.lower() for keyword in ["計画", "実装", "実行", "レビュー"]):
                return "base_main_specialized"
        
        # 制約の複雑さ
        constraints = agent_state.get('constraints', [])
        if len(constraints) > 2:  # 制約が多い場合は複雑
            return "base_main_specialized"
        
        return None
    
    def _get_pattern_by_context(self, conversation_context: Dict[str, Any]) -> Optional[str]:
        """会話コンテキストによるパターン判定"""
        
        # 会話の長さ
        conversation_length = conversation_context.get('length', 0)
        if conversation_length > 10:  # 長い会話は複雑
            return "base_main_specialized"
        
        # 最近の操作の種類
        recent_operations = conversation_context.get('recent_operations', [])
        if recent_operations:
            complex_ops = ["file_write", "file_create", "file_delete", "command_execute"]
            if any(op in recent_operations for op in complex_ops):
                return "base_main_specialized"
        
        return None
    
    def generate_prompt(self, pattern: str, 
                       agent_state: Optional[Dict[str, Any]] = None,
                       conversation_history: Optional[List[Dict[str, Any]]] = None,
                       session_data: Optional[Dict[str, Any]] = None,
                       specialized_step: Optional[str] = None) -> str:
        """選択されたパターンでプロンプトを生成"""
        try:
            self.logger.info(f"プロンプト生成開始: パターン={pattern}")
            
            if pattern == "base_main":
                return self._generate_base_main_prompt(agent_state, conversation_history, session_data)
            elif pattern == "base_main_specialized":
                return self._generate_base_main_specialized_prompt(agent_state, conversation_history, session_data, specialized_step)
            elif pattern == "base_specialized":
                return self._generate_base_specialized_prompt(agent_state, session_data, specialized_step)
            else:
                raise ValueError(f"サポートされていないパターン: {pattern}")
                
        except Exception as e:
            self.logger.error(f"プロンプト生成エラー: {e}")
            # エラー時は base_main を返す
            return self._generate_base_main_prompt(agent_state, conversation_history, session_data)
    
    def _generate_base_main_prompt(self, agent_state: Optional[Dict[str, Any]], 
                                  conversation_history: Optional[List[Dict[str, Any]]], 
                                  session_data: Optional[Dict[str, Any]]) -> str:
        """Base + Main プロンプトを生成"""
        base_prompt = self.base_generator.generate(session_data)
        main_prompt = self.main_generator.generate(agent_state)
        
        separator = "\n\n" + "="*50 + "\n\n"
        return base_prompt + separator + main_prompt
    
    def _generate_base_main_specialized_prompt(self, agent_state: Optional[Dict[str, Any]], 
                                             conversation_history: Optional[List[Dict[str, Any]]], 
                                             session_data: Optional[Dict[str, Any]],
                                             specialized_step: Optional[str]) -> str:
        """Base + Main + Specialized プロンプトを生成"""
        base_prompt = self.base_generator.generate(session_data)
        main_prompt = self.main_generator.generate(agent_state)
        
        # Specialized Promptの生成
        if specialized_step:
            specialized_prompt = self.specialized_generator.generate(specialized_step, agent_state)
        else:
            # ステップが指定されていない場合は、AgentStateから推測
            current_step = agent_state.get('step', 'PLANNING') if agent_state else 'PLANNING'
            specialized_prompt = self.specialized_generator.generate(current_step, agent_state)
        
        separator = "\n\n" + "="*50 + "\n\n"
        return base_prompt + separator + main_prompt + separator + specialized_prompt
    
    def _generate_base_specialized_prompt(self, agent_state: Optional[Dict[str, Any]], 
                                        session_data: Optional[Dict[str, Any]],
                                        specialized_step: Optional[str]) -> str:
        """Base + Specialized プロンプトを生成"""
        base_prompt = self.base_generator.generate(session_data)
        
        # Specialized Promptの生成
        if specialized_step:
            specialized_prompt = self.specialized_generator.generate(specialized_step, agent_state)
        else:
            # ステップが指定されていない場合は、AgentStateから推測
            current_step = agent_state.get('step', 'PLANNING') if agent_state else 'PLANNING'
            specialized_prompt = self.specialized_generator.generate(current_step, agent_state)
        
        separator = "\n\n" + "="*50 + "\n\n"
        return base_prompt + separator + specialized_prompt
    
    def get_routing_rules(self) -> Dict[str, Dict[str, Any]]:
        """ルーティングルールを取得"""
        return self.routing_rules.copy()
    
    def get_usage_statistics(self) -> Dict[str, int]:
        """使用統計を取得"""
        return self.usage_statistics.copy()
    
    def reset_statistics(self):
        """統計をリセット"""
        for key in self.usage_statistics:
            self.usage_statistics[key] = 0
        self.logger.info("使用統計をリセットしました")
    
    def get_pattern_recommendation(self, 
                                 agent_state: Optional[Dict[str, Any]] = None,
                                 user_input: Optional[str] = None) -> List[Tuple[str, str, float]]:
        """パターンの推奨度を取得"""
        recommendations = []
        
        for pattern, rule in self.routing_rules.items():
            score = 0.0
            
            # ステップによるスコア
            if agent_state and 'step' in agent_state:
                step = agent_state['step']
                if pattern == "base_main_specialized" and step in ["PLANNING", "EXECUTION", "REVIEW"]:
                    score += 0.4
                elif pattern == "base_main" and step == "AWAITING_APPROVAL":
                    score += 0.4
            
            # 入力内容によるスコア
            if user_input:
                input_score = self._calculate_input_score(user_input, pattern)
                score += input_score * 0.3
            
            # 優先度によるスコア
            priority_score = (4 - rule['priority']) / 3  # 1.0 (最高) から 0.33 (最低)
            score += priority_score * 0.3
            
            recommendations.append((pattern, rule['description'], score))
        
        # スコア順にソート
        recommendations.sort(key=lambda x: x[2], reverse=True)
        return recommendations
    
    def _calculate_input_score(self, user_input: str, pattern: str) -> float:
        """入力内容によるスコアを計算"""
        input_lower = user_input.lower()
        
        if pattern == "base_main_specialized":
            complex_keywords = ["計画", "実装", "実行", "レビュー", "設計", "開発"]
            return sum(0.15 for keyword in complex_keywords if keyword in input_lower)
        
        elif pattern == "base_specialized":
            specialized_keywords = ["バッチ", "自動化", "スクリプト", "ツール", "変換"]
            return sum(0.15 for keyword in specialized_keywords if keyword in input_lower)
        
        elif pattern == "base_main":
            light_keywords = ["確認", "説明", "教えて", "何", "どう", "なぜ"]
            return sum(0.15 for keyword in light_keywords if keyword in input_lower)
        
        return 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """設定を辞書形式で取得"""
        return {
            'routing_rules': self.routing_rules,
            'usage_statistics': self.usage_statistics,
            'supported_patterns': list(self.routing_rules.keys())
        }

    def get_supported_steps(self) -> List[str]:
        """SpecializedPromptGeneratorがサポートするステップ名を返す"""
        try:
            return self.specialized_generator.get_supported_steps()
        except Exception:
            # フォールバック（基本3ステップ）
            return ["PLANNING", "EXECUTION", "REVIEW"]
