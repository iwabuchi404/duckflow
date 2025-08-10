"""
PromptSmith Orchestrator – テスト結果からプロンプト改善を行う実装

このモジュールは CI のテスト実行後に呼び出され、ユニットテストと
E2E テストのレポートを解析し、改善提案を生成します。

拡張: 改善提案を基に ImprovementEngine + PromptManager を用いて
安全な範囲でプロンプト改善を新バージョンとして保存し、任意で適用します。
適用は環境変数 `PROMPTSMITH_AUTO_APPLY=1` で有効化できます（デフォルト無効）。
"""

import json
import os
from pathlib import Path
from typing import Dict, Any

from .improvement_engine import ImprovementEngine
from .prompt_manager import PromptManager

class PromptSmithOrchestrator:
    """テスト結果を読み込み、簡易的な改善提案を生成する"""

    def __init__(self, unit_report_path: str = "reports/unit.json", e2e_report_path: str = "reports/e2e.json"):
        self.unit_report_path = Path(unit_report_path)
        self.e2e_report_path = Path(e2e_report_path)
        self.improvement_engine = ImprovementEngine()
        self.prompt_manager = PromptManager("codecrafter/prompts/system_prompts")

    def _load_json(self, path: Path) -> Dict:
        if not path.is_file():
            raise FileNotFoundError(f"Report not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_reports(self) -> Dict[str, Any]:
        # Load unit test report
        unit_data = {}
        if self.unit_report_path.is_file():
            unit_data = self._load_json(self.unit_report_path)
        else:
            # フォールバックの空レポート
            unit_data = {"total": 0, "failed": 0, "total_interactions": 0, "context_correct": 0}
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
            try:
                e2e_metrics = extract_e2e_metrics(str(self.e2e_report_path))
            except Exception:
                e2e_metrics = {"e2e_success_rate": 0.0}

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

    def _analysis_to_evaluation(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """ImprovementEngine が利用できる評価フォーマットへ簡易変換"""
        hallucination_rate = float(analysis.get("hallucination_rate", 0.0))
        context_retention = float(analysis.get("context_retention", 0.0))
        e2e_success = float(analysis.get("e2e_metrics", {}).get("e2e_success_rate", 1.0))

        # 0-100 スケールに変換（最低限のヒューリスティック）
        quality_score = max(0.0, min(100.0, (1.0 - hallucination_rate) * 100))
        completeness_score = max(0.0, min(100.0, context_retention * 100))
        efficiency_score = max(0.0, min(100.0, e2e_success * 100))

        return {
            "quality_score": quality_score,
            "completeness_score": completeness_score,
            "efficiency_score": efficiency_score,
        }

    def _apply_improvements_if_enabled(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """環境変数で有効化時に改善案を生成し、安全な範囲で適用"""
        auto_apply = os.getenv("PROMPTSMITH_AUTO_APPLY", "0").lower() in ("1", "true", "yes")
        result: Dict[str, Any] = {"auto_apply": auto_apply, "applied": False}

        # 改善案生成
        evaluation_results = self._analysis_to_evaluation(analysis)
        improvements = self.improvement_engine.generate_targeted_improvements({
            "evaluation_results": evaluation_results,
            # conversation_analysis/weakness_patterns は今回は空（将来拡張）
            "conversation_analysis": {},
            "weakness_patterns": [],
        })

        result["improvements_count"] = len(improvements)

        if not auto_apply or not improvements:
            return result

        base_prompt = self.prompt_manager.load_current_prompt()
        variations = self.improvement_engine.create_prompt_variations(base_prompt, improvements)

        # 安全な案を選択
        chosen_variant = None
        chosen_validation = None
        for variant in variations:
            validation = self.improvement_engine.validate_improvement_safety(variant["prompt"], base_prompt)
            if validation.get("is_safe", False):
                chosen_variant = variant
                chosen_validation = validation
                break

        if not chosen_variant:
            result["reason"] = "no_safe_variant"
            return result

        # 新バージョン保存と適用
        changes = [f"Auto-apply improvements: {', '.join(chosen_variant.get('applied_improvements', []))}"]
        version_id = self.prompt_manager.save_new_version(
            chosen_variant["prompt"],
            changes,
            performance_metrics=evaluation_results,
        )
        applied = self.prompt_manager.apply_version(version_id)

        # 追記: 適用結果をファイル出力
        updates_dir = Path("promptsmith/updates")
        updates_dir.mkdir(parents=True, exist_ok=True)
        with open(updates_dir / "applied_version.json", "w", encoding="utf-8") as f:
            json.dump({
                "version_id": version_id,
                "applied": applied,
                "validation": chosen_validation,
                "variant": {k: v for k, v in chosen_variant.items() if k != "prompt"},
            }, f, ensure_ascii=False, indent=2)

        result.update({
            "applied": applied,
            "version_id": version_id,
            "validation": chosen_validation,
            "variant_id": chosen_variant.get("variant_id"),
        })
        return result

    def run_improvement_cycle(self):
        data = self._load_reports()
        analysis = self._analyze(data)
        self._write_suggestions(analysis)
        apply_result = self._apply_improvements_if_enabled(analysis)
        if apply_result.get("applied"):
            print(f"Applied improved prompt version: {apply_result['version_id']}")
        else:
            if apply_result.get("auto_apply"):
                print("No safe variant to apply. Improvements were not applied.")
            else:
                print("Auto-apply disabled. Improvements saved only as suggestions.")


def main():
    orchestrator = PromptSmithOrchestrator()
    orchestrator.run_improvement_cycle()


if __name__ == "__main__":
    main()
