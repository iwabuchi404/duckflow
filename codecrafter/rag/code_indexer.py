"""
プロジェクトコードのインデックス化システム
LangChainとChromaDBを使用してコードベースをベクトル化
"""
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_community.embeddings import HuggingFaceEmbeddings

from ..base.config import config_manager
from ..ui.rich_ui import rich_ui


class CodeDocument:
    """コードドキュメントを表現するクラス"""
    
    def __init__(
        self,
        file_path: str,
        content: str,
        language: str,
        size: int,
        modified_time: datetime
    ):
        """コードドキュメントを初期化
        
        Args:
            file_path: ファイルパス
            content: ファイル内容
            language: プログラミング言語
            size: ファイルサイズ
            modified_time: 最終更新時刻
        """
        self.file_path = file_path
        self.content = content
        self.language = language
        self.size = size
        self.modified_time = modified_time


class CodeIndexer:
    """プロジェクトコードのインデックス化を管理するクラス"""
    
    def __init__(self, project_path: str = "."):
        """インデックサーを初期化
        
        Args:
            project_path: プロジェクトのルートパス
        """
        self.project_path = Path(project_path).resolve()
        self.config = config_manager.load_config()
        
        # ベクトルストア設定
        self.vector_store_path = self.project_path / ".duckflow" / "vectorstore"
        self.vector_store: Optional[Chroma] = None
        
        # インデックス対象の拡張子
        self.supported_extensions = {
            '.py': 'python',
            '.js': 'javascript', 
            '.ts': 'typescript',
            '.jsx': 'jsx',
            '.tsx': 'tsx',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.cs': 'csharp',
            '.go': 'go',
            '.rs': 'rust',
            '.php': 'php',
            '.rb': 'ruby',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.scala': 'scala',
            '.md': 'markdown',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.json': 'json',
            '.xml': 'xml',
            '.html': 'html',
            '.css': 'css',
            '.sql': 'sql',
            '.sh': 'bash',
            '.ps1': 'powershell',
        }
        
        # 除外するディレクトリ
        self.excluded_dirs = {
            '.git', '.svn', '.hg',
            'node_modules', '.venv', 'venv', '.env',
            '__pycache__', '.pytest_cache',
            'build', 'dist', 'target',
            '.idea', '.vscode',
            '.duckflow'
        }
        
        # テキスト分割設定
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )
        
        # 埋め込みモデル
        self.embeddings = self._initialize_embeddings()
    
    def _initialize_embeddings(self) -> Any:
        """埋め込みモデルを初期化
        
        Returns:
            初期化された埋め込みモデル
        """
        try:
            # OpenAI embeddings を優先
            if hasattr(self.config.llm, 'openai_api_key') and self.config.llm.openai_api_key:
                return OpenAIEmbeddings(
                    openai_api_key=self.config.llm.openai_api_key,
                    model="text-embedding-3-small"
                )
            else:
                # フォールバック: HuggingFace embeddings（ローカル）
                rich_ui.print_message("OpenAI APIキーが設定されていません。ローカル埋め込みモデルを使用します", "warning")
                return HuggingFaceEmbeddings(
                    model_name="sentence-transformers/all-MiniLM-L6-v2",
                    model_kwargs={'device': 'cpu'}
                )
        except Exception as e:
            # エラーメッセージを簡略化して表示（Unicode問題回避）
            print(f"Warning: Failed to initialize embedding model: {str(e)}")
            # 最小限のフォールバック
            try:
                return HuggingFaceEmbeddings(
                    model_name="sentence-transformers/all-MiniLM-L6-v2",
                    model_kwargs={'device': 'cpu'}
                )
            except Exception:
                # 最終的なフォールバック - 埋め込み無しモード
                raise ValueError("RAG機能を使用するにはOpenAI APIキーまたはsentence-transformersが必要です")
    
    def scan_project(self) -> List[CodeDocument]:
        """プロジェクト内のコードファイルをスキャン
        
        Returns:
            検出されたコードドキュメント一覧
        """
        code_docs = []
        scanned_files = 0
        
        rich_ui.print_message(f"📁 プロジェクトをスキャン中: {self.project_path}", "info")
        
        for file_path in self.project_path.rglob("*"):
            if not file_path.is_file():
                continue
            
            # 除外ディレクトリチェック
            if any(excluded in file_path.parts for excluded in self.excluded_dirs):
                continue
            
            # サポート対象の拡張子チェック
            if file_path.suffix.lower() not in self.supported_extensions:
                continue
            
            try:
                # ファイル情報取得
                stat = file_path.stat()
                if stat.st_size > 1024 * 1024:  # 1MB以上のファイルをスキップ
                    rich_ui.print_message(f"⚠️  大きなファイルをスキップ: {file_path} ({stat.st_size} bytes)", "warning")
                    continue
                
                # ファイル内容読み込み
                try:
                    content = file_path.read_text(encoding='utf-8')
                except UnicodeDecodeError:
                    # UTF-8で読めない場合はスキップ
                    continue
                
                # CodeDocumentを作成
                language = self.supported_extensions[file_path.suffix.lower()]
                modified_time = datetime.fromtimestamp(stat.st_mtime)
                
                relative_path = file_path.relative_to(self.project_path)
                
                code_doc = CodeDocument(
                    file_path=str(relative_path),
                    content=content,
                    language=language,
                    size=stat.st_size,
                    modified_time=modified_time
                )
                
                code_docs.append(code_doc)
                scanned_files += 1
                
                # プログレス表示
                if scanned_files % 10 == 0:
                    rich_ui.print_message(f"📄 {scanned_files} ファイルをスキャン済み...", "muted")
                
            except Exception as e:
                rich_ui.print_message(f"⚠️  {file_path} の読み込みに失敗: {e}", "warning")
                continue
        
        rich_ui.print_success(f"✅ スキャン完了: {len(code_docs)} ファイルを発見")
        return code_docs
    
    def create_index(self, force_rebuild: bool = False) -> bool:
        """プロジェクトのインデックスを作成
        
        Args:
            force_rebuild: 既存インデックスを強制再構築するか
            
        Returns:
            インデックス作成が成功したか
        """
        try:
            # 既存インデックスのチェック
            if not force_rebuild and self.vector_store_path.exists():
                rich_ui.print_message("📊 既存のインデックスを読み込み中...", "info")
                self.vector_store = Chroma(
                    persist_directory=str(self.vector_store_path),
                    embedding_function=self.embeddings
                )
                collection = self.vector_store._collection
                if collection.count() > 0:
                    rich_ui.print_success(f"✅ 既存インデックスを読み込み完了 ({collection.count()} ドキュメント)")
                    return True
            
            # プロジェクトスキャン
            code_docs = self.scan_project()
            if not code_docs:
                rich_ui.print_warning("インデックス化するファイルが見つかりませんでした")
                return False
            
            # LangChain Documents に変換
            rich_ui.print_message("🔄 ドキュメントを変換中...", "info")
            documents = []
            
            for code_doc in code_docs:
                # コードを適切なサイズに分割
                chunks = self.text_splitter.split_text(code_doc.content)
                
                for i, chunk in enumerate(chunks):
                    metadata = {
                        "file_path": code_doc.file_path,
                        "language": code_doc.language,
                        "size": code_doc.size,
                        "modified_time": code_doc.modified_time.isoformat(),
                        "chunk_index": i,
                        "total_chunks": len(chunks)
                    }
                    
                    document = Document(
                        page_content=chunk,
                        metadata=metadata
                    )
                    documents.append(document)
            
            rich_ui.print_message(f"📚 {len(documents)} チャンクに分割完了", "info")
            
            # ベクトルストア作成
            rich_ui.print_message("🧠 ベクトル埋め込みを作成中...", "info")
            start_time = time.time()
            
            # ディレクトリ準備
            self.vector_store_path.parent.mkdir(parents=True, exist_ok=True)
            
            # ChromaDBでベクトルストア作成
            self.vector_store = Chroma.from_documents(
                documents=documents,
                embedding=self.embeddings,
                persist_directory=str(self.vector_store_path)
            )
            
            # 永続化
            self.vector_store.persist()
            
            elapsed = time.time() - start_time
            rich_ui.print_success(f"✅ インデックス作成完了 ({elapsed:.2f}秒)")
            rich_ui.print_message(f"💾 インデックスを保存: {self.vector_store_path}", "info")
            
            return True
            
        except Exception as e:
            rich_ui.print_error(f"インデックス作成に失敗: {e}")
            return False
    
    def get_index_stats(self) -> Dict[str, Any]:
        """インデックスの統計情報を取得
        
        Returns:
            インデックス統計情報
        """
        if not self.vector_store:
            return {"status": "not_initialized"}
        
        try:
            collection = self.vector_store._collection
            count = collection.count()
            
            # ファイル数を集計
            all_docs = self.vector_store.get()
            file_paths = set()
            languages = {}
            
            for metadata in all_docs.get('metadatas', []):
                if metadata:
                    file_path = metadata.get('file_path')
                    language = metadata.get('language')
                    
                    if file_path:
                        file_paths.add(file_path)
                    
                    if language:
                        languages[language] = languages.get(language, 0) + 1
            
            return {
                "status": "ready",
                "total_chunks": count,
                "unique_files": len(file_paths),
                "languages": languages,
                "index_path": str(self.vector_store_path),
                "created": self.vector_store_path.exists()
            }
            
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def search_code(self, query: str, k: int = 5, filter_dict: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """コードを検索
        
        Args:
            query: 検索クエリ
            k: 取得する結果数
            filter_dict: メタデータフィルタ
            
        Returns:
            検索結果一覧
        """
        if not self.vector_store:
            raise ValueError("ベクトルストアが初期化されていません")
        
        try:
            # 類似検索実行
            if filter_dict:
                docs = self.vector_store.similarity_search_with_score(
                    query, k=k, filter=filter_dict
                )
            else:
                docs = self.vector_store.similarity_search_with_score(query, k=k)
            
            results = []
            for doc, score in docs:
                result = {
                    "content": doc.page_content,
                    "score": float(score),
                    "metadata": doc.metadata,
                    "file_path": doc.metadata.get("file_path", "unknown"),
                    "language": doc.metadata.get("language", "unknown"),
                    "chunk_index": doc.metadata.get("chunk_index", 0)
                }
                results.append(result)
            
            return results
            
        except Exception as e:
            rich_ui.print_error(f"コード検索に失敗: {e}")
            return []
    
    def close(self) -> None:
        """リソースをクリーンアップ"""
        if self.vector_store:
            try:
                self.vector_store.persist()
            except Exception as e:
                rich_ui.print_warning(f"インデックス保存時に警告: {e}")
        
        self.vector_store = None