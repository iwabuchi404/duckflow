#!/usr/bin/env python3
"""
Duckflow サンドボックス評価システム - 基盤フレームワーク

安全な分離環境でDuckflowの機能をテスト・評価するシステム
"""

import tempfile
import os
import shutil
import ast
import re
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from contextlib import contextmanager
from datetime import datetime
import json


class FileSystemSandbox:
    """ファイルシステム分離サンドボックス環境"""
    
    def __init__(self, scenario_name: str):
        """
        サンドボックス環境を初期化
        
        Args:
            scenario_name: シナリオ識別名
        """
        self.scenario_name = scenario_name
        self.sandbox_root = Path(tempfile.mkdtemp(prefix=f"duckflow_test_{scenario_name}_"))
        self.original_cwd = os.getcwd()
        self.initial_files = set()
        self.execution_log = []
        self.created_at = datetime.now()
        
        print(f"[SANDBOX] 環境作成: {self.sandbox_root}")
    
    def setup_scenario_files(self, setup_files: List[Dict[str, str]]) -> None:
        """
        シナリオ用の初期ファイルをセットアップ
        
        Args:
            setup_files: ファイル情報のリスト
                [{"path": "相対パス", "content": "内容"}, ...]
        """
        print(f"[SANDBOX] 初期ファイル設定開始...")
        
        for file_info in setup_files:
            file_path = self.sandbox_root / file_info['path']
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(file_info['content'], encoding='utf-8')
            
            rel_path = str(file_path.relative_to(self.sandbox_root))
            self.initial_files.add(rel_path)
            
            print(f"[SANDBOX] 初期ファイル作成: {rel_path}")
        
        print(f"[SANDBOX] 初期ファイル設定完了: {len(setup_files)}個")
    
    def __enter__(self):
        """コンテキストマネージャー開始"""
        os.chdir(str(self.sandbox_root))
        print(f"[SANDBOX] 作業ディレクトリ変更: {self.sandbox_root}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """コンテキストマネージャー終了・クリーンアップ"""
        os.chdir(self.original_cwd)
        
        # デバッグモードの場合は一時的に保持
        if os.getenv('DUCKFLOW_DEBUG_SANDBOX'):
            print(f"[SANDBOX] デバッグモード: 環境保持 {self.sandbox_root}")
        else:
            shutil.rmtree(str(self.sandbox_root), ignore_errors=True)
            print(f"[SANDBOX] 環境クリーンアップ完了")
    
    def log_execution(self, action: str, details: Dict[str, Any]) -> None:
        """実行ログの記録"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'details': details
        }
        self.execution_log.append(log_entry)
        print(f"[SANDBOX] {action}: {details.get('summary', '')}")
    
    def execute_duckflow_scenario(self, user_input: str) -> Dict[str, Any]:
        """
        サンドボックス内でDuckflowシナリオを実行（模擬）
        
        Args:
            user_input: ユーザー入力
            
        Returns:
            Dict: 実行結果の詳細分析
        """
        start_time = time.time()
        
        self.log_execution("scenario_start", {
            "user_input": user_input,
            "summary": f"シナリオ実行開始: {user_input[:50]}..."
        })
        
        # モック応答を取得・処理
        mock_responses = self.get_mock_ai_responses(user_input)
        
        for i, response in enumerate(mock_responses):
            self.log_execution("ai_response", {
                "response_index": i,
                "response_length": len(response),
                "summary": f"AI応答{i+1}を処理中"
            })
            self._process_ai_response(response)
        
        # 実行結果を分析
        results = self.analyze_execution_results()
        
        execution_time = time.time() - start_time
        
        self.log_execution("scenario_complete", {
            "execution_time": execution_time,
            "files_created": len(results.get('files_created', [])),
            "summary": f"シナリオ完了 ({execution_time:.2f}s)"
        })
        
        return results
    
    def get_mock_ai_responses(self, user_input: str) -> List[str]:
        """
        ユーザー入力に応じたモック応答を生成
        
        Args:
            user_input: ユーザー入力
            
        Returns:
            List[str]: モック応答のリスト
        """
        user_input_lower = user_input.lower()
        
        # パターンマッチングによる応答選択
        if self._matches_pattern(user_input_lower, ["hello.py", "hello, world!", "作成"]):
            return self._get_hello_world_response()
        
        elif self._matches_pattern(user_input_lower, ["ライブラリプロジェクト", "mathutils", "src/", "tests/", "setup.py", "構造"]):
            return self._get_python_package_response()
        
        elif self._matches_pattern(user_input_lower, ["config.json", "デバッグモード", "monitoring", "features"]):
            return self._get_config_edit_response()
            
        elif self._matches_pattern(user_input_lower, ["プロジェクト", "分析", "問題点", "修正", "テスト", "calculator"]):
            return self._get_project_analysis_response()
            
        elif self._matches_pattern(user_input_lower, ["flask", "webアプリ", "挨拶", "templates"]):
            return self._get_flask_app_response()
        
        elif self._matches_pattern(user_input_lower, ["requirements.txt", "requests", "追加"]):
            return self._get_requirements_edit_response()
        
        elif self._matches_pattern(user_input_lower, ["プロジェクト", "分析", "構成", "アプリケーション"]):
            return self._get_project_analysis_response()
        
        elif self._matches_pattern(user_input_lower, ["flask", "todo", "アプリ", "app.py", "templates"]):
            return self._get_flask_todo_response()
        
        else:
            return self._get_default_response(user_input)
    
    def _matches_pattern(self, text: str, keywords: List[str]) -> bool:
        """キーワードパターンマッチング"""
        if not keywords:
            return False
        matches = sum(1 for keyword in keywords if keyword.lower() in text.lower())
        return matches >= max(1, len(keywords) // 2)
    
    def _get_hello_world_response(self) -> List[str]:
        """Hello World作成応答"""
        return ["""Hello Worldを出力するPythonファイルを作成します。

FILE_OPERATION:CREATE hello.py
```python
#!/usr/bin/env python3
'''
Hello World プログラム
シンプルなPythonスクリプトの例
'''

def main():
    '''メイン関数'''
    print("Hello, World!")
    print("Duckflowでファイルが作成されました！")

if __name__ == "__main__":
    main()
```

hello.pyファイルを作成しました。以下の機能が含まれています：
- Hello Worldメッセージの出力
- 適切なdocstring
- if __name__ == "__main__" パターン

実行するには `python hello.py` を実行してください。"""]
    
    def _get_python_package_response(self) -> List[str]:
        """Pythonパッケージ作成応答"""
        return ["""新しいPythonライブラリプロジェクト 'mathutils' を作成します。

FILE_OPERATION:CREATE setup.py
```python
'''
mathutils - 数学ユーティリティライブラリ
'''
from setuptools import setup, find_packages

setup(
    name="mathutils",
    version="0.1.0",
    author="Duckflow User",
    author_email="user@example.com",
    description="A simple math utilities library",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.8",
    install_requires=[
        "numpy>=1.20.0",
    ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
)
```

FILE_OPERATION:CREATE README.md
```markdown
# MathUtils

数学計算のためのシンプルなPythonライブラリです。

## インストール

```bash
pip install mathutils
```

## 使用方法

```python
from mathutils import basic

# 基本的な計算
result = basic.add(5, 3)
print(result)  # 8
```

## 開発者向け

### テスト実行

```bash
pytest tests/
```

### インストール（開発版）

```bash
pip install -e .
```
```

FILE_OPERATION:CREATE src/mathutils/__init__.py
```python
'''
mathutils - 数学ユーティリティライブラリ
'''

__version__ = "0.1.0"
__author__ = "Duckflow User"

from .basic import add, subtract, multiply, divide

__all__ = ["add", "subtract", "multiply", "divide"]
```

FILE_OPERATION:CREATE src/mathutils/basic.py
```python
'''
基本的な数学演算モジュール
'''

def add(a, b):
    '''2つの数値を加算
    
    Args:
        a (float): 第1の数値
        b (float): 第2の数値
        
    Returns:
        float: 加算結果
    '''
    return a + b

def subtract(a, b):
    '''2つの数値を減算
    
    Args:
        a (float): 第1の数値
        b (float): 第2の数値
        
    Returns:
        float: 減算結果
    '''
    return a - b

def multiply(a, b):
    '''2つの数値を乗算
    
    Args:
        a (float): 第1の数値
        b (float): 第2の数値
        
    Returns:
        float: 乗算結果
    '''
    return a * b

def divide(a, b):
    '''2つの数値を除算
    
    Args:
        a (float): 第1の数値
        b (float): 第2の数値
        
    Returns:
        float: 除算結果
        
    Raises:
        ZeroDivisionError: bが0の場合
    '''
    if b == 0:
        raise ZeroDivisionError("除数が0です")
    return a / b
```

FILE_OPERATION:CREATE tests/__init__.py
```python
'''
mathutils テストパッケージ
'''
```

FILE_OPERATION:CREATE tests/test_basic.py
```python
'''
basic モジュールのテスト
'''
import pytest
from mathutils.basic import add, subtract, multiply, divide

def test_add():
    '''加算のテスト'''
    assert add(2, 3) == 5
    assert add(-1, 1) == 0
    assert add(0.5, 0.3) == pytest.approx(0.8)

def test_subtract():
    '''減算のテスト'''
    assert subtract(5, 3) == 2
    assert subtract(-1, 1) == -2
    assert subtract(0, 0) == 0

def test_multiply():
    '''乗算のテスト'''
    assert multiply(3, 4) == 12
    assert multiply(-2, 3) == -6
    assert multiply(0, 5) == 0

def test_divide():
    '''除算のテスト'''
    assert divide(10, 2) == 5
    assert divide(9, 3) == 3
    assert divide(-6, 2) == -3

def test_divide_by_zero():
    '''ゼロ除算のエラーテスト'''
    with pytest.raises(ZeroDivisionError, match="除数が0です"):
        divide(10, 0)
```

FILE_OPERATION:CREATE requirements.txt
```
numpy>=1.20.0
pytest>=6.0.0
```

## 作成したプロジェクト構造:
```
mathutils/
├── setup.py          # パッケージ設定
├── README.md          # プロジェクト説明
├── requirements.txt   # 依存関係
├── src/
│   └── mathutils/
│       ├── __init__.py    # パッケージ初期化
│       └── basic.py       # 基本数学演算
└── tests/
    ├── __init__.py        # テストパッケージ初期化
    └── test_basic.py      # 基本機能テスト
```

標準的なPythonパッケージ構造を作成しました。"""]
    
    def _get_requirements_edit_response(self) -> List[str]:
        """requirements.txt編集応答"""
README = (HERE / "README.md").read_text(encoding="utf-8") if (HERE / "README.md").exists() else ""

setup(
    name="myapp",
    version="0.1.0", 
    author="Duckflow User",
    author_email="user@example.com",
    description="A sample Python package created by Duckflow",
    long_description=README,
    long_description_content_type="text/markdown",
    url="https://github.com/user/myapp",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        # 本番用依存関係をここに追加
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "black>=22.0.0",
            "flake8>=4.0.0",
            "mypy>=0.950",
        ],
    },
    entry_points={
        "console_scripts": [
            "myapp=myapp:hello",
        ],
    },
)
```

FILE_OPERATION:CREATE requirements.txt
```
# 開発用依存関係
pytest>=7.0.0
black>=22.0.0
flake8>=4.0.0
mypy>=0.950

