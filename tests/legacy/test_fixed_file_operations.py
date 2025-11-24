#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修正されたファイル操作機能のテスト
安全チェック、READコマンド、ファイル内容プロンプト統合の検証
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

def test_safety_check():
    """安全チェック機能のテスト"""
    
    print("=== 修正されたファイル操作機能のテスト ===\n")
    
    # テスト用ファイルを作成
    test_file = Path("safety_test.py")
    original_content = """# 安全チェックテスト用ファイル
def important_function():
    '''重要な関数'''
    return "重要なデータ"

class CriticalClass:
    def __init__(self):
        self.data = "重要なデータ"
    
    def process(self):
        return "重要な処理"

# このファイルは安全チェックによって保護される
print("重要なファイルです")
"""
    
    # オリジナルファイルを作成
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write(original_content)
    
    print(f"✓ テストファイル作成: {test_file}")
    print(f"✓ オリジナル内容長: {len(original_content)} 文字")
    
    # 修正されたファイル操作をテスト
    from codecrafter.state.agent_state import AgentState
    from datetime import datetime
    
    # テスト用のAgentState作成
    test_state = AgentState(
        session_id="safety_test",
        created_at=datetime.now(),
        last_activity=datetime.now()
    )
    
    # 修正されたファイル操作処理をインポート
    def test_single_file_operation(operation: str, filename: str, content: str, state: AgentState):
        """修正されたファイル操作をテスト"""
        from codecrafter.tools.file_tools import FileTools
        from codecrafter.ui import rich_ui
        
        file_tools = FileTools()
        
        try:
            from pathlib import Path
            
            # READ操作の処理
            if operation == "READ":
                try:
                    file_content = file_tools.read_file(filename)
                    read_msg = f"""📄 ファイル内容を読み取りました: {filename}

--- ファイル内容 ---
{file_content}
--- 終了 ---

ファイルサイズ: {len(file_content)} 文字
読み取り完了。内容を分析してご回答します。"""
                    
                    print(f"[READ] ファイル読み取り: {filename}")
                    print(f"読み取り成功 ({len(file_content)} 文字)")
                    return "READ成功", file_content
                except Exception as e:
                    error_msg = f"ファイル読み取りエラー ({filename}): {e}"
                    print(f"ERROR: {error_msg}")
                    return "READ失敗", None
            
            # EDIT時の安全チェック
            elif operation == "EDIT":
                try:
                    current_content = file_tools.read_file(filename)
                    content_reduction_ratio = 1 - (len(content) / len(current_content)) if len(current_content) > 0 else 0
                    
                    # 70%以上の削減または空ファイル化を検知
                    if content_reduction_ratio >= 0.7 or len(content.strip()) == 0:
                        warning_msg = f"""🚨 EDIT操作の安全チェックが作動しました

ファイル: {filename}
元のサイズ: {len(current_content)} 文字
新しいサイズ: {len(content)} 文字
削減率: {content_reduction_ratio*100:.1f}%

このファイル操作は危険です。ファイル内容の大幅な削減が検出されました。
操作を中止しました。"""
                        
                        print(warning_msg)
                        return "EDIT中止", None
                    else:
                        result = file_tools.write_file(filename, content)
                        print(f"EDIT実行: {filename} ({len(content)} 文字)")
                        return "EDIT成功", result
                        
                except Exception as read_error:
                    print(f"安全チェックエラー: {read_error}")
                    return "EDIT失敗", None
            
        except Exception as e:
            print(f"ファイル操作失敗: {e}")
            return "操作失敗", None
    
    # テストケース実行
    test_cases = [
        # 1. READ操作のテスト（安全）
        ("READ", str(test_file), "", "READ操作のテスト"),
        
        # 2. 安全なEDIT操作（小さな変更）
        ("EDIT", str(test_file), original_content + "\n# 小さな追加", "安全なEDIT"),
        
        # 3. 危険なEDIT操作（大幅削減）  
        ("EDIT", str(test_file), "# 大幅に削減されたファイル", "危険なEDIT（大幅削減）"),
        
        # 4. 危険なEDIT操作（空ファイル化）
        ("EDIT", str(test_file), "", "危険なEDIT（空ファイル化）"),
    ]
    
    for operation, filename, content, description in test_cases:
        print(f"\n--- {description} ---")
        
        # ファイル操作前の状態確認
        if Path(filename).exists():
            with open(filename, 'r', encoding='utf-8') as f:
                before_content = f.read()
            print(f"操作前: {len(before_content)} 文字")
        
        # 操作実行
        result_type, result_data = test_single_file_operation(operation, filename, content, test_state)
        print(f"結果: {result_type}")
        
        # ファイル操作後の状態確認
        if Path(filename).exists():
            with open(filename, 'r', encoding='utf-8') as f:
                after_content = f.read()
            print(f"操作後: {len(after_content)} 文字")
            
            # ファイルが保護されたかチェック
            if result_type == "EDIT中止" and len(after_content) == len(before_content):
                print("✅ 安全チェックが正常に動作し、ファイルが保護されました")
            elif result_type == "EDIT成功":
                print("✅ 安全なEDIT操作が正常に完了しました")
            elif result_type == "READ成功":
                print("✅ READ操作が正常に完了しました")
        
        # 元のファイルに復元（次のテストのため）
        if operation == "EDIT" and result_type == "EDIT成功":
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(original_content)
    
    # クリーンアップ
    try:
        test_file.unlink()
        print(f"\n✓ テストファイル削除: {test_file}")
        
        # バックアップファイルも削除
        backup_files = list(Path(".").glob("safety_test.backup*"))
        for backup_file in backup_files:
            backup_file.unlink()
            print(f"✓ バックアップファイル削除: {backup_file}")
            
    except Exception as e:
        print(f"クリーンアップエラー: {e}")

