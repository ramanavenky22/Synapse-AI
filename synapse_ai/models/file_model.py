from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FileModel:
    path: str
    relative_path: str
    name: str
    extension: str
    size: int

    def to_dict(self) -> dict[str, str | int]:
        return {
            "path": self.path,
            "relative_path": self.relative_path,
            "name": self.name,
            "extension": self.extension,
            "size": self.size,
        }