# 本番用依存関係
# 必要に応じてここに追加
```

FILE_OPERATION:CREATE tests/__init__.py
```python
\"\"\"
myapp テストパッケージ
\"\"\"
```

FILE_OPERATION:CREATE tests/test_myapp.py
```python
\"\"\"
myapp パッケージのテスト
\"\"\"
import unittest
from myapp import get_version, hello
import io
import sys

class TestMyApp(unittest.TestCase):
    \"\"\"MyAppのテストクラス\"\"\"
    
    def test_get_version(self):
        \"\"\"バージョン取得テスト\"\"\"
        version = get_version()
        self.assertEqual(version, "0.1.0")
        self.assertIsInstance(version, str)
    
    def test_hello(self):
        \"\"\"挨拶関数テスト\"\"\"
        # 標準出力をキャプチャ
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        hello()
        
        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()
        
        self.assertIn("Hello from myapp", output)
        self.assertIn("v0.1.0", output)

if __name__ == "__main__":
    unittest.main()
```

FILE_OPERATION:CREATE README.md
```markdown
# myapp

Duckflowによって作成されたサンプルPythonパッケージです。

## 特徴

- シンプルなパッケージ構造
- 適切なsetup.py設定
- 基本的なテストの実装
- 開発用依存関係の管理

## インストール

### 開発環境
```bash
# 開発モードでインストール
pip install -e .

# 開発用依存関係も含めてインストール
pip install -e .[dev]
```

### 本番環境
```bash
pip install myapp
```

## 使用方法

### Python から使用
```python
import myapp

# バージョン情報を取得
print(myapp.get_version())

# 挨拶メッセージを表示
myapp.hello()
```

### コマンドラインから使用
```bash
myapp
```

## 開発

### テスト実行
```bash
pytest tests/
```

### コード品質チェック
```bash
# フォーマット
black myapp/ tests/

# リント
flake8 myapp/ tests/

# 型チェック
mypy myapp/
```

## ライセンス

MIT License
```

Pythonパッケージの基本構造を作成しました。以下が含まれています：

[SUCCESS] **パッケージ構造**
- `myapp/` - メインパッケージディレクトリ
- `tests/` - テストディレクトリ

[SUCCESS] **設定ファイル**
- `setup.py` - パッケージ設定
- `requirements.txt` - 依存関係管理
- `README.md` - ドキュメント

[SUCCESS] **機能**
- バージョン管理
- コマンドラインエントリーポイント
- 基本テストの実装

このパッケージは以下のコマンドで開発を開始できます：
```bash
pip install -e .
python -m pytest tests/
```
"""]
    
    def _get_requirements_edit_response(self) -> List[str]:
        """requirements.txt編集応答"""
        return ["""
requirements.txtファイルにrequests==2.28.1を追加します。

FILE_OPERATION:EDIT requirements.txt
```
flask==2.0.1
requests==2.28.1
```

requests==2.28.1を追加しました。requestsライブラリを使用してHTTPリクエストを送信できます。

## requests ライブラリについて
- HTTP リクエストの送信
- JSON データの処理
- セッション管理
- 認証サポート

使用例：
```python
import requests

response = requests.get('https://api.example.com/data')
data = response.json()
```
"""]
    
    def _get_project_analysis_response(self) -> List[str]:
        """プロジェクト分析応答"""
        return ["""
プロジェクトの構成を分析します。ファイル構造と内容を確認中...

## [INFO] プロジェクト分析結果

### [TARGET] プロジェクト概要
**アプリケーションタイプ**: Flask Webアプリケーション  
**開発段階**: 初期開発フェーズ  
**プロジェクト規模**: 小規模 (シングル開発者向け)

### [FOLDER] ファイル構成分析

#### 1. **main.py** - メインアプリケーション
```python
# 検出された主要要素:
- Flask フレームワークの使用
- requests ライブラリのインポート
- 基本的なルーティング設定 (/)
- 開発サーバー設定 (debug=True)
```

**特徴**:
- [SUCCESS] シンプルな構造
- [SUCCESS] 開発者フレンドリー
- [WARNING]  本番環境設定が不足

#### 2. **requirements.txt** - 依存関係管理
```
Flask 2.3.0 - Web フレームワーク
requests 2.28.1 - HTTP クライアントライブラリ
```

**評価**:
- [SUCCESS] 安定バージョンを使用
- [SUCCESS] 最低限の依存関係を管理
- [IDEA] 推奨: 追加ライブラリ (python-dotenv, gunicorn)

#### 3. **config.py** - アプリケーション設定
```python
# 設定項目:
- DEBUG = True (開発モード)
- SECRET_KEY = 'dev-key' (セキュリティキー)
- DATABASE_URL = SQLite データベース
```

**セキュリティ考慮事項**:
- [WARNING]  本番用SECRET_KEYの設定が必要
- [SUCCESS] SQLite使用 (開発環境適切)
- [IDEA] 推奨: 環境変数による設定管理

#### 4. **README.md** - プロジェクト文書
- [SUCCESS] 基本的な説明あり
- [IDEA] 推奨: セットアップ手順・API仕様の追加

### 🔍 技術スタック詳細

| 要素 | 使用技術 | バージョン | 評価 |
|------|----------|------------|------|
| Webフレームワーク | Flask | 2.3.0 | [SUCCESS] 適切 |
| HTTPクライアント | requests | 2.28.1 | [SUCCESS] 適切 |
| データベース | SQLite | - | [SUCCESS] 開発環境適切 |

### [START] 発展可能性の分析

**このプロジェクトは以下に発展できます**:
1. **REST API サーバー** - JSON APIエンドポイントの追加
2. **Webアプリケーション** - テンプレートエンジンの活用
3. **マイクロサービス** - Docker化・AWS/GCP展開

### [INFO] 推奨される次のステップ

#### 即座に改善可能:
1. **環境設定の改善**
   ```bash
   pip install python-dotenv
   # .env ファイルでの環境変数管理
   ```

2. **ログ機能追加**
   ```python
   import logging
   app.logger.setLevel(logging.INFO)
   ```

3. **エラーハンドリング強化**
   ```python
   @app.errorhandler(404)
   def not_found(error):
       return jsonify({"error": "Not found"}), 404
   ```

#### 中長期的な改善:
- [SUCCESS] テストスイートの追加 (pytest)
- [SUCCESS] CI/CDパイプライン設定
- [SUCCESS] API文書化 (Swagger/OpenAPI)
- [SUCCESS] 本番環境設定 (Docker, gunicorn)

### [TARGET] 総合評価

| 項目 | スコア | コメント |
|------|--------|----------|
| 構造の明確性 | 85% | シンプルで理解しやすい |
| セキュリティ | 60% | 開発環境適切、本番要改善 |
| 拡張性 | 80% | Flask基盤で拡張容易 |
| 保守性 | 75% | 設定分離等でさらに向上可能 |

**結論**: 開発初期段階として良好な構造。基本的なWebアプリケーション開発の土台として適切です。
"""]
    
    def _get_flask_todo_response(self) -> List[str]:
        """Flask Todoアプリ作成応答"""
        return ["""
FlaskによるTodoアプリケーションを作成します。現代的なWebアプリケーション構造で実装します。

FILE_OPERATION:CREATE app.py
```python
\"\"\"
Flask Todo アプリケーション
シンプルで機能的なTodoリスト管理システム
\"\"\"

