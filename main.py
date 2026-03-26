from __future__ import annotations

import argparse
import json
import sys

from synapse_ai.ingestion.directory_mapper import map_directory_structure, pretty_print_tree
from synapse_ai.ingestion.file_traverser import traverse_repository
from synapse_ai.ingestion.repo_loader import cleanup_temporary_repository, load_repository


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load a repository and index supported source files."
    )
    parser.add_argument(
        "--repo",
        required=True,
        help="Local repository path or GitHub repository URL",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Maximum number of source files to collect. Omit for no limit.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON output for indexed files and summary",
    )
    parser.add_argument(
        "--print-max",
        type=int,
        default=100,
        help="Max number of file paths and directory-tree lines to print. Use 0 for no limit.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_ctx = None

    try:
        repo_ctx = load_repository(args.repo)
        repo_path = repo_ctx.local_path
        directory_tree = map_directory_structure(repo_path)
        source_files, total_scanned = traverse_repository(
            repo_path, max_files=args.max_files
        )

        print_max = args.print_max
        if print_max is not None and print_max <= 0:
            print_max = None

        tree_pretty = pretty_print_tree(directory_tree)
        tree_lines = tree_pretty.splitlines()
        tree_truncated = print_max is not None and len(tree_lines) > print_max
        tree_pretty_out = (
            tree_pretty
            if not tree_truncated
            else "\n".join(tree_lines[:print_max]) + "\n...(truncated)"
        )

        files_truncated = print_max is not None and len(source_files) > print_max
        files_out = source_files if not files_truncated else source_files[:print_max]

        if args.json:
            payload = {
                "repository_path": str(repo_path),
                "total_files_scanned": total_scanned,
                "total_source_files_found": len(source_files),
                "files_printed": len(files_out),
                "files_truncated": bool(files_truncated),
                "files": [file_obj.to_dict() for file_obj in files_out],
                "directory_tree_pretty_lines": len(tree_lines),
                "directory_tree_truncated": bool(tree_truncated),
                "directory_tree": tree_pretty_out,
            }
            print(json.dumps(payload, indent=2))
            return

        print("\n=== Repository Scan Summary ===")
        print(f"Repository path: {repo_path}")
        print(f"Total files scanned: {total_scanned}")
        print(f"Total source files found: {len(source_files)}")

        print("\nFile paths:")
        for file_obj in files_out:
            print(f"- {file_obj.relative_path}")

        print("\nDirectory tree:")
        print(tree_pretty_out)
    except (FileNotFoundError, NotADirectoryError, RuntimeError, ValueError) as exc:
        print(f"[error] {exc}")
        sys.exit(1)
    finally:
        if repo_ctx is not None:
            cleanup_temporary_repository(repo_ctx)


if __name__ == "__main__":
    main()
