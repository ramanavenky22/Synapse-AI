from __future__ import annotations

import ast
from pathlib import Path

from synapse_ai.dependency_graph.models import (
    CallRecord,
    ClassRecord,
    FunctionRecord,
    ImportRecord,
    ParsedFile,
)


def _get_call_name(node: ast.AST) -> str | None:
    """
    Resolved callee string for typical call forms.

    Examples: ``helper`` -> ``helper``, ``obj.method`` -> ``obj.method``,
    ``self.run`` -> ``self.run``.
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _get_call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Subscript):
        base = _get_call_name(node.value)
        return f"{base}[…]" if base else None
    if isinstance(node, ast.Call):
        inner = _get_call_name(node.func)
        return f"{inner}(…)" if inner else None
    return None


def _import_from_module_str(node: ast.ImportFrom) -> str:
    """Build a textual module specifier for ImportFrom (absolute or relative)."""
    if node.level == 0:
        return node.module or ""

    dots = "." * node.level
    if node.module:
        return f"{dots}{node.module}"
    return dots


def _parsed_file_error_shell(
    *,
    repo_abs: Path,
    absolute_path: Path,
    errors: list[str],
) -> ParsedFile:
    try:
        relative_path = absolute_path.relative_to(repo_abs).as_posix()
    except ValueError:
        relative_path = absolute_path.as_posix()

    return ParsedFile(
        file_path=relative_path,
        absolute_path=str(absolute_path),
        language="python",
        parse_errors=list(errors),
    )


class _PythonAstVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.imports: list[ImportRecord] = []
        self.functions: list[FunctionRecord] = []
        self.classes: list[ClassRecord] = []
        self.calls: list[CallRecord] = []

        self._scope_stack: list[str] = []

    def _qualified(self, name: str) -> str:
        parts = [*self._scope_stack, name]
        return ".".join(parts)

    def _caller(self) -> str | None:
        return ".".join(self._scope_stack) if self._scope_stack else None

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        for alias in node.names:
            self.imports.append(
                ImportRecord(
                    module=alias.name,
                    name=None,
                    alias=alias.asname,
                    import_type="import",
                    line_no=node.lineno,
                    resolved_path=None,
                    is_external=False,
                )
            )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        module_txt = _import_from_module_str(node)
        line = node.lineno
        if any(a.name == "*" for a in node.names):
            self.imports.append(
                ImportRecord(
                    module=module_txt,
                    name="*",
                    alias=None,
                    import_type="from_import",
                    line_no=line,
                    resolved_path=None,
                    is_external=False,
                )
            )
        else:
            for alias in node.names:
                self.imports.append(
                    ImportRecord(
                        module=module_txt,
                        name=alias.name,
                        alias=alias.asname,
                        import_type="from_import",
                        line_no=line,
                        resolved_path=None,
                        is_external=False,
                    )
                )
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        self._visit_def_or_async(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        self._visit_def_or_async(node)

    def _visit_def_or_async(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        line_end = getattr(node, "end_lineno", None)
        self.functions.append(
            FunctionRecord(
                name=node.name,
                qualified_name=self._qualified(node.name),
                line_start=node.lineno,
                line_end=line_end,
            )
        )
        self._scope_stack.append(node.name)
        try:
            self.generic_visit(node)
        finally:
            self._scope_stack.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        line_end = getattr(node, "end_lineno", None)
        self.classes.append(
            ClassRecord(
                name=node.name,
                qualified_name=self._qualified(node.name),
                line_start=node.lineno,
                line_end=line_end,
            )
        )
        self._scope_stack.append(node.name)
        try:
            self.generic_visit(node)
        finally:
            self._scope_stack.pop()

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        callee = _get_call_name(node.func)
        if callee is not None:
            self.calls.append(
                CallRecord(
                    name=callee,
                    caller=self._caller(),
                    line_no=getattr(node, "lineno", None),
                )
            )
        self.generic_visit(node)


def parse_python_file(file_path: Path, repo_root: Path) -> ParsedFile:
    """
    Parse a Python file with :mod:`ast` and return :class:`ParsedFile`.

    Does not resolve imports or build graphs.
    """
    repo_abs = repo_root.expanduser().resolve(strict=False)
    path_obj = Path(file_path).expanduser()
    absolute_path = path_obj if path_obj.is_absolute() else repo_abs / path_obj
    absolute_path = absolute_path.resolve(strict=False)

    try:
        source = absolute_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        return _parsed_file_error_shell(
            repo_abs=repo_abs,
            absolute_path=absolute_path,
            errors=[
                f"read_failed error={type(exc).__name__}: {exc} path={absolute_path}"
            ],
        )

    try:
        tree = ast.parse(source, filename=str(absolute_path))
    except SyntaxError as exc:
        return _parsed_file_error_shell(
            repo_abs=repo_abs,
            absolute_path=absolute_path,
            errors=[f"syntax_error error={type(exc).__name__}: {exc}"],
        )

    visitor = _PythonAstVisitor()
    visitor.visit(tree)

    try:
        relative_path = absolute_path.relative_to(repo_abs).as_posix()
    except ValueError:
        relative_path = absolute_path.as_posix()

    return ParsedFile(
        file_path=relative_path,
        absolute_path=str(absolute_path),
        language="python",
        imports=visitor.imports,
        functions=visitor.functions,
        classes=visitor.classes,
        calls=visitor.calls,
        parse_errors=[],
    )
