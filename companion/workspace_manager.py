# workspace_manager.py
"""
Workspace Manager - 作業フォルダ管理システム
作業ディレクトリの切り替え、履歴管理、ブックマーク機能を提供
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class WorkspaceInfo:
    """作業スペース情報"""
    path: str
    name: Optional[str] = None
    description: Optional[str] = None
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    is_bookmark: bool = False
    project_type: Optional[str] = None  # プロジェクトの種類（python, js, etc.）
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "path": self.path,
            "name": self.name,
            "description": self.description,
            "last_accessed": self.last_accessed.isoformat(),
            "access_count": self.access_count,
            "is_bookmark": self.is_bookmark,
            "project_type": self.project_type
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkspaceInfo':
        """辞書からWorkspaceInfoを復元"""
        return cls(
            path=data["path"],
            name=data.get("name"),
            description=data.get("description"),
            last_accessed=datetime.fromisoformat(data.get("last_accessed", datetime.now().isoformat())),
            access_count=data.get("access_count", 0),
            is_bookmark=data.get("is_bookmark", False),
            project_type=data.get("project_type")
        )


class WorkspaceManager:
    """作業フォルダ管理システム"""
    
    def __init__(self, config_file: Optional[str] = None):
        """初期化
        
        Args:
            config_file: 設定ファイルのパス
        """
        if config_file:
            self.config_file = Path(config_file)
        else:
            self.config_file = Path.home() / ".duckflow_workspaces.json"
        
        self.current_workspace: str = os.getcwd()
        self.workspace_history: List[WorkspaceInfo] = []
        self.bookmarks: Dict[str, WorkspaceInfo] = {}
        self.max_history = 20  # 履歴の最大保持数
        
        # 設定を読み込み
        self._load_config()
        
        # 現在のワークスペースを履歴に追加
        self._add_to_history(self.current_workspace)
    
    def _load_config(self):
        """設定ファイルから情報を読み込み"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 履歴を復元
                self.workspace_history = [
                    WorkspaceInfo.from_dict(item) 
                    for item in data.get("history", [])
                ]
                
                # ブックマークを復元
                bookmarks_data = data.get("bookmarks", {})
                self.bookmarks = {
                    name: WorkspaceInfo.from_dict(info)
                    for name, info in bookmarks_data.items()
                }
                
                # 現在のワークスペースを復元
                self.current_workspace = data.get("current_workspace", os.getcwd())
                
        except Exception as e:
            print(f"設定ファイル読み込みエラー: {e}")
            # エラーの場合はデフォルト値を使用
    
    def _save_config(self):
        """設定ファイルに情報を保存"""
        try:
            # ディレクトリが存在しない場合は作成
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                "current_workspace": self.current_workspace,
                "history": [workspace.to_dict() for workspace in self.workspace_history],
                "bookmarks": {
                    name: info.to_dict() 
                    for name, info in self.bookmarks.items()
                }
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"設定ファイル保存エラー: {e}")
    
    def change_workspace(self, path: str, name: Optional[str] = None) -> tuple[bool, str]:
        """作業フォルダを変更
        
        Args:
            path: 新しい作業フォルダのパス
            name: ワークスペースの名前（オプション）
            
        Returns:
            tuple[bool, str]: (成功フラグ, メッセージ)
        """
        try:
            # パスを正規化
            target_path = Path(path).resolve()
            
            # ディレクトリの存在確認
            if not target_path.exists():
                return False, f"❌ パスが存在しません: {target_path}"
            
            if not target_path.is_dir():
                return False, f"❌ ディレクトリではありません: {target_path}"
            
            # アクセス権限確認
            if not os.access(target_path, os.R_OK):
                return False, f"❌ 読み取り権限がありません: {target_path}"
            
            # 現在のワークスペースを履歴に追加
            self._add_to_history(self.current_workspace)
            
            # ワークスペースを変更
            old_workspace = self.current_workspace
            self.current_workspace = str(target_path)
            os.chdir(target_path)
            
            # 新しいワークスペースを履歴に追加
            self._add_to_history(str(target_path), name)
            
            # 設定を保存
            self._save_config()
            
            # プロジェクト種別を検出
            project_type = self._detect_project_type(target_path)
            project_info = f" ({project_type}プロジェクト)" if project_type else ""
            
            return True, f"✅ 作業フォルダを変更しました\n📁 {old_workspace}\n  ↓\n📂 {target_path}{project_info}"
            
        except Exception as e:
            return False, f"❌ 作業フォルダの変更に失敗: {str(e)}"
    
    def _add_to_history(self, path: str, name: Optional[str] = None):
        """履歴にワークスペースを追加"""
        path = str(Path(path).resolve())
        
        # 既存の履歴から同じパスを削除
        self.workspace_history = [w for w in self.workspace_history if w.path != path]
        
        # 新しいエントリを作成
        workspace_info = WorkspaceInfo(
            path=path,
            name=name or self._get_folder_name(path),
            project_type=self._detect_project_type(Path(path))
        )
        
        # 既存のワークスペース情報があれば更新
        for existing in self.workspace_history:
            if existing.path == path:
                existing.access_count += 1
                existing.last_accessed = datetime.now()
                break
        else:
            # 新しいエントリを先頭に追加
            self.workspace_history.insert(0, workspace_info)
        
        # 履歴の上限管理
        if len(self.workspace_history) > self.max_history:
            self.workspace_history = self.workspace_history[:self.max_history]
    
    def _get_folder_name(self, path: str) -> str:
        """フォルダ名を取得"""
        return Path(path).name or str(Path(path))
    
    def get_current_directory_name(self) -> str:
        """現在のディレクトリ名を取得（ChatLoopとの互換性用）"""
        return self._get_folder_name(self.current_workspace)
    
    def cd(self, path: str) -> str:
        """ディレクトリを変更（ChatLoopとの互換性用）
        
        Args:
            path: 移動先のパス
            
        Returns:
            str: 結果メッセージ
            
        Raises:
            Exception: 移動に失敗した場合
        """
        success, message = self.change_workspace(path)
        if success:
            return message
        else:
            raise Exception(message.replace("❌ ", ""))
    
    def pwd(self) -> str:
        """現在のディレクトリパスを取得（ChatLoopとの互換性用）
        
        Returns:
            str: 現在のディレクトリパス
        """
        return str(Path(self.current_workspace).resolve())
    
    def ls(self, path: str = ".") -> str:
        """ディレクトリの内容を一覧表示（ChatLoopとの互換性用）
        
        Args:
            path: 一覧表示するパス（デフォルト: 現在のディレクトリ）
            
        Returns:
            str: ディレクトリの内容
        """
        try:
            # パスが相対パスの場合は現在のワークスペースからの相対パスとして解釈
            if not Path(path).is_absolute():
                target_path = Path(self.current_workspace) / path
            else:
                target_path = Path(path)
            
            target_path = target_path.resolve()
            
            if not target_path.exists():
                return f"パスが存在しません: {target_path}"
            
            if not target_path.is_dir():
                return f"ディレクトリではありません: {target_path}"
            
            # ディレクトリの内容を取得
            items = []
            try:
                for item in target_path.iterdir():
                    if item.is_dir():
                        items.append(f"📁 {item.name}/")
                    else:
                        items.append(f"📄 {item.name}")
            except PermissionError:
                return f"アクセス権限がありません: {target_path}"
            
            if not items:
                return "空のディレクトリです"
            
            return "\n".join(sorted(items))
            
        except Exception as e:
            return f"エラー: {e}"
    
    def _detect_project_type(self, path: Path) -> Optional[str]:
        """プロジェクトの種類を検出"""
        try:
            files = [f.name.lower() for f in path.iterdir() if f.is_file()]
            
            # Python project
            if any(f in files for f in ['requirements.txt', 'pyproject.toml', 'setup.py', 'pipfile']):
                return "Python"
            
            # Node.js project
            if 'package.json' in files:
                return "Node.js"
            
            # Rust project
            if 'cargo.toml' in files:
                return "Rust"
            
            # Go project
            if 'go.mod' in files:
                return "Go"
            
            # Java project
            if any(f in files for f in ['pom.xml', 'build.gradle']):
                return "Java"
            
            # C/C++ project
            if any(f in files for f in ['makefile', 'cmakelists.txt']):
                return "C/C++"
            
            # Git repository
            if (path / '.git').exists():
                return "Git"
            
            return None
            
        except Exception:
            return None
    
    def get_current_workspace(self) -> WorkspaceInfo:
        """現在のワークスペース情報を取得"""
        current_info = None
        for workspace in self.workspace_history:
            if workspace.path == self.current_workspace:
                current_info = workspace
                break
        
        if not current_info:
            current_info = WorkspaceInfo(
                path=self.current_workspace,
                name=self._get_folder_name(self.current_workspace),
                project_type=self._detect_project_type(Path(self.current_workspace))
            )
        
        return current_info
    
    def list_recent_workspaces(self, limit: int = 10) -> List[WorkspaceInfo]:
        """最近のワークスペース一覧を取得
        
        Args:
            limit: 取得する最大数
            
        Returns:
            List[WorkspaceInfo]: 最近のワークスペース一覧
        """
        return self.workspace_history[:limit]
    
    def add_bookmark(self, name: str, path: Optional[str] = None, description: Optional[str] = None) -> tuple[bool, str]:
        """ブックマークを追加
        
        Args:
            name: ブックマーク名
            path: パス（指定しない場合は現在のワークスペース）
            description: 説明
            
        Returns:
            tuple[bool, str]: (成功フラグ, メッセージ)
        """
        try:
            target_path = path or self.current_workspace
            target_path = str(Path(target_path).resolve())
            
            if not Path(target_path).exists():
                return False, f"❌ パスが存在しません: {target_path}"
            
            # ブックマーク名の重複チェック
            if name in self.bookmarks:
                return False, f"❌ ブックマーク名 '{name}' は既に存在します"
            
            # ブックマークを作成
            bookmark = WorkspaceInfo(
                path=target_path,
                name=name,
                description=description,
                is_bookmark=True,
                project_type=self._detect_project_type(Path(target_path))
            )
            
            self.bookmarks[name] = bookmark
            self._save_config()
            
            return True, f"📌 ブックマーク '{name}' を追加しました: {target_path}"
            
        except Exception as e:
            return False, f"❌ ブックマーク追加に失敗: {str(e)}"
    
    def remove_bookmark(self, name: str) -> tuple[bool, str]:
        """ブックマークを削除
        
        Args:
            name: ブックマーク名
            
        Returns:
            tuple[bool, str]: (成功フラグ, メッセージ)
        """
        if name not in self.bookmarks:
            return False, f"❌ ブックマーク '{name}' が見つかりません"
        
        removed_path = self.bookmarks[name].path
        del self.bookmarks[name]
        self._save_config()
        
        return True, f"🗑️ ブックマーク '{name}' を削除しました: {removed_path}"
    
    def list_bookmarks(self) -> List[WorkspaceInfo]:
        """ブックマーク一覧を取得"""
        return list(self.bookmarks.values())
    
    def change_to_bookmark(self, name: str) -> tuple[bool, str]:
        """ブックマークに移動
        
        Args:
            name: ブックマーク名
            
        Returns:
            tuple[bool, str]: (成功フラグ, メッセージ)
        """
        if name not in self.bookmarks:
            return False, f"❌ ブックマーク '{name}' が見つかりません"
        
        bookmark = self.bookmarks[name]
        
        # ブックマークのアクセス回数を更新
        bookmark.access_count += 1
        bookmark.last_accessed = datetime.now()
        
        return self.change_workspace(bookmark.path, bookmark.name)
    
    def go_back(self) -> tuple[bool, str]:
        """前のワークスペースに戻る
        
        Returns:
            tuple[bool, str]: (成功フラグ, メッセージ)
        """
        if len(self.workspace_history) < 2:
            return False, "❌ 戻る先のワークスペースがありません"
        
        # 現在のワークスペース（履歴の先頭）を除いて、次のワークスペースに移動
        previous_workspace = self.workspace_history[1]
        return self.change_workspace(previous_workspace.path, previous_workspace.name)
    
    def search_workspaces(self, query: str) -> List[WorkspaceInfo]:
        """ワークスペースを検索
        
        Args:
            query: 検索クエリ
            
        Returns:
            List[WorkspaceInfo]: 検索結果
        """
        query_lower = query.lower()
        results = []
        
        # 履歴から検索
        for workspace in self.workspace_history:
            if (query_lower in workspace.path.lower() or 
                (workspace.name and query_lower in workspace.name.lower()) or
                (workspace.description and query_lower in workspace.description.lower()) or
                (workspace.project_type and query_lower in workspace.project_type.lower())):
                results.append(workspace)
        
        # ブックマークから検索
        for workspace in self.bookmarks.values():
            if workspace not in results:
                if (query_lower in workspace.path.lower() or 
                    (workspace.name and query_lower in workspace.name.lower()) or
                    (workspace.description and query_lower in workspace.description.lower()) or
                    (workspace.project_type and query_lower in workspace.project_type.lower())):
                    results.append(workspace)
        
        return results
    
    def get_workspace_info_display(self) -> str:
        """現在のワークスペース情報を表示用に整形"""
        current = self.get_current_workspace()
        
        display = f"""
📂 **現在の作業フォルダ**

**パス:** {current.path}
**名前:** {current.name or '未設定'}
**種類:** {current.project_type or '不明'}
**アクセス回数:** {current.access_count}回
**最終アクセス:** {current.last_accessed.strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        if current.description:
            display += f"**説明:** {current.description}\n"
        
        # 最近のワークスペース
        recent = self.list_recent_workspaces(5)
        if len(recent) > 1:  # 現在のもの以外にある場合
            display += "\n**最近のワークスペース:**\n"
            for i, workspace in enumerate(recent[1:], 1):  # 現在のものは除く
                project_info = f" ({workspace.project_type})" if workspace.project_type else ""
                display += f"{i}. {workspace.name}{project_info}\n   📁 {workspace.path}\n"
        
        # ブックマーク
        bookmarks = self.list_bookmarks()
        if bookmarks:
            display += "\n**ブックマーク:**\n"
            for bookmark in bookmarks:
                project_info = f" ({bookmark.project_type})" if bookmark.project_type else ""
                display += f"📌 {bookmark.name}{project_info}\n   📁 {bookmark.path}\n"
        
        return display.strip()
    
    def get_workspace_list_display(self) -> str:
        """ワークスペース一覧を表示用に整形"""
        display = "📁 **ワークスペース一覧**\n\n"
        
        # 現在のワークスペース
        current = self.get_current_workspace()
        project_info = f" ({current.project_type})" if current.project_type else ""
        display += f"**📂 現在:** {current.name}{project_info}\n"
        display += f"   {current.path}\n\n"
        
        # 最近のワークスペース
        recent = self.list_recent_workspaces(10)
        if len(recent) > 1:
            display += "**🕒 最近のワークスペース:**\n"
            for i, workspace in enumerate(recent[1:], 1):
                project_info = f" ({workspace.project_type})" if workspace.project_type else ""
                display += f"{i}. {workspace.name}{project_info}\n"
                display += f"   📁 {workspace.path}\n"
                display += f"   🕐 {workspace.last_accessed.strftime('%m-%d %H:%M')}\n\n"
        
        # ブックマーク
        bookmarks = self.list_bookmarks()
        if bookmarks:
            display += "**📌 ブックマーク:**\n"
            for bookmark in bookmarks:
                project_info = f" ({bookmark.project_type})" if bookmark.project_type else ""
                display += f"• {bookmark.name}{project_info}\n"
                display += f"  📁 {bookmark.path}\n"
                if bookmark.description:
                    display += f"  💬 {bookmark.description}\n"
                display += f"  🕐 {bookmark.last_accessed.strftime('%m-%d %H:%M')}\n\n"
        
        return display.strip()
    
    def suggest_similar_paths(self, partial_path: str) -> List[str]:
        """類似パスの候補を提案
        
        Args:
            partial_path: 部分的なパス
            
        Returns:
            List[str]: 候補パス一覧
        """
        suggestions = []
        
        try:
            # 絶対パスの場合
            if os.path.isabs(partial_path):
                base_path = Path(partial_path)
                if base_path.exists() and base_path.is_dir():
                    # サブディレクトリを提案
                    for item in base_path.iterdir():
                        if item.is_dir():
                            suggestions.append(str(item))
                else:
                    # 親ディレクトリが存在する場合、その中から候補を探す
                    parent = base_path.parent
                    if parent.exists():
                        name_start = base_path.name.lower()
                        for item in parent.iterdir():
                            if item.is_dir() and item.name.lower().startswith(name_start):
                                suggestions.append(str(item))
            
            # 相対パスの場合
            else:
                current_path = Path(self.current_workspace)
                target_path = current_path / partial_path
                
                if target_path.exists() and target_path.is_dir():
                    # サブディレクトリを提案
                    for item in target_path.iterdir():
                        if item.is_dir():
                            suggestions.append(str(item.relative_to(current_path)))
                else:
                    # 現在のディレクトリから類似名を探す
                    for item in current_path.iterdir():
                        if item.is_dir() and partial_path.lower() in item.name.lower():
                            suggestions.append(item.name)
            
            # 履歴とブックマークからも候補を探す
            query_lower = partial_path.lower()
            for workspace in self.workspace_history + list(self.bookmarks.values()):
                if query_lower in workspace.path.lower():
                    suggestions.append(workspace.path)
            
            # 重複を除去してソート
            suggestions = list(set(suggestions))
            suggestions.sort()
            
            return suggestions[:10]  # 最大10個の候補
            
        except Exception:
            return []