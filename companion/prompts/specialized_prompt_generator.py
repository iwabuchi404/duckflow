"""
SpecializedPromptGenerator - Phase 3: 専門知識と手順書の生成
DuckFlowのSpecialized Prompt（手順書）を生成する
"""

from typing import Dict, Any, Optional, List
from datetime import datetime


class SpecializedPromptGenerator:
    """専門知識と手順書の生成器"""
    
    def __init__(self):
        self.specialized_templates = {
            "PLANNING": self._get_planning_template(),
            "EXECUTION": self._get_execution_template(),
            "REVIEW": self._get_review_template()
        }
        
        self.quality_standards = {
            "PLANNING": [
                "各ステップは具体的で実行可能",
                "リスクは適切に評価されている",
                "成功基準は測定可能"
            ],
            "EXECUTION": [
                "安全性チェックが完了している",
                "段階的な実行と進捗確認",
                "エラーハンドリングと復旧"
            ],
            "REVIEW": [
                "内容の正確性（仕様との一致）",
                "安全性（リスクの評価）",
                "品質（パフォーマンス、保守性）"
            ]
        }
    
    def generate(self, step: str, agent_state: Optional[Dict[str, Any]] = None) -> str:
        """Specialized Promptを生成"""
        if step not in self.specialized_templates:
            raise ValueError(f"サポートされていないステップ: {step}")
        
        template = self.specialized_templates[step]
        quality_standards = self.quality_standards[step]
        
        # AgentStateから必要な情報を抽出
        context_info = self._extract_context_info(step, agent_state) if agent_state else {}
        
        # プロンプトを構築
        prompt = self._build_specialized_prompt(step, template, quality_standards, context_info)
        
        return prompt
    
    def _get_planning_template(self) -> Dict[str, str]:
        """計画作成用のテンプレート"""
        return {
            "title": "計画作成の専門知識・手順書",
            "procedure": [
                "要求の分析と分解（最大3つのステップ）",
                "必要なリソースの特定",
                "リスク評価（低/中/高）",
                "成功基準の設定（具体的で測定可能）"
            ],
            "output_format": """プラン名: [プランの名称]
目的: [達成したいこと]
ステップ:
  1. [ステップ1の詳細]
  2. [ステップ2の詳細]
  3. [ステップ3の詳細]
リスク: [想定されるリスク]
成功基準: [成功の判断基準]""",
            "focus": "計画の品質と実行可能性"
        }
    
    def _get_execution_template(self) -> Dict[str, str]:
        """実行用のテンプレート"""
        return {
            "title": "実行の専門知識・手順書",
            "procedure": [
                "計画の確認と準備",
                "安全性チェック（ファイル操作、システム影響）",
                "段階的な実行と進捗確認",
                "エラーハンドリングと復旧"
            ],
            "safety_check": [
                "ファイル操作の安全性（パス、権限、バックアップ）",
                "システムへの影響（リソース、依存関係）",
                "データの整合性（入力値、出力値）"
            ],
            "progress_management": [
                "各ステップの完了確認",
                "エラー発生時の適切な処理",
                "ユーザーへの進捗報告"
            ],
            "focus": "安全性と進捗管理"
        }
    
    def _get_review_template(self) -> Dict[str, str]:
        """レビュー用のテンプレート"""
        return {
            "title": "レビューの専門知識・手順書",
            "review_points": [
                "内容の正確性（仕様との一致）",
                "安全性（リスクの評価）",
                "品質（パフォーマンス、保守性）",
                "改善点（効率化、最適化）"
            ],
            "evaluation_criteria": {
                "良い": "仕様を満たし、安全で高品質",
                "普通": "基本的な要求は満たしている",
                "要改善": "問題があり、修正が必要"
            },
            "output_format": """評価: [良い/普通/要改善]
問題点: [発見された問題]
改善提案: [具体的な改善案]
承認可否: [承認/要修正/拒否]""",
            "focus": "品質評価と改善提案"
        }
    
    def _extract_context_info(self, step: str, agent_state: Dict[str, Any]) -> Dict[str, Any]:
        """AgentStateから必要な情報を抽出"""
        context_info = {}
        
        # 基本情報
        if 'goal' in agent_state:
            context_info['goal'] = agent_state['goal']
        if 'constraints' in agent_state:
            context_info['constraints'] = agent_state['constraints']
        if 'plan_brief' in agent_state:
            context_info['plan_brief'] = agent_state['plan_brief']
        
        # ステップ固有の情報
        if step == "PLANNING":
            if 'open_questions' in agent_state:
                context_info['open_questions'] = agent_state['open_questions']
        
        elif step == "EXECUTION":
            if 'context_refs' in agent_state:
                context_info['file_references'] = [
                    ref for ref in agent_state['context_refs'] 
                    if ref.startswith('file:')
                ]
        
        elif step == "REVIEW":
            if 'decision_log' in agent_state:
                context_info['recent_decisions'] = agent_state['decision_log'][-3:]
        
        return context_info
    
    def _build_specialized_prompt(self, step: str, template: Dict[str, Any], 
                                 quality_standards: List[str], 
                                 context_info: Dict[str, Any]) -> str:
        """Specialized Promptを構築"""
        prompt_parts = []
        
        # タイトル
        prompt_parts.append(f"# {template['title']}")
        prompt_parts.append("")
        
        # 手順
        if 'procedure' in template:
            prompt_parts.append("## 手順")
            for i, procedure in enumerate(template['procedure'], 1):
                prompt_parts.append(f"{i}. {procedure}")
            prompt_parts.append("")
        
        # 安全性チェック（EXECUTION用）
        if step == "EXECUTION" and 'safety_check' in template:
            prompt_parts.append("## 安全性チェック項目")
            for check_item in template['safety_check']:
                prompt_parts.append(f"- {check_item}")
            prompt_parts.append("")
        
        # 進捗管理（EXECUTION用）
        if step == "EXECUTION" and 'progress_management' in template:
            prompt_parts.append("## 進捗管理")
            for mgmt_item in template['progress_management']:
                prompt_parts.append(f"- {mgmt_item}")
            prompt_parts.append("")
        
        # レビューポイント（REVIEW用）
        if step == "REVIEW" and 'review_points' in template:
            prompt_parts.append("## レビューの観点")
            for i, point in enumerate(template['review_points'], 1):
                prompt_parts.append(f"{i}. {point}")
            prompt_parts.append("")
        
        # 評価基準（REVIEW用）
        if step == "REVIEW" and 'evaluation_criteria' in template:
            prompt_parts.append("## 評価基準")
            for level, description in template['evaluation_criteria'].items():
                prompt_parts.append(f"- {level}: {description}")
            prompt_parts.append("")
        
        # 出力形式
        if 'output_format' in template:
            prompt_parts.append("## 出力形式")
            prompt_parts.append("```")
            prompt_parts.append(template['output_format'])
            prompt_parts.append("```")
            prompt_parts.append("")
        
        # 品質基準
        prompt_parts.append("## 品質基準")
        for standard in quality_standards:
            prompt_parts.append(f"- {standard}")
        prompt_parts.append("")
        
        # 文脈情報
        if context_info:
            prompt_parts.append("## 現在の文脈")
            if 'goal' in context_info:
                prompt_parts.append(f"目標: {context_info['goal']}")
            if 'constraints' in context_info:
                constraints_str = ', '.join(context_info['constraints'])
                prompt_parts.append(f"制約: {constraints_str}")
            if 'plan_brief' in context_info:
                plan_str = ', '.join(context_info['plan_brief'])
                prompt_parts.append(f"計画概要: {plan_str}")
            
            # ステップ固有の文脈
            if step == "PLANNING" and 'open_questions' in context_info:
                questions_str = ', '.join(context_info['open_questions'])
                prompt_parts.append(f"未解決の問い: {questions_str}")
            
            elif step == "EXECUTION" and 'file_references' in context_info:
                files_str = ', '.join([ref[5:] for ref in context_info['file_references']])
                prompt_parts.append(f"関連ファイル: {files_str}")
            
            elif step == "REVIEW" and 'recent_decisions' in context_info:
                decisions_str = ', '.join(context_info['recent_decisions'])
                prompt_parts.append(f"最近の決定: {decisions_str}")
            
            prompt_parts.append("")
        
        # 焦点
        if 'focus' in template:
            prompt_parts.append(f"## 焦点")
            prompt_parts.append(f"このステップでは「{template['focus']}」に集中してください。")
            prompt_parts.append("")
        
        return "\n".join(prompt_parts)
    
    def get_supported_steps(self) -> List[str]:
        """サポートされているステップを取得"""
        return list(self.specialized_templates.keys())
    
    def get_template_info(self, step: str) -> Optional[Dict[str, Any]]:
        """テンプレート情報を取得"""
        if step in self.specialized_templates:
            return {
                'step': step,
                'template': self.specialized_templates[step],
                'quality_standards': self.quality_standards[step]
            }
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """設定を辞書形式で取得"""
        return {
            'supported_steps': self.get_supported_steps(),
            'templates': self.specialized_templates,
            'quality_standards': self.quality_standards
        }
