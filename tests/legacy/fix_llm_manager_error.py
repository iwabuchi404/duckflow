#!/usr/bin/env python3
"""
LLMManager get_default_client エラー修正スクリプト

問題: 'LLMManager' object has no attribute 'get_default_client'
対応: 不足しているメソッドを追加し、キャッシュをクリアする
"""

import os
import sys
from pathlib import Path

def fix_llm_manager():
    """LLMManagerにget_default_clientメソッドを追加"""
    
    llm_client_path = Path("codecrafter/base/llm_client.py")
    
    if not llm_client_path.exists():
        print(f"❌ ファイルが見つかりません: {llm_client_path}")
        return False
    
    # ファイルを読み取り
    with open(llm_client_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # get_default_clientメソッドが既に存在するかチェック
    if 'def get_default_client(' in content:
        print("✅ get_default_clientメソッドは既に存在します")
        return True
    
    # LLMManagerクラスの最後にメソッドを追加
    method_to_add = '''
    def get_default_client(self) -> BaseLLMClient:
        """デフォルトクライアントを取得 (後方互換性のため)
        
        Returns:
            現在のメインクライアント
        """
        return self.current_client
    
    def get_client(self, client_type: str = "main") -> BaseLLMClient:
        """指定されたタイプのクライアントを取得
        
        Args:
            client_type: クライアントタイプ ("main" または "summary")
            
        Returns:
            指定されたクライアント
        """
        if client_type == "summary":
            return self.summary_client
        return self.current_client
'''
    
    # is_mock_clientメソッドの後に追加
    if 'def is_mock_client(self) -> bool:' in content:
        # is_mock_clientメソッドの終了位置を見つける
        lines = content.split('\n')
        insert_index = -1
        
        for i, line in enumerate(lines):
            if 'def is_mock_client(self) -> bool:' in line:
                # このメソッドの終了を見つける
                for j in range(i + 1, len(lines)):
                    if lines[j].strip() and not lines[j].startswith('    ') and not lines[j].startswith('\t'):
                        insert_index = j
                        break
                break
        
        if insert_index > 0:
            lines.insert(insert_index, method_to_add)
            new_content = '\n'.join(lines)
            
            # ファイルに書き戻し
            with open(llm_client_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            print("✅ get_default_clientメソッドを追加しました")
            return True
    
    print("❌ 適切な挿入位置が見つかりませんでした")
    return False

def clear_python_cache():
    """Pythonキャッシュファイルをクリア"""
    print("🧹 Pythonキャッシュをクリア中...")
    
    cache_patterns = [
        "**/__pycache__",
        "**/*.pyc",
        "**/*.pyo"
    ]
    
    deleted_count = 0
    
    for pattern in cache_patterns:
        for cache_path in Path(".").glob(pattern):
            try:
                if cache_path.is_file():
                    cache_path.unlink()
                    deleted_count += 1
                elif cache_path.is_dir():
                    import shutil
                    shutil.rmtree(cache_path)
                    deleted_count += 1
            except Exception as e:
                print(f"⚠️ キャッシュ削除失敗: {cache_path} - {e}")
    
    print(f"✅ {deleted_count}個のキャッシュファイル/ディレクトリを削除しました")

def verify_fix():
    """修正が正しく適用されたかを確認"""
    print("🔍 修正の確認中...")
    
    try:
        # プロジェクトルートをパスに追加
        sys.path.insert(0, str(Path.cwd()))
        
        from codecrafter.base.llm_client import llm_manager
        
        # get_default_clientメソッドが存在するかチェック
        if hasattr(llm_manager, 'get_default_client'):
            print("✅ get_default_clientメソッドが利用可能です")
            
            # 実際に呼び出してみる
            try:
                client = llm_manager.get_default_client()
                print(f"✅ get_default_client()の呼び出し成功: {type(client).__name__}")
                return True
            except Exception as e:
                print(f"❌ get_default_client()の呼び出し失敗: {e}")
                return False
        else:
            print("❌ get_default_clientメソッドが見つかりません")
            return False
            
    except ImportError as e:
        print(f"❌ インポートエラー: {e}")
        return False
    except Exception as e:
        print(f"❌ 確認中にエラー: {e}")
        return False

def main():
    """メイン修正処理"""
    print("🔧 LLMManager get_default_client エラー修正開始")
    print("="*50)
    
    # Step 1: Pythonキャッシュをクリア
    clear_python_cache()
    
    # Step 2: LLMManagerにメソッドを追加
    if fix_llm_manager():
        print("✅ LLMManagerの修正完了")
    else:
        print("❌ LLMManagerの修正失敗")
        return False
    
    # Step 3: 修正の確認
    if verify_fix():
        print("✅ 修正が正常に適用されました")
        
        print("\n" + "="*50)
        print("🎉 修正完了！")
        print("次のコマンドでテストしてください:")
        print("python test_five_node_simple.py")
        return True
    else:
        print("❌ 修正の確認に失敗しました")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)