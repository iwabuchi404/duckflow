#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
実際のDuckflowでのファイル分析動作テスト
ユーザーの報告する「存在しない内容を言ってくる」問題を再現・検証
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from codecrafter.main_v2 import DuckflowAgentV2

def test_file_analysis_behavior():
    """実際のファイル分析動作をテスト"""
    
    print("=== 実際のDuckflow ファイル分析動作テスト ===\n")
    
    # テスト用ファイルを作成
    test_file = Path("temp_test_analysis.py")
    test_content = """# テスト用Pythonファイル
def calculate_area(width, height):
    \"\"\"長方形の面積を計算\"\"\"
    return width * height

def validate_input(value):
    \"\"\"入力値の検証\"\"\"
    if value <= 0:
        raise ValueError("値は正の数である必要があります")
    return True

class DataProcessor:
    def __init__(self, name):
        self.name = name
        self.processed_count = 0
    
    def process_data(self, data_list):
        \"\"\"データを処理\"\"\"
        result = []
        for item in data_list:
            result.append(item * 2)
        self.processed_count += len(data_list)
        return result

if __name__ == "__main__":
    processor = DataProcessor("test")
    print(f"Area: {calculate_area(5, 3)}")
"""
    
    # テストファイルを作成
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write(test_content)
    
    print(f"✓ テストファイル作成: {test_file}")
    print(f"✓ 実際のファイル内容:")
    print("---")
    print(test_content[:300] + "...")
    print("---\n")
    
    try:
        # Duckflowエージェントを初期化
        agent = DuckflowAgentV2()
        
        # ファイル分析リクエストをテスト
        test_queries = [
            f"{test_file}の内容を分析してください",
            f"{test_file}にはどのような関数がありますか？",
            f"{test_file}のコード構造を説明してください",
            f"{test_file}に問題がないかチェックしてください"
        ]
        
        for i, query in enumerate(test_queries, 1):
            print(f"【テスト {i}】")
            print(f"クエリ: {query}")
            
            # エージェントでの処理をシミュレーション
            # (実際の対話ループは複雑なので、主要部分をテスト)
            
            # 1. システムプロンプト生成の確認
            from codecrafter.prompts.prompt_compiler import PromptCompiler
            compiler = PromptCompiler()
            
            # 現在のプロンプト生成プロセスを確認
            # AgentStateを作成
            from codecrafter.state.agent_state import AgentState
            from datetime import datetime
            
            test_state = AgentState(
                session_id="test_session",
                current_task=query,
                created_at=datetime.now(),
                last_activity=datetime.now()
            )
            
            system_prompt = compiler.compile_system_prompt(
                state=test_state,
                rag_results=None,
                file_context={"target_file": str(test_file)}
            )
            
            # ファイル内容がプロンプトに含まれているかチェック
            file_content_included = test_content[:100] in system_prompt
            file_path_included = str(test_file) in system_prompt
            
            print(f"  - ファイルパスがプロンプトに含まれる: {file_path_included}")
            print(f"  - ファイル内容がプロンプトに含まれる: {file_content_included}")
            
            # プロンプトの関連部分を表示
            if str(test_file) in system_prompt:
                print("  ✓ ファイル参照が検出されました")
            else:
                print("  ❌ ファイル参照が検出されませんでした")
            
            # プロンプト内容の一部を表示
            print(f"  システムプロンプト長: {len(system_prompt)} 文字")
            if len(system_prompt) > 500:
                print("  プロンプト抜粋:")
                print("    " + system_prompt[:200].replace('\n', '\\n'))
                print("    ...")
            
            print("-" * 50)
    
    except Exception as e:
        print(f"❌ テスト実行エラー: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # テストファイルを削除
        if test_file.exists():
            test_file.unlink()
            print(f"✓ テストファイル削除: {test_file}")

if __name__ == "__main__":
    test_file_analysis_behavior()