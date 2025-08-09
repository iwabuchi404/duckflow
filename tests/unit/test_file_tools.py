import pytest
from codecrafter.tools.file_tools import FileTools, FileOperationError

def test_read_file_success(tmp_path):
    # Create a temporary file
    file_path = tmp_path / "sample.txt"
    file_path.write_text("hello world")
    # Use FileTools to read the file
    content = FileTools.read_file(str(file_path))
    assert content == "hello world"

def test_read_file_not_found():
    with pytest.raises(FileOperationError):
        FileTools.read_file("non_existent_file.txt")