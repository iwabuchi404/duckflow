import sys
from pathlib import Path
import pytest

# Add script directory to path to allow import
# This is a common pattern for testing scripts
script_dir = Path(__file__).parent.parent / "scripts"
sys.path.append(str(script_dir))

# Now we can import the script's functions
from compile_flows import run_compiler

@pytest.fixture
def setup_test_environment(tmp_path):
    """Pytest fixture to create a temporary directory structure for testing."""
    # Create temporary directories
    flowspec_dir = tmp_path / "flowspec"
    flowspec_dir.mkdir()
    
    template_dir = tmp_path / "templates"
    template_dir.mkdir(exist_ok=True)
    
    output_dir = tmp_path / "output"
    # Output dir is created by the script, so we don't create it here.

    # Create a dummy flowspec file
    dummy_yaml_content = """
id: flow.test.v1
title: テストフロー
version: 1
status: draft
owner: team/test
summary: A test flow.
rationale: To test the compiler.
steps:
  - id: s1
    name: test.step
    actor: test_actor
    outputs: [test_output]
"""
    (flowspec_dir / "flow.test.v1.yaml").write_text(dummy_yaml_content, encoding="utf-8")

    # Create dummy template files
    main_template_content = "# {{ flow.title }}\n- Actor: {{ flow.steps[0].actor }}\n{{ mermaid_sequence_diagram }}"
    (template_dir / "flow_card.md.j2").write_text(main_template_content, encoding="utf-8")
    
    sequence_template_content = "sequenceDiagram\n  A->>B: Test"
    (template_dir / "sequence.mmd.j2").write_text(sequence_template_content, encoding="utf-8")

    return flowspec_dir, template_dir, output_dir

def test_run_compiler_success(setup_test_environment):
    """Tests the successful generation of a documentation file."""
    flowspec_dir, template_dir, output_dir = setup_test_environment

    # Run the compiler
    run_compiler(flowspec_dir, template_dir, output_dir)

    # Check if the output file was created
    expected_output_file = output_dir / "flow.test.v1.md"
    assert expected_output_file.exists()

    # Check the content of the output file
    content = expected_output_file.read_text(encoding="utf-8")
    assert "# テストフロー" in content
    assert "- Actor: test_actor" in content
    assert "sequenceDiagram" in content
    assert "A->>B: Test" in content

def test_run_compiler_no_files(capsys, setup_test_environment):
    """Tests the behavior when the flowspec directory is empty."""
    flowspec_dir, template_dir, output_dir = setup_test_environment
    
    # Empty the flowspec directory
    for f in flowspec_dir.glob("*.yaml"):
        f.unlink()

    # Run the compiler
    run_compiler(flowspec_dir, template_dir, output_dir)

    # Capture the standard output
    captured = capsys.readouterr()
    assert "No flowspec YAML files found." in captured.out
    
    # Ensure no output files were created
    assert not list(output_dir.glob("*.md"))

def test_run_compiler_nonexistent_input_dir(capsys, tmp_path):
    """Tests behavior with a non-existent input directory."""
    non_existent_dir = tmp_path / "non_existent"
    template_dir = tmp_path / "templates"
    template_dir.mkdir(exist_ok=True)
    output_dir = tmp_path / "output"

    run_compiler(non_existent_dir, template_dir, output_dir)
    
    captured = capsys.readouterr()
    assert "Flowspec directory does not exist." in captured.out

