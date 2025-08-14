"""
Phase 1ファイル操作改善プロンプトの適用

ファイル読み込み・操作の問題を修正し、
AIが正確なファイルデータを参照できるようにします。
"""

import yaml
from pathlib import Path
from prompt_manager import PromptManager
import subprocess
import sys

def load_file_operation_fix_prompt():
    """ファイル操作改善プロンプトを読み込み"""
    fix_file = Path("../../codecrafter/prompts/system_prompts/phase1_file_operation_fix.yaml")
    
    if not fix_file.exists():
        print(f"エラー: {fix_file} が見つかりません")
        return None
    
    try:
        with open(fix_file, 'r', encoding='utf-8') as f:
            content = yaml.safe_load(f)
        print(f"ファイル操作改善プロンプトを読み込みました: {len(content)} セクション")
        return content
    except Exception as e:
        print(f"プロンプトファイル読み込みエラー: {e}")
        return None

def apply_file_operation_fix():
    """ファイル操作改善を適用"""
    
    # ファイル操作改善プロンプトを読み込み
    fix_prompt = load_file_operation_fix_prompt()
    if not fix_prompt:
        return False
    
    # PromptManager初期化
    manager = PromptManager("codecrafter/prompts/system_prompts")
    
    # 現行プロンプトを表示
    current = manager.load_current_prompt()
    print(f"\n現行プロンプト:")
    for key, value in current.items():
        print(f"  {key}: {str(value)[:80]}...")
    
    # ファイル操作改善内容の表示
    print(f"\n=== ファイル操作改善内容 ===")
    changes = [
        "ファイル操作と参照の強制実行ルール追加",
        "ファイル読み込み前の存在確認強制",
        "FILE_OPERATION形式でのファイル操作指示",
        "推測によるファイル情報提供の完全禁止",
        "実際のファイル内容に基づく分析の強制"
    ]
    
    for i, change in enumerate(changes, 1):
        print(f"  {i}. {change}")
    
    # 新バージョンとして保存
    version_id = manager.save_new_version(
        fix_prompt,
        changes,
        {
            "expected_file_accuracy": 95.0,      # ファイル参照精度の大幅改善
            "expected_data_reliability": 90.0,   # データ信頼性向上
            "expected_error_reduction": 80.0,    # ファイル関連エラー削減
            "expected_user_confidence": 85.0     # ユーザー信頼度向上
        }
    )
    
    print(f"\nファイル操作改善版を新バージョンとして保存: {version_id}")
    
    # バージョンを現行に適用
    if manager.apply_version(version_id):
        print(f"ファイル操作改善版を現行プロンプトに適用しました")
        
        # 適用後の確認
        updated_current = manager.load_current_prompt()
        print(f"\n適用後のプロンプト主要セクション:")
        for key in ["system_role", "file_operation_rules", "mandatory_response_pattern"]:
            if key in updated_current:
                preview = str(updated_current[key])[:150].replace('\n', ' ')
                print(f"  {key}: {preview}...")
        
        return True
    else:
        print(f"バージョン適用に失敗しました")
        return False

def test_file_operation_improvement():
    """ファイル操作改善をPromptSmithでテスト"""
    print(f"\nファイル操作改善効果をPromptSmithでテスト中...")
    try:
        result = subprocess.run([
            "uv", "run", "python", "orchestrator.py"
        ], capture_output=True, text=True, cwd=".", encoding='utf-8')
        
        if result.returncode == 0:
            print("PromptSmithテスト完了")
            # 重要な結果を表示
            lines = result.stdout.split('\n')
            for line in lines:
                if any(keyword in line for keyword in ['成功:', 'スコア:', '改善:', 'ファイル']):
                    print(f"  {line}")
            return True
        else:
            print("PromptSmithテストでエラーが発生")
            print(result.stderr[:500])
            return False
    except Exception as e:
        print(f"テスト実行エラー: {e}")
        return False

def main():
    """メイン実行関数"""
    print("=== ファイル操作改善プロンプト適用ツール ===")
    
    if apply_file_operation_fix():
        print(f"\n🎯 ファイル操作改善が完了しました!")
        
        print(f"\n次のステップ:")
        print(f"1. 実際のファイル参照テストの実行")
        print(f"2. PromptSmithによる効果測定")
        print(f"3. ファイル読み込み精度の確認")
        
        # PromptSmithテストの実行
        test_response = input("\nPromptSmithテストを実行しますか？ (y/N): ").lower().strip()
        
        if test_response == 'y':
            if test_file_operation_improvement():
                print(f"\n✅ ファイル操作改善効果の測定が完了しました!")
            else:
                print(f"\n⚠️ テスト実行に問題がありましたが、改善は適用されました")
        
    else:
        print(f"❌ ファイル操作改善の適用に失敗しました")
        sys.exit(1)

if __name__ == "__main__":
    main()