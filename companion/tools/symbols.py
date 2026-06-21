"""Symbol-layer tools using Python's ast module.

Provides list_symbols and find_definition for structural code navigation
without external dependencies (no LSP, no tree-sitter).

Design: companion/tools/symbols.py (S3-2 Phase B)
"""

import ast
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SymbolInfo:
    """Information about a single symbol (function/class)."""
    name: str
    kind: str  # "function", "async_function", "class"
    signature: str
    line_start: int
    line_end: int
    docstring: str = ""
    file_path: str = ""

    def to_display(self) -> str:
        """One-line display format for list output."""
        doc = f"  # {self.docstring}" if self.docstring else ""
        # Show qualified name for nested symbols
        simple = self.name.rsplit(".")[-1]
        qual_prefix = f"({self.name}) " if "." in self.name else ""
        return f"  {qual_prefix}{self.signature}  (lines {self.line_start}-{self.line_end}){doc}"


def _parse_file(file_path: Path) -> Optional[ast.AST]:
    """Parse a Python file and return its AST, or None on failure."""
    try:
        source = file_path.read_text(encoding="utf-8", errors="ignore")
        return ast.parse(source, filename=str(file_path))
    except (SyntaxError, ValueError, OSError) as e:
        logger.debug(f"Failed to parse {file_path}: {e}")
        return None


def _extract_symbols(file_path: Path, source_lines: list[str]) -> List[SymbolInfo]:
    """Extract all top-level and nested symbols from a parsed AST.

    Args:
        file_path: Path to the Python file.
        source_lines: Lines of the source code (for signature extraction).

    Returns:
        List of SymbolInfo for all functions and classes.
    """
    tree = _parse_file(file_path)
    if tree is None:
        return []

    symbols: List[SymbolInfo] = []

    def _visit(node: ast.AST, parent_qualname: str = ""):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                kind = "async_function" if isinstance(child, ast.AsyncFunctionDef) else "function"
                name = child.name
                qualname = f"{parent_qualname}.{name}" if parent_qualname else name

                # Extract signature from source line
                line_idx = child.lineno - 1
                signature = source_lines[line_idx].strip() if line_idx < len(source_lines) else f"def {name}(...)"

                # Extract docstring
                docstring = ""
                if (child.body and isinstance(child.body[0], ast.Expr)
                        and isinstance(child.body[0].value, ast.Constant)
                        and isinstance(child.body[0].value.value, str)):
                    raw_doc = child.body[0].value.value
                    docstring = raw_doc.strip().split("\n")[0][:80]

                symbols.append(SymbolInfo(
                    name=qualname,
                    kind=kind,
                    signature=signature,
                    line_start=child.lineno,
                    line_end=getattr(child, "end_lineno", child.lineno) or child.lineno,
                    docstring=docstring,
                    file_path=str(file_path),
                ))

                # Recurse into function body for nested functions
                _visit(child, qualname)

            elif isinstance(child, ast.ClassDef):
                name = child.name
                qualname = f"{parent_qualname}.{name}" if parent_qualname else name

                line_idx = child.lineno - 1
                signature = source_lines[line_idx].strip() if line_idx < len(source_lines) else f"class {name}"

                docstring = ""
                if (child.body and isinstance(child.body[0], ast.Expr)
                        and isinstance(child.body[0].value, ast.Constant)
                        and isinstance(child.body[0].value.value, str)):
                    raw_doc = child.body[0].value.value
                    docstring = raw_doc.strip().split("\n")[0][:80]

                symbols.append(SymbolInfo(
                    name=qualname,
                    kind="class",
                    signature=signature,
                    line_start=child.lineno,
                    line_end=getattr(child, "end_lineno", child.lineno) or child.lineno,
                    docstring=docstring,
                    file_path=str(file_path),
                ))

                # Recurse into class body for methods
                _visit(child, qualname)

    _visit(tree)
    return symbols


async def list_symbols(path: str, workspace_root: str = ".") -> str:
    """List all functions and classes in a Python file.

    Shows name, signature, line range, and docstring first line for each symbol.
    Nested functions and methods are included with qualified names (e.g. "Class.method").

    Sym-Ops format:
        ::list_symbols
        <<<
        ---
        path: "companion/core.py"
        ---
        >>>

    Args:
        path: Path to a Python file (relative to workspace root).
        workspace_root: Workspace root directory.

    Returns:
        Formatted list of symbols with signatures and line ranges.
    """
    root = Path(workspace_root).resolve()
    file_path = (root / path).resolve()

    if not file_path.exists():
        return f"::status error\nReason: File not found: {path}"

    if file_path.suffix != ".py":
        return f"::status error\nReason: Not a Python file: {path}"

    try:
        source_lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError as e:
        return f"::status error\nReason: Cannot read file: {e}"

    symbols = _extract_symbols(file_path, source_lines)

    if not symbols:
        return f"No symbols found in {path}"

    parts = [f"Symbols in {path} ({len(symbols)}):"]
    for sym in symbols:
        parts.append(sym.to_display())

    return "\n".join(parts)


async def find_definition(
    name: str,
    scope: str = ".",
    workspace_root: str = ".",
) -> str:
    """Find where a symbol (function/class) is defined.

    Searches all Python files under `scope` using ast. Returns the file path,
    line number, and signature for each match. When multiple definitions exist
    with the same name, all candidates are listed.

    Sym-Ops format:
        ::find_definition
        <<<
        ---
        name: "execute_actions"
        scope: "companion"
        ---
        >>>

    Args:
        name: Symbol name to search for (function or class name).
        scope: Directory to search (default: ".", relative to workspace root).
        workspace_root: Workspace root directory.

    Returns:
        List of definition locations with file:line and signature.
    """
    root = Path(workspace_root).resolve()
    search_dir = (root / scope).resolve()

    if not search_dir.exists():
        return f"::status error\nReason: Path not found: {scope}"

    # Collect all Python files
    py_files: List[Path] = []
    if search_dir.is_file() and search_dir.suffix == ".py":
        py_files = [search_dir]
    else:
        for f in search_dir.rglob("*.py"):
            if any(part.startswith(".") for part in f.parts):
                continue
            py_files.append(f)

    matches: List[str] = []

    for py_file in py_files:
        try:
            source_lines = py_file.read_text(encoding="utf-8", errors="ignore").splitlines()
            symbols = _extract_symbols(py_file, source_lines)
            rel_path = py_file.relative_to(root)

            for sym in symbols:
                # Match by simple name (last component of qualified name)
                simple_name = sym.name.rsplit(".")[-1]
                if simple_name == name:
                    matches.append(
                        f"  {rel_path}:{sym.line_start}: {sym.signature}"
                    )
        except (OSError, PermissionError):
            pass

    if not matches:
        return f"No definition found for '{name}' in '{scope}'"

    header = f"Definition(s) of '{name}' ({len(matches)} found):"
    return "\n".join([header] + matches)
