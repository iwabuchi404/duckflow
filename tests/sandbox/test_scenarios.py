#!/usr/bin/env python3
"""
Duckflow サンドボックス評価システム - テストシナリオ定義

5つの主要な開発シナリオを定義し、評価テストを実行する
"""

import pytest
import json
from pathlib import Path
from typing import Dict, List, Any

try:
    from .sandbox_framework import FileSystemSandbox, SandboxTestRunner
except ImportError:
    from sandbox_framework import FileSystemSandbox, SandboxTestRunner


class TestScenarios:
    """サンドボックステストシナリオの定義クラス"""
    
    @staticmethod
    def get_scenario_1_basic_file_creation() -> Dict[str, Any]:
        """シナリオ1: 基本的なファイル作成・編集"""
        return {
            "name": "基本ファイル作成",
            "description": "簡単なPythonファイルの作成と編集",
            "setup_files": [
                {
                    "path": "README.md", 
                    "content": "# テストプロジェクト\n\n新しいPythonプロジェクト"
                }
            ],
            "user_input": "hello.py という名前で 'Hello, World!' を出力するPythonファイルを作成してください",
            "expected_results": {
                "files_created": ["hello.py"],
                "file_contents": {
                    "hello.py": {
                        "contains": ["print", "Hello, World!"],
                        "syntax_valid": True
                    }
                },
                "project_analysis": {
                    "language": "python",
                    "file_count": 2,
                    "has_executable": True
                }
            }
        }
    
    @staticmethod
    def get_scenario_2_project_structure() -> Dict[str, Any]:
        """シナリオ2: プロジェクト構造の作成"""
        return {
            "name": "プロジェクト構造作成",
            "description": "完全なPythonプロジェクト構造の構築",
            "setup_files": [],
            "user_input": "新しいPythonライブラリプロジェクト 'mathutils' を作成してください。src/、tests/、setup.pyを含む標準的な構造で",
            "expected_results": {
                "files_created": [
                    "setup.py", "requirements.txt", "README.md",
                    "src/mathutils/__init__.py", "src/mathutils/basic.py",
                    "tests/__init__.py", "tests/test_basic.py"
                ],
                "directories_created": ["src", "src/mathutils", "tests"],
                "project_analysis": {
                    "language": "python",
                    "has_package_structure": True,
                    "has_tests": True,
                    "framework": "setuptools"
                }
            }
        }
    
    @staticmethod
    def get_scenario_3_config_modification() -> Dict[str, Any]:
        """シナリオ3: 設定ファイルの修正"""
        return {
            "name": "設定ファイル修正",
            "description": "既存の設定ファイルの安全な変更",
            "setup_files": [
                {
                    "path": "config.json",
                    "content": json.dumps({
                        "database": {
                            "host": "localhost",
                            "port": 5432,
                            "name": "testdb"
                        },
                        "debug": False,
                        "features": ["auth", "logging"]
                    }, indent=2)
                },
                {
                    "path": "app.py",
                    "content": """import json

def load_config():
    with open('config.json', 'r') as f:
        return json.load(f)

if __name__ == '__main__':
    config = load_config()
    print(f"Connecting to {config['database']['host']}")
"""
                }
            ],
            "user_input": "config.jsonでデバッグモードを有効にし、新しい機能 'monitoring' を features リストに追加してください",
            "expected_results": {
                "files_modified": ["config.json"],
                "file_contents": {
                    "config.json": {
                        "json_valid": True,
                        "contains": ["\"debug\": true", "monitoring"],
                        "preserves": ["localhost", "5432", "testdb"]
                    }
                },
                "project_analysis": {
                    "config_files": ["config.json"],
                    "has_valid_json": True
                }
            }
        }
    
    @staticmethod
    def get_scenario_4_project_analysis() -> Dict[str, Any]:
        """シナリオ4: プロジェクト分析と改善提案"""
        return {
            "name": "プロジェクト分析",
            "description": "既存コードの分析とリファクタリング",
            "setup_files": [
                {
                    "path": "calculator.py",
                    "content": """def add(a, b):
    return a + b

def subtract(a, b):
    return a - b

def multiply(a, b):
    return a * b

def divide(a, b):
    return a / b  # ゼロ除算エラーの可能性

# テストコード
print(add(1, 2))
print(divide(10, 0))  # 問題のあるコード
"""
                },
                {
                    "path": "requirements.txt",
                    "content": "numpy==1.21.0\nrequests==2.25.1"
                }
            ],
            "user_input": "このプロジェクトを分析して、問題点を修正し、テストを追加してください",
            "expected_results": {
                "files_modified": ["calculator.py"],
                "files_created": ["test_calculator.py"],
                "improvements": {
                    "error_handling": True,
                    "tests_added": True,
                    "documentation": True
                },
                "project_analysis": {
                    "issues_found": ["zero_division", "no_tests", "no_docstrings"],
                    "issues_fixed": True
                }
            }
        }
    
    @staticmethod
    def get_scenario_5_web_app() -> Dict[str, Any]:
        """シナリオ5: Webアプリケーション開発"""
        return {
            "name": "Webアプリ開発",
            "description": "簡単なWebアプリケーションの作成",
            "setup_files": [
                {
                    "path": "requirements.txt",
                    "content": "flask==2.3.0\nwerkzeug==2.3.0"
                }
            ],
            "user_input": "Flaskを使用して、ユーザーが名前を入力すると挨拶を返すシンプルなWebアプリを作成してください",
            "expected_results": {
                "files_created": ["app.py", "templates/index.html"],
                "directories_created": ["templates"],
                "project_analysis": {
                    "language": "python",
                    "framework": "flask",
                    "has_templates": True,
                    "has_routes": True
                },
                "file_contents": {
                    "app.py": {
                        "contains": ["from flask import Flask", "@app.route", "render_template"],
                        "syntax_valid": True
                    },
                    "templates/index.html": {
                        "contains": ["<form", "input", "name"]
                    }
                }
            }
        }


