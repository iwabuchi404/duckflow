#!/usr/bin/env python3
"""
Duckflow サンドボックス評価システム - 基盤フレームワーク（修正版）

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
        if "hello.py" in user_input_lower or "hello, world!" in user_input_lower:
            return self._get_hello_world_response()
        elif "mathutils" in user_input_lower or "setup.py" in user_input_lower:
            return self._get_python_package_response()
        elif "config.json" in user_input_lower and "monitoring" in user_input_lower:
            return self._get_config_edit_response()
        elif ("分析" in user_input_lower and "問題点" in user_input_lower) or "calculator" in user_input_lower:
            return self._get_project_analysis_response()
        elif "flask" in user_input_lower or "webアプリ" in user_input_lower:
            return self._get_flask_app_response()
        else:
            return self._get_default_response(user_input)
    
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

hello.pyファイルを作成しました。"""]
    
    def _get_python_package_response(self) -> List[str]:
        """Pythonパッケージ作成応答"""
        return ["""新しいPythonライブラリプロジェクト 'mathutils' を作成します。

FILE_OPERATION:CREATE setup.py
```python
from setuptools import setup, find_packages

setup(
    name="mathutils",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
)
```

FILE_OPERATION:CREATE src/mathutils/__init__.py
```python
'''mathutils - 数学ユーティリティライブラリ'''
__version__ = "0.1.0"
```

FILE_OPERATION:CREATE src/mathutils/basic.py
```python
'''基本的な数学演算モジュール'''

def add(a, b):
    return a + b

def subtract(a, b):
    return a - b
```

FILE_OPERATION:CREATE tests/__init__.py
```python
'''mathutils テストパッケージ'''
```

FILE_OPERATION:CREATE tests/test_basic.py
```python
'''basic モジュールのテスト'''
import pytest
from mathutils.basic import add, subtract

def test_add():
    assert add(2, 3) == 5

def test_subtract():
    assert subtract(5, 3) == 2
```

FILE_OPERATION:CREATE requirements.txt
```
pytest>=6.0.0
```

FILE_OPERATION:CREATE README.md
```markdown
# MathUtils

数学計算のためのシンプルなPythonライブラリです。
```

標準的なPythonパッケージ構造を作成しました。"""]
    
    def _get_config_edit_response(self) -> List[str]:
        """設定ファイル編集応答"""
        return ["""config.jsonファイルを編集します。

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

config.jsonを更新しました。"""]
    
    def _get_project_analysis_response(self) -> List[str]:
        """プロジェクト分析・修正応答"""
        return ["""プロジェクトを分析して問題点を修正します。

FILE_OPERATION:EDIT calculator.py
```python
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b

def multiply(a, b):
    return a * b

def divide(a, b):
    if b == 0:
        raise ZeroDivisionError("Division by zero is not allowed")
    return a / b

if __name__ == "__main__":
    print(f"加算: {add(1, 2)}")
    try:
        result = divide(10, 0)
    except ZeroDivisionError as e:
        print(f"エラー: {e}")
```

FILE_OPERATION:CREATE test_calculator.py
```python
import pytest
from calculator import add, subtract, multiply, divide

def test_add():
    assert add(2, 3) == 5

def test_divide_by_zero():
    with pytest.raises(ZeroDivisionError):
        divide(10, 0)
```

calculator.pyにエラーハンドリングを追加し、テストを作成しました。"""]
    
    def _get_flask_app_response(self) -> List[str]:
        """Flask Webアプリ作成応答"""
        return ["""FlaskでWebアプリケーションを作成します。

FILE_OPERATION:CREATE app.py
```python
from flask import Flask, render_template, request

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/greet', methods=['POST'])
def greet():
    name = request.form.get('name', '名無し')
    return render_template('greet.html', name=name)

if __name__ == '__main__':
    app.run(debug=True)
```

FILE_OPERATION:CREATE templates/index.html
```html
<!DOCTYPE html>
<html>
<head><title>挨拶アプリ</title></head>
<body>
    <h1>挨拶アプリ</h1>
    <form method="POST" action="/greet">
        <input type="text" name="name" placeholder="お名前" required>
        <input type="submit" value="挨拶する">
    </form>
</body>
</html>
```

FILE_OPERATION:CREATE templates/greet.html
```html
<!DOCTYPE html>
<html>
<head><title>挨拶結果</title></head>
<body>
    <h1>こんにちは、{{ name }}さん！</h1>
    <a href="/">戻る</a>
</body>
</html>
```

Flask Webアプリケーションを作成しました。"""]
    
    def _get_default_response(self, user_input: str) -> List[str]:
        """デフォルト応答"""
        return [f"""ユーザーからの要求「{user_input}」を処理します。

FILE_OPERATION:CREATE example.txt
```
このファイルは Duckflow によって作成されました。
ユーザー要求: {user_input}
作成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
```

example.txtを作成しました。"""]
    
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
            'execution_success': True,
            'execution_summary': {
                'total_execution_time': 0,
                'files_created_count': 0,
                'files_modified_count': 0
            }
        }
        
        # ファイルシステムをスキャン
        for item in self.sandbox_root.rglob('*'):
            if item.is_file():
                rel_path = str(item.relative_to(self.sandbox_root))
                if rel_path not in self.initial_files:
                    analysis['files_created'].append(rel_path)
                
                try:
                    if item.suffix in ['.py', '.html', '.css', '.txt', '.md', '.json']:
                        content = item.read_text(encoding='utf-8')
                        analysis['content_analysis'][rel_path] = content
                        
                        # Python構文チェック
                        if item.suffix == '.py':
                            try:
                                ast.parse(content)
                                analysis['syntax_validation'][rel_path] = True
                            except SyntaxError:
                                analysis['syntax_validation'][rel_path] = False
                except Exception:
                    pass
            
            elif item.is_dir():
                rel_path = str(item.relative_to(self.sandbox_root))
                if rel_path != '.':
                    analysis['directories_created'].append(rel_path)
        
        # 実行サマリー更新
        analysis['execution_summary']['total_execution_time'] = time.time() - start_time
        analysis['execution_summary']['files_created_count'] = len(analysis['files_created'])
        analysis['execution_summary']['files_modified_count'] = len(analysis['files_modified'])
        
        self.log_execution("analysis_complete", {
            "files_analyzed": len(analysis['content_analysis']),
            "summary": f"分析完了: {len(analysis['content_analysis'])}ファイル"
        })
        
        return analysis


