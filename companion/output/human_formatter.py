#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HumanOutputFormatter - 構造化データを人間が読みやすい文章に変換

設計思想:
- 構造化データ（辞書・JSON）をLLMで自然な日本語文章に変換
- データの正確性を保ちつつ、読みやすさを向上
- プロキシシステムの複雑性を排除
"""

import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime

@dataclass
class FormatterRequest:
    """フォーマット要求"""
    data: Dict[str, Any]
    context: str
    format_type: str  # 'file_analysis', 'search_result', 'operation_result'
    user_intent: Optional[str] = None

@dataclass
class FormattedOutput:
    """フォーマット済み出力"""
    human_text: str
    summary: str
    details: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None

class HumanOutputFormatter:
    """構造化データを人間が読みやすい文章に変換するフォーマッター"""
    
    def __init__(self, llm_service=None):
        """初期化
        
        Args:
            llm_service: LLMサービス（後で注入される予定）
        """
        self.logger = logging.getLogger(__name__)
        self.llm_service = llm_service
        
        # フォーマットテンプレート
        self.templates = {
            'file_analysis': self._get_file_analysis_template(),
            'search_result': self._get_search_result_template(), 
            'operation_result': self._get_operation_result_template(),
            'generic': self._get_generic_template()
        }
    
    async def format_data(self, request: FormatterRequest) -> FormattedOutput:
        """メインのフォーマット処理
        
        Args:
            request: フォーマット要求
            
        Returns:
            FormattedOutput: フォーマット済み出力
        """
        try:
            self.logger.info(f"フォーマット開始: type={request.format_type}, data_size={len(str(request.data))}")
            
            # テンプレート選択
            template = self.templates.get(request.format_type, self.templates['generic'])
            
            # LLMサービスが利用可能な場合はLLMでフォーマット
            if self.llm_service:
                return await self._format_with_llm(request, template)
            else:
                # フォールバック: テンプレートベースフォーマット
                return self._format_with_template(request, template)
                
        except Exception as e:
            self.logger.error(f"フォーマットエラー: {e}")
            return FormattedOutput(
                human_text=f"データの処理中にエラーが発生しました: {str(e)}",
                summary="エラー",
                success=False,
                error_message=str(e)
            )
    
    async def _format_with_llm(self, request: FormatterRequest, template: str) -> FormattedOutput:
        """LLMを使用したフォーマット"""
        try:
            # データを安全な形式に変換
            safe_data = self._prepare_data_for_llm(request.data)
            
            # プロンプト構築
            prompt = template.format(
                data=json.dumps(safe_data, ensure_ascii=False, indent=2),
                context=request.context,
                user_intent=request.user_intent or "情報の理解"
            )
            
            # LLM呼び出し（利用可能なメソッドを使用）
            if hasattr(self.llm_service, 'generate_text'):
                response = await self.llm_service.generate_text(prompt)
            else:
                # LLMServiceが利用できない場合はテンプレートベースにフォールバック
                return self._format_with_template(request, template)
            
            # レスポンス解析
            return self._parse_llm_response(response)
            
        except Exception as e:
            self.logger.error(f"LLMフォーマットエラー: {e}")
            # フォールバックへ
            return self._format_with_template(request, template)
    
    def _format_with_template(self, request: FormatterRequest, template: str) -> FormattedOutput:
        """テンプレートベースフォーマット（フォールバック）"""
        try:
            data = request.data
            
            if request.format_type == 'file_analysis':
                return self._format_file_analysis_simple(data)
            elif request.format_type == 'search_result':
                return self._format_search_result_simple(data)
            elif request.format_type == 'operation_result':
                return self._format_operation_result_simple(data)
            elif request.format_type == 'plan_generation':
                return self._format_plan_generation_simple(data)
            else:
                return self._format_generic_simple(data)
                
        except Exception as e:
            self.logger.error(f"テンプレートフォーマットエラー: {e}")
            return FormattedOutput(
                human_text=str(data),
                summary="生データ",
                success=False,
                error_message=str(e)
            )
    
    def _format_file_analysis_simple(self, data: Dict[str, Any]) -> FormattedOutput:
        """ファイル分析結果の簡易フォーマット"""
        file_path = data.get('file_path', '不明')
        file_info = data.get('file_info', {})
        headers = data.get('headers', [])
        sections = data.get('sections', [])
        
        lines = []
        lines.append(f"📄 ファイル分析結果: {file_path}")
        
        if file_info:
            lines.append(f"   • 総行数: {file_info.get('total_lines', 0)}行")
            lines.append(f"   • 文字数: {file_info.get('total_chars', 0)}文字")
        
        if headers:
            lines.append(f"   • ヘッダー: {len(headers)}個")
            # 主要なヘッダーを表示
            for header in headers[:3]:
                level_marker = "  " * (header.get('level', 1) - 1)
                lines.append(f"     {level_marker}• {header.get('text', '')}")
        
        if sections:
            lines.append(f"   • セクション: {len(sections)}個")
        
        human_text = "\n".join(lines)
        summary = f"ファイル {file_path} を分析しました"
        
        return FormattedOutput(
            human_text=human_text,
            summary=summary,
            success=True
        )
    
    def _format_search_result_simple(self, data: Dict[str, Any]) -> FormattedOutput:
        """検索結果の簡易フォーマット"""
        pattern = data.get('pattern', '')
        file_path = data.get('file_path', '')
        matches_found = data.get('matches_found', 0)
        results = data.get('results', [])
        
        lines = []
        lines.append(f"🔍 検索結果: '{pattern}' in {file_path}")
        lines.append(f"   • マッチ数: {matches_found}件")
        
        if results:
            lines.append(f"   • 検索結果:")
            for i, result in enumerate(results[:3]):
                line_num = result.get('line_number', 0)
                match_text = result.get('match_text', '').strip()
                full_line = result.get('full_line', '').strip()
                # match_textが空の場合はfull_lineを使用
                display_text = match_text if match_text else full_line[:100]
                lines.append(f"     {i+1}. L{line_num}: {display_text}")
        
        human_text = "\n".join(lines)
        summary = f"'{pattern}'で{matches_found}件見つかりました"
        
        return FormattedOutput(
            human_text=human_text,
            summary=summary,
            success=True
        )
    
    def _format_operation_result_simple(self, data: Dict[str, Any]) -> FormattedOutput:
        """操作結果の簡易フォーマット"""
        success = data.get('success', False)
        message = data.get('message', '')
        path = data.get('path', '')
        
        if success:
            human_text = f"✅ 操作完了: {message}"
            if path:
                human_text += f"\n   📁 対象: {path}"
            summary = "操作成功"
        else:
            human_text = f"❌ 操作失敗: {message}"
            summary = "操作失敗"
        
        return FormattedOutput(
            human_text=human_text,
            summary=summary,
            success=success
        )
    
    def _format_generic_simple(self, data: Dict[str, Any]) -> FormattedOutput:
        """汎用の簡易フォーマット"""
        # 辞書の主要な情報を抽出
        lines = []
        lines.append("📋 データ概要:")
        
        for key, value in list(data.items())[:5]:  # 最大5項目まで
            if isinstance(value, (str, int, float, bool)):
                lines.append(f"   • {key}: {value}")
            elif isinstance(value, list):
                lines.append(f"   • {key}: {len(value)}項目")
            elif isinstance(value, dict):
                lines.append(f"   • {key}: {len(value)}要素")
        
        human_text = "\n".join(lines)
        summary = "データを整理しました"
        
        return FormattedOutput(
            human_text=human_text,
            summary=summary,
            success=True
        )
    
    def _format_plan_generation_simple(self, data: Dict[str, Any]) -> FormattedOutput:
        """実装プラン生成結果の簡易フォーマット"""
        operation = data.get('operation', '不明な操作')
        success = data.get('success', False)
        generated_plan = data.get('generated_plan', '')
        base_document = data.get('base_document', '')
        focus_areas = data.get('focus_areas', [])
        
        lines = []
        
        if success:
            lines.append(f"📋 {operation}完了: {base_document}")
            if focus_areas:
                lines.append(f"   • 重点領域: {', '.join(focus_areas)}")
            lines.append("")
            
            # 生成されたプランを表示
            if generated_plan:
                lines.append("🎯 生成されたプラン:")
                lines.append("")
                
                # プランを適切に表示（長すぎる場合は要約）
                plan_lines = generated_plan.split('\n')
                for line in plan_lines:
                    if line.strip():
                        # ヘッダー行はそのまま表示
                        if line.strip().startswith('#'):
                            lines.append(line)
                        # その他の行は適切にインデント
                        else:
                            lines.append(f"   {line}")
                        
                        # 行数制限（長すぎる場合）
                        if len(lines) > 50:
                            lines.append("   ... (省略)")
                            break
            else:
                lines.append("⚠️ プラン内容が生成されませんでした")
            
            summary = f"実装プランを生成しました（{len(plan_lines) if generated_plan else 0}行）"
            
        else:
            error_message = data.get('error_message', '不明なエラー')
            lines.append(f"❌ {operation}失敗")
            lines.append(f"   エラー: {error_message}")
            summary = "プラン生成に失敗"
        
        human_text = "\n".join(lines)
        
        return FormattedOutput(
            human_text=human_text,
            summary=summary,
            success=success
        )
    
    def _prepare_data_for_llm(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """LLM用にデータを安全な形式に変換"""
        # 大きすぎるデータや複雑すぎるデータを簡略化
        safe_data = {}
        
        for key, value in data.items():
            if isinstance(value, str) and len(value) > 500:
                safe_data[key] = value[:500] + "..."
            elif isinstance(value, list) and len(value) > 10:
                safe_data[key] = value[:10]
            elif isinstance(value, dict) and len(value) > 20:
                safe_data[key] = dict(list(value.items())[:20])
            else:
                safe_data[key] = value
        
        return safe_data
    
    def _parse_llm_response(self, response: str) -> FormattedOutput:
        """LLMレスポンスを解析"""
        # シンプルな解析 - 改行で要約と詳細を分離
        lines = response.strip().split('\n')
        
        if len(lines) >= 2:
            summary = lines[0]
            human_text = '\n'.join(lines[1:])
        else:
            summary = "LLM応答"
            human_text = response
        
        return FormattedOutput(
            human_text=human_text,
            summary=summary,
            success=True
        )
    
    def _get_file_analysis_template(self) -> str:
        """ファイル分析用プロンプトテンプレート"""
        return """
