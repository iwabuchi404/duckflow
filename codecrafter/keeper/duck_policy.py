"""
Duck Keeper Policy - アクセスポリシー管理システム

The Duck Keeperの核となるポリシー管理とセキュリティ検証を担当
"""

import os
import fnmatch
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
import yaml

from ..base.config import config_manager


@dataclass
class PolicyViolation:
    """ポリシー違反情報"""
    path: str
    violation_type: str
    message: str
    severity: str  # "error", "warning", "info"


@dataclass
class ValidationResult:
    """ファイルアクセス検証結果"""
    is_allowed: bool
    path: str
    violations: List[PolicyViolation]
    sanitized_path: Optional[str] = None


class DuckKeeperPolicy:
    """The Duck Keeperのアクセスポリシー管理
    
    全てのファイルシステム操作に対する統一されたセキュリティポリシーを管理し、
    アクセス許可の検証を行う賢明な管理人システム
    """
    
    def __init__(self):
        """ポリシー管理システムを初期化"""
        self.config = config_manager.load_config()
        self._load_policy_settings()
        self._workspace_root = self._detect_workspace_root()
        self._gitignore_patterns = self._load_gitignore_patterns()
    
    def _load_policy_settings(self) -> None:
        """設定ファイルからポリシー設定を読み込み"""
        # Duck Keeper設定を取得
        duck_keeper_config = self.config.duck_keeper
        
        # 設定を辞書形式で保持（既存コードとの互換性のため）
        self.policy = {
            'allowed_extensions': duck_keeper_config.allowed_extensions,
            'directory_blacklist': duck_keeper_config.directory_blacklist,
            'enforce_workspace_boundary': duck_keeper_config.enforce_workspace_boundary,
            'respect_gitignore': duck_keeper_config.respect_gitignore,
            'max_file_read_tokens': duck_keeper_config.max_file_read_tokens
        }
    
    def _detect_workspace_root(self) -> Path:
        """プロジェクトのワークスペースルートを検出"""
        current_path = Path.cwd()
        
        # 上位ディレクトリを探索して.gitやpyproject.tomlを探す
        for parent in [current_path] + list(current_path.parents):
            if (parent / '.git').exists() or \
               (parent / 'pyproject.toml').exists() or \
               (parent / 'setup.py').exists() or \
               (parent / 'package.json').exists():
                return parent
        
        # 見つからない場合は現在のディレクトリを使用
        return current_path
    
    def _load_gitignore_patterns(self) -> Set[str]:
        """.gitignoreファイルからパターンを読み込み"""
        patterns = set()
        
        if not self.policy.get('respect_gitignore', True):
            return patterns
        
        gitignore_path = self._workspace_root / '.gitignore'
        if gitignore_path.exists():
            try:
                with open(gitignore_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            patterns.add(line)
            except Exception as e:
                print(f"[DUCK_KEEPER] .gitignore読み込みエラー: {e}")
        
        return patterns
    
    def validate_file_access(self, file_path: str, operation: str = "read") -> ValidationResult:
        """ファイルアクセスの総合的な検証
        
        Args:
            file_path: 検証対象のファイルパス
            operation: 操作種別 ("read", "write", "scan")
            
        Returns:
            ValidationResult: 検証結果
        """
        violations = []
        path_obj = Path(file_path).resolve()
        
        # 1. ワークスペース境界チェック
        if self.policy.get('enforce_workspace_boundary', True):
            if not self._is_within_workspace(path_obj):
                violations.append(PolicyViolation(
                    path=str(path_obj),
                    violation_type="workspace_boundary",
                    message=f"ファイルがワークスペース外です: {path_obj}",
                    severity="error"
                ))
        
        # 2. 拡張子ホワイトリストチェック
        if not self._is_extension_allowed(path_obj):
            violations.append(PolicyViolation(
                path=str(path_obj),
                violation_type="extension_blocked",
                message=f"許可されていない拡張子です: {path_obj.suffix}",
                severity="error"
            ))
        
        # 3. ディレクトリブラックリストチェック
        if self._is_directory_blacklisted(path_obj):
            violations.append(PolicyViolation(
                path=str(path_obj),
                violation_type="directory_blacklisted",
                message=f"ブラックリストディレクトリです: {path_obj.parent}",
                severity="error"
            ))
        
        # 4. .gitignoreパターンチェック
        if self._is_gitignored(path_obj):
            violations.append(PolicyViolation(
                path=str(path_obj),
                violation_type="gitignored",
                message=f".gitignoreで除外されています: {path_obj}",
                severity="warning"
            ))
        
        # 5. ファイル存在チェック（読み取り操作の場合）
        if operation == "read" and not path_obj.exists():
            violations.append(PolicyViolation(
                path=str(path_obj),
                violation_type="file_not_found",
                message=f"ファイルが存在しません: {path_obj}",
                severity="error"
            ))
        
        # エラーレベルの違反がある場合はアクセス拒否
        error_violations = [v for v in violations if v.severity == "error"]
        is_allowed = len(error_violations) == 0
        
        return ValidationResult(
            is_allowed=is_allowed,
            path=str(path_obj),
            violations=violations,
            sanitized_path=str(path_obj) if is_allowed else None
        )
    
    def _is_within_workspace(self, path: Path) -> bool:
        """ファイルがワークスペース内にあるかチェック"""
        try:
            path.resolve().relative_to(self._workspace_root.resolve())
            return True
        except ValueError:
            return False
    
    def _is_extension_allowed(self, path: Path) -> bool:
        """拡張子がホワイトリストに含まれているかチェック"""
        allowed_extensions = self.policy.get('allowed_extensions', [])
        if not allowed_extensions:  # ホワイトリストが空の場合は全て許可
            return True
        
        return path.suffix.lower() in [ext.lower() for ext in allowed_extensions]
    
    def _is_directory_blacklisted(self, path: Path) -> bool:
        """ディレクトリがブラックリストに含まれているかチェック"""
        blacklist = self.policy.get('directory_blacklist', [])
        if not blacklist:
            return False
        
        # パスの全ての親ディレクトリをチェック
        for parent in path.parents:
            if parent.name in blacklist:
                return True
        
        # ファイルが直接ブラックリストディレクトリにある場合もチェック
        if path.parent.name in blacklist:
            return True
        
        return False
    
    def _is_gitignored(self, path: Path) -> bool:
        """.gitignoreパターンにマッチするかチェック"""
        if not self._gitignore_patterns:
            return False
        
        # ワークスペースルートからの相対パスを取得
        try:
            relative_path = path.resolve().relative_to(self._workspace_root.resolve())
            relative_str = str(relative_path).replace('\\', '/')
            
            # パターンマッチング
            for pattern in self._gitignore_patterns:
                if fnmatch.fnmatch(relative_str, pattern) or \
                   fnmatch.fnmatch(path.name, pattern):
                    return True
            
        except ValueError:
            # ワークスペース外のファイルの場合
            pass
        
        return False
    
    def get_allowed_extensions(self) -> List[str]:
        """許可された拡張子一覧を取得"""
        return self.policy.get('allowed_extensions', [])
    
    def get_max_file_read_tokens(self) -> int:
        """ファイル読み取り最大トークン数を取得"""
        return self.policy.get('max_file_read_tokens', 8000)
    
    def get_workspace_root(self) -> Path:
        """ワークスペースルートパスを取得"""
        return self._workspace_root
    
    def is_safe_for_bulk_operations(self, paths: List[str]) -> Dict[str, ValidationResult]:
        """複数ファイルの一括検証"""
        results = {}
        for path in paths:
            results[path] = self.validate_file_access(path)
        return results


# グローバルインスタンス
duck_keeper = DuckKeeperPolicy()