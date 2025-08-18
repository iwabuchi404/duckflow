import pytest

@pytest.mark.asyncio
async def test_context_assembler_uses_fixed_five():
	from companion.enhanced_core import EnhancedCompanionCore
	from companion.core import ActionType
	core = EnhancedCompanionCore()
	# 固定5項目を設定
	core.state.set_fixed_five(goal="G", why_now="N", constraints=["C1"], plan_brief=["P1"], open_questions=["Q1"])
	# 軽量ワークスペース文脈
	core.state.collected_context["workspace_info"] = {"current_path": ".", "files": ["a.txt", "b.md"]}
	# Direct responseを実行して内部でsystem promptを構築
	res = await core.process_with_intent_result({
		"enhanced_mode": True,
		"action_type": ActionType.DIRECT_RESPONSE,
		"message": "hello"
	})
	# 例外なく通ること
	assert isinstance(res, str)
