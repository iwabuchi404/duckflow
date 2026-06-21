"""
Tests for companion/output/human_formatter.py

HumanOutputFormatter converts structured data to human-readable text.
These tests exercise the template-based (non-LLM) formatting paths.
"""

import pytest

from companion.output.human_formatter import (
    FormattedOutput,
    FormatterRequest,
    HumanOutputFormatter,
)


@pytest.fixture
def formatter() -> HumanOutputFormatter:
    """Formatter without an LLM service (template fallback)."""
    return HumanOutputFormatter(llm_service=None)


# ---------- FormattedOutput dataclass ----------


class TestFormattedOutputDefaults:
    def test_defaults(self) -> None:
        out = FormattedOutput(human_text="hello", summary="s")
        assert out.success is True
        assert out.details is None
        assert out.error_message is None


# ---------- Template-based formatting ----------


class TestFormatFileAnalysis:
    def test_basic_file_analysis(self, formatter: HumanOutputFormatter) -> None:
        data = {
            "file_path": "src/main.py",
            "file_info": {"total_lines": 120, "total_chars": 3500},
            "headers": [
                {"level": 1, "text": "Main Module"},
                {"level": 2, "text": "Helper Functions"},
            ],
            "sections": [{"name": "imports"}, {"name": "logic"}],
        }
        req = FormatterRequest(data=data, context="test", format_type="file_analysis")
        result = formatter._format_with_template(req, "")
        assert result.success
        assert "src/main.py" in result.human_text
        assert "120" in result.human_text
        assert "Main Module" in result.human_text

    def test_file_analysis_empty_data(self, formatter: HumanOutputFormatter) -> None:
        data: dict = {}
        req = FormatterRequest(data=data, context="test", format_type="file_analysis")
        result = formatter._format_with_template(req, "")
        assert result.success


class TestFormatSearchResult:
    def test_basic_search_result(self, formatter: HumanOutputFormatter) -> None:
        data = {
            "pattern": "def main",
            "file_path": "src/",
            "matches_found": 2,
            "results": [
                {
                    "line_number": 10,
                    "match_text": "def main():",
                    "full_line": "def main():",
                },
                {
                    "line_number": 55,
                    "match_text": "def main_loop():",
                    "full_line": "def main_loop():",
                },
            ],
        }
        req = FormatterRequest(data=data, context="test", format_type="search_result")
        result = formatter._format_with_template(req, "")
        assert result.success
        assert "def main" in result.human_text
        assert "2" in result.summary

    def test_search_result_no_matches(self, formatter: HumanOutputFormatter) -> None:
        data = {"pattern": "xyz", "file_path": ".", "matches_found": 0, "results": []}
        req = FormatterRequest(data=data, context="test", format_type="search_result")
        result = formatter._format_with_template(req, "")
        assert result.success
        assert "0" in result.summary

    def test_search_result_uses_full_line_when_match_text_empty(
        self, formatter: HumanOutputFormatter
    ) -> None:
        data = {
            "pattern": "todo",
            "file_path": ".",
            "matches_found": 1,
            "results": [
                {"line_number": 5, "match_text": "", "full_line": "# TODO: fix this"},
            ],
        }
        req = FormatterRequest(data=data, context="test", format_type="search_result")
        result = formatter._format_with_template(req, "")
        assert "TODO" in result.human_text


class TestFormatOperationResult:
    def test_successful_operation(self, formatter: HumanOutputFormatter) -> None:
        data = {"success": True, "message": "File created", "path": "/project/new.py"}
        req = FormatterRequest(
            data=data, context="test", format_type="operation_result"
        )
        result = formatter._format_with_template(req, "")
        assert result.success
        assert "/project/new.py" in result.human_text

    def test_failed_operation(self, formatter: HumanOutputFormatter) -> None:
        data = {"success": False, "message": "Permission denied", "path": ""}
        req = FormatterRequest(
            data=data, context="test", format_type="operation_result"
        )
        result = formatter._format_with_template(req, "")
        assert not result.success
        assert "Permission denied" in result.human_text


class TestFormatGenericSimple:
    def test_generic_with_mixed_types(self, formatter: HumanOutputFormatter) -> None:
        data = {
            "name": "test",
            "count": 42,
            "enabled": True,
            "items": [1, 2, 3],
            "nested": {"a": 1},
        }
        req = FormatterRequest(data=data, context="test", format_type="generic")
        result = formatter._format_with_template(req, "")
        assert result.success
        assert "42" in result.human_text
        assert "3" in result.human_text  # list length

    def test_generic_truncates_to_5_keys(self, formatter: HumanOutputFormatter) -> None:
        data = {f"key_{i}": i for i in range(10)}
        req = FormatterRequest(data=data, context="test", format_type="generic")
        result = formatter._format_with_template(req, "")
        assert result.success


