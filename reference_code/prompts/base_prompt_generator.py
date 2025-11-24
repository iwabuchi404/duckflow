"""
BasePromptGenerator - 基本プロンプト生成器
Base/Mainコンテキストの生成を担当
"""

import logging
from typing import Dict, Any, Optional


class BasePromptGenerator:
    """基本プロンプト生成器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def generate_base_context(self) -> str:
        """Baseコンテキスト（システム設定・制約・安全ルール）を生成"""
        try:
            base_context = """あなたはDuckFlowのアシスタントです。

基本的なルール:
- 安全性を最優先に行動する
- ファイル操作前には必ず確認する
- エラーが発生した場合は適切に報告する
- ユーザーの要求を正確に理解し、適切な対応を行う

制約事項:
- 作業ディレクトリ外のファイル操作は禁止
- 危険なファイル拡張子（.exe, .bat等）の作成は禁止
- システムコマンドの実行は承認が必要

## 📏 応答制限の基本原則
### 応答の品質と長さ
- **簡潔性**: 必要最小限の情報で明確に回答
- **可読性**: 読みやすく、理解しやすい構造化された回答
- **実用性**: ユーザーが実際に活用できる具体的な情報
- **制限遵守**: 指定された文字数制限を必ず遵守

### 大容量データの扱い
- **自動要約**: 長い内容は自動的に要約版を提供
- **ツール連携**: 詳細が必要な場合は適切なツール使用を提案
- **段階的表示**: 概要→詳細の順で情報を提供

利用可能な機能:
- ファイル読み込み・書き込み・一覧表示
- コード解析・要約・生成
- 計画立案・実行管理
- 会話履歴の管理・要約"""
            
            return base_context
            
        except Exception as e:
            self.logger.error(f"Baseコンテキスト生成エラー: {e}")
            return self._get_fallback_base_context()
    
    def generate_main_context(self, context_data: Dict[str, Any]) -> str:
        """Mainコンテキスト（会話履歴・固定5項目・短期記憶）を生成"""
        try:
            main_context = "現在のコンテキスト:\n"
            
            # 固定5項目の情報を追加
            if context_data:
                main_context += self._format_context_data(context_data)
            else:
                main_context += "- コンテキスト情報が利用できません\n"
            
            # 短期記憶の情報を追加
            short_term = self._get_short_term_memory_context()
            if short_term:
                main_context += f"\n短期記憶:\n{short_term}"
            
            return main_context
            
        except Exception as e:
            self.logger.error(f"Mainコンテキスト生成エラー: {e}")
            return self._get_fallback_main_context()
    
    def _format_context_data(self, context_data: Dict[str, Any]) -> str:
        """コンテキストデータをフォーマット"""
        try:
            formatted = ""
            
            # 会話履歴
            if 'conversation_history' in context_data:
                history = context_data['conversation_history']
                if history:
                    formatted += f"- 会話履歴: {len(history)}件のメッセージ\n"
                    # 最新3件を表示
                    recent = history[-3:] if len(history) > 3 else history
                    for i, msg in enumerate(recent):
                        role = "ユーザー" if msg.get('role') == 'user' else "アシスタント"
                        content = msg.get('content', '')[:100]
                        formatted += f"  {i+1}. {role}: {content}...\n"
            
            # 現在のステップ・ステータス
            if 'current_step' in context_data:
                formatted += f"- 現在のステップ: {context_data['current_step']}\n"
            if 'current_status' in context_data:
                formatted += f"- 現在のステータス: {context_data['current_status']}\n"
            
            # 作業ディレクトリ
            if 'workspace' in context_data:
                workspace = context_data['workspace']
                if isinstance(workspace, dict) and 'work_dir' in workspace:
                    formatted += f"- 作業ディレクトリ: {workspace['work_dir']}\n"
            
            # 最後のタスク結果
            if 'last_task_result' in context_data:
                last_result = context_data['last_task_result']
                if last_result:
                    formatted += f"- 最後のタスク結果: {str(last_result)[:200]}...\n"
            
            return formatted if formatted else "- コンテキスト情報なし\n"
            
        except Exception as e:
            self.logger.error(f"コンテキストデータフォーマットエラー: {e}")
            return "- コンテキスト情報のフォーマットに失敗\n"
    
    def _get_short_term_memory_context(self) -> str:
        """短期記憶のコンテキストを取得"""
        try:
            # 現在は基本的な情報のみ
            # 将来的には実際の短期記憶システムと連携
            return "- 短期記憶: 利用可能\n"
        except Exception as e:
            self.logger.error(f"短期記憶コンテキスト取得エラー: {e}")
            return ""
    
    def _get_fallback_base_context(self) -> str:
        """フォールバック用のBaseコンテキスト"""
        return """あなたはDuckFlowのアシスタントです。
基本的なルール:
- 安全性を最優先に行動する
- ファイル操作前には必ず確認する
- エラーが発生した場合は適切に報告する"""
    
    def _get_fallback_main_context(self) -> str:
        """フォールバック用のMainコンテキスト"""
        return "現在のコンテキスト情報を取得できませんでした。基本的な情報のみで対応します。"
