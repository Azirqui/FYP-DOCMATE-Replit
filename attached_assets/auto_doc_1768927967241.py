
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Literal, Tuple

from .parser import (
    analyze_project,
    FileAnalysis,
    FunctionInfo,
    ClassInfo,
)
from .docstring_generator import (
    generate_function_docstring,
    generate_class_docstring,
)


def get_function_source(lines: List[str], func: FunctionInfo) -> str:
    """Extract the source code of a function/method from file lines."""
    start = func.lineno - 1
    end = func.end_lineno
    snippet_lines = lines[start:end]
    return "\n".join(snippet_lines)


def get_class_source(lines: List[str], cls: ClassInfo) -> str:
    """Extract the source code of a class from file lines."""
    start = cls.lineno - 1
    end = cls.end_lineno
    snippet_lines = lines[start:end]
    return "\n".join(snippet_lines)


def build_docstring_block(indent: str, docstring_text: str) -> List[str]:
    """
    Build a list of lines representing the docstring block with correct indentation.

    Example (indent = body indentation):

        \"\"\"Some text
        goes here.\"\"\"
    """
    body_indent = indent
    lines: List[str] = []

    lines.append(f'{body_indent}"""')
    for line in docstring_text.splitlines():
        if line.strip():
            lines.append(f"{body_indent}{line}")
        else:
            lines.append(body_indent)
    lines.append(f'{body_indent}"""')

    return lines


def insert_function_docstring(lines: List[str], func: FunctionInfo, docstring_text: str) -> None:
    """
    Insert a docstring for a function or method into the list of lines, in-place.

    We insert just after the 'def ...' line.
    """
    def_index = func.lineno - 1
    def_line = lines[def_index]

    # Detect indentation of the 'def' line
    leading_spaces = len(def_line) - len(def_line.lstrip(" "))
    def_indent = " " * leading_spaces

    # Assume function body is indented one level (4 spaces) further
    body_indent = def_indent + " " * 4

    doc_block = build_docstring_block(body_indent, docstring_text)

    insert_at = def_index + 1
    lines[insert_at:insert_at] = doc_block


def insert_class_docstring(lines: List[str], cls: ClassInfo, docstring_text: str) -> None:
    """
    Insert a docstring for a class into the list of lines, in-place.

    We insert just after the 'class ...' line.
    """
    class_index = cls.lineno - 1
    class_line = lines[class_index]

    leading_spaces = len(class_line) - len(class_line.lstrip(" "))
    class_indent = " " * leading_spaces

    # Class body is usually indented one level (4 spaces) further
    body_indent = class_indent + " " * 4

    doc_block = build_docstring_block(body_indent, docstring_text)

    insert_at = class_index + 1
    lines[insert_at:insert_at] = doc_block


def process_file(analysis: FileAnalysis) -> None:
    """
    Generate and insert docstrings for a single file.

    Handles:
    - top-level functions
    - classes
    - methods inside classes
    """
    path = analysis.path
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    # Build a unified list of targets: (kind, object)
    # kind: "function" | "class"
    targets: List[Tuple[Literal["function", "class"], object]] = []

    # Top-level functions without docstrings
    for f in analysis.functions:
        if not f.has_docstring:
            targets.append(("function", f))

    # Classes and methods inside classes
    for cls in analysis.classes:
        if not cls.has_docstring:
            targets.append(("class", cls))
        for m in cls.methods:
            if not m.has_docstring:
                targets.append(("function", m))

    if not targets:
        print(f"[SKIP] {path} (no missing docstrings)")
        return

    # Sort by lineno descending so that inserting docstrings does not break later indices
    def get_lineno(item: Tuple[Literal["function", "class"], object]) -> int:
        kind, obj = item
        if kind == "function":
            return obj.lineno
        else:
            return obj.lineno

    targets.sort(key=get_lineno, reverse=True)

    print(f"[FILE] {path} - {len(targets)} items need docstrings")

    for kind, obj in targets:
        if kind == "function":
            func: FunctionInfo = obj  # type: ignore
            element_type = "method" if func.parent_class else "function"
            print(f"  - Generating docstring for {element_type}: "
                  f"{func.name} (line {func.lineno}, parent={func.parent_class})")

            try:
                func_code = get_function_source(lines, func)
                docstring_text = generate_function_docstring(func_code)
                insert_function_docstring(lines, func, docstring_text)
            except Exception as e:
                print(f"    ! Error generating docstring for {element_type} {func.name}: {e}")

        elif kind == "class":
            cls: ClassInfo = obj  # type: ignore
            print(f"  - Generating docstring for class: {cls.name} (line {cls.lineno})")

            try:
                class_code = get_class_source(lines, cls)
                docstring_text = generate_class_docstring(class_code)
                insert_class_docstring(lines, cls, docstring_text)
            except Exception as e:
                print(f"    ! Error generating docstring for class {cls.name}: {e}")

    new_text = "\n".join(lines) + "\n"
    path.write_text(new_text, encoding="utf-8")
    print(f"[UPDATED] {path}")


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python -m code_doc_ai.app.auto_doc <project_root_or_file>")
        raise SystemExit(1)

    root = Path(sys.argv[1]).resolve()
    if not root.exists():
        print(f"Path does not exist: {root}")
        raise SystemExit(1)

    # If it's a single file, analyze that. If it's a directory, analyze recursively.
    if root.is_file() and root.suffix == ".py":
        from .parser import analyze_file
        analysis = analyze_file(root)
        process_file(analysis)
    else:
        print(f"Analyzing project at: {root}")
        analyses = analyze_project(root)
        for file_analysis in analyses:
            process_file(file_analysis)


if __name__ == "__main__":
    main()
