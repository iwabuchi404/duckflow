#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
StructuredFileOpsの_read_file_safely メソッドをデバッグ
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from companion.tools.structured_file_ops import StructuredFileOps, AnalyzeFileRequest

def test_read_file_safely():
    """_read_file_safely メソッドの直接テスト"""
    print("=== _read_file_safely 直接テスト ===")
    
    # StructuredFileOps インスタンス作成
    file_ops = StructuredFileOps()
    
    # game_doc.mdのパス
    file_path = Path("game_doc.md")
    
    print(f"ファイルパス: {file_path}")
    print(f"ファイル存在確認: {file_path.exists()}")
    print(f"ファイルサイズ: {file_path.stat().st_size if file_path.exists() else 'N/A'}")
    
    try:
        # _read_file_safely を直接呼び出し
        content = file_ops._read_file_safely(file_path)
        
        print(f"読み取り内容の文字数: {len(content)}")
        print(f"読み取り内容の行数: {len(content.split('\\n'))}")
        print("読み取り内容の最初の3行:")
        for i, line in enumerate(content.split('\\n')[:3]):
            print(f"  {i+1}: {line}")
        
        # 改行文字の確認
        print(f"\\n の数: {content.count('\\n')}")
        print(f"\\r の数: {content.count('\\r')}")
        
        return True
        
    except Exception as e:
        print(f"ERROR: _read_file_safely エラー: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_analyze_file_structure():
    """analyze_file_structure メソッドの直接テスト"""
    print("\\n=== analyze_file_structure 直接テスト ===")
    
    # StructuredFileOps インスタンス作成
    file_ops = StructuredFileOps()
    
    # 分析要求を作成
    request = AnalyzeFileRequest(
        file_path="game_doc.md",
        include_content_preview=True,
        max_headers=50
    )
    
    try:
        # analyze_file_structure を直接呼び出し
        response = file_ops.analyze_file_structure(request)
        
        print(f"分析成功: {response.success}")
        print(f"ファイルパス: {response.file_path}")
        print(f"総行数: {response.file_info.total_lines}")
        print(f"総文字数: {response.file_info.total_chars}")
        print(f"サイズ(bytes): {response.file_info.size_bytes}")
        print(f"ヘッダー数: {len(response.headers)}")
        print(f"セクション数: {len(response.sections)}")
        
        if response.headers:
            print("\\nヘッダー一覧:")
            for header in response.headers[:3]:
                print(f"  L{header.line_number}: {'#' * header.level} {header.text}")
        
        if response.error_message:
            print(f"エラーメッセージ: {response.error_message}")
        
        return True
        
    except Exception as e:
        print(f"ERROR: analyze_file_structure エラー: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """メインテスト関数"""
    print("DEBUG: StructuredFileOps ファイル読み取りデバッグ開始")
    
    success1 = test_read_file_safely()
    success2 = test_analyze_file_structure()
    
    if success1 and success2:
        print("\\nSUCCESS: ファイル読み取り機能は正常に動作しています")
        return True
    else:
        print("\\nERROR: ファイル読み取りに問題があります")
        return False

if __name__ == "__main__":
    exit(0 if main() else 1)