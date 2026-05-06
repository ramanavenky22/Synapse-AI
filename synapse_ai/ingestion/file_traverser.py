from __future__ import annotations

from pathlib import Path
from typing import Any, NamedTuple

from synapse_ai.ingestion.filters import (
    DEFAULT_SOURCE_EXTENSIONS,
    normalize_extensions,
    is_source_file,
    should_skip_directory,
)
from synapse_ai.ingestion.resolver import deduplicate_files, resolve_file
from synapse_ai.models.file_model import FileModel


class ResolvedTraverseResult(NamedTuple):
    """Output of :func:`traverse_repository_with_resolution`."""

    source_files: list[FileModel]
    total_scanned: int
    resolved_files: list[dict[str, Any]]
    unique_files: list[dict[str, Any]]
    duplicate_files: list[dict[str, Any]]


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


def traverse_repository_with_resolution(
    repo_root: Path,
    max_files: int | None = None,
    extensions: set[str] | None = None,
) -> ResolvedTraverseResult:
    """
    Run :func:`traverse_repository`, then Layer 1 :func:`resolve_file` on each
    entry, then :func:`deduplicate_files` by ``(device, inode)``.

    Connects repository root (from :func:`~synapse_ai.ingestion.repo_loader.load_repository`)
    to filesystem metadata + physical uniqueness for the manifest.

    ``resolved_files`` is ordered like ``source_files`` (full list before dedupe).
    ``unique_files`` / ``duplicate_files`` partition by shared ``identity``.
    """
    source_files, total_scanned = traverse_repository(
        repo_root, max_files=max_files, extensions=extensions
    )
    root = repo_root.expanduser().resolve(strict=False)

    resolved_files: list[dict[str, Any]] = []
    for f in source_files:
        path = root / f.relative_path
        resolved_files.append(resolve_file(path, root))

    unique_files, duplicate_files = deduplicate_files(resolved_files)
    return ResolvedTraverseResult(
        source_files=source_files,
        total_scanned=total_scanned,
        resolved_files=resolved_files,
        unique_files=unique_files,
        duplicate_files=duplicate_files,
    )
