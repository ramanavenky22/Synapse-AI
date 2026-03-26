from __future__ import annotations

from pathlib import Path
from typing import Any

from synapse_ai.ingestion.filters import (
    DEFAULT_SOURCE_EXTENSIONS,
    is_source_file,
    normalize_extensions,
    should_skip_directory,
)


def map_directory_structure(
    repo_root: Path, extensions: set[str] | None = None
) -> dict[str, Any]:
    """
    Build a nested dictionary tree for repository directories and source files.
    """
    if not repo_root.exists():
        raise FileNotFoundError(f"Repository path does not exist: {repo_root}")
    if not repo_root.is_dir():
        raise NotADirectoryError(f"Repository path is not a directory: {repo_root}")

    if extensions is None:
        extensions_set = DEFAULT_SOURCE_EXTENSIONS
    else:
        extensions_set = normalize_extensions(extensions)
        if not extensions_set:
            raise ValueError("extensions must contain at least one non-empty extension.")

    visited_dirs: set[Path] = set()

    def _build_tree(current_dir: Path) -> dict[str, Any]:
        try:
            resolved_dir = current_dir.resolve()
        except OSError:
            return {
                "type": "directory",
                "name": current_dir.name,
                "relative_path": current_dir.relative_to(repo_root).as_posix()
                if current_dir != repo_root
                else ".",
                "directories": {},
                "files": [],
            }

        if resolved_dir in visited_dirs:
            return {
                "type": "directory",
                "name": current_dir.name,
                "relative_path": current_dir.relative_to(repo_root).as_posix()
                if current_dir != repo_root
                else ".",
                "directories": {},
                "files": [],
            }

        visited_dirs.add(resolved_dir)

        directories: dict[str, Any] = {}
        files: list[str] = []

        try:
            entries = sorted(current_dir.iterdir(), key=lambda p: p.name.lower())
        except (PermissionError, FileNotFoundError, OSError):
            entries = []

        for entry in entries:
            if entry.is_dir():
                if should_skip_directory(entry):
                    continue
                directories[entry.name] = _build_tree(entry)
                continue

            if is_source_file(entry, extensions_set):
                files.append(entry.name)

        return {
            "type": "directory",
            "name": current_dir.name,
            "relative_path": current_dir.relative_to(repo_root).as_posix()
            if current_dir != repo_root
            else ".",
            "directories": directories,
            "files": files,
        }

    return _build_tree(repo_root)


def pretty_print_tree(tree: dict[str, Any]) -> str:
    """
    Convert a mapped directory tree into a printable string.
    """
    lines: list[str] = [f"{tree['name']}/"]

    def _walk(node: dict[str, Any], prefix: str) -> None:
        dir_items = sorted(node.get("directories", {}).items(), key=lambda item: item[0].lower())
        file_items = sorted(node.get("files", []), key=lambda name: name.lower())
        children_count = len(dir_items) + len(file_items)

        index = 0
        for dir_name, dir_node in dir_items:
            index += 1
            is_last = index == children_count
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{dir_name}/")
            next_prefix = f"{prefix}{'    ' if is_last else '│   '}"
            _walk(dir_node, next_prefix)

        for file_name in file_items:
            index += 1
            is_last = index == children_count
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{file_name}")

    _walk(tree, "")
    return "\n".join(lines)
