"""
PromptSmith Orchestrator – テスト結果からプロンプト改善を行う実装

このモジュールは CI のテスト実行後に呼び出され、ユニットテストと
E2E テストのレポートを解析し、改善提案を生成します。
"""

import json
from pathlib import Path
from typing import Dict, Any

class PromptSmithOrchestrator:
    """テスト結果を読み込み、簡易的な改善提案を生成する"""

    def __init__(self, unit_report_path: str = "reports/unit.json", e2e_report_path: str = "reports/e2e.json"):
        self.unit_report_path = Path(unit_report_path)
        self.e2e_report_path = Path(e2e_report_path)

    def _load_json(self, path: Path) -> Dict:
        if not path.is_file():
            raise FileNotFoundError(f"Report not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_reports(self) -> Dict[str, Any]:
        # Load unit test report
        unit_data = self._load_json(self.unit_report_path)
        # Load E2E report if it exists
        e2e_data = {}
        if self.e2e_report_path.is_file():
            e2e_data = self._load_json(self.e2e_report_path)
        return {"unit": unit_data, "e2e": e2e_data}

    def _analyze(self, data: Dict[str, Any]) -> Dict:
        """
        テスト結果から簡易的に改善点を抽出。
        - ハルシネーション率、コンテキスト保持率、E2E 成功率を評価
        """
        from scripts.metrics import (
            calculate_hallucination_rate,
            calculate_context_retention,
            extract_e2e_metrics,
        )

        unit = data.get("unit", {})
        e2e = data.get("e2e", {})

        # 基本メトリクス
        hallucination_rate = calculate_hallucination_rate(unit)
        context_retention = calculate_context_retention(unit)

        # E2E メトリクス
        e2e_metrics = {}
        if self.e2e_report_path.is_file():
            e2e_metrics = extract_e2e_metrics(str(self.e2e_report_path))

        suggestions = []
        if hallucination_rate > 0.05:
            suggestions.append(
                f"ハルシネーション率が {hallucination_rate:.2%} と高いため、"
                "プロンプトの具体性を向上させる改善が必要です。"
            )
        if context_retention < 0.90:
            suggestions.append(
                f"コンテキスト保持率が {context_retention:.2%} と低いため、"
                "対話履歴の要約・保持ロジックを見直してください。"
            )
        # E2E 成功率のチェック
        e2e_success = e2e_metrics.get("e2e_success_rate", 1.0)
        if e2e_success < 0.9:
            suggestions.append(
                f"E2E 成功率が {e2e_success:.2%} と低いため、"
                "テストケースや LLM 応答ロジックの見直しが必要です。"
            )

        return {
            "hallucination_rate": hallucination_rate,
            "context_retention": context_retention,
            "e2e_metrics": e2e_metrics,
            "suggestions": suggestions,
        }

    def _write_suggestions(self, analysis: Dict):
        output_dir = Path("promptsmith/updates")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "improvement_suggestions.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2)
        print(f"Improvement suggestions written to {output_file}")

    def run_improvement_cycle(self):
        data = self._load_reports()
        analysis = self._analyze(data)
        self._write_suggestions(analysis)


def main():
    orchestrator = PromptSmithOrchestrator()
    orchestrator.run_improvement_cycle()


if __name__ == "__main__":
    main()