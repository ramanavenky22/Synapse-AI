from __future__ import annotations

from pathlib import Path
from typing import Any

from synapse_ai.ingestion.directory_mapper import map_directory_structure
from synapse_ai.ingestion.file_traverser import traverse_repository_with_resolution
from synapse_ai.ingestion.filters import SKIP_DIRECTORIES
from synapse_ai.ingestion.manifest import build_manifest, save_manifest
from synapse_ai.ingestion.repo_loader import cleanup_temporary_repository, load_repository


def build_repository_manifest(
    repo_input: str,
    output_path: Path | None = None,
    max_files: int | None = None,
    extensions: set[str] | None = None,
    include_directory_tree: bool = True,
    ignored_dirs: list[str] | None = None,
) -> dict[str, Any]:
    """
    Run the complete Layer 1 ingestion flow and return a manifest.

    Flow:
    1) Load repository (local path or supported URL)
    2) Map directory structure (optional)
    3) Traverse files + resolve filesystem metadata + deduplicate by inode
    4) Build manifest
    5) Save manifest (optional)

    Parameters
    ----------
    repo_input:
        Local repository path or supported repository URL.
    output_path:
        Optional JSON output path for persisted manifest.
    max_files:
        Optional cap on number of source files collected.
    extensions:
        Optional set of source extensions to index.
    include_directory_tree:
        If True, include directory tree in the manifest.
    ignored_dirs:
        Optional list of ignored directory names to record in the manifest.
        If omitted, defaults to the current ingestion skip set.
    """
    repo_ctx = None
    try:
        repo_ctx = load_repository(repo_input)
        repo_root = repo_ctx.local_path

        directory_tree = (
            map_directory_structure(repo_root, extensions=extensions)
            if include_directory_tree
            else None
        )
        traversed = traverse_repository_with_resolution(
            repo_root, max_files=max_files, extensions=extensions
        )

        manifest = build_manifest(
            repo_root=repo_root,
            directory_tree=directory_tree,
            resolved_files=traversed.resolved_files,
            unique_files=traversed.unique_files,
            duplicate_files=traversed.duplicate_files,
            total_scanned=traversed.total_scanned,
            ignored_dirs=ignored_dirs if ignored_dirs is not None else sorted(SKIP_DIRECTORIES),
        )

        if output_path is not None:
            saved_path = save_manifest(manifest, output_path)
            manifest["manifest_path"] = str(saved_path.resolve(strict=False))

        return manifest
    finally:
        if repo_ctx is not None:
            cleanup_temporary_repository(repo_ctx)
