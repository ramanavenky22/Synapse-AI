from __future__ import annotations

import argparse
import json
import sys

from synapse_ai.ingestion.directory_mapper import pretty_print_tree
from synapse_ai.ingestion.pipeline import build_repository_manifest


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
    parser.add_argument(
        "--manifest-out",
        default=None,
        help="Optional output path to save the generated manifest JSON.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        manifest = build_repository_manifest(
            repo_input=args.repo,
            output_path=args.manifest_out,
            max_files=args.max_files,
            include_directory_tree=True,
        )
        repo_path = manifest["repo_root"]
        source_files = manifest["source_files"]
        total_scanned = manifest["total_scanned"]

        print_max = args.print_max
        if print_max is not None and print_max <= 0:
            print_max = None

        directory_tree = manifest["directory_tree"]
        tree_pretty = pretty_print_tree(directory_tree) if directory_tree else ""
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
            print(json.dumps(manifest, indent=2))
            return

        print("\n=== Repository Scan Summary ===")
        print(f"Repository path: {repo_path}")
        print(f"Total files scanned: {total_scanned}")
        print(f"Total source files found: {len(source_files)}")
        print(
            f"Unique physical files (by inode): {manifest['total_unique_files']} | "
            f"Duplicate paths (same inode): {manifest['total_duplicate_files']}"
        )

        print("\nFile paths:")
        for file_obj in files_out:
            print(f"- {file_obj['original_path']}")

        print("\nDirectory tree:")
        print(tree_pretty_out)
    except (FileNotFoundError, NotADirectoryError, RuntimeError, ValueError) as exc:
        print(f"[error] {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