class SandboxTestRunner:
    """サンドボックステストの実行・評価管理（評価エンジン統合版）"""
    
    def __init__(self):
        self.test_scenarios = []
        self.results = {}
        # 評価エンジンを統合
        import os
        metrics_path = os.path.join(os.path.dirname(__file__), "metrics_history.json")
        
        try:
            from evaluation_engine import EvaluationEngine, MetricsCollector
            self.evaluation_engine = EvaluationEngine()
            self.metrics_collector = MetricsCollector(metrics_path)
            self.evaluation_enabled = True
        except ImportError:
            try:
                from .evaluation_engine import EvaluationEngine, MetricsCollector
                self.evaluation_engine = EvaluationEngine()
                self.metrics_collector = MetricsCollector(metrics_path)
                self.evaluation_enabled = True
            except ImportError:
                self.evaluation_enabled = False
                print("[WARNING] 評価エンジンが利用できません")
        
        # テストシナリオを事前にロード
        self._load_test_scenarios()
    
    def _load_test_scenarios(self) -> None:
        """テストシナリオを動的にロード"""
        try:
            from test_scenarios import TestScenarios
        except ImportError:
            try:
                from .test_scenarios import TestScenarios
            except ImportError:
                print("[WARNING] TestScenariosの読み込みに失敗しました")
                return
        
        try:
            self.test_scenarios = [
                TestScenarios.get_scenario_1_basic_file_creation(),
                TestScenarios.get_scenario_2_project_structure(),
                TestScenarios.get_scenario_3_config_modification(),
                TestScenarios.get_scenario_4_project_analysis(),
                TestScenarios.get_scenario_5_web_app()
            ]
        except Exception as e:
            print(f"[WARNING] テストシナリオの読み込み中にエラーが発生: {e}")
            self.test_scenarios = []
    
    def run_all_scenarios(self) -> Dict[str, Any]:
        """全シナリオを実行して結果を返す"""
        print("[TARGET] Duckflow サンドボックステスト開始")
        print("=" * 80)
        
        if not self.test_scenarios:
            print("[ERROR] テストシナリオがロードされていません")
            return {'error': 'シナリオロード失敗'}
        
        scenarios = self.test_scenarios
        print(f"[INFO] 実行可能シナリオ: {len(scenarios)}個")
        print("=" * 80)
        
        results = {}
        total_start_time = time.time()
        
        try:
            for i, scenario in enumerate(scenarios, 1):
                print(f"\n[SCENARIO {i}] {scenario['name']}")
                print("-" * 60)
                
                scenario_start_time = time.time()
                
                with FileSystemSandbox(f"scenario_{i}") as sandbox:
                    # セットアップ
                    sandbox.setup_scenario_files(scenario.get('setup_files', []))
                    
                    # 実行
                    execution_result = sandbox.execute_duckflow_scenario(scenario['user_input'])
                    scenario_time = time.time() - scenario_start_time
                    
                    # 評価エンジンによる詳細評価
                    if self.evaluation_enabled:
                        evaluation = self.evaluation_engine.evaluate_scenario(
                            scenario['name'],
                            scenario['expected_results'],
                            execution_result,
                            {'execution_time': scenario_time}
                        )
                        
                        # メトリクス保存
                        self.metrics_collector.store_evaluation(evaluation)
                        
                        # 結果表示
                        self._display_detailed_evaluation(evaluation)
                        
                        results[scenario['name']] = {
                            'passed': evaluation.metrics.overall_score >= 70,
                            'score': evaluation.metrics.overall_score,
                            'execution_time': scenario_time,
                            'evaluation': evaluation
                        }
                    else:
                        # 基本評価のみ
                        basic_passed = len(execution_result.get('files_created', [])) > 0
                        results[scenario['name']] = {
                            'passed': basic_passed,
                            'score': 80 if basic_passed else 40,
                            'execution_time': scenario_time
                        }
            
            total_time = time.time() - total_start_time
            
            # サマリー生成
            summary = self._generate_summary(results, total_time)
            self._display_summary(summary)
            
            return summary
            
        except Exception as e:
            print(f"[ERROR] シナリオ実行中にエラーが発生: {e}")
            return {'error': 'シナリオ実行失敗'}
    
    def _display_detailed_evaluation(self, evaluation) -> None:
        """詳細評価結果の表示"""
        metrics = evaluation.metrics
        
        print(f"[EVALUATION] 総合スコア: {metrics.overall_score:.1f}/100")
        print(f"  品質スコア: {metrics.quality_score:.1f}/100")
        print(f"  完成度スコア: {metrics.completeness_score:.1f}/100") 
        print(f"  効率性スコア: {metrics.efficiency_score:.1f}/100")
        print(f"  実行時間: {metrics.execution_time:.2f}秒")
        print(f"  作成ファイル数: {metrics.files_created}")
        print(f"  生成コード行数: {metrics.lines_of_code}")
        
        if metrics.syntax_errors:
            print(f"[ISSUES] 構文エラー: {len(metrics.syntax_errors)}件")
        
        if evaluation.recommendations:
            print("[RECOMMENDATIONS]")
            for i, rec in enumerate(evaluation.recommendations[:3], 1):
                print(f"  {i}. {rec}")
    
    def _generate_summary(self, results: Dict, total_time: float) -> Dict[str, Any]:
        """実行サマリー生成"""
        total_scenarios = len(results)
        passed = sum(1 for r in results.values() if r['passed'])
        failed = total_scenarios - passed
        success_rate = passed / total_scenarios if total_scenarios > 0 else 0
        
        # 平均スコア計算
        avg_score = sum(r['score'] for r in results.values()) / total_scenarios if total_scenarios > 0 else 0
        
        return {
            'total_scenarios': total_scenarios,
            'passed': passed,
            'failed': failed,
            'success_rate': success_rate,
            'average_score': avg_score,
            'total_execution_time': total_time,
            'scenario_results': results
        }
    
    def get_metrics_report(self) -> Dict[str, Any]:
        """メトリクスレポート取得"""
        if self.evaluation_enabled:
            return self.metrics_collector.generate_summary_report()
        else:
            return {'error': '評価エンジンが無効です'}
    
    def get_trend_analysis(self, days: int = 7) -> Dict[str, Any]:
        """トレンド分析取得"""
        if self.evaluation_enabled:
            return self.metrics_collector.get_trend_analysis(days)
        else:
            return {'error': '評価エンジンが無効です'}
    
    def _display_summary(self, summary: Dict) -> None:
        """総合結果サマリーの表示"""
        print("\n" + "=" * 80)
        print("[STATS] **テスト結果サマリー**")
        print("=" * 80)
        
        print(f"[STATS] 総合結果:")
        print(f"   [TARGET] 総シナリオ数: {summary['total_scenarios']}")
        print(f"   [SUCCESS] 成功: {summary['passed']}")
        print(f"   [ERROR] 失敗: {summary['failed']}")
        print(f"   [STATS] 成功率: {summary['success_rate']:.1%}")
        
        print(f"\n[TIME]  実行時間:")
        print(f"   [CLOCK] 総実行時間: {summary['total_execution_time']:.2f}秒")
        
        # 成功率に応じたメッセージ
        if summary['success_rate'] >= 0.9:
            print(f"\n[COMPLETE] 優秀！ほぼ全ての機能が正常に動作しています")
        elif summary['success_rate'] >= 0.7:
            print(f"\n[GOOD] 良好！基本機能は正常に動作しています")
        elif summary['success_rate'] >= 0.5:
            print(f"\n[WARNING]  改善の余地あり。いくつかの機能で問題があります")
        else:
            print(f"\n[FIX] 要改善。多くの機能で問題が発生しています")
        
        print("=" * 80)