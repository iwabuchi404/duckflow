"""
ファイル操作改善プロンプトの実際のテスト

実際のファイル内容を参照させて、
AIが正確にデータを読み取れるかを確認します。
"""

from codecrafter.main import DuckflowAgent
from codecrafter.base.config import config_manager
import tempfile
import os

def create_test_files():
    """テスト用ファイルを作成"""
    test_dir = "temp_test_files"
    os.makedirs(test_dir, exist_ok=True)
    
    # テストファイル1: 設定ファイル
    config_content = """
# アプリケーション設定
app_name = "TestApp"
version = "1.2.3"
database_url = "sqlite:///test.db"
debug_mode = true
max_users = 1000

# API設定
api_endpoints = {
    "users": "/api/v1/users",
    "products": "/api/v1/products"
}
"""
    
    with open(f"{test_dir}/config.py", "w", encoding="utf-8") as f:
        f.write(config_content)
    
    # テストファイル2: データファイル
    data_content = """name,age,city,score
田中太郎,25,東京,85
佐藤花子,30,大阪,92
鈴木次郎,28,名古屋,78
高橋美咲,24,福岡,88
"""
    
    with open(f"{test_dir}/users.csv", "w", encoding="utf-8") as f:
        f.write(data_content)
    
    # テストファイル3: プロジェクト情報
    readme_content = """# TestProject

このプロジェクトは以下の機能を提供します：

## 主な機能
1. ユーザー管理システム
2. データ分析ツール
3. レポート生成機能

## 技術スタック
- Python 3.9+
- FastAPI
- SQLite
- Pandas

## インストール
```bash
pip install -r requirements.txt
```

## 実行
```bash
python main.py
```
"""
    
    with open(f"{test_dir}/README.md", "w", encoding="utf-8") as f:
        f.write(readme_content)
    
    return test_dir

def test_file_reading_scenarios():
    """ファイル読み込みテストシナリオ"""
    
    # テストファイル作成
    test_dir = create_test_files()
    
    print("=== ファイル操作テストシナリオ ===")
    print(f"テストディレクトリ: {test_dir}")
    print(f"作成されたファイル:")
    print(f"  - {test_dir}/config.py (設定ファイル)")
    print(f"  - {test_dir}/users.csv (データファイル)")  
    print(f"  - {test_dir}/README.md (プロジェクト情報)")
    
    # テストシナリオの提案
    print(f"\n推奨テストシナリオ:")
    print(f"")
    print(f"1. 【設定ファイル分析】")
    print(f"   「{test_dir}/config.py ファイルの内容を分析して、")
    print(f"    アプリケーションの設定をまとめてください」")
    print(f"")
    print(f"2. 【データファイル解析】") 
    print(f"   「{test_dir}/users.csv のデータを読み込んで、")
    print(f"    ユーザーの平均年齢と最高スコアを教えてください」")
    print(f"")
    print(f"3. 【プロジェクト情報要約】")
    print(f"   「{test_dir}/README.md を読んで、")
    print(f"    このプロジェクトの概要を3行で説明してください」")
    print(f"")
    
    # 改善前後の予想結果
    print(f"期待される改善:")
    print(f"")
    print(f"【改善前（推測ベース）】")
    print(f"  - 存在しないファイル情報を推測で回答")
    print(f"  - 一般的な内容を想像して回答")
    print(f"  - 具体的なデータ値を提供できない")
    print(f"")
    print(f"【改善後（実際のデータ）】")
    print(f"  - 実際のファイル内容を正確に参照")
    print(f"  - 具体的な設定値やデータを提供")
    print(f"  - ファイルが見つからない場合は正直に報告")
    
    return test_dir

def cleanup_test_files(test_dir):
    """テストファイルの削除"""
    import shutil
    try:
        shutil.rmtree(test_dir)
        print(f"\nテストファイルを削除しました: {test_dir}")
    except Exception as e:
        print(f"テストファイル削除でエラー: {e}")

if __name__ == "__main__":
    # テストファイル作成
    test_dir = create_test_files()
    
    print(f"\nテスト実行方法:")
    print(f"1. Duckflow を起動")
    print(f"2. 上記のテストシナリオを実行")
    print(f"3. AIの応答を確認")
    print(f"4. ファイル読み込みが正確かチェック")
    
    # ユーザーに削除確認
    response = input(f"\nテストファイルを削除しますか？ (y/N): ").lower().strip()
    if response == 'y':
        cleanup_test_files(test_dir)
    else:
        print(f"テストファイルは残されました: {test_dir}")