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
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            lines = content.split('\n')
            total_lines = len(lines)
            total_chars = len(content)
            
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
        """ファイル読み込み（シンプル版）"""
        try:
            self.logger.info(f"ファイル読み込み開始: {file_path}")
            
            path = Path(file_path)
            if not path.exists() or not path.is_file():
                return {
                    "success": False,
                    "error": f"ファイルが見つかりません: {file_path}"
                }
            
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return {
                "success": True,
                "file_path": file_path,
                "content": content,
                "size_bytes": len(content.encode('utf-8')),
                "lines": len(content.split('\n')),
                "read_time": datetime.now().isoformat()
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
            # 承認要求
            approval_request = ApprovalRequest(
                operation="ファイル書き込み",
                description=f"ファイル '{file_path}' に内容を書き込みます",
                target=file_path,
                risk_level=self._assess_write_risk(file_path),
                details=f"内容サイズ: {len(content)}文字"
            )
            
            approval = self.approval_gate.request_approval(approval_request)
            if not approval.approved:
                return {
                    "success": False,
                    "error": f"承認拒否: {approval.reason}"
                }
            
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
            self.logger.error(f"ファイル書き込みエラー: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _assess_write_risk(self, file_path: str) -> RiskLevel:
        """書き込みリスク評価"""
        path = Path(file_path)
        
        # システムファイルの保護
        if str(path).startswith(('/etc', '/usr', '/var', 'C:\\Windows', 'C:\\Program Files')):
            return RiskLevel.HIGH
        
        # 既存ファイルの上書き
        if path.exists():
            return RiskLevel.MEDIUM
        
        # 新規ファイル作成
        return RiskLevel.LOW