class TestSandboxExecution:
    """サンドボックス実行テストクラス"""
    
    def test_scenario_1_basic_file_creation(self):
        """シナリオ1: 基本ファイル作成のテスト"""
        scenario = TestScenarios.get_scenario_1_basic_file_creation()
        
        with FileSystemSandbox("basic_file_creation") as sandbox:
            sandbox.setup_scenario_files(scenario["setup_files"])
            
            # テスト実行
            result = sandbox.execute_duckflow_scenario(scenario["user_input"])
            
            # 結果の検証
            assert result["execution_success"], f"実行失敗: {result.get('error', 'Unknown error')}"
            
            # ファイル作成の確認
            expected_files = scenario["expected_results"]["files_created"]
            for filename in expected_files:
                file_path = sandbox.sandbox_root / filename
                assert file_path.exists(), f"期待されたファイルが作成されていません: {filename}"
            
            # 内容の検証
            hello_py_content = (sandbox.sandbox_root / "hello.py").read_text(encoding='utf-8')
            expected_contains = scenario["expected_results"]["file_contents"]["hello.py"]["contains"]
            for expected in expected_contains:
                assert expected in hello_py_content, f"期待される内容が含まれていません: {expected}"
            
            print(f"[SUCCESS] {scenario['name']} テスト成功")
    
    def test_scenario_2_project_structure(self):
        """シナリオ2: プロジェクト構造作成のテスト"""
        scenario = TestScenarios.get_scenario_2_project_structure()
        
        with FileSystemSandbox("project_structure") as sandbox:
            sandbox.setup_scenario_files(scenario["setup_files"])
            
            result = sandbox.execute_duckflow_scenario(scenario["user_input"])
            
            assert result["execution_success"], f"実行失敗: {result.get('error', 'Unknown error')}"
            
            # ディレクトリ構造の確認
            for directory in scenario["expected_results"]["directories_created"]:
                dir_path = sandbox.sandbox_root / directory
                assert dir_path.exists() and dir_path.is_dir(), f"期待されたディレクトリが作成されていません: {directory}"
            
            # ファイル作成の確認
            for filename in scenario["expected_results"]["files_created"]:
                file_path = sandbox.sandbox_root / filename
                assert file_path.exists(), f"期待されたファイルが作成されていません: {filename}"
            
            print(f"[SUCCESS] {scenario['name']} テスト成功")
    
    def test_scenario_3_config_modification(self):
        """シナリオ3: 設定ファイル修正のテスト"""
        scenario = TestScenarios.get_scenario_3_config_modification()
        
        with FileSystemSandbox("config_modification") as sandbox:
            sandbox.setup_scenario_files(scenario["setup_files"])
            
            result = sandbox.execute_duckflow_scenario(scenario["user_input"])
            
            assert result["execution_success"], f"実行失敗: {result.get('error', 'Unknown error')}"
            
            # 設定ファイルの変更確認
            config_content = (sandbox.sandbox_root / "config.json").read_text(encoding='utf-8')
            
            # JSON有効性の確認
            try:
                config_data = json.loads(config_content)
                assert config_data["debug"] == True, "デバッグモードが有効になっていません"
                assert "monitoring" in config_data["features"], "monitoring機能が追加されていません"
            except json.JSONDecodeError:
                pytest.fail("config.json が有効なJSONではありません")
            
            print(f"[SUCCESS] {scenario['name']} テスト成功")
    
    def test_scenario_4_project_analysis(self):
        """シナリオ4: プロジェクト分析のテスト"""
        scenario = TestScenarios.get_scenario_4_project_analysis()
        
        with FileSystemSandbox("project_analysis") as sandbox:
            sandbox.setup_scenario_files(scenario["setup_files"])
            
            result = sandbox.execute_duckflow_scenario(scenario["user_input"])
            
            assert result["execution_success"], f"実行失敗: {result.get('error', 'Unknown error')}"
            
            # 修正されたファイルの確認
            calculator_content = (sandbox.sandbox_root / "calculator.py").read_text(encoding='utf-8')
            
            # エラーハンドリングの追加を確認
            assert "ZeroDivisionError" in calculator_content or "if b == 0" in calculator_content, \
                "ゼロ除算エラーハンドリングが追加されていません"
            
            # テストファイルの作成確認
            test_file = sandbox.sandbox_root / "test_calculator.py"
            assert test_file.exists(), "テストファイルが作成されていません"
            
            print(f"[SUCCESS] {scenario['name']} テスト成功")
    
    def test_scenario_5_web_app(self):
        """シナリオ5: Webアプリ開発のテスト"""
        scenario = TestScenarios.get_scenario_5_web_app()
        
        with FileSystemSandbox("web_app") as sandbox:
            sandbox.setup_scenario_files(scenario["setup_files"])
            
            result = sandbox.execute_duckflow_scenario(scenario["user_input"])
            
            assert result["execution_success"], f"実行失敗: {result.get('error', 'Unknown error')}"
            
            # Flaskアプリファイルの確認
            app_content = (sandbox.sandbox_root / "app.py").read_text(encoding='utf-8')
            flask_imports = ["from flask import Flask", "Flask(__name__)"]
            for import_stmt in flask_imports:
                assert import_stmt in app_content, f"Flask関連のコードが見つかりません: {import_stmt}"
            
            # テンプレートディレクトリとファイルの確認
            templates_dir = sandbox.sandbox_root / "templates"
            assert templates_dir.exists() and templates_dir.is_dir(), "templatesディレクトリが作成されていません"
            
            index_html = templates_dir / "index.html"
            assert index_html.exists(), "index.htmlが作成されていません"
            
            print(f"[SUCCESS] {scenario['name']} テスト成功")


