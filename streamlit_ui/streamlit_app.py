from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable

import streamlit as st
import streamlit.components.v1 as components
try:
    import plotly.graph_objects as go
except Exception:  # pragma: no cover - optional UI dependency
    go = None
try:
    from pyvis.network import Network
except Exception:  # pragma: no cover - optional UI dependency
    Network = None

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from synapse_ai.dependency_graph.graph_builder import (  # noqa: E402
    build_dependency_graph,
    save_dependency_graph,
)
from synapse_ai.dependency_graph.import_resolver import (  # noqa: E402
    resolve_all_imports,
    save_resolved_dependencies,
)
from synapse_ai.dependency_graph.parser_registry import parse_file_by_extension  # noqa: E402
from synapse_ai.ingestion.pipeline import build_repository_manifest  # noqa: E402
from synapse_ai.ingestion.repo_loader import (  # noqa: E402
    cleanup_temporary_repository,
    load_repository,
)

_NODE_COLORS = {
    "file": "#7aa5d6",
    "function": "#7fc8a9",
    "class": "#e7be7a",
    "external_module": "#df8f8f",
    "unresolved_symbol": "#b8a5d6",
}

_EDGE_COLORS = {
    "imports": "#aebed0",
    "imports_external": "#d9b3b3",
    "defines_function": "#b7d8c8",
    "defines_class": "#e7d8b1",
    "calls_unresolved": "#d2c7df",
}


