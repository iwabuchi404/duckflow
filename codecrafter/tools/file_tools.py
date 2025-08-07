"""
ファイル操作ツール
"""
import os
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from ..base.config import config_manager


class FileOperationError(Exception):
    """ファイル操作エラー"""
    pass


class FileTools:
    """ファイル操作ツールクラス"""
    
    def __init__(self):
        """初期化"""
        self.config = config_manager.load_config()
        self.file_config = self.config.tools.file_operations
        
        # 許可されるファイル拡張子
        self.allowed_extensions = self.file_config.get('allowed_extensions', [])
        
        # 最大ファイルサイズ（MB）
        self.max_file_size_mb = self.file_config.get('max_file_size_mb', 10)
        
        # バックアップが有効かどうか
        self.backup_enabled = self.file_config.get('backup_enabled', True)
    
    def _validate_file_path(self, file_path: str) -> Path:
        """ファイルパスの検証"""
        path = Path(file_path).resolve()
        
        # 拡張子のチェック
        if self.allowed_extensions and path.suffix not in self.allowed_extensions:
            raise FileOperationError(f"許可されていないファイル拡張子です: {path.suffix}")
        
        return path
    
    def _validate_file_size(self, file_path: Path) -> None:
        """ファイルサイズの検証"""
        if file_path.exists():
            size_mb = file_path.stat().st_size / (1024 * 1024)
            if size_mb > self.max_file_size_mb:
                raise FileOperationError(f"ファイルサイズが制限を超えています: {size_mb:.2f}MB > {self.max_file_size_mb}MB")
    
    def _create_backup(self, file_path: Path) -> Optional[Path]:
        """ファイルのバックアップを作成"""
        if not self.backup_enabled or not file_path.exists():
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = file_path.with_suffix(f".backup_{timestamp}{file_path.suffix}")
        
        try:
            shutil.copy2(file_path, backup_path)
            return backup_path
        except Exception as e:
            # バックアップに失敗しても処理は継続
            print(f"警告: バックアップの作成に失敗しました: {e}")
            return None
    
    def list_files(self, directory_path: str, pattern: str = "*", recursive: bool = False) -> List[Dict[str, Any]]:
        """
        ディレクトリ内のファイル一覧を取得
        
        Args:
            directory_path: ディレクトリパス
            pattern: ファイルパターン（例: "*.py"）
            recursive: 再帰的に検索するかどうか
        
        Returns:
            ファイル情報のリスト
        """
        try:
            dir_path = Path(directory_path).resolve()
            
            if not dir_path.exists():
                raise FileOperationError(f"ディレクトリが存在しません: {directory_path}")
            
            if not dir_path.is_dir():
                raise FileOperationError(f"パスがディレクトリではありません: {directory_path}")
            
            # ファイル検索
            if recursive:
                files = list(dir_path.rglob(pattern))
            else:
                files = list(dir_path.glob(pattern))
            
            # ファイル情報を構築
            file_list = []
            for file_path in sorted(files):
                if file_path.is_file():
                    stat = file_path.stat()
                    file_info = {
                        'name': file_path.name,
                        'path': str(file_path),
                        'relative_path': str(file_path.relative_to(dir_path)),
                        'size': stat.st_size,
                        'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        'extension': file_path.suffix,
                    }
                    file_list.append(file_info)
            
            return file_list
            
        except Exception as e:
            raise FileOperationError(f"ファイル一覧の取得に失敗しました: {e}")
    
    def read_file(self, file_path: str, encoding: str = 'utf-8') -> str:
        """
        ファイルを読み取り
        
        Args:
            file_path: ファイルパス
            encoding: 文字エンコーディング
        
        Returns:
            ファイルの内容
        """
        try:
            path = self._validate_file_path(file_path)
            self._validate_file_size(path)
            
            if not path.exists():
                raise FileOperationError(f"ファイルが存在しません: {file_path}")
            
            if not path.is_file():
                raise FileOperationError(f"パスがファイルではありません: {file_path}")
            
            with open(path, 'r', encoding=encoding) as f:
                return f.read()
                
        except Exception as e:
            raise FileOperationError(f"ファイル読み取りに失敗しました: {e}")
    
    def write_file(self, file_path: str, content: str, encoding: str = 'utf-8', create_dirs: bool = True) -> Dict[str, Any]:
        """
        ファイルに書き込み
        
        Args:
            file_path: ファイルパス
            content: 書き込む内容
            encoding: 文字エンコーディング
            create_dirs: 親ディレクトリを作成するかどうか
        
        Returns:
            操作結果の情報
        """
        try:
            path = self._validate_file_path(file_path)
            
            # バックアップの作成
            backup_path = self._create_backup(path)
            
            # 親ディレクトリの作成
            if create_dirs:
                path.parent.mkdir(parents=True, exist_ok=True)
            
            # ファイルに書き込み
            with open(path, 'w', encoding=encoding) as f:
                f.write(content)
            
            # 結果情報
            stat = path.stat()
            result = {
                'path': str(path),
                'size': stat.st_size,
                'backup_created': backup_path is not None,
                'backup_path': str(backup_path) if backup_path else None,
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            }
            
            return result
            
        except Exception as e:
            raise FileOperationError(f"ファイル書き込みに失敗しました: {e}")
    
    def create_directory(self, directory_path: str, parents: bool = True) -> Dict[str, Any]:
        """
        ディレクトリを作成
        
        Args:
            directory_path: ディレクトリパス
            parents: 親ディレクトリも作成するかどうか
        
        Returns:
            操作結果の情報
        """
        try:
            path = Path(directory_path).resolve()
            
            if path.exists():
                if path.is_dir():
                    return {
                        'path': str(path),
                        'created': False,
                        'message': 'ディレクトリは既に存在します'
                    }
                else:
                    raise FileOperationError(f"同名のファイルが既に存在します: {directory_path}")
            
            path.mkdir(parents=parents, exist_ok=False)
            
            return {
                'path': str(path),
                'created': True,
                'message': 'ディレクトリを作成しました'
            }
            
        except Exception as e:
            raise FileOperationError(f"ディレクトリ作成に失敗しました: {e}")
    
    def delete_file(self, file_path: str, create_backup: bool = True) -> Dict[str, Any]:
        """
        ファイルを削除
        
        Args:
            file_path: ファイルパス
            create_backup: バックアップを作成するかどうか
        
        Returns:
            操作結果の情報
        """
        try:
            path = Path(file_path).resolve()
            
            if not path.exists():
                raise FileOperationError(f"ファイルが存在しません: {file_path}")
            
            if not path.is_file():
                raise FileOperationError(f"パスがファイルではありません: {file_path}")
            
            # バックアップの作成
            backup_path = None
            if create_backup:
                backup_path = self._create_backup(path)
            
            # ファイル削除
            path.unlink()
            
            result = {
                'path': str(path),
                'deleted': True,
                'backup_created': backup_path is not None,
                'backup_path': str(backup_path) if backup_path else None,
            }
            
            return result
            
        except Exception as e:
            raise FileOperationError(f"ファイル削除に失敗しました: {e}")
    
    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """
        ファイル情報を取得
        
        Args:
            file_path: ファイルパス
        
        Returns:
            ファイル情報
        """
        try:
            path = Path(file_path).resolve()
            
            if not path.exists():
                raise FileOperationError(f"ファイルが存在しません: {file_path}")
            
            stat = path.stat()
            
            return {
                'name': path.name,
                'path': str(path),
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'is_file': path.is_file(),
                'is_directory': path.is_dir(),
                'extension': path.suffix,
                'parent': str(path.parent),
            }
            
        except Exception as e:
            raise FileOperationError(f"ファイル情報の取得に失敗しました: {e}")


# グローバルなファイルツールインスタンス
file_tools = FileTools()