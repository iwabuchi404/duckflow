import subprocess
from pathlib import Path
from typing import List, Set

from companion.utils.fs_utils import is_excluded_dir


def _resolve_within_workspace(
    path: str, workspace_root: str = "."
) -> tuple[Path, Path]:
    """Resolve a requested tree path and enforce workspace containment.

    Args:
        path: Requested path, relative to workspace_root unless absolute.
        workspace_root: Workspace root directory.

    Returns:
        Tuple of resolved workspace root and resolved target path.

    Raises:
        PermissionError: If the resolved target is outside the workspace root.
    """
    root = Path(workspace_root).resolve()
    requested = Path(path)
    target = (
        requested.resolve() if requested.is_absolute() else (root / requested).resolve()
    )

    if target != root and root not in target.parents:
        raise PermissionError(
            f"Duck Keeper Alert: Access denied to {path} (Outside workspace)"
        )

    return root, target


def _load_ignored_files(root: Path, respect_gitignore: bool) -> Set[str]:
    """Load gitignored paths relative to the workspace root.

    Args:
        root: Resolved workspace root.
        respect_gitignore: Whether to query git ignored paths.

    Returns:
        Set of POSIX-style relative paths ignored by git.
    """
    if not respect_gitignore:
        return set()

    try:
        result = subprocess.run(
            ["git", "ls-files", "--others", "--ignored", "--exclude-standard"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        return {
            line.strip().replace("\\", "/")
            for line in result.stdout.splitlines()
            if line.strip()
        }
    except (subprocess.CalledProcessError, FileNotFoundError):
        return set()


def _coerce_bool(value: bool | str) -> bool:
    """Convert parser-provided bool-like values to a boolean.

    Args:
        value: Boolean value or string representation.

    Returns:
        Parsed boolean value.
    """
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)


async def get_project_tree(  # ← async追加
    path: str = ".",
    depth: int = 3,
    respect_gitignore: bool = True,
    workspace_root: str = ".",
) -> str:
    """
    プロジェクトのディレクトリツリーを取得（安全かつ効率的な探索）

    Args:
        path: 探索起点パス（デフォルト: カレントディレクトリ）
        depth: 最大探索深度（デフォルト: 3）
        respect_gitignore: .gitignoreを尊重するか（デフォルト: True）
        workspace_root: 探索を許可するワークスペースルート

    Returns:
        視認性の高いテキストツリー形式の出力
    """
    # 型変換（パーサーから文字列で渡される場合がある）
    depth = int(depth) if isinstance(depth, str) else depth
    respect_gitignore = _coerce_bool(respect_gitignore)

    try:
        root_path, start_path = _resolve_within_workspace(path, workspace_root)
    except PermissionError as exc:
        return f"Error: {exc}"

    if not start_path.exists():
        return f"Error: Path not found - {start_path}"
    if not start_path.is_dir():
        return f"Error: Path is not a directory - {start_path}"

    ignored_files = _load_ignored_files(root_path, respect_gitignore)

    # ツリー構築
    def build_tree(current: Path, current_depth: int) -> List[str]:
        """Build a visible tree below current while staying inside the workspace."""
        if current_depth > depth:
            return []

        items = []
        try:
            entries = sorted(
                current.iterdir(),
                key=lambda item: (not item.is_dir(), item.name.lower()),
            )
            for entry in entries:
                try:
                    resolved_entry = entry.resolve()
                except OSError:
                    continue

                if (
                    resolved_entry != root_path
                    and root_path not in resolved_entry.parents
                ):
                    continue

                rel_path = resolved_entry.relative_to(root_path).as_posix()
                parts = resolved_entry.relative_to(root_path).parts

                if (
                    is_excluded_dir(entry.name)
                    or any(is_excluded_dir(part) for part in parts)
                    or rel_path in ignored_files
                ):
                    continue

                if entry.is_dir():
                    children = build_tree(resolved_entry, current_depth + 1)
                    items.append(f"{entry.name}/")
                    items.extend(
                        [f"{'  ' * current_depth}{child}" for child in children]
                    )
                elif current_depth <= depth:
                    items.append(entry.name)
        except PermissionError:
            pass

        return items

    tree = build_tree(start_path, 1)
    return "\n".join(tree) if tree else "No visible files/directories found"
