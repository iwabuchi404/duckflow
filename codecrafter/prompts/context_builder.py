"""
PromptContextBuilder - AgentStateからPromptContextを安全に構築
機微情報のマスク、トークン予算管理、安全性チェックを実行
"""
import os
from datetime import datetime
from typing import Dict, List, Optional, Any, Set
from pathlib import Path

from .prompt_context import PromptContext, FileContext, RAGContext, SafetyFlags
from ..state.agent_state import AgentState, ConversationMessage


class PromptContextBuilder:
    """PromptContext構築用のビルダークラス"""
    
    def __init__(self, token_budget: int = 8000):
        """
        ビルダーを初期化
        
        Args:
            token_budget: 最大トークン予算
        """
        self.token_budget = token_budget
        self._reset()
    
    def _reset(self):
        """ビルダーの状態をリセット"""
        self.template_name = "system_base"
        self.workspace_path = "未設定"
        self.current_file = None
        self.current_task = None
        self.session_duration = 0.0
        self.workspace_manifest = []
        self.recent_messages = []
        self.memory_summary = None
        self.file_context = None
        self.rag_context = None
        self.safety_flags = SafetyFlags()
        self.routing_hints = {}
    
    def from_agent_state(self, 
                        state: AgentState, 
                        template_name: Optional[str] = None,
                        rag_results: Optional[List[Dict[str, Any]]] = None,
                        file_context_dict: Optional[Dict[str, Any]] = None) -> 'PromptContextBuilder':
        """
        AgentStateからPromptContextBuilderを初期化
        
        Args:
            state: エージェント状態
            template_name: テンプレート名（任意）
            rag_results: RAG検索結果（任意）
            file_context_dict: ファイルコンテキスト（任意）
            
        Returns:
            設定されたビルダー
        """
        self._reset()
        
        # テンプレート選択ロジック
        if template_name:
            self.template_name = template_name
        elif state.last_error and state.retry_count > 0:
            self.template_name = "system_error_recovery"
        elif (rag_results and len(rag_results) > 0) or (file_context_dict and any(file_context_dict.values())):
            self.template_name = "system_rag_enhanced"
        else:
            self.template_name = "system_base"
        
        # 基本情報の設定
        self.workspace_path = state.workspace.path if state.workspace else "未設定"
        self.current_file = state.workspace.current_file if state.workspace and state.workspace.current_file else None
        self.current_task = state.current_task
        
        # セッション時間の計算
        if hasattr(state, 'created_at') and state.created_at:
            self.session_duration = (datetime.now() - state.created_at).total_seconds() / 60
        
        # 対話履歴の処理（最新10件、機微情報マスク）
        if state.conversation_history:
            recent = state.get_recent_messages(10)
            self.recent_messages = [self._mask_sensitive_content(msg) for msg in recent]
        
        # 記憶サマリーの設定
        memory_context = state.get_memory_context() if hasattr(state, 'get_memory_context') else None
        self.memory_summary = memory_context if memory_context else None
        
        # ファイルコンテキストの構築
        if file_context_dict:
            self.file_context = self._build_file_context(file_context_dict, state)
        
        # RAGコンテキストの構築
        if rag_results:
            self.rag_context = self._build_rag_context(rag_results)
        
        # ワークスペースマニフェストの構築
        self.workspace_manifest = self._build_workspace_manifest(state, file_context_dict)
        
        # 安全性フラグの設定
        self.safety_flags = self._build_safety_flags(state, file_context_dict)
        
        # ルーティングヒントの設定
        self.routing_hints = self._build_routing_hints(state)
        
        return self
    
    def _mask_sensitive_content(self, message: ConversationMessage) -> ConversationMessage:
        """メッセージ内の機微情報をマスク"""
        import re
        content = message.content
        
        # API키나 패스워드 등을 마스킹
        patterns = [
            (r'(api[_-]?key\s*[=:]\s*)[^\s\n,}]+', r'\1***'),
            (r'(password\s*[=:]\s*)[^\s\n,}]+', r'\1***'),
            (r'(token\s*[=:]\s*)[^\s\n,}]+', r'\1***'),
        ]
        
        for pattern, replacement in patterns:
            content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
        
        # 新しいConversationMessageを作成（元のタイムスタンプとメタデータを保持）
        return ConversationMessage(
            role=message.role,
            content=content,
            timestamp=message.timestamp,
            metadata=message.metadata
        )
    
    def _build_file_context(self, file_context_dict: Dict[str, Any], state: AgentState) -> FileContext:
        """ファイルコンテキストを構築"""
        files_list = []
        if isinstance(file_context_dict.get('files_list'), list):
            files_list = file_context_dict['files_list'][:30]  # 최대 30개로 제한
        
        file_contents = {}
        if isinstance(file_context_dict.get('file_contents'), dict):
            # ファイル内容を適切な長さに制限
            for file_path, content in file_context_dict['file_contents'].items():
                if isinstance(content, str):
                    file_contents[file_path] = content[:2000]  # 최대 2000文字
        
        read_request_targets = []
        if isinstance(file_context_dict.get('read_request_targets'), list):
            read_request_targets = file_context_dict['read_request_targets']
        
        return FileContext(
            files_list=files_list,
            file_contents=file_contents,
            read_request_targets=read_request_targets
        )
    
    def _build_rag_context(self, rag_results: List[Dict[str, Any]]) -> RAGContext:
        """RAGコンテキストを構築"""
        # 언어 통계 계산
        languages = {}
        unique_files = set()
        
        for result in rag_results:
            lang = result.get("language", "unknown")
            languages[lang] = languages.get(lang, 0) + 1
            
            file_path = result.get("file_path", "")
            if file_path:
                unique_files.add(file_path)
        
        # 상위 3개 언어
        sorted_langs = sorted(languages.items(), key=lambda x: x[1], reverse=True)
        primary_languages = [lang for lang, _ in sorted_langs[:3]]
        
        return RAGContext(
            index_status="利用可能",
            search_results=rag_results[:5],  # 상위 5개 결과만 보관
            total_files=len(unique_files),
            primary_languages=primary_languages,
            recent_activity=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
    
    def _build_workspace_manifest(self, state: AgentState, file_context_dict: Optional[Dict[str, Any]]) -> List[str]:
        """軽量ワークスペースマニフェストを構築"""
        files = []
        
        # file_contextから優先取得
        if file_context_dict and isinstance(file_context_dict, dict):
            fl = file_context_dict.get('files_list')
            if isinstance(fl, list):
                files = [
                    f.get('relative_path') or f.get('path') or f.get('name', '')
                    for f in fl[:30]  # 최대 30개
                ]
        
        # 代替: state.workspace.files
        if not files and state.workspace and state.workspace.files:
            files = [
                str(Path(p).relative_to(Path.cwd()) if os.path.isabs(p) else p)
                for p in state.workspace.files[:30]
            ]
        
        return [f for f in files if f]  # 空文字列を除외
    
    def _build_safety_flags(self, state: AgentState, file_context_dict: Optional[Dict[str, Any]]) -> SafetyFlags:
        """安全性フラグを構築"""
        unknown_files = []
        requires_approval = False
        destructive_ops = []
        boundary_violations = []
        
        # 未知ファイル言급 감지 (구현 필요시)
        # 파괴적 작업 감지 (구현 필요시)
        # 워크스페이스 경계 위반 감지 (구현 필요시)
        
        return SafetyFlags(
            unknown_file_mentions=unknown_files,
            requires_approval=requires_approval,
            destructive_operations=destructive_ops,
            workspace_boundary_violations=boundary_violations
        )
    
    def _build_routing_hints(self, state: AgentState) -> Dict[str, bool]:
        """라우팅 힌트를 구築"""
        hints = {}
        
        # 最近の메시지를 바탕으로 라우팅 힌트 생성
        if state.conversation_history:
            recent_msg = state.get_recent_messages(1)
            if recent_msg:
                user_msg = recent_msg[0].content.lower()
                hints['needs_file_read'] = any(
                    keyword in user_msg 
                    for keyword in ['내용', '중身', '확인', '요약', 'read', 'show']
                )
                hints['needs_file_list'] = any(
                    keyword in user_msg
                    for keyword in ['파일', 'list', 'files', '목록']
                )
        
        return hints
    
    def with_token_budget(self, budget: int) -> 'PromptContextBuilder':
        """トークン予算を設定"""
        self.token_budget = budget
        return self
    
    def build(self) -> PromptContext:
        """PromptContextを構築して返す"""
        context = PromptContext(
            template_name=self.template_name,
            workspace_path=self.workspace_path,
            current_file=self.current_file,
            current_task=self.current_task,
            session_duration_minutes=self.session_duration,
            workspace_manifest=self.workspace_manifest,
            recent_messages=self.recent_messages,
            memory_summary=self.memory_summary,
            file_context=self.file_context,
            rag_context=self.rag_context,
            safety_flags=self.safety_flags,
            routing_hints=self.routing_hints,
            token_budget=self.token_budget,
            created_at=datetime.now()
        )
        
        # トークン예산 초과 시 조정 (구현 필요시)
        if not context.is_within_token_budget():
            # 로그 출력하거나 경고
            pass
        
        return context