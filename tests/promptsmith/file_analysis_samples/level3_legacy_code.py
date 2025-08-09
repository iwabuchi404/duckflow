# レベル3テスト: レガシーコード（現代化が必要）
# このコードは2010年頃のPython 2.7スタイルで書かれています

import sys
import os
import string
import re

# 古いスタイル: グローバル変数の多用
GLOBAL_COUNTER = 0
DEBUG_MODE = True
DATABASE_CONNECTION = None

def process_data_old_style(data_string):
    """
    古いスタイルのデータ処理関数
    - 型ヒントなし
    - 適切な例外処理なし  
    - グローバル変数に依存
    - 非Pythonic記法
    """
    global GLOBAL_COUNTER
    GLOBAL_COUNTER = GLOBAL_COUNTER + 1
    
    if DEBUG_MODE == True:
        print "Processing data item #" + str(GLOBAL_COUNTER)  # Python 2 print文
    
    # 古い文字列フォーマット
    result = "Data: %s (processed at %s)" % (data_string, str(GLOBAL_COUNTER))
    
    # C言語スタイルのループ
    i = 0
    while i < len(data_string):
        char = data_string[i]
        # 非効率な文字チェック
        if char in string.ascii_letters:
            pass  # 何もしない
        i = i + 1
    
    return result

class OldStyleClass:
    """古いスタイルのクラス（Python 2時代）"""
    
    def __init__(self, name):
        # プライベート属性の慣例を無視
        self.name = name
        self.data = []
        self.is_initialized = False
    
    def add_data(self, item):
        # 型チェックを手動で実装
        if type(item) != str and type(item) != unicode:  # Python 2のunicode
            raise Exception("Item must be string or unicode")
        
        self.data.append(item)
        
        # 冗長な条件式
        if self.is_initialized == False:
            self.is_initialized = True
    
    def get_data_count(self):
        # 組み込み関数を使わない
        count = 0
        for item in self.data:
            count = count + 1
        return count
    
    def print_data(self):
        # Python 2 print文
        print "Data for", self.name + ":"
        
        # enumerate を使わないインデックスループ
        for i in range(len(self.data)):
            print "  " + str(i) + ":", self.data[i]

def file_operation_old_way(filename):
    """古いスタイルのファイル操作"""
    
    # ファイル操作でwithを使わない
    try:
        file_handle = open(filename, 'r')
        content = file_handle.read()
        file_handle.close()
    except:
        # 雑な例外処理
        print "Error reading file!"
        return None
    
    # 手動での行分割処理
    lines = []
    current_line = ""
    for char in content:
        if char == '\n':
            lines.append(current_line)
            current_line = ""
        else:
            current_line = current_line + char
    
    if current_line:
        lines.append(current_line)
    
    return lines

def data_validation_old_style(user_input):
    """古いスタイルのデータ検証"""
    
    # 複雑で読みにくい条件式
    if user_input != None and user_input != "" and len(user_input) > 0:
        if type(user_input) == str or type(user_input) == unicode:
            # 正規表現の直接使用（コンパイルしない）
            if re.match(r'^[a-zA-Z0-9._%-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,4}$', user_input):
                return True
            else:
                return False
        else:
            return False
    else:
        return False

class DatabaseManagerOldStyle:
    """古いスタイルのデータベース管理"""
    
    def __init__(self):
        self.connection = None
        self.cursor = None
        self.connected = False
    
    def connect(self, host, user, password, database):
        """接続処理（エラーハンドリングが不適切）"""
        try:
            # 仮想的なデータベース接続
            print "Connecting to database..."
            self.connected = True
            global DATABASE_CONNECTION
            DATABASE_CONNECTION = self
        except:
            print "Failed to connect!"
            self.connected = False
    
    def execute_query(self, query):
        """クエリ実行（SQLインジェクション脆弱性あり）"""
        
        if self.connected != True:
            raise Exception("Not connected to database")
        
        # 危険: 直接文字列結合でSQL構築
        full_query = "SELECT * FROM users WHERE " + query
        
        print "Executing:", full_query
        
        # ダミーの結果
        return [{'id': 1, 'name': 'John'}, {'id': 2, 'name': 'Jane'}]
    
    def close_connection(self):
        """接続終了"""
        if self.connected == True:
            self.connected = False
            print "Connection closed"

def main_old_style():
    """古いスタイルのメイン関数"""
    
    print "=== Legacy Code Demo ==="
    
    # 古いスタイルの変数宣言
    processor = OldStyleClass("TestProcessor")
    
    # 手動でのループ処理
    test_data = ["item1", "item2", "item3"]
    i = 0
    while i < len(test_data):
        processor.add_data(test_data[i])
        i = i + 1
    
    processor.print_data()
    
    # ファイル操作テスト
    # test_lines = file_operation_old_way("test.txt")  # コメントアウト（ファイルが存在しない）
    
    # データベース操作テスト
    db = DatabaseManagerOldStyle()
    db.connect("localhost", "user", "password", "testdb")
    
    # 危険なクエリ実行例
    results = db.execute_query("name='John' OR '1'='1'")  # SQLインジェクション例
    print "Query results:", results
    
    db.close_connection()

# Python 2スタイルの実行
if __name__ == '__main__':
    main_old_style()

# このファイルの問題点：
# 1. Python 2 構文（print文、unicode型）
# 2. 型ヒントの欠如
# 3. グローバル変数の過度な使用
# 4. 非Pythonic記法（C言語的な書き方）
# 5. 適切でない例外処理
# 6. セキュリティ脆弱性（SQLインジェクション）
# 7. リソース管理の問題（withを使わないファイル操作）
# 8. 非効率なアルゴリズム（手動でのループ処理）
# 9. コード重複
# 10. 可読性の低い条件式