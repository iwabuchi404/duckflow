"""
PromptContext - プロンプト生成用のDTO（Data Transfer Object）
ステップ2e: ハルシネーション抑制、決定性と再現性の向上、テスト容易性の確保
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from datetime import datetime

from ..state.agent_state import ConversationMessage


@dataclass(frozen=True)
class SafetyFlags:
    """安全性フラグ - 危険な操作や未知ファイルへの警告"""
    unknown_file_mentions: List[str] = field(default_factory=list)
    requires_approval: bool = False
    destructive_operations: List[str] = field(default_factory=list)
    workspace_boundary_violations: List[str] = field(default_factory=list)


@dataclass(frozen=True)  
class FileContext:
    """ファイルコンテキスト - 参照可能なファイル情報"""
    files_list: List[Dict[str, str]] = field(default_factory=list)
    file_contents: Dict[str, str] = field(default_factory=dict)
    read_request_targets: List[str] = field(default_factory=list)
    
    def get_files_sample(self, limit: int = 30) -> List[str]:
        """ファイル一覧の軽量サンプルを取得"""
        return [
            f.get('relative_path') or f.get('path') or f.get('name', '') 
            for f in self.files_list[:limit]
        ]
    
    def get_contents_excerpt(self, max_length: int = 1500) -> Dict[str, str]:
        """ファイル内容の抜粋を取得"""
        excerpts = {}
        for file_path, content in self.file_contents.items():
            if len(content) > max_length:
                excerpts[file_path] = content[:max_length] + "...(省略)"
            else:
                excerpts[file_path] = content
        return excerpts


@dataclass(frozen=True)
class RAGContext:
    """RAG検索コンテキスト - プロジェクト理解情報"""
    index_status: str = "未初期化"
    search_results: List[Dict[str, Any]] = field(default_factory=list)
    total_files: int = 0
    primary_languages: List[str] = field(default_factory=list)
    recent_activity: Optional[str] = None
    
    def get_topk_summary(self, k: int = 3) -> List[Dict[str, str]]:
        """上位K件の検索結果サマリーを取得"""
        summaries = []
        for result in self.search_results[:k]:
            file_path = result.get("file_path", "unknown")
            language = result.get("language", "unknown")
            content = result.get("content", "")
            
            # コンテンツを適切な長さに切り詰め
            preview = content[:300] + "..." if len(content) > 300 else content
            summaries.append({
                "file_path": file_path,
                "language": language,
                "preview": preview
            })
        return summaries


@dataclass(frozen=True)
class PromptContext:
    """プロンプト生成用の不変DTO - 必要最小限の情報のみを保持"""
    
    # 基本テンプレート情報
    template_name: str
    workspace_path: str
    current_file: Optional[str] = None
    current_task: Optional[str] = None
    session_duration_minutes: float = 0.0
    
    # 軽量ワークスペースマニフェスト
    workspace_manifest: List[str] = field(default_factory=list)
    
    # 対話・記憶コンテキスト（制限付き）
    recent_messages: List[ConversationMessage] = field(default_factory=list)
    memory_summary: Optional[str] = None
    
    # ファイルコンテキスト（軽量）
    file_context: Optional[FileContext] = None
    
    # RAGコンテキスト（要約版）
    rag_context: Optional[RAGContext] = None
    
    # 安全性とルーティング制御
    safety_flags: SafetyFlags = field(default_factory=SafetyFlags)
    routing_hints: Dict[str, bool] = field(default_factory=dict)
    
    # トークン予算管理
    token_budget: int = 8000  # プロンプトの最大トークン数
    
    # 生成タイムスタンプ（再現性検証用）
    created_at: datetime = field(default_factory=datetime.now)
    
    def get_manifest_formatted(self, max_files: int = 30) -> str:
        """フォーマット済みワークスペースマニフェストを取得"""
        if not self.workspace_manifest:
            return "(ファイル一覧未取得。必要に応じて list_files を実行してください)"
        
        lines = []
        for i, file_path in enumerate(self.workspace_manifest[:max_files], 1):
            lines.append(f"{i}. {file_path}")
        
        more = f"\n... 他{len(self.workspace_manifest) - max_files}件" if len(self.workspace_manifest) > max_files else ""
        return "\n".join(lines) + more
    
    def get_recent_conversation_formatted(self) -> str:
        """フォーマット済み対話履歴を取得"""
        if not self.recent_messages:
            return "対話履歴なし"
        
        conversation_parts = []
        for msg in self.recent_messages:
            timestamp = msg.timestamp.strftime("%H:%M")
            role_label = {
                "user": "ユーザー",
                "assistant": "AI", 
                "system": "システム"
            }.get(msg.role, msg.role)
            
            # メッセージ内容を適切な長さに制限
            content = msg.content[:300]
            if len(msg.content) > 300:
                content += "..."
            
            conversation_parts.append(f"[{timestamp}] {role_label}: {content}")
        
        if not conversation_parts:
            return "対話履歴なし"
        
        header = "以下は最近の対話履歴です（最新が下）:"
        return header + "\n" + "\n".join(conversation_parts)
    
    def get_file_contents_formatted(self) -> str:
        """フォーマット済みファイル内容を取得"""
        if not self.file_context or not self.file_context.file_contents:
            return "(ファイル内容未収集)"
        
        excerpts = self.file_context.get_contents_excerpt(max_length=1500)
        if not excerpts:
            return "(対象ファイル内容なし)"
        
        formatted_contents = []
        for file_path, content in excerpts.items():
            formatted_contents.append(f"""
📁 **{file_path}** ({len(self.file_context.file_contents.get(file_path, ''))} 文字)
```
{content}
```
""")
        
        return "\n".join(formatted_contents)
    
    def get_rag_context_formatted(self) -> str:
        """フォーマット済みRAGコンテキストを取得"""
        if not self.rag_context or not self.rag_context.search_results:
            return "関連するコードコンテキストは見つかりませんでした"
        
        summaries = self.rag_context.get_topk_summary(k=3)
        context_parts = []
        
        for i, summary in enumerate(summaries, 1):
            file_path = summary["file_path"]
            language = summary["language"]
            preview = summary["preview"]
            
            context_parts.append(f"[{i}] {file_path} ({language}):\n{preview}")
        
        return "\n\n".join(context_parts)
    
    def has_file_content_available(self) -> bool:
        """参照可能なファイル内容が存在するかチェック"""
        return bool(
            self.file_context and 
            self.file_context.file_contents
        )
    
    def has_rag_results_available(self) -> bool:
        """RAG検索結果が利用可能かチェック"""
        return bool(
            self.rag_context and 
            self.rag_context.search_results
        )
    
    def estimate_token_usage(self) -> int:
        """現在のコンテキストの推定トークン使用量を計算"""
        # 簡易的なトークン数推定（文字数 / 4）
        total_chars = 0
        
        # マニフェスト
        total_chars += len(self.get_manifest_formatted())
        
        # 対話履歴  
        total_chars += len(self.get_recent_conversation_formatted())
        
        # ファイル内容
        total_chars += len(self.get_file_contents_formatted())
        
        # RAGコンテキスト
        total_chars += len(self.get_rag_context_formatted())
        
        # メモリサマリー
        if self.memory_summary:
            total_chars += len(self.memory_summary)
            
        return total_chars // 4  # 概算トークン数
    
    def is_within_token_budget(self) -> bool:
        """トークン予算内に収まっているかチェック"""
        return self.estimate_token_usage() <= self.token_budget