class TestSandboxRunner:
    """サンドボックステストランナーのテスト"""
    
    def test_runner_initialization(self):
        """テストランナーの初期化テスト"""
        runner = SandboxTestRunner()
        
        assert runner is not None
        assert len(runner.test_scenarios) == 5, "5つのシナリオが定義されている必要があります"
        
        print("[SUCCESS] サンドボックステストランナー初期化成功")
    
    def test_all_scenarios_execution(self):
        """全シナリオの実行テスト"""
        runner = SandboxTestRunner()
        
        results = runner.run_all_scenarios()
        
        assert results is not None
        assert "total_scenarios" in results
        assert "scenario_results" in results
        assert results["total_scenarios"] == 5
        assert len(results["scenario_results"]) == 5
        
        # 各シナリオの結果確認
        for scenario_name, result in results["scenario_results"].items():
            assert "passed" in result
            assert "score" in result
            assert "execution_time" in result
            
            print(f"[RESULT] {scenario_name}: スコア {result['score']:.1f}/100, 実行時間 {result['execution_time']:.2f}秒")
        
        print(f"[TOTAL] 平均スコア: {results['average_score']:.1f}/100, 成功率: {results['success_rate']*100:.1f}%")
        print("[SUCCESS] 全シナリオ実行テスト完了")


def run_manual_sandbox_demo():
    """手動デモ実行用の関数"""
    print("サンドボックス評価システム デモ実行開始")
    print("=" * 60)
    
    try:
        # シナリオ1のデモ実行
        print("\n[シナリオ1] 基本ファイル作成")
        scenario = TestScenarios.get_scenario_1_basic_file_creation()
        
        with FileSystemSandbox("demo_basic") as sandbox:
            sandbox.setup_scenario_files(scenario["setup_files"])
            print(f"ユーザー入力: {scenario['user_input']}")
            
            result = sandbox.execute_duckflow_scenario(scenario["user_input"])
            
            if result["execution_success"]:
                print(">>> 実行成功")
                
                # 作成されたファイルの内容を表示
                hello_file = sandbox.sandbox_root / "hello.py"
                if hello_file.exists():
                    print("\n作成されたファイル内容:")
                    print("-" * 30)
                    print(hello_file.read_text(encoding='utf-8'))
                    print("-" * 30)
            else:
                print(f">>> 実行失敗: {result.get('error', 'Unknown error')}")
        
        # 全シナリオの実行結果
        print("\n[全シナリオ実行テスト]")
        runner = SandboxTestRunner()
        overall_results = runner.run_all_scenarios()
        
        if 'overall_score' in overall_results:
            print(f"\n最終評価スコア: {overall_results['overall_score']:.1f}/100")
        else:
            print("\n[INFO] 全シナリオテストが完了しました")
        
        print("\n" + "=" * 60)
        print("サンドボックス評価システム デモ完了")
        
    except Exception as e:
        print(f">>> デモ実行中にエラーが発生しました: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # pytest実行時は自動テスト、直接実行時はデモ
    import sys
    if len(sys.argv) == 1:
        run_manual_sandbox_demo()
    else:
        # pytestで実行
        pytest.main([__file__, "-v"])