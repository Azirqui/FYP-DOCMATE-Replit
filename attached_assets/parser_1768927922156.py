from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class FunctionInfo:
    """Information about a single function or method."""
    name: str
    lineno: int          # Line where 'def' starts (1-based)
    end_lineno: int      # Line where function ends (1-based)
    has_docstring: bool
    parent_class: Optional[str] = None  # None = top-level function, otherwise class name


@dataclass
class ClassInfo:
    """Information about a single class."""
    name: str
    lineno: int          # Line where 'class' starts (1-based)
    end_lineno: int      # Line where class ends (1-based)
    has_docstring: bool
    methods: List[FunctionInfo]


@dataclass
class FileAnalysis:
    """Analysis result for a single Python file."""
    path: Path
    functions: List[FunctionInfo]       # top-level functions
    classes: List[ClassInfo]           # classes (with methods)


def _extract_top_level_functions(tree: ast.Module) -> List[FunctionInfo]:
    functions: List[FunctionInfo] = []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node, clean=False)
            has_docstring = doc is not None
            end_lineno = getattr(node, "end_lineno", node.lineno)

            functions.append(
                FunctionInfo(
                    name=node.name,
                    lineno=node.lineno,
                    end_lineno=end_lineno,
                    has_docstring=has_docstring,
                    parent_class=None,
                )
            )

    return functions


def _extract_classes(tree: ast.Module) -> List[ClassInfo]:
    classes: List[ClassInfo] = []

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            class_doc = ast.get_docstring(node, clean=False)
            class_has_docstring = class_doc is not None
            class_end_lineno = getattr(node, "end_lineno", node.lineno)

            methods: List[FunctionInfo] = []
            for body_node in node.body:
                if isinstance(body_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_doc = ast.get_docstring(body_node, clean=False)
                    method_has_docstring = method_doc is not None
                    method_end_lineno = getattr(body_node, "end_lineno", body_node.lineno)

                    methods.append(
                        FunctionInfo(
                            name=body_node.name,
                            lineno=body_node.lineno,
                            end_lineno=method_end_lineno,
                            has_docstring=method_has_docstring,
                            parent_class=node.name,
                        )
                    )

            classes.append(
                ClassInfo(
                    name=node.name,
                    lineno=node.lineno,
                    end_lineno=class_end_lineno,
                    has_docstring=class_has_docstring,
                    methods=methods,
                )
            )

    return classes


def analyze_file(path: Path) -> FileAnalysis:
    """Parse a single Python file and extract top-level functions and classes."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    functions = _extract_top_level_functions(tree)
    classes = _extract_classes(tree)

    return FileAnalysis(path=path, functions=functions, classes=classes)


def analyze_project(root: Path) -> List[FileAnalysis]:
    """Recursively analyze all .py files under a project root."""
    analyses: List[FileAnalysis] = []
    for py_file in root.rglob("*.py"):
        # Optionally, skip virtualenvs
        if ".venv" in py_file.parts or "venv" in py_file.parts:
            continue
        analyses.append(analyze_file(py_file))
    return analyses
