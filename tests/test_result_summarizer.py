"""
Tests for companion/execution/result_summarizer.py

ResultSummarizer generates natural-language summaries of task execution results.
These tests exercise the non-LLM paths (prompt building, formatting, fallback).
"""

from companion.execution.result_summarizer import (
    ExecutionSummary,
    ResultSummarizer,
)


class TestExecutionSummaryModel:
    def test_minimal_summary(self) -> None:
        s = ExecutionSummary(summary="All done")
        assert s.summary == "All done"
        assert s.highlights == []
        assert s.next_steps == ""

    def test_full_summary(self) -> None:
        s = ExecutionSummary(
            summary="Two tasks completed",
            highlights=["Created file", "Ran tests"],
            next_steps="Deploy",
        )
        assert len(s.highlights) == 2
        assert s.next_steps == "Deploy"


class TestBuildSummaryPrompt:
    def _make(self) -> ResultSummarizer:
        """Create a summarizer without a real LLM (we won't call chat)."""

        class FakeLLM:
            pass

        return ResultSummarizer(llm_client=FakeLLM())  # type: ignore[arg-type]

    def test_prompt_contains_task_counts(self) -> None:
        rs = self._make()
        data = {"total": 5, "completed": 3, "failed": 2, "execution_log": []}
        prompt = rs._build_summary_prompt(data)
        assert "5 tasks" in prompt
        assert "Completed: 3" in prompt
        assert "Failed: 2" in prompt

    def test_prompt_includes_completed_tasks(self) -> None:
        rs = self._make()
        data = {
            "total": 1,
            "completed": 1,
            "failed": 0,
            "execution_log": [
                {"task_title": "Write module", "status": "completed", "result": "OK"},
            ],
        }
        prompt = rs._build_summary_prompt(data)
        assert "Write module" in prompt
        assert "OK" in prompt

    def test_prompt_includes_failed_tasks(self) -> None:
        rs = self._make()
        data = {
            "total": 1,
            "completed": 0,
            "failed": 1,
            "execution_log": [
                {"task_title": "Deploy", "status": "failed", "error": "Timeout"},
            ],
        }
        prompt = rs._build_summary_prompt(data)
        assert "Deploy" in prompt
        assert "Timeout" in prompt

    def test_prompt_with_empty_log(self) -> None:
        rs = self._make()
        data = {"total": 0, "completed": 0, "failed": 0, "execution_log": []}
        prompt = rs._build_summary_prompt(data)
        assert "0 tasks" in prompt


class TestFormatSummary:
    def _make(self) -> ResultSummarizer:
        class FakeLLM:
            pass

        return ResultSummarizer(llm_client=FakeLLM())  # type: ignore[arg-type]

    def test_format_includes_summary_text(self) -> None:
        rs = self._make()
        summary_obj = ExecutionSummary(
            summary="Everything passed",
            highlights=["Fast", "Clean"],
            next_steps="Ship it",
        )
        data = {"total": 2, "completed": 2, "failed": 0, "success_rate": 1.0}
        result = rs._format_summary(summary_obj, data)
        assert "Everything passed" in result
        assert "Fast" in result
        assert "Ship it" in result
        assert "100.0%" in result

    def test_format_with_no_highlights(self) -> None:
        rs = self._make()
        summary_obj = ExecutionSummary(summary="Done")
        data = {"total": 1, "completed": 1, "failed": 0, "success_rate": 1.0}
        result = rs._format_summary(summary_obj, data)
        assert "Done" in result
        assert "Key Highlights" not in result

    def test_format_with_no_next_steps(self) -> None:
        rs = self._make()
        summary_obj = ExecutionSummary(summary="Done", highlights=["A"])
        data = {"total": 1, "completed": 1, "failed": 0, "success_rate": 1.0}
        result = rs._format_summary(summary_obj, data)
        assert "Next Steps" not in result


class TestSimpleSummary:
    def _make(self) -> ResultSummarizer:
        class FakeLLM:
            pass

        return ResultSummarizer(llm_client=FakeLLM())  # type: ignore[arg-type]

    def test_simple_summary_content(self) -> None:
        rs = self._make()
        data = {"total": 3, "completed": 2, "failed": 1}
        result = rs._simple_summary(data)
        assert "3 tasks" in result
        assert "2 succeeded" in result
        assert "1 failed" in result

    def test_simple_summary_all_zeros(self) -> None:
        rs = self._make()
        data = {"total": 0, "completed": 0, "failed": 0}
        result = rs._simple_summary(data)
        assert "0 tasks" in result
