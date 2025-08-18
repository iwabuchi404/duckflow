import os
from pathlib import Path


def test_phase1_config_keys_present():
    cfg_path = Path('config/config.yaml')
    assert cfg_path.exists(), 'config/config.yaml missing'
    text = cfg_path.read_text(encoding='utf-8')
    assert 'phase1:' in text
    assert 'work_dir:' in text
    assert 'safe_extensions:' in text


def test_file_protector_blocks_outside(tmp_path, monkeypatch):
    # Set work_dir to tmp workspace for test isolation
    repo_root = Path.cwd()
    try:
        from companion.security.file_protector import FileProtector
    except Exception as e:
        raise AssertionError(f'Failed to import FileProtector: {e}')

    work_dir = tmp_path / 'work'
    work_dir.mkdir(parents=True, exist_ok=True)
    protector = FileProtector(str(work_dir), ['.txt'])

    # outside path
    outside_file = repo_root / 'outside.txt'
    assert protector.check_operation('read', str(outside_file)) is True
    assert protector.check_operation('write', str(outside_file)) is False

    # inside path
    inside_file = work_dir / 'note.txt'
    assert protector.check_operation('write', str(inside_file)) is True


def test_transition_controller_basic():
    from companion.state.transition import TransitionController
    from companion.state.agent_state import Step

    tc = TransitionController()
    assert tc.is_transition_allowed(Step.PLANNING, Step.EXECUTION)
    assert not tc.is_transition_allowed(Step.EXECUTION, Step.PLANNING)  # only via error recovery
    assert tc.get_error_recovery_step(Step.EXECUTION) == Step.PLANNING


def test_transition_limiter_one_per_utterance():
    from companion.state.transition import TransitionLimiter
    tl = TransitionLimiter(max_transitions_per_utterance=1, reset_interval_seconds=60)
    assert tl.can_transition() is True
    tl.record_transition()
    assert tl.can_transition() is False
    tl.reset()
    assert tl.can_transition() is True


def test_enhanced_status_display():
    """強化されたステータス表示のテスト"""
    try:
        from companion.enhanced_dual_loop import EnhancedDualLoopSystem
        from companion.simple_approval import ApprovalMode
        
        # システムを初期化
        system = EnhancedDualLoopSystem(approval_mode=ApprovalMode.STANDARD)
        
        # ステータス取得
        status = system.get_status()
        
        # Phase 1情報が含まれているかチェック
        assert "phase1" in status, "Phase 1情報が含まれていない"
        phase1 = status["phase1"]
        
        # 基本フィールドの存在確認
        assert "current_step" in phase1, "current_stepが含まれていない"
        assert "current_status" in phase1, "current_statusが含まれていない"
        assert "transition_control" in phase1, "transition_controlが含まれていない"
        
        # 遷移制御情報の確認
        transition_control = phase1["transition_control"]
        assert "enabled" in transition_control, "transition_control.enabledが含まれていない"
        assert "max_transitions" in transition_control, "transition_control.max_transitionsが含まれていない"
        assert "current_count" in transition_control, "transition_control.current_countが含まれていない"
        
        # 初期状態の確認
        assert phase1["current_step"] == "PLANNING", f"初期ステップが不正: {phase1['current_step']}"
        assert phase1["current_status"] == "IN_PROGRESS", f"初期ステータスが不正: {phase1['current_status']}"
        assert transition_control["enabled"] is True, "遷移制御が無効になっている"
        assert transition_control["current_count"] == 0, "初期カウントが0でない"
        
        print("✅ 強化されたステータス表示テスト成功")
        
    except Exception as e:
        raise AssertionError(f'強化されたステータス表示テスト失敗: {e}')


def test_enhanced_task_loop_status():
    """EnhancedTaskLoopのステータス表示テスト"""
    try:
        from companion.enhanced_dual_loop import EnhancedTaskLoop, EnhancedDualLoopSystem
        from companion.simple_approval import ApprovalMode
        import queue
        
        # システムを初期化
        system = EnhancedDualLoopSystem(approval_mode=ApprovalMode.STANDARD)
        task_queue = queue.Queue()
        status_queue = queue.Queue()
        
        # EnhancedTaskLoopを初期化
        task_loop = EnhancedTaskLoop(
            task_queue, status_queue, 
            system.enhanced_companion, 
            system.context_manager,
            system
        )
        
        # ステータス取得
        status = task_loop.get_status()
        
        # Phase 1情報が含まれているかチェック
        assert "phase1" in status, "TaskLoop Phase 1情報が含まれていない"
        phase1 = status["phase1"]
        
        # 基本フィールドの存在確認
        assert "step" in phase1, "stepが含まれていない"
        assert "status" in phase1, "statusが含まれていない"
        
        print("✅ EnhancedTaskLoopステータス表示テスト成功")
        
    except Exception as e:
        raise AssertionError(f'EnhancedTaskLoopステータス表示テスト失敗: {e}')


