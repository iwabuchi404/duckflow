"""
ファイル探索ツール - 段階的ファイル発見システム

大規模プロジェクトでも効率的に動作する3レベル探索アーキテクチャ：
- レベル1: ルート + 1階層（即座実行）
- レベル2: 必要時の深掘り探索（ツール実行）  
- レベル3: ripgrepベースのグローバル検索（最終手段）
"""

import os
import subprocess
import glob
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass
import json
import re

from ..ui.rich_ui import rich_ui
from ..base.config import config_manager


@dataclass
class FileDiscoveryResult:
    """ファイル探索結果"""
    files: List[str]
    search_level: int  # 1, 2, 3
    search_method: str
    total_found: int
    truncated: bool = False
    search_time_ms: int = 0


@dataclass  
class FileExplorationContext:
    """ファイル探索コンテキスト"""
    target_patterns: List[str]
    exclude_patterns: List[str] = None
    max_depth: int = 2
    max_files: int = 30
    
    def __post_init__(self):
        if self.exclude_patterns is None:
            self.exclude_patterns = [
                "node_modules", "__pycache__", ".git", ".env", 
                "*.pyc", "*.log", "build", "dist", ".pytest_cache"
            ]


class FileDiscoveryTools:
    """段階的ファイル探索ツールセット"""
    
    def __init__(self):
        """ファイル探索ツールを初期化"""
        self.config = config_manager.load_config()
        
        # ripgrepの利用可能性チェック
        self.ripgrep_available = self._check_ripgrep_availability()
        if self.ripgrep_available:
            rich_ui.print_message("[ファイル探索] ripgrep が利用可能", "info")
        else:
            rich_ui.print_message("[ファイル探索] ripgrep 未検出、fallbackを使用", "warning")
    
    def _check_ripgrep_availability(self) -> bool:
        """ripgrepが利用可能かチェック"""
        try:
            result = subprocess.run(
                ["rg", "--version"], 
                capture_output=True, 
                text=True, 
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def level1_shallow_discovery(
        self, 
        base_path: str = ".", 
        context: Optional[FileExplorationContext] = None
    ) -> FileDiscoveryResult:
        """
        レベル1: ルート + 1階層の高速探索
        
        Args:
            base_path: 探索開始パス
            context: 探索コンテキスト
            
        Returns:
            ファイル探索結果
        """
        if context is None:
            context = FileExplorationContext(
                target_patterns=["*.md", "*.py", "*.json", "*.yaml", "*.yml", "*.txt", "*.cfg"],
                max_files=30,
                max_depth=1
            )
        
        rich_ui.print_message(f"[レベル1探索] 開始: {base_path}", "info")
        
        found_files = []
        search_patterns = []
        
        # ルートレベルのパターン
        for pattern in context.target_patterns:
            search_patterns.append(pattern)
            
        # 1階層サブディレクトリのパターン  
        common_dirs = ["docs", "src", "lib", "config", "tests", "scripts", "tools"]
        for dir_name in common_dirs:
            if os.path.isdir(os.path.join(base_path, dir_name)):
                for pattern in context.target_patterns:
                    search_patterns.append(f"{dir_name}/{pattern}")
        
        # glob実行
        for pattern in search_patterns:
            try:
                matches = glob.glob(os.path.join(base_path, pattern), recursive=False)
                for match in matches:
                    relative_path = os.path.relpath(match, base_path)
                    if self._should_include_file(relative_path, context.exclude_patterns):
                        found_files.append(relative_path)
            except Exception as e:
                rich_ui.print_message(f"[レベル1探索] パターンエラー {pattern}: {e}", "warning")
        
        # 重複除去と制限適用
        unique_files = list(dict.fromkeys(found_files))
        truncated = len(unique_files) > context.max_files
        result_files = unique_files[:context.max_files]
        
        rich_ui.print_message(f"[レベル1探索] 完了: {len(result_files)}ファイル発見", "info")
        
        return FileDiscoveryResult(
            files=result_files,
            search_level=1,
            search_method="shallow_glob",
            total_found=len(unique_files),
            truncated=truncated
        )
    
    def level2_targeted_discovery(
        self,
        target_directory: str,
        file_patterns: List[str],
        max_files: int = 20,
        skip_files: int = 0
    ) -> FileDiscoveryResult:
        """
        レベル2: 特定ディレクトリの深掘り探索（段階的取得対応）
        
        Args:
            target_directory: 対象ディレクトリ
            file_patterns: ファイルパターンリスト
            max_files: 最大ファイル数
            skip_files: スキップするファイル数（2回目以降の呼び出し用）
            
        Returns:
            ファイル探索結果
        """
        rich_ui.print_message(f"[レベル2探索] ターゲット: {target_directory}", "info")
        
        if not os.path.isdir(target_directory):
            return FileDiscoveryResult(
                files=[],
                search_level=2,
                search_method="targeted_discovery", 
                total_found=0
            )
        
        all_found_files = []
        
        # os.walk による深掘り（階層制限なし）
        for root, dirs, files in os.walk(target_directory):
            # 除外ディレクトリのフィルタリング
            exclude_dirs = ['__pycache__', 'node_modules', 'build', 'dist', '.venv', '.env']
            dirs[:] = [d for d in dirs if not (
                d.startswith('.') or d in exclude_dirs
            )]
                
            # ファイルマッチング
            for file in files:
                if any(self._match_pattern(file, pattern) for pattern in file_patterns):
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, ".")
                    all_found_files.append(relative_path)
        
        # ソート（一貫した順序のため）
        all_found_files.sort()
        
        # skip_files分をスキップして、max_files分を取得
        start_index = skip_files
        end_index = skip_files + max_files
        found_files = all_found_files[start_index:end_index]
        
        if skip_files > 0:
            rich_ui.print_message(f"[レベル2探索] {skip_files}ファイルをスキップ、{len(found_files)}ファイルを取得", "info")
        
        # より多くのファイルがあるかチェック
        has_more = end_index < len(all_found_files)
        
        rich_ui.print_message(f"[レベル2探索] 完了: {len(found_files)}ファイル発見", "info")
        
        return FileDiscoveryResult(
            files=found_files,
            search_level=2,
            search_method=f"targeted_discovery_skip_{skip_files}",
            total_found=len(all_found_files),
            truncated=has_more
        )
    
    def level3_ripgrep_discovery(
        self,
        search_query: str,
        file_pattern: Optional[str] = None,
        max_files: int = 10
    ) -> FileDiscoveryResult:
        """
        レベル3: ripgrepベースのグローバル検索
        
        Args:
            search_query: 検索クエリ（ファイル名またはコンテンツ）
            file_pattern: ファイルパターン（例: "*.py"）
            max_files: 最大ファイル数
            
        Returns:
            ファイル探索結果
        """
        rich_ui.print_message(f"[レベル3探索] ripgrepクエリ: {search_query}", "info")
        
        if not self.ripgrep_available:
            return self._fallback_global_search(search_query, file_pattern, max_files)
        
        try:
            # ripgrepコマンド構築
            cmd = ["rg", "--files-with-matches", "--no-heading"]
            
            if file_pattern:
                cmd.extend(["--glob", file_pattern])
            
            # 除外パターン
            exclude_patterns = ["node_modules", "__pycache__", ".git", "build", "dist"]
            for pattern in exclude_patterns:
                cmd.extend(["--glob", f"!{pattern}"])
            
            # 検索実行
            cmd.append(search_query)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd="."
            )
            
            if result.returncode == 0:
                files = [line.strip() for line in result.stdout.split('\n') if line.strip()]
                found_files = files[:max_files]
                
                rich_ui.print_message(f"[レベル3探索] ripgrep完了: {len(found_files)}ファイル発見", "info")
                
                return FileDiscoveryResult(
                    files=found_files,
                    search_level=3,
                    search_method="ripgrep",
                    total_found=len(files),
                    truncated=len(files) > max_files
                )
            else:
                rich_ui.print_message(f"[レベル3探索] ripgrepエラー: {result.stderr}", "warning")
                return self._fallback_global_search(search_query, file_pattern, max_files)
                
        except Exception as e:
            rich_ui.print_message(f"[レベル3探索] ripgrep例外: {e}", "warning")
            return self._fallback_global_search(search_query, file_pattern, max_files)
    
    def _fallback_global_search(
        self,
        search_query: str,
        file_pattern: Optional[str] = None,
        max_files: int = 10
    ) -> FileDiscoveryResult:
        """
        フォールバック: findコマンドを使ったグローバル検索
        
        Args:
            search_query: 検索クエリ
            file_pattern: ファイルパターン
            max_files: 最大ファイル数
            
        Returns:
            ファイル探索結果
        """
        rich_ui.print_message(f"[レベル3探索] findフォールバック: {search_query}", "info")
        
        try:
            # findコマンド構築
            if os.name == 'nt':  # Windows
                # Windows findコマンドは制限があるため、Pythonでフォールバック
                return self._python_fallback_search(search_query, file_pattern, max_files)
            else:
                # Unix系システム
                cmd = ["find", ".", "-type", "f"]
                
                if file_pattern:
                    cmd.extend(["-name", file_pattern])
                else:
                    cmd.extend(["-name", f"*{search_query}*"])
                
                # 除外パターン
                exclude_dirs = ["node_modules", "__pycache__", ".git", "build", "dist"]
                for exclude_dir in exclude_dirs:
                    cmd.extend(["-not", "-path", f"*/{exclude_dir}/*"])
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0:
                    files = [line.strip() for line in result.stdout.split('\n') if line.strip()]
                    found_files = files[:max_files]
                    
                    return FileDiscoveryResult(
                        files=found_files,
                        search_level=3,
                        search_method="find_fallback",
                        total_found=len(files),
                        truncated=len(files) > max_files
                    )
                
        except Exception as e:
            rich_ui.print_message(f"[レベル3探索] findエラー: {e}", "warning")
        
        # 最終フォールバック
        return self._python_fallback_search(search_query, file_pattern, max_files)
    
    def _python_fallback_search(
        self,
        search_query: str,
        file_pattern: Optional[str] = None,
        max_files: int = 10
    ) -> FileDiscoveryResult:
        """
        最終フォールバック: Pythonでのファイル検索
        
        Args:
            search_query: 検索クエリ
            file_pattern: ファイルパターン
            max_files: 最大ファイル数
            
        Returns:
            ファイル探索結果
        """
        rich_ui.print_message(f"[レベル3探索] Pythonフォールバック: {search_query}", "info")
        
        found_files = []
        
        try:
            for root, dirs, files in os.walk("."):
                # 除外ディレクトリ
                dirs[:] = [d for d in dirs if d not in [
                    'node_modules', '__pycache__', '.git', 'build', 'dist', '.env'
                ]]
                
                for file in files:
                    # パターンマッチング
                    matches = False
                    if file_pattern:
                        matches = self._match_pattern(file, file_pattern)
                    else:
                        matches = search_query.lower() in file.lower()
                    
                    if matches:
                        file_path = os.path.join(root, file)
                        relative_path = os.path.relpath(file_path, ".")
                        found_files.append(relative_path)
                        
                        if len(found_files) >= max_files:
                            break
                
                if len(found_files) >= max_files:
                    break
                    
        except Exception as e:
            rich_ui.print_message(f"[レベル3探索] Python検索エラー: {e}", "error")
        
        return FileDiscoveryResult(
            files=found_files[:max_files],
            search_level=3,
            search_method="python_fallback",
            total_found=len(found_files),
            truncated=len(found_files) > max_files
        )
    
    def find_specific_file(self, filename: str) -> FileDiscoveryResult:
        """
        特定ファイル名の検索（全レベル統合）
        
        Args:
            filename: 検索するファイル名
            
        Returns:
            ファイル探索結果
        """
        rich_ui.print_message(f"[統合検索] ファイル検索: {filename}", "info")
        
        # レベル1: 浅い検索
        level1_result = self.level1_shallow_discovery(
            context=FileExplorationContext(
                target_patterns=[filename, f"*{filename}*"],
                max_files=5
            )
        )
        
        if level1_result.files:
            rich_ui.print_message(f"[統合検索] レベル1で発見: {len(level1_result.files)}ファイル", "success")
            return level1_result
        
        # レベル3: ripgrepまたはフォールバック検索
        level3_result = self.level3_ripgrep_discovery(
            search_query=filename,
            max_files=10
        )
        
        if level3_result.files:
            rich_ui.print_message(f"[統合検索] レベル3で発見: {len(level3_result.files)}ファイル", "success") 
            return level3_result
        
        rich_ui.print_message(f"[統合検索] ファイル未発見: {filename}", "warning")
        return FileDiscoveryResult(
            files=[],
            search_level=0,
            search_method="comprehensive_search",
            total_found=0
        )
    
    def _should_include_file(self, file_path: str, exclude_patterns: List[str]) -> bool:
        """
        ファイルを含めるべきかチェック
        
        Args:
            file_path: ファイルパス
            exclude_patterns: 除外パターンリスト
            
        Returns:
            含めるべきかどうか
        """
        file_path_lower = file_path.lower()
        
        for pattern in exclude_patterns:
            if pattern.startswith('*.'):
                # 拡張子パターン
                ext = pattern[2:]
                if file_path_lower.endswith(f'.{ext}'):
                    return False
            elif pattern in file_path_lower:
                # 部分マッチ
                return False
        
        return True
    
    def _match_pattern(self, filename: str, pattern: str) -> bool:
        """
        ファイル名パターンマッチング
        
        Args:
            filename: ファイル名
            pattern: パターン
            
        Returns:
            マッチするかどうか
        """
        if '*' in pattern:
            # glob形式のパターン
            import fnmatch
            return fnmatch.fnmatch(filename, pattern)
        else:
            # 部分マッチ
            return pattern.lower() in filename.lower()


    def level2_iterative_discovery(
        self,
        target_directory: str,
        file_patterns: List[str],
        iteration: int = 1,
        batch_size: int = 20
    ) -> FileDiscoveryResult:
        """
        レベル2の段階的探索（反復実行用）
        
        Args:
            target_directory: 対象ディレクトリ
            file_patterns: ファイルパターンリスト
            iteration: 実行回数（1回目、2回目...）
            batch_size: 1回で取得するファイル数
            
        Returns:
            ファイル探索結果
        """
        skip_files = (iteration - 1) * batch_size
        
        rich_ui.print_message(f"[レベル2段階探索] 第{iteration}回目実行", "info")
        
        return self.level2_targeted_discovery(
            target_directory=target_directory,
            file_patterns=file_patterns,
            max_files=batch_size,
            skip_files=skip_files
        )
    
    def has_more_files_available(
        self,
        target_directory: str,
        file_patterns: List[str],
        current_iteration: int,
        batch_size: int = 20
    ) -> bool:
        """
        さらなるファイルが利用可能かチェック
        
        Args:
            target_directory: 対象ディレクトリ
            file_patterns: ファイルパターンリスト
            current_iteration: 現在の実行回数
            batch_size: バッチサイズ
            
        Returns:
            さらなるファイルがあるかどうか
        """
        # 現在取得済みのファイル数
        files_already_retrieved = current_iteration * batch_size
        
        # 簡単なカウントチェック
        try:
            count = 0
            for root, dirs, files in os.walk(target_directory):
                exclude_dirs = ['__pycache__', 'node_modules', 'build', 'dist', '.venv', '.env']
                dirs[:] = [d for d in dirs if not (
                    d.startswith('.') or d in exclude_dirs
                )]
                
                for file in files:
                    if any(self._match_pattern(file, pattern) for pattern in file_patterns):
                        count += 1
                        # 効率化：必要十分な数が確認できたら早期終了
                        if count > files_already_retrieved:
                            return True
            
            return False
            
        except Exception as e:
            rich_ui.print_message(f"[段階探索チェック] エラー: {e}", "warning")
            return False


# ツールインスタンス
file_discovery_tools = FileDiscoveryTools()