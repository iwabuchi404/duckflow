#!/usr/bin/env python3
"""
Duckflow メトリクスレポーター

評価エンジンの結果を分析し、HTMLレポートやコンソール表示を生成する
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import statistics


class MetricsReporter:
    """メトリクスレポート生成器"""
    
    def __init__(self, metrics_path: str = "tests/sandbox/metrics_history.json"):
        self.metrics_path = Path(metrics_path)
        self.metrics_data = self._load_metrics()
    
    def _load_metrics(self) -> List[Dict[str, Any]]:
        """メトリクスデータの読み込み"""
        if self.metrics_path.exists():
            try:
                with open(self.metrics_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def generate_console_report(self, days: int = 7) -> None:
        """コンソール向けレポート生成"""
        print("\n" + "="*80)
        print("DUCKFLOW 評価メトリクス レポート")
        print("="*80)
        
        if not self.metrics_data:
            print("データがありません。まず評価を実行してください。")
            return
        
        # 期間フィルタリング
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_data = [
            record for record in self.metrics_data
            if datetime.fromisoformat(record['timestamp']) > cutoff_date
        ]
        
        if not recent_data:
            print(f"過去{days}日間のデータがありません。")
            return
        
        print(f"分析期間: 過去{days}日間 ({len(recent_data)}件の評価)")
        print("-"*80)
        
        # 基本統計
        self._print_basic_stats(recent_data)
        
        # シナリオ別分析
        self._print_scenario_analysis(recent_data)
        
        # 品質傾向分析
        self._print_quality_trends(recent_data)
        
        # 推奨事項
        self._print_recommendations(recent_data)
        
        print("="*80)
    
    def _print_basic_stats(self, data: List[Dict]) -> None:
        """基本統計の表示"""
        print("\n基本統計")
        print("-"*40)
        
        overall_scores = [record['metrics']['overall_score'] for record in data]
        quality_scores = [record['metrics']['quality_score'] for record in data]
        completeness_scores = [record['metrics']['completeness_score'] for record in data]
        efficiency_scores = [record['metrics']['efficiency_score'] for record in data]
        
        stats = [
            ("総合スコア", overall_scores),
            ("品質スコア", quality_scores),
            ("完成度スコア", completeness_scores),
            ("効率性スコア", efficiency_scores)
        ]
        
        for name, scores in stats:
            avg = statistics.mean(scores)
            median = statistics.median(scores)
            min_score = min(scores)
            max_score = max(scores)
            
            print(f"{name:12} | 平均: {avg:5.1f} | 中央値: {median:5.1f} | 範囲: {min_score:5.1f}-{max_score:5.1f}")
        
        # 成功率
        high_quality = sum(1 for score in overall_scores if score >= 80)
        good_quality = sum(1 for score in overall_scores if 60 <= score < 80)
        poor_quality = sum(1 for score in overall_scores if score < 60)
        
        print(f"\n品質分布:")
        print(f"  優秀 (80+):   {high_quality:2d}件 ({high_quality/len(data)*100:4.1f}%)")
        print(f"  良好 (60-79): {good_quality:2d}件 ({good_quality/len(data)*100:4.1f}%)")
        print(f"  要改善 (<60): {poor_quality:2d}件 ({poor_quality/len(data)*100:4.1f}%)")
    
    def _print_scenario_analysis(self, data: List[Dict]) -> None:
        """シナリオ別分析の表示"""
        print("\nシナリオ別分析")
        print("-"*40)
        
        # シナリオ別にデータをグループ化
        scenario_data = {}
        for record in data:
            scenario = record['scenario_name']
            if scenario not in scenario_data:
                scenario_data[scenario] = []
            scenario_data[scenario].append(record)
        
        # 各シナリオの統計を表示
        for scenario, records in scenario_data.items():
            scores = [r['metrics']['overall_score'] for r in records]
            avg_score = statistics.mean(scores)
            count = len(records)
            
            # 最新の詳細を取得
            latest = max(records, key=lambda x: x['timestamp'])
            latest_metrics = latest['metrics']
            
            print(f"\n{scenario}")
            print(f"  評価回数: {count}回 | 平均スコア: {avg_score:.1f}/100")
            print(f"  最新結果: 品質={latest_metrics['quality_score']:.1f} | "
                  f"完成度={latest_metrics['completeness_score']:.1f} | "
                  f"効率性={latest_metrics['efficiency_score']:.1f}")
            
            # 問題がある場合は警告
            if avg_score < 70:
                print(f"  [注意] 改善が必要 (平均スコア: {avg_score:.1f})")
    
    def _print_quality_trends(self, data: List[Dict]) -> None:
        """品質傾向の表示"""
        print("\n品質傾向分析")
        print("-"*40)
        
        if len(data) < 3:
            print("データが少ないためトレンド分析できません")
            return
        
        # 時系列でソート
        sorted_data = sorted(data, key=lambda x: x['timestamp'])
        
        # 前半と後半で比較
        mid_point = len(sorted_data) // 2
        first_half = sorted_data[:mid_point]
        second_half = sorted_data[mid_point:]
        
        first_avg = statistics.mean([r['metrics']['overall_score'] for r in first_half])
        second_avg = statistics.mean([r['metrics']['overall_score'] for r in second_half])
        trend = second_avg - first_avg
        
        if trend > 5:
            trend_text = "向上中"
        elif trend < -5:
            trend_text = "低下中"
        else:
            trend_text = "安定"
        
        print(f"全体的な傾向: {trend_text} (変化: {trend:+.1f}ポイント)")
        
        # 各メトリクスのトレンド
        metrics_trends = {}
        for metric_name in ['quality_score', 'completeness_score', 'efficiency_score']:
            first_avg = statistics.mean([r['metrics'][metric_name] for r in first_half])
            second_avg = statistics.mean([r['metrics'][metric_name] for r in second_half])
            metrics_trends[metric_name] = second_avg - first_avg
        
        print("\n詳細トレンド:")
        for metric, trend in metrics_trends.items():
            name_map = {
                'quality_score': '品質',
                'completeness_score': '完成度', 
                'efficiency_score': '効率性'
            }
            name = name_map[metric]
            if trend > 2:
                status = "↑"
            elif trend < -2:
                status = "↓"
            else:
                status = "→"
            
            print(f"  {name:8}: {status} {trend:+.1f}ポイント")
    
    def _print_recommendations(self, data: List[Dict]) -> None:
        """推奨事項の表示"""
        print("\n推奨事項")
        print("-"*40)
        
        recent_scores = [r['metrics'] for r in data[-5:]]  # 最新5件
        
        recommendations = []
        
        # 品質スコアが低い
        avg_quality = statistics.mean([s['quality_score'] for s in recent_scores])
        if avg_quality < 70:
            recommendations.append("コード品質の向上に注力してください")
            
            # 詳細分析
            avg_syntax = statistics.mean([s.get('syntax_accuracy', 100) for s in recent_scores])
            if avg_syntax < 90:
                recommendations.append("   - 構文エラーを減らしてください")
        
        # 完成度が低い
        avg_completeness = statistics.mean([s['completeness_score'] for s in recent_scores])
        if avg_completeness < 80:
            recommendations.append("要求仕様の実装完成度を上げてください")
        
        # 効率性が低い
        avg_efficiency = statistics.mean([s['efficiency_score'] for s in recent_scores])
        if avg_efficiency < 70:
            avg_time = statistics.mean([s['execution_time'] for s in recent_scores])
            if avg_time > 5:
                recommendations.append("実行時間の短縮を検討してください")
        
        # パフォーマンスが良い場合
        overall_avg = statistics.mean([s['overall_score'] for s in recent_scores])
        if overall_avg >= 85:
            recommendations.append("優秀なパフォーマンスです！現在の品質を維持してください")
        
        if not recommendations:
            recommendations.append("継続的な品質向上を目指しましょう")
        
        for rec in recommendations:
            print(f"  {rec}")
    
    def generate_html_report(self, output_path: str = "evaluation_report.html") -> None:
        """HTMLレポート生成"""
        if not self.metrics_data:
            print("データがないためHTMLレポートを生成できません")
            return
        
        html_content = self._build_html_report()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"HTMLレポートを生成しました: {output_path}")
    
    def _build_html_report(self) -> str:
        """HTMLレポートコンテンツの構築"""
        # 基本統計を計算
        recent_data = self.metrics_data[-30:]  # 最新30件
        overall_scores = [r['metrics']['overall_score'] for r in recent_data]
        
        avg_score = statistics.mean(overall_scores) if overall_scores else 0
        total_evaluations = len(self.metrics_data)
        
        # シナリオ別統計
        scenario_stats = {}
        for record in recent_data:
            scenario = record['scenario_name']
            if scenario not in scenario_stats:
                scenario_stats[scenario] = []
            scenario_stats[scenario].append(record['metrics']['overall_score'])
        
        scenario_html = ""
        for scenario, scores in scenario_stats.items():
            avg = statistics.mean(scores)
            scenario_html += f"""
                <tr>
                    <td>{scenario}</td>
                    <td>{len(scores)}</td>
                    <td>{avg:.1f}</td>
                    <td>{'良好' if avg >= 80 else '普通' if avg >= 60 else '要改善'}</td>
                </tr>
            """
        
        html_template = f"""
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Duckflow 評価レポート</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 40px; line-height: 1.6; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; text-align: center; }}
        .metric-card {{ background: white; border-radius: 8px; padding: 20px; margin: 20px 0; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .metric-value {{ font-size: 2.5em; font-weight: bold; color: #667eea; }}
        .metric-label {{ color: #666; font-size: 0.9em; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #f8f9fa; }}
        .score-excellent {{ color: #28a745; }}
        .score-good {{ color: #ffc107; }}
        .score-poor {{ color: #dc3545; }}
        .progress-bar {{ background-color: #e9ecef; border-radius: 10px; height: 20px; margin: 10px 0; }}
        .progress-fill {{ background: linear-gradient(90deg, #28a745, #20c997); height: 100%; border-radius: 10px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Duckflow 評価レポート</h1>
        <p>生成日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M')}</p>
    </div>
    
    <div class="metric-card">
        <h2>総合統計</h2>
        <div style="display: flex; justify-content: space-around;">
            <div style="text-align: center;">
                <div class="metric-value">{avg_score:.1f}</div>
                <div class="metric-label">平均スコア</div>
            </div>
            <div style="text-align: center;">
                <div class="metric-value">{total_evaluations}</div>
                <div class="metric-label">総評価回数</div>
            </div>
            <div style="text-align: center;">
                <div class="metric-value">{len(scenario_stats)}</div>
                <div class="metric-label">テストシナリオ数</div>
            </div>
        </div>
        
        <div class="progress-bar">
            <div class="progress-fill" style="width: {avg_score}%;"></div>
        </div>
        <p style="text-align: center; margin-top: 10px;">全体品質レベル: {avg_score:.1f}/100</p>
    </div>
    
    <div class="metric-card">
        <h2>シナリオ別パフォーマンス</h2>
        <table>
            <thead>
                <tr>
                    <th>シナリオ名</th>
                    <th>評価回数</th>
                    <th>平均スコア</th>
                    <th>ステータス</th>
                </tr>
            </thead>
            <tbody>
                {scenario_html}
            </tbody>
        </table>
    </div>
    
    <div class="metric-card">
        <h2>改善提案</h2>
        <ul>
            <li>継続的な品質監視を実施してください</li>
            <li>低スコアシナリオの原因分析を行ってください</li>
            <li>定期的なベンチマークテストを実行してください</li>
        </ul>
    </div>
    
    <footer style="text-align: center; margin-top: 50px; color: #666;">
        <p>Generated by Duckflow Evaluation Engine v2.0</p>
    </footer>
</body>
</html>
        """
        
        return html_template
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """パフォーマンス要約の取得"""
        if not self.metrics_data:
            return {"error": "データがありません"}
        
        recent_data = self.metrics_data[-10:]  # 最新10件
        
        overall_scores = [r['metrics']['overall_score'] for r in recent_data]
        quality_scores = [r['metrics']['quality_score'] for r in recent_data]
        
        return {
            "recent_evaluations": len(recent_data),
            "average_overall_score": statistics.mean(overall_scores),
            "average_quality_score": statistics.mean(quality_scores),
            "score_distribution": {
                "excellent": sum(1 for s in overall_scores if s >= 80),
                "good": sum(1 for s in overall_scores if 60 <= s < 80),
                "poor": sum(1 for s in overall_scores if s < 60)
            },
            "latest_score": overall_scores[-1] if overall_scores else 0,
            "trend": "improving" if len(overall_scores) >= 2 and overall_scores[-1] > overall_scores[0] else "stable"
        }


def run_metrics_demo():
    """メトリクスレポートのデモ実行"""
    print("メトリクスレポーター デモ実行")
    
    import os
    metrics_path = os.path.join(os.path.dirname(__file__), "metrics_history.json")
    reporter = MetricsReporter(metrics_path)
    
    # コンソールレポート
    reporter.generate_console_report(days=30)
    
    # HTMLレポート生成
    try:
        reporter.generate_html_report("tests/sandbox/evaluation_report.html")
    except Exception as e:
        print(f"HTMLレポート生成エラー: {e}")
    
    # パフォーマンス要約
    summary = reporter.get_performance_summary()
    print(f"\nパフォーマンス要約:")
    print(f"  最新スコア: {summary.get('latest_score', 0):.1f}")
    print(f"  平均スコア: {summary.get('average_overall_score', 0):.1f}")


if __name__ == "__main__":
    run_metrics_demo()