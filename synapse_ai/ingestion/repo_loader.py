from __future__ import annotations

from dataclasses import dataclass
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse


def _is_github_url(repo_input: str) -> bool:
    if repo_input.startswith("git@github.com:"):
        return True

    parsed = urlparse(repo_input)
    return parsed.scheme in {"http", "https"} and parsed.netloc.lower() == "github.com"


def _looks_like_url(repo_input: str) -> bool:
    parsed = urlparse(repo_input)
    return bool(parsed.scheme and parsed.netloc)


@dataclass
class RepositoryContext:
    local_path: Path
    is_temporary: bool = False
    temp_root: Path | None = None


def _clone_github_repo(repo_url: str) -> RepositoryContext:
    temp_dir = Path(tempfile.mkdtemp(prefix="synapse_ai_repo_"))
    clone_target = temp_dir / "repo"

    if shutil.which("git") is None:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise RuntimeError("git is not installed or not available in PATH.")

    print(f"[repo_loader] Cloning GitHub repository: {repo_url}")
    try:
        subprocess.run(
            ["git", "clone", repo_url, str(clone_target)],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise RuntimeError(
            f"Failed to clone repository '{repo_url}': {exc.stderr.strip() or exc}"
        ) from exc

    print(f"[repo_loader] Repository cloned to: {clone_target}")
    return RepositoryContext(local_path=clone_target, is_temporary=True, temp_root=temp_dir)


def load_repository(repo_input: str) -> RepositoryContext:
    """
    Load a repository from a local path or a GitHub URL.
    Returns context containing local filesystem path and temp metadata.
    """
    if _is_github_url(repo_input):
        return _clone_github_repo(repo_input)

    if _looks_like_url(repo_input):
        raise ValueError(
            "Invalid repository URL. Only GitHub repository URLs are supported."
        )

    local_path = Path(repo_input).expanduser().resolve()
    if not local_path.exists():
        raise FileNotFoundError(f"Local path does not exist: {local_path}")
    if not local_path.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {local_path}")

    print(f"[repo_loader] Using local repository path: {local_path}")
    return RepositoryContext(local_path=local_path)


def cleanup_temporary_repository(repo_ctx: RepositoryContext) -> None:
    if not repo_ctx.is_temporary or repo_ctx.temp_root is None:
        return
    print(f"[repo_loader] Cleaning up temporary repository: {repo_ctx.temp_root}")
    shutil.rmtree(repo_ctx.temp_root, ignore_errors=True)