from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from datetime import datetime
import json
import os

# Flaskアプリケーションの初期化
app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'

# データストレージ（実際のアプリではDBを使用）
TODOS_FILE = 'todos.json'

class TodoManager:
    \"\"\"Todo管理クラス\"\"\"
    
    def __init__(self):
        self.todos = self.load_todos()
    
    def load_todos(self):
        \"\"\"保存されたTodoを読み込み\"\"\"
        if os.path.exists(TODOS_FILE):
            try:
                with open(TODOS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        return [
            {
                'id': 1,
                'text': 'Duckflowでアプリを作成する',
                'done': True,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'category': 'work'
            },
            {
                'id': 2,
                'text': 'Todo機能をテストする',
                'done': False,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'category': 'personal'
            }
        ]
    
    def save_todos(self):
        \"\"\"Todoをファイルに保存\"\"\"
        try:
            with open(TODOS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.todos, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存エラー: {e}")
    
    def add_todo(self, text, category='personal'):
        \"\"\"新しいTodoを追加\"\"\"
        if not text.strip():
            return False
        
        new_id = max([t['id'] for t in self.todos], default=0) + 1
        new_todo = {
            'id': new_id,
            'text': text.strip(),
            'done': False,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'category': category
        }
        self.todos.append(new_todo)
        self.save_todos()
        return True
    
    def toggle_todo(self, todo_id):
        \"\"\"Todoの完了状態を切り替え\"\"\"
        for todo in self.todos:
            if todo['id'] == todo_id:
                todo['done'] = not todo['done']
                self.save_todos()
                return True
        return False
    
    def delete_todo(self, todo_id):
        \"\"\"Todoを削除\"\"\"
        original_length = len(self.todos)
        self.todos = [todo for todo in self.todos if todo['id'] != todo_id]
        if len(self.todos) < original_length:
            self.save_todos()
            return True
        return False
    
    def get_stats(self):
        \"\"\"統計情報を取得\"\"\"
        total = len(self.todos)
        completed = len([t for t in self.todos if t['done']])
        return {
            'total': total,
            'completed': completed,
            'remaining': total - completed,
            'completion_rate': (completed / total * 100) if total > 0 else 0
        }

# TodoManagerのインスタンス化
todo_manager = TodoManager()

@app.route('/')
def index():
    \"\"\"メインページ\"\"\"
    stats = todo_manager.get_stats()
    return render_template('index.html', 
                         todos=todo_manager.todos, 
                         stats=stats)

@app.route('/add', methods=['POST'])
def add_todo():
    \"\"\"新しいTodo追加\"\"\"
    todo_text = request.form.get('todo', '').strip()
    category = request.form.get('category', 'personal')
    
    if todo_manager.add_todo(todo_text, category):
        flash('新しいTodoを追加しました！', 'success')
    else:
        flash('Todoテキストを入力してください。', 'error')
    
    return redirect(url_for('index'))

@app.route('/toggle/<int:todo_id>')
def toggle_todo(todo_id):
    \"\"\"Todoの完了状態切り替え\"\"\"
    if todo_manager.toggle_todo(todo_id):
        flash('Todoの状態を更新しました。', 'info')
    else:
        flash('Todoが見つかりませんでした。', 'error')
    
    return redirect(url_for('index'))

@app.route('/delete/<int:todo_id>')
def delete_todo(todo_id):
    \"\"\"Todo削除\"\"\"
    if todo_manager.delete_todo(todo_id):
        flash('Todoを削除しました。', 'info')
    else:
        flash('Todoが見つかりませんでした。', 'error')
    
    return redirect(url_for('index'))

@app.route('/api/todos')
def api_todos():
    \"\"\"Todo一覧API (JSON)\"\"\"
    return jsonify({
        'todos': todo_manager.todos,
        'stats': todo_manager.get_stats()
    })

@app.route('/api/add', methods=['POST'])
def api_add_todo():
    \"\"\"Todo追加API\"\"\"
    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({'error': 'Todo text is required'}), 400
    
    success = todo_manager.add_todo(
        data['text'], 
        data.get('category', 'personal')
    )
    
    if success:
        return jsonify({'message': 'Todo added successfully'}), 201
    else:
        return jsonify({'error': 'Failed to add todo'}), 400

@app.errorhandler(404)
def not_found(error):
    \"\"\"404エラーハンドラー\"\"\"
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    \"\"\"500エラーハンドラー\"\"\"
    return render_template('500.html'), 500

if __name__ == '__main__':
    # 開発サーバー起動
    app.run(debug=True, host='127.0.0.1', port=5000)
```

FILE_OPERATION:CREATE templates/index.html
```html
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📝 Todo App - Duckflow作成</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
</head>
<body>
    <div class="container">
        <!-- ヘッダー -->
        <header class="header">
            <h1><i class="fas fa-check-circle"></i> Todo アプリ</h1>
            <p class="subtitle">Duckflowで作成されたモダンなTodo管理システム</p>
        </header>

        <!-- 統計情報 -->
        <div class="stats">
            <div class="stat-card">
                <div class="stat-number">{{ stats.total }}</div>
                <div class="stat-label">総Todo数</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ stats.completed }}</div>
                <div class="stat-label">完了済み</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ stats.remaining }}</div>
                <div class="stat-label">残り</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ "%.0f"|format(stats.completion_rate) }}%</div>
                <div class="stat-label">達成率</div>
            </div>
        </div>

        <!-- フラッシュメッセージ -->
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                <div class="flash-messages">
                    {% for category, message in messages %}
                        <div class="flash flash-{{ category }}">
                            <i class="fas fa-info-circle"></i>
                            {{ message }}
                        </div>
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}

        <!-- Todo追加フォーム -->
        <div class="add-todo-section">
            <h2><i class="fas fa-plus"></i> 新しいTodoを追加</h2>
            <form action="/add" method="post" class="todo-form">
                <div class="form-row">
                    <input 
                        type="text" 
                        name="todo" 
                        placeholder="やることを入力してください..." 
                        required 
                        class="todo-input"
                        maxlength="200"
                    >
                    <select name="category" class="category-select">
                        <option value="personal">個人</option>
                        <option value="work">仕事</option>
                        <option value="study">勉強</option>
                        <option value="health">健康</option>
                        <option value="other">その他</option>
                    </select>
                    <button type="submit" class="add-btn">
                        <i class="fas fa-plus"></i> 追加
                    </button>
                </div>
            </form>
        </div>

        <!-- Todo一覧 -->
        <div class="todos-section">
            <h2><i class="fas fa-list"></i> Todo一覧</h2>
            
            {% if todos %}
                <div class="todo-list">
                    {% for todo in todos %}
                        <div class="todo-item {{ 'completed' if todo.done else 'pending' }}">
                            <div class="todo-content">
                                <div class="todo-main">
                                    <span class="todo-text">{{ todo.text }}</span>
                                    <span class="todo-category category-{{ todo.category }}">
                                        {{ todo.category }}
                                    </span>
                                </div>
                                <div class="todo-meta">
                                    <small class="todo-date">
                                        <i class="fas fa-calendar"></i>
                                        {{ todo.created_at }}
                                    </small>
                                    <small class="todo-id">#{{ todo.id }}</small>
                                </div>
                            </div>
                            
                            <div class="todo-actions">
                                <a href="/toggle/{{ todo.id }}" 
                                   class="btn btn-toggle {{ 'btn-undo' if todo.done else 'btn-complete' }}"
                                   title="{{ '未完了に戻す' if todo.done else '完了にする' }}">
                                    {% if todo.done %}
                                        <i class="fas fa-undo"></i> 未完了
                                    {% else %}
                                        <i class="fas fa-check"></i> 完了
                                    {% endif %}
                                </a>
                                <a href="/delete/{{ todo.id }}" 
                                   class="btn btn-delete"
                                   onclick="return confirm('「{{ todo.text }}」を削除しますか？')"
                                   title="削除">
                                    <i class="fas fa-trash"></i> 削除
                                </a>
                            </div>
                        </div>
                    {% endfor %}
                </div>
            {% else %}
                <div class="empty-state">
                    <i class="fas fa-clipboard-list empty-icon"></i>
                    <h3>Todoがありません</h3>
                    <p>上のフォームから新しいTodoを追加してください。</p>
                </div>
            {% endif %}
        </div>
    </div>

    <!-- フッター -->
    <footer class="footer">
        <p>
            <i class="fas fa-robot"></i>
            このアプリは <strong>Duckflow</strong> によって作成されました
        </p>
        <p class="api-info">
            <small>
                <i class="fas fa-code"></i>
                API エンドポイント: <code>/api/todos</code> | <code>/api/add</code>
            </small>
        </p>
    </footer>

    <script>
        // シンプルなJavaScript機能
        document.addEventListener('DOMContentLoaded', function() {
            // フラッシュメッセージの自動非表示
            const flashMessages = document.querySelectorAll('.flash');
            flashMessages.forEach(function(message) {
                setTimeout(function() {
                    message.style.opacity = '0';
                    setTimeout(function() {
                        message.remove();
                    }, 300);
                }, 5000);
            });

            // Todo入力フィールドのフォーカス
            const todoInput = document.querySelector('.todo-input');
            if (todoInput) {
                todoInput.focus();
            }
        });
    </script>
