from companion.modules.session_manager import SessionManager
from companion.state.agent_state import AgentMode, AgentState, SyntaxErrorInfo


def test_session_manager_round_trips_agent_state(tmp_path) -> None:
    """SessionManager should save and restore core AgentState fields."""
    state = AgentState()
    state.session_id = "session-test"
    state.current_mode = AgentMode.INVESTIGATION
    state.add_message("user", "調査してください")
    state.last_action_result = "last result"
    state.last_syntax_errors.append(
        SyntaxErrorInfo(
            error_type="unknown_tool",
            raw_snippet="bad_tool",
            correction_hint="use a known tool",
        )
    )
    state.touch()

    manager = SessionManager(str(tmp_path / "sessions"))
    manager.save(state)

    loaded = manager.load("session-test")

    assert loaded is not None
    assert loaded.session_id == state.session_id
    assert loaded.current_mode == AgentMode.INVESTIGATION
    assert loaded.conversation_history == state.conversation_history
    assert loaded.last_action_result == "last result"
    assert loaded.last_syntax_errors[0].error_type == "unknown_tool"
    assert manager.get_latest_id() == "session-test"


def test_session_manager_returns_none_for_corrupt_session(tmp_path) -> None:
    """A corrupt session file should not crash load()."""
    session_dir = tmp_path / "sessions"
    session_dir.mkdir()
    (session_dir / "broken.json").write_text("{not-json", encoding="utf-8")

    manager = SessionManager(str(session_dir))

    assert manager.load("broken") is None
