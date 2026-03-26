from __future__ import annotations

from pathlib import Path

from synapse_ai.ingestion.filters import (
    DEFAULT_SOURCE_EXTENSIONS,
    normalize_extensions,
    is_source_file,
    should_skip_directory,
)
from synapse_ai.models.file_model import FileModel


def traverse_repository(
    repo_root: Path,
    max_files: int | None = None,
    extensions: set[str] | None = None,
) -> tuple[list[FileModel], int]:
    """
    Traverse repository recursively and return:
    - list of Python file metadata
    - total file count scanned (all files, excluding skipped directories)
    """
    if not repo_root.exists():
        raise FileNotFoundError(f"Repository path does not exist: {repo_root}")
    if not repo_root.is_dir():
        raise NotADirectoryError(f"Repository path is not a directory: {repo_root}")
    if max_files is not None and max_files <= 0:
        raise ValueError("max_files must be greater than 0.")

    if extensions is None:
        extensions_set = DEFAULT_SOURCE_EXTENSIONS
    else:
        extensions_set = normalize_extensions(extensions)
        if not extensions_set:
            raise ValueError("extensions must contain at least one non-empty extension.")

    source_files: list[FileModel] = []
    total_files_scanned = 0

    stack: list[Path] = [repo_root]
    visited_dirs: set[Path] = set()

    while stack:
        current_dir = stack.pop()

        try:
            resolved_dir = current_dir.resolve()
        except OSError:
            continue

        if resolved_dir in visited_dirs:
            continue
        visited_dirs.add(resolved_dir)

        if should_skip_directory(current_dir):
            continue

        try:
            entries = list(current_dir.iterdir())
        except (PermissionError, FileNotFoundError, OSError):
            continue

        for entry in entries:
            if entry.is_dir():
                if not should_skip_directory(entry):
                    stack.append(entry)
                continue

            if not entry.is_file():
                continue

            total_files_scanned += 1

            if not is_source_file(entry, extensions_set):
                continue

            relative_path = entry.relative_to(repo_root).as_posix()
            source_files.append(
                FileModel(
                    path=relative_path,
                    relative_path=relative_path,
                    name=entry.name,
                    extension=entry.suffix,
                    size=entry.stat().st_size,
                )
            )

            if max_files is not None and len(source_files) >= max_files:
                return source_files, total_files_scanned

    return source_files, total_files_scanned
