#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
StructuredFileOps - シンプルなファイル操作ツール

設計思想:
- シンプルな辞書入出力
- 他のツールと同じ呼び出しパターン
- エラーハンドリングの統一
"""

import os
import time
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

# 既存の承認システムを活用
from ..simple_approval import SimpleApprovalGate, ApprovalRequest, RiskLevel, ApprovalResult, ApprovalMode

class StructuredFileOps:
    """シンプルなファイル操作ツール"""
    
    def __init__(self):
        self.approval_gate = SimpleApprovalGate()
        self.logger = logging.getLogger(__name__)
    
    async def analyze_file_structure(self, file_path: str, **kwargs) -> Dict[str, Any]:
        """ファイル構造分析（シンプル版）"""
        try:
            self.logger.info(f"ファイル構造分析開始: {file_path}")
            
            path = Path(file_path)
            if not path.exists() or not path.is_file():
                return {
                    "success": False,
                    "error": f"ファイルが見つかりません: {file_path}"
                }
            
            # ファイル情報取得
            stat = path.stat()
            self.logger.debug(f"ファイル統計情報: size={stat.st_size}, mtime={stat.st_mtime}")
            
            # ファイル読み込み（デバッグ付き）
            content = None
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.logger.debug(f"ファイル読み込み成功: 内容長={len(content) if content else 0}")
                self.logger.debug(f"ファイル内容の最初の100文字: {repr(content[:100]) if content else 'None'}")
            except Exception as read_error:
                self.logger.error(f"ファイル読み込みエラー: {read_error}")
                return {
                    "success": False,
                    "error": f"ファイル読み込みエラー: {read_error}"
                }
            
            if content is None:
                self.logger.error("ファイル内容がNone")
                return {
                    "success": False,
                    "error": "ファイル内容を読み込めませんでした"
                }
            
            lines = content.split('\n')
            total_lines = len(lines)
            total_chars = len(content)
            
            self.logger.debug(f"解析結果: total_lines={total_lines}, total_chars={total_chars}")
            self.logger.debug(f"最初の3行: {lines[:3] if lines else 'なし'}")
            
            # ヘッダー検出
            headers = []
            sections = []
            current_section = None
            
            for i, line in enumerate(lines, 1):
                line_stripped = line.strip()
                
                if line_stripped.startswith('#'):
                    level = 0
                    for char in line_stripped:
                        if char == '#':
                            level += 1
                        else:
                            break
                    
                    header_text = line_stripped[level:].strip()
                    
                    if level <= 6:  # ヘッダーレベル制限
                        headers.append({
                            "line_number": i,
                            "level": level,
                            "text": header_text,
                            "full_line": line_stripped
                        })
                    
                    # セクション管理（レベル2以上）
                    if level >= 2:
                        if current_section:
                            current_section["end_line"] = i - 1
                        
                        current_section = {
                            "title": header_text,
                            "level": level,
                            "start_line": i
                        }
                        sections.append(current_section)
            
            # 最後のセクションを処理
            if current_section:
                current_section["end_line"] = total_lines
            
            return {
                "success": True,
                "file_path": file_path,
                "file_info": {
                    "total_lines": total_lines,
                    "total_chars": total_chars,
                    "size_bytes": stat.st_size,
                    "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat()
                },
                "headers": headers,
                "sections": sections,
                "analysis_time": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"ファイル構造分析エラー: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def search_content(self, file_path: str, pattern: str, **kwargs) -> Dict[str, Any]:
        """コンテンツ検索（シンプル版）"""
        try:
            self.logger.info(f"コンテンツ検索開始: pattern='{pattern}' in {file_path}")
            
            path = Path(file_path)
            if not path.exists() or not path.is_file():
                return {
                    "success": False,
                    "error": f"ファイルが見つかりません: {file_path}"
                }
            
            # ファイル読み込み
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            lines = content.split('\n')
            
            # 検索実行
            matches = []
            context_lines = kwargs.get('context_lines', 2)
            max_results = kwargs.get('max_results', 10)
            case_sensitive = kwargs.get('case_sensitive', False)
            
            flags = 0 if case_sensitive else re.IGNORECASE
            try:
                pattern_re = re.compile(pattern, flags)
            except re.error:
                return {
                    "success": False,
                    "error": f"無効な検索パターン: {pattern}"
                }
            
            for i, line in enumerate(lines):
                match = pattern_re.search(line)
                if match and len(matches) < max_results:
                    # コンテキスト取得
                    start_idx = max(0, i - context_lines)
                    end_idx = min(len(lines), i + context_lines + 1)
                    
                    context_before = '\n'.join(lines[start_idx:i]) if i > start_idx else ""
                    context_after = '\n'.join(lines[i+1:end_idx]) if i+1 < end_idx else ""
                    
                    matches.append({
                        "line_number": i + 1,
                        "match_text": match.group(),
                        "context_before": context_before,
                        "context_after": context_after,
                        "full_line": line
                    })
            
            return {
                "success": True,
                "file_path": file_path,
                "pattern": pattern,
                "matches_found": len(matches),
                "results": matches,
                "search_time": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"コンテンツ検索エラー: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def read_file(self, file_path: str, **kwargs) -> Dict[str, Any]:
        """ファイル読み込み（大容量対応版）"""
        try:
            self.logger.info(f"ファイル読み込み開始: {file_path}")
            
            path = Path(file_path)
            if not path.exists() or not path.is_file():
                return {
                    "success": False,
                    "error": f"ファイルが見つかりません: {file_path}"
                }
            
            # 複数のエンコーディングを試行
            encodings_to_try = ['utf-8', 'shift_jis', 'euc-jp', 'iso-2022-jp', 'cp932']
            content = None
            used_encoding = None
            
            for encoding in encodings_to_try:
                try:
                    with open(path, 'r', encoding=encoding) as f:
                        content = f.read()
                    used_encoding = encoding
                    break
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    self.logger.warning(f"エンコーディング {encoding} での読み込み失敗: {e}")
                    continue
            
            if content is None:
                # すべてのエンコーディングで失敗した場合、バイナリとして読み込み
                try:
                    with open(path, 'rb') as f:
                        binary_content = f.read()
                        # バイナリ内容を16進数文字列として表現（最初の3000文字分）
                        content = binary_content.hex()[:3000]
                        used_encoding = 'binary'
                        self.logger.warning(f"バイナリファイルとして読み込み: {file_path}")
                except Exception as e:
                    return {"success": False, "error": f"すべてのエンコーディングで読み込み失敗: {e}"}
            
            # 大容量ファイル判断と切り詰め処理
            total_chars = len(content)
            total_lines = len(content.split('\n')) if used_encoding != 'binary' else 1
            is_truncated = False
            truncated_content = content
            
            # 一定文字数（3000文字）を超える場合は切り詰め
            max_chars = kwargs.get('max_chars', 3000)
            if total_chars > max_chars:
                is_truncated = True
                truncated_content = content[:max_chars]
                self.logger.info(f"大容量ファイル検出: {total_chars}文字 -> {max_chars}文字に切り詰め")
            
            # メタデータ構築
            metadata = {
                "total_chars": total_chars,
                "total_lines": total_lines,
                "is_truncated": is_truncated,
                "truncated_chars": len(truncated_content),
                "max_chars_limit": max_chars,
                "used_encoding": used_encoding,
                "read_time": datetime.now().isoformat()
            }
            
            return {
                "success": True,
                "file_path": file_path,
                "content": truncated_content,
                "metadata": metadata,
                "size_bytes": len(truncated_content.encode('utf-8')) if used_encoding != 'binary' else len(truncated_content),
                "lines": len(truncated_content.split('\n')) if used_encoding != 'binary' else 1
            }
            
        except Exception as e:
            self.logger.error(f"ファイル読み込みエラー: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def write_file(self, file_path: str, content: str, **kwargs) -> Dict[str, Any]:
        """ファイル書き込み（承認付き、シンプル版）"""
        try:
            self.logger.info(f"ファイル書き込み開始: {file_path}")
            self.logger.debug(f"承認ゲート状態: {self.approval_gate}")
            self.logger.debug(f"承認ゲート設定: {getattr(self.approval_gate, 'config', 'N/A')}")
            
            # 承認要求
            approval_request = ApprovalRequest(
                operation="ファイル書き込み",
                description=f"ファイル '{file_path}' に内容を書き込みます",
                target=file_path,
                risk_level=self._assess_write_risk(file_path),
                details=f"内容サイズ: {len(content)}文字"
            )
            
            self.logger.debug(f"承認要求作成: {approval_request}")
            
            # 承認処理
            approval = self.approval_gate.request_approval(approval_request)
            self.logger.debug(f"承認結果: {approval}")
            
            if not approval.approved:
                error_msg = f"承認拒否: {approval.reason}"
                self.logger.warning(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "approval_details": {
                        "requested": approval_request.description,
                        "reason": approval.reason,
                        "risk_level": approval_request.risk_level
                    }
                }
            
            self.logger.info("承認完了、ファイル書き込みを実行")
            
            # 書き込み実行
            path = Path(file_path)
            if not path.parent.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return {
                "success": True,
                "file_path": file_path,
                "message": "ファイル書き込み完了",
                "size_bytes": len(content.encode('utf-8')),
                "lines": len(content.split('\n')),
                "write_time": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"ファイル書き込みエラー: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    def _assess_write_risk(self, file_path: str) -> RiskLevel:
        """書き込みリスク評価"""
        path = Path(file_path)
        
        self.logger.debug(f"書き込みリスク評価開始: {file_path}")
        
        # システムファイルの保護
        if str(path).startswith(('/etc', '/usr', '/var', 'C:\\Windows', 'C:\\Program Files')):
            self.logger.debug(f"システムファイルとして判定: {file_path}")
            return RiskLevel.HIGH
        
        # 既存ファイルの上書き
        if path.exists():
            self.logger.debug(f"既存ファイルの上書きとして判定: {file_path}")
            return RiskLevel.MEDIUM
        
        # 新規ファイル作成
        self.logger.debug(f"新規ファイル作成として判定: {file_path}")
        return RiskLevel.LOW
    
    async def read_file_section(self, file_path: str, start_line: int = 1, line_count: int = 50, **kwargs) -> Dict[str, Any]:
        """ファイルの指定範囲を読み込み（大容量ファイル対応）"""
        try:
            self.logger.info(f"ファイルセクション読み込み開始: {file_path} (L{start_line}-{start_line + line_count - 1})")
            
            path = Path(file_path)
            if not path.exists() or not path.is_file():
                return {
                    "success": False,
                    "error": f"ファイルが見つかりません: {file_path}"
                }
            
            # ファイル内容を読み込み
            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            total_lines = len(lines)
            
            # 行番号の調整（1ベースから0ベースへ）
            start_idx = max(0, start_line - 1)
            end_idx = min(total_lines, start_idx + line_count)
            
            # 実際に読み込まれた行数
            actual_lines = end_idx - start_idx
            
            if start_idx >= total_lines:
                return {
                    "success": False,
                    "error": f"開始行 {start_line} がファイルの行数 {total_lines} を超えています"
                }
            
            # 指定範囲の内容を抽出
            section_lines = lines[start_idx:end_idx]
            content = ''.join(section_lines)
            
            # セクション情報を構築
            section_info = {
                "start_line": start_line,
                "end_line": start_line + actual_lines - 1,
                "actual_lines": actual_lines,
                "total_file_lines": total_lines,
                "requested_lines": line_count
            }
            
            # メタデータ構築
            metadata = {
                "total_chars": len(content),
                "total_lines": actual_lines,
                "is_section": True,
                "section_range": f"L{start_line}-{start_line + actual_lines - 1}",
                "read_time": datetime.now().isoformat()
            }
            
            return {
                "success": True,
                "file_path": file_path,
                "content": content,
                "section_info": section_info,
                "metadata": metadata,
                "size_bytes": len(content.encode('utf-8'))
            }
            
        except Exception as e:
            self.logger.error(f"ファイルセクション読み込みエラー: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def read_file_chunk(self, file_path: str, offset: int = 0, size: int = 8192, **kwargs) -> Dict[str, Any]:
        """ファイルの指定範囲を文字ベースで読み込み（堅牢性向上版）"""
        try:
            self.logger.info(f"ファイルチャンク読み込み開始: {file_path} (offset={offset}, size={size})")
            path = Path(file_path)
            if not path.exists() or not path.is_file():
                return {"success": False, "error": f"ファイルが見つかりません: {file_path}"}

            stat = path.stat()
            total_size = stat.st_size

            if offset >= total_size:
                self.logger.warning(f"オフセット({offset})がファイルサイズ({total_size})を超えています。空の内容を返します。")
                content = ""
                actual_read_size = 0
                used_encoding = "N/A"
            else:
                # 1. ファイルをバイナリモードで開いて読み込む
                with open(path, 'rb') as f:
                    f.seek(offset)
                    binary_chunk = f.read(size)
                
                actual_read_size = len(binary_chunk)

                # 2. デコードを試みる
                content = None
                used_encoding = None
                encodings_to_try = ['utf-8', 'shift_jis', 'euc-jp', 'cp932', 'latin-1']
                for encoding in encodings_to_try:
                    try:
                        content = binary_chunk.decode(encoding)
                        used_encoding = encoding
                        self.logger.info(f"エンコーディング {encoding} でデコード成功")
                        break
                    except UnicodeDecodeError:
                        continue
                
                # 3. 全てのデコードに失敗した場合のフォールバック
                if content is None:
                    content = binary_chunk.hex()
                    used_encoding = 'binary'
                    self.logger.warning(f"全てのテキストデコードに失敗したため、バイナリ(hex)として扱います: {file_path}")

            is_complete = (offset + actual_read_size) >= total_size
            metadata = {
                "file_path": file_path,
                "total_size_bytes": total_size,
                "offset": offset,
                "requested_size": size,
                "actual_read_size": actual_read_size,
                "is_complete": is_complete,
                "used_encoding": used_encoding,
                "read_time": datetime.now().isoformat()
            }

            return {
                "success": True,
                "file_path": file_path,
                "content": content,
                "metadata": metadata
            }

        except Exception as e:
            self.logger.error(f"ファイルチャンク読み込みエラー: {e}", exc_info=True)
            return {"success": False, "error": str(e)}