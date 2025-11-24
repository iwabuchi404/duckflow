#!/usr/bin/env python3
"""
PlanTool デモスクリプト

PlanToolの基本的な使用方法を示すデモンストレーション
"""

import tempfile
import shutil
from pathlib import Path

from companion.enhanced_core import EnhancedCompanionCore
from companion.plan_tool import PlanTool
from companion.collaborative_planner import ActionSpec


def demo_basic_plan_tool():
    """基本的なPlanToolの使用例"""
    print("=== PlanTool 基本デモ ===")
    
    # 一時ディレクトリでデモ実行
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"作業ディレクトリ: {temp_dir}")
        
        # PlanTool初期化
        plan_tool = PlanTool(logs_dir=temp_dir, allow_external_paths=True)
        
        # 1. プラン提案
        print("\n1. プラン提案")
        plan_id = plan_tool.propose(
            content="""# Webアプリケーション作成プラン

## 概要
シンプルなWebアプリケーションを作成します。

## 実装手順
1. プロジェクトディレクトリ作成
2. HTMLファイル作成
3. CSSファイル作成
4. JavaScriptファイル作成
5. 設定ファイル作成

## 期待される成果物
- index.html
- style.css
- script.js
- config.json
""",
            sources=[],
            rationale="学習目的でのWebアプリケーション作成",
            tags=["web", "demo", "learning"]
        )
        print(f"プラン作成完了: {plan_id}")
        
        # 2. ActionSpec設定
        print("\n2. ActionSpec設定")
        project_dir = Path(temp_dir) / "webapp_demo"
        specs = [
            ActionSpec(
                kind='mkdir',
                path=str(project_dir),
                description='プロジェクトディレクトリ作成'
            ),
            ActionSpec(
                kind='create',
                path=str(project_dir / "index.html"),
                content="""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Demo Web App</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <h1>PlanTool Demo Web App</h1>
    <p>このアプリはPlanToolによって作成されました。</p>
    <button id="demo-button">クリックしてください</button>
    <script src="script.js"></script>
</body>
</html>""",
                description='メインHTMLファイル作成'
            ),
            ActionSpec(
                kind='create',
                path=str(project_dir / "style.css"),
                content="""body {
    font-family: Arial, sans-serif;
    max-width: 800px;
    margin: 0 auto;
    padding: 20px;
    background-color: #f5f5f5;
}

h1 {
    color: #333;
    text-align: center;
}

button {
    background-color: #007bff;
    color: white;
    border: none;
    padding: 10px 20px;
    border-radius: 5px;
    cursor: pointer;
    font-size: 16px;
}

button:hover {
    background-color: #0056b3;
}""",
                description='スタイルシート作成'
            ),
            ActionSpec(
                kind='create',
                path=str(project_dir / "script.js"),
                content="""document.addEventListener('DOMContentLoaded', function() {
    const button = document.getElementById('demo-button');
    
    button.addEventListener('click', function() {
        alert('PlanToolデモが正常に動作しています！');
    });
});""",
                description='JavaScriptファイル作成'
            ),
            ActionSpec(
                kind='create',
                path=str(project_dir / "config.json"),
                content="""{
    "app_name": "PlanTool Demo Web App",
    "version": "1.0.0",
    "created_by": "PlanTool",
    "description": "PlanToolによって自動生成されたWebアプリケーション"
}""",
                description='設定ファイル作成'
            )
        ]
        
        validation_result = plan_tool.set_action_specs(plan_id, specs)
        print(f"ActionSpec設定完了: {validation_result.ok}")
        if not validation_result.ok:
            print(f"バリデーションエラー: {validation_result.issues}")
            return
        
        # 3. プレビュー
        print("\n3. プレビュー")
        preview = plan_tool.preview(plan_id)
        print(f"対象ファイル数: {len(preview.files)}")
        print(f"リスクスコア: {preview.risk_score:.2f}")
        for file_path in preview.files:
            print(f"  - {file_path}")
        
        # 4. 承認
        print("\n4. 承認")
        from companion.plan_tool import SpecSelection
        selection = SpecSelection(all=True)
        
        approval_id = plan_tool.request_approval(plan_id, selection)
        print(f"承認要求ID: {approval_id}")
        
        approved = plan_tool.approve(plan_id, "demo_user", selection)
        print(f"承認完了: {approved['plan_id']}")
        
        # 5. 実行
        print("\n5. 実行")
        result = plan_tool.execute(plan_id)
        print(f"実行結果: {'成功' if result.overall_success else '失敗'}")
        print(f"実行件数: {len(result.results)}")
        
        for i, res in enumerate(result.results, 1):
            status = "✓" if res['success'] else "✗"
            print(f"  {status} {i}. {res['kind']} {res['path']}")
        
        # 6. 結果確認
        print("\n6. 結果確認")
        if project_dir.exists():
            print(f"プロジェクトディレクトリ作成: ✓")
            files = list(project_dir.glob("*"))
            print(f"作成されたファイル数: {len(files)}")
            for file_path in files:
                print(f"  - {file_path.name} ({file_path.stat().st_size} bytes)")
        
        print(f"\n作成されたWebアプリケーションは {project_dir} にあります。")
        print("index.htmlをブラウザで開いて動作確認してください。")


