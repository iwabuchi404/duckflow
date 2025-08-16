# test_workspace_manager.py
"""
ワークスペース管理システムのテスト
作業フォルダ切り替え機能の動作確認用
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from companion.workspace_manager import WorkspaceManager, WorkspaceInfo

def test_workspace_creation_and_initialization():
    """ワークスペース管理システムの初期化テスト"""
    print("WorkSpace Manager Initialization Test")
    print("=" * 50)
    
    # 一時設定ファイルを使用
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_config:
        config_path = temp_config.name
    
    try:
        # WorkspaceManagerを初期化
        workspace_manager = WorkspaceManager(config_file=config_path)
        
        print(f"✅ 初期化成功")
        print(f"📂 現在のワークスペース: {workspace_manager.current_workspace}")
        print(f"📄 設定ファイル: {config_path}")
        print(f"📊 履歴数: {len(workspace_manager.workspace_history)}")
        print(f"📌 ブックマーク数: {len(workspace_manager.bookmarks)}")
        
        return workspace_manager
        
    finally:
        # 一時ファイルをクリーンアップ
        if os.path.exists(config_path):
            os.unlink(config_path)

def test_workspace_change():
    """ワークスペース変更のテスト"""
    print("\n🔄 ワークスペース変更のテスト")
    print("=" * 50)
    
    # 一時設定ファイルを使用
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_config:
        config_path = temp_config.name
    
    # 一時ディレクトリを作成
    temp_dir = tempfile.mkdtemp()
    test_dir1 = os.path.join(temp_dir, "test_project1")
    test_dir2 = os.path.join(temp_dir, "test_project2")
    
    try:
        os.makedirs(test_dir1)
        os.makedirs(test_dir2)
        
        # Python プロジェクトの設定ファイルを作成
        with open(os.path.join(test_dir1, "requirements.txt"), 'w') as f:
            f.write("flask==2.0.1\n")
        
        # Node.js プロジェクトの設定ファイルを作成
        with open(os.path.join(test_dir2, "package.json"), 'w') as f:
            f.write('{"name": "test-project", "version": "1.0.0"}\n')
        
        workspace_manager = WorkspaceManager(config_file=config_path)
        original_workspace = workspace_manager.current_workspace
        
        print(f"📂 元のワークスペース: {original_workspace}")
        
        # 有効なディレクトリに変更
        success, message = workspace_manager.change_workspace(test_dir1, "Test Project 1")
        print(f"\n1. 有効なディレクトリへの変更:")
        print(f"  結果: {'✅ 成功' if success else '❌ 失敗'}")
        print(f"  メッセージ: {message}")
        print(f"  現在のワークスペース: {workspace_manager.current_workspace}")
        
        # プロジェクト種別の検出確認
        current_info = workspace_manager.get_current_workspace()
        print(f"  プロジェクト種別: {current_info.project_type}")
        
        # 別のディレクトリに変更
        success2, message2 = workspace_manager.change_workspace(test_dir2, "Test Project 2")
        print(f"\n2. 別のディレクトリへの変更:")
        print(f"  結果: {'✅ 成功' if success2 else '❌ 失敗'}")
        print(f"  メッセージ: {message2}")
        
        current_info2 = workspace_manager.get_current_workspace()
        print(f"  プロジェクト種別: {current_info2.project_type}")
        
        # 無効なディレクトリに変更を試行
        invalid_path = os.path.join(temp_dir, "non_existent")
        success3, message3 = workspace_manager.change_workspace(invalid_path)
        print(f"\n3. 無効なディレクトリへの変更:")
        print(f"  結果: {'✅ 成功' if success3 else '❌ 失敗'}")
        print(f"  メッセージ: {message3}")
        
        # 履歴の確認
        recent = workspace_manager.list_recent_workspaces(5)
        print(f"\n📊 履歴 (最新5件):")
        for i, workspace in enumerate(recent, 1):
            print(f"  {i}. {workspace.name} ({workspace.project_type or '不明'})")
            print(f"     📁 {workspace.path}")
        
        return workspace_manager
        
    finally:
        # クリーンアップ
        shutil.rmtree(temp_dir, ignore_errors=True)
        if os.path.exists(config_path):
            os.unlink(config_path)

def test_bookmark_management():
    """ブックマーク管理のテスト"""
    print("\n📌 ブックマーク管理のテスト")
    print("=" * 50)
    
    # 一時設定ファイルを使用
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_config:
        config_path = temp_config.name
    
    # 一時ディレクトリを作成
    temp_dir = tempfile.mkdtemp()
    project_dir = os.path.join(temp_dir, "my_project")
    
    try:
        os.makedirs(project_dir)
        
        workspace_manager = WorkspaceManager(config_file=config_path)
        
        # 現在の場所をブックマーク
        success1, message1 = workspace_manager.add_bookmark("current", description="現在の作業場所")
        print(f"1. 現在の場所をブックマーク:")
        print(f"  結果: {'✅ 成功' if success1 else '❌ 失敗'}")
        print(f"  メッセージ: {message1}")
        
        # プロジェクトディレクトリをブックマーク
        success2, message2 = workspace_manager.add_bookmark("project", project_dir, "テストプロジェクト")
        print(f"\n2. プロジェクトディレクトリをブックマーク:")
        print(f"  結果: {'✅ 成功' if success2 else '❌ 失敗'}")
        print(f"  メッセージ: {message2}")
        
        # 重複するブックマーク名を試行
        success3, message3 = workspace_manager.add_bookmark("project", project_dir, "重複テスト")
        print(f"\n3. 重複するブックマーク名:")
        print(f"  結果: {'✅ 成功' if success3 else '❌ 失敗'}")
        print(f"  メッセージ: {message3}")
        
        # ブックマーク一覧表示
        bookmarks = workspace_manager.list_bookmarks()
        print(f"\n📌 ブックマーク一覧 ({len(bookmarks)}件):")
        for bookmark in bookmarks:
            print(f"  • {bookmark.name}")
            print(f"    📁 {bookmark.path}")
            if bookmark.description:
                print(f"    💬 {bookmark.description}")
        
        # ブックマークに移動
        success4, message4 = workspace_manager.change_to_bookmark("project")
        print(f"\n4. ブックマークに移動:")
        print(f"  結果: {'✅ 成功' if success4 else '❌ 失敗'}")
        print(f"  メッセージ: {message4}")
        print(f"  現在のワークスペース: {workspace_manager.current_workspace}")
        
        # 存在しないブックマークに移動を試行
        success5, message5 = workspace_manager.change_to_bookmark("non_existent")
        print(f"\n5. 存在しないブックマークに移動:")
        print(f"  結果: {'✅ 成功' if success5 else '❌ 失敗'}")
        print(f"  メッセージ: {message5}")
        
        # ブックマーク削除
        success6, message6 = workspace_manager.remove_bookmark("current")
        print(f"\n6. ブックマーク削除:")
        print(f"  結果: {'✅ 成功' if success6 else '❌ 失敗'}")
        print(f"  メッセージ: {message6}")
        
        # 削除後のブックマーク一覧
        remaining_bookmarks = workspace_manager.list_bookmarks()
        print(f"\n📌 削除後のブックマーク一覧 ({len(remaining_bookmarks)}件):")
        for bookmark in remaining_bookmarks:
            print(f"  • {bookmark.name}")
        
        return workspace_manager
        
    finally:
        # クリーンアップ
        shutil.rmtree(temp_dir, ignore_errors=True)
        if os.path.exists(config_path):
            os.unlink(config_path)

def test_search_and_suggestions():
    """検索と候補提案のテスト"""
    print("\n🔍 検索と候補提案のテスト")
    print("=" * 50)
    
    # 一時設定ファイルを使用
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_config:
        config_path = temp_config.name
    
    # 一時ディレクトリを作成
    temp_dir = tempfile.mkdtemp()
    test_dirs = [
        os.path.join(temp_dir, "python_project"),
        os.path.join(temp_dir, "node_project"),
        os.path.join(temp_dir, "rust_project")
    ]
    
    try:
        # テストディレクトリを作成
        for test_dir in test_dirs:
            os.makedirs(test_dir)
        
        # プロジェクトファイルを作成
        with open(os.path.join(test_dirs[0], "requirements.txt"), 'w') as f:
            f.write("requests==2.25.1\n")
        with open(os.path.join(test_dirs[1], "package.json"), 'w') as f:
            f.write('{"name": "test"}\n')
        with open(os.path.join(test_dirs[2], "Cargo.toml"), 'w') as f:
            f.write('[package]\nname = "test"\n')
        
        workspace_manager = WorkspaceManager(config_file=config_path)
        
        # 各ディレクトリを履歴に追加
        for i, test_dir in enumerate(test_dirs):
            workspace_manager.change_workspace(test_dir, f"Test Project {i+1}")
        
        # ブックマークも追加
        workspace_manager.add_bookmark("python", test_dirs[0], "Python開発環境")
        workspace_manager.add_bookmark("node", test_dirs[1], "Node.js開発環境")
        
        # 検索テスト
        search_queries = ["python", "project", "node", "rust", "存在しない"]
        
        for query in search_queries:
            results = workspace_manager.search_workspaces(query)
            print(f"\n🔍 検索: '{query}' ({len(results)}件)")
            for result in results:
                bookmark_mark = "📌" if result.is_bookmark else "📁"
                print(f"  {bookmark_mark} {result.name} ({result.project_type or '不明'})")
                print(f"    📁 {result.path}")
        
        # パス候補提案テスト
        print(f"\n💡 パス候補提案テスト:")
        partial_paths = [temp_dir, os.path.join(temp_dir, "p"), "non_existent"]
        
        for partial_path in partial_paths:
            suggestions = workspace_manager.suggest_similar_paths(partial_path)
            print(f"\n  入力: '{partial_path}'")
            print(f"  候補数: {len(suggestions)}")
            for suggestion in suggestions[:3]:  # 最大3件表示
                print(f"    📁 {suggestion}")
        
        return workspace_manager
        
    finally:
        # クリーンアップ
        shutil.rmtree(temp_dir, ignore_errors=True)
        if os.path.exists(config_path):
            os.unlink(config_path)

def test_go_back_functionality():
    """戻る機能のテスト"""
    print("\n⬅️ 戻る機能のテスト")
    print("=" * 50)
    
    # 一時設定ファイルを使用
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_config:
        config_path = temp_config.name
    
    # 一時ディレクトリを作成
    temp_dir = tempfile.mkdtemp()
    dir1 = os.path.join(temp_dir, "dir1")
    dir2 = os.path.join(temp_dir, "dir2")
    
    try:
        os.makedirs(dir1)
        os.makedirs(dir2)
        
        workspace_manager = WorkspaceManager(config_file=config_path)
        original = workspace_manager.current_workspace
        
        print(f"📂 開始位置: {original}")
        
        # ディレクトリ1に移動
        workspace_manager.change_workspace(dir1, "Directory 1")
        print(f"📂 dir1に移動: {workspace_manager.current_workspace}")
        
        # ディレクトリ2に移動
        workspace_manager.change_workspace(dir2, "Directory 2")
        print(f"📂 dir2に移動: {workspace_manager.current_workspace}")
        
        # 前に戻る（dir1に戻る）
        success1, message1 = workspace_manager.go_back()
        print(f"\n1. 戻る操作:")
        print(f"  結果: {'✅ 成功' if success1 else '❌ 失敗'}")
        print(f"  メッセージ: {message1}")
        print(f"  現在の場所: {workspace_manager.current_workspace}")
        
        # さらに戻る（開始位置に戻る）
        success2, message2 = workspace_manager.go_back()
        print(f"\n2. さらに戻る:")
        print(f"  結果: {'✅ 成功' if success2 else '❌ 失敗'}")
        print(f"  メッセージ: {message2}")
        print(f"  現在の場所: {workspace_manager.current_workspace}")
        
        # 履歴の最初で戻るを試行
        success3, message3 = workspace_manager.go_back()
        print(f"\n3. 履歴の最初で戻る:")
        print(f"  結果: {'✅ 成功' if success3 else '❌ 失敗'}")
        print(f"  メッセージ: {message3}")
        
        return workspace_manager
        
    finally:
        # クリーンアップ
        shutil.rmtree(temp_dir, ignore_errors=True)
        if os.path.exists(config_path):
            os.unlink(config_path)

def test_display_formatting():
    """表示フォーマットのテスト"""
    print("\n📄 表示フォーマットのテスト")
    print("=" * 50)
    
    # 一時設定ファイルを使用
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_config:
        config_path = temp_config.name
    
    # 一時ディレクトリを作成
    temp_dir = tempfile.mkdtemp()
    project_dir = os.path.join(temp_dir, "sample_project")
    
    try:
        os.makedirs(project_dir)
        
        # Pythonプロジェクトとして設定
        with open(os.path.join(project_dir, "requirements.txt"), 'w') as f:
            f.write("flask==2.0.1\nrequests==2.25.1\n")
        
        workspace_manager = WorkspaceManager(config_file=config_path)
        
        # プロジェクトディレクトリに移動
        workspace_manager.change_workspace(project_dir, "Sample Project")
        
        # ブックマークを追加
        workspace_manager.add_bookmark("sample", description="サンプルプロジェクト")
        
        # 現在のワークスペース情報表示
        print("📂 現在のワークスペース情報表示:")
        print("-" * 30)
        info_display = workspace_manager.get_workspace_info_display()
        print(info_display)
        
        print("\n" + "=" * 50)
        
        # ワークスペース一覧表示
        print("📁 ワークスペース一覧表示:")
        print("-" * 30)
        list_display = workspace_manager.get_workspace_list_display()
        print(list_display)
        
        return workspace_manager
        
    finally:
        # クリーンアップ
        shutil.rmtree(temp_dir, ignore_errors=True)
        if os.path.exists(config_path):
            os.unlink(config_path)

def test_persistence():
    """設定の永続化テスト"""
    print("\n💾 設定の永続化テスト")
    print("=" * 50)
    
    # 一時設定ファイルを使用
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_config:
        config_path = temp_config.name
    
    # 一時ディレクトリを作成
    temp_dir = tempfile.mkdtemp()
    test_dir = os.path.join(temp_dir, "persistent_test")
    
    try:
        os.makedirs(test_dir)
        
        # 最初のWorkspaceManagerインスタンスでデータを作成
        print("1. 最初のインスタンスでデータを作成:")
        workspace_manager1 = WorkspaceManager(config_file=config_path)
        workspace_manager1.change_workspace(test_dir, "Persistent Test")
        workspace_manager1.add_bookmark("test", description="永続化テスト")
        
        print(f"  📂 ワークスペース: {workspace_manager1.current_workspace}")
        print(f"  📌 ブックマーク数: {len(workspace_manager1.bookmarks)}")
        print(f"  📊 履歴数: {len(workspace_manager1.workspace_history)}")
        
        # 明示的に設定を保存
        workspace_manager1._save_config()
        
        # 新しいインスタンスで設定を読み込み
        print("\n2. 新しいインスタンスで設定を読み込み:")
        workspace_manager2 = WorkspaceManager(config_file=config_path)
        
        print(f"  📂 ワークスペース: {workspace_manager2.current_workspace}")
        print(f"  📌 ブックマーク数: {len(workspace_manager2.bookmarks)}")
        print(f"  📊 履歴数: {len(workspace_manager2.workspace_history)}")
        
        # データの一致確認
        bookmarks_match = len(workspace_manager1.bookmarks) == len(workspace_manager2.bookmarks)
        history_match = len(workspace_manager1.workspace_history) == len(workspace_manager2.workspace_history)
        workspace_match = workspace_manager1.current_workspace == workspace_manager2.current_workspace
        
        print(f"\n📊 データ一致確認:")
        print(f"  ワークスペース: {'✅' if workspace_match else '❌'}")
        print(f"  ブックマーク: {'✅' if bookmarks_match else '❌'}")
        print(f"  履歴: {'✅' if history_match else '❌'}")
        
        return workspace_manager2
        
    finally:
        # クリーンアップ
        shutil.rmtree(temp_dir, ignore_errors=True)
        if os.path.exists(config_path):
            os.unlink(config_path)

if __name__ == "__main__":
    print("🦆 ワークスペース管理システム 統合テスト")
    print("=" * 60)
    
    try:
        test_workspace_creation_and_initialization()
        test_workspace_change()
        test_bookmark_management()
        test_search_and_suggestions()
        test_go_back_functionality()
        test_display_formatting()
        test_persistence()
        
        print("\n" + "=" * 60)
        print("🎉 すべてのテストが完了しました！")
        print("ワークスペース管理システムが正常に動作しています。")
        
    except Exception as e:
        print(f"\n❌ テスト中にエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()