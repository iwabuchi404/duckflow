"""Repo Map: ast-based symbol map generation with ranking and token budget.

Generates a compressed overview of the repository's symbols (functions/classes)
and injects it into the agent's context, reducing the need for exploratory
search actions — especially helpful for weaker models.

Design: companion/modules/repo_map.py (S3-2 Phase C)
"""

import ast
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Default token budget for repo map (1.5k tokens ≈ ~6k chars)
DEFAULT_TOKEN_BUDGET = 1500
# Rough chars-per-token estimate
CHARS_PER_TOKEN = 4
# Max files to include in the map
DEFAULT_MAX_FILES = 80
# Noise directories to skip
_NOISE_DIRS = {
    "__pycache__", ".git", ".venv", "venv", "node_modules",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist", "build",
    ".eggs", ".tox", "htmlcov", ".idea", ".vscode",
}


@dataclass
class FileSymbols:
    """Symbols extracted from a single file."""
    path: str
    mtime: float
    symbols: List[Tuple[str, str, int, int]]  # (kind, signature, line_start, line_end)


@dataclass
class RepoMap:
    """A ranked, budget-compressed repository symbol map."""
    text: str
    file_count: int
    symbol_count: int
    truncated: bool = False


class RepoMapGenerator:
    """Generates and caches a repo map from Python source files.

    Uses ast to extract symbols, a simple heuristic for ranking
    (reference count via grep + file size + recency), and mtime-based
    per-file caching to avoid re-parsing unchanged files.
    """

    def __init__(
        self,
        workspace_root: str = ".",
        token_budget: int = DEFAULT_TOKEN_BUDGET,
        max_files: int = DEFAULT_MAX_FILES,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.token_budget = token_budget
        self.max_files = max_files
        self._cache: Dict[str, FileSymbols] = {}

    def _collect_py_files(self) -> List[Path]:
        """Collect all Python files in the workspace, excluding noise dirs."""
        py_files: List[Path] = []
        for root, dirs, files in os.walk(self.workspace_root):
            # Filter out noise directories in-place
            dirs[:] = [d for d in dirs if d not in _NOISE_DIRS and not d.startswith(".")]
            for f in files:
                if f.endswith(".py"):
                    py_files.append(Path(root) / f)
        return py_files

    def _extract_file_symbols(self, file_path: Path) -> FileSymbols:
        """Extract symbols from a single Python file using ast."""
        rel_path = str(file_path.relative_to(self.workspace_root)).replace("\\", "/")
        mtime = file_path.stat().st_mtime

        # Check cache
        cached = self._cache.get(rel_path)
        if cached and cached.mtime == mtime:
            return cached

        symbols: List[Tuple[str, str, int, int]] = []
        try:
            source = file_path.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(source, filename=str(file_path))
            lines = source.splitlines()

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    line_idx = node.lineno - 1
                    sig = lines[line_idx].strip() if line_idx < len(lines) else f"def {node.name}(...)"
                    kind = "async_def" if isinstance(node, ast.AsyncFunctionDef) else "def"
                    end_line = getattr(node, "end_lineno", node.lineno) or node.lineno
                    symbols.append((kind, sig, node.lineno, end_line))
                elif isinstance(node, ast.ClassDef):
                    line_idx = node.lineno - 1
                    sig = lines[line_idx].strip() if line_idx < len(lines) else f"class {node.name}"
                    end_line = getattr(node, "end_lineno", node.lineno) or node.lineno
                    symbols.append(("class", sig, node.lineno, end_line))
        except (SyntaxError, ValueError, OSError) as e:
            logger.debug(f"Failed to parse {file_path}: {e}")

        fs = FileSymbols(path=rel_path, mtime=mtime, symbols=symbols)
        self._cache[rel_path] = fs
        return fs

    def _rank_files(
        self, file_symbols: List[FileSymbols]
    ) -> List[FileSymbols]:
        """Rank files by a simple heuristic.

        Score = symbol_count * 2 + file_size_factor + recency_factor.
        Higher score = more important = included first.
        """
        now = max(fs.mtime for fs in file_symbols) if file_symbols else 0
        scored: List[Tuple[float, FileSymbols]] = []

        for fs in file_symbols:
            # Symbol count factor (more symbols = more important)
            sym_score = len(fs.symbols) * 2
            # Recency factor (newer = better), normalized 0-10
            recency = ((fs.mtime - (now - 86400 * 30)) / (86400 * 30)) * 10 if now else 0
            recency = max(0, min(10, recency))
            # File path priority: companion/ > tests/ > docs/ > root
            path_score = 0
            if fs.path.startswith("companion/"):
                path_score = 5
            elif fs.path.startswith("src/"):
                path_score = 4
            elif fs.path.startswith("tests/"):
                path_score = 2

            total = sym_score + recency + path_score
            scored.append((total, fs))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [fs for _, fs in scored]

    def _format_repo_map(
        self, ranked: List[FileSymbols], char_budget: int
    ) -> Tuple[str, bool]:
        """Format the ranked symbols into a compact text within budget.

        Returns (text, truncated).
        """
        lines: List[str] = []
        total_chars = 0
        header = "## Repo Map (symbols)"
        total_chars += len(header) + 1
        lines.append(header)

        file_count = 0
        truncated = False

        for fs in ranked:
            if not fs.symbols:
                continue

            file_header = f"\n### {fs.path}"
            file_section = [file_header]
            for kind, sig, start, end in fs.symbols:
                # Compact: just the signature
                file_section.append(f"  {sig}")

            section_text = "\n".join(file_section)
            if total_chars + len(section_text) + 1 > char_budget:
                truncated = True
                break

            lines.append(section_text)
            total_chars += len(section_text) + 1
            file_count += 1

            if file_count >= self.max_files:
                truncated = True
                break

        if file_count == 0:
            # If there were symbols but none fit the budget, still mark truncated
            has_symbols = any(fs.symbols for fs in ranked)
            return "", truncated and has_symbols

        footer = f"\n({file_count} file(s), {sum(len(fs.symbols) for fs in ranked[:file_count])} symbol(s))"
        if truncated:
            footer += " [truncated]"
        lines.append(footer)

        return "\n".join(lines), truncated

    def generate(self) -> RepoMap:
        """Generate the repo map.

        Returns a RepoMap with the compressed text and metadata.
        """
        py_files = self._collect_py_files()
        if not py_files:
            return RepoMap(text="", file_count=0, symbol_count=0)

        # Extract symbols from all files
        all_symbols: List[FileSymbols] = []
        for f in py_files:
            try:
                fs = self._extract_file_symbols(f)
                if fs.symbols:
                    all_symbols.append(fs)
            except OSError:
                pass

        # Rank files
        ranked = self._rank_files(all_symbols)

        # Format within budget
        char_budget = self.token_budget * CHARS_PER_TOKEN
        text, truncated = self._format_repo_map(ranked, char_budget)

        symbol_count = sum(len(fs.symbols) for fs in all_symbols)

        return RepoMap(
            text=text,
            file_count=len(all_symbols),
            symbol_count=symbol_count,
            truncated=truncated,
        )

    def invalidate(self, file_path: str) -> None:
        """Invalidate cache for a specific file (after edit/write/delete).

        Args:
            file_path: Relative path to the file (forward-slash separated).
        """
        if file_path in self._cache:
            del self._cache[file_path]
            logger.debug(f"Repo map cache invalidated for {file_path}")


# Singleton instance (lazily initialized)
_repo_map_generator: Optional[RepoMapGenerator] = None


def get_repo_map_generator(workspace_root: str = ".") -> RepoMapGenerator:
    """Get or create the singleton RepoMapGenerator."""
    global _repo_map_generator
    if _repo_map_generator is None:
        _repo_map_generator = RepoMapGenerator(workspace_root=workspace_root)
    return _repo_map_generator


def generate_repo_map_text(workspace_root: str = ".") -> str:
    """Generate repo map text for prompt injection.

    Returns the compressed symbol map text, or empty string if no symbols found.
    """
    gen = get_repo_map_generator(workspace_root)
    repo_map = gen.generate()
    return repo_map.text
