from __future__ import annotations

from pathlib import Path
from typing import List

from .parser import analyze_project, FileAnalysis, ClassInfo, FunctionInfo
from .docstring_generator import (
    generate_module_markdown,
    generate_project_overview_markdown,
)


def _build_file_outline(fa: FileAnalysis, root: Path) -> str:
    """
    Build a simple text outline for a single file:
    - Relative path
    - Classes and methods
    - Top-level functions
    """
    rel_path = fa.path.relative_to(root)
    lines: List[str] = [f"File: {rel_path}"]

    if fa.classes:
        lines.append("  Classes:")
        for cls in fa.classes:
            lines.append(f"    - {cls.name}")
            if cls.methods:
                for m in cls.methods:
                    lines.append(f"      * method: {m.name}")

    if fa.functions:
        lines.append("  Top-level functions:")
        for fn in fa.functions:
            lines.append(f"    - {fn.name}")

    return "\n".join(lines)


def build_project_outline(analyses: List[FileAnalysis], root: Path) -> str:
    """
    Build a high-level outline for the entire project that we can feed to the LLM.
    """
    lines: List[str] = []
    for fa in analyses:
        lines.append(_build_file_outline(fa, root))
        lines.append("")  # blank line between files
    return "\n".join(lines)


def generate_module_docs(root: Path, analyses: List[FileAnalysis]) -> None:
    """
    Generate per-module Markdown docs under: <root>/docs/modules/<relative_path>.md
    """
    docs_root = root / "docs" / "modules"
    docs_root.mkdir(parents=True, exist_ok=True)

    for fa in analyses:
        rel_path = fa.path.relative_to(root)
        outline = _build_file_outline(fa, root)

        # Read source code for a short excerpt (limit to first ~120 lines)
        source = fa.path.read_text(encoding="utf-8")
        lines = source.splitlines()
        excerpt = "\n".join(lines[:120])

        short_name = rel_path.stem

        print(f"[MODULE DOC] Generating docs for {rel_path}")
        md = generate_module_markdown(
            path=str(rel_path),
            short_name=short_name,
            outline=outline,
            code_excerpt=excerpt,
        )

        # Write markdown file mirroring folder structure
        target_path = docs_root / (str(rel_path) + ".md")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(md + "\n", encoding="utf-8")


def generate_project_overview(root: Path, analyses: List[FileAnalysis]) -> None:
    """
    Generate a single PROJECT_OVERVIEW.md at the project root.
    """
    outline = build_project_outline(analyses, root)
    print("[PROJECT DOC] Generating project overview from outline...")
    md = generate_project_overview_markdown(outline)

    target = root / "PROJECT_OVERVIEW.md"
    target.write_text(md + "\n", encoding="utf-8")
    print(f"[PROJECT DOC] Wrote overview to {target}")