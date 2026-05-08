#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Repo root: .../Synapse-AI (parent of synapse_ai package)
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from synapse_ai.dependency_graph.parser_registry import parse_file_by_extension


def _write_json(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def run_single_file_test(
    *,
    single_path: Path,
    repo_root: Path,
    out_path: Path,
) -> bool:
    if not single_path.is_file():
        print(f"[single] skip: file not found: {single_path}", file=sys.stderr)
        return False
    parsed = parse_file_by_extension(single_path, repo_root)
    blob = parsed.to_dict()
    _write_json(out_path, blob)

    print(f"[single] wrote {out_path}")
    print(json.dumps(blob, indent=2))
    return True


def run_manifest_test(
    *,
    manifest_path: Path,
    out_path: Path,
) -> int:
    if not manifest_path.is_file():
        print(f"[manifest] skip: not found: {manifest_path}", file=sys.stderr)
        return 0

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[manifest] failed to read JSON: {exc}", file=sys.stderr)
        return 0

    repo_root_raw = manifest.get("repo_root")
    if not repo_root_raw:
        print("[manifest] skip: manifest missing 'repo_root'", file=sys.stderr)
        return 0

    repo_root = Path(repo_root_raw).expanduser().resolve(strict=False)
    source_files = manifest.get("source_files")
    if not isinstance(source_files, list):
        print("[manifest] skip: 'source_files' not a list", file=sys.stderr)
        return 0

    results: list[dict] = []
    errors: list[str] = []

    for i, entry in enumerate(source_files):
        if not isinstance(entry, dict):
            errors.append(f"index {i}: entry is not an object, skipped")
            continue

        abs_str = entry.get("absolute_path")
        if not abs_str:
            errors.append(f"index {i}: missing absolute_path, skipped")
            continue

        file_path = Path(abs_str).expanduser()
        if not file_path.is_file():
            errors.append(f"index {i}: not a file: {file_path}")
            continue

        ext = entry.get("extension")
        if ext is not None and not isinstance(ext, str):
            ext = str(ext)

        try:
            parsed = parse_file_by_extension(file_path, repo_root, ext)
            results.append(parsed.to_dict())
        except OSError as exc:
            errors.append(f"index {i}: parse failed {file_path}: {exc}")

    payload = {
        "repo_root": str(repo_root),
        "manifest_path": str(manifest_path),
        "parsed_count": len(results),
        "errors": errors,
        "parsed_files": results,
    }
    _write_json(out_path, payload)

    print(f"[manifest] wrote {out_path}")
    print(f"[manifest] total parsed: {len(results)}")
    if errors:
        print(f"[manifest] skipped/failed rows: {len(errors)}", file=sys.stderr)
        for line in errors[:20]:
            print(f"  - {line}", file=sys.stderr)
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more", file=sys.stderr)

    return len(results)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Smoke-test Layer 2 parser routing (registry + Python AST)."
    )
    parser.add_argument(
        "--single",
        type=Path,
        default=REPO_ROOT / "test_repo" / "src" / "main.py",
        help="Python file to parse in single-file mode.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root for single-file test (default: parent of --single).",
    )
    parser.add_argument(
        "--single-out",
        type=Path,
        default=Path.cwd() / "parsed_single.json",
        help="Output JSON for single-file parse.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path.cwd() / "repo_manifest.json",
        help="Layer 1 manifest JSON path.",
    )
    parser.add_argument(
        "--manifest-out",
        type=Path,
        default=Path.cwd() / "parsed_files.json",
        help="Output JSON for manifest batch parse.",
    )
    parser.add_argument(
        "--skip-single",
        action="store_true",
        help="Skip single-file test.",
    )
    parser.add_argument(
        "--skip-manifest",
        action="store_true",
        help="Skip manifest batch test.",
    )
    args = parser.parse_args()

    if not args.skip_single:
        single = args.single.expanduser().resolve(strict=False)
        repo_root_single = (
            args.repo_root.expanduser().resolve(strict=False)
            if args.repo_root is not None
            else single.parent
        )

        ran = False
        if single.is_file():
            run_single_file_test(
                single_path=single,
                repo_root=repo_root_single,
                out_path=args.single_out.expanduser(),
            )
            ran = True
        else:
            fallback = (
                REPO_ROOT
                / "synapse_ai"
                / "dependency_graph"
                / "parsers"
                / "python_parser.py"
            )
            print(
                f"[single] default path missing ({single}); trying fallback: {fallback}",
                file=sys.stderr,
            )
            if fallback.is_file():
                run_single_file_test(
                    single_path=fallback,
                    repo_root=REPO_ROOT,
                    out_path=args.single_out.expanduser(),
                )
                ran = True

        if not ran:
            print(
                "[single] no sample file ran; provide --single or create test_repo/src/main.py",
                file=sys.stderr,
            )

    if not args.skip_manifest:
        run_manifest_test(
            manifest_path=args.manifest.expanduser(),
            out_path=args.manifest_out.expanduser(),
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
