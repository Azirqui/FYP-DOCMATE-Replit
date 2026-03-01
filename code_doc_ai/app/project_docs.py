from __future__ import annotations

from pathlib import Path
from typing import List

from .parser import FileAnalysis, ClassInfo, FunctionInfo
from .docstring_generator import (
    generate_module_markdown,
    generate_project_overview_markdown,
)
from .uml_generator import (
    generate_class_diagram,
    generate_dependency_graph,
    generate_module_class_diagram,
)
from .relationship_mapper import get_metrics, build_class_relationships


def _build_file_outline(fa: FileAnalysis, root: Path) -> str:
    rel_path = fa.path.relative_to(root)
    lines: List[str] = [f"File: {rel_path}"]

    if fa.classes:
        lines.append("  Classes:")
        for cls in fa.classes:
            base_str = ""
            if cls.base_classes:
                base_str = f" (extends: {', '.join(cls.base_classes)})"
            lines.append(f"    - {cls.name}{base_str}")
            
            if cls.attributes:
                lines.append("      Attributes:")
                for attr in cls.attributes:
                    type_str = f": {attr.type_hint}" if attr.type_hint else ""
                    lines.append(f"        * {attr.name}{type_str}")
            
            if cls.methods:
                lines.append("      Methods:")
                for m in cls.methods:
                    params = ", ".join(
                        f"{p[0]}: {p[1]}" if p[1] else p[0]
                        for p in m.parameters if p[0] not in ("self", "cls")
                    )
                    return_str = f" -> {m.return_type}" if m.return_type else ""
                    lines.append(f"        * {m.name}({params}){return_str}")

    if fa.functions:
        lines.append("  Top-level functions:")
        for fn in fa.functions:
            params = ", ".join(
                f"{p[0]}: {p[1]}" if p[1] else p[0]
                for p in fn.parameters
            )
            return_str = f" -> {fn.return_type}" if fn.return_type else ""
            lines.append(f"    - {fn.name}({params}){return_str}")
    
    if fa.imports:
        lines.append("  Imports:")
        for imp in fa.imports[:10]:
            if imp.is_from_import:
                names = ", ".join(imp.names[:5])
                if len(imp.names) > 5:
                    names += ", ..."
                lines.append(f"    - from {imp.module} import {names}")
            else:
                lines.append(f"    - import {imp.module}")

    return "\n".join(lines)


def build_project_outline(analyses: List[FileAnalysis], root: Path) -> str:
    lines: List[str] = []
    for fa in analyses:
        lines.append(_build_file_outline(fa, root))
        lines.append("")
    return "\n".join(lines)


def _format_metrics(metrics: dict) -> str:
    lines = [
        f"- Total files: {metrics['total_files']}",
        f"- Total classes: {metrics['total_classes']}",
        f"- Total functions: {metrics['total_functions']}",
        f"- Total methods: {metrics['total_methods']}",
        f"- Total lines of code: {metrics['total_lines_of_code']}",
        f"- Average lines per file: {metrics['avg_lines_per_file']:.1f}",
    ]
    return "\n".join(lines)


def generate_module_docs(root: Path, analyses: List[FileAnalysis]) -> None:
    docs_root = root / "docs" / "modules"
    docs_root.mkdir(parents=True, exist_ok=True)

    for fa in analyses:
        rel_path = fa.path.relative_to(root)
        outline = _build_file_outline(fa, root)

        source = fa.path.read_text(encoding="utf-8")
        lines = source.splitlines()
        excerpt = "\n".join(lines[:120])

        short_name = rel_path.stem

        print(f"[MODULE DOC] Generating docs for {rel_path}")
        
        try:
            md = generate_module_markdown(
                path=str(rel_path),
                short_name=short_name,
                outline=outline,
                code_excerpt=excerpt,
            )
        except Exception as e:
            print(f"[WARNING] LLM call failed for {rel_path}: {e}")
            md = f"## {short_name} Module\n\n*Documentation generation failed.*\n"
        
        class_diagram = generate_module_class_diagram(fa, root)
        if class_diagram:
            md += f"\n\n### Class Diagram\n\n```mermaid\n{class_diagram}\n```\n"

        target_path = docs_root / (str(rel_path) + ".md")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(md + "\n", encoding="utf-8")


def generate_project_overview(root: Path, analyses: List[FileAnalysis]) -> None:
    outline = build_project_outline(analyses, root)
    metrics = get_metrics(analyses)
    metrics_str = _format_metrics(metrics)
    
    class_diagram = generate_class_diagram(analyses, root)
    dependency_graph = generate_dependency_graph(analyses, root)
    
    print("[PROJECT DOC] Generating project overview from outline...")
    
    try:
        md = generate_project_overview_markdown(
            project_outline=outline,
            metrics=metrics_str,
            class_diagram=class_diagram,
        )
    except Exception as e:
        print(f"[WARNING] LLM call failed for project overview: {e}")
        md = "# Project Overview\n\n*Documentation generation failed.*\n"
    
    if dependency_graph:
        md += f"\n\n## Dependency Graph\n\n```mermaid\n{dependency_graph}\n```\n"

    target = root / "PROJECT_OVERVIEW.md"
    target.write_text(md + "\n", encoding="utf-8")
    print(f"[PROJECT DOC] Wrote overview to {target}")


def generate_uml_diagrams_only(root: Path, analyses: List[FileAnalysis]) -> None:
    docs_root = root / "docs" / "diagrams"
    docs_root.mkdir(parents=True, exist_ok=True)
    
    print("[UML] Generating class diagram...")
    class_diagram = generate_class_diagram(analyses, root)
    (docs_root / "class_diagram.md").write_text(
        f"# Class Diagram\n\n```mermaid\n{class_diagram}\n```\n"
    )
    
    print("[UML] Generating dependency graph...")
    dependency_graph = generate_dependency_graph(analyses, root)
    (docs_root / "dependency_graph.md").write_text(
        f"# Dependency Graph\n\n```mermaid\n{dependency_graph}\n```\n"
    )
    
    print(f"[UML] Diagrams written to {docs_root}")
