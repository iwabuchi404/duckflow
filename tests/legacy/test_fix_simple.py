#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修正後の動作テスト
"""

def test_search_pattern():
    """ripgrepパターンテスト"""
    test_content = """# RPGゲーム「勇者の旅路」設計ドキュメント

## ゲーム概要
中世ファンタジー世界を舞台にしたターン制RPGゲーム。
プレイヤーは勇者となり、世界を脅かす魔王を倒すため冒険する。"""
    
    # 正規表現パターンテスト
    import re
    pattern = "概要|プロジェクト概要|目的"
    matches = list(re.finditer(pattern, test_content))
    
    print(f"パターン '{pattern}' での検索結果:")
    for match in matches:
        start = max(0, test_content.rfind('\n', 0, match.start()) + 1)
        end = test_content.find('\n', match.end())
        if end == -1:
            end = len(test_content)
        line = test_content[start:end]
        print(f"  マッチ: '{match.group()}' in '{line}'")
    
    return len(matches) > 0

def test_file_structure():
    """ファイル構造分析テスト"""
    try:
        from companion.file_ops import SimpleFileOps
        file_ops = SimpleFileOps()
        
        result = file_ops.analyze_file_structure("game_doc.md")
        
        print("\n📊 ファイル構造分析結果:")
        print(f"  operation: {result.get('operation')}")
        print(f"  file_path: {result.get('file_path')}")
        file_info = result.get('file_info', {})
        print(f"  total_lines: {file_info.get('total_lines')}")
        print(f"  total_chars: {file_info.get('total_chars')}")
        print(f"  headers_count: {len(result.get('headers', []))}")
        
        # ヘッダー情報表示
        headers = result.get('headers', [])[:3]
        for h in headers:
            print(f"    L{h['line_number']}: {'#' * h['level']} {h['text']}")
        
        return True
        
    except Exception as e:
        print(f"❌ ファイル構造分析エラー: {e}")
        return False

def test_search_content():
    """検索機能テスト"""
    try:
        from companion.file_ops import SimpleFileOps
        file_ops = SimpleFileOps()
        
        result = file_ops.search_content("game_doc.md", "概要|プロジェクト概要|目的", 2)
        
        print(f"\n🔍 検索結果:")
        print(f"  pattern: {result.get('pattern')}")
        print(f"  matches_found: {result.get('matches_found', 0)}")
        print(f"  tool_used: {result.get('tool_used')}")
        
        results = result.get('results', [])
        for r in results[:2]:
            print(f"    L{r['line_number']}: {r['match']}")
        
        return result.get('matches_found', 0) > 0
        
    except Exception as e:
        print(f"❌ 検索エラー: {e}")
        return False

if __name__ == "__main__":
    print("=== 修正後動作テスト ===")
    
    success_count = 0
    
    # パターン検索テスト
    if test_search_pattern():
        print("✅ 正規表現パターン検索 - 成功")
        success_count += 1
    else:
        print("❌ 正規表現パターン検索 - 失敗")
    
    # ファイル構造分析テスト  
    if test_file_structure():
        print("✅ ファイル構造分析 - 成功")
        success_count += 1
    else:
        print("❌ ファイル構造分析 - 失敗")
    
    # 検索機能テスト
    if test_search_content():
        print("✅ 検索機能 - 成功")  
        success_count += 1
    else:
        print("❌ 検索機能 - 失敗")
    
    print(f"\n=== テスト結果: {success_count}/3 成功 ===")
    exit(0 if success_count == 3 else 1)