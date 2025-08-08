#!/usr/bin/env python3
"""
Duckflow サンドボックス評価エンジン

サンドボックス実行結果の品質・完成度・効率性を多角的に評価するシステム
"""

import ast
import json
import re
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import subprocess
import tempfile
import shutil


@dataclass
class EvaluationMetrics:
    """評価メトリクス結果"""
    overall_score: float
    quality_score: float
    completeness_score: float
    efficiency_score: float
    
    # 詳細メトリクス
    syntax_accuracy: float
    code_style_score: float
    security_score: float
    requirement_match: float
    test_coverage: float
    execution_time: float
    retry_count: int
    files_created: int
    lines_of_code: int
    
    # エラー・問題点
    syntax_errors: List[str]
    style_violations: List[str]
    security_issues: List[str]
    missing_requirements: List[str]


@dataclass
class ScenarioEvaluation:
    """シナリオ評価結果"""
    scenario_name: str
    metrics: EvaluationMetrics
    detailed_analysis: Dict[str, Any]
    recommendations: List[str]
    timestamp: datetime


class CodeQualityAnalyzer:
    """コード品質解析器"""
    
    def __init__(self):
        self.python_keywords = [
            'def', 'class', 'if', 'else', 'elif', 'for', 'while', 
            'try', 'except', 'finally', 'with', 'import', 'from'
        ]
    
    def analyze_syntax(self, file_path: Path, content: str) -> Tuple[bool, List[str]]:
        """
        構文解析
        
        Returns:
            Tuple[bool, List[str]]: (構文正確性, エラーメッセージリスト)
        """
        errors = []
        
        if file_path.suffix == '.py':
            try:
                ast.parse(content)
                return True, []
            except SyntaxError as e:
                errors.append(f"構文エラー: {e.msg} (行 {e.lineno})")
                return False, errors
        
        elif file_path.suffix == '.json':
            try:
                json.loads(content)
                return True, []
            except json.JSONDecodeError as e:
                errors.append(f"JSON構文エラー: {e.msg}")
                return False, errors
        
        elif file_path.suffix == '.html':
            # 基本的なHTMLタグの対応チェック
            if self._check_html_structure(content):
                return True, []
            else:
                errors.append("HTML構造に問題があります")
                return False, errors
        
        return True, []  # その他のファイル形式は構文チェック対象外
    
    def analyze_code_style(self, file_path: Path, content: str) -> Tuple[float, List[str]]:
        """
        コードスタイル解析
        
        Returns:
            Tuple[float, List[str]]: (スタイルスコア 0-100, 違反リスト)
        """
        violations = []
        score = 100.0
        
        if file_path.suffix == '.py':
            # PEP8基本チェック
            lines = content.split('\n')
            
            for i, line in enumerate(lines, 1):
                # 行長チェック
                if len(line) > 88:  # PEP8では79文字だが、現代的な88文字を採用
                    violations.append(f"行 {i}: 行が長すぎます ({len(line)}文字)")
                    score -= 2
                
                # インデントチェック
                if line.startswith('\t'):
                    violations.append(f"行 {i}: タブではなくスペースを使用してください")
                    score -= 1
                
                # 空白行の過剰使用チェック
                if i > 1 and not line.strip() and not lines[i-2].strip():
                    violations.append(f"行 {i}: 連続する空行が多すぎます")
                    score -= 0.5
            
            # インポート順序チェック
            import_lines = [line for line in lines if line.startswith(('import ', 'from '))]
            if len(import_lines) > 1:
                # 標準ライブラリ、サードパーティ、ローカルの順序チェック（簡易版）
                if not self._check_import_order(import_lines):
                    violations.append("インポートの順序が推奨されません")
                    score -= 3
            
            # docstring存在チェック
            if 'def ' in content and '"""' not in content and "'''" not in content:
                violations.append("関数にdocstringがありません")
                score -= 5
        
        return max(0, score), violations
    
    def analyze_security(self, file_path: Path, content: str) -> Tuple[float, List[str]]:
        """
        セキュリティ分析
        
        Returns:
            Tuple[float, List[str]]: (セキュリティスコア 0-100, 問題リスト)
        """
        issues = []
        score = 100.0
        
        if file_path.suffix == '.py':
            # 危険なパターンの検出
            dangerous_patterns = [
                (r'exec\s*\(', 'exec()の使用は危険です'),
                (r'eval\s*\(', 'eval()の使用は危険です'),
                (r'subprocess\.call\s*\([^)]*shell\s*=\s*True', 'shell=Trueは危険です'),
                (r'os\.system\s*\(', 'os.system()の使用は危険です'),
                (r'pickle\.loads?\s*\(', 'pickleの使用は注意が必要です'),
                (r'input\s*\([^)]*\).*exec', 'ユーザー入力を直接実行するのは危険です'),
            ]
            
            for pattern, message in dangerous_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    issues.append(message)
                    score -= 15
            
            # ハードコードされた認証情報の検出
            credential_patterns = [
                (r'password\s*=\s*["\'][^"\']+["\']', 'ハードコードされたパスワード'),
                (r'api_?key\s*=\s*["\'][^"\']+["\']', 'ハードコードされたAPIキー'),
                (r'secret\s*=\s*["\'][^"\']+["\']', 'ハードコードされたシークレット'),
            ]
            
            for pattern, message in credential_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    issues.append(message)
                    score -= 20
        
        elif file_path.suffix == '.html':
            # XSS脆弱性の簡易チェック
            if '<script>' in content and 'user' in content.lower():
                issues.append('XSS脆弱性の可能性があります')
                score -= 10
        
        return max(0, score), issues
    
    def calculate_complexity(self, file_path: Path, content: str) -> int:
        """McCabe複雑度計算（簡易版）"""
        if file_path.suffix != '.py':
            return 1
        
        complexity = 1  # 基本複雑度
        
        # 制御フローステートメントをカウント
        control_patterns = [
            r'\bif\b', r'\belif\b', r'\bfor\b', r'\bwhile\b',
            r'\btry\b', r'\bexcept\b', r'\band\b', r'\bor\b'
        ]
        
        for pattern in control_patterns:
            complexity += len(re.findall(pattern, content))
        
        return complexity
    
    def _check_html_structure(self, content: str) -> bool:
        """HTML構造の基本チェック"""
        # 基本的なHTMLタグの対応チェック
        tag_pairs = [
            ('html', 'html'), ('head', 'head'), ('body', 'body'),
            ('div', 'div'), ('form', 'form'), ('script', 'script')
        ]
        
        for open_tag, close_tag in tag_pairs:
            open_count = content.count(f'<{open_tag}')
            close_count = content.count(f'</{close_tag}>')
            if open_count != close_count:
                return False
        
        return True
    
    def _check_import_order(self, import_lines: List[str]) -> bool:
        """インポート順序の簡易チェック"""
        # 標準ライブラリのパターン（簡易版）
        stdlib_modules = [
            'os', 'sys', 'json', 'time', 'datetime', 'pathlib', 
            'typing', 'dataclasses', 'subprocess', 'tempfile'
        ]
        
        has_stdlib = False
        has_third_party = False
        
        for line in import_lines:
            # from module import ... または import module の形式をチェック
            if 'from ' in line:
                module = line.split('from ')[1].split(' import')[0].strip()
            else:
                module = line.split('import ')[1].split()[0].strip()
            
            if module in stdlib_modules:
                if has_third_party:
                    return False  # サードパーティの後に標準ライブラリ
                has_stdlib = True
            else:
                has_third_party = True
        
        return True


