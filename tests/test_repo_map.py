"""Tests for S3-2 Phase C: Repo Map generation and injection."""

import pytest
from pathlib import Path

from companion.modules.repo_map import (
    RepoMapGenerator,
    RepoMap,
    generate_repo_map_text,
    get_repo_map_generator,
)


@pytest.fixture
def workspace(tmp_path):
    """Create a temporary workspace with test Python files."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")

    (tmp_path / "pkg" / "core.py").write_text(
        '''"""Core module."""


def main():
    """Entry point."""
    return "hello"


class Engine:
    """Main engine class."""

    def start(self):
        """Start the engine."""
        pass

    def stop(self):
        """Stop the engine."""
        pass
'''
    )

    (tmp_path / "pkg" / "utils.py").write_text(
        '''"""Utility functions."""


def helper(x):
    """A helper function."""
    return x * 2


async def async_helper():
    """An async helper."""
    pass
'''
    )

    # Non-Python file (should be ignored)
    (tmp_path / "README.md").write_text("# Test Project")

    # Noise directory (should be skipped)
    (tmp_path / "__pycache__").mkdir(exist_ok=True)
    (tmp_path / "__pycache__" / "cached.py").write_text("def cached(): pass")

    return tmp_path


def test_repo_map_generates_text(workspace):
    """Repo map should generate non-empty text with symbols."""
    gen = RepoMapGenerator(workspace_root=str(workspace))
    repo_map = gen.generate()
    assert repo_map.text
    assert "def main" in repo_map.text
    assert "class Engine" in repo_map.text
    assert "def helper" in repo_map.text
    assert "async def async_helper" in repo_map.text


def test_repo_map_excludes_noise_dirs(workspace):
    """Repo map should not include files from __pycache__ etc."""
    gen = RepoMapGenerator(workspace_root=str(workspace))
    repo_map = gen.generate()
    assert "__pycache__" not in repo_map.text
    assert "cached" not in repo_map.text


def test_repo_map_excludes_non_python(workspace):
    """Repo map should only include Python files."""
    gen = RepoMapGenerator(workspace_root=str(workspace))
    repo_map = gen.generate()
    assert "README" not in repo_map.text


def test_repo_map_symbol_count(workspace):
    """Repo map should count symbols correctly."""
    gen = RepoMapGenerator(workspace_root=str(workspace))
    repo_map = gen.generate()
    # main, Engine, start, stop, helper, async_helper = 6 symbols
    assert repo_map.symbol_count == 6


def test_repo_map_file_count(workspace):
    """Repo map should count files correctly (only files with symbols)."""
    gen = RepoMapGenerator(workspace_root=str(workspace))
    repo_map = gen.generate()
    # core.py and utils.py have symbols; __init__.py has none
    assert repo_map.file_count == 2


def test_repo_map_token_budget(tmp_path):
    """Repo map should respect token budget."""
    # Create many files with many symbols
    for i in range(20):
        (tmp_path / f"mod_{i}.py").write_text(
            "\n".join(f"def func_{i}_{j}(): pass" for j in range(20))
        )

    gen = RepoMapGenerator(workspace_root=str(tmp_path), token_budget=100)  # Very small budget
    repo_map = gen.generate()
    assert repo_map.truncated
    # Text should be within budget (100 tokens * 4 chars = 400 chars, plus header)
    assert len(repo_map.text) < 600


def test_repo_map_caching(workspace):
    """Repo map should cache file symbols by mtime."""
    gen = RepoMapGenerator(workspace_root=str(workspace))
    # First generation populates cache
    gen.generate()
    assert len(gen._cache) > 0

    # Second generation should use cache (same mtime)
    core_path = str(workspace / "pkg" / "core.py")
    rel_path = "pkg/core.py"
    assert rel_path in gen._cache

    # Modify file -> mtime changes -> cache should be invalidated on next generate
    import time
    time.sleep(0.1)
    (workspace / "pkg" / "core.py").write_text("def new_func(): pass")
    gen.generate()
    assert gen._cache[rel_path].symbols[0][1] == "def new_func(): pass"


def test_repo_map_invalidate(workspace):
    """Manual cache invalidation should work."""
    gen = RepoMapGenerator(workspace_root=str(workspace))
    gen.generate()
    assert "pkg/core.py" in gen._cache
    gen.invalidate("pkg/core.py")
    assert "pkg/core.py" not in gen._cache


def test_repo_map_empty_workspace(tmp_path):
    """Empty workspace should produce empty repo map."""
    gen = RepoMapGenerator(workspace_root=str(tmp_path))
    repo_map = gen.generate()
    assert repo_map.text == ""
    assert repo_map.file_count == 0


def test_repo_map_file_with_syntax_error(tmp_path):
    """Files with syntax errors should be skipped gracefully."""
    (tmp_path / "bad.py").write_text("def broken(:\n  pass")
    (tmp_path / "good.py").write_text("def works(): pass")
    gen = RepoMapGenerator(workspace_root=str(tmp_path))
    repo_map = gen.generate()
    assert "def works" in repo_map.text
    assert "broken" not in repo_map.text


def test_repo_map_companion_priority(workspace):
    """Files under companion/ should rank higher than other dirs."""
    # Create a file in a non-priority directory
    (workspace / "other").mkdir()
    (workspace / "other" / "misc.py").write_text("def misc(): pass")
    (workspace / "companion").mkdir()
    (workspace / "companion" / "main.py").write_text("def main(): pass")

    gen = RepoMapGenerator(workspace_root=str(workspace))
    ranked = gen._rank_files([
        gen._extract_file_symbols(workspace / "other" / "misc.py"),
        gen._extract_file_symbols(workspace / "companion" / "main.py"),
    ])
    # companion file should rank higher
    assert ranked[0].path == "companion/main.py"


def test_generate_repo_map_text_function(workspace):
    """Module-level generate_repo_map_text should return text."""
    # Reset singleton
    import companion.modules.repo_map as rm
    rm._repo_map_generator = None
    text = generate_repo_map_text(str(workspace))
    assert text
    assert "def main" in text


def test_generate_repo_map_text_respects_token_budget_override(tmp_path):
    """token_budget param should override the singleton's current budget.

    This is how TierProfile.repo_map_token_budget rations the repo map by
    model strength (docs/agent_surface_redesign_design.md §5.2).
    """
    import companion.modules.repo_map as rm

    for i in range(20):
        (tmp_path / f"mod_{i}.py").write_text(
            "\n".join(f"def func_{i}_{j}(): pass" for j in range(20))
        )

    rm._repo_map_generator = None
    full_text = generate_repo_map_text(str(tmp_path))
    assert len(full_text) > 600

    # Same singleton, but a low-tier-sized budget should truncate hard.
    tight_text = generate_repo_map_text(str(tmp_path), token_budget=100)
    assert len(tight_text) < len(full_text)
    assert len(tight_text) < 600

    # A budget of 0 should suppress the repo map entirely (low tier could
    # configure this to disable it).
    off_text = generate_repo_map_text(str(tmp_path), token_budget=0)
    assert off_text == ""