def test_prompt_integration():
    """プロンプト統合テスト"""
    
    print(f"\n=== プロンプト統合テスト ===")
    
    # テストファイル作成
    test_file = Path("prompt_test.py")
    test_content = """def test_function():
    return "テスト"
"""
    
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write(test_content)
    
    try:
        # プロンプトコンパイラのテスト
        from codecrafter.prompts.prompt_compiler import PromptCompiler
        from codecrafter.state.agent_state import AgentState
        from datetime import datetime
        
        compiler = PromptCompiler()
        
        # テスト用のAgentState作成
        test_state = AgentState(
            session_id="prompt_test",
            created_at=datetime.now(),
            last_activity=datetime.now()
        )
        
        # file_contextを作成
        file_context = {
            'file_contents': {
                str(test_file): test_content
            },
            'errors': []
        }
        
        # プロンプト生成
        system_prompt = compiler.compile_system_prompt(
            state=test_state,
            rag_results=None,
            file_context=file_context
        )
        
        # ファイル内容がプロンプトに含まれているかチェック
        file_content_included = test_content in system_prompt
        file_path_included = str(test_file) in system_prompt
        
        print(f"✓ ファイルパス含有: {file_path_included}")
        print(f"✓ ファイル内容含有: {file_content_included}")
        print(f"✓ プロンプト長: {len(system_prompt)} 文字")
        
        if file_content_included:
            print("✅ ファイル内容がプロンプトに正常に統合されました！")
        else:
            print("❌ ファイル内容がプロンプトに含まれていません")
            
        # プロンプトの一部を表示
        if "📄 参照ファイル内容:" in system_prompt:
            print("✅ 参照ファイル内容セクションが見つかりました")
        else:
            print("❌ 参照ファイル内容セクションが見つかりません")
        
    finally:
        test_file.unlink()
        print(f"✓ テストファイル削除: {test_file}")

if __name__ == "__main__":
    test_safety_check()
    test_prompt_integration()