from companion.tools.results import ToolStatus, ToolResult, format_symops_response, serialize_to_text


def test_serialization():
    data = {
      "file": "app.py",
      "issues": [
        { "line": 10, "message": "Unused variable" },
        { "line": 25, "message": "Syntax error" }
      ]
    }
    expected = """file: app.py
issues:
  -
    line: 10
    message: Unused variable
  -
    line: 25
    message: Syntax error"""
    
    result = serialize_to_text(data)
    assert result == expected


def test_format_symops_response():
    data = {
      "file": "app.py",
      "issues": [
        { "line": 10, "message": "Unused variable" }
      ]
    }
    res = ToolResult(
        status=ToolStatus.OK,
        tool_name="linter",
        target="app.py",
        content=data
    )
    
    output = format_symops_response(res)
    
    assert "::status ok" in output
    assert "::linter @app.py" in output
    assert "<<<" in output
    assert "file: app.py" in output
    assert ">>>" in output


def test_error_response():
    res = ToolResult(
        status=ToolStatus.ERROR,
        tool_name="shell",
        target="ls",
        content=Exception("File not found")
    )
    output = format_symops_response(res)
    assert "::status error" in output
    assert "Exception: File not found" in output