def _apply_light_theme_css() -> None:
    """
    Comprehensive light theme that forces all Streamlit components
    (text, inputs, buttons, metrics, tabs, alerts, dataframes) to be
    clearly visible regardless of the user's OS / browser dark mode.
    """
    st.markdown(
        """
        <style>
        :root {
            --sa-bg: #ffffff;
            --sa-bg-soft: #f5f7fb;
            --sa-bg-card: #ffffff;
            --sa-border: #e2e8f0;
            --sa-border-strong: #cbd5e1;
            --sa-text: #0f172a;
            --sa-text-soft: #475569;
            --sa-text-muted: #64748b;
            --sa-primary: #2563eb;
            --sa-primary-hover: #1d4ed8;
            --sa-accent: #0ea5e9;
            --sa-success-bg: #ecfdf5;
            --sa-success-text: #065f46;
            --sa-info-bg: #eff6ff;
            --sa-info-text: #1e3a8a;
            --sa-warn-bg: #fffbeb;
            --sa-warn-text: #92400e;
            --sa-error-bg: #fef2f2;
            --sa-error-text: #991b1b;
        }

        html, body, .stApp, [data-testid="stAppViewContainer"],
        [data-testid="stMain"], section.main, .block-container {
            background: var(--sa-bg) !important;
            color: var(--sa-text) !important;
        }

        [data-testid="stHeader"] {
            background: var(--sa-bg) !important;
            border-bottom: 1px solid var(--sa-border) !important;
        }
        [data-testid="stHeader"] * { color: var(--sa-text) !important; }

        [data-testid="stSidebar"], [data-testid="stSidebar"] > div {
            background: var(--sa-bg-soft) !important;
            border-right: 1px solid var(--sa-border) !important;
        }
        [data-testid="stSidebar"] * { color: var(--sa-text) !important; }

        .block-container {
            padding-top: 5rem !important;
            padding-bottom: 3rem !important;
            max-width: 1400px !important;
        }

        h1, h2, h3, h4, h5, h6,
        .stMarkdown h1, .stMarkdown h2, .stMarkdown h3,
        .stMarkdown h4, .stMarkdown h5, .stMarkdown h6 {
            color: var(--sa-text) !important;
            font-weight: 700 !important;
            letter-spacing: -0.01em !important;
        }
        h1, .stMarkdown h1 { font-size: 2.1rem !important; }
        h2, .stMarkdown h2 { font-size: 1.45rem !important; }
        h3, .stMarkdown h3 { font-size: 1.15rem !important; }

        p, li, span, label, div, .stMarkdown,
        .stMarkdown p, .stMarkdown li, .stMarkdown span {
            color: var(--sa-text) !important;
        }
        small, .stCaption, [data-testid="stCaptionContainer"],
        [data-testid="stCaptionContainer"] * {
            color: var(--sa-text-muted) !important;
        }

        /* Text input */
        .stTextInput > div > div > input,
        .stTextInput input,
        [data-baseweb="input"] input {
            background: #ffffff !important;
            color: var(--sa-text) !important;
            border: 1px solid var(--sa-border-strong) !important;
            border-radius: 8px !important;
            padding: 0.55rem 0.85rem !important;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04) !important;
        }
        .stTextInput input::placeholder { color: var(--sa-text-muted) !important; }
        .stTextInput input:focus,
        .stTextInput > div > div:focus-within {
            border-color: var(--sa-primary) !important;
            box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15) !important;
        }
        [data-baseweb="input"] {
            background: #ffffff !important;
            border-radius: 8px !important;
        }

        /* Selectbox / Multiselect */
        [data-baseweb="select"] > div {
            background: #ffffff !important;
            border: 1px solid var(--sa-border-strong) !important;
            border-radius: 8px !important;
            color: var(--sa-text) !important;
        }
        [data-baseweb="select"] * { color: var(--sa-text) !important; }
        [data-baseweb="tag"] {
            background: #eef2ff !important;
            color: #3730a3 !important;
            border-radius: 6px !important;
        }
        [data-baseweb="tag"] * { color: #3730a3 !important; }
        [data-baseweb="popover"] [role="listbox"] {
            background: #ffffff !important;
            border: 1px solid var(--sa-border) !important;
        }
        [data-baseweb="popover"] [role="option"] { color: var(--sa-text) !important; }
        [data-baseweb="popover"] [role="option"]:hover {
            background: var(--sa-bg-soft) !important;
        }

        /* Slider */
        [data-baseweb="slider"] [role="slider"] {
            background: var(--sa-primary) !important;
            border-color: var(--sa-primary) !important;
        }

        /* Buttons */
        .stButton > button {
            background: var(--sa-primary) !important;
            color: #ffffff !important;
            border: 1px solid var(--sa-primary) !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            padding: 0.55rem 1.1rem !important;
            box-shadow: 0 1px 2px rgba(37, 99, 235, 0.25) !important;
            transition: all 0.15s ease !important;
        }
        .stButton > button:hover {
            background: var(--sa-primary-hover) !important;
            border-color: var(--sa-primary-hover) !important;
            transform: translateY(-1px);
        }
        .stButton > button:focus { box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.25) !important; }
        .stDownloadButton > button {
            background: #ffffff !important;
            color: var(--sa-primary) !important;
            border: 1px solid var(--sa-primary) !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
        }
        .stDownloadButton > button:hover {
            background: #eef4ff !important;
        }

        /* Metric cards */
        [data-testid="stMetric"] {
            background: var(--sa-bg-card) !important;
            border: 1px solid var(--sa-border) !important;
            border-radius: 12px !important;
            padding: 1rem 1.1rem !important;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04) !important;
        }
        [data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * {
            color: var(--sa-text-muted) !important;
            font-weight: 500 !important;
        }
        [data-testid="stMetricValue"], [data-testid="stMetricValue"] * {
            color: var(--sa-text) !important;
            font-weight: 700 !important;
        }

        /* Pill-tab radio (used for the main section nav) */
        .sa-pill-tabs [role="radiogroup"] {
            display: flex !important;
            flex-wrap: wrap !important;
            gap: 0.4rem !important;
            background: #f1f5f9 !important;
            border: 1px solid #e2e8f0 !important;
            border-radius: 12px !important;
            padding: 6px !important;
            margin-bottom: 1rem !important;
        }
        .sa-pill-tabs [role="radiogroup"] > label {
            background: transparent !important;
            border-radius: 8px !important;
            padding: 0.45rem 1rem !important;
            margin: 0 !important;
            cursor: pointer !important;
            transition: background 0.15s ease, color 0.15s ease !important;
        }
        .sa-pill-tabs [role="radiogroup"] > label:hover {
            background: #e2e8f0 !important;
        }
        .sa-pill-tabs [role="radiogroup"] > label > div:first-child {
            display: none !important;
        }
        .sa-pill-tabs [role="radiogroup"] > label p {
            color: #475569 !important;
            font-weight: 600 !important;
            font-size: 13px !important;
            margin: 0 !important;
        }
        .sa-pill-tabs [role="radiogroup"] > label[data-checked="true"],
        .sa-pill-tabs [role="radiogroup"] > label:has(input:checked) {
            background: #ffffff !important;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08) !important;
            border: 1px solid #e2e8f0 !important;
        }
        .sa-pill-tabs [role="radiogroup"] > label:has(input:checked) p {
            color: #2563eb !important;
        }

        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {
            background: transparent !important;
            border-bottom: 1px solid var(--sa-border) !important;
            gap: 0.25rem !important;
        }
        .stTabs [data-baseweb="tab"] {
            background: transparent !important;
            color: var(--sa-text-muted) !important;
            font-weight: 600 !important;
            padding: 0.6rem 1rem !important;
            border-radius: 8px 8px 0 0 !important;
        }
        .stTabs [data-baseweb="tab"]:hover {
            background: var(--sa-bg-soft) !important;
            color: var(--sa-text) !important;
        }
        .stTabs [aria-selected="true"] {
            color: var(--sa-primary) !important;
            background: #eef4ff !important;
        }
        .stTabs [data-baseweb="tab-highlight"] { background: var(--sa-primary) !important; }
        .stTabs [data-baseweb="tab-panel"] { padding-top: 1rem !important; }

        /* Alerts */
        [data-testid="stAlert"] {
            border-radius: 10px !important;
            border: 1px solid var(--sa-border) !important;
        }
        [data-testid="stAlert"][kind="info"],
        .stAlert[data-baseweb="notification"][data-kind="info"] {
            background: var(--sa-info-bg) !important;
        }
        [data-testid="stAlert"][kind="success"] {
            background: var(--sa-success-bg) !important;
        }
        [data-testid="stAlert"][kind="warning"] {
            background: var(--sa-warn-bg) !important;
        }
        [data-testid="stAlert"][kind="error"] {
            background: var(--sa-error-bg) !important;
        }
        [data-testid="stAlert"] * { color: var(--sa-text) !important; }

        /* Status / expander */
        [data-testid="stStatusWidget"], [data-testid="stExpander"] {
            background: var(--sa-bg-card) !important;
            border: 1px solid var(--sa-border) !important;
            border-radius: 10px !important;
        }
        [data-testid="stStatusWidget"] *, [data-testid="stExpander"] * {
            color: var(--sa-text) !important;
        }

        /* Dataframes */
        [data-testid="stDataFrame"], [data-testid="stTable"] {
            background: var(--sa-bg-card) !important;
            border: 1px solid var(--sa-border) !important;
            border-radius: 10px !important;
        }
        [data-testid="stDataFrame"] * { color: var(--sa-text) !important; }

        /* JSON viewer */
        [data-testid="stJson"] {
            background: var(--sa-bg-soft) !important;
            border: 1px solid var(--sa-border) !important;
            border-radius: 10px !important;
            padding: 0.5rem !important;
        }
        [data-testid="stJson"] * { color: var(--sa-text) !important; }

        /* Checkbox label */
        [data-testid="stCheckbox"] label, [data-testid="stCheckbox"] p {
            color: var(--sa-text) !important;
        }

        /* Card-like wrapper for the graph */
        .sa-graph-card {
            background: var(--sa-bg-card);
            border: 1px solid var(--sa-border);
            border-radius: 12px;
            padding: 0.5rem;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
        }

        /* Scrollbars */
        ::-webkit-scrollbar { width: 10px; height: 10px; }
        ::-webkit-scrollbar-thumb {
            background: #cbd5e1; border-radius: 8px;
        }
        ::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
        ::-webkit-scrollbar-track { background: transparent; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _save_json(payload: Any, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _run_analysis(
    repo_input: str,
    output_dir: Path,
    step: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    def emit(message: str) -> None:
        if step is not None:
            step(message)

    repo_ctx = None
    try:
        repo_ctx = load_repository(repo_input)
        emit("Repository loaded")

        manifest = build_repository_manifest(
            repo_ctx=repo_ctx,
            output_path=output_dir / "repo_manifest.json",
            include_directory_tree=True,
        )
        emit("Manifest generated")

        repo_root = Path(manifest["repo_root"])
        source_files = manifest.get("source_files", [])

        parsed_files: list[dict[str, Any]] = []
        for file_info in source_files:
            if not isinstance(file_info, dict):
                continue
            absolute_raw = file_info.get("absolute_path")
            if not absolute_raw:
                continue
            absolute_path = Path(str(absolute_raw)).expanduser()
            if not absolute_path.is_file():
                continue
            extension = file_info.get("extension")
            parsed = parse_file_by_extension(absolute_path, repo_root, extension)
            parsed_files.append(parsed.to_dict())

        parsed_path = _save_json(parsed_files, output_dir / "parsed_files.json")
        emit("Files parsed")

        resolved_dependencies = resolve_all_imports(
            manifest=manifest,
            parsed_files=parsed_files,
        )
        resolved_path = save_resolved_dependencies(
            resolved_dependencies,
            output_dir / "resolved_dependencies.json",
        )
        emit("Imports resolved")

        dependency_graph = build_dependency_graph(
            manifest=manifest,
            parsed_files=parsed_files,
            resolved_dependencies=resolved_dependencies,
        )
        graph_path = save_dependency_graph(
            dependency_graph,
            output_dir / "dependency_graph.json",
        )
        emit("Dependency graph built")

        return {
            "manifest": manifest,
            "parsed_files": parsed_files,
            "resolved_dependencies": resolved_dependencies,
            "dependency_graph": dependency_graph,
            "paths": {
                "repo_manifest": str((output_dir / "repo_manifest.json").resolve(strict=False)),
                "parsed_files": str(parsed_path.resolve(strict=False)),
                "resolved_dependencies": str(resolved_path.resolve(strict=False)),
                "dependency_graph": str(graph_path.resolve(strict=False)),
            },
        }
    finally:
        if repo_ctx is not None:
            cleanup_temporary_repository(repo_ctx)


def _metric_values(data: dict[str, Any]) -> dict[str, int]:
    parsed_files = data["parsed_files"]
    graph_summary = data["dependency_graph"].get("summary", {})
    resolved = data["resolved_dependencies"]

    total_functions = sum(len(p.get("functions", [])) for p in parsed_files if isinstance(p, dict))
    total_classes = sum(len(p.get("classes", [])) for p in parsed_files if isinstance(p, dict))
    total_parse_errors = sum(len(p.get("parse_errors", [])) for p in parsed_files if isinstance(p, dict))
    external_deps = sum(1 for d in resolved if isinstance(d, dict) and d.get("is_external"))

    return {
        "total_files": len(data["manifest"].get("source_files", [])),
        "functions": total_functions,
        "classes": total_classes,
        "external_dependencies": external_deps,
        "nodes": int(graph_summary.get("total_nodes", 0)),
        "edges": int(graph_summary.get("total_edges", 0)),
        "parse_errors": total_parse_errors,
    }


def _to_graphviz_dot(graph: dict[str, Any], max_edges: int = 300) -> str:
    """
    Convert dependency graph JSON into Graphviz DOT for Streamlit rendering.
    """
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    if not isinstance(nodes, list):
        nodes = []
    if not isinstance(edges, list):
        edges = []

    edges = edges[:max_edges]
    node_ids_in_edges: set[str] = set()
    for e in edges:
        if not isinstance(e, dict):
            continue
        s = e.get("source")
        t = e.get("target")
        if isinstance(s, str):
            node_ids_in_edges.add(s)
        if isinstance(t, str):
            node_ids_in_edges.add(t)

    node_map = {
        n.get("id"): n
        for n in nodes
        if isinstance(n, dict) and isinstance(n.get("id"), str)
    }

    dot_lines = [
        "digraph DependencyGraph {",
        "  rankdir=LR;",
        "  node [shape=box, style=filled, fontname=\"Helvetica\", fontsize=10];",
        "  edge [fontname=\"Helvetica\", fontsize=9, arrowsize=0.8];",
    ]

    for node_id in sorted(node_ids_in_edges):
        node = node_map.get(node_id, {"id": node_id, "type": "unknown"})
        ntype = str(node.get("type", "unknown"))
        fill = _NODE_COLORS.get(ntype, "#eeeeee")
        label = node_id
        if len(label) > 55:
            label = label[:52] + "..."
        safe_id = node_id.replace('"', '\\"')
        safe_label = label.replace('"', '\\"')
        dot_lines.append(
            f'  "{safe_id}" [label="{safe_label}", fillcolor="{fill}"];'
        )

    for e in edges:
        if not isinstance(e, dict):
            continue
        src = e.get("source")
        tgt = e.get("target")
        etype = str(e.get("type", "edge"))
        if not isinstance(src, str) or not isinstance(tgt, str):
            continue
        color = _EDGE_COLORS.get(etype, "#666666")
        safe_src = src.replace('"', '\\"')
        safe_tgt = tgt.replace('"', '\\"')
        safe_etype = etype.replace('"', '\\"')
        dot_lines.append(
            f'  "{safe_src}" -> "{safe_tgt}" [label="{safe_etype}", color="{color}"];'
        )

    dot_lines.append("}")
    return "\n".join(dot_lines)


def _node_xyz_positions(nodes: list[dict[str, Any]]) -> dict[str, tuple[float, float, float]]:
    """
    Deterministic pseudo-3D layout grouped by node type.
    """
    import math

    type_z = {
        "file": 0.0,
        "function": 18.0,
        "class": 12.0,
        "external_module": -12.0,
        "unresolved_symbol": 24.0,
    }
    type_radius = {
        "file": 24.0,
        "function": 36.0,
        "class": 30.0,
        "external_module": 42.0,
        "unresolved_symbol": 50.0,
    }

    groups: dict[str, list[str]] = {}
    for n in nodes:
        node_id = n.get("id")
        ntype = str(n.get("type", "unknown"))
        if isinstance(node_id, str):
            groups.setdefault(ntype, []).append(node_id)
    for ids in groups.values():
        ids.sort()

    pos: dict[str, tuple[float, float, float]] = {}
    golden = 2.399963229728653  # golden angle for spacing

    for ntype, ids in sorted(groups.items()):
        radius = type_radius.get(ntype, 28.0)
        z = type_z.get(ntype, 6.0)
        for i, node_id in enumerate(ids):
            angle = i * golden
            x = radius * math.cos(angle)
            y = radius * math.sin(angle)
            # Slight deterministic wave to reduce overlap.
            zz = z + 3.0 * math.sin(i * 0.7)
            pos[node_id] = (x, y, zz)
    return pos


def _build_3d_graph_figure(
    graph: dict[str, Any],
    max_edges: int = 400,
    allowed_edge_types: set[str] | None = None,
    allowed_node_types: set[str] | None = None,
    show_node_labels: bool = True,
    show_edge_labels: bool = True,
):
    if go is None:
        return None

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    if not isinstance(nodes, list):
        nodes = []
    if not isinstance(edges, list):
        edges = []

    nodes = [n for n in nodes if isinstance(n, dict) and isinstance(n.get("id"), str)]
    if allowed_node_types:
        nodes = [n for n in nodes if str(n.get("type", "")) in allowed_node_types]
    allowed_node_ids = {str(n["id"]) for n in nodes}
    edges = [e for e in edges if isinstance(e, dict)]
    if allowed_edge_types:
        edges = [e for e in edges if str(e.get("type", "")) in allowed_edge_types]
    edges = [
        e
        for e in edges
        if isinstance(e.get("source"), str)
        and isinstance(e.get("target"), str)
        and e["source"] in allowed_node_ids
        and e["target"] in allowed_node_ids
    ]
    edges = edges[:max_edges]

    pos = _node_xyz_positions(nodes)

    edge_x: list[float | None] = []
    edge_y: list[float | None] = []
    edge_z: list[float | None] = []
    edge_label_x: list[float] = []
    edge_label_y: list[float] = []
    edge_label_z: list[float] = []
    edge_label_text: list[str] = []
    for e in edges:
        src = e.get("source")
        tgt = e.get("target")
        if not isinstance(src, str) or not isinstance(tgt, str):
            continue
        if src not in pos or tgt not in pos:
            continue
        x0, y0, z0 = pos[src]
        x1, y1, z1 = pos[tgt]
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]
        edge_z += [z0, z1, None]
        if show_edge_labels:
            edge_label_x.append((x0 + x1) / 2.0)
            edge_label_y.append((y0 + y1) / 2.0)
            edge_label_z.append((z0 + z1) / 2.0)
            etype = str(e.get("type", "edge"))
            edge_label_text.append(etype)

    node_x: list[float] = []
    node_y: list[float] = []
    node_z: list[float] = []
    node_text: list[str] = []
    node_color: list[str] = []
    for n in nodes:
        nid = n["id"]
        x, y, z = pos[nid]
        node_x.append(x)
        node_y.append(y)
        node_z.append(z)
        ntype = str(n.get("type", "unknown"))
        node_color.append(_NODE_COLORS.get(ntype, "#aaaaaa"))
        node_text.append(f"{nid}<br>type={ntype}")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter3d(
            x=edge_x,
            y=edge_y,
            z=edge_z,
            mode="lines",
        line=dict(color="#7f8c8d", width=2),
            hoverinfo="none",
            name="edges",
        )
    )
    fig.add_trace(
        go.Scatter3d(
            x=node_x,
            y=node_y,
            z=node_z,
            mode="markers+text" if show_node_labels else "markers",
            marker=dict(size=7, color=node_color, opacity=0.95),
            text=node_text,
            textposition="top center",
            hoverinfo="text",
            name="nodes",
        )
    )
    if show_edge_labels and edge_label_text:
        fig.add_trace(
            go.Scatter3d(
                x=edge_label_x,
                y=edge_label_y,
                z=edge_label_z,
                mode="text",
                text=edge_label_text,
                textposition="middle center",
                hoverinfo="none",
                name="edge_labels",
            )
        )
    fig.update_layout(
        margin=dict(l=0, r=0, t=20, b=0),
        scene=dict(
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            zaxis=dict(visible=False),
        ),
        showlegend=False,
        height=560,
    )
    return fig


_NODE_STYLE = {
    "file": {
        "shape": "dot",
        "color": "#2563eb",
        "border": "#1e40af",
        "highlight": "#3b82f6",
        "size": 26,
        "font": "#0f172a",
    },
    "function": {
        "shape": "dot",
        "color": "#10b981",
        "border": "#047857",
        "highlight": "#34d399",
        "size": 14,
        "font": "#064e3b",
    },
    "class": {
        "shape": "diamond",
        "color": "#f59e0b",
        "border": "#b45309",
        "highlight": "#fbbf24",
        "size": 18,
        "font": "#7c2d12",
    },
    "external_module": {
        "shape": "hexagon",
        "color": "#ef4444",
        "border": "#b91c1c",
        "highlight": "#f87171",
        "size": 20,
        "font": "#7f1d1d",
    },
    "unresolved_symbol": {
        "shape": "triangle",
        "color": "#a855f7",
        "border": "#7e22ce",
        "highlight": "#c084fc",
        "size": 12,
        "font": "#581c87",
    },
}

_EDGE_STYLE = {
    "imports": {"color": "#3b82f6", "width": 2.0, "dashes": False},
    "imports_external": {"color": "#ef4444", "width": 1.6, "dashes": [6, 4]},
    "defines_function": {"color": "#10b981", "width": 1.2, "dashes": False},
    "defines_class": {"color": "#f59e0b", "width": 1.4, "dashes": False},
    "calls_unresolved": {"color": "#a855f7", "width": 1.0, "dashes": [2, 3]},
}


def _build_pyvis_network_html(
    graph: dict[str, Any],
    max_edges: int = 500,
    allowed_edge_types: set[str] | None = None,
    allowed_node_types: set[str] | None = None,
    show_node_labels: bool = True,
    show_edge_labels: bool = True,
) -> str | None:
    """
    Build a polished, modern interactive dependency graph using Vis.js.
    """
    if Network is None:
        return None

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    if not isinstance(nodes, list):
        nodes = []
    if not isinstance(edges, list):
        edges = []

    nodes = [n for n in nodes if isinstance(n, dict) and isinstance(n.get("id"), str)]
    if allowed_node_types:
        nodes = [n for n in nodes if str(n.get("type", "")) in allowed_node_types]
    allowed_ids = {str(n["id"]) for n in nodes}

    edges = [e for e in edges if isinstance(e, dict)]
    if allowed_edge_types:
        edges = [e for e in edges if str(e.get("type", "")) in allowed_edge_types]
    edges = [
        e
        for e in edges
        if isinstance(e.get("source"), str)
        and isinstance(e.get("target"), str)
        and e["source"] in allowed_ids
        and e["target"] in allowed_ids
    ][:max_edges]

    in_degree: dict[str, int] = {}
    for e in edges:
        tgt = str(e["target"])
        in_degree[tgt] = in_degree.get(tgt, 0) + 1

    net = Network(
        height="720px",
        width="100%",
        bgcolor="#fafbff",
        font_color="#0f172a",
        directed=True,
    )

    net.set_options(
        """
        {
          "nodes": {
            "borderWidth": 2,
            "borderWidthSelected": 3,
            "shadow": {
              "enabled": true,
              "color": "rgba(15, 23, 42, 0.18)",
              "size": 10,
              "x": 0,
              "y": 3
            },
            "font": {
              "size": 12,
              "face": "Inter, -apple-system, Helvetica, Arial",
              "color": "#0f172a",
              "strokeWidth": 3,
              "strokeColor": "#ffffff"
            },
            "scaling": {
              "min": 10,
              "max": 50,
              "label": {
                "enabled": true,
                "min": 10,
                "max": 18
              }
            }
          },
          "edges": {
            "arrows": {
              "to": {
                "enabled": true,
                "scaleFactor": 0.6,
                "type": "arrow"
              }
            },
            "smooth": {
              "enabled": true,
              "type": "continuous",
              "roundness": 0.5
            },
            "color": { "inherit": false, "opacity": 0.85 },
            "shadow": {
              "enabled": false
            },
            "selectionWidth": 2,
            "hoverWidth": 1.5,
            "font": {
              "size": 9,
              "face": "Inter, Helvetica, Arial",
              "color": "#475569",
              "strokeWidth": 4,
              "strokeColor": "#ffffff",
              "align": "middle"
            }
          },
          "interaction": {
            "hover": true,
            "navigationButtons": true,
            "keyboard": true,
            "tooltipDelay": 120,
            "hideEdgesOnDrag": true,
            "multiselect": true
          },
          "physics": {
            "enabled": true,
            "solver": "forceAtlas2Based",
            "forceAtlas2Based": {
              "gravitationalConstant": -65,
              "centralGravity": 0.012,
              "springLength": 140,
              "springConstant": 0.06,
              "damping": 0.55,
              "avoidOverlap": 0.7
            },
            "minVelocity": 0.7,
            "stabilization": {
              "enabled": true,
              "iterations": 220,
              "updateInterval": 25,
              "fit": true
            }
          }
        }
        """
    )

    for n in nodes:
        nid = str(n["id"])
        ntype = str(n.get("type", "unknown"))
        style = _NODE_STYLE.get(ntype, _NODE_STYLE["function"])

        display_label = nid
        if "::" in nid:
            display_label = nid.split("::", 1)[1]
        if "/" in display_label and ntype == "file":
            display_label = display_label.rsplit("/", 1)[-1]
        if display_label.startswith("external::"):
            display_label = display_label.split("::", 1)[1]
        if len(display_label) > 32:
            display_label = display_label[:29] + "..."

        importance = in_degree.get(nid, 0)
        size = style["size"] + min(importance * 1.5, 18)

        tooltip = (
            f"<div style='font-family:Inter,Arial;padding:6px 8px;"
            f"min-width:180px;color:#0f172a;'>"
            f"<div style='font-weight:700;font-size:12px;"
            f"color:{style['border']};margin-bottom:4px;"
            f"text-transform:uppercase;letter-spacing:0.5px;'>{ntype}</div>"
            f"<div style='font-size:11px;color:#334155;"
            f"word-break:break-all;'>{nid}</div>"
            + (
                f"<div style='font-size:10px;color:#64748b;margin-top:4px;'>"
                f"incoming: {importance}</div>"
                if importance > 0
                else ""
            )
            + "</div>"
        )

        net.add_node(
            nid,
            label=display_label if show_node_labels else " ",
            title=tooltip,
            shape=style["shape"],
            size=size,
            color={
                "background": style["color"],
                "border": style["border"],
                "highlight": {
                    "background": style["highlight"],
                    "border": style["border"],
                },
                "hover": {
                    "background": style["highlight"],
                    "border": style["border"],
                },
            },
            font={
                "color": style["font"],
                "size": 12,
                "face": "Inter, Helvetica, Arial",
                "strokeWidth": 3,
                "strokeColor": "#ffffff",
            },
        )

    for e in edges:
        src = str(e["source"])
        tgt = str(e["target"])
        etype = str(e.get("type", "edge"))
        style = _EDGE_STYLE.get(etype, {"color": "#94a3b8", "width": 1.0, "dashes": False})

        line_no = e.get("line_no")
        tooltip = (
            f"<div style='font-family:Inter,Arial;padding:6px 8px;'>"
            f"<div style='font-weight:600;font-size:11px;color:{style['color']};'>"
            f"{etype}</div>"
            f"<div style='font-size:10px;color:#334155;margin-top:2px;'>"
            f"{src} -> {tgt}</div>"
            + (
                f"<div style='font-size:10px;color:#64748b;'>line {line_no}</div>"
                if line_no
                else ""
            )
            + "</div>"
        )

        edge_kwargs = {
            "title": tooltip,
            "color": style["color"],
            "width": style["width"],
        }
        if style["dashes"]:
            edge_kwargs["dashes"] = style["dashes"]
        if show_edge_labels:
            edge_kwargs["label"] = etype
            edge_kwargs["font"] = {
                "size": 9,
                "color": style["color"],
                "face": "Inter, Helvetica, Arial",
                "strokeWidth": 4,
                "strokeColor": "#ffffff",
                "align": "middle",
            }

        net.add_edge(src, tgt, **edge_kwargs)

    html = net.generate_html(notebook=False)

    legend_items = [
        ("Files", "#2563eb", "circle"),
        ("Functions", "#10b981", "circle"),
        ("Classes", "#f59e0b", "diamond"),
        ("External", "#ef4444", "hexagon"),
        ("Unresolved", "#a855f7", "triangle"),
    ]
    legend_html_parts = [
        '<div style="position:absolute;top:12px;left:12px;z-index:50;'
        "background:rgba(255,255,255,0.92);backdrop-filter:blur(8px);"
        "border:1px solid #e2e8f0;border-radius:10px;padding:10px 12px;"
        "box-shadow:0 4px 12px rgba(15,23,42,0.06);"
        'font-family:Inter,Helvetica,Arial;font-size:11px;color:#0f172a;">'
        '<div style="font-weight:700;font-size:10px;text-transform:uppercase;'
        'letter-spacing:0.5px;color:#64748b;margin-bottom:6px;">Legend</div>'
    ]
    for label, color, _shape in legend_items:
        legend_html_parts.append(
            '<div style="display:flex;align-items:center;gap:8px;margin:3px 0;">'
            f'<div style="width:10px;height:10px;border-radius:50%;'
            f'background:{color};box-shadow:0 1px 2px rgba(0,0,0,0.15);"></div>'
            f'<span style="color:#334155;">{label}</span>'
            "</div>"
        )
    legend_html_parts.append("</div>")
    legend_html = "".join(legend_html_parts)

    bg_overlay = (
        '<div style="position:absolute;inset:0;pointer-events:none;'
        "background:radial-gradient(circle at 20% 10%,rgba(37,99,235,0.06),transparent 50%),"
        "radial-gradient(circle at 80% 90%,rgba(16,185,129,0.05),transparent 50%);"
        'z-index:1;"></div>'
    )

    wrapper_open = (
        '<div style="position:relative;width:100%;height:720px;'
        "background:linear-gradient(135deg,#fafbff 0%,#f3f6fb 100%);"
        "border-radius:12px;overflow:hidden;"
        'border:1px solid #e2e8f0;">'
    )
    wrapper_close = "</div>"

    if "<body>" in html:
        html = html.replace(
            "<body>",
            f"<body>{wrapper_open}{bg_overlay}{legend_html}",
            1,
        )
        html = html.replace("</body>", f"{wrapper_close}</body>", 1)
    else:
        html = wrapper_open + bg_overlay + legend_html + html + wrapper_close

    return html


_LANG_COLORS = {
    "python": "#3b82f6",
    "javascript": "#f59e0b",
    "typescript": "#0ea5e9",
    "java": "#ef4444",
    "go": "#10b981",
    "rust": "#a855f7",
    "c": "#64748b",
    "cpp": "#475569",
    "csharp": "#7c3aed",
    "ruby": "#e11d48",
    "php": "#6366f1",
    "shell": "#0f766e",
    "sql": "#db2777",
    "html": "#f97316",
    "css": "#06b6d4",
    "yaml": "#eab308",
    "json": "#84cc16",
    "markdown": "#94a3b8",
    "unknown": "#94a3b8",
    "generic": "#94a3b8",
}


def _section_header(title: str, subtitle: str | None = None, icon: str = "") -> None:
    """Render a styled section header above tab content."""
    sub_html = (
        f'<div style="font-size:12px;color:#64748b;margin-top:2px;">{subtitle}</div>'
        if subtitle
        else ""
    )
    icon_html = (
        f'<span style="font-size:14px;">{icon}</span>' if icon else ""
    )
    html = (
        '<div style="display:flex;align-items:flex-start;gap:8px;'
        "margin:1.1rem 0 0.6rem 0;padding-bottom:0.5rem;"
        'border-bottom:1px solid #e2e8f0;">'
        '<div style="display:flex;align-items:center;gap:8px;">'
        f"{icon_html}"
        "<div>"
        '<div style="font-size:14px;font-weight:700;color:#0f172a;'
        f'letter-spacing:-0.005em;">{title}</div>'
        f"{sub_html}"
        "</div></div></div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def _stat_chip(label: str, value: int | str, color: str = "#3b82f6") -> str:
    """Inline HTML for a small statistic chip."""
    return (
        f'<span style="display:inline-flex;align-items:center;gap:6px;'
        f"background:#ffffff;border:1px solid #e2e8f0;border-radius:999px;"
        f'padding:4px 10px;margin:2px 4px 2px 0;font-size:11px;color:#334155;">'
        f'<span style="width:7px;height:7px;border-radius:50%;background:{color};"></span>'
        f'<span style="color:#64748b;">{label}</span>'
        f'<strong style="color:#0f172a;">{value}</strong>'
        f"</span>"
    )


def _render_language_distribution(parsed_files: list[dict[str, Any]]) -> None:
    """Pretty horizontal bars for language counts."""
    counts: Counter[str] = Counter()
    for p in parsed_files:
        if isinstance(p, dict):
            counts[str(p.get("language", "unknown"))] += 1

    if not counts:
        st.info("No language data available.")
        return

    total = sum(counts.values())
    rows = counts.most_common()
    parts = ['<div style="display:flex;flex-direction:column;gap:8px;">']
    for lang, n in rows:
        pct = (n / total * 100) if total else 0
        color = _LANG_COLORS.get(lang.lower(), "#94a3b8")
        parts.append(
            f'<div style="display:flex;align-items:center;gap:10px;">'
            f'<div style="width:120px;font-size:12px;font-weight:600;'
            f'color:#0f172a;text-transform:capitalize;">{lang}</div>'
            f'<div style="flex:1;background:#f1f5f9;border-radius:8px;'
            f'height:10px;overflow:hidden;">'
            f'<div style="width:{pct:.1f}%;height:100%;background:{color};'
            f'border-radius:8px;"></div></div>'
            f'<div style="min-width:90px;text-align:right;font-size:11px;'
            f'color:#475569;"><strong style="color:#0f172a;">{n}</strong>'
            f' files <span style="color:#94a3b8;">({pct:.0f}%)</span></div>'
            f"</div>"
        )
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def _render_extension_chips(ext_summary: dict[str, Any]) -> None:
    if not ext_summary:
        st.info("No extension data available.")
        return
    items = sorted(ext_summary.items(), key=lambda kv: -int(kv[1]))
    chips = "".join(
        _stat_chip(ext or "(none)", count, "#0ea5e9") for ext, count in items
    )
    st.markdown(
        f'<div style="display:flex;flex-wrap:wrap;gap:2px;">{chips}</div>',
        unsafe_allow_html=True,
    )


def _render_graph_summary_cards(summary: dict[str, Any]) -> None:
    """Replace the raw JSON dump with grouped metric cards."""
    if not summary:
        st.info("No graph summary available.")
        return

    groups = [
        ("Nodes", "#2563eb", [
            ("Total", "total_nodes"),
            ("Files", "file_nodes"),
            ("Functions", "function_nodes"),
            ("Classes", "class_nodes"),
            ("External", "external_nodes"),
        ]),
        ("Edges", "#10b981", [
            ("Total", "total_edges"),
            ("Imports", "import_edges"),
            ("Definitions", "definition_edges"),
            ("Calls", "call_edges"),
        ]),
    ]

    parts = ['<div style="display:flex;flex-direction:column;gap:14px;">']
    for title, accent, fields in groups:
        cards = []
        for label, key in fields:
            value = summary.get(key, 0)
            cards.append(
                f'<div style="flex:1;min-width:120px;background:#ffffff;'
                f'border:1px solid #e2e8f0;border-left:3px solid {accent};'
                f'border-radius:10px;padding:10px 12px;">'
                f'<div style="font-size:10px;color:#64748b;text-transform:uppercase;'
                f'letter-spacing:0.6px;font-weight:600;">{label}</div>'
                f'<div style="font-size:20px;font-weight:700;color:#0f172a;'
                f'margin-top:2px;">{value}</div></div>'
            )
        parts.append(
            f'<div><div style="font-size:11px;color:#64748b;font-weight:700;'
            f'letter-spacing:0.5px;text-transform:uppercase;margin-bottom:6px;">'
            f"{title}</div>"
            f'<div style="display:flex;flex-wrap:wrap;gap:8px;">{"".join(cards)}</div>'
            f"</div>"
        )
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def _render_top_list(
    title: str,
    items: list[tuple[str, int]],
    color: str,
    empty_text: str = "No data",
    limit: int = 8,
) -> None:
    """Render a ranked list (e.g. top imported files / top external libs)."""
    items = items[:limit]
    if not items:
        st.markdown(
            f'<div style="font-size:12px;color:#94a3b8;'
            f'padding:8px 4px;">{empty_text}</div>',
            unsafe_allow_html=True,
        )
        return

    max_v = max(v for _, v in items) or 1
    rows = []
    for i, (name, v) in enumerate(items, start=1):
        pct = v / max_v * 100
        display_name = name if len(name) <= 38 else name[:35] + "..."
        rows.append(
            f'<div style="display:flex;align-items:center;gap:10px;'
            f"padding:6px 0;border-bottom:1px dashed #f1f5f9;\">"
            f'<div style="width:22px;font-size:11px;color:#94a3b8;'
            f'font-weight:700;">#{i}</div>'
            f'<div style="flex:1;min-width:0;">'
            f'<div style="font-size:12px;color:#0f172a;font-weight:600;'
            f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">'
            f'{display_name}</div>'
            f'<div style="margin-top:4px;background:#f1f5f9;height:5px;'
            f'border-radius:6px;overflow:hidden;">'
            f'<div style="width:{pct:.0f}%;height:100%;background:{color};'
            f'border-radius:6px;"></div></div></div>'
            f'<div style="min-width:36px;text-align:right;font-size:12px;'
            f'font-weight:700;color:{color};">{v}</div></div>'
        )
    st.markdown(
        f'<div style="background:#ffffff;border:1px solid #e2e8f0;'
        f'border-radius:10px;padding:6px 14px;">'
        f'<div style="font-size:11px;color:#64748b;font-weight:700;'
        f'letter-spacing:0.5px;text-transform:uppercase;padding:8px 0 4px 0;">'
        f"{title}</div>"
        + "".join(rows)
        + "</div>",
        unsafe_allow_html=True,
    )


def _render_file_summary_chips(parsed_file: dict[str, Any]) -> None:
    counts = {
        "Imports": (len(parsed_file.get("imports", [])), "#3b82f6"),
        "Functions": (len(parsed_file.get("functions", [])), "#10b981"),
        "Classes": (len(parsed_file.get("classes", [])), "#f59e0b"),
        "Calls": (len(parsed_file.get("calls", [])), "#a855f7"),
        "Errors": (len(parsed_file.get("parse_errors", [])), "#ef4444"),
    }
    chips = "".join(_stat_chip(label, v, color) for label, (v, color) in counts.items())
    lang = str(parsed_file.get("language", "unknown")).capitalize()
    lang_color = _LANG_COLORS.get(lang.lower(), "#94a3b8")
    lang_chip = (
        f'<span style="display:inline-flex;align-items:center;gap:6px;'
        f'background:{lang_color}1f;border:1px solid {lang_color}55;'
        f'border-radius:999px;padding:4px 10px;margin:2px 4px 2px 0;'
        f'font-size:11px;font-weight:700;color:{lang_color};">'
        f"{lang}</span>"
    )
    st.markdown(
        f'<div style="display:flex;flex-wrap:wrap;align-items:center;'
        f'gap:2px;margin-bottom:0.4rem;">{lang_chip}{chips}</div>',
        unsafe_allow_html=True,
    )


def _render_raw_output_cards(outputs: dict[str, Any]) -> None:
    """Pretty download cards with a tiny preview for each artifact."""
    descriptions = {
        "repo_manifest.json": "Layer 1 ingestion manifest: repo metadata, source files, directory tree.",
        "parsed_files.json": "Layer 2 parser output: imports, functions, classes, calls per file.",
        "resolved_dependencies.json": "Layer 2 import resolution: file-to-file dependency records.",
        "dependency_graph.json": "Final graph: nodes, edges, and summary statistics.",
    }
    accent = {
        "repo_manifest.json": "#2563eb",
        "parsed_files.json": "#10b981",
        "resolved_dependencies.json": "#f59e0b",
        "dependency_graph.json": "#a855f7",
    }

    cols = st.columns(2)
    for i, (filename, payload) in enumerate(outputs.items()):
        blob = json.dumps(payload, indent=2)
        size_kb = len(blob.encode("utf-8")) / 1024
        size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.2f} MB"
        item_count = (
            len(payload) if isinstance(payload, (list, dict)) else 1
        )
        col = cols[i % 2]
        with col:
            st.markdown(
                f'<div style="background:#ffffff;border:1px solid #e2e8f0;'
                f'border-left:3px solid {accent[filename]};border-radius:10px;'
                f'padding:14px 16px;margin-bottom:10px;">'
                f'<div style="display:flex;justify-content:space-between;'
                f'align-items:center;gap:8px;">'
                f'<div style="font-family:JetBrains Mono,Menlo,monospace;'
                f'font-size:12px;font-weight:700;color:#0f172a;">{filename}</div>'
                f'<div style="font-size:10px;color:#64748b;background:#f1f5f9;'
                f'border-radius:999px;padding:2px 8px;">{size_str}</div></div>'
                f'<div style="font-size:11px;color:#64748b;margin:6px 0 8px 0;">'
                f"{descriptions.get(filename, '')}</div>"
                f'<div style="font-size:10px;color:#94a3b8;">'
                f"{item_count} top-level items</div></div>",
                unsafe_allow_html=True,
            )
            st.download_button(
                label=f"Download {filename}",
                data=blob,
                file_name=filename,
                mime="application/json",
                use_container_width=True,
                key=f"dl_{filename}",
            )


def main() -> None:
    st.set_page_config(page_title="Synapse AI", layout="wide")
    _apply_light_theme_css()
    st.markdown(
        '<div style="display:flex;align-items:center;gap:0.75rem;'
        'margin-bottom:0.25rem;">'
        '<div style="width:36px;height:36px;border-radius:10px;'
        "background:linear-gradient(135deg,#2563eb,#0ea5e9);"
        'box-shadow:0 4px 10px rgba(37,99,235,0.25);"></div>'
        "<div>"
        '<div style="font-size:1.85rem;font-weight:800;color:#0f172a;'
        'line-height:1.1;">Synapse AI</div>'
        '<div style="font-size:0.95rem;color:#64748b;">'
        "Repository-Wide Dependency Analyzer</div>"
        "</div></div>"
        '<hr style="border:none;border-top:1px solid #e2e8f0;'
        'margin:1rem 0 1.25rem 0;" />',
        unsafe_allow_html=True,
    )

    if "analysis" not in st.session_state:
        st.session_state.analysis = None
    if "analysis_error" not in st.session_state:
        st.session_state.analysis_error = None
    if "repo_input_value" not in st.session_state:
        st.session_state.repo_input_value = ""

    st.subheader("Repository Input")
    repo_input = st.text_input(
        "GitHub URL or local repository path",
        key="repo_input_value",
    )
    analyze = st.button("Analyze Repository", type="primary")

    if analyze:
        if not repo_input.strip():
            st.error("Please enter a GitHub URL or local repository path.")
        else:
            output_dir = REPO_ROOT / "output"
            with st.status("Analyzing repository...", expanded=True) as status:
                try:
                    st.session_state.analysis = _run_analysis(
                        repo_input=repo_input.strip(),
                        output_dir=output_dir,
                        step=lambda msg: st.write(f"- {msg}"),
                    )
                    st.session_state.analysis_error = None
                except Exception as exc:  # defensive UI boundary
                    st.session_state.analysis = None
                    st.session_state.analysis_error = exc
                    status.update(label="Analysis failed", state="error")
                else:
                    status.update(label="Analysis complete", state="complete")

    if st.session_state.analysis_error is not None:
        st.exception(st.session_state.analysis_error)
        return

    analysis = st.session_state.analysis
    if analysis is None:
        st.info("Enter a repository and click 'Analyze Repository'.")
        return

    metrics = _metric_values(analysis)

    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    c1.metric("Total files", metrics["total_files"])
    c2.metric("Functions", metrics["functions"])
    c3.metric("Classes", metrics["classes"])
    c4.metric("External deps", metrics["external_dependencies"])
    c5.metric("Nodes", metrics["nodes"])
    c6.metric("Edges", metrics["edges"])
    c7.metric("Parse errors", metrics["parse_errors"])

    st.markdown("### Dependency Graph")
    graph = analysis["dependency_graph"]
    st.caption("Interactive dependency graph")
    c_node, c_edge_types = st.columns([1, 1])
    with c_node:
        node_type_options = [
            "file",
            "function",
            "class",
            "external_module",
            "unresolved_symbol",
        ]
        selected_node_types = st.multiselect(
            "Node types",
            options=node_type_options,
            default=["file", "function", "class", "external_module"],
            key="graph_node_types",
        )
    with c_edge_types:
        edge_type_options = [
            "imports",
            "imports_external",
            "defines_function",
            "defines_class",
            "calls_unresolved",
        ]
        selected_edge_types = st.multiselect(
            "Edge types",
            options=edge_type_options,
            default=["imports", "imports_external", "defines_function", "defines_class"],
            key="graph_edge_types",
        )
    edge_limit = 500
    c_flags1, c_flags2, _ = st.columns([2, 2, 4])
    with c_flags1:
        show_node_labels = st.checkbox("Show node labels", value=True, key="show_node_labels")
    with c_flags2:
        show_edge_labels = st.checkbox("Show edge labels", value=True, key="show_edge_labels")

    pyvis_html = _build_pyvis_network_html(
        graph=graph,
        max_edges=edge_limit,
        allowed_edge_types=set(selected_edge_types) if selected_edge_types else None,
        allowed_node_types=set(selected_node_types) if selected_node_types else None,
        show_node_labels=show_node_labels,
        show_edge_labels=show_edge_labels,
    )
    if pyvis_html is not None:
        st.markdown('<div class="sa-graph-card">', unsafe_allow_html=True)
        components.html(pyvis_html, height=720, scrolling=False)
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.warning("Interactive graph requires pyvis. Install with: pip install pyvis")
        fig3d = _build_3d_graph_figure(
            graph,
            max_edges=edge_limit,
            allowed_edge_types=set(selected_edge_types) if selected_edge_types else None,
            allowed_node_types=set(selected_node_types) if selected_node_types else None,
            show_node_labels=show_node_labels,
            show_edge_labels=show_edge_labels,
        )
        if fig3d is not None:
            st.plotly_chart(fig3d, use_container_width=True, theme="streamlit")
        else:
            st.graphviz_chart(_to_graphviz_dot(graph, max_edges=300), use_container_width=True)

    parsed_files_all = [
        p for p in analysis["parsed_files"] if isinstance(p, dict)
    ]
    deps_all = [d for d in analysis["resolved_dependencies"] if isinstance(d, dict)]
    internal_deps = [d for d in deps_all if not d.get("is_external") and d.get("target_file")]
    external_deps = [d for d in deps_all if d.get("is_external")]

    nav_options = ["Overview", "Files", "Dependencies", "Graph", "Raw Output"]
    if "section_nav" not in st.session_state:
        st.session_state.section_nav = nav_options[0]
    st.markdown('<div class="sa-pill-tabs">', unsafe_allow_html=True)
    active_section = st.radio(
        "Section",
        options=nav_options,
        horizontal=True,
        label_visibility="collapsed",
        key="section_nav",
    )
    st.markdown("</div>", unsafe_allow_html=True)

    if active_section == "Overview":
        col_left, col_right = st.columns([1.1, 1])
        with col_left:
            _section_header(
                "Language Distribution",
                "Source files grouped by detected programming language",
            )
            _render_language_distribution(parsed_files_all)

            _section_header(
                "File Extensions",
                "Counts by file extension across the repository",
            )
            _render_extension_chips(analysis["manifest"].get("extension_summary", {}))

        with col_right:
            _section_header(
                "Graph Statistics",
                "Composition of the dependency graph",
            )
            _render_graph_summary_cards(analysis["dependency_graph"].get("summary", {}))

        _section_header(
            "Insights",
            "Most depended-on files and most-used external libraries",
        )
        c_in, c_ex = st.columns(2)
        with c_in:
            in_count: Counter[str] = Counter()
            for d in internal_deps:
                tgt = d.get("target_file")
                if isinstance(tgt, str):
                    in_count[tgt] += 1
            _render_top_list(
                "Top Imported Files (Internal)",
                in_count.most_common(),
                "#2563eb",
                empty_text="No internal imports detected.",
            )
        with c_ex:
            ex_count: Counter[str] = Counter()
            for d in external_deps:
                mod = d.get("import_module")
                if isinstance(mod, str):
                    ex_count[mod] += 1
            _render_top_list(
                "Top External Libraries",
                ex_count.most_common(),
                "#ef4444",
                empty_text="No external dependencies detected.",
            )

    elif active_section == "Files":
        parsed_files = [p for p in parsed_files_all if p.get("file_path")]
        if not parsed_files:
            st.info("No parsed files available.")
        else:
            _section_header(
                "Per-File Inspector",
                "Pick any source file to view its parsed structure",
            )
            file_names = [str(p["file_path"]) for p in parsed_files]
            selected = st.selectbox("Select file", options=file_names, key="files_selectbox")
            selected_file = next(p for p in parsed_files if p["file_path"] == selected)

            _render_file_summary_chips(selected_file)

            sub_imp, sub_fn, sub_cls, sub_call = st.tabs(
                ["Imports", "Functions", "Classes", "Calls"]
            )
            with sub_imp:
                imports = selected_file.get("imports", [])
                if imports:
                    st.dataframe(imports, use_container_width=True, hide_index=True)
                else:
                    st.info("No imports in this file.")
            with sub_fn:
                functions = selected_file.get("functions", [])
                if functions:
                    st.dataframe(functions, use_container_width=True, hide_index=True)
                else:
                    st.info("No functions in this file.")
            with sub_cls:
                classes = selected_file.get("classes", [])
                if classes:
                    st.dataframe(classes, use_container_width=True, hide_index=True)
                else:
                    st.info("No classes in this file.")
            with sub_call:
                calls = selected_file.get("calls", [])
                if calls:
                    st.dataframe(calls, use_container_width=True, hide_index=True)
                else:
                    st.info("No call sites detected in this file.")

    elif active_section == "Dependencies":
        c1, c2, c3 = st.columns(3)
        c1.metric("Total dependencies", len(deps_all))
        c2.metric("Internal", len(internal_deps))
        c3.metric("External / unresolved", len(external_deps))

        sub_int, sub_ext = st.tabs(
            [f"Internal ({len(internal_deps)})", f"External ({len(external_deps)})"]
        )
        with sub_int:
            _section_header(
                "Internal Dependencies",
                "File-to-file imports resolved within the repository",
            )
            if internal_deps:
                st.dataframe(internal_deps, use_container_width=True, hide_index=True)
            else:
                st.info("No internal dependencies detected.")
        with sub_ext:
            _section_header(
                "External / Unresolved Dependencies",
                "Imports that point outside the repository or could not be resolved",
            )
            if external_deps:
                st.dataframe(external_deps, use_container_width=True, hide_index=True)
            else:
                st.info("No external or unresolved dependencies detected.")

    elif active_section == "Graph":
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])

        node_type_counts: Counter[str] = Counter()
        for n in nodes:
            if isinstance(n, dict):
                node_type_counts[str(n.get("type", "unknown"))] += 1
        edge_type_counts: Counter[str] = Counter()
        for e in edges:
            if isinstance(e, dict):
                edge_type_counts[str(e.get("type", "unknown"))] += 1

        _section_header("Composition", "Node and edge types in the graph")
        chips_html = "".join(
            _stat_chip(t, c, _NODE_STYLE.get(t, {"color": "#94a3b8"})["color"])
            for t, c in node_type_counts.most_common()
        ) + "".join(
            _stat_chip(
                t,
                c,
                _EDGE_STYLE.get(t, {"color": "#94a3b8"})["color"],
            )
            for t, c in edge_type_counts.most_common()
        )
        st.markdown(
            f'<div style="display:flex;flex-wrap:wrap;gap:2px;">{chips_html}</div>',
            unsafe_allow_html=True,
        )

        in_deg: Counter[str] = Counter()
        out_deg: Counter[str] = Counter()
        for e in edges:
            if isinstance(e, dict):
                s = e.get("source")
                t = e.get("target")
                if isinstance(s, str):
                    out_deg[s] += 1
                if isinstance(t, str):
                    in_deg[t] += 1

        _section_header(
            "Hubs",
            "Most connected nodes by incoming and outgoing edges",
        )
        c_in, c_out = st.columns(2)
        with c_in:
            _render_top_list(
                "Top Incoming",
                in_deg.most_common(),
                "#2563eb",
                empty_text="No incoming edges.",
            )
        with c_out:
            _render_top_list(
                "Top Outgoing",
                out_deg.most_common(),
                "#10b981",
                empty_text="No outgoing edges.",
            )

        sub_n, sub_e, sub_imp = st.tabs(
            [f"Nodes ({len(nodes)})", f"Edges ({len(edges)})", "File Imports"]
        )
        with sub_n:
            st.dataframe(nodes, use_container_width=True, hide_index=True)
        with sub_e:
            st.dataframe(edges, use_container_width=True, hide_index=True)
        with sub_imp:
            file_import_edges = [
                e for e in edges if isinstance(e, dict) and e.get("type") == "imports"
            ]
            if file_import_edges:
                st.dataframe(file_import_edges, use_container_width=True, hide_index=True)
            else:
                st.info("No file-to-file import edges.")

    elif active_section == "Raw Output":
        _section_header(
            "Generated Artifacts",
            "Download the JSON outputs produced by the pipeline",
        )
        outputs = {
            "repo_manifest.json": analysis["manifest"],
            "parsed_files.json": analysis["parsed_files"],
            "resolved_dependencies.json": analysis["resolved_dependencies"],
            "dependency_graph.json": analysis["dependency_graph"],
        }
        _render_raw_output_cards(outputs)


if __name__ == "__main__":
    main()
