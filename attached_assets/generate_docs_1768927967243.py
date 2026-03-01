from __future__ import annotations

import sys
from pathlib import Path

from .parser import analyze_project
from .project_docs import generate_module_docs, generate_project_overview


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python -m code_doc_ai.app.generate_docs <project_root>")
        raise SystemExit(1)

    root = Path(sys.argv[1]).resolve()
    if not root.exists() or not root.is_dir():
        print(f"Path is not a directory: {root}")
        raise SystemExit(1)

    print(f"[DOC GEN] Analyzing project at: {root}")
    analyses = analyze_project(root)

    # Generate per-module docs
    generate_module_docs(root, analyses)

    # Generate single project overview
    generate_project_overview(root, analyses)

    print("[DOC GEN] Done.")


if __name__ == "__main__":
    main()
