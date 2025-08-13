"""
Duck Scan - インテリジェント探索ツール群

The Duck Keeperのアクセスポリシーに従い、
「どこを探すべきか」というファイル候補リストを安全かつ効率的に生成する
"""

import os
import subprocess
import fnmatch
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass
from datetime import datetime

from ..keeper import duck_keeper, DuckFileSystemError
from ..ui.rich_ui import rich_ui


@dataclass
class ScanResult:
    """スキャン結果"""
    files: List[str]                    # 発見されたファイルパス一覧
    scan_method: str                    # 使用されたスキャン手法
    query: Optional[str]                # 検索クエリ（該当する場合）
    total_files_found: int              # 発見総数
    filtered_files_count: int           # フィルタリング後の数
    scan_time_seconds: float            # スキャン実行時間
    workspace_root: str                 # ワークスペースルート
    metadata: Dict[str, Any]            # 追加メタデータ


class DuckScanError(Exception):
    """Duck Scan固有のエラー"""
    pass


class DuckScan:
    """Duck Scan - プロジェクト探索システム
    
    The Duck Keeperのポリシーに基づく、統合的なファイル探索ツール
    ripgrep → 階層的スキャン → 最終フィルタリングのパイプラインで動作
    """
    
    def __init__(self):
        """Duck Scanを初期化"""
        self.policy = duck_keeper
        self.workspace_root = self.policy.get_workspace_root()
        self.config = self.policy.config.duck_keeper.scan_settings
        
    def scan_workspace(self, query: str) -> ScanResult:
        """プロジェクト全体を対象とした統合的な初期探索
        
        Args:
            query: 検索クエリ（キーワード、ファイル名パターンなど）
            
        Returns:
            ScanResult: スキャン結果オブジェクト
            
        Raises:
            DuckScanError: スキャン実行エラー
        """
        start_time = datetime.now()
        
        try:
            rich_ui.print_step(f"[Duck Scan] ワークスペース探索開始: '{query}'")
            
            # 1. キーワード検索（ripgrep使用）
            ripgrep_files = self._ripgrep_search(query)
            
            # 2. ファイル名パターン検索
            pattern_files = self._pattern_search(query)
            
            # 3. 階層的スキャン（フォールバック）
            hierarchical_files = []
            if not ripgrep_files and not pattern_files:
                hierarchical_files = self._hierarchical_scan(query)
            
            # 4. 結果統合
            all_files = set(ripgrep_files + pattern_files + hierarchical_files)
            
            # 5. Duck Keeperポリシーによる最終フィルタリング
            filtered_files = self._apply_duck_keeper_filtering(list(all_files))
            
            # 6. 優先順位付け
            prioritized_files = self._prioritize_files(filtered_files, query)
            
            scan_time = (datetime.now() - start_time).total_seconds()
            
            # 使用されたスキャン手法を決定
            if ripgrep_files:
                scan_method = "ripgrep_content_search"
            elif pattern_files:
                scan_method = "filename_pattern_search"
            elif hierarchical_files:
                scan_method = "hierarchical_fallback_scan"
            else:
                scan_method = "no_results"
            
            result = ScanResult(
                files=prioritized_files,
                scan_method=scan_method,
                query=query,
                total_files_found=len(all_files),
                filtered_files_count=len(filtered_files),
                scan_time_seconds=scan_time,
                workspace_root=str(self.workspace_root),
                metadata={
                    'ripgrep_results': len(ripgrep_files),
                    'pattern_results': len(pattern_files),
                    'hierarchical_results': len(hierarchical_files),
                    'policy_violations_filtered': len(all_files) - len(filtered_files)
                }
            )
            
            rich_ui.print_success(f"[Duck Scan] 完了: {len(prioritized_files)}ファイル発見 ({scan_time:.2f}秒)")
            
            return result
            
        except Exception as e:
            raise DuckScanError(f"ワークスペーススキャンエラー: {str(e)}")
    
    def scan_directory(self, path: str, recursive: bool = False) -> ScanResult:
        """特定ディレクトリの安全なリストアップ
        
        Args:
            path: スキャン対象ディレクトリパス
            recursive: 再帰的スキャンを行うか
            
        Returns:
            ScanResult: スキャン結果オブジェクト
            
        Raises:
            DuckScanError: スキャン実行エラー
        """
        start_time = datetime.now()
        
        try:
            rich_ui.print_step(f"[Duck Scan] ディレクトリスキャン: {path} (recursive={recursive})")
            
            # ディレクトリパスの検証
            dir_path = Path(path).resolve()
            if not dir_path.exists():
                raise DuckScanError(f"ディレクトリが存在しません: {path}")
            
            if not dir_path.is_dir():
                raise DuckScanError(f"パスがディレクトリではありません: {path}")
            
            # Duck Keeperポリシーによる事前チェック
            validation = self.policy.validate_file_access(str(dir_path), operation="scan")
            if not validation.is_allowed:
                error_violations = [v for v in validation.violations if v.severity == "error"]
                if error_violations:
                    raise DuckScanError(f"ディレクトリアクセス拒否: {error_violations[0].message}")
            
            # ファイル収集
            all_files = []
            
            if recursive:
                # 再帰的スキャン
                max_depth = self.config.max_scan_depth
                for root, dirs, files in os.walk(dir_path):
                    # 深度制限チェック
                    current_depth = len(Path(root).relative_to(dir_path).parts)
                    if current_depth > max_depth:
                        dirs.clear()  # これ以上深く進まない
                        continue
                    
                    # ディレクトリフィルタリング
                    dirs[:] = [d for d in dirs if not self._is_directory_filtered(Path(root) / d)]
                    
                    # ファイル追加
                    for file in files:
                        file_path = Path(root) / file
                        all_files.append(str(file_path))
            else:
                # 非再帰的スキャン
                try:
                    for item in dir_path.iterdir():
                        if item.is_file():
                            all_files.append(str(item))
                except PermissionError:
                    raise DuckScanError(f"ディレクトリアクセス権限がありません: {path}")
            
            # Duck Keeperポリシーによる最終フィルタリング
            filtered_files = self._apply_duck_keeper_filtering(all_files)
            
            scan_time = (datetime.now() - start_time).total_seconds()
            
            result = ScanResult(
                files=filtered_files,
                scan_method="directory_scan_recursive" if recursive else "directory_scan_flat",
                query=None,
                total_files_found=len(all_files),
                filtered_files_count=len(filtered_files),
                scan_time_seconds=scan_time,
                workspace_root=str(self.workspace_root),
                metadata={
                    'target_directory': str(dir_path),
                    'recursive': recursive,
                    'max_depth_used': self.config.max_scan_depth if recursive else 1
                }
            )
            
            rich_ui.print_success(f"[Duck Scan] ディレクトリスキャン完了: {len(filtered_files)}ファイル ({scan_time:.2f}秒)")
            
            return result
            
        except Exception as e:
            raise DuckScanError(f"ディレクトリスキャンエラー: {str(e)}")
    
    def _ripgrep_search(self, query: str) -> List[str]:
        """ripgrepを使用した高速コンテンツ検索"""
        if not self.config.use_ripgrep:
            return []
        
        try:
            # ripgrepコマンドの構築
            cmd = [
                'rg',
                '--files-with-matches',  # マッチしたファイル名のみ出力
                '--no-heading',
                '--no-line-number',
                '--max-count', '1',  # ファイルごとに最初のマッチのみ
                '--timeout', str(self.config.search_timeout),
            ]
            
            # 許可された拡張子のみを対象とする
            allowed_extensions = self.policy.get_allowed_extensions()
            if allowed_extensions:
                for ext in allowed_extensions:
                    cmd.extend(['--glob', f'*{ext}'])
            
            # ブラックリストディレクトリを除外
            blacklist = self.policy.policy.get('directory_blacklist', [])
            for dir_name in blacklist:
                cmd.extend(['--glob', f'!{dir_name}/**'])
            
            # 検索クエリを追加
            cmd.append(query)
            cmd.append(str(self.workspace_root))
            
            # ripgrep実行
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.search_timeout,
                cwd=self.workspace_root
            )
            
            if result.returncode == 0:
                files = [line.strip() for line in result.stdout.split('\n') if line.strip()]
                return files[:self.config.max_search_results]
            
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
            # ripgrepが利用できない場合は空リストを返す
            pass
        
        return []
    
    def _pattern_search(self, query: str) -> List[str]:
        """ファイル名パターンによる検索"""
        files = []
        
        try:
            # ワイルドカードパターンとして解釈
            patterns = [
                f"*{query}*",
                f"{query}*",
                f"*{query}",
                query
            ]
            
            for root, dirs, filenames in os.walk(self.workspace_root):
                # ディレクトリフィルタリング
                dirs[:] = [d for d in dirs if not self._is_directory_filtered(Path(root) / d)]
                
                for filename in filenames:
                    for pattern in patterns:
                        if fnmatch.fnmatch(filename.lower(), pattern.lower()):
                            file_path = Path(root) / filename
                            files.append(str(file_path))
                            break
                
                # 結果数制限
                if len(files) >= self.config.max_search_results:
                    break
            
        except Exception:
            pass
        
        return files
    
    def _hierarchical_scan(self, query: str) -> List[str]:
        """階層的フォールバックスキャン"""
        files = []
        
        try:
            # ルートレベルから段階的にスキャン
            for depth in range(min(3, self.config.max_scan_depth)):
                level_files = self._scan_at_depth(depth)
                files.extend(level_files)
                
                # 十分な結果が得られた場合は終了
                if len(files) >= 20:
                    break
            
        except Exception:
            pass
        
        return files[:self.config.max_search_results]
    
    def _scan_at_depth(self, depth: int) -> List[str]:
        """指定深度でのファイルスキャン"""
        files = []
        
        for root, dirs, filenames in os.walk(self.workspace_root):
            current_depth = len(Path(root).relative_to(self.workspace_root).parts)
            
            if current_depth == depth:
                # ディレクトリフィルタリング
                dirs[:] = [d for d in dirs if not self._is_directory_filtered(Path(root) / d)]
                
                for filename in filenames:
                    file_path = Path(root) / filename
                    files.append(str(file_path))
            elif current_depth > depth:
                dirs.clear()  # これ以上深く進まない
        
        return files
    
    def _apply_duck_keeper_filtering(self, files: List[str]) -> List[str]:
        """Duck Keeperポリシーによる最終フィルタリング"""
        filtered_files = []
        
        for file_path in files:
            validation = self.policy.validate_file_access(file_path, operation="read")
            if validation.is_allowed:
                filtered_files.append(file_path)
        
        return filtered_files
    
    def _is_directory_filtered(self, dir_path: Path) -> bool:
        """ディレクトリがフィルタリング対象かチェック"""
        blacklist = self.policy.policy.get('directory_blacklist', [])
        return dir_path.name in blacklist
    
    def _prioritize_files(self, files: List[str], query: str) -> List[str]:
        """ファイルの優先順位付け"""
        if not files:
            return files
        
        # 優先度スコア計算
        scored_files = []
        query_lower = query.lower()
        
        for file_path in files:
            path_obj = Path(file_path)
            score = 0
            
            # ファイル名マッチ
            if query_lower in path_obj.name.lower():
                score += 10
            
            # 拡張子による優先度
            if path_obj.suffix in ['.py', '.md', '.json']:
                score += 5
            
            # ルートに近いファイルを優先
            depth = len(path_obj.relative_to(self.workspace_root).parts)
            score += max(0, 10 - depth)
            
            # ファイルサイズ（適度なサイズを優先）
            try:
                size = path_obj.stat().st_size
                if 100 < size < 50000:  # 100B - 50KB
                    score += 3
            except:
                pass
            
            scored_files.append((score, file_path))
        
        # スコア順でソート
        scored_files.sort(key=lambda x: x[0], reverse=True)
        
        return [file_path for score, file_path in scored_files]


# グローバルインスタンス
duck_scan = DuckScan()