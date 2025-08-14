"""
Phase 1緊急修正プロンプトの適用とテスト

より直接的で強制力のあるプロンプト構造を適用し、
PromptSmithで改善効果を測定します。
"""

import yaml
from pathlib import Path
from prompt_manager import PromptManager
import subprocess
import sys

def load_critical_fix_prompt():
    """緊急修正プロンプトを読み込み"""
    # 現在のディレクトリから相対パスで指定
    fix_file = Path("../../codecrafter/prompts/system_prompts/phase1_critical_fix.yaml")
    
    if not fix_file.exists():
        print(f"エラー: {fix_file} が見つかりません")
        return None
    
    try:
        with open(fix_file, 'r', encoding='utf-8') as f:
            content = yaml.safe_load(f)
        print(f"緊急修正プロンプトを読み込みました: {len(content)} セクション")
        return content
    except Exception as e:
        print(f"プロンプトファイル読み込みエラー: {e}")
        return None

def apply_critical_fix():
    """緊急修正を適用"""
    
    # 緊急修正プロンプトを読み込み
    fix_prompt = load_critical_fix_prompt()
    if not fix_prompt:
        return False
    
    # PromptManager初期化
    manager = PromptManager("codecrafter/prompts/system_prompts")
    
    # 現行プロンプトを表示
    current = manager.load_current_prompt()
    print(f"\n現行プロンプト:")
    for key, value in current.items():
        print(f"  {key}: {str(value)[:80]}...")
    
    # 緊急修正内容の表示
    print(f"\n=== Phase 1緊急修正内容 ===")
    changes = [
        "強制実行パターンの導入（「了解しました」応答の完全禁止）",
        "必須確認質問の強制実行（4つの基本質問）",
        "タスク分類の強制実行（A～E分類）",
        "直接的で具体的な指示形式への変更",
        "推測による実装の完全禁止"
    ]
    
    for i, change in enumerate(changes, 1):
        print(f"  {i}. {change}")
    
    # 新バージョンとして保存
    version_id = manager.save_new_version(
        fix_prompt,
        changes,
        {
            "expected_intent_understanding_rate": 60.0,  # 大幅改善期待
            "expected_question_quality": 90.0,         # 強制質問で大幅向上期待
            "expected_communication_efficiency": 70.0,  # 構造化で向上期待
            "expected_total_score": 50.0              # 0.0 → 50点への大幅改善期待
        }
    )
    
    print(f"\nPhase 1緊急修正版を新バージョンとして保存: {version_id}")
    
    # バージョンを現行に適用
    if manager.apply_version(version_id):
        print(f"Phase 1緊急修正版を現行プロンプトに適用しました")
        
        # 適用後の確認
        updated_current = manager.load_current_prompt()
        print(f"\n適用後のプロンプト主要セクション:")
        for key in ["system_role", "mandatory_response_pattern", "task_classification_mandatory"]:
            if key in updated_current:
                preview = str(updated_current[key])[:100].replace('\n', ' ')
                print(f"  {key}: {preview}...")
        
        return True
    else:
        print(f"バージョン適用に失敗しました")
        return False

def run_promptsmith_test():
    """PromptSmithテストを実行"""
    print(f"\nPromptSmithテストを実行中...")
    try:
        result = subprocess.run([
            "uv", "run", "python", "orchestrator.py"
        ], capture_output=True, text=True, cwd="codecrafter/promptsmith", encoding='utf-8')
        
        if result.returncode == 0:
            print("PromptSmithテスト完了")
            # テスト結果の要約を表示
            lines = result.stdout.split('\n')
            for line in lines:
                if 'スコア:' in line or '成功率:' in line or '改善効果:' in line:
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
    print("=== Phase 1緊急修正適用ツール ===")
    
    if apply_critical_fix():
        print(f"\n Phase 1緊急修正が完了しました!")
        
        # 自動でPromptSmithテストを実行
        print(f"\n自動でPromptSmithテストを実行します...")
        
        if run_promptsmith_test():
            print(f"\n 緊急修正の効果測定が完了しました!")
            print(f"\n結果ファイル: codecrafter/promptsmith/promptsmith_results/")
        else:
            print(f"\nテスト実行に問題がありましたが、修正は適用されました")
        
        print(f"\n次のステップ:")
        print(f"1. テスト結果の詳細分析")
        print(f"2. さらなる調整の検討")
        print(f"3. Phase 2機能の実装準備")
        
    else:
        print(f"Phase 1緊急修正の適用に失敗しました")
        sys.exit(1)

if __name__ == "__main__":
    main()