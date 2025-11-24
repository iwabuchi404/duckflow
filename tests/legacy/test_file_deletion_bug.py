#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ファイル内容消去バグの再現テスト
「ファイル確認」でファイル内容が消えるバグを調査
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

def test_file_deletion_bug():
    """ファイル内容消去バグの再現テスト"""
    
    print("=== ファイル内容消去バグの調査 ===\n")
    
    # テスト用ファイルを作成
    test_file = Path("temp_content_test.py")
    original_content = """# 重要なテストファイル
def important_function():
    '''この関数は削除されてはいけません'''
    return "重要なデータ"

class ImportantClass:
    def __init__(self):
        self.data = "削除されてはいけないデータ"
    
    def process(self):
        return "重要な処理結果"

if __name__ == "__main__":
    func_result = important_function()
    obj = ImportantClass()
    print(f"結果: {func_result}, {obj.process()}")
"""
    
    # オリジナルファイルを作成
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write(original_content)
    
    print(f"✓ テストファイル作成: {test_file}")
    print(f"✓ オリジナル内容長: {len(original_content)} 文字")
    
    # 内容確認
    with open(test_file, 'r', encoding='utf-8') as f:
        read_content = f.read()
    
    print(f"✓ 作成後内容長: {len(read_content)} 文字")
    print("✓ オリジナル内容の最初の3行:")
    for i, line in enumerate(original_content.split('\n')[:3], 1):
        print(f"  {i}: {line}")
    
    # AIが間違って出力する可能性のあるパターンをテスト
    dangerous_responses = [
        # パターン1: 空のEDIT
        """ファイルを確認しました。

FILE_OPERATION:EDIT:temp_content_test.py
```python
```
""",
        
        # パターン2: 部分的な内容でのEDIT  
        """ファイルの内容を分析しました。

FILE_OPERATION:EDIT:temp_content_test.py
```python
def important_function():
    return "重要なデータ"
```
""",
        
        # パターン3: コメントだけのEDIT
        """このファイルは以下のようになっています：

FILE_OPERATION:EDIT:temp_content_test.py
```python
# 分析結果: 重要な関数があります
```
""",
    ]
    
    # ファイル操作処理を直接テスト
    from codecrafter.state.agent_state import AgentState
    from datetime import datetime
    
    # テスト用のAgentState作成
    test_state = AgentState(
        session_id="test_deletion_bug",
        created_at=datetime.now(),
        last_activity=datetime.now()
    )
    
    # ファイル操作処理を直接実装
    def execute_file_operations_test(ai_response: str, state: AgentState) -> None:
        """ファイル操作処理のテスト版"""
        from codecrafter.tools.file_tools import FileTools
        
        file_tools = FileTools()
        lines = ai_response.split("\n")  # 修正: \\n -> \n
        current_op, filename, content, in_code, buf = None, None, [], False, []
        
        print(f"  解析対象行数: {len(lines)}")
        
        for i, line in enumerate(lines):
            print(f"  行{i+1}: '{line.strip()}'")  # デバッグ出力
            
            if line.startswith("FILE_OPERATION:"):
                parts = line.split(":")
                if len(parts) >= 3:
                    current_op = parts[1].upper()
                    filename = parts[2].strip()  # trim空白
                    buf = []
                    print(f"  -> 操作検出: {current_op}, ファイル: {filename}")
                    continue
                    
            if line.strip().startswith("```"):
                print(f"  -> コードブロック切り替え: in_code={in_code}")
                if in_code and current_op and filename:
                    # ここで実際のファイル操作を実行
                    if current_op in ["CREATE", "EDIT"]:
                        content_str = "\n".join(buf)  # 修正: \\n -> \n
                        print(f"  🚨 実行: {current_op} {filename} ({len(content_str)} 文字)")
                        print(f"    内容: '{content_str[:100]}{'...' if len(content_str) > 100 else ''}'")
                        result = file_tools.write_file(filename, content_str)
                        print(f"    結果: {result}")
                    current_op, filename, buf = None, None, []
                in_code = not in_code
                continue
                
            if in_code and current_op and filename:
                buf.append(line)
                print(f"  -> バッファに追加: '{line}'")
    
    for i, dangerous_response in enumerate(dangerous_responses, 1):
        print(f"\n--- 危険パターン {i} のテスト ---")
        print(f"AIの応答: {dangerous_response[:100]}...")
        
        # ファイル操作前の内容確認
        try:
            with open(test_file, 'r', encoding='utf-8') as f:
                before_content = f.read()
            print(f"実行前内容長: {len(before_content)} 文字")
            
            # ファイル操作を実行
            execute_file_operations_test(dangerous_response, test_state)
            
            # ファイル操作後の内容確認
            with open(test_file, 'r', encoding='utf-8') as f:
                after_content = f.read()
            print(f"実行後内容長: {len(after_content)} 文字")
            
            # 内容の変化をチェック
            if len(after_content) < len(before_content):
                print(f"🚨 WARNING: ファイル内容が減少しました！")
                print(f"  減少量: {len(before_content) - len(after_content)} 文字")
                print(f"  実行後内容:")
                print("---")
                print(after_content[:200] if after_content else "(空ファイル)")
                print("---")
                
                # バックアップファイルをチェック
                backup_files = list(Path(".").glob(f"{test_file.stem}.backup*"))
                if backup_files:
                    print(f"  バックアップファイル: {backup_files}")
                    with open(backup_files[0], 'r', encoding='utf-8') as f:
                        backup_content = f.read()
                    print(f"  バックアップ内容長: {len(backup_content)} 文字")
                else:
                    print("  ❌ バックアップファイルが見つかりません")
            elif after_content != before_content:
                print(f"⚠️  ファイル内容が変更されました")
            else:
                print(f"✅ ファイル内容は変更されませんでした")
                
        except Exception as e:
            print(f"❌ テスト実行エラー: {e}")
            import traceback
            traceback.print_exc()
        
        # ファイルを元の状態に復元
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(original_content)
    
    # クリーンアップ
    try:
        test_file.unlink()
        print(f"\n✓ テストファイル削除: {test_file}")
        
        # バックアップファイルも削除
        backup_files = list(Path(".").glob("temp_content_test.backup*"))
        for backup_file in backup_files:
            backup_file.unlink()
            print(f"✓ バックアップファイル削除: {backup_file}")
            
    except Exception as e:
        print(f"クリーンアップエラー: {e}")

if __name__ == "__main__":
    test_file_deletion_bug()