"""
Regex-based extraction for JavaScript and TypeScript source files.

This is a regex-based JS/TS parser and may miss complex syntax or produce
false positives inside comments/strings. It does not resolve modules or build
graphs. Use for lightweight dependency signal only.
"""

from __future__ import annotations

import re
from pathlib import Path

from synapse_ai.dependency_graph.models import (
    CallRecord,
    ClassRecord,
    FunctionRecord,
    ImportRecord,
    ParsedFile,
)

_JS_CALL_DENYLIST = frozenset(
    {
        "if",
        "while",
        "for",
        "switch",
        "catch",
        "with",
        "function",
        "return",
        "throw",
        "typeof",
        "void",
        "delete",
        "await",
        "case",
        "new",
        "import",
        "export",
        "default",
        "try",
        "finally",
        "else",
        "do",
        "super",
        "this",
        "class",
        "extends",
        "static",
        "async",
        "yield",
        "var",
        "let",
        "const",
    }
)


def _resolve_absolute_path(file_path: Path, repo_root: Path) -> Path:
    repo_abs = repo_root.expanduser().resolve(strict=False)
    path_obj = Path(file_path).expanduser()
    joined = path_obj if path_obj.is_absolute() else repo_abs / path_obj
    return joined.resolve(strict=False)


def _relative_path_or_abs(repo_abs: Path, absolute_path: Path) -> str:
    try:
        return absolute_path.relative_to(repo_abs).as_posix()
    except ValueError:
        return absolute_path.as_posix()


def _detect_language(path: Path) -> str:
    suf = path.suffix.lower()
    if suf in {".ts", ".tsx"}:
        return "typescript"
    return "javascript"


def _split_named_import_bindings(inner: str) -> list[tuple[str, str | None]]:
    bindings: list[tuple[str, str | None]] = []
    cleaned = inner.replace("\n", " ")
    for part in cleaned.split(","):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^(?:(\w+)\s+as\s+)?(\w+)$", part)
        if m:
            orig, final = m.group(1), m.group(2)
            if orig:
                bindings.append((orig, final))
            else:
                bindings.append((final, None))
        elif part.split():
            bindings.append((part.split()[0], None))
    return bindings