class RequirementMatcher:
    """要求仕様マッチング分析器"""
    
    def analyze_completion(self, expected: Dict[str, Any], actual: Dict[str, Any]) -> Tuple[float, List[str]]:
        """
        要求仕様との一致度分析
        
        Returns:
            Tuple[float, List[str]]: (完成度スコア 0-100, 未達成項目リスト)
        """
        missing_items = []
        total_score = 0
        max_score = 0
        
        # ファイル作成チェック
        if 'files_created' in expected:
            max_score += 30
            expected_files = set(expected['files_created'])
            actual_files = set(actual.get('files_created', []))
            
            created_files = expected_files & actual_files
            missing_files = expected_files - actual_files
            
            if missing_files:
                missing_items.extend([f"未作成ファイル: {f}" for f in missing_files])
            
            file_score = (len(created_files) / len(expected_files)) * 30
            total_score += file_score
        
        # ディレクトリ作成チェック
        if 'directories_created' in expected:
            max_score += 20
            expected_dirs = set(expected['directories_created'])
            actual_dirs = set(actual.get('directories_created', []))
            
            created_dirs = expected_dirs & actual_dirs
            missing_dirs = expected_dirs - actual_dirs
            
            if missing_dirs:
                missing_items.extend([f"未作成ディレクトリ: {d}" for d in missing_dirs])
            
            dir_score = (len(created_dirs) / len(expected_dirs)) * 20 if expected_dirs else 20
            total_score += dir_score
        
        # ファイル内容チェック
        if 'file_contents' in expected:
            max_score += 40
            content_score = 0
            
            for filename, expectations in expected['file_contents'].items():
                if filename in actual.get('content_analysis', {}):
                    actual_content = actual['content_analysis'][filename]
                    
                    # 必要な内容が含まれているかチェック
                    if 'contains' in expectations:
                        contains_items = expectations['contains']
                        found_items = sum(1 for item in contains_items if item in actual_content)
                        content_score += (found_items / len(contains_items)) * 10
                    
                    # 構文有効性チェック
                    if 'syntax_valid' in expectations:
                        if expectations['syntax_valid']:
                            if actual.get('syntax_validation', {}).get(filename, False):
                                content_score += 10
                            else:
                                missing_items.append(f"{filename}: 構文エラー")
                    
                    # JSONの有効性チェック
                    if 'json_valid' in expectations and expectations['json_valid']:
                        try:
                            json.loads(actual_content)
                            content_score += 10
                        except:
                            missing_items.append(f"{filename}: JSON形式が無効")
                else:
                    missing_items.append(f"ファイル内容未取得: {filename}")
            
            total_score += min(content_score, 40)
        
        # プロジェクト分析チェック
        if 'project_analysis' in expected:
            max_score += 10
            project_score = 0
            
            expected_analysis = expected['project_analysis']
            if 'framework' in expected_analysis:
                # フレームワーク検出は簡易チェック
                project_score += 5
            
            if 'has_tests' in expected_analysis and expected_analysis['has_tests']:
                test_files = [f for f in actual.get('files_created', []) if 'test' in f.lower()]
                if test_files:
                    project_score += 5
                else:
                    missing_items.append("テストファイルが作成されていません")
            
            total_score += project_score
        
        # スコア正規化
        if max_score > 0:
            completion_score = (total_score / max_score) * 100
        else:
            completion_score = 100
        
        return min(100, completion_score), missing_items


