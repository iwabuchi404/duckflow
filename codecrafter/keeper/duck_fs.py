"""
Duck FS - 統合ファイル操作システム

The Duck Keeperの安全なファイルI/O操作を担当する
全てのファイル操作は事前にDuck Policyによる検証を経て実行される
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass
from datetime import datetime
import mimetypes

from .duck_policy import duck_keeper, ValidationResult, PolicyViolation


@dataclass
class FileReadResult:
    """ファイル読み取り結果"""
    content: str                        # 読み取り内容
    path: str                          # ファイルパス
    read_percentage: float             # 読み取り割合 (0.0-1.0)
    total_size_bytes: int              # 総ファイルサイズ
    read_size_bytes: int               # 読み取りサイズ
    file_type: str                     # ファイル種別
    encoding: str                      # 文字エンコーディング
    is_truncated: bool                 # トークン制限により切り詰められたか
    metadata: Dict[str, Any]           # 追加メタデータ
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class FileWriteResult:
    """ファイル書き込み結果"""
    success: bool                      # 成功フラグ
    path: str                         # 書き込み先パス
    bytes_written: int                # 書き込みバイト数
    backup_path: Optional[str]        # バックアップファイルパス
    timestamp: datetime               # 書き込み時刻
    message: str                      # 結果メッセージ
    metadata: Dict[str, Any]          # 追加メタデータ
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class DuckFileSystemError(Exception):
    """Duck FS固有のエラー"""
    pass


class DuckFS:
    """Duck File System - 安全なファイル操作システム
    
    The Duck Keeperのポリシーに基づく、統一されたファイルI/Oインターフェース
    全ての操作は事前に安全性検証を行い、ポリシー違反を防ぐ
    """
    
    def __init__(self):
        """Duck FSを初期化"""
        self.policy = duck_keeper
        self.default_encoding = 'utf-8'
        
    def read(self, path: str) -> FileReadResult:
        """ファイル内容を安全に読み取り
        
        Args:
            path: 読み取り対象のファイルパス
            
        Returns:
            FileReadResult: 読み取り結果オブジェクト
            
        Raises:
            DuckFileSystemError: ポリシー違反またはI/Oエラー
        """
        # ポリシー検証
        validation = self.policy.validate_file_access(path, operation="read")
        if not validation.is_allowed:
            error_msg = self._format_validation_errors(validation)
            raise DuckFileSystemError(f"ファイルアクセス拒否: {error_msg}")
        
        path_obj = Path(validation.sanitized_path)
        
        try:
            # ファイル情報取得
            file_stat = path_obj.stat()
            total_size = file_stat.st_size
            
            # ファイル種別判定
            file_type = self._detect_file_type(path_obj)
            
            # 文字エンコーディング検出
            encoding = self._detect_encoding(path_obj)
            
            # トークン制限に基づく読み取りサイズ計算
            max_tokens = self.policy.get_max_file_read_tokens()
            max_bytes = max_tokens * 4  # 1トークン≈4バイトの概算
            
            should_truncate = total_size > max_bytes
            read_size = min(total_size, max_bytes)
            
            # ファイル読み取り（文字化けに対応）
            with open(path_obj, 'r', encoding=encoding, errors='replace') as f:
                if should_truncate:
                    content = f.read(read_size)
                else:
                    content = f.read()
                    
            # 文字化けが検出された場合はUTF-8で再読み取りを試行
            if '\ufffd' in content and encoding != 'utf-8':
                try:
                    with open(path_obj, 'r', encoding='utf-8', errors='replace') as f:
                        if should_truncate:
                            content = f.read(read_size)
                        else:
                            content = f.read()
                    encoding = 'utf-8'  # 成功した場合はエンコーディングを更新
                except:
                    pass  # 元の内容を使用
            
            actual_read_size = len(content.encode(encoding))
            read_percentage = min(actual_read_size / total_size, 1.0) if total_size > 0 else 1.0
            
            # メタデータ構築
            metadata = {
                'created_time': datetime.fromtimestamp(file_stat.st_ctime),
                'modified_time': datetime.fromtimestamp(file_stat.st_mtime),
                'file_extension': path_obj.suffix,
                'mime_type': mimetypes.guess_type(str(path_obj))[0] or 'unknown',
                'validation_warnings': [v.message for v in validation.violations if v.severity == "warning"]
            }
            
            return FileReadResult(
                content=content,
                path=str(path_obj),
                read_percentage=read_percentage,
                total_size_bytes=total_size,
                read_size_bytes=actual_read_size,
                file_type=file_type,
                encoding=encoding,
                is_truncated=should_truncate,
                metadata=metadata
            )
            
        except Exception as e:
            raise DuckFileSystemError(f"ファイル読み取りエラー {path}: {str(e)}")
    
    def read_range(self, path: str, start_line: int, end_line: int) -> FileReadResult:
        """指定行範囲のファイル内容を読み取り
        
        Args:
            path: 読み取り対象のファイルパス
            start_line: 開始行番号（1から始まる）
            end_line: 終了行番号（包含）
            
        Returns:
            FileReadResult: 読み取り結果オブジェクト
            
        Raises:
            DuckFileSystemError: ポリシー違反またはI/Oエラー
        """
        # ポリシー検証
        validation = self.policy.validate_file_access(path, operation="read")
        if not validation.is_allowed:
            error_msg = self._format_validation_errors(validation)
            raise DuckFileSystemError(f"ファイルアクセス拒否: {error_msg}")
        
        path_obj = Path(validation.sanitized_path)
        
        try:
            # パラメータ検証
            if start_line < 1 or end_line < start_line:
                raise DuckFileSystemError(f"不正な行範囲指定: {start_line}-{end_line}")
            
            # ファイル情報取得
            file_stat = path_obj.stat()
            encoding = self._detect_encoding(path_obj)
            
            # 行範囲読み取り
            selected_lines = []
            total_lines = 0
            
            with open(path_obj, 'r', encoding=encoding, errors='replace') as f:
                for line_num, line in enumerate(f, 1):
                    total_lines = line_num
                    if start_line <= line_num <= end_line:
                        selected_lines.append(line.rstrip('\n\r'))
                    elif line_num > end_line:
                        break
            
            content = '\n'.join(selected_lines)
            actual_end_line = min(end_line, total_lines)
            read_percentage = (actual_end_line - start_line + 1) / total_lines if total_lines > 0 else 0.0
            
            # メタデータ構築
            metadata = {
                'start_line': start_line,
                'end_line': actual_end_line,
                'total_lines': total_lines,
                'lines_read': len(selected_lines),
                'file_extension': path_obj.suffix,
                'validation_warnings': [v.message for v in validation.violations if v.severity == "warning"]
            }
            
            return FileReadResult(
                content=content,
                path=str(path_obj),
                read_percentage=read_percentage,
                total_size_bytes=file_stat.st_size,
                read_size_bytes=len(content.encode(encoding)),
                file_type=self._detect_file_type(path_obj),
                encoding=encoding,
                is_truncated=actual_end_line < end_line,
                metadata=metadata
            )
            
        except Exception as e:
            raise DuckFileSystemError(f"範囲読み取りエラー {path}: {str(e)}")
    
    def get_summary(self, path: str) -> FileReadResult:
        """大型ファイルの構造と概要を効率的に取得
        
        Args:
            path: 対象ファイルパス
            
        Returns:
            FileReadResult: 要約結果オブジェクト
            
        Raises:
            DuckFileSystemError: ポリシー違反またはI/Oエラー
        """
        # ポリシー検証
        validation = self.policy.validate_file_access(path, operation="read")
        if not validation.is_allowed:
            error_msg = self._format_validation_errors(validation)
            raise DuckFileSystemError(f"ファイルアクセス拒否: {error_msg}")
        
        path_obj = Path(validation.sanitized_path)
        
        try:
            file_stat = path_obj.stat()
            file_type = self._detect_file_type(path_obj)
            encoding = self._detect_encoding(path_obj)
            
            # ファイル種別に応じた要約戦略
            if file_type == "source_code":
                summary_content = self._summarize_source_code(path_obj, encoding)
            elif file_type == "json":
                summary_content = self._summarize_json_file(path_obj, encoding)
            elif file_type == "log":
                summary_content = self._summarize_log_file(path_obj, encoding)
            elif file_type == "document":
                summary_content = self._summarize_document(path_obj, encoding)
            else:
                summary_content = self._summarize_generic_file(path_obj, encoding)
            
            # メタデータ構築
            metadata = {
                'summary_type': f"{file_type}_summary",
                'original_size_bytes': file_stat.st_size,
                'compression_ratio': len(summary_content) / file_stat.st_size if file_stat.st_size > 0 else 0,
                'file_extension': path_obj.suffix,
                'validation_warnings': [v.message for v in validation.violations if v.severity == "warning"]
            }
            
            return FileReadResult(
                content=summary_content,
                path=str(path_obj),
                read_percentage=1.0,  # 要約は全体を対象とする
                total_size_bytes=file_stat.st_size,
                read_size_bytes=len(summary_content.encode(encoding)),
                file_type=file_type,
                encoding=encoding,
                is_truncated=False,
                metadata=metadata
            )
            
        except Exception as e:
            raise DuckFileSystemError(f"要約生成エラー {path}: {str(e)}")
    
    def write(self, path: str, content: str, backup: bool = True) -> FileWriteResult:
        """ファイルに内容を安全に書き込み
        
        Args:
            path: 書き込み先ファイルパス
            content: 書き込む内容
            backup: 既存ファイルのバックアップを作成するか
            
        Returns:
            FileWriteResult: 書き込み結果オブジェクト
            
        Raises:
            DuckFileSystemError: ポリシー違反またはI/Oエラー
        """
        # ポリシー検証
        validation = self.policy.validate_file_access(path, operation="write")
        if not validation.is_allowed:
            error_msg = self._format_validation_errors(validation)
            raise DuckFileSystemError(f"ファイル書き込み拒否: {error_msg}")
        
        path_obj = Path(validation.sanitized_path)
        backup_path = None
        
        try:
            # 既存ファイルのバックアップ作成
            if backup and path_obj.exists():
                backup_path = self._create_backup(path_obj)
            
            # ディレクトリの作成（必要に応じて）
            path_obj.parent.mkdir(parents=True, exist_ok=True)
            
            # ファイル書き込み
            encoding = self._detect_encoding(path_obj) if path_obj.exists() else self.default_encoding
            with open(path_obj, 'w', encoding=encoding) as f:
                f.write(content)
            
            bytes_written = len(content.encode(encoding))
            
            return FileWriteResult(
                success=True,
                path=str(path_obj),
                bytes_written=bytes_written,
                backup_path=backup_path,
                timestamp=datetime.now(),
                message=f"ファイル書き込み成功: {bytes_written}バイト",
                metadata={
                    'encoding': encoding,
                    'backup_created': backup_path is not None,
                    'validation_warnings': [v.message for v in validation.violations if v.severity == "warning"]
                }
            )
            
        except Exception as e:
            raise DuckFileSystemError(f"ファイル書き込みエラー {path}: {str(e)}")
    
    def _detect_file_type(self, path: Path) -> str:
        """ファイル種別の自動検出"""
        suffix = path.suffix.lower()
        
        # ソースコード
        source_extensions = {'.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.h', 
                           '.cs', '.php', '.rb', '.go', '.rs', '.scala', '.kt'}
        if suffix in source_extensions:
            return "source_code"
        
        # データ形式
        if suffix == '.json':
            return "json"
        elif suffix in {'.yaml', '.yml'}:
            return "yaml"
        elif suffix == '.csv':
            return "csv"
        elif suffix in {'.xml', '.html', '.htm'}:
            return "markup"
        
        # ドキュメント
        if suffix in {'.md', '.txt', '.rst'}:
            return "document"
        
        # ログファイル
        if suffix == '.log' or 'log' in path.name.lower():
            return "log"
        
        # 設定ファイル  
        if suffix in {'.ini', '.cfg', '.conf', '.toml'}:
            return "config"
        
        return "text"
    
    def _detect_encoding(self, path: Path) -> str:
        """文字エンコーディングの自動検出"""
        try:
            import chardet
            with open(path, 'rb') as f:
                raw_data = f.read(8192)  # 先頭8KBをサンプリング
            result = chardet.detect(raw_data)
            return result.get('encoding', self.default_encoding) or self.default_encoding
        except ImportError:
            # chardetが利用できない場合のフォールバック
            return self._detect_encoding_fallback(path)
        except Exception:
            return self.default_encoding
    
    def _detect_encoding_fallback(self, path: Path) -> str:
        """chardetが使えない場合のエンコーディング判定"""
        import platform
        
        # Windows環境でのエンコーディング推測
        if platform.system() == 'Windows':
            # よく使われるエンコーディングの順番で試行
            encodings = ['utf-8', 'cp932', 'shift_jis', 'utf-8-sig']
        else:
            import locale
            encodings = ['utf-8', 'utf-8-sig', locale.getpreferredencoding()]
        
        for encoding in encodings:
            if encoding is None:
                continue
            try:
                with open(path, 'r', encoding=encoding, errors='replace') as f:
                    content = f.read(100)  # 最初の100文字を試し読み
                    # 置換文字が含まれていない場合は成功とみなす
                    if '\ufffd' not in content:
                        return encoding
            except (UnicodeDecodeError, UnicodeError):
                continue
        
        # すべて失敗した場合はUTF-8を返す（errors='replace'で読み取り保証）
        return self.default_encoding
    
    def _create_backup(self, path: Path) -> str:
        """既存ファイルのバックアップを作成"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = path.with_suffix(f"{path.suffix}.backup_{timestamp}")
        
        import shutil
        shutil.copy2(path, backup_path)
        
        return str(backup_path)
    
    def _format_validation_errors(self, validation: ValidationResult) -> str:
        """検証エラーを読みやすい形式にフォーマット"""
        error_messages = []
        for violation in validation.violations:
            if violation.severity == "error":
                error_messages.append(f"{violation.violation_type}: {violation.message}")
        
        return "; ".join(error_messages) if error_messages else "不明なエラー"
    
    def _summarize_source_code(self, path: Path, encoding: str) -> str:
        """ソースコードファイルの構造要約"""
        try:
            with open(path, 'r', encoding=encoding, errors='replace') as f:
                lines = f.readlines()
            
            summary_parts = []
            summary_parts.append(f"=== {path.name} 構造要約 ===")
            summary_parts.append(f"総行数: {len(lines)}")
            summary_parts.append(f"ファイル種別: {path.suffix} ソースコード")
            summary_parts.append("")
            
            # 関数・クラス定義の抽出（シンプル版）
            functions = []
            classes = []
            imports = []
            
            for i, line in enumerate(lines[:200], 1):  # 先頭200行を分析
                line = line.strip()
                if line.startswith('def ') and ':' in line:
                    functions.append(f"L{i}: {line}")
                elif line.startswith('class ') and ':' in line:
                    classes.append(f"L{i}: {line}")
                elif line.startswith(('import ', 'from ')) and len(imports) < 10:
                    imports.append(f"L{i}: {line}")
            
            if imports:
                summary_parts.append("主要インポート:")
                summary_parts.extend(imports[:5])
                summary_parts.append("")
            
            if classes:
                summary_parts.append("クラス定義:")
                summary_parts.extend(classes)
                summary_parts.append("")
            
            if functions:
                summary_parts.append("関数定義:")
                summary_parts.extend(functions[:10])
                summary_parts.append("")
            
            # 先頭と末尾の数行を含める
            summary_parts.append("=== ファイル先頭 (10行) ===")
            summary_parts.extend([f"L{i}: {line.rstrip()}" for i, line in enumerate(lines[:10], 1)])
            
            if len(lines) > 20:
                summary_parts.append("")
                summary_parts.append("=== ファイル末尾 (5行) ===")
                summary_parts.extend([f"L{len(lines)-4+i}: {line.rstrip()}" 
                                    for i, line in enumerate(lines[-5:])])
            
            return '\n'.join(summary_parts)
            
        except Exception as e:
            return f"ソースコード要約エラー: {str(e)}"
    
    def _summarize_json_file(self, path: Path, encoding: str) -> str:
        """JSONファイルの構造要約"""
        try:
            with open(path, 'r', encoding=encoding) as f:
                data = json.load(f)
            
            summary_parts = []
            summary_parts.append(f"=== {path.name} JSON構造要約 ===")
            
            if isinstance(data, dict):
                summary_parts.append(f"オブジェクト型 - キー数: {len(data)}")
                summary_parts.append("主要キー:")
                for key in list(data.keys())[:10]:
                    value_type = type(data[key]).__name__
                    summary_parts.append(f"  {key}: {value_type}")
            elif isinstance(data, list):
                summary_parts.append(f"配列型 - 要素数: {len(data)}")
                if data:
                    first_item_type = type(data[0]).__name__
                    summary_parts.append(f"要素型: {first_item_type}")
            
            # JSONの一部を表示
            json_preview = json.dumps(data, ensure_ascii=False, indent=2)
            if len(json_preview) > 1000:
                json_preview = json_preview[:1000] + "..."
            
            summary_parts.append("")
            summary_parts.append("=== JSON内容プレビュー ===")
            summary_parts.append(json_preview)
            
            return '\n'.join(summary_parts)
            
        except Exception as e:
            return f"JSON要約エラー: {str(e)}"
    
    def _summarize_log_file(self, path: Path, encoding: str) -> str:
        """ログファイルの統計要約"""
        try:
            with open(path, 'r', encoding=encoding, errors='replace') as f:
                lines = f.readlines()
            
            summary_parts = []
            summary_parts.append(f"=== {path.name} ログ要約 ===")
            summary_parts.append(f"総行数: {len(lines)}")
            
            # ログレベル統計
            log_levels = {'ERROR': 0, 'WARN': 0, 'INFO': 0, 'DEBUG': 0}
            for line in lines[:1000]:  # 最初の1000行を分析
                line_upper = line.upper()
                for level in log_levels:
                    if level in line_upper:
                        log_levels[level] += 1
                        break
            
            summary_parts.append("")
            summary_parts.append("ログレベル統計:")
            for level, count in log_levels.items():
                if count > 0:
                    summary_parts.append(f"  {level}: {count}件")
            
            # 先頭と末尾
            summary_parts.append("")
            summary_parts.append("=== 先頭10行 ===")
            summary_parts.extend(lines[:10])
            
            if len(lines) > 20:
                summary_parts.append("")
                summary_parts.append("=== 末尾5行 ===")
                summary_parts.extend(lines[-5:])
            
            return ''.join(summary_parts).rstrip()
            
        except Exception as e:
            return f"ログ要約エラー: {str(e)}"
    
    def _summarize_document(self, path: Path, encoding: str) -> str:
        """ドキュメントファイルの要約"""
        try:
            with open(path, 'r', encoding=encoding, errors='replace') as f:
                content = f.read()
            
            lines = content.split('\n')
            
            summary_parts = []
            summary_parts.append(f"=== {path.name} ドキュメント要約 ===")
            summary_parts.append(f"総行数: {len(lines)}")
            summary_parts.append(f"文字数: {len(content)}")
            summary_parts.append("")
            
            # Markdownのヘッダー抽出
            if path.suffix.lower() == '.md':
                headers = []
                for i, line in enumerate(lines[:100], 1):
                    line = line.strip()
                    if line.startswith('#'):
                        headers.append(f"L{i}: {line}")
                
                if headers:
                    summary_parts.append("見出し構造:")
                    summary_parts.extend(headers)
                    summary_parts.append("")
            
            # 先頭部分
            summary_parts.append("=== 内容プレビュー（先頭1000文字） ===")
            preview = content[:1000]
            if len(content) > 1000:
                preview += "..."
            summary_parts.append(preview)
            
            return '\n'.join(summary_parts)
            
        except Exception as e:
            return f"ドキュメント要約エラー: {str(e)}"
    
    def _summarize_generic_file(self, path: Path, encoding: str) -> str:
        """汎用ファイルの基本要約"""
        try:
            with open(path, 'r', encoding=encoding, errors='replace') as f:
                content = f.read(2000)  # 先頭2KB
            
            file_stat = path.stat()
            
            summary_parts = []
            summary_parts.append(f"=== {path.name} ファイル要約 ===")
            summary_parts.append(f"ファイルサイズ: {file_stat.st_size}バイト")
            summary_parts.append(f"エンコーディング: {encoding}")
            summary_parts.append("")
            summary_parts.append("=== 内容プレビュー ===")
            summary_parts.append(content)
            
            if file_stat.st_size > 2000:
                summary_parts.append("...")
                summary_parts.append(f"(残り{file_stat.st_size - len(content)}バイト)")
            
            return '\n'.join(summary_parts)
            
        except Exception as e:
            return f"汎用要約エラー: {str(e)}"


# グローバルインスタンス
duck_fs = DuckFS()