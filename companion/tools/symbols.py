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
from typing import List, Optional, Tuple

from .results import ToolResult

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


async def list_symbols(path: str, workspace_root: str = ".") -> str | ToolResult:
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
        return ToolResult.error("list_symbols", path, f"File not found: {path}")

    if file_path.suffix != ".py":
        return ToolResult.error("list_symbols", path, f"Not a Python file: {path}")

    try:
        source_lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError as e:
        return ToolResult.error("list_symbols", path, f"Cannot read file: {e}")

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
) -> str | ToolResult:
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
        return ToolResult.error("find_definition", name, f"Path not found: {scope}")

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


async def replace_function(
    path: str,
    name: str,
    body: str,
    workspace_root: str = ".",
) -> str | ToolResult:
    r'''Replace a function or class definition in a Python file by name.

    Uses ast to locate the target symbol by name, then replaces its source
    text with the provided body. The new body is syntax-validated before
    writing. If multiple symbols share the same name, an ambiguity error
    is returned with candidate locations.

    Sym-Ops format:
        ::replace_function
        <<<
        ---
        path: "companion/core.py"
        name: "execute_actions"
        body: |
          def execute_actions(actions):
              """Execute a list of actions."""
              for a in actions:
                  await a.run()
        ---
        >>>

    Args:
        path: Path to the Python file (relative to workspace root).
        name: Symbol name to replace (function or class).
        body: New function/class source code (must be valid Python).
        workspace_root: Workspace root directory.

    Returns:
        Success message with line range, or error message.
    '''
    root = Path(workspace_root).resolve()
    file_path = (root / path).resolve()

    if not file_path.exists():
        return ToolResult.error("replace_function", path, f"File not found: {path}")

    if file_path.suffix != ".py":
        return ToolResult.error("replace_function", path, f"Not a Python file: {path}")

    # Validate new body syntax
    try:
        ast.parse(body)
    except SyntaxError as e:
        return ToolResult.error(
            "replace_function", path, f"New body has syntax error: {e}"
        )

    # Read source
    try:
        source = file_path.read_text(encoding="utf-8")
    except OSError as e:
        return ToolResult.error("replace_function", path, f"Cannot read file: {e}")

    source_lines = source.splitlines(keepends=True)

    # Parse and find matching symbols
    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError as e:
        return ToolResult.error("replace_function", path, f"File has syntax error: {e}")

    candidates: List[Tuple[int, int, str]] = []  # (lineno, end_lineno, kind)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            simple_name = node.name.rsplit(".")[-1] if hasattr(node, 'name') else ""
            if simple_name == name:
                end_line = getattr(node, "end_lineno", node.lineno) or node.lineno
                kind = "class" if isinstance(node, ast.ClassDef) else "function"
                candidates.append((node.lineno, end_line, kind))

    if not candidates:
        return ToolResult.error(
            "replace_function", path, f"Symbol '{name}' not found in {path}"
        )

    if len(candidates) > 1:
        locs = "\n".join(
            f"  line {ln}-{end} ({kind})" for ln, end, kind in candidates
        )
        return ToolResult.error(
            "replace_function",
            path,
            (
                f"Multiple definitions of '{name}' found:\n{locs}\n"
                f"Use edit_file with SEARCH/REPLACE for ambiguous targets."
            ),
        )

    start_line, end_line, kind = candidates[0]

    # Replace the source lines
    # source_lines is 0-indexed, ast lineno is 1-indexed
    new_lines = source_lines[:start_line - 1] + [body]
    if not body.endswith("\n"):
        new_lines.append("\n")
    new_lines.extend(source_lines[end_line:])

    new_source = "".join(new_lines)

    # Validate the full file after replacement
    try:
        ast.parse(new_source)
    except SyntaxError as e:
        return ToolResult.error(
            "replace_function", path, f"Replacement produces invalid syntax in file: {e}"
        )

    # Write the file
    try:
        file_path.write_text(new_source, encoding="utf-8")
    except OSError as e:
        return ToolResult.error("replace_function", path, f"Cannot write file: {e}")

    # Invalidate repo map cache
    try:
        from companion.modules.repo_map import get_repo_map_generator
        rel = str(file_path.relative_to(root)).replace("\\", "/")
        get_repo_map_generator().invalidate(rel)
    except Exception:
        pass  # Best-effort

    return (
        f"Replaced {kind} '{name}' in {path} "
        f"(lines {start_line}-{end_line} -> new body)."
    )
