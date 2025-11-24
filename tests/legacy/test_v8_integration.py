#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V8システム統合テスト

実際のシステムでV8が動作するかを確認
"""

import sys
from pathlib import Path

# パス設定
sys.path.append(str(Path(__file__).parent))

def test_v8_import():
    """V8システムのインポートテスト"""
    print("=== V8システム インポートテスト ===")
    
    try:
        from companion.enhanced_dual_loop import EnhancedDualLoopSystem
        print("✅ EnhancedDualLoopSystem インポート成功")
        
        # V8の統合確認
        system = EnhancedDualLoopSystem()
        
        # V8コアが使用されているか確認
        core_class_name = system.enhanced_companion.__class__.__name__
        print(f"✅ 使用中のコア: {core_class_name}")
        
        if "V8" in core_class_name:
            print("✅ V8システムの統合成功")
            
            # V8特有の機能確認
            if hasattr(system.enhanced_companion, 'human_formatter'):
                print("✅ HumanOutputFormatter 統合済み")
            
            if hasattr(system.enhanced_companion, 'structured_file_ops'):
                print("✅ StructuredFileOps 統合済み")
            
            return True
        else:
            print(f"❌ V8システムが使用されていません: {core_class_name}")
            return False
        
    except Exception as e:
        print(f"❌ インポートエラー: {e}")
        return False

def test_v8_formatter():
    """V8フォーマッターの基本動作テスト"""
    print("\n=== V8フォーマッター動作テスト ===")
    
    try:
        from companion.output.human_formatter import HumanOutputFormatter, FormatterRequest
        
        formatter = HumanOutputFormatter()
        
        # game_doc.mdのような構造化データをテスト
        test_data = {
            "operation": "構造分析",
            "file_path": "game_doc.md", 
            "file_info": {
                "total_lines": 40,
                "total_chars": 532,
                "encoding": "utf-8"
            },
            "headers": [
                {"line_number": 1, "level": 1, "text": "RPGゲーム「勇者の旅路」設計ドキュメント"},
                {"line_number": 3, "level": 2, "text": "ゲーム概要"},
                {"line_number": 7, "level": 2, "text": "主要システム"},
                {"line_number": 23, "level": 2, "text": "技術仕様"}
            ],
            "sections": [
                {"title": "ゲーム概要", "level": 2, "start_line": 3, "end_line": 6},
                {"title": "主要システム", "level": 2, "start_line": 7, "end_line": 22}
            ]
        }
        
        request = FormatterRequest(
            data=test_data,
            context="RPGゲームドキュメントの分析",
            format_type="file_analysis"
        )
        
        # 同期版フォーマットテスト
        result = formatter._format_with_template(request, formatter.templates['file_analysis'])
        
        print("✅ V8フォーマッター動作成功")
        print(f"要約: {result.summary}")
        print("フォーマット結果:")
        print(result.human_text)
        
        return True
        
    except Exception as e:
        print(f"❌ V8フォーマッターテストエラー: {e}")
        return False

def main():
    """テストメイン"""
    print("🚀 V8システム統合テスト開始")
    
    success_count = 0
    total_tests = 2
    
    if test_v8_import():
        success_count += 1
    
    if test_v8_formatter():
        success_count += 1
    
    print(f"\n🎯 統合テスト結果: {success_count}/{total_tests} 成功")
    
    if success_count == total_tests:
        print("\n✅ V8システム統合成功")
        print("📋 次のステップ:")
        print("  1. main_companion.py でV8システムをテスト")
        print("  2. game_doc.md分析が読みやすくなることを確認")
        print("  3. プロキシシステムが排除されることを確認")
    else:
        print("❌ 統合に問題があります")
    
    return success_count == total_tests

if __name__ == "__main__":
    exit(0 if main() else 1)