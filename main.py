from __future__ import annotations

import argparse
from collections import Counter
import json
import sys
from pathlib import Path

from synapse_ai.dependency_graph.graph_builder import (
    build_dependency_graph,
    save_dependency_graph,
)
from synapse_ai.dependency_graph.import_resolver import (
    resolve_all_imports,
    save_resolved_dependencies,
)
from synapse_ai.dependency_graph.parser_registry import parse_file_by_extension
from synapse_ai.ingestion.directory_mapper import pretty_print_tree
from synapse_ai.ingestion.pipeline import build_repository_manifest
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
    parser.add_argument(
        "--manifest-out",
        default=None,
        help="Optional output path to save the generated manifest JSON.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_ctx = None

    try:
        repo_ctx = load_repository(args.repo)
        manifest = build_repository_manifest(
            repo_ctx=repo_ctx,
            output_path=args.manifest_out,
            max_files=args.max_files,
            include_directory_tree=True,
        )
        repo_path = manifest["repo_root"]
        source_files = manifest["source_files"]
        repo_root = Path(manifest["repo_root"])
        total_scanned = manifest["total_scanned"]

        parsed_files: list[dict] = []
        language_counts: Counter[str] = Counter()
        total_parse_errors = 0

        for file_info in source_files:
            absolute_raw = file_info.get("absolute_path")
            if not absolute_raw:
                continue

            absolute_path = Path(str(absolute_raw)).expanduser()
            if not absolute_path.is_file():
                continue

            extension = file_info.get("extension")
            parsed = parse_file_by_extension(absolute_path, repo_root, extension)
            parsed_dict = parsed.to_dict()
            parsed_files.append(parsed_dict)
            language_counts[parsed.language] += 1
            total_parse_errors += len(parsed.parse_errors)

        output_dir = Path("output")
        output_dir.mkdir(parents=True, exist_ok=True)
        parsed_output_path = output_dir / "parsed_files.json"
        parsed_output_path.write_text(json.dumps(parsed_files, indent=2), encoding="utf-8")
        resolved_dependencies = resolve_all_imports(
            manifest=manifest,
            parsed_files=parsed_files,
        )
        resolved_output_path = output_dir / "resolved_dependencies.json"
        save_resolved_dependencies(resolved_dependencies, resolved_output_path)
        internal_resolved_count = sum(
            1 for dep in resolved_dependencies if dep.get("resolution_status") == "resolved"
        )
        external_or_unresolved_count = len(resolved_dependencies) - internal_resolved_count
        dependency_graph = build_dependency_graph(
            manifest=manifest,
            parsed_files=parsed_files,
            resolved_dependencies=resolved_dependencies,
        )
        graph_output_path = output_dir / "dependency_graph.json"
        save_dependency_graph(dependency_graph, graph_output_path)

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

        print("\n=== Layer 2 Parser Summary ===")
        print(f"Total parsed files: {len(parsed_files)}")
        print(f"Total parse errors: {total_parse_errors}")
        print(f"Language counts: {dict(sorted(language_counts.items()))}")
        print(f"Output file: {parsed_output_path.resolve(strict=False)}")
        print(f"Total dependency records: {len(resolved_dependencies)}")
        print(f"Internal resolved: {internal_resolved_count}")
        print(f"External/unresolved: {external_or_unresolved_count}")
        print(f"Resolved dependencies file: {resolved_output_path.resolve(strict=False)}")
        print(f"Dependency graph file: {graph_output_path.resolve(strict=False)}")
        print(f"Graph total nodes: {dependency_graph['summary']['total_nodes']}")
        print(f"Graph total edges: {dependency_graph['summary']['total_edges']}")
    except (FileNotFoundError, NotADirectoryError, RuntimeError, ValueError) as exc:
        print(f"[error] {exc}")
        sys.exit(1)
    finally:
        if repo_ctx is not None:
            cleanup_temporary_repository(repo_ctx)


if __name__ == "__main__":
    main()
