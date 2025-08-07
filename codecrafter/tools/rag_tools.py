"""
RAG (Retrieval-Augmented Generation) ツール群
プロジェクトコードの検索とインデックス管理
"""
import time
from typing import Dict, List, Optional, Any
from pathlib import Path

from ..rag.code_indexer import CodeIndexer
from ..ui.rich_ui import rich_ui


class RAGToolError(Exception):
    """RAGツール関連のエラー"""
    pass


class RAGTools:
    """RAG機能のツール群を提供するクラス"""
    
    def __init__(self, project_path: str = "."):
        """RAGツールを初期化
        
        Args:
            project_path: プロジェクトのルートパス
        """
        self.project_path = project_path
        self.indexer: Optional[CodeIndexer] = None
        self._indexer_error: Optional[str] = None
        self._try_initialize_indexer()
    
    def _try_initialize_indexer(self) -> None:
        """コードインデックサーを初期化（エラー時は遅延初期化）"""
        try:
            self.indexer = CodeIndexer(self.project_path)
        except Exception as e:
            # 初期化エラーを記録するが、例外は投げない（遅延初期化）
            self._indexer_error = f"RAG system initialization failed: {str(e)}"
            print(f"Warning: {self._indexer_error}")
            print("RAG features will be unavailable until OpenAI API key is configured or sentence-transformers is installed")
    
    def _ensure_indexer(self) -> None:
        """インデックサーが利用可能か確認し、必要に応じて初期化"""
        if self.indexer is None:
            if self._indexer_error:
                raise RAGToolError(self._indexer_error)
            # 遅延初期化を試行
            try:
                self.indexer = CodeIndexer(self.project_path)
                self._indexer_error = None
            except Exception as e:
                error_msg = f"RAG system initialization failed: {str(e)}"
                self._indexer_error = error_msg
                raise RAGToolError(error_msg)
    
    def index_project(self, force_rebuild: bool = False) -> Dict[str, Any]:
        """プロジェクトをインデックス化
        
        Args:
            force_rebuild: 既存インデックスを強制再構築するか
            
        Returns:
            インデックス化の結果
        """
        try:
            self._ensure_indexer()
            
            start_time = time.time()
            
            rich_ui.print_message("🔍 プロジェクトのインデックス化を開始...", "info")
            
            success = self.indexer.create_index(force_rebuild=force_rebuild)
            
            if success:
                elapsed = time.time() - start_time
                stats = self.indexer.get_index_stats()
                
                result = {
                    "success": True,
                    "message": "プロジェクトのインデックス化が完了しました",
                    "elapsed_time": elapsed,
                    "stats": stats
                }
                
                rich_ui.print_success(f"✅ インデックス化完了: {stats.get('unique_files', 0)} ファイル, {stats.get('total_chunks', 0)} チャンク")
                return result
            else:
                return {
                    "success": False,
                    "message": "インデックス化に失敗しました"
                }
            
        except Exception as e:
            error_msg = f"インデックス化エラー: {e}"
            rich_ui.print_error(error_msg)
            raise RAGToolError(error_msg)
    
    def search_code(
        self, 
        query: str, 
        max_results: int = 5, 
        file_type: Optional[str] = None,
        file_path_pattern: Optional[str] = None
    ) -> Dict[str, Any]:
        """コードを検索
        
        Args:
            query: 検索クエリ
            max_results: 最大結果数
            file_type: ファイルタイプでフィルタ（例: "python", "javascript"）
            file_path_pattern: ファイルパスパターンでフィルタ
            
        Returns:
            検索結果
        """
        try:
            self._ensure_indexer()
            
            # インデックス存在確認
            stats = self.indexer.get_index_stats()
            if stats.get("status") != "ready":
                return {
                    "success": False,
                    "message": "インデックスが利用できません。先に 'index_project' を実行してください",
                    "results": []
                }
            
            start_time = time.time()
            
            # フィルタ条件構築
            filter_dict = None
            if file_type or file_path_pattern:
                filter_dict = {}
                if file_type:
                    filter_dict["language"] = file_type
                if file_path_pattern:
                    # 簡単なパターンマッチング（完全マッチのみ）
                    filter_dict["file_path"] = file_path_pattern
            
            rich_ui.print_message(f"🔍 検索中: '{query}'", "info")
            
            # 検索実行
            search_results = self.indexer.search_code(
                query=query, 
                k=max_results, 
                filter_dict=filter_dict
            )
            
            elapsed = time.time() - start_time
            
            # 結果をフォーマット
            formatted_results = []
            for result in search_results:
                formatted_result = {
                    "file_path": result["file_path"],
                    "language": result["language"],
                    "content": result["content"],
                    "relevance_score": result["score"],
                    "chunk_index": result["chunk_index"]
                }
                formatted_results.append(formatted_result)
            
            result_summary = {
                "success": True,
                "query": query,
                "total_results": len(formatted_results),
                "elapsed_time": elapsed,
                "results": formatted_results
            }
            
            # 結果表示
            if formatted_results:
                rich_ui.print_success(f"✅ {len(formatted_results)} 件の検索結果を発見")
                
                for i, result in enumerate(formatted_results[:3], 1):  # 最初の3件を表示
                    rich_ui.print_message(f"\n📄 {i}. {result['file_path']} ({result['language']})", "info")
                    content_preview = result['content'][:200]
                    if len(result['content']) > 200:
                        content_preview += "..."
                    rich_ui.print_message(f"   {content_preview}", "muted")
                
                if len(formatted_results) > 3:
                    rich_ui.print_message(f"   ... その他 {len(formatted_results) - 3} 件", "muted")
            else:
                rich_ui.print_message(f"🔍 '{query}' に該当するコードが見つかりませんでした", "warning")
            
            return result_summary
            
        except Exception as e:
            error_msg = f"コード検索エラー: {e}"
            rich_ui.print_error(error_msg)
            return {
                "success": False,
                "message": error_msg,
                "results": []
            }
    
    def get_index_status(self) -> Dict[str, Any]:
        """インデックスの状態を取得
        
        Returns:
            インデックス状態情報
        """
        try:
            if self.indexer is None and self._indexer_error:
                return {
                    "status": "error", 
                    "message": f"RAG system not available: {self._indexer_error}"
                }
            
            if self.indexer is None:
                return {
                    "status": "not_initialized",
                    "message": "RAG system not initialized"
                }
            
            stats = self.indexer.get_index_stats()
            
            # 表示用にフォーマット
            if stats.get("status") == "ready":
                rich_ui.print_message("📊 インデックス状態:", "info")
                rich_ui.print_message(f"  ファイル数: {stats.get('unique_files', 0)}", "muted")
                rich_ui.print_message(f"  チャンク数: {stats.get('total_chunks', 0)}", "muted")
                
                languages = stats.get('languages', {})
                if languages:
                    rich_ui.print_message("  言語別分布:", "muted")
                    for lang, count in sorted(languages.items()):
                        rich_ui.print_message(f"    {lang}: {count} チャンク", "muted")
                
                rich_ui.print_message(f"  保存場所: {stats.get('index_path', 'unknown')}", "muted")
            
            return stats
            
        except Exception as e:
            error_msg = f"インデックス状態取得エラー: {e}"
            rich_ui.print_error(error_msg)
            return {
                "status": "error",
                "message": error_msg
            }
    
    def cleanup(self) -> None:
        """リソースをクリーンアップ"""
        if self.indexer:
            self.indexer.close()
            self.indexer = None


# グローバルインスタンス
rag_tools = RAGTools()