以下のファイル分析データを、ユーザーが理解しやすい自然な日本語で要約してください。

分析データ:
{data}

コンテキスト: {context}
ユーザーの意図: {user_intent}

要求:
1. 最初の行に簡潔な要約を書いてください
2. 2行目以降に詳細な説明を書いてください
3. ファイルの構造、内容、特徴を分かりやすく説明してください
4. 技術的な詳細は避け、ユーザーが知りたい情報に焦点を当ててください
"""
    
    def _get_search_result_template(self) -> str:
        """検索結果用プロンプトテンプレート"""
        return """
以下の検索結果データを、ユーザーが理解しやすい自然な日本語で要約してください。

検索データ:
{data}

コンテキスト: {context}
ユーザーの意図: {user_intent}

要求:
1. 最初の行に簡潔な要約を書いてください
2. 2行目以降に詳細な説明を書いてください
3. 検索結果の重要なポイントを強調してください
4. 見つかった内容の意味や関連性を説明してください
"""
    
    def _get_operation_result_template(self) -> str:
        """操作結果用プロンプトテンプレート"""
        return """
以下の操作結果データを、ユーザーが理解しやすい自然な日本語で要約してください。

操作データ:
{data}

コンテキスト: {context}
ユーザーの意図: {user_intent}

要求:
1. 最初の行に簡潔な要約を書いてください
2. 2行目以降に詳細な説明を書いてください
3. 操作の成功/失敗、影響範囲を明確に示してください
4. 次に取るべきアクションがあれば提案してください
"""
    
    def _get_generic_template(self) -> str:
        """汎用プロンプトテンプレート"""
        return """
以下のデータを、ユーザーが理解しやすい自然な日本語で要約してください。

データ:
{data}

コンテキスト: {context}
ユーザーの意図: {user_intent}

要求:
1. 最初の行に簡潔な要約を書いてください
2. 2行目以降に詳細な説明を書いてください
3. データの重要なポイントを分かりやすく説明してください
4. 技術的な詳細は避け、ユーザーが知りたい情報に焦点を当ててください
"""