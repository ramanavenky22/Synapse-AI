from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ImportRecord:
    """Represents one import statement discovered in a file."""

    module: str
    name: str | None = None
    alias: str | None = None
    import_type: str = "import"
    line_no: int | None = None
    resolved_path: str | None = None
    is_external: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FunctionRecord:
    """Represents one function declaration in a file."""

    name: str
    qualified_name: str
    line_start: int | None = None
    line_end: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ClassRecord:
    """Represents one class declaration in a file."""

    name: str
    qualified_name: str
    line_start: int | None = None
    line_end: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CallRecord:
    """Represents one function/method call occurrence in a file."""

    name: str
    caller: str | None = None
    line_no: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ParsedFile:
    """Parsed Layer 2 view of one source file."""

    file_path: str
    absolute_path: str
    language: str
    imports: list[ImportRecord] = field(default_factory=list)
    functions: list[FunctionRecord] = field(default_factory=list)
    classes: list[ClassRecord] = field(default_factory=list)
    calls: list[CallRecord] = field(default_factory=list)
    parse_errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
