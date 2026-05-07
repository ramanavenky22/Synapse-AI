from __future__ import annotations

from pathlib import Path
from typing import Any

from synapse_ai.ingestion.directory_mapper import map_directory_structure
from synapse_ai.ingestion.file_traverser import traverse_repository_with_resolution
from synapse_ai.ingestion.filters import SKIP_DIRECTORIES
from synapse_ai.ingestion.manifest import build_manifest, save_manifest
from synapse_ai.ingestion.repo_loader import RepositoryContext


def build_repository_manifest(
    repo_ctx: RepositoryContext,
    output_path: Path | None = None,
    max_files: int | None = None,
    extensions: set[str] | None = None,
    include_directory_tree: bool = True,
    ignored_dirs: list[str] | None = None,
) -> dict[str, Any]:
    """
    Build a Layer 1 manifest from an already loaded repository context.

    This variant does not perform repository loading or cleanup.
    """
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
