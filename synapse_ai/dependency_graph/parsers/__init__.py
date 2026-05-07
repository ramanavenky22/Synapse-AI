from __future__ import annotations

from synapse_ai.dependency_graph.parsers.generic_parser import parse_generic_file
from synapse_ai.dependency_graph.parsers.javascript_parser import parse_javascript_file
from synapse_ai.dependency_graph.parsers.python_parser import parse_python_file

__all__ = [
    "parse_python_file",
    "parse_javascript_file",
    "parse_generic_file",
]