class TestFormatPlanGeneration:
    def test_successful_plan(self, formatter: HumanOutputFormatter) -> None:
        data = {
            "operation": "Plan Generation",
            "success": True,
            "generated_plan": "# Step 1\nDo thing A\n# Step 2\nDo thing B",
            "base_document": "design.md",
            "focus_areas": ["performance", "security"],
        }
        req = FormatterRequest(data=data, context="test", format_type="plan_generation")
        result = formatter._format_with_template(req, "")
        assert result.success
        assert "design.md" in result.human_text
        assert "performance" in result.human_text

    def test_failed_plan(self, formatter: HumanOutputFormatter) -> None:
        data = {
            "operation": "Plan Generation",
            "success": False,
            "error_message": "LLM timeout",
            "generated_plan": "",
            "base_document": "",
            "focus_areas": [],
        }
        req = FormatterRequest(data=data, context="test", format_type="plan_generation")
        result = formatter._format_with_template(req, "")
        assert not result.success
        assert "LLM timeout" in result.human_text

    def test_empty_plan_content(self, formatter: HumanOutputFormatter) -> None:
        data = {
            "operation": "Plan Generation",
            "success": True,
            "generated_plan": "",
            "base_document": "x.md",
            "focus_areas": [],
        }
        req = FormatterRequest(data=data, context="test", format_type="plan_generation")
        result = formatter._format_with_template(req, "")
        assert result.success


# ---------- _prepare_data_for_llm ----------


class TestPrepareDataForLLM:
    def test_long_string_truncated(self, formatter: HumanOutputFormatter) -> None:
        data = {"text": "x" * 1000}
        safe = formatter._prepare_data_for_llm(data)
        assert len(safe["text"]) <= 504  # 500 + "..."

    def test_long_list_truncated(self, formatter: HumanOutputFormatter) -> None:
        data = {"items": list(range(20))}
        safe = formatter._prepare_data_for_llm(data)
        assert len(safe["items"]) == 10

    def test_large_dict_truncated(self, formatter: HumanOutputFormatter) -> None:
        data = {"nested": {str(i): i for i in range(30)}}
        safe = formatter._prepare_data_for_llm(data)
        assert len(safe["nested"]) == 20

    def test_small_values_unchanged(self, formatter: HumanOutputFormatter) -> None:
        data = {"a": "short", "b": [1, 2], "c": {"k": "v"}}
        safe = formatter._prepare_data_for_llm(data)
        assert safe == data


# ---------- _parse_llm_response ----------


class TestParseLLMResponse:
    def test_multi_line_response(self, formatter: HumanOutputFormatter) -> None:
        response = "Summary line\nDetail 1\nDetail 2"
        result = formatter._parse_llm_response(response)
        assert result.summary == "Summary line"
        assert "Detail 1" in result.human_text

    def test_single_line_response(self, formatter: HumanOutputFormatter) -> None:
        response = "Just one line"
        result = formatter._parse_llm_response(response)
        assert result.summary == "LLM応答"
        assert result.human_text == "Just one line"


# ---------- format_data async entrypoint ----------


class TestFormatDataAsync:
    @pytest.mark.asyncio
    async def test_format_data_without_llm_uses_template(
        self, formatter: HumanOutputFormatter
    ) -> None:
        req = FormatterRequest(
            data={"success": True, "message": "OK", "path": "/a.py"},
            context="test",
            format_type="operation_result",
        )
        result = await formatter.format_data(req)
        assert result.success
        assert "OK" in result.human_text

    @pytest.mark.asyncio
    async def test_format_data_unknown_type_uses_generic(
        self, formatter: HumanOutputFormatter
    ) -> None:
        req = FormatterRequest(
            data={"key": "value"},
            context="test",
            format_type="nonexistent_type",
        )
        result = await formatter.format_data(req)
        assert result.success

    @pytest.mark.asyncio
    async def test_format_data_handles_exception(
        self, formatter: HumanOutputFormatter
    ) -> None:
        """If data processing raises, the result should still be returned with success=False."""
        req = FormatterRequest(
            data=None,  # type: ignore[arg-type]
            context="test",
            format_type="file_analysis",
        )
        result = await formatter.format_data(req)
        assert not result.success
        assert result.error_message is not None


# ---------- Template getters ----------


class TestTemplateGetters:
    def test_all_templates_are_non_empty_strings(
        self, formatter: HumanOutputFormatter
    ) -> None:
        for key, tmpl in formatter.templates.items():
            assert isinstance(tmpl, str) and len(tmpl) > 0, f"Template '{key}' is empty"
