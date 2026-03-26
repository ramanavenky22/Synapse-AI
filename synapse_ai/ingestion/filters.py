from __future__ import annotations

from pathlib import Path


# Default set of "supported source" extensions for repository indexing.
# You can expand this list as more language support is needed.
DEFAULT_SOURCE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".cs",
    ".rb",
    ".go",
    ".rs",
    ".php",
    ".swift",
    ".kt",
    ".scala",
    ".sql",
    ".sh",
}

SKIP_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",

    # Python virtual environments
    ".venv",
    "venv",
    "env",

    # Python caches
    "node_modules",
    "__pycache__",

    # Test / type-check / lint caches
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".cache",

    # Test envs
    ".tox",
    ".nox",

    # Package manager directories
    "node_modules",
    "bower_components",
    "jspm_packages",

    # Build / distribution outputs
    "build",
    "dist",
    "out",
    "coverage",

    # IDE/editor dirs (avoid indexing local project metadata)
    ".idea",
    ".vscode",

    # OS / tool temp dirs
    "tmp",
    "temp",

    # Rust/Go/etc build artifacts commonly present in repos
    "target",
    "vendor",

    # Egg metadata used by python packaging
    ".eggs",
}


def should_skip_directory(path: Path) -> bool:
    return path.name in SKIP_DIRECTORIES


def normalize_extensions(extensions: set[str]) -> set[str]:
    normalized: set[str] = set()
    for ext in extensions:
        ext = ext.strip().lower()
        if not ext:
            continue
        if not ext.startswith("."):
            ext = "." + ext
        normalized.add(ext)
    return normalized


def is_source_file(path: Path, extensions: set[str]) -> bool:
    return path.is_file() and path.suffix.lower() in extensions


def is_python_file(path: Path) -> bool:
    # Backwards-compatible helper for Python-only mode.
    return is_source_file(path, DEFAULT_SOURCE_EXTENSIONS)
