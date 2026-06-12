import sys
import os
sys.path.append(os.getcwd())

from companion.tools.results import ToolStatus, ToolResult, format_symops_response, serialize_to_text

def test_serialization():
    print("Testing serialization...")
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
    print(f"Result:\n{result}")
    assert result == expected
    print("✅ Serialization test passed!")

def test_format_symops_response():
    print("\nTesting format_symops_response...")
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
    print(f"Output:\n{output}")
    
    assert "::status ok" in output
    assert "::linter @app.py" in output
    assert "<<<" in output
    assert "file: app.py" in output
    assert ">>>" in output
    print("✅ format_symops_response test passed!")

def test_error_response():
    print("\nTesting error response...")
    res = ToolResult(
        status=ToolStatus.ERROR,
        tool_name="shell",
        target="ls",
        content=Exception("File not found")
    )
    output = format_symops_response(res)
    print(f"Output:\n{output}")
    assert "::status error" in output
    assert "Exception: File not found" in output
    print("✅ Error response test passed!")

if __name__ == "__main__":
    try:
        test_serialization()
        test_format_symops_response()
        test_error_response()
        print("\n✨ All tests passed successfully!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
