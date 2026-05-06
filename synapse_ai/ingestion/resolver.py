from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def resolve_file(path: Path, repo_root: Path) -> dict[str, Any]:
    """
    Collect filesystem-level metadata for a single path under ``repo_root``.

    This is Layer 1 ingestion only: no import/module resolution.

    ``original_path`` is the path relative to ``repo_root`` using the **logical**
    location (symlink path if applicable), not the symlink target's path.

    Parameters
    ----------
    path:
        File path (typically absolute from directory traversal).
    repo_root:
        Repository root used to compute ``original_path``.

    Returns
    -------
    dict
        Keys: ``original_path``, ``absolute_path``, ``resolved_path``, ``exists``,
        ``link_exists``, ``is_symlink``, ``size_bytes``, ``extension``, ``inode``,
        ``device``, ``identity`` (``[device, inode]``).
        ``link_exists`` is true if the path is a resolvable file/dir *or* a symlink
        still present on disk (including broken symlinks).

    Raises
    ------
    ValueError
        If ``path`` does not lie under ``repo_root`` (after normalizing).
    """
    repo_abs = repo_root.expanduser().resolve(strict=False)

    path_obj = Path(path).expanduser()
    if not path_obj.is_absolute():
        joined = repo_abs / path_obj
    else:
        joined = path_obj

    # Absolute path without following symlinks (preserves symlink location).
    absolute_norm = os.path.abspath(joined)
    p = Path(absolute_norm)

    try:
        original_path = p.relative_to(repo_abs).as_posix()
    except ValueError as exc:
        raise ValueError(
            f"Path {p} is not inside repository root {repo_abs}"
        ) from exc

    absolute_path = absolute_norm

    try:
        resolved_path = str(p.resolve(strict=False))
    except (OSError, RuntimeError):
        resolved_path = absolute_path

    try:
        exists = p.exists()
    except OSError:
        exists = False

    try:
        is_symlink = p.is_symlink()
    except OSError:
        is_symlink = False

    try:
        link_exists = p.exists() or p.is_symlink()
    except OSError:
        link_exists = bool(exists or is_symlink)

    extension = p.suffix.lower()

    size_bytes = 0
    inode = 0
    device = 0

    try:
        if is_symlink and not exists:
            # Broken symlink: metadata lives on the link itself.
            st = p.lstat()
        elif is_symlink:
            # Follow to target for size and physical identity of the content.
            st = p.stat()
        else:
            st = p.stat()
        size_bytes = int(st.st_size)
        inode = int(st.st_ino)
        device = int(st.st_dev)
    except (OSError, FileNotFoundError):
        try:
            st = p.lstat()
            size_bytes = int(st.st_size)
            inode = int(st.st_ino)
            device = int(st.st_dev)
        except OSError:
            pass

    identity: list[int] = [device, inode]

    return {
        "original_path": original_path,
        "absolute_path": absolute_path,
        "resolved_path": resolved_path,
        "exists": exists,
        "link_exists": link_exists,
        "is_symlink": is_symlink,
        "size_bytes": size_bytes,
        "extension": extension,
        "inode": inode,
        "device": device,
        "identity": identity,
    }


def deduplicate_files(
    files: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Partition file records into physically unique vs duplicate paths.

    Duplicates share the same ``identity`` ``[device, inode]`` as an earlier
    record (hard links or multiple symlink paths to one file). The **first**
    occurrence stays in the unique list; later rows go to ``duplicates``.

    Rows without a valid two-element ``identity`` are treated as unique and
    never moved to ``duplicates``. ``[0, 0]`` is treated as non-deduplicable
    so unrelated edge cases do not collapse together.

    Parameters
    ----------
    files:
        Dicts typically produced by :func:`resolve_file` (must include
        ``identity`` for deduplication).
    """
    seen: set[tuple[int, int]] = set()
    unique: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []

    for f in files:
        ident = f.get("identity")
        if not isinstance(ident, (list, tuple)) or len(ident) != 2:
            unique.append(f)
            continue
        try:
            key = (int(ident[0]), int(ident[1]))
        except (TypeError, ValueError):
            unique.append(f)
            continue
        if key == (0, 0):
            unique.append(f)
            continue
        if key in seen:
            duplicates.append(f)
        else:
            seen.add(key)
            unique.append(f)

    return unique, duplicates
