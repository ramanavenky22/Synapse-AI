#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from synapse_ai.dependency_graph.parser_registry import parse_file_by_extension


def _ensure_test_repo(repo_root: Path) -> dict[str, Path]:
    test_repo = repo_root / "test_repo"
    test_repo.mkdir(parents=True, exist_ok=True)

    samples: dict[str, tuple[str, str]] = {
        "sample.py": (
            "python",
            "import os\nfrom pathlib import Path\n\ndef run():\n    print(Path('.'))\n",
        ),
        "sample.js": (
            "javascript",
            "import React from \"react\";\nconst run = () => console.log('ok');\nrun();\n",
        ),
        "sample.ts": (
            "typescript",
            "import { readFile } from \"fs\";\nconst run = async () => readFile;\nrun();\n",
        ),
        "Sample.java": (
            "java",
            "import com.example.Service;\nclass Sample { void run() {} }\n",
        ),
        "main.go": (
            "go",
            "package main\nimport \"fmt\"\nfunc main(){ fmt.Println(\"hi\") }\n",
        ),
        "main.rs": (
            "rust",
            "use crate::module;\nfn main(){ println!(\"hi\"); }\n",
        ),
        "setup.sh": (
            "shell",
            "#!/usr/bin/env bash\nsource ./env.sh\nfunction run(){ echo ok; }\nrun\n",
        ),
    }

    paths: dict[str, Path] = {}
    for filename, (_language, content) in samples.items():
        p = test_repo / filename
        if not p.exists():
            p.write_text(content, encoding="utf-8")
        paths[filename] = p
    return paths


def main() -> int:
    files = _ensure_test_repo(REPO_ROOT)
    expected_language = {
        "sample.py": "python",
        "sample.js": "javascript",
        "sample.ts": "typescript",
        "Sample.java": "java",
        "main.go": "go",
        "main.rs": "rust",
        "setup.sh": "shell",
    }

    parsed_results: list[dict] = []
    errors: list[str] = []

    for filename, path in files.items():
        parsed = parse_file_by_extension(path, REPO_ROOT)
        parsed_dict = parsed.to_dict()
        parsed_results.append(parsed_dict)

        print(f"\n=== {filename} ===")
        print(json.dumps(parsed_dict, indent=2))

        expected = expected_language[filename]
        if parsed.language != expected:
            errors.append(
                f"{filename}: expected language={expected}, got {parsed.language}"
            )

    out_path = REPO_ROOT / "parsed_files_smoke.json"
    out_path.write_text(json.dumps(parsed_results, indent=2), encoding="utf-8")
    print(f"\nSaved smoke parse results to: {out_path}")

    if errors:
        print("\nLanguage checks failed:", file=sys.stderr)
        for err in errors:
            print(f"- {err}", file=sys.stderr)
        return 1

    print("Language checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
