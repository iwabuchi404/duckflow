"""
Tests for companion/validators/llm_output.py

LLMOutputFormatter validates and repairs LLM output against the MainLLMOutput schema.
"""

from companion.state.enums import Status, Step
from companion.validators.llm_output import LLMOutputFormatter, MainLLMOutput


class TestMainLLMOutput:
    def test_valid_construction(self) -> None:
        output = MainLLMOutput(
            rationale="Analyzing the request",
            goal_consistency="Consistent",
            constraint_check="All constraints met",
            next_step="Execute the plan",
            step=Step.PLANNING,
            status=Status.IN_PROGRESS,
        )
        assert output.rationale == "Analyzing the request"
        assert output.step == Step.PLANNING
        assert output.status == Status.IN_PROGRESS
        assert output.state_delta is None

    def test_with_state_delta(self) -> None:
        output = MainLLMOutput(
            rationale="r",
            goal_consistency="g",
            constraint_check="c",
            next_step="n",
            step=Step.EXECUTION,
            status=Status.SUCCESS,
            state_delta="updated file",
        )
        assert output.state_delta == "updated file"


class TestLLMOutputFormatterValidate:
    def _make(self) -> LLMOutputFormatter:
        return LLMOutputFormatter()

    def test_validate_valid_data(self) -> None:
        fmt = self._make()
        data = {
            "rationale": "r",
            "goal_consistency": "g",
            "constraint_check": "c",
            "next_step": "n",
            "step": Step.PLANNING,
            "status": Status.PENDING,
        }
        result = fmt.validate(data)
        assert isinstance(result, MainLLMOutput)
        assert result.step == Step.PLANNING

    def test_validate_string_enum_values(self) -> None:
        fmt = self._make()
        data = {
            "rationale": "r",
            "goal_consistency": "g",
            "constraint_check": "c",
            "next_step": "n",
            "step": "PLANNING",
            "status": "PENDING",
        }
        result = fmt.validate(data)
        assert result.step == Step.PLANNING
        assert result.status == Status.PENDING


class TestLLMOutputFormatterTryRepair:
    def _make(self) -> LLMOutputFormatter:
        return LLMOutputFormatter()

    def test_repair_empty_dict(self) -> None:
        fmt = self._make()
        result = fmt.try_repair({})
        assert result is not None
        assert result.rationale == ""
        assert result.step == Step.IDLE
        assert result.status == Status.PENDING

    def test_repair_partial_data(self) -> None:
        fmt = self._make()
        result = fmt.try_repair({"rationale": "Something went wrong"})
        assert result is not None
        assert result.rationale == "Something went wrong"

    def test_repair_with_valid_step_status(self) -> None:
        fmt = self._make()
        result = fmt.try_repair(
            {
                "step": Step.EXECUTION,
                "status": Status.IN_PROGRESS,
            }
        )
        assert result is not None
        assert result.step == Step.EXECUTION
