from __future__ import annotations

from pathlib import Path
from typing import Callable

from synapse_ai.dependency_graph.models import ParsedFile
from synapse_ai.dependency_graph.parsers.generic_parser import parse_generic_file
from synapse_ai.dependency_graph.parsers.javascript_parser import parse_javascript_file
from synapse_ai.dependency_graph.parsers.python_parser import parse_python_file

EXTENSION_LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c_header",
    ".cs": "csharp",
    ".rb": "ruby",
    ".go": "go",
    ".rs": "rust",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".sql": "sql",
    ".sh": "shell",
}


def normalize_extension(extension: str) -> str:
    """
    Normalize extension: trim, lowercase, and ensure leading dot.
    """
    ext = extension.strip().lower()
    if not ext:
        return ""
    if not ext.startswith("."):
        ext = "." + ext
    return ext


def get_language_for_extension(extension: str) -> str:
    """
    Resolve language from extension; fallback to "generic".
    """
    ext = normalize_extension(extension)
    return EXTENSION_LANGUAGE_MAP.get(ext, "generic")


def get_parser_for_extension(extension: str) -> Callable[..., ParsedFile]:
    """
    Return parser function for extension.
    """
    ext = normalize_extension(extension)
    if ext == ".py":
        return parse_python_file
    if ext in {".js", ".ts"}:
        return parse_javascript_file
    return parse_generic_file


def parse_file_by_extension(
    file_path: Path, repo_root: Path, extension: str | None = None
) -> ParsedFile:
    """
    Parse a file by extension using the registry and return ParsedFile.

    If parser raises, returns a valid ParsedFile with parse_errors populated.
    """
    ext = normalize_extension(extension or file_path.suffix)
    language = get_language_for_extension(ext)
    parser = get_parser_for_extension(ext)

    try:
        if ext not in {".py", ".js", ".ts"}:
            return parse_generic_file(
                file_path=file_path, repo_root=repo_root, language=language
            )
        if ext == ".py":
            return parse_python_file(file_path=file_path, repo_root=repo_root)
        return parse_javascript_file(file_path=file_path, repo_root=repo_root)
    except Exception as exc:  # pragma: no cover - defensive boundary
        repo_abs = repo_root.expanduser().resolve(strict=False)
        path_obj = Path(file_path).expanduser()
        absolute_path = path_obj if path_obj.is_absolute() else repo_abs / path_obj
        absolute_path = absolute_path.resolve(strict=False)
        try:
            relative_path = absolute_path.relative_to(repo_abs).as_posix()
        except ValueError:
            relative_path = absolute_path.as_posix()

        err = (
            f"parser={parser.__name__} extension={ext or '<none>'} "
            f"error={type(exc).__name__}: {exc}"
        )
        return ParsedFile(
            file_path=relative_path,
            absolute_path=str(absolute_path),
            language=language,
            imports=[],
            functions=[],
            classes=[],
            calls=[],
            parse_errors=[err],
        )