</body>
</html>
```

FILE_OPERATION:CREATE static/style.css
```css
/* ===== Duckflow Todo App スタイル ===== */

/* リセット・ベース */
* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

:root {
    /* カラーパレット */
    --primary-color: #667eea;
    --secondary-color: #764ba2;
    --success-color: #48bb78;
    --danger-color: #f56565;
    --warning-color: #ed8936;
    --info-color: #4299e1;
    
    /* グレースケール */
    --gray-50: #f9fafb;
    --gray-100: #f3f4f6;
    --gray-200: #e5e7eb;
    --gray-300: #d1d5db;
    --gray-400: #9ca3af;
    --gray-500: #6b7280;
    --gray-600: #4b5563;
    --gray-700: #374151;
    --gray-800: #1f2937;
    --gray-900: #111827;
    
    /* シャドウ */
    --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
    --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
    --shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
    
    /* ボーダー */
    --border-radius: 8px;
    --border-radius-lg: 12px;
    
    /* フォント */
    --font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
}

body {
    font-family: var(--font-family);
    background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
    color: var(--gray-800);
    line-height: 1.6;
    min-height: 100vh;
}

.container {
    max-width: 900px;
    margin: 0 auto;
    padding: 20px;
    min-height: 100vh;
}

/* ===== ヘッダー ===== */
.header {
    text-align: center;
    margin-bottom: 40px;
    padding: 30px 0;
    background: rgba(255, 255, 255, 0.1);
    backdrop-filter: blur(10px);
    border-radius: var(--border-radius-lg);
    border: 1px solid rgba(255, 255, 255, 0.2);
}

.header h1 {
    font-size: 2.5rem;
    color: white;
    margin-bottom: 10px;
    text-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.header h1 i {
    margin-right: 10px;
    color: #ffd700;
}

.subtitle {
    color: rgba(255, 255, 255, 0.8);
    font-size: 1.1rem;
}

/* ===== 統計情報 ===== */
.stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 15px;
    margin-bottom: 30px;
}

.stat-card {
    background: rgba(255, 255, 255, 0.95);
    padding: 20px;
    border-radius: var(--border-radius);
    text-align: center;
    box-shadow: var(--shadow-md);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.stat-card:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-lg);
}

.stat-number {
    font-size: 2rem;
    font-weight: bold;
    color: var(--primary-color);
    margin-bottom: 5px;
}

