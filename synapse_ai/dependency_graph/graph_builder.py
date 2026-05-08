from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _add_node(nodes: dict[str, dict[str, Any]], node: dict[str, Any]) -> None:
    node_id = node.get("id")
    if not isinstance(node_id, str) or not node_id:
        return
    if node_id not in nodes:
        nodes[node_id] = node


def _edge_key(edge: dict[str, Any]) -> tuple[Any, ...]:
    return (
        edge.get("source"),
        edge.get("target"),
        edge.get("type"),
        edge.get("line_no"),
    )


def build_dependency_graph(
    manifest: dict,
    parsed_files: list[dict],
    resolved_dependencies: list[dict],
) -> dict:
    """
    Build a deterministic dependency graph JSON (dict/list), no NetworkX.
    """
    _ = manifest  # reserved for future enrichment; current build uses parsed/dependency payloads.

    nodes_by_id: dict[str, dict[str, Any]] = {}
    edges_by_key: dict[tuple[Any, ...], dict[str, Any]] = {}

    # File/function/class nodes + definition edges.
    for parsed in parsed_files:
        if not isinstance(parsed, dict):
            continue
        file_id = parsed.get("file_path")
        if not isinstance(file_id, str) or not file_id:
            continue

        language = parsed.get("language") if isinstance(parsed.get("language"), str) else None
        _add_node(
            nodes_by_id,
            {"id": file_id, "type": "file", "language": language or "unknown"},
        )

        for fn in parsed.get("functions", []) or []:
            if not isinstance(fn, dict):
                continue
            qname = fn.get("qualified_name")
            if not isinstance(qname, str) or not qname:
                continue
            fn_id = f"{file_id}::{qname}"
            _add_node(
                nodes_by_id,
                {
                    "id": fn_id,
                    "type": "function",
                    "name": fn.get("name"),
                    "qualified_name": qname,
                    "line_start": fn.get("line_start"),
                    "line_end": fn.get("line_end"),
                },
            )
            edge = {"source": file_id, "target": fn_id, "type": "defines_function"}
            edges_by_key[_edge_key(edge)] = edge

        for cls in parsed.get("classes", []) or []:
            if not isinstance(cls, dict):
                continue
            qname = cls.get("qualified_name")
            if not isinstance(qname, str) or not qname:
                continue
            cls_id = f"{file_id}::{qname}"
            _add_node(
                nodes_by_id,
                {
                    "id": cls_id,
                    "type": "class",
                    "name": cls.get("name"),
                    "qualified_name": qname,
                    "line_start": cls.get("line_start"),
                    "line_end": cls.get("line_end"),
                },
            )
            edge = {"source": file_id, "target": cls_id, "type": "defines_class"}
            edges_by_key[_edge_key(edge)] = edge

        for call in parsed.get("calls", []) or []:
            if not isinstance(call, dict):
                continue
            call_name = call.get("name")
            if not isinstance(call_name, str) or not call_name:
                continue
            caller = call.get("caller")
            if isinstance(caller, str) and caller:
                source = f"{file_id}::{caller}"
            else:
                source = file_id
            target = f"symbol::{call_name}"
            _add_node(nodes_by_id, {"id": target, "type": "unresolved_symbol"})
            edge = {
                "source": source,
                "target": target,
                "type": "calls_unresolved",
                "line_no": call.get("line_no"),
            }
            edges_by_key[_edge_key(edge)] = edge

    # Import edges + external nodes.
    for dep in resolved_dependencies:
        if not isinstance(dep, dict):
            continue
        source_file = dep.get("source_file")
        if not isinstance(source_file, str) or not source_file:
            continue

        is_external = bool(dep.get("is_external", False))
        target_file = dep.get("target_file")
        line_no = dep.get("line_no")

        common_meta = {
            "import_module": dep.get("import_module"),
            "import_name": dep.get("import_name"),
            "import_type": dep.get("import_type"),
            "line_no": line_no,
            "resolution_status": dep.get("resolution_status"),
        }

        if (not is_external) and isinstance(target_file, str) and target_file:
            edge = {
                "source": source_file,
                "target": target_file,
                "type": "imports",
                **common_meta,
            }
            edges_by_key[_edge_key(edge)] = edge
        else:
            import_module = dep.get("import_module")
            ext_mod = str(import_module) if import_module is not None else "unknown"
            ext_id = f"external::{ext_mod}"
            _add_node(nodes_by_id, {"id": ext_id, "type": "external_module"})
            edge = {
                "source": source_file,
                "target": ext_id,
                "type": "imports_external",
                **common_meta,
            }
            edges_by_key[_edge_key(edge)] = edge

    nodes = sorted(nodes_by_id.values(), key=lambda n: (str(n.get("type", "")), str(n["id"])))
    edges = sorted(
        edges_by_key.values(),
        key=lambda e: (
            str(e.get("type", "")),
            str(e.get("source", "")),
            str(e.get("target", "")),
            -1 if e.get("line_no") is None else int(e.get("line_no")),
        ),
    )

    summary = {
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "file_nodes": sum(1 for n in nodes if n.get("type") == "file"),
        "function_nodes": sum(1 for n in nodes if n.get("type") == "function"),
        "class_nodes": sum(1 for n in nodes if n.get("type") == "class"),
        "external_nodes": sum(1 for n in nodes if n.get("type") == "external_module"),
        "import_edges": sum(
            1 for e in edges if e.get("type") in {"imports", "imports_external"}
        ),
        "definition_edges": sum(
            1 for e in edges if e.get("type") in {"defines_function", "defines_class"}
        ),
        "call_edges": sum(1 for e in edges if e.get("type") == "calls_unresolved"),
    }

    return {"nodes": nodes, "edges": edges, "summary": summary}


def save_dependency_graph(graph: dict, output_path: Path) -> Path:
    """
    Save dependency graph JSON to disk with deterministic pretty formatting.
    """
    out = Path(output_path).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(graph, indent=2), encoding="utf-8")
    return out
