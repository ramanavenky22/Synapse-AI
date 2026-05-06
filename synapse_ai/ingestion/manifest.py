from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


def build_manifest(
    repo_root: Path,
    directory_tree: dict[str, Any] | None,
    resolved_files: list[dict[str, Any]],
    unique_files: list[dict[str, Any]],
    duplicate_files: list[dict[str, Any]],
    total_scanned: int | None = None,
    ignored_dirs: list[str] | None = None,
) -> dict[str, Any]:
    """
    Build the final Layer 1 repository manifest.

    The manifest is the handoff contract for Layer 2 dependency modeling.
    ``source_files`` contains unique physical files only (deduplicated by
    ``(device, inode)`` upstream).
    """
    extension_counter: Counter[str] = Counter()
    symlink_count = 0
    broken_symlink_count = 0

    for file_info in unique_files:
        extension = file_info.get("extension")
        if isinstance(extension, str) and extension:
            extension_counter[extension.lower()] += 1

        is_symlink = bool(file_info.get("is_symlink", False))
        exists = bool(file_info.get("exists", False))
        if is_symlink:
            symlink_count += 1
            if not exists:
                broken_symlink_count += 1

    manifest: dict[str, Any] = {
        "repo_root": str(repo_root.expanduser().resolve(strict=False)),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_scanned": total_scanned,
        "total_resolved_files": len(resolved_files),
        "total_unique_files": len(unique_files),
        "total_duplicate_files": len(duplicate_files),
        "source_files": unique_files,
        "duplicates": duplicate_files,
        "directory_tree": directory_tree,
        "ignored_dirs": ignored_dirs or [],
        "extension_summary": dict(sorted(extension_counter.items())),
        "symlink_count": symlink_count,
        "broken_symlink_count": broken_symlink_count,
    }
    return manifest


def save_manifest(manifest: dict[str, Any], output_path: Path) -> Path:
    """
    Save a manifest to disk as pretty JSON and return the saved path.
    """
    output = Path(output_path).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return output


def load_manifest(path: Path) -> dict[str, Any]:
    """
    Load a manifest JSON file from disk.
    """
    manifest_path = Path(path).expanduser()
    return json.loads(manifest_path.read_text(encoding="utf-8"))