def demo_enhanced_core_integration():
    """EnhancedCore統合デモ"""
    print("\n\n=== EnhancedCore統合デモ ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"作業ディレクトリ: {temp_dir}")
        
        # EnhancedCore初期化
        enhanced_core = EnhancedCompanionCore()
        enhanced_core.plan_tool = PlanTool(logs_dir=temp_dir, allow_external_paths=True)
        
        # 1. 高レベルAPIでプラン作成
        print("\n1. 高レベルAPIでプラン作成")
        plan_id = enhanced_core.propose_plan(
            content="# Python スクリプト作成プラン\n- Hello World スクリプト作成\n- 実行テスト",
            rationale="Python学習用",
            tags=["python", "learning"]
        )
        print(f"プラン作成: {plan_id}")
        
        # 2. ActionSpec設定（辞書形式）
        print("\n2. ActionSpec設定")
        script_path = Path(temp_dir) / "hello_world.py"
        specs = [
            {
                'kind': 'create',
                'path': str(script_path),
                'content': '''#!/usr/bin/env python3
"""
Hello World スクリプト
PlanToolによって自動生成
"""

def main():
    print("Hello, World from PlanTool!")
    print("このスクリプトはPlanToolによって作成されました。")
    
    # 簡単な計算デモ
    numbers = [1, 2, 3, 4, 5]
    total = sum(numbers)
    print(f"数値の合計: {total}")
    
    # ファイル情報表示
    import os
    print(f"スクリプトサイズ: {os.path.getsize(__file__)} bytes")

if __name__ == "__main__":
    main()
''',
                'description': 'Hello World Pythonスクリプト'
            }
        ]
        
        result = enhanced_core.set_plan_action_specs(plan_id, specs)
        print(f"ActionSpec設定: {'成功' if result['ok'] else '失敗'}")
        
        # 3. ワンステップ承認・実行
        print("\n3. 承認・実行")
        approval_result = enhanced_core.approve_plan(plan_id)
        print(f"承認: {approval_result['plan_id']}")
        
        execution_result = enhanced_core.execute_plan(plan_id)
        print(f"実行: {'成功' if execution_result['success'] else '失敗'}")
        
        # 4. 結果確認
        print("\n4. 結果確認")
        if script_path.exists():
            print(f"スクリプト作成: ✓")
            print(f"ファイルサイズ: {script_path.stat().st_size} bytes")
            
            # スクリプト実行テスト
            print("\n5. スクリプト実行テスト")
            import subprocess
            try:
                result = subprocess.run(
                    ['python', str(script_path)], 
                    capture_output=True, 
                    text=True,
                    cwd=temp_dir
                )
                print("実行結果:")
                print(result.stdout)
                if result.stderr:
                    print("エラー:")
                    print(result.stderr)
            except Exception as e:
                print(f"実行エラー: {e}")
        
        # 6. プラン一覧表示
        print("\n6. プラン一覧")
        plans = enhanced_core.list_plans()
        for plan in plans:
            print(f"  - {plan['title']} ({plan['status']}) - {plan['action_count']}件")


def demo_legacy_compatibility():
    """レガシー互換性デモ"""
    print("\n\n=== レガシー互換性デモ ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        enhanced_core = EnhancedCompanionCore()
        enhanced_core.plan_tool = PlanTool(logs_dir=temp_dir, allow_external_paths=True)
        
        # 従来のset_plan_state使用
        print("\n1. 従来のset_plan_state使用")
        plan_content = """# レガシー互換性テストプラン

## 目的
従来のset_plan_stateメソッドがPlanToolと統合されていることを確認

## 手順
1. set_plan_stateでプラン設定
2. PlanToolでプラン確認
3. 状態の整合性確認
"""
        
        enhanced_core.set_plan_state(plan_content, "legacy_test")
        
        # 2. 状態確認
        print("\n2. 状態確認")
        legacy_state = enhanced_core.get_plan_state()
        print(f"レガシー状態 - pending: {legacy_state['pending']}")
        print(f"レガシー状態 - plan_type: {legacy_state['plan_type']}")
        print(f"PlanTool統合 - plan_id: {legacy_state.get('plan_id', 'なし')}")
        
        # 3. PlanTool側での確認
        print("\n3. PlanTool側での確認")
        current_plan = enhanced_core.get_current_plan()
        if current_plan:
            print(f"現在のプラン: {current_plan['title']}")
            print(f"ステータス: {current_plan['status']}")
        else:
            print("現在のプランなし")
        
        # 4. クリア動作確認
        print("\n4. クリア動作確認")
        enhanced_core.clear_plan_state()
        
        cleared_state = enhanced_core.get_plan_state()
        print(f"クリア後 - pending: {cleared_state['pending']}")
        
        current_after_clear = enhanced_core.get_current_plan()
        print(f"クリア後のPlanTool: {'なし' if not current_after_clear else current_after_clear['title']}")


if __name__ == "__main__":
    print("PlanTool デモンストレーション")
    print("=" * 50)
    
    try:
        # 基本デモ
        demo_basic_plan_tool()
        
        # 統合デモ
        demo_enhanced_core_integration()
        
        # 互換性デモ
        demo_legacy_compatibility()
        
        print("\n" + "=" * 50)
        print("デモ完了！")
        print("\nPlanToolの主な機能:")
        print("✓ プラン提案・管理")
        print("✓ ActionSpec設定・バリデーション")
        print("✓ リスク評価・プレビュー")
        print("✓ 承認ワークフロー")
        print("✓ 安全な実行")
        print("✓ 永続化・履歴管理")
        print("✓ EnhancedCore統合")
        print("✓ レガシー互換性")
        
    except Exception as e:
        print(f"\nデモ実行エラー: {e}")
        import traceback
        traceback.print_exc()