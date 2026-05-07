"""
Generic multi-language parser using regex.

Limitations:
- Not syntax-aware
- May miss complex constructs
- May produce partial results
- Designed for lightweight dependency extraction only
"""

from __future__ import annotations

import re
from pathlib import Path
from re import Pattern
from typing import Any

from synapse_ai.dependency_graph.models import (
    CallRecord,
    ClassRecord,
    FunctionRecord,
    ImportRecord,
    ParsedFile,
)

_CALL_KEYWORDS = frozenset(
    {
        "if",
        "while",
        "for",
        "switch",
        "return",
        "throw",
        "catch",
        "try",
        "new",
        "sizeof",
        "goto",
        "case",
        "default",
        "else",
        "defer",
        "package",
        "import",
        "func",
        "echo",
        "test",
        "select",
        "where",
    },
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


def _import_record(
    module: str,
    *,
    line_no: int,
    import_type: str,
    name: str | None = None,
    alias: str | None = None,
) -> ImportRecord:
    return ImportRecord(
        module=module.strip().strip(";").strip(),
        name=name,
        alias=alias,
        import_type=import_type,
        line_no=line_no,
        resolved_path=None,
        is_external=False,
    )


def _grep_calls(line: str, line_no: int) -> list[CallRecord]:
    out: list[CallRecord] = []
    for mm in re.finditer(
        r"\b(?P<tgt>[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)+)\s*\(",
        line,
    ):
        out.append(CallRecord(name=mm.group("tgt"), caller=None, line_no=line_no))
    for ms in re.finditer(r"(?<![.\w])(?P<tgt>[A-Za-z_$][\w$]*)\s*\(", line):
        nm = ms.group("tgt")
        if nm in _CALL_KEYWORDS:
            continue
        out.append(CallRecord(name=nm, caller=None, line_no=line_no))
    return out


def _scan_patterns(
    lines: list[str],
    *,
    import_specs: list[tuple[Pattern[str], str]],
    class_patterns: list[Pattern[str]],
    func_patterns: list[Pattern[str]],
    grab_calls: bool = True,
) -> tuple[list[ImportRecord], list[FunctionRecord], list[ClassRecord], list[CallRecord]]:
    imports: list[ImportRecord] = []
    functions: list[FunctionRecord] = []
    classes: list[ClassRecord] = []
    calls: list[CallRecord] = []

    for line_no, line in enumerate(lines, start=1):
        for rx, itype in import_specs:
            for m in rx.finditer(line):
                gd = m.groupdict()
                mod = gd.get("mod") or gd.get("pkg") or gd.get("path")
                if mod:
                    imports.append(_import_record(mod, line_no=line_no, import_type=itype))
                elif m.groups():
                    mod2 = next((g.strip() for g in m.groups() if g), None)
                    if mod2:
                        imports.append(_import_record(mod2, line_no=line_no, import_type=itype))

        for rx in class_patterns:
            mr = rx.search(line)
            if mr and mr.groupdict().get("name"):
                nm = mr.group("name")
                classes.append(
                    ClassRecord(
                        name=nm, qualified_name=nm, line_start=line_no, line_end=line_no
                    )
                )

        for rx in func_patterns:
            mr = rx.search(line)
            if mr and mr.groupdict().get("name"):
                nm = mr.group("name")
                if nm == "self":
                    continue
                functions.append(
                    FunctionRecord(
                        name=nm, qualified_name=nm, line_start=line_no, line_end=line_no
                    )
                )

        if grab_calls:
            calls.extend(_grep_calls(line, line_no))

    return imports, functions, classes, calls


def _patterns_c_like() -> dict[str, Any]:
    return {
        "import_specs": [
            (re.compile(r'#\s*include\s*<(?P<mod>[^>]+)>'), "include"),
            (re.compile(r'#\s*include\s+"(?P<mod>[^"]+)"'), "include"),
        ],
        "class_patterns": [],
        "func_patterns": [
            re.compile(
                r"^\s*(?:extern\s+|static\s+|inline\s+|const\s+|volatile\s+)*"
                r"(?:[\w\*\s]+)\s+(?P<name>[A-Za-z_]\w*)\s*\([^;{}]*?\)\s*(?:\{|\s|;|$)",
            ),
        ],
    }


def _patterns_java_like() -> dict[str, Any]:
    return {
        "import_specs": [
            (re.compile(r"^\s*import\s+(?P<mod>[\w.]+\.?(?:\*));"), "import"),
        ],
        "class_patterns": [
            re.compile(
                r"^\s*(?:public|private|protected)?\s*(?:abstract\s+|final\s+|sealed\s+|non-sealed\s*)?"
                r"(?:class|interface|enum|record)\s+(?P<name>\w+)",
            ),
        ],
        "func_patterns": [
            re.compile(
                r"^\s*(?:@\w+(?:\([^)]*\))?\s+)*(?:public|private|protected|static|final|\s)+\s*(?:<[^>]+>)?\s*"
                r"[\w\[\],\s.]+\s+(?P<name>\w+)\s*\(",
            ),
        ],
    }


def _extract_go(lines: list[str]) -> tuple[list[ImportRecord], list[FunctionRecord], list[ClassRecord], list[CallRecord]]:
    imports: list[ImportRecord] = []
    functions: list[FunctionRecord] = []
    classes: list[ClassRecord] = []
    calls: list[CallRecord] = []

    rx_single = re.compile(r'^\s*import\s+"(?P<pkg>[^"]+)"\s*$')
    rx_fn = re.compile(r"^\s*func\s+(?:\([^)]*\)\s+)?(?P<name>[A-Za-z_]\w*)\s*\(")
    rx_quote_pkg = re.compile(r'"(?P<pkg>[^"]+)"')

    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        line_no = i + 1

        ms = rx_single.match(line)
        if ms:
            imports.append(
                _import_record(ms.group("pkg"), line_no=line_no, import_type="import")
            )
            i += 1
            continue

        if re.match(r"^\s*import\s*\(\s*", line):
            block_start_ln = line_no
            i += 1
            while i < n:
                iline = lines[i]
                if re.match(r"^\s*\)\s*$", iline.strip()):
                    i += 1
                    break
                for mp in rx_quote_pkg.finditer(iline):
                    imports.append(
                        _import_record(
                            mp.group("pkg"), line_no=block_start_ln, import_type="import"
                        )
                    )
                i += 1
            continue

        mf = rx_fn.search(line)
        if mf:
            functions.append(
                FunctionRecord(
                    name=mf.group("name"),
                    qualified_name=mf.group("name"),
                    line_start=line_no,
                    line_end=line_no,
                )
            )

        calls.extend(_grep_calls(line, line_no))
        i += 1

    return imports, functions, classes, calls


JAVA_LIKE = _patterns_java_like()
C_LIKE = _patterns_c_like()

LANGUAGE_PATTERNS: dict[str, dict[str, Any]] = {
    "java": JAVA_LIKE,
    "kotlin": {
        "import_specs": [
            (
                re.compile(r"^\s*import\s+(?P<mod>[A-Za-z_][\w.]*(?:\.\*)?(?:\s+as\s+\w+)?)"),
                "import",
            ),
        ],
        "class_patterns": [re.compile(r"^\s*(?:data\s+)?(?:sealed\s+)?class\s+(?P<name>\w+)")],
        "func_patterns": [re.compile(r"^\s*fun\s+(?P<name>\w+)\s*\(")],
    },
    "scala": {
        "import_specs": [
            (re.compile(r"^\s*import\s+(?P<mod>[\w.]+[^\n]*)"), "import"),
        ],
        "class_patterns": [
            re.compile(r"^\s*(?:abstract\s+|final\s+)?class\s+(?P<name>\w+)"),
        ],
        "func_patterns": [re.compile(r"^\s*def\s+(?P<name>\w+)\s*[:(]")],
    },
    "swift": {
        "import_specs": [
            (re.compile(r"^\s*import\s+(?P<mod>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)"), "import"),
        ],
        "class_patterns": [
            re.compile(r"^\s*(?:public|internal|private|open|final\s+)?class\s+(?P<name>\w+)"),
        ],
        "func_patterns": [
            re.compile(r"^\s*(?:public|internal|private|open|@\w+\s+)?func\s+(?P<name>\w+)\s*\("),
        ],
    },
    "csharp": {
        "import_specs": [
            (re.compile(r"^\s*using\s+(?P<mod>[\w.]+(?:\.\w+)*)\s*=\s*(?P<alias>[\w.<>,\s]+);"), "using_alias"),
            (re.compile(r"^\s*using\s+(?:static\s+)?(?P<mod>[\w.]+(?:\([^)]*\))?)\s*;"), "using"),
        ],
        "class_patterns": [
            re.compile(
                r"^\s*(?:public|internal|private|protected)?\s*(?:static\s+|abstract\s+|sealed\s+)?"
                r"(?:partial\s+)?class\s+(?P<name>\w+)",
            ),
        ],
        "func_patterns": [
            re.compile(
                r"\b(?:void|bool|byte|short|int|long|ulong|ushort|double|float|decimal|string|char|object|dynamic|Task|Task<[^>]+>|IActionResult|ActionResult|[\w]+\[\])\s+(?P<name>\w+)\s*\(",
            ),
        ],
    },
    "c": C_LIKE,
    "cpp": C_LIKE,
    "c_header": C_LIKE,
    "rust": {
        "import_specs": [
            (re.compile(r"^\s*(?:pub\s*\([^)]*\)\s+)?(?:pub\s+)?use\s+(?P<mod>[^;]+);"), "use"),
        ],
        "class_patterns": [],
        "func_patterns": [
            re.compile(r"^\s*(?:pub\s+)?(?:unsafe\s+)?fn\s+(?P<name>\w+)\s*\("),
        ],
    },
    "ruby": {
        "import_specs": [
            (re.compile(r"^\s*require\s+['\"](?P<mod>[^'\"]+)['\"]"), "require"),
            (
                re.compile(r"^\s*require_relative\s+['\"](?P<mod>[^'\"]+)['\"]"),
                "require_relative",
            ),
            (re.compile(r"^\s*load\s+['\"](?P<mod>[^'\"]+)['\"]"), "load"),
        ],
        "class_patterns": [
            re.compile(r"^\s*class\s+(?P<name>\w+)"),
            re.compile(r"^\s*module\s+(?P<name>\w+)\s*$"),
        ],
        "func_patterns": [
            re.compile(
                r"^\s*def\s+(?:self\.)?(?P<name>[A-Za-z_]\w*[!?]?)(?:\s|\(|;|$|\n)",
            ),
        ],
    },
    "php": {
        "import_specs": [
            (re.compile(r"^\s*use\s+(?P<mod>[^;]+);"), "use"),
            (
                re.compile(
                    r"^\s*(?:require|require_once|include|include_once)"
                    r"\s*(?:\(|\s+)(?P<mod>[\"'][^\"']+[\"']|[^\s\)]+)",
                ),
                "require",
            ),
        ],
        "class_patterns": [re.compile(r"^\s*class\s+(?P<name>\w+)")],
        "func_patterns": [re.compile(r"^\s*function\s+(?P<name>\w+)\s*\(")],
    },
    "shell": {
        "import_specs": [
            (re.compile(r"^\s*source\s+['\"]?(?P<mod>\S+)['\"]?\s*$"), "source"),
            (re.compile(r"^\s*\.\s+['\"]?(?P<mod>[./]\S+)['\"]?\s*$"), "dot_source"),
        ],
        "class_patterns": [],
        "func_patterns": [re.compile(r"^\s*function\s+(?P<name>\w+)\s*\(")],
    },
    "sql": {
        "import_specs": [],
        "class_patterns": [],
        "func_patterns": [],
    },
}


def _sql_skeleton_calls(lines: list[str]) -> list[CallRecord]:
    calls: list[CallRecord] = []
    for line_no, line in enumerate(lines, start=1):
        lm = re.match(r"^\s*([A-Za-z]+)\b", line)
        if lm and lm.group(1).upper() in frozenset(
            {"CREATE", "DROP", "ALTER", "INSERT", "UPDATE", "DELETE", "SELECT", "WITH", "MERGE", "EXEC", "CALL"}
        ):
            calls.append(
                CallRecord(name=lm.group(1).upper(), caller=None, line_no=line_no)
            )
    return calls


def parse_generic_file(
    file_path: Path, repo_root: Path, language: str = "generic"
) -> ParsedFile:
    """Best-effort regex parse for manifest languages except Python/JS (handled elsewhere)."""
    repo_abs = repo_root.expanduser().resolve(strict=False)
    absolute_path = _resolve_absolute_path(file_path, repo_root)
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

    lang_key = language.strip().lower()
    lines = text.splitlines()

    imports: list[ImportRecord] = []
    functions: list[FunctionRecord] = []
    classes: list[ClassRecord] = []
    calls: list[CallRecord] = []

    if lang_key == "generic":
        pass
    elif lang_key == "go":
        imports, functions, classes, calls = _extract_go(lines)
    elif lang_key == "sql":
        calls = _sql_skeleton_calls(lines)
    else:
        pdata = LANGUAGE_PATTERNS.get(lang_key)
        if pdata is not None:
            imports, functions, classes, calls = _scan_patterns(
                lines,
                import_specs=pdata["import_specs"],
                class_patterns=pdata["class_patterns"],
                func_patterns=pdata["func_patterns"],
                grab_calls=True,
            )

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
