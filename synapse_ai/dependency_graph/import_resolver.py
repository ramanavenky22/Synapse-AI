from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _module_key_from_path(path_str: str) -> str:
    p = Path(path_str)
    no_suffix = p.with_suffix("")
    parts = list(no_suffix.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def build_module_index(manifest: dict) -> dict[str, str]:
    """
    Build module-name -> repository file path index from Layer 1 source files.
    """
    source_files = manifest.get("source_files", [])
    if not isinstance(source_files, list):
        return {}

    index: dict[str, str] = {}
    for file_info in source_files:
        if not isinstance(file_info, dict):
            continue
        original_path = file_info.get("original_path")
        if not isinstance(original_path, str) or not original_path:
            continue

        key = _module_key_from_path(original_path)
        if key:
            index[key] = original_path
    return index


def resolve_import(
    source_file: str, import_record: dict, module_index: dict[str, str]
) -> dict[str, Any]:
    """
    Resolve one parsed import record to an internal target file when possible.
    """
    module = import_record.get("module")
    name = import_record.get("name")
    import_type = import_record.get("import_type")
    line_no = import_record.get("line_no")

    module_str = str(module) if module is not None else ""
    lookup_key = module_str.strip().lstrip(".")
    target_file = module_index.get(lookup_key)

    if target_file is not None:
        return {
            "source_file": source_file,
            "target_file": target_file,
            "import_module": module_str,
            "import_name": name,
            "import_type": import_type,
            "line_no": line_no,
            "is_external": False,
            "resolution_status": "resolved",
        }

    return {
        "source_file": source_file,
        "target_file": None,
        "import_module": module_str,
        "import_name": name,
        "import_type": import_type,
        "line_no": line_no,
        "is_external": True,
        "resolution_status": "external_or_unresolved",
    }


def resolve_all_imports(manifest: dict, parsed_files: list[dict]) -> list[dict]:
    """
    Resolve imports for all parsed files to internal targets where possible.
    """
    module_index = build_module_index(manifest)
    dependencies: list[dict] = []

    for parsed in parsed_files:
        if not isinstance(parsed, dict):
            continue
        source_file = parsed.get("file_path")
        if not isinstance(source_file, str) or not source_file:
            continue

        imports = parsed.get("imports", [])
        if not isinstance(imports, list):
            continue

        for import_record in imports:
            if not isinstance(import_record, dict):
                continue
            dependencies.append(resolve_import(source_file, import_record, module_index))

    return dependencies


def save_resolved_dependencies(dependencies: list[dict], output_path: Path) -> Path:
    """
    Persist resolved dependency records as pretty JSON.
    """
    out = Path(output_path).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dependencies, indent=2), encoding="utf-8")
    return out