def parse_javascript_file(file_path: Path, repo_root: Path) -> ParsedFile:
    """Regex-only parse of CommonJS / ES modules, declarations, and simple calls."""
    repo_abs = repo_root.expanduser().resolve(strict=False)
    absolute_path = _resolve_absolute_path(file_path, repo_root)
    language = _detect_language(absolute_path)
    relative = _relative_path_or_abs(repo_abs, absolute_path)

    try:
        text = absolute_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        return ParsedFile(
            file_path=relative,
            absolute_path=str(absolute_path),
            language=language,
            parse_errors=[f"read_failed error={type(exc).__name__}: {exc}"],
        )

    imports: list[ImportRecord] = []
    functions: list[FunctionRecord] = []
    classes: list[ClassRecord] = []
    calls: list[CallRecord] = []

    re_default_import = re.compile(
        r"^\s*(?:export\s+)?import\s+(?P<name>[A-Za-z_$][\w$]*)\s+from\s+"
        r"['\"](?P<mod>[^'\"]+)['\"]",
    )
    re_named_import = re.compile(
        r"^\s*(?:export\s+)?import\s*\{(?P<inner>[^}]*)\}\s*from\s*"
        r"['\"](?P<mod>[^'\"]+)['\"]",
    )
    re_namespace_import = re.compile(
        r"^\s*(?:export\s+)?import\s*\*\s+as\s+(?P<alias>[A-Za-z_$][\w$]*)\s+from\s+"
        r"['\"](?P<mod>[^'\"]+)['\"]",
    )
    re_side_effect_import = re.compile(
        r"^\s*(?:export\s+)?import\s+['\"](?P<mod>[^'\"]+)['\"]\s*(?:;)?\s*$",
    )
    re_function_decl = re.compile(
        r"^\s*(?:export\s+)?(?:async\s+)?function\s*\*?\s*(?P<name>[A-Za-z_$][\w$]*)"
        r"\s*\(",
    )
    re_arrow_async = re.compile(
        r"^\s*(?:export\s+)?(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*="
        r"\s*async\s*\([^)]*\)\s*=>",
    )
    re_arrow = re.compile(
        r"^\s*(?:export\s+)?(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*="
        r"\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>",
    )
    re_class = re.compile(
        r"^\s*(?:export\s+)?class\s+(?P<name>[A-Za-z_$][\w$]*)",
    )
    re_require = re.compile(r"require\s*\(\s*['\"](?P<mod>[^'\"]+)['\"]")
    re_method_call = re.compile(
        r"\b(?P<tgt>[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)+)\s*\(",
    )
    re_simple_call = re.compile(r"(?<![.\w])(?P<tgt>[A-Za-z_$][\w$]*)\s*\(")

    lines = text.splitlines()

    for line_no, raw_line in enumerate(lines, start=1):
        if re_default_import.match(raw_line):
            m = re_default_import.match(raw_line)
            assert m is not None
            imports.append(
                ImportRecord(
                    module=m.group("mod"),
                    name=m.group("name"),
                    alias=None,
                    import_type="from_import",
                    line_no=line_no,
                )
            )
            continue

        if re_named_import.match(raw_line):
            m = re_named_import.match(raw_line)
            assert m is not None
            mod = m.group("mod")
            for nm, alias in _split_named_import_bindings(m.group("inner")):
                imports.append(
                    ImportRecord(
                        module=mod,
                        name=nm,
                        alias=alias,
                        import_type="from_import",
                        line_no=line_no,
                    )
                )
            continue

        if re_namespace_import.match(raw_line):
            m = re_namespace_import.match(raw_line)
            assert m is not None
            imports.append(
                ImportRecord(
                    module=m.group("mod"),
                    name="*",
                    alias=m.group("alias"),
                    import_type="namespace_import",
                    line_no=line_no,
                )
            )
            continue

        if (
            " from " not in raw_line
            and re_side_effect_import.match(raw_line)
        ):
            m = re_side_effect_import.match(raw_line)
            assert m is not None
            imports.append(
                ImportRecord(
                    module=m.group("mod"),
                    name=None,
                    alias=None,
                    import_type="side_effect_import",
                    line_no=line_no,
                )
            )

        if re_arrow_async.match(raw_line):
            m = re_arrow_async.match(raw_line)
            assert m is not None
            nm = m.group("name")
            functions.append(
                FunctionRecord(name=nm, qualified_name=nm, line_start=line_no, line_end=line_no)
            )
        elif re_arrow.match(raw_line):
            m = re_arrow.match(raw_line)
            assert m is not None
            nm = m.group("name")
            functions.append(
                FunctionRecord(name=nm, qualified_name=nm, line_start=line_no, line_end=line_no)
            )

        if re_function_decl.match(raw_line):
            m = re_function_decl.match(raw_line)
            assert m is not None
            nm = m.group("name")
            functions.append(
                FunctionRecord(name=nm, qualified_name=nm, line_start=line_no, line_end=line_no)
            )

        if re_class.match(raw_line):
            m = re_class.match(raw_line)
            assert m is not None
            nm = m.group("name")
            classes.append(
                ClassRecord(name=nm, qualified_name=nm, line_start=line_no, line_end=line_no)
            )

        for mreq in re_require.finditer(raw_line):
            imports.append(
                ImportRecord(
                    module=mreq.group("mod"),
                    name=None,
                    alias=None,
                    import_type="require",
                    line_no=line_no,
                )
            )

        method_spans = [mm.span() for mm in re_method_call.finditer(raw_line)]
        for mm in re_method_call.finditer(raw_line):
            calls.append(CallRecord(name=mm.group("tgt"), caller=None, line_no=line_no))

        for ms in re_simple_call.finditer(raw_line):
            nm = ms.group("tgt")
            if nm in _JS_CALL_DENYLIST:
                continue
            span = ms.span()
            if any(s <= span[0] < e for s, e in method_spans):
                continue
            calls.append(CallRecord(name=nm, caller=None, line_no=line_no))

    return ParsedFile(
        file_path=relative,
        absolute_path=str(absolute_path),
        language=language,
        imports=imports,
        functions=functions,
        classes=classes,
        calls=calls,
        parse_errors=[],
    )
