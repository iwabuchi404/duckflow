"""
Integration Bridge for LLM-based Intent Understanding

既存のキーワードマッチングシステムと新しいLLMベース意図理解システムを統合
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from .intent_understanding.intent_integration import IntentUnderstandingSystem
from .improved_mock_llm import improved_mock_llm_client


@dataclass
class IntegratedIntentResult:
    """統合意図理解結果"""
    needs_file_read: bool = False
    operation_type: str = "chat"
    target_files: List[str] = None
    confidence: float = 0.0
    routing_reason: str = ""
    detected_patterns: List[str] = None
    
    # 新しいLLMベースシステムの結果
    llm_intent_analysis: Optional[Any] = None
    task_profile: Optional[Any] = None
    task_decomposition: Optional[Any] = None
    overall_confidence: float = 0.0
    
    def __post_init__(self):
        if self.target_files is None:
            self.target_files = []
        if self.detected_patterns is None:
            self.detected_patterns = []


class IntentUnderstandingBridge:
    """意図理解システム統合ブリッジ"""
    
    def __init__(self, use_llm: bool = True, fallback_to_keywords: bool = True):
        """ブリッジを初期化"""
        self.use_llm = use_llm
        self.fallback_to_keywords = fallback_to_keywords
        self.logger = logging.getLogger(__name__)
        
        # LLMベースシステムの初期化
        if self.use_llm:
            try:
                self.llm_system = IntentUnderstandingSystem(improved_mock_llm_client)
                self.logger.info("LLMベース意図理解システムを初期化しました")
            except Exception as e:
                self.logger.error(f"LLMシステム初期化エラー: {e}")
                self.use_llm = False
        
        # キーワードベースシステム（フォールバック用）
        self.keyword_system = KeywordBasedIntentAnalyzer()
    
    async def analyze_user_intent(
        self, 
        user_message: str, 
        workspace_files: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> IntegratedIntentResult:
        """
        統合意図理解の実行
        
        Args:
            user_message: ユーザーのメッセージ
            workspace_files: ワークスペースファイル一覧
            context: 追加コンテキスト
            
        Returns:
            統合意図理解結果
        """
        try:
            # Phase 1: LLMベース意図理解（優先）
            if self.use_llm:
                try:
                    llm_result = await self.llm_system.understand_intent(user_message, context)
                    return self._convert_llm_result_to_integrated(llm_result, user_message, workspace_files)
                except Exception as e:
                    self.logger.warning(f"LLM意図理解エラー: {e}")
                    if not self.fallback_to_keywords:
                        raise
            
            # Phase 2: キーワードベースフォールバック
            if self.fallback_to_keywords:
                keyword_result = self.keyword_system.analyze_intent(user_message, workspace_files)
                return self._convert_keyword_result_to_integrated(keyword_result, user_message)
            
            # デフォルト結果
            return IntegratedIntentResult(
                needs_file_read=False,
                operation_type="chat",
                confidence=0.0,
                routing_reason="意図理解に失敗"
            )
            
        except Exception as e:
            self.logger.error(f"統合意図理解エラー: {e}")
            return IntegratedIntentResult(
                needs_file_read=False,
                operation_type="chat",
                confidence=0.0,
                routing_reason=f"エラー: {str(e)}"
            )
    
    def _convert_llm_result_to_integrated(
        self, 
        llm_result: Any, 
        user_message: str, 
        workspace_files: Optional[List[str]]
    ) -> IntegratedIntentResult:
        """LLM結果を統合結果に変換"""
        
        # TaskProfileに基づく操作タイプの決定
        operation_type = self._determine_operation_type_from_profile(llm_result.task_profile.profile_type.value)
        
        # ファイル読み取りの必要性判定
        needs_file_read = self._determine_file_read_needs(llm_result, user_message, workspace_files)
        
        # 対象ファイルの特定
        target_files = self._extract_target_files(llm_result, user_message, workspace_files)
        
        return IntegratedIntentResult(
            needs_file_read=needs_file_read,
            operation_type=operation_type,
            target_files=target_files,
            confidence=llm_result.overall_confidence,
            routing_reason=f"LLM分析: {llm_result.task_profile.profile_type.value}",
            detected_patterns=[llm_result.task_profile.profile_type.value],
            llm_intent_analysis=llm_result.intent_analysis,
            task_profile=llm_result.task_profile,
            task_decomposition=llm_result.task_decomposition,
            overall_confidence=llm_result.overall_confidence
        )
    
    def _determine_operation_type_from_profile(self, profile_type: str) -> str:
        """TaskProfileから操作タイプを決定"""
        profile_to_operation = {
            "information_request": "information_search",
            "analysis_request": "analysis_report",
            "creation_request": "code_generation",
            "modification_request": "code_generation",
            "search_request": "information_search",
            "guidance_request": "chat"
        }
        return profile_to_operation.get(profile_type, "chat")
    
    def _determine_file_read_needs(self, llm_result: Any, user_message: str, workspace_files: Optional[List[str]]) -> bool:
        """ファイル読み取りの必要性を判定"""
        # 分析・情報要求の場合はファイル読み取りが必要
        if llm_result.task_profile.profile_type.value in ["information_request", "analysis_request"]:
            return True
        
        # 修正要求の場合も対象ファイルの読み取りが必要
        if llm_result.task_profile.profile_type.value == "modification_request":
            return True
        
        # 検索要求の場合もファイル読み取りが必要
        if llm_result.task_profile.profile_type.value == "search_request":
            return True
        
        return False
    
    def _extract_target_files(self, llm_result: Any, user_message: str, workspace_files: Optional[List[str]]) -> List[str]:
        """対象ファイルを抽出"""
        target_files = []
        
        # LLM分析結果から検出された対象を取得
        if hasattr(llm_result.intent_analysis, 'detected_targets'):
            target_files.extend(llm_result.intent_analysis.detected_targets)
        
        # TaskProfile結果から検出された対象を取得
        if hasattr(llm_result.task_profile, 'detected_targets'):
            target_files.extend(llm_result.task_profile.detected_targets)
        
        # ユーザーメッセージからファイル名を抽出（簡易版）
        import re
        file_patterns = [
            r'[\w\-\./\\ぁ-ゖァ-ヾ一-龯・]+?\.[A-Za-z0-9]{1,8}',
            r'[A-Za-z]:\\[^\n\r]+?\.[A-Za-z0-9]{1,8}'
        ]
        
        for pattern in file_patterns:
            matches = re.findall(pattern, user_message)
            target_files.extend(matches)
        
        # 重複を除去
        target_files = list(set(target_files))
        
        # ワークスペース内のファイルかチェック
        if workspace_files:
            validated_files = [f for f in target_files if f in workspace_files]
            if validated_files:
                return validated_files
        
        return target_files
    
    def _convert_keyword_result_to_integrated(self, keyword_result: Any, user_message: str) -> IntegratedIntentResult:
        """キーワード結果を統合結果に変換"""
        # キーワードベースシステムの結果を統合結果形式に変換
        return IntegratedIntentResult(
            needs_file_read=keyword_result.get("needs_file_read", False),
            operation_type=keyword_result.get("operation_type", "chat"),
            target_files=keyword_result.get("target_files", []),
            confidence=keyword_result.get("confidence", 0.5),
            routing_reason="キーワードベース分析（フォールバック）",
            detected_patterns=["keyword_fallback"]
        )


class KeywordBasedIntentAnalyzer:
    """キーワードベース意図分析器（フォールバック用）"""
    
    def __init__(self):
        """初期化"""
        # 基本的なキーワードパターン
        self.content_keywords = [
            '内容', '中身', '要約', '概要', '確認', '見て', '開いて', '読んで',
            '把握', 'チェック', '分析', 'レビュー', '調べて', 'コード', 
            'ファイル', '実装', 'シナリオ', '詳細', '情報'
        ]
        
        self.creation_keywords = [
            '作成', '作って', '実装', '書いて', '構築', '新規', '追加',
            'create', 'implement', 'write', 'build', 'new', 'add'
        ]
    
    def analyze_intent(self, user_message: str, workspace_files: Optional[List[str]] = None) -> Dict[str, Any]:
        """キーワードベース意図分析"""
        msg_lower = user_message.lower()
        
        # ファイル内容確認の検出
        if any(kw in msg_lower for kw in self.content_keywords):
            return {
                "needs_file_read": True,
                "operation_type": "information_search",
                "target_files": [],
                "confidence": 0.7,
                "routing_reason": "キーワードベース: ファイル内容確認要求"
            }
        
        # 作成要求の検出
        if any(kw in msg_lower for kw in self.creation_keywords):
            return {
                "needs_file_read": False,
                "operation_type": "code_generation",
                "target_files": [],
                "confidence": 0.7,
                "routing_reason": "キーワードベース: 作成要求"
            }
        
        # デフォルト
        return {
            "needs_file_read": False,
            "operation_type": "chat",
            "target_files": [],
            "confidence": 0.5,
            "routing_reason": "キーワードベース: 対話要求"
        }


# グローバルインスタンス
intent_bridge = IntentUnderstandingBridge(use_llm=True, fallback_to_keywords=True)
