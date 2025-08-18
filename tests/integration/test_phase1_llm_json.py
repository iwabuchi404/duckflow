import pytest


def test_llm_output_formatter_repair():
	from companion.validators.llm_output import LLMOutputFormatter
	fmt = LLMOutputFormatter()
	# 欠損キーがあってもrepairで補完できる
	partial = {"rationale": "test"}
	repaired = fmt.try_repair(partial)
	assert repaired is not None
	data = repaired.model_dump()
	for k in ["rationale", "goal_consistency", "constraint_check", "next_step", "step", "state_delta"]:
		assert k in data


@pytest.mark.asyncio
async def test_analyze_intent_produces_main_llm_output():
	from companion.enhanced_core import EnhancedCompanionCore
	core = EnhancedCompanionCore()
	result = await core.analyze_intent_only("テストです")
	assert "main_llm_output" in result
	m = result["main_llm_output"]
	for k in ["rationale", "goal_consistency", "constraint_check", "next_step", "step", "state_delta"]:
		assert k in m
