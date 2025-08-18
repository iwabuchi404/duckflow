import os
from pathlib import Path


def test_main_flow_normal_execution(tmp_path):
	# 準備: 小さなテストファイルを作成（500文字未満でLLM要約を回避）
	repo_root = Path.cwd()
	sample_dir = repo_root / 'temp_test_files'
	sample_dir.mkdir(parents=True, exist_ok=True)
	sample_file = sample_dir / 'phase1_flow_sample.txt'
	sample_file.write_text('hello phase1 flow test', encoding='utf-8')
	
	# システム初期化
	from companion.enhanced_dual_loop import EnhancedDualLoopSystem
	from companion.simple_approval import ApprovalMode
	from companion.state.agent_state import Step
	from companion.core import ActionType
	
	system = EnhancedDualLoopSystem(approval_mode=ApprovalMode.STANDARD)
	# 正常系フローで PLANNING→EXECUTION→REVIEW を許可（1発話2遷移に緩和）
	if hasattr(system, 'transition_limiter'):
		system.transition_limiter.max_transitions_per_utterance = 2
	
	# intent_resultを構築（ファイル読み取りを促すメッセージ）
	intent_result = {
		"action_type": ActionType.FILE_OPERATION,
		"message": f'ファイルを読んで: "{sample_file.as_posix()}"'
	}
	
	# タスクデータを作成し、直接実行（メインフロー: 実行→検証→結果）
	task_data = {
		"type": "enhanced_execution_with_verification",
		"intent_result": intent_result,
		"verification_required": True,
	}
	
	system.task_loop._execute_enhanced_execution_with_verification(task_data)
	
	# 期待: REVIEWステップに遷移している（正常系完了）
	assert system.enhanced_companion.state.step == Step.REVIEW


def test_main_flow_error_recovery():
	# システム初期化
	from companion.enhanced_dual_loop import EnhancedDualLoopSystem
	from companion.simple_approval import ApprovalMode
	from companion.state.agent_state import Step, Status
	
	system = EnhancedDualLoopSystem(approval_mode=ApprovalMode.STANDARD)
	
	# messageを欠落させて早期ガードの復旧フローを誘発
	task_data = {
		"type": "enhanced_execution_with_verification",
		"intent_result": {},
		"verification_required": True,
	}
	
	system.task_loop._execute_enhanced_execution_with_verification(task_data)
	
	# 期待: エラー復旧でPLANNINGに戻る + Status=ERROR
	assert system.enhanced_companion.state.step == Step.PLANNING
	assert system.enhanced_companion.state.status == Status.ERROR
