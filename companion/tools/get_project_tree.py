import os
import subprocess
from typing import List, Dict, Optional

DEFAULT_EXCLUDES = [
    'node_modules', 'venv', '__pycache__', '.venv', 'vendor', 'site-packages',
    '.git', '.svn', 'dist', 'build', 'out', 'target', 'bin', 'obj', '.next',
    '.env', '.idea', '.vscode'
]

async def get_project_tree(  # ← async追加
    path: str = '.', 
    depth: int = 3, 
    respect_gitignore: bool = True
) -> str:
    """
    プロジェクトのディレクトリツリーを取得（安全かつ効率的な探索）
    
    Args:
        path: 探索起点パス（デフォルト: カレントディレクトリ）
        depth: 最大探索深度（デフォルト: 3）
        respect_gitignore: .gitignoreを尊重するか（デフォルト: True）
    
    Returns:
        視認性の高いテキストツリー形式の出力
    """
    abs_path = os.path.abspath(path)
    if not os.path.exists(abs_path):
        return f"Error: Path not found - {abs_path}"

    # .gitignore処理
    ignored_files = set()
    if respect_gitignore:
        try:
            result = subprocess.run(
                ['git', 'ls-files', '--others', '--ignored', '--exclude-standard'],
                cwd=abs_path,
                capture_output=True,
                text=True,
                check=False
            )
            ignored_files = set(result.stdout.splitlines())
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass  # gitコマンドがない場合は無視

    # ツリー構築
    def build_tree(current: str, current_depth: int) -> List[str]:
        if current_depth > depth:
            return []
        
        items = []
        try:
            with os.scandir(current) as it:
                for entry in sorted(it, key=lambda e: (not e.is_dir(), e.name.lower())):
                    rel_path = os.path.relpath(entry.path, abs_path)
                    
                    # 除外判定
                    if (
                        entry.name in DEFAULT_EXCLUDES or
                        any(exclude in rel_path.split(os.sep) for exclude in DEFAULT_EXCLUDES) or
                        rel_path in ignored_files
                    ):
                        continue
                    
                    # ディレクトリ処理
                    if entry.is_dir():
                        children = build_tree(entry.path, current_depth + 1)
                        if children:
                            items.append(f"{entry.name}/")
                            items.extend([f"{'  ' * (current_depth)}{child}" for child in children])
                        else:
                            items.append(f"{entry.name}/")
                    # ファイル処理
                    elif current_depth <= depth:
                        items.append(entry.name)
        except PermissionError:
            pass
        
        return items

    tree = build_tree(abs_path, 1)
    return "\n".join(tree) if tree else "No visible files/directories found"