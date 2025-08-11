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
from ..base.llm_client import llm_manager


@dataclass
class RoutingDecision:
    """ルーティング判定結果"""
    needs_file_read: bool = False
    needs_file_list: bool = False
    target_files: List[str] = None
    confidence: float = 0.0
    detected_patterns: List[str] = None
    routing_reason: str = ""
    operation_type: str = "chat"  # 追加: デフォルトは'chat'
    
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
        
        # 拡張されたoperation_type定義
        self.operation_types = {
            "information_search": "情報検索・参照",  # ファイル読み取り、調査
            "code_generation": "コード生成・編集",   # ファイル作成、修正
            "analysis_report": "分析・レポート",     # 分析、要約、レポート生成
            "command_execution": "コマンド実行",    # シェルコマンド、テスト実行
            "chat": "対話"                        # 通常の対話
        }
        # 日本語ファイル内容確認キーワード
        self.content_keywords_ja = [
            '内容', '中身', '要約', '概要', '確認', '見て', '開いて', '読んで',
            '把握', 'チェック', '分析', 'レビュー', '調べて', 'コード', 
            'ファイル', '実装', 'シナリオ', '詳細', '情報'
        ]
        
        # 英語ファイル内容確認キーワード  
        self.content_keywords_en = [
            'content', 'contents', 'read', 'show', 'open', 'check', 'review',
            'analyze', 'summary', 'summarize', 'overview', 'examine', 'inspect',
            'code', 'file', 'implementation', 'scenario', 'detail', 'information'
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
            r'[\w\.\-ぁ-ゖァ-ヾ一-龯・]+(?:[\\/][\w\.\-ぁ-ゖァ-ヾ一-龯・]+)+\.[A-Za-z0-9]{1,8}',
            # パターン4: ハイフンを含むファイル名（design-doc.mdなど）
            r'[a-zA-Z][a-zA-Z0-9\-_]*\.[a-zA-Z0-9]{1,8}'
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
            decision.operation_type = "file_list"
        
        # Step 2: ファイル内容要求の検出
        content_detected, content_confidence, target_files = self._detect_file_content_intent(
            user_message, msg_lower, workspace_files
        )
        
        if content_detected:
            decision.needs_file_read = True
            decision.target_files = target_files
            
            # ファイルが明示的に検出されなかった場合、キーワードから推定
            if not target_files:
                rich_ui.print_message(f"[DEBUG] ファイル明示なし、キーワード推定を実行", "info")
                inferred_files = self._infer_files_from_keywords(user_message, workspace_files)
                rich_ui.print_message(f"[DEBUG] キーワード推定結果: {len(inferred_files)}件 - {inferred_files[:3]}", "info")
                if inferred_files:
                    decision.target_files = inferred_files
                    decision.detected_patterns.append("keyword_based_inference")
                    target_files = inferred_files
                else:
                    rich_ui.print_message(f"[DEBUG] キーワード推定でもファイル見つからず", "warning")
            
            decision.confidence = max(decision.confidence, content_confidence)
            decision.detected_patterns.append("file_content_request")
            decision.operation_type = "file_read"
            
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
                f"(信頼度: {decision.confidence:.2f}, needs_file_read: {decision.needs_file_read})", "info"
            )
        
        # Step 4: LLMベースのタスク種別分類
        decision.operation_type = self._classify_task_type_with_llm(user_message, decision)
        
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
        
        rich_ui.print_message(f"[DEBUG] コンテンツキーワード検出: {content_keywords_detected}, マッチ: {keyword_matches}", "info")
        
        if not content_keywords_detected:
            return False, 0.0, []
        
        # Step 2: ファイルパス・ファイル名の検出
        target_files = self._extract_file_paths(user_message)
        
        rich_ui.print_message(f"[DEBUG] 抽出されたファイルパス: {len(target_files)}件 - {target_files}", "info")
        
        # Step 3: ワークスペース内ファイルとの照合
        if workspace_files:
            target_files = self._validate_and_resolve_files(target_files, workspace_files)
            rich_ui.print_message(f"[DEBUG] 検証後のファイル: {len(target_files)}件 - {target_files}", "info")
        
        # Step 4: 信頼度計算
        base_confidence = 0.5 + (len(keyword_matches) * 0.1)
        file_confidence = len(target_files) * 0.2
        total_confidence = min(0.95, base_confidence + file_confidence)
        
        if target_files:
            return True, total_confidence, target_files
        
        # ファイルが検出されなくても、強い内容確認キーワードがあれば部分的に検出
        strong_keywords = ['内容', '中身', 'content', 'contents', 'read', 'show', 'コード', 'code', 'シナリオ', 'scenario', '確認']
        has_strong_keyword = any(kw in msg_lower for kw in strong_keywords)
        
        # より緩い条件でファイル読み取り必要性を判定
        if has_strong_keyword and len(keyword_matches) >= 1:
            return True, 0.8, []  # ファイル指定なしでも高い信頼度
        
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
    
    def _infer_files_from_keywords(self, user_message: str, workspace_files: Optional[List[str]] = None) -> List[str]:
        """キーワードから関連ファイルを推定"""
        if not workspace_files:
            rich_ui.print_message("[DEBUG] ワークスペースファイルがありません", "warning")
            return []
        
        msg_lower = user_message.lower()
        inferred_files = []
        
        rich_ui.print_message(f"[DEBUG] キーワード推定開始: '{user_message}' (ワークスペース: {len(workspace_files)}ファイル)", "info")
        
        # キーワードマッピング
        keyword_mappings = {
            'prompt': ['prompt', 'プロンプト'],
            'orchestr': ['orchestr', 'オーケストレ'], 
            'four_node': ['four_node', '4node', '4ノード'],
            'config': ['config', '設定'],
            'test': ['test', 'テスト'],
            'ui': ['ui', 'rich_ui', 'interface'],
            'state': ['state', 'agent_state'],
            'tool': ['tool', 'ツール'],
            'rag': ['rag', 'search', '検索'],
            'scenario': ['scenario', 'シナリオ'],
            'code': ['code', 'コード'],
        }
        
        # マッチしたキーワードを収集
        matched_keywords = []
        for category, keywords in keyword_mappings.items():
            if any(kw in msg_lower for kw in keywords):
                matched_keywords.append(category)
        
        rich_ui.print_message(f"[DEBUG] マッチしたキーワードカテゴリ: {matched_keywords}", "info")
        
        # キーワードに基づいてファイルをフィルタリング
        for keyword in matched_keywords:
            pattern = keyword.lower()
            matches_for_keyword = []
            for file_path in workspace_files:
                file_lower = file_path.lower()
                if pattern in file_lower and file_path not in inferred_files:
                    inferred_files.append(file_path)
                    matches_for_keyword.append(file_path)
            rich_ui.print_message(f"[DEBUG] '{keyword}'パターンで{len(matches_for_keyword)}件マッチ", "info")
        
        # 最大5ファイルに制限し、重要度順にソート
        priority_patterns = ['test', 'config', 'prompt']
        sorted_files = []
        
        # 優先度の高いファイルから追加
        for priority in priority_patterns:
            for file_path in inferred_files:
                if priority in file_path.lower() and file_path not in sorted_files:
                    sorted_files.append(file_path)
        
        # 残りのファイルを追加
        for file_path in inferred_files:
            if file_path not in sorted_files:
                sorted_files.append(file_path)
        
        rich_ui.print_message(f"[DEBUG] 最終推定結果: {len(sorted_files[:5])}件 - {sorted_files[:5]}", "info")
        
        return sorted_files[:5]
    
    def _classify_task_type_with_llm(self, user_message: str, decision: RoutingDecision) -> str:
        """
        LLMベースのタスク種別分類
        
        Args:
            user_message: ユーザーのメッセージ
            decision: 現在の判定結果
            
        Returns:
            分類されたタスク種別
        """
        try:
            # 既にファイル操作が特定されている場合の優先判定
            if decision.needs_file_read or decision.needs_file_list:
                # ファイル読み取り要求がある場合でも、目的に応じてより詳細に分類
                if any(keyword in user_message.lower() for keyword in 
                       ['作成', 'create', '生成', 'generate', '編集', 'edit', '修正', 'fix']):
                    return "code_generation"
                elif any(keyword in user_message.lower() for keyword in 
                         ['分析', 'analyze', '要約', 'summary', 'レポート', 'report']):
                    return "analysis_report"
                else:
                    return "information_search"
            
            # LLMによる分類プロンプト
            classification_prompt = self._build_task_classification_prompt(user_message)
            
            # 高速LLMで分類実行
            llm_response = llm_manager.get_default_client().chat(
                classification_prompt,
                system_prompt=self._get_task_classification_system_prompt(),
                max_tokens=100
            )
            
            # レスポンスから operation_type を抽出
            return self._parse_task_classification(llm_response)
            
        except Exception as e:
            rich_ui.print_warning(f"タスク分類で問題発生: {e}")
            return "chat"  # フォールバック
    
    def _build_task_classification_prompt(self, user_message: str) -> str:
        """タスク分類用プロンプトの構築"""
        return f"""
以下のユーザー要求を分析し、最も適切なタスク種別を1つ選択してください。

**ユーザー要求:**
{user_message}

**選択肢:**
1. information_search - 情報検索・参照（ファイル読み取り、調査、確認）
2. code_generation - コード生成・編集（ファイル作成、修正、実装）  
3. analysis_report - 分析・レポート（分析、要約、レポート生成）
4. command_execution - コマンド実行（テスト実行、ビルド、デプロイ）
5. chat - 対話（質問回答、説明、議論）

**回答形式:** 選択肢の番号のみ回答してください（例: 1）
"""
    
    def _get_task_classification_system_prompt(self) -> str:
        """タスク分類用システムプロンプト"""
        return """あなたはタスク分類の専門家です。
ユーザーの要求を正確に理解し、最も適切なタスク種別を判定してください。

判定基準:
- 明確に作成・編集を求めている → code_generation
- 実行・テスト・デプロイを求めている → command_execution  
- 分析・要約・レポートを求めている → analysis_report
- 情報参照・調査を求めている → information_search
- 上記に当てはまらない → chat

簡潔に番号のみで回答してください。"""
    
    def _parse_task_classification(self, llm_response: str) -> str:
        """LLMレスポンスからタスク種別を抽出"""
        response_clean = llm_response.strip()
        
        # 数字を抽出
        import re
        numbers = re.findall(r'\d+', response_clean)
        
        if numbers:
            choice = int(numbers[0])
            type_mapping = {
                1: "information_search",
                2: "code_generation", 
                3: "analysis_report",
                4: "command_execution",
                5: "chat"
            }
            return type_mapping.get(choice, "chat")
        
        # キーワードベースのフォールバック
        response_lower = response_clean.lower()
        if any(keyword in response_lower for keyword in ['information', 'search', '情報', '検索']):
            return "information_search"
        elif any(keyword in response_lower for keyword in ['code', 'generation', 'コード', '生成']):
            return "code_generation"
        elif any(keyword in response_lower for keyword in ['analysis', 'report', '分析', 'レポート']):
            return "analysis_report"
        elif any(keyword in response_lower for keyword in ['command', 'execution', 'コマンド', '実行']):
            return "command_execution"
        else:
            return "chat"
    
    def generate_deferral_message(self, decision: RoutingDecision) -> str:
        """응답 연기 시 표시할 메시지 생성"""
        if decision.target_files:
            file_list = ", ".join(decision.target_files[:3])
            if len(decision.target_files) > 3:
                file_list += f" 등 {len(decision.target_files)}개 파일"
            return f"파일 내용을 확인 중입니다: {file_list}"
        else:
            return "관련 파일 내용을 수집 중입니다..."