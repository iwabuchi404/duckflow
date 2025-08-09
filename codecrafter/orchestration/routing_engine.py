"""
RoutingEngine - ユーザー発話ドリブンの決定論的ルーティングシステム
ステップ2e: 推測回答の完全防止、確実な処理分岐の実現
"""
import re
import os
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass
from pathlib import Path

from ..ui.rich_ui import rich_ui


@dataclass
class RoutingDecision:
    """ルーティング判定結果"""
    needs_file_read: bool = False
    needs_file_list: bool = False
    target_files: List[str] = None
    confidence: float = 0.0
    detected_patterns: List[str] = None
    routing_reason: str = ""
    
    def __post_init__(self):
        if self.target_files is None:
            self.target_files = []
        if self.detected_patterns is None:
            self.detected_patterns = []


@dataclass
class FileContentRequest:
    """ファイル内容要求の詳細"""
    intent_type: str  # 'content_check', 'summary', 'analysis', 'list'
    target_files: List[str]
    is_mandatory: bool  # 強制実行フラグ
    priority: int = 1  # 1=高, 2=中, 3=低


class RoutingEngine:
    """決定論的ルーティングエンジン"""
    
    def __init__(self):
        """ルーティングエンジンを初期化"""
        # 日本語ファイル内容確認キーワード
        self.content_keywords_ja = [
            '内容', '中身', '要約', '概要', '確認', '見て', '開いて', '読んで',
            '把握', 'チェック', '分析', 'レビュー', '調べて'
        ]
        
        # 英語ファイル内容確認キーワード  
        self.content_keywords_en = [
            'content', 'contents', 'read', 'show', 'open', 'check', 'review',
            'analyze', 'summary', 'summarize', 'overview', 'examine', 'inspect'
        ]
        
        # ファイル一覧要求キーワード
        self.list_keywords_ja = [
            'ファイル一覧', 'ファイルリスト', 'ファイル構造', 'ファイルを見',
            'リスト', '一覧', '構造', 'ディレクトリ'
        ]
        
        self.list_keywords_en = [
            'list files', 'file list', 'ls', 'dir', 'files', 'directory',
            'structure', 'file structure'
        ]
        
        # 日本語ファイル名対応の正規表現パターン
        self.file_patterns = [
            # パターン1: 日本語対応（ドライブレター / 相対パス含む）
            r'[A-Za-z]:\\[^\n\r]+?\.[A-Za-z0-9]{1,8}',
            r'[\w\-\./\\ぁ-ゖァ-ヾ一-龯・]+?\.[A-Za-z0-9]{1,8}',
            # パターン2: 日本語対応 区切りを含む相対/絶対パス
            r'(?:[A-Za-z]:)?(?:[\\/][^\s\n\r]+)+?\.[A-Za-z0-9]{1,8}',
            # パターン3: 日本語対応 ディレクトリ名+ファイル名形式（区切り必須）
            r'[\w\.\-ぁ-ゖァ-ヾ一-龯・]+(?:[\\/][\w\.\-ぁ-ゖァ-ヾ一-龯・]+)+\.[A-Za-z0-9]{1,8}'
        ]
    
    def analyze_user_intent(self, user_message: str, workspace_files: Optional[List[str]] = None) -> RoutingDecision:
        """
        ユーザー発話から意図を分析してルーティング判定
        
        Args:
            user_message: ユーザーのメッセージ
            workspace_files: ワークスペース内のファイル一覧（存在チェック用）
            
        Returns:
            ルーティング判定結果
        """
        if not user_message or not user_message.strip():
            return RoutingDecision()
        
        decision = RoutingDecision()
        msg_lower = user_message.lower()
        
        # Step 1: ファイル一覧要求の検出
        list_detected, list_confidence = self._detect_file_list_intent(msg_lower)
        if list_detected:
            decision.needs_file_list = True
            decision.confidence = list_confidence
            decision.detected_patterns.append("file_list_request")
            decision.routing_reason = "ファイル一覧要求を検出"
        
        # Step 2: ファイル内容要求の検出
        content_detected, content_confidence, target_files = self._detect_file_content_intent(
            user_message, msg_lower, workspace_files
        )
        
        if content_detected:
            decision.needs_file_read = True
            decision.target_files = target_files
            decision.confidence = max(decision.confidence, content_confidence)
            decision.detected_patterns.append("file_content_request")
            
            if decision.routing_reason:
                decision.routing_reason += " + ファイル内容確認要求"
            else:
                decision.routing_reason = f"ファイル内容確認要求 ({len(target_files)}件)"
        
        # Step 3: 決定論化 - 該当パターンがある場合は強制的に処理
        if decision.needs_file_read or decision.needs_file_list:
            decision.confidence = max(decision.confidence, 0.9)  # 強制的に高信頼度に
            
            # デバッグ出力
            rich_ui.print_message(
                f"[ROUTING] 決定論的ルーティング: {decision.routing_reason} "
                f"(信頼度: {decision.confidence:.2f})", "info"
            )
        
        return decision
    
    def _detect_file_list_intent(self, msg_lower: str) -> Tuple[bool, float]:
        """ファイル一覧要求の検出"""
        # 日本語キーワード検出
        ja_matches = [kw for kw in self.list_keywords_ja if kw in msg_lower]
        
        # 英語キーワード検出
        en_matches = [kw for kw in self.list_keywords_en if kw in msg_lower]
        
        total_matches = len(ja_matches) + len(en_matches)
        
        if total_matches > 0:
            confidence = min(0.9, 0.6 + (total_matches * 0.1))
            return True, confidence
        
        return False, 0.0
    
    def _detect_file_content_intent(
        self, 
        user_message: str, 
        msg_lower: str, 
        workspace_files: Optional[List[str]] = None
    ) -> Tuple[bool, float, List[str]]:
        """ファイル内容確認要求の検出"""
        
        # Step 1: 内容確認キーワードの検出
        content_keywords_detected = False
        keyword_matches = []
        
        # 日本語キーワード検出
        for kw in self.content_keywords_ja:
            if kw in msg_lower:
                keyword_matches.append(kw)
                content_keywords_detected = True
        
        # 英語キーワード検出
        for kw in self.content_keywords_en:
            if kw in msg_lower:
                keyword_matches.append(kw)
                content_keywords_detected = True
        
        if not content_keywords_detected:
            return False, 0.0, []
        
        # Step 2: ファイルパス・ファイル名の検出
        target_files = self._extract_file_paths(user_message)
        
        # Step 3: ワークスペース内ファイルとの照合
        if workspace_files:
            target_files = self._validate_and_resolve_files(target_files, workspace_files)
        
        # Step 4: 信頼度計算
        base_confidence = 0.5 + (len(keyword_matches) * 0.1)
        file_confidence = len(target_files) * 0.2
        total_confidence = min(0.95, base_confidence + file_confidence)
        
        if target_files:
            return True, total_confidence, target_files
        
        # ファイルが検出されなくても、強い内容確認キーワードがあれば部分的に検出
        strong_keywords = ['内容', '中身', 'content', 'contents', 'read', 'show']
        has_strong_keyword = any(kw in msg_lower for kw in strong_keywords)
        
        if has_strong_keyword and len(keyword_matches) >= 2:
            return True, 0.7, []  # ファイル指定なしでも高い信頼度
        
        return False, 0.0, []
    
    def _extract_file_paths(self, text: str) -> List[str]:
        """テキストからファイルパスを抽出（日本語対応）"""
        candidates = []
        
        # 各パターンでファイルパスを検索
        for pattern in self.file_patterns:
            matches = re.findall(pattern, text)
            candidates.extend(matches)
        
        # 正規化（末尾の句読点や括弧を除去、日本語対応）
        normalized = []
        for candidate in candidates:
            cleaned = candidate.strip().rstrip('。、.）)』】」》〉】〕]')
            # バックスラッシュを正規化（Windows環境対応）
            cleaned = cleaned.replace('\\', '/')
            if cleaned and len(cleaned) > 2:  # 最小長チェック
                normalized.append(cleaned)
        
        # 重複排除しつつ順序維持
        seen = set()
        unique_files = []
        for path in normalized:
            if path not in seen:
                seen.add(path)
                unique_files.append(path)
        
        return unique_files[:5]  # 최대 5개로 제한
    
    def _validate_and_resolve_files(self, candidates: List[str], workspace_files: List[str]) -> List[str]:
        """候補ファイルをワークスペース内ファイルと照合・解決"""
        if not candidates or not workspace_files:
            return candidates
        
        validated_files = []
        workspace_set = set(workspace_files)
        
        for candidate in candidates:
            # 정확히 일치하는 파일
            if candidate in workspace_set:
                validated_files.append(candidate)
                continue
            
            # 부분 일치 검색 (파일명만 또는 경로 일부)
            candidate_name = os.path.basename(candidate)
            for ws_file in workspace_files:
                if candidate_name == os.path.basename(ws_file):
                    validated_files.append(ws_file)
                    break
                elif candidate in ws_file or ws_file.endswith(candidate):
                    validated_files.append(ws_file)
                    break
        
        # 검증되지 않은 파일도 포함 (존재하지 않는 파일에 대한 명시적 처리 위해)
        for candidate in candidates:
            if candidate not in validated_files:
                validated_files.append(candidate)
        
        return list(dict.fromkeys(validated_files))  # 순서 유지하면서 중복 제거
    
    def create_file_content_request(
        self, 
        decision: RoutingDecision,
        priority: int = 1
    ) -> Optional[FileContentRequest]:
        """ルーティング判定からファイル内容要求を生성"""
        if not decision.needs_file_read:
            return None
        
        # 의도 타입 결정
        intent_type = "content_check"
        if any("요약" in pattern or "summary" in pattern for pattern in decision.detected_patterns):
            intent_type = "summary"
        elif any("분석" in pattern or "analysis" in pattern for pattern in decision.detected_patterns):
            intent_type = "analysis"
        
        return FileContentRequest(
            intent_type=intent_type,
            target_files=decision.target_files,
            is_mandatory=decision.confidence >= 0.8,  # 높은 신뢰도일 때 강제
            priority=priority
        )
    
    def should_defer_response(
        self, 
        decision: RoutingDecision, 
        available_file_contents: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        응답을 연기해야 하는지 판정 (파일 내용이 아직 수집되지 않은 경우)
        
        Args:
            decision: 라우팅 판정 결과
            available_file_contents: 현재 사용 가능한 파일 내용
            
        Returns:
            응답 연기 여부
        """
        if not decision.needs_file_read:
            return False
        
        if not decision.target_files:
            return False
        
        if not available_file_contents:
            return True  # 파일 내용이 전혀 없으면 연기
        
        # 대상 파일 중 하나라도 사용 가능하면 진행 가능
        for target_file in decision.target_files:
            if target_file in available_file_contents:
                return False
        
        return True  # 대상 파일이 하나도 사용 가능하지 않으면 연기
    
    def generate_deferral_message(self, decision: RoutingDecision) -> str:
        """응답 연기 시 표시할 메시지 생성"""
        if decision.target_files:
            file_list = ", ".join(decision.target_files[:3])
            if len(decision.target_files) > 3:
                file_list += f" 등 {len(decision.target_files)}개 파일"
            return f"파일 내용을 확인 중입니다: {file_list}"
        else:
            return "관련 파일 내용을 수집 중입니다..."