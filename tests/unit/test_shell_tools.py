import pytest
from codecrafter.tools.shell_tools import ShellTools, ShellExecutionError, ShellSecurityError

def test_execute_safe_command(monkeypatch):
    # Mock subprocess.run to avoid real command execution
    def mock_run(*args, **kwargs):
        class Result:
            stdout = "mock output"
            stderr = ""
        return Result()
    monkeypatch.setattr("subprocess.run", mock_run)

    output = ShellTools.execute("echo hello")
    assert output == "mock output"

def test_execute_unsafe_command():
    # Attempt to run a disallowed command should raise SecurityError
    with pytest.raises(ShellSecurityError):
        ShellTools.execute("rm -rf /")