"""
Phase 1改善プロンプトをDuckflowの現行システムに適用するスクリプト

Phase1_improved.yamlの内容をPromptManagerを通じて適用し、
改善効果をPromptSmithでテストします。
"""

import yaml
from pathlib import Path
from prompt_manager import PromptManager
import sys

def load_phase1_improved_prompt():
    """Phase 1改善プロンプトを読み込み"""
    phase1_file = Path("codecrafter/prompts/system_prompts/phase1_improved.yaml")
    
    if not phase1_file.exists():
        print(f"エラー: {phase1_file} が見つかりません")
        return None
    
    try:
        with open(phase1_file, 'r', encoding='utf-8') as f:
            content = yaml.safe_load(f)
        print(f"Phase 1改善プロンプトを読み込みました: {len(content)} セクション")
        return content
    except Exception as e:
        print(f"プロンプトファイル読み込みエラー: {e}")
        return None

def apply_improvements():
    """Phase 1改善をPromptManagerに適用"""
    
    # Phase 1改善プロンプトを読み込み
    improved_prompt = load_phase1_improved_prompt()
    if not improved_prompt:
        return False
    
    # PromptManager初期化
    manager = PromptManager("codecrafter/prompts/system_prompts")
    
    # 現行プロンプトを表示
    current = manager.load_current_prompt()
    print(f"\n現行プロンプト:")
    for key, value in current.items():
        print(f"  {key}: {value[:100]}...")
    
    # 改善内容の詳細表示
    print(f"\n=== Phase 1改善内容 ===")
    changes = [
        "タスク分類システムの導入（5種類のタスクタイプ識別）",
        "適応的確認質問システム（タスクタイプ別専用質問）",
        "段階的アプローチシステム（3段階の実行フェーズ）",
        "構造化された応答形式の強制",
        "推測による実装の禁止強化"
    ]
    
    for i, change in enumerate(changes, 1):
        print(f"  {i}. {change}")
    
    # 新バージョンとして保存
    version_id = manager.save_new_version(
        improved_prompt,
        changes,
        {
            "expected_intent_understanding_rate": 40.0,  # 0.06 → 0.40への改善を期待
            "expected_question_quality": 70.0,         # 0.0 → 0.7への改善を期待
            "expected_communication_efficiency": 50.0,  # 0.0 → 0.5への改善を期待
            "expected_total_score": 30.0              # 0.0 → 30点への改善を期待
        }
    )
    
    print(f"\nPhase 1改善版を新バージョンとして保存: {version_id}")
    
    # バージョンを現行に適用
    if manager.apply_version(version_id):
        print(f"✅ Phase 1改善版を現行プロンプトに適用しました")
        
        # 適用後の現行プロンプトを確認
        updated_current = manager.load_current_prompt()
        print(f"\n適用後のプロンプト主要セクション:")
        for key in ["system_role", "task_classification", "task_understanding"]:
            if key in updated_current:
                preview = updated_current[key][:150].replace('\n', ' ')
                print(f"  {key}: {preview}...")
        
        return True
    else:
        print(f"❌ バージョン適用に失敗しました")
        return False

def main():
    """メイン実行関数"""
    print("=== Phase 1改善プロンプト適用ツール ===")
    
    if apply_improvements():
        print(f"\n🎯 Phase 1改善が完了しました!")
        print(f"\n次のステップ:")
        print(f"1. PromptSmithテストの実行")
        print(f"2. 改善効果の測定")
        print(f"3. 追加調整の検討")
        
        # PromptSmithテストの提案
        print(f"\nPromptSmithテストを実行しますか？")
        response = input("y/N: ").lower().strip()
        
        if response == 'y':
            print("PromptSmithテストを実行中...")
            import subprocess
            try:
                result = subprocess.run([
                    "uv", "run", "python", "codecrafter/promptsmith/orchestrator.py"
                ], capture_output=True, text=True, cwd=".", encoding='utf-8')
                
                if result.returncode == 0:
                    print("✅ PromptSmithテスト完了")
                    print(result.stdout)
                else:
                    print("❌ PromptSmithテストでエラーが発生")
                    print(result.stderr)
            except Exception as e:
                print(f"テスト実行エラー: {e}")
    else:
        print(f"❌ Phase 1改善の適用に失敗しました")
        sys.exit(1)

if __name__ == "__main__":
    main()