.stat-label {
    font-size: 0.85rem;
    color: var(--gray-600);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* ===== フラッシュメッセージ ===== */
.flash-messages {
    margin-bottom: 20px;
}

.flash {
    padding: 12px 16px;
    border-radius: var(--border-radius);
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    transition: opacity 0.3s ease;
}

.flash i {
    margin-right: 10px;
}

.flash-success {
    background-color: #d4edda;
    border: 1px solid #c3e6cb;
    color: #155724;
}

.flash-error {
    background-color: #f8d7da;
    border: 1px solid #f5c6cb;
    color: #721c24;
}

.flash-info {
    background-color: #d1ecf1;
    border: 1px solid #bee5eb;
    color: #0c5460;
}

/* ===== セクション共通 ===== */
.add-todo-section,
.todos-section {
    background: rgba(255, 255, 255, 0.95);
    padding: 25px;
    border-radius: var(--border-radius-lg);
    box-shadow: var(--shadow-lg);
    margin-bottom: 25px;
}

.add-todo-section h2,
.todos-section h2 {
    margin-bottom: 20px;
    color: var(--gray-700);
    font-size: 1.5rem;
}

.add-todo-section h2 i,
.todos-section h2 i {
    margin-right: 10px;
    color: var(--primary-color);
}

/* ===== Todo追加フォーム ===== */
.todo-form .form-row {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
}

.todo-input {
    flex: 1;
    min-width: 250px;
    padding: 12px 16px;
    border: 2px solid var(--gray-200);
    border-radius: var(--border-radius);
    font-size: 16px;
    transition: border-color 0.3s ease, box-shadow 0.3s ease;
}

.todo-input:focus {
    outline: none;
    border-color: var(--primary-color);
    box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.category-select {
    padding: 12px 16px;
    border: 2px solid var(--gray-200);
    border-radius: var(--border-radius);
    font-size: 16px;
    background-color: white;
    cursor: pointer;
    min-width: 120px;
}

.add-btn {
    padding: 12px 20px;
    background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
    color: white;
    border: none;
    border-radius: var(--border-radius);
    font-size: 16px;
    font-weight: 600;
    cursor: pointer;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
    white-space: nowrap;
}

.add-btn:hover {
    transform: translateY(-1px);
    box-shadow: var(--shadow-md);
}

.add-btn i {
    margin-right: 8px;
}

/* ===== Todo一覧 ===== */
.todo-list {
    display: flex;
    flex-direction: column;
    gap: 15px;
}

.todo-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px;
    border: 2px solid transparent;
    border-radius: var(--border-radius);
    transition: all 0.3s ease;
}

.todo-item.pending {
    background: linear-gradient(135deg, #fff 0%, #f8f9ff 100%);
    border-color: var(--gray-200);
}

.todo-item.completed {
    background: linear-gradient(135deg, #f0fff4 0%, #e6fffa 100%);
    border-color: var(--success-color);
    opacity: 0.8;
}

.todo-item:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
}

.todo-content {
    flex: 1;
    margin-right: 20px;
}

.todo-main {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 8px;
}

.todo-text {
    font-size: 1.1rem;
    font-weight: 500;
    color: var(--gray-800);
}

.completed .todo-text {
    text-decoration: line-through;
    color: var(--gray-500);
}

.todo-category {
    padding: 4px 8px;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.category-personal { background: #e0e7ff; color: #3730a3; }
.category-work { background: #fef3c7; color: #92400e; }
.category-study { background: #dcfce7; color: #166534; }
.category-health { background: #fed7d7; color: #c53030; }
.category-other { background: #f3e8ff; color: #6b46c1; }

.todo-meta {
    display: flex;
    align-items: center;
    gap: 15px;
    font-size: 0.85rem;
    color: var(--gray-500);
}

.todo-date i {
    margin-right: 5px;
}

.todo-id {
    color: var(--gray-400);
}

/* ===== Todo アクション ===== */
.todo-actions {
    display: flex;
    gap: 8px;
}

.btn {
    padding: 8px 12px;
    border: none;
    border-radius: var(--border-radius);
    font-size: 0.85rem;
    font-weight: 500;
    text-decoration: none;
    cursor: pointer;
    transition: all 0.2s ease;
    display: inline-flex;
    align-items: center;
    white-space: nowrap;
}

.btn i {
    margin-right: 6px;
}

.btn-complete {
    background-color: var(--success-color);
    color: white;
}

.btn-complete:hover {
    background-color: #38a169;
}

.btn-undo {
    background-color: var(--warning-color);
    color: white;
}

.btn-undo:hover {
    background-color: #dd6b20;
}

.btn-delete {
    background-color: var(--danger-color);
    color: white;
}

.btn-delete:hover {
    background-color: #e53e3e;
}

/* ===== 空の状態 ===== */
.empty-state {
    text-align: center;
    padding: 60px 20px;
    color: var(--gray-500);
}

.empty-icon {
    font-size: 4rem;
    margin-bottom: 20px;
    color: var(--gray-300);
}

.empty-state h3 {
    font-size: 1.5rem;
    margin-bottom: 10px;
    color: var(--gray-600);
}

/* ===== フッター ===== */
.footer {
    text-align: center;
    padding: 30px 20px;
    margin-top: 50px;
    background: rgba(255, 255, 255, 0.1);
    backdrop-filter: blur(10px);
    border-radius: var(--border-radius-lg);
    border: 1px solid rgba(255, 255, 255, 0.2);
    color: white;
}

.footer p {
    margin-bottom: 10px;
}

.footer strong {
    color: #ffd700;
}

.api-info code {
    background: rgba(0, 0, 0, 0.2);
    padding: 2px 6px;
    border-radius: 4px;
    font-family: 'Courier New', monospace;
}

/* ===== レスポンシブ対応 ===== */
@media (max-width: 768px) {
    .container {
        padding: 15px;
    }
    
    .header h1 {
        font-size: 2rem;
    }
    
    .stats {
        grid-template-columns: repeat(2, 1fr);
    }
    
    .todo-form .form-row {
        flex-direction: column;
    }
    
    .todo-input,
    .category-select,
    .add-btn {
        width: 100%;
    }
    
    .todo-item {
        flex-direction: column;
        align-items: stretch;
        gap: 15px;
    }
    
    .todo-content {
        margin-right: 0;
    }
    
    .todo-actions {
        justify-content: center;
    }
    
    .btn {
        flex: 1;
        justify-content: center;
    }
}

@media (max-width: 480px) {
    .stats {
        grid-template-columns: 1fr;
    }
    
    .stat-card {
        padding: 15px;
    }
    
    .add-todo-section,
    .todos-section {
        padding: 20px;
    }
}

/* ===== アニメーション ===== */
@keyframes fadeIn {
    from {
        opacity: 0;
        transform: translateY(10px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.todo-item {
    animation: fadeIn 0.3s ease;
}

/* ===== プリント対応 ===== */
@media print {
    body {
        background: white;
        color: black;
    }
    
    .header,
    .add-todo-section,
    .footer {
        background: white !important;
        color: black !important;
    }
    
    .todo-actions {
        display: none;
    }
    
    .flash-messages {
        display: none;
    }
}
```

FlaskによるモダンなTodoアプリケーションを作成しました！

## ✨ **実装された機能**

### [TARGET] **核心機能**
- [SUCCESS] Todo の追加・完了・削除
- [SUCCESS] カテゴリー分類（仕事・個人・勉強・健康・その他）
- [SUCCESS] 統計情報表示（総数・完了数・達成率）
- [SUCCESS] データの永続化（JSON形式）

### 🎨 **UI/UX**
- [SUCCESS] レスポンシブデザイン（PC・タブレット・スマホ対応）
- [SUCCESS] モダンなグラデーション・カードデザイン
- [SUCCESS] Font Awesome アイコン統合
- [SUCCESS] フラッシュメッセージ（自動非表示）
- [SUCCESS] ホバーエフェクト・アニメーション

### [FIX] **技術機能**
- [SUCCESS] RESTful API エンドポイント（`/api/todos`, `/api/add`）
- [SUCCESS] エラーハンドリング（404・500）
- [SUCCESS] セキュリティ考慮（フォーム検証・XSS対策）
- [SUCCESS] 設定可能なカテゴリーシステム

### 📱 **アクセシビリティ**
- [SUCCESS] キーボードナビゲーション対応
- [SUCCESS] スクリーンリーダー対応
- [SUCCESS] 高コントラスト設計
- [SUCCESS] プリント用CSS

## [START] **起動方法**
```bash
python app.py
# ブラウザで http://127.0.0.1:5000 にアクセス
```

このTodoアプリは本格的なWebアプリケーションとして使用できる完成度の高い実装です。
"""]
    
    def _get_default_response(self, user_input: str) -> List[str]:
        """デフォルト応答"""
        return [f"""
入力内容を理解しました: {user_input}

申し訳ありませんが、この特定の要求に対する具体的なコード実装は現在準備されていません。

## [IDEA] **代替提案**

以下の一般的なタスクでしたらお手伝いできます：

1. **ファイル作成**
   - Python スクリプト
   - 設定ファイル
   - ドキュメント

2. **プロジェクト構築**
   - Python パッケージ構造
   - Web アプリケーション
   - 開発環境設定

3. **コード分析**
   - 既存プロジェクトの理解
   - 構造分析
   - 改善提案

具体的な要求を教えていただけますか？
"""]
    
    def _process_ai_response(self, ai_response: str) -> None:
        """
        AI応答を処理してファイル操作を実行
        
        Args:
            ai_response: AI応答テキスト
        """
        lines = ai_response.split('\n')
        current_op = None
        filename = None
        content_lines = []
        in_code_block = False
        
        for line in lines:
            # FILE_OPERATION: パターンを検出
            if line.strip().startswith('FILE_OPERATION:'):
                parts = line.strip().split(':', 1)
                if len(parts) >= 2:
                    operation_part = parts[1].strip()
                    operation_tokens = operation_part.split()
                    if len(operation_tokens) >= 2:
                        current_op = operation_tokens[0].strip()
                        filename = ' '.join(operation_tokens[1:]).strip()
                        content_lines = []
                        
                        self.log_execution("file_operation_detected", {
                            "operation": current_op,
                            "filename": filename,
                            "summary": f"{current_op} {filename}"
                        })
                continue
            
            # コードブロックの開始・終了を検出
            if line.strip().startswith('```'):
                if in_code_block and current_op and filename:
                    # コードブロック終了 - ファイル操作実行
                    content = '\n'.join(content_lines)
                    self._execute_file_operation(current_op, filename, content)
                    current_op = None
                    filename = None
                    content_lines = []
                in_code_block = not in_code_block
                continue
            
            # コードブロック内の内容を収集
            if in_code_block and current_op and filename:
                content_lines.append(line)
    
    def _execute_file_operation(self, operation: str, filename: str, content: str) -> None:
        """
        実際のファイル操作を実行
        
        Args:
            operation: 操作種別 (CREATE, EDIT等)
            filename: ファイル名
            content: ファイル内容
        """
        try:
            file_path = self.sandbox_root / filename
            
            if operation in ['CREATE', 'EDIT']:
                # ディレクトリを作成
                file_path.parent.mkdir(parents=True, exist_ok=True)
                
                # ファイルを作成・編集
                file_path.write_text(content, encoding='utf-8')
                
                self.log_execution("file_created", {
                    "filename": filename,
                    "size": len(content),
                    "lines": len(content.split('\n')),
                    "summary": f"作成: {filename} ({len(content)} chars)"
                })
            
            else:
                self.log_execution("unsupported_operation", {
                    "operation": operation,
                    "filename": filename,
                    "summary": f"未対応操作: {operation}"
                })
                
        except Exception as e:
            self.log_execution("file_operation_error", {
                "operation": operation,
                "filename": filename,
                "error": str(e),
                "summary": f"ファイル操作エラー: {e}"
            })
    
    def analyze_execution_results(self) -> Dict[str, Any]:
        """
        実行結果の詳細分析
        
        Returns:
            Dict: 分析結果
        """
        start_time = time.time()
        
        analysis = {
            'files_created': [],
            'files_modified': [],
            'directories_created': [],
            'content_analysis': {},
            'syntax_validation': {},
            'structure_analysis': {},
            'project_analysis': {
                'framework_detected': None,
                'dependencies_identified': [],
                'project_type': None,
                'files_analyzed': []
            },
            'execution_summary': {
                'total_execution_time': 0,
                'operations_count': len(self.execution_log),
                'sandbox_path': str(self.sandbox_root)
            }
        }
        
        # 全ファイル・ディレクトリをスキャン
        for item in self.sandbox_root.rglob('*'):
            if item.is_file():
                rel_path = str(item.relative_to(self.sandbox_root))
                
                # 初期ファイル vs 新規作成ファイル
                if rel_path in self.initial_files:
                    analysis['files_modified'].append(rel_path)
                else:
                    analysis['files_created'].append(rel_path)
                
                # ファイル内容分析
                try:
                    if item.suffix in ['.py', '.html', '.css', '.txt', '.md', '.json', '.yaml', '.yml']:
                        content = item.read_text(encoding='utf-8')
                        analysis['content_analysis'][rel_path] = content
                        
                        # Python構文チェック
                        if item.suffix == '.py':
                            try:
                                ast.parse(content)
                                analysis['syntax_validation'][rel_path] = True
                            except SyntaxError as e:
                                analysis['syntax_validation'][rel_path] = False
                                self.log_execution("syntax_error", {
                                    "filename": rel_path,
                                    "error": str(e),
                                    "summary": f"構文エラー: {rel_path}"
                                })
                        
                        # プロジェクト分析
                        self._analyze_project_content(rel_path, content, analysis['project_analysis'])
                        
                except Exception as e:
                    self.log_execution("content_analysis_error", {
                        "filename": rel_path,
                        "error": str(e),
                        "summary": f"内容分析エラー: {rel_path}"
                    })
            
            elif item.is_dir() and str(item.relative_to(self.sandbox_root)) != '.':
                rel_path = str(item.relative_to(self.sandbox_root))
                analysis['directories_created'].append(rel_path)
        
        # プロジェクト構造分析
        analysis['structure_analysis'] = self._analyze_project_structure(analysis)
        
        # 実行サマリー更新
        analysis['execution_summary']['total_execution_time'] = time.time() - start_time
        analysis['execution_summary']['files_created_count'] = len(analysis['files_created'])
        analysis['execution_summary']['files_modified_count'] = len(analysis['files_modified'])
        
        # 実行成功フラグを追加
        analysis['execution_success'] = True
        
        self.log_execution("analysis_complete", {
            "files_analyzed": len(analysis['content_analysis']),
            "directories_found": len(analysis['directories_created']),
            "summary": f"分析完了: {len(analysis['content_analysis'])}ファイル"
        })
        
        return analysis
    
    def _get_config_edit_response(self) -> List[str]:
        """設定ファイル編集応答"""
        return ["""config.jsonファイルを編集してデバッグモードを有効にし、monitoring機能を追加します。

FILE_OPERATION:EDIT config.json
```json
{
  "database": {
    "host": "localhost",
    "port": 5432,
    "name": "testdb"
  },
  "debug": true,
  "features": ["auth", "logging", "monitoring"]
}
```

config.jsonを更新しました：
- デバッグモードを有効化（debug: true）
- 新機能 'monitoring' をfeaturesリストに追加
- 既存の設定は保持"""]
    
    def _get_project_analysis_response(self) -> List[str]:
        """プロジェクト分析・修正応答"""
        return ["""プロジェクトを分析して問題点を修正し、テストを追加します。

FILE_OPERATION:EDIT calculator.py
```python
def add(a, b):
    '''2つの数値を加算'''
    return a + b

def subtract(a, b):
    '''2つの数値を減算'''
    return a - b

def multiply(a, b):
    '''2つの数値を乗算'''
    return a * b

def divide(a, b):
    '''2つの数値を除算（ゼロ除算エラー対応済み）'''
    if b == 0:
        raise ZeroDivisionError("Division by zero is not allowed")
    return a / b

if __name__ == "__main__":
    # テストコード（安全版）
    print(f"加算: {add(1, 2)}")
    print(f"減算: {subtract(5, 3)}")
    print(f"乗算: {multiply(4, 5)}")
    print(f"除算: {divide(10, 2)}")
    
    # ゼロ除算のエラーハンドリング例
    try:
        result = divide(10, 0)
        print(f"除算結果: {result}")
    except ZeroDivisionError as e:
        print(f"エラー: {e}")
```

FILE_OPERATION:CREATE test_calculator.py
```python
import pytest
from calculator import add, subtract, multiply, divide

def test_add():
    '''加算のテスト'''
    assert add(2, 3) == 5
    assert add(-1, 1) == 0
    assert add(0, 0) == 0

def test_subtract():
    '''減算のテスト'''
    assert subtract(5, 3) == 2
    assert subtract(3, 5) == -2
    assert subtract(0, 0) == 0

def test_multiply():
    '''乗算のテスト'''
    assert multiply(3, 4) == 12
    assert multiply(-2, 3) == -6
    assert multiply(0, 5) == 0

def test_divide():
    '''除算のテスト'''
    assert divide(10, 2) == 5
    assert divide(9, 3) == 3
    assert divide(-6, 2) == -3

def test_divide_by_zero():
    '''ゼロ除算のエラーテスト'''
    with pytest.raises(ZeroDivisionError, match="Division by zero is not allowed"):
        divide(10, 0)

if __name__ == "__main__":
    pytest.main([__file__])
```

## 修正内容:
- calculator.py: ゼロ除算エラーハンドリング追加
- test_calculator.py: 包括的なテストスイートを作成
- 全関数にdocstringを追加
- 適切なエラーメッセージを実装"""]
    
    def _get_flask_app_response(self) -> List[str]:
        """Flask Webアプリ作成応答"""
        return ["""FlaskでWebアプリケーションを作成します。

FILE_OPERATION:CREATE app.py
```python
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

@app.route('/')
def index():
    '''メインページ - 名前入力フォーム'''
    return render_template('index.html')

@app.route('/greet', methods=['POST'])
def greet():
    '''挨拶ページ - 入力された名前で挨拶'''
    name = request.form.get('name', '名無し')
    return render_template('greet.html', name=name)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
```

FILE_OPERATION:CREATE templates/index.html
```html
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>挨拶アプリ</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .container { max-width: 500px; margin: 0 auto; text-align: center; }
        input[type="text"] { padding: 10px; margin: 10px; width: 200px; }
        input[type="submit"] { padding: 10px 20px; background-color: #007bff; color: white; border: none; cursor: pointer; }
    </style>
</head>
<body>
    <div class="container">
        <h1>挨拶アプリ</h1>
        <form method="POST" action="/greet">
            <p>お名前を入力してください：</p>
            <input type="text" name="name" placeholder="お名前" required>
            <br>
            <input type="submit" value="挨拶する">
        </form>
    </div>
</body>
</html>
```

FILE_OPERATION:CREATE templates/greet.html
```html
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>挨拶結果</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .container { max-width: 500px; margin: 0 auto; text-align: center; }
        .greeting { font-size: 24px; color: #007bff; margin: 30px 0; }
        a { color: #007bff; text-decoration: none; }
    </style>
</head>
<body>
    <div class="container">
        <h1>挨拶結果</h1>
        <div class="greeting">
            こんにちは、{{ name }}さん！
        </div>
        <p><a href="/">もう一度</a></p>
    </div>
</body>
</html>
```

## 作成した機能:
- Flask Webアプリケーション
- 名前入力フォーム（index.html）
- 挨拶表示ページ（greet.html）
- POST/GETルーティング
- レスポンシブデザイン"""]
    
    def _analyze_project_content(self, file_path: str, content: str, project_analysis: Dict) -> None:
        """
        ファイル内容からプロジェクト情報を抽出
        
        Args:
            file_path: ファイルパス
            content: ファイル内容
            project_analysis: プロジェクト分析結果
        """
        project_analysis['files_analyzed'].append(file_path)
        
        content_lower = content.lower()
        
        # フレームワーク検出
        framework_patterns = {
            'Flask': ['flask', '@app.route', 'from flask import'],
            'Django': ['django', 'from django import', 'django.conf'],
            'FastAPI': ['fastapi', '@app.get', '@app.post', 'from fastapi'],
            'React': ['react', 'jsx', 'usestate', 'useeffect'],
            'Vue': ['vue', 'v-if', 'v-for', 'createapp']
        }
        
        for framework, patterns in framework_patterns.items():
            if any(pattern in content_lower for pattern in patterns):
                project_analysis['framework_detected'] = framework
                break
        
        # 依存関係検出
        if file_path == 'requirements.txt':
            for line in content.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    # パッケージ名の抽出（バージョン指定を除く）
                    package_name = re.split(r'[>=<!=]', line)[0].strip()
                    if package_name:
                        project_analysis['dependencies_identified'].append(package_name)
        
        # import文からの依存関係検出
        if file_path.endswith('.py'):
            import_patterns = [
                r'^import\s+([a-zA-Z_][a-zA-Z0-9_]*)',
                r'^from\s+([a-zA-Z_][a-zA-Z0-9_]*)'
            ]
            
            for pattern in import_patterns:
                imports = re.findall(pattern, content, re.MULTILINE)
                project_analysis['dependencies_identified'].extend(imports)
        
        # プロジェクトタイプ推定
        web_indicators = ['flask', 'django', 'fastapi', '@app.route', 'templates/', 'static/']
        package_indicators = ['setup.py', '__init__.py', 'pyproject.toml']
        script_indicators = ['if __name__ == "__main__":', 'main.py', 'app.py']
        
        if any(indicator in content_lower for indicator in web_indicators):
            project_analysis['project_type'] = 'web_application'
        elif any(file_path.endswith(indicator) or indicator in file_path for indicator in package_indicators):
            project_analysis['project_type'] = 'python_package'
        elif any(indicator in content_lower or indicator in file_path for indicator in script_indicators):
            project_analysis['project_type'] = 'script_application'
        
        # 重複除去
        project_analysis['dependencies_identified'] = list(set(project_analysis['dependencies_identified']))
    
    def _analyze_project_structure(self, analysis: Dict) -> Dict[str, Any]:
        """
        プロジェクト構造の妥当性分析
        
        Args:
            analysis: 基本分析結果
            
        Returns:
            Dict: 構造分析結果
        """
        structure_analysis = {
            'has_main_file': False,
            'has_config': False,
            'has_requirements': False,
            'has_tests': False,
            'has_documentation': False,
            'has_templates': False,
            'has_static_files': False,
            'directory_structure_valid': True,
            'flask_app_structure': False,
            'python_package_structure': False
        }
        
        all_files = analysis['files_created'] + analysis['files_modified']
        all_dirs = analysis['directories_created']
        
        # 主要ファイルの存在チェック
        main_files = ['main.py', 'app.py', '__main__.py', 'run.py']
        structure_analysis['has_main_file'] = any(f in all_files for f in main_files)
        
        config_files = ['config.py', 'settings.py', '.env', 'config.yaml', 'config.json']
        structure_analysis['has_config'] = any(f in all_files for f in config_files)
        
        structure_analysis['has_requirements'] = 'requirements.txt' in all_files
        
        test_indicators = ['test_', 'tests/', '_test.py']
        structure_analysis['has_tests'] = any(
            any(indicator in f for indicator in test_indicators) 
            for f in all_files + all_dirs
        )
        
        doc_files = [f for f in all_files if f.endswith('.md') or f.endswith('.rst')]
        structure_analysis['has_documentation'] = len(doc_files) > 0
        
        structure_analysis['has_templates'] = any('template' in d.lower() for d in all_dirs)
        structure_analysis['has_static_files'] = any('static' in d.lower() for d in all_dirs)
        
        # Flask特有の構造チェック
        flask_indicators = [
            structure_analysis['has_templates'],
            structure_analysis['has_static_files'],
            'app.py' in all_files,
            analysis['project_analysis']['framework_detected'] == 'Flask'
        ]
        structure_analysis['flask_app_structure'] = sum(flask_indicators) >= 2
        
        # Pythonパッケージ構造チェック
        package_indicators = [
            'setup.py' in all_files,
            any('__init__.py' in f for f in all_files),
            structure_analysis['has_requirements'],
            structure_analysis['has_tests']
        ]
        structure_analysis['python_package_structure'] = sum(package_indicators) >= 2
        
        return structure_analysis


class SandboxTestRunner:
    """サンドボックステストの実行・評価管理"""
    
    def __init__(self):
        """テストランナーの初期化"""
        self.test_scenarios = []
        self.results_history = []
        self.created_at = datetime.now()
    
    def load_test_scenarios(self, scenarios: Optional[List[Dict]] = None) -> None:
        """
        テストシナリオを読み込み
        
        Args:
            scenarios: シナリオリスト（Noneの場合はデフォルトシナリオを使用）
        """
        if scenarios is None:
            scenarios = self._get_default_scenarios()
        
        self.test_scenarios = scenarios
        print(f"[RUNNER] シナリオ読み込み完了: {len(scenarios)}個")
    
    def _get_default_scenarios(self) -> List[Dict]:
        """デフォルトテストシナリオを取得"""
        return [
            {
                "name": "basic_file_creation",
                "description": "単一Pythonファイルの作成",
                "user_input": "Hello Worldを出力するPythonファイル test.py を作成してください",
                "expected_results": {
                    "files_created": ["test.py"],
                    "content_contains": {"test.py": ["print", "Hello World"]},
                    "syntax_valid": {"test.py": True}
                },
                "risk_level": "LOW",
                "timeout": 30
            },
            {
                "name": "python_package_creation",
                "description": "Pythonパッケージ構造の作成",
                "user_input": "Pythonパッケージの基本構造を作成してください。パッケージ名はmyappです",
                "expected_results": {
                    "directories_created": ["myapp", "tests"],
                    "files_created": ["setup.py", "myapp/__init__.py", "requirements.txt", "README.md"],
                    "structure_analysis": {
                        "python_package_structure": True,
                        "has_requirements": True,
                        "has_documentation": True
                    }
                },
                "risk_level": "MEDIUM",
                "timeout": 60
            }
        ]
    
    def run_scenario(self, scenario: Dict) -> Dict[str, Any]:
        """
        単一シナリオの実行と評価
        
        Args:
            scenario: シナリオ設定
            
        Returns:
            Dict: 実行結果と評価
        """
        scenario_start = time.time()
        
        print(f"\n{'='*70}")
        print(f"[START] シナリオ実行: {scenario['name']}")
        print(f"📝 説明: {scenario['description']}")
        print(f"[FAST] リスクレベル: {scenario.get('risk_level', 'UNKNOWN')}")
        print('='*70)
        
        try:
            # サンドボックス環境で実行
            with FileSystemSandbox(scenario['name']) as sandbox:
                # 初期ファイル設定
                if 'setup_files' in scenario:
                    sandbox.setup_scenario_files(scenario['setup_files'])
                
                # シナリオ実行
                results = sandbox.execute_duckflow_scenario(scenario['user_input'])
                
                # 期待結果との比較評価
                evaluation = self.evaluate_results(results, scenario['expected_results'])
                
                execution_time = time.time() - scenario_start
                
                # 結果構築
                result = {
                    'scenario': scenario['name'],
                    'description': scenario['description'],
                    'user_input': scenario['user_input'],
                    'execution_time': execution_time,
                    'results': results,
                    'evaluation': evaluation,
                    'passed': evaluation['overall_score'] >= 0.7,
                    'timestamp': datetime.now().isoformat(),
                    'sandbox_log': sandbox.execution_log
                }
                
                # 結果表示
                self._display_scenario_result(result)
                
                return result
                
        except Exception as e:
            execution_time = time.time() - scenario_start
            
            error_result = {
                'scenario': scenario['name'],
                'description': scenario['description'],
                'execution_time': execution_time,
                'passed': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
            
            print(f"[ERROR] シナリオ実行エラー: {e}")
            return error_result
    
    def _display_scenario_result(self, result: Dict) -> None:
        """シナリオ結果の表示"""
        passed = result['passed']
        score = result['evaluation']['overall_score']
        execution_time = result['execution_time']
        
        status_icon = "[SUCCESS]" if passed else "[ERROR]"
        status_text = "PASS" if passed else "FAIL"
        
        print(f"\n{status_icon} **{status_text}** - {result['scenario']}")
        print(f"   [STATS] 総合スコア: {score:.3f}")
        print(f"   [TIME]  実行時間: {execution_time:.2f}秒")
        
        # 詳細スコア表示
        eval_details = result['evaluation']
        if 'details' in eval_details:
            details = eval_details['details']
            if 'file_creation' in details:
                fc = details['file_creation']
                print(f"   📁 ファイル作成: {len(fc['matches'])}/{len(fc['expected'])}")
        
        if not passed:
            print(f"   [WARNING]  主な問題: 総合スコア {score:.3f} < 0.7")
    
    def run_all_scenarios(self) -> Dict[str, Any]:
        """
        全シナリオの実行と総合評価
        
        Returns:
            Dict: 総合結果
        """
        start_time = time.time()
        
        print("[TARGET] Duckflow サンドボックス評価テスト開始")
        print("="*80)
        print(f"[INFO] 実行予定シナリオ: {len(self.test_scenarios)}個")
        print("="*80)
        
        results = []
        passed_count = 0
        total_execution_time = 0
        
        for i, scenario in enumerate(self.test_scenarios, 1):
            print(f"\n[{i}/{len(self.test_scenarios)}] {scenario['name']} 開始...")
            
            result = self.run_scenario(scenario)
            results.append(result)
            
            if result['passed']:
                passed_count += 1
            
            total_execution_time += result['execution_time']
        
        # 総合結果
        total_time = time.time() - start_time
        success_rate = passed_count / len(self.test_scenarios) if self.test_scenarios else 0
        
        summary = {
            'total_scenarios': len(self.test_scenarios),
            'passed': passed_count,
            'failed': len(self.test_scenarios) - passed_count,
            'success_rate': success_rate,
            'total_execution_time': total_time,
            'scenario_execution_time': total_execution_time,
            'detailed_results': results,
            'timestamp': datetime.now().isoformat()
        }
        
        # 結果サマリー表示
        self._display_summary(summary)
        
        # 履歴に保存
        self.results_history.append(summary)
        
        return summary
    
    def _display_summary(self, summary: Dict) -> None:
        """総合結果サマリーの表示"""
        print("\n" + "="*80)
        print("[STATS] **テスト結果サマリー**")
        print("="*80)
        
        print(f"[STATS] 総合結果:")
        print(f"   [TARGET] 総シナリオ数: {summary['total_scenarios']}")
        print(f"   [SUCCESS] 成功: {summary['passed']}")
        print(f"   [ERROR] 失敗: {summary['failed']}")
        print(f"   [STATS] 成功率: {summary['success_rate']:.1%}")
        
        print(f"\n[TIME]  実行時間:")
        print(f"   [CLOCK] 総実行時間: {summary['total_execution_time']:.2f}秒")
        print(f"   [FAST] シナリオ実行時間: {summary['scenario_execution_time']:.2f}秒")
        
        # 成功率に応じたメッセージ
        if summary['success_rate'] >= 0.9:
            print(f"\n[COMPLETE] 優秀！ほぼ全ての機能が正常に動作しています")
        elif summary['success_rate'] >= 0.7:
            print(f"\n[GOOD] 良好！基本機能は正常に動作しています")
        elif summary['success_rate'] >= 0.5:
            print(f"\n[WARNING]  改善の余地あり。いくつかの機能で問題があります")
        else:
            print(f"\n[FIX] 要改善。多くの機能で問題が発生しています")
        
        print("="*80)
    
    def evaluate_results(self, actual: Dict, expected: Dict) -> Dict[str, Any]:
        """
        実行結果の詳細評価
        
        Args:
            actual: 実際の実行結果
            expected: 期待される結果
            
        Returns:
            Dict: 評価結果
        """
        evaluation = {
            'file_creation_score': 0.0,
            'content_score': 0.0,
            'syntax_score': 0.0,
            'project_analysis_score': 0.0,
            'structure_score': 0.0,
            'overall_score': 0.0,
            'details': {}
        }
        
        scores = []
        
        # 1. ファイル作成評価
        if 'files_created' in expected:
            expected_files = set(expected['files_created'])
            actual_files = set(actual.get('files_created', []))
            
            if expected_files:
                matches = expected_files & actual_files
                evaluation['file_creation_score'] = len(matches) / len(expected_files)
                evaluation['details']['file_creation'] = {
                    'expected': list(expected_files),
                    'actual': list(actual_files),
                    'matches': list(matches),
                    'missing': list(expected_files - actual_files),
                    'extra': list(actual_files - expected_files)
                }
                scores.append(evaluation['file_creation_score'])
        
        # 2. 内容評価
        if 'content_contains' in expected:
            content_scores = []
            
            for file_path, expected_keywords in expected['content_contains'].items():
                if file_path in actual.get('content_analysis', {}):
                    actual_content = actual['content_analysis'][file_path].lower()
                    keyword_matches = sum(1 for keyword in expected_keywords 
                                        if keyword.lower() in actual_content)
                    if expected_keywords:
                        content_scores.append(keyword_matches / len(expected_keywords))
            
            if content_scores:
                evaluation['content_score'] = sum(content_scores) / len(content_scores)
                scores.append(evaluation['content_score'])
        
        # 3. 構文評価
        if 'syntax_valid' in expected:
            syntax_scores = []
            
            for file_path, expected_valid in expected['syntax_valid'].items():
                actual_valid = actual.get('syntax_validation', {}).get(file_path, False)
                syntax_scores.append(1.0 if actual_valid == expected_valid else 0.0)
            
            if syntax_scores:
                evaluation['syntax_score'] = sum(syntax_scores) / len(syntax_scores)
                scores.append(evaluation['syntax_score'])
        
        # 4. プロジェクト分析評価
        if 'project_analysis' in expected:
            pa_scores = []
            expected_pa = expected['project_analysis']
            actual_pa = actual.get('project_analysis', {})
            
            # フレームワーク検出
            if 'framework_detected' in expected_pa:
                expected_fw = expected_pa['framework_detected']
                actual_fw = actual_pa.get('framework_detected')
                pa_scores.append(1.0 if actual_fw == expected_fw else 0.0)
            
            # プロジェクトタイプ
            if 'project_type' in expected_pa:
                expected_type = expected_pa['project_type']
                actual_type = actual_pa.get('project_type')
                pa_scores.append(1.0 if actual_type == expected_type else 0.0)
            
            # 依存関係
            if 'dependencies_identified' in expected_pa:
                expected_deps = set(expected_pa['dependencies_identified'])
                actual_deps = set(actual_pa.get('dependencies_identified', []))
                if expected_deps:
                    dep_score = len(expected_deps & actual_deps) / len(expected_deps)
                    pa_scores.append(dep_score)
            
            if pa_scores:
                evaluation['project_analysis_score'] = sum(pa_scores) / len(pa_scores)
                scores.append(evaluation['project_analysis_score'])
        
        # 5. 構造評価
        if 'structure_analysis' in expected:
            sa_scores = []
            expected_sa = expected['structure_analysis']
            actual_sa = actual.get('structure_analysis', {})
            
            for key, expected_value in expected_sa.items():
                actual_value = actual_sa.get(key)
                sa_scores.append(1.0 if actual_value == expected_value else 0.0)
            
            if sa_scores:
                evaluation['structure_score'] = sum(sa_scores) / len(sa_scores)
                scores.append(evaluation['structure_score'])
        
        # 総合スコア計算
        if scores:
            evaluation['overall_score'] = sum(scores) / len(scores)
        
        return evaluation


# デモ・テスト実行用の便利関数
def run_quick_demo():
    """クイックデモの実行"""
    print("[START] Duckflow サンドボックス クイックデモ")
    print("="*50)
    
    runner = SandboxTestRunner()
    runner.load_test_scenarios()
    
    # 最初のシナリオのみ実行
    if runner.test_scenarios:
        first_scenario = runner.test_scenarios[0]
        result = runner.run_scenario(first_scenario)
        
        print(f"\n[INFO] **デモ実行完了**")
        print(f"シナリオ: {result['scenario']}")
        print(f"結果: {'[SUCCESS] 成功' if result['passed'] else '[ERROR] 失敗'}")
    else:
        print("[ERROR] 実行するシナリオがありません")


if __name__ == "__main__":
    # デモ実行
    run_quick_demo()