class PerformanceAnalyzer:
    """パフォーマンス分析器"""
    
    def analyze_efficiency(self, execution_data: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
        """
        効率性分析
        
        Returns:
            Tuple[float, Dict]: (効率性スコア 0-100, 詳細データ)
        """
        score = 100.0
        details = {}
        
        # 実行時間分析
        execution_time = execution_data.get('execution_time', 0)
        details['execution_time'] = execution_time
        
        if execution_time > 30:  # 30秒以上
            score -= 20
        elif execution_time > 10:  # 10秒以上
            score -= 10
        elif execution_time > 5:   # 5秒以上
            score -= 5
        
        # ファイル作成効率
        files_count = len(execution_data.get('files_created', []))
        details['files_created_count'] = files_count
        
        if files_count == 0:
            score -= 30
        elif files_count > 10:
            # 多すぎるファイル作成は非効率の可能性
            score -= 5
        
        # コード生成量
        total_lines = 0
        for content in execution_data.get('content_analysis', {}).values():
            total_lines += len(content.split('\n'))
        
        details['total_lines_generated'] = total_lines
        
        # エラー率（構文エラーがある場合）
        syntax_errors = sum(1 for valid in execution_data.get('syntax_validation', {}).values() if not valid)
        total_files = len(execution_data.get('syntax_validation', {}))
        
        if total_files > 0:
            error_rate = syntax_errors / total_files
            details['syntax_error_rate'] = error_rate
            score -= error_rate * 50  # エラー率に応じて減点
        
        return max(0, score), details


class EvaluationEngine:
    """評価エンジン本体"""
    
    def __init__(self):
        self.code_analyzer = CodeQualityAnalyzer()
        self.requirement_matcher = RequirementMatcher()
        self.performance_analyzer = PerformanceAnalyzer()
    
    def evaluate_scenario(self, scenario_name: str, expected: Dict[str, Any], 
                         actual: Dict[str, Any], execution_data: Dict[str, Any]) -> ScenarioEvaluation:
        """
        シナリオの包括的評価
        
        Args:
            scenario_name: シナリオ名
            expected: 期待される結果
            actual: 実際の結果
            execution_data: 実行データ
            
        Returns:
            ScenarioEvaluation: 評価結果
        """
        # 品質分析
        quality_score, quality_details = self._analyze_quality(actual)
        
        # 完成度分析
        completeness_score, missing_items = self.requirement_matcher.analyze_completion(expected, actual)
        
        # 効率性分析
        efficiency_score, efficiency_details = self.performance_analyzer.analyze_efficiency(execution_data)
        
        # 総合スコア計算
        overall_score = (
            quality_score * 0.4 +
            completeness_score * 0.4 +
            efficiency_score * 0.2
        )
        
        # メトリクス作成
        metrics = EvaluationMetrics(
            overall_score=overall_score,
            quality_score=quality_score,
            completeness_score=completeness_score,
            efficiency_score=efficiency_score,
            
            syntax_accuracy=quality_details['syntax_accuracy'],
            code_style_score=quality_details['style_score'],
            security_score=quality_details['security_score'],
            requirement_match=completeness_score,
            test_coverage=quality_details.get('test_coverage', 0),
            execution_time=efficiency_details.get('execution_time', 0),
            retry_count=0,  # 現在は未実装
            files_created=efficiency_details.get('files_created_count', 0),
            lines_of_code=efficiency_details.get('total_lines_generated', 0),
            
            syntax_errors=quality_details['syntax_errors'],
            style_violations=quality_details['style_violations'],
            security_issues=quality_details['security_issues'],
            missing_requirements=missing_items
        )
        
        # 詳細分析データ
        detailed_analysis = {
            'quality_breakdown': quality_details,
            'efficiency_breakdown': efficiency_details,
            'completion_analysis': {
                'missing_items': missing_items,
                'completion_rate': completeness_score
            }
        }
        
        # 推奨事項生成
        recommendations = self._generate_recommendations(metrics, detailed_analysis)
        
        return ScenarioEvaluation(
            scenario_name=scenario_name,
            metrics=metrics,
            detailed_analysis=detailed_analysis,
            recommendations=recommendations,
            timestamp=datetime.now()
        )
    
    def _analyze_quality(self, actual: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
        """品質分析"""
        total_score = 0
        file_count = 0
        syntax_errors = []
        style_violations = []
        security_issues = []
        
        for file_path_str, content in actual.get('content_analysis', {}).items():
            file_path = Path(file_path_str)
            file_count += 1
            
            # 構文分析
            syntax_ok, syntax_errs = self.code_analyzer.analyze_syntax(file_path, content)
            syntax_errors.extend(syntax_errs)
            
            # スタイル分析
            style_score, style_viols = self.code_analyzer.analyze_code_style(file_path, content)
            style_violations.extend(style_viols)
            
            # セキュリティ分析
            security_score, sec_issues = self.code_analyzer.analyze_security(file_path, content)
            security_issues.extend(sec_issues)
            
            # ファイル毎のスコア合計
            file_score = (
                (100 if syntax_ok else 0) * 0.4 +
                style_score * 0.3 +
                security_score * 0.3
            )
            total_score += file_score
        
        # 平均スコア計算
        if file_count > 0:
            avg_score = total_score / file_count
            syntax_accuracy = (1 - len(syntax_errors) / file_count) * 100
            avg_style_score = total_score / file_count if style_violations else 100
            avg_security_score = 100 - (len(security_issues) * 10)
        else:
            avg_score = 0
            syntax_accuracy = 0
            avg_style_score = 0
            avg_security_score = 0
        
        # テストカバレッジ（簡易計算）
        test_files = [f for f in actual.get('files_created', []) if 'test' in f.lower()]
        regular_files = [f for f in actual.get('files_created', []) if 'test' not in f.lower() and f.endswith('.py')]
        test_coverage = (len(test_files) / max(1, len(regular_files))) * 100
        
        quality_details = {
            'syntax_accuracy': max(0, syntax_accuracy),
            'style_score': max(0, avg_style_score),
            'security_score': max(0, avg_security_score),
            'test_coverage': min(100, test_coverage),
            'syntax_errors': syntax_errors,
            'style_violations': style_violations,
            'security_issues': security_issues,
            'files_analyzed': file_count
        }
        
        return max(0, avg_score), quality_details
    
    def _generate_recommendations(self, metrics: EvaluationMetrics, 
                                 detailed_analysis: Dict[str, Any]) -> List[str]:
        """推奨事項の生成"""
        recommendations = []
        
        # 品質に関する推奨
        if metrics.quality_score < 70:
            if metrics.syntax_accuracy < 90:
                recommendations.append("構文エラーを修正してください")
            if metrics.code_style_score < 80:
                recommendations.append("コードスタイル（PEP8）を改善してください")
            if metrics.security_score < 90:
                recommendations.append("セキュリティ問題に対処してください")
        
        # 完成度に関する推奨
        if metrics.completeness_score < 80:
            recommendations.append("要求仕様の未実装部分を完成させてください")
            if metrics.missing_requirements:
                recommendations.append(f"不足項目: {', '.join(metrics.missing_requirements[:3])}")
        
        # 効率性に関する推奨
        if metrics.efficiency_score < 70:
            if metrics.execution_time > 10:
                recommendations.append("実行時間を短縮してください")
            if metrics.lines_of_code < 10:
                recommendations.append("より詳細な実装を提供してください")
        
        # テストカバレッジ
        if metrics.test_coverage < 50:
            recommendations.append("テストケースを追加してください")
        
        # 全体的な推奨
        if metrics.overall_score >= 90:
            recommendations.append("優秀な実装です！継続してください")
        elif metrics.overall_score >= 70:
            recommendations.append("良い実装です。細かい改善を続けてください")
        else:
            recommendations.append("大幅な改善が必要です。基本的な要件から見直してください")
        
        return recommendations[:5]  # 最大5つまで


class MetricsCollector:
    """メトリクス収集・管理システム"""
    
    def __init__(self, storage_path: str = "evaluation_metrics.json"):
        self.storage_path = Path(storage_path)
        self.metrics_history: List[Dict[str, Any]] = []
        self.load_history()
    
    def store_evaluation(self, evaluation: ScenarioEvaluation) -> None:
        """評価結果の保存"""
        record = {
            'timestamp': evaluation.timestamp.isoformat(),
            'scenario_name': evaluation.scenario_name,
            'metrics': {
                'overall_score': evaluation.metrics.overall_score,
                'quality_score': evaluation.metrics.quality_score,
                'completeness_score': evaluation.metrics.completeness_score,
                'efficiency_score': evaluation.metrics.efficiency_score,
                'execution_time': evaluation.metrics.execution_time,
                'files_created': evaluation.metrics.files_created,
                'lines_of_code': evaluation.metrics.lines_of_code,
                'syntax_accuracy': evaluation.metrics.syntax_accuracy
            },
            'recommendations_count': len(evaluation.recommendations)
        }
        
        self.metrics_history.append(record)
        self.save_history()
    
    def get_trend_analysis(self, days: int = 30) -> Dict[str, Any]:
        """トレンド分析"""
        cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)
        recent_records = [
            r for r in self.metrics_history 
            if datetime.fromisoformat(r['timestamp']).timestamp() > cutoff_date
        ]
        
        if not recent_records:
            return {'error': 'データが不足しています'}
        
        # 平均スコア計算
        avg_overall = sum(r['metrics']['overall_score'] for r in recent_records) / len(recent_records)
        avg_quality = sum(r['metrics']['quality_score'] for r in recent_records) / len(recent_records)
        avg_completeness = sum(r['metrics']['completeness_score'] for r in recent_records) / len(recent_records)
        avg_efficiency = sum(r['metrics']['efficiency_score'] for r in recent_records) / len(recent_records)
        
        # トレンド計算（最初の50%と最後の50%を比較）
        mid_point = len(recent_records) // 2
        first_half = recent_records[:mid_point] if mid_point > 0 else recent_records
        second_half = recent_records[mid_point:] if mid_point > 0 else recent_records
        
        first_avg = sum(r['metrics']['overall_score'] for r in first_half) / len(first_half)
        second_avg = sum(r['metrics']['overall_score'] for r in second_half) / len(second_half)
        trend = second_avg - first_avg
        
        return {
            'period_days': days,
            'total_evaluations': len(recent_records),
            'average_scores': {
                'overall': round(avg_overall, 2),
                'quality': round(avg_quality, 2),
                'completeness': round(avg_completeness, 2),
                'efficiency': round(avg_efficiency, 2)
            },
            'trend': {
                'direction': 'improving' if trend > 0 else 'declining' if trend < 0 else 'stable',
                'change': round(trend, 2)
            },
            'scenario_breakdown': self._get_scenario_breakdown(recent_records)
        }
    
    def generate_summary_report(self) -> Dict[str, Any]:
        """総合レポート生成"""
        if not self.metrics_history:
            return {'error': 'データがありません'}
        
        all_scores = [r['metrics']['overall_score'] for r in self.metrics_history]
        
        return {
            'total_evaluations': len(self.metrics_history),
            'score_statistics': {
                'average': round(sum(all_scores) / len(all_scores), 2),
                'maximum': round(max(all_scores), 2),
                'minimum': round(min(all_scores), 2)
            },
            'recent_trend': self.get_trend_analysis(7),
            'top_scenarios': self._get_top_performing_scenarios(),
            'improvement_areas': self._identify_improvement_areas()
        }
    
    def load_history(self) -> None:
        """履歴データの読み込み"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    self.metrics_history = json.load(f)
            except:
                self.metrics_history = []
    
    def save_history(self) -> None:
        """履歴データの保存"""
        with open(self.storage_path, 'w', encoding='utf-8') as f:
            json.dump(self.metrics_history, f, ensure_ascii=False, indent=2)
    
    def _get_scenario_breakdown(self, records: List[Dict]) -> Dict[str, Any]:
        """シナリオ別分析"""
        scenario_stats = {}
        
        for record in records:
            scenario = record['scenario_name']
            if scenario not in scenario_stats:
                scenario_stats[scenario] = {'scores': [], 'count': 0}
            
            scenario_stats[scenario]['scores'].append(record['metrics']['overall_score'])
            scenario_stats[scenario]['count'] += 1
        
        # 各シナリオの平均計算
        for scenario in scenario_stats:
            scores = scenario_stats[scenario]['scores']
            scenario_stats[scenario]['average'] = round(sum(scores) / len(scores), 2)
        
        return scenario_stats
    
    def _get_top_performing_scenarios(self) -> List[Dict[str, Any]]:
        """高評価シナリオの特定"""
        scenario_averages = {}
        
        for record in self.metrics_history:
            scenario = record['scenario_name']
            score = record['metrics']['overall_score']
            
            if scenario not in scenario_averages:
                scenario_averages[scenario] = []
            scenario_averages[scenario].append(score)
        
        # 平均スコア計算とソート
        top_scenarios = []
        for scenario, scores in scenario_averages.items():
            avg_score = sum(scores) / len(scores)
            top_scenarios.append({
                'scenario': scenario,
                'average_score': round(avg_score, 2),
                'evaluation_count': len(scores)
            })
        
        return sorted(top_scenarios, key=lambda x: x['average_score'], reverse=True)[:3]
    
    def _identify_improvement_areas(self) -> List[str]:
        """改善領域の特定"""
        if len(self.metrics_history) < 5:
            return ["データ不足のため分析できません"]
        
        recent_records = self.metrics_history[-10:]  # 最新10件
        
        # 各メトリクスの平均
        avg_quality = sum(r['metrics']['quality_score'] for r in recent_records) / len(recent_records)
        avg_completeness = sum(r['metrics']['completeness_score'] for r in recent_records) / len(recent_records)
        avg_efficiency = sum(r['metrics']['efficiency_score'] for r in recent_records) / len(recent_records)
        
        improvement_areas = []
        
        if avg_quality < 70:
            improvement_areas.append("コード品質の向上が必要")
        if avg_completeness < 70:
            improvement_areas.append("要求仕様の達成度向上が必要")
        if avg_efficiency < 70:
            improvement_areas.append("実行効率の改善が必要")
        
        if not improvement_areas:
            improvement_areas.append("全体的に良好なパフォーマンスです")
        
        return improvement_areas