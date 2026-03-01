from __future__ import annotations

import ast
from pathlib import Path
from typing import List, Optional, Set, Tuple

from .models import (
    AttributeInfo,
    FunctionInfo,
    ClassInfo,
    ImportInfo,
    FileAnalysis,
)


def _get_type_annotation(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Constant):
        return str(node.value)
    elif isinstance(node, ast.Subscript):
        base = _get_type_annotation(node.value)
        slice_val = _get_type_annotation(node.slice)
        return f"{base}[{slice_val}]"
    elif isinstance(node, ast.Attribute):
        value = _get_type_annotation(node.value)
        return f"{value}.{node.attr}"
    elif isinstance(node, ast.Tuple):
        elements = ", ".join(_get_type_annotation(e) for e in node.elts)
        return f"({elements})"
    elif isinstance(node, ast.List):
        elements = ", ".join(_get_type_annotation(e) for e in node.elts)
        return f"[{elements}]"
    elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        left = _get_type_annotation(node.left)
        right = _get_type_annotation(node.right)
        return f"{left} | {right}"
    else:
        return "Any"


def _extract_decorator_names(decorators: List[ast.expr]) -> List[str]:
    names = []
    for dec in decorators:
        if isinstance(dec, ast.Name):
            names.append(dec.id)
        elif isinstance(dec, ast.Attribute):
            names.append(f"{_get_type_annotation(dec.value)}.{dec.attr}")
        elif isinstance(dec, ast.Call):
            if isinstance(dec.func, ast.Name):
                names.append(dec.func.id)
            elif isinstance(dec.func, ast.Attribute):
                names.append(dec.func.attr)
    return names


def _extract_function_info(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    parent_class: Optional[str] = None
) -> FunctionInfo:
    doc = ast.get_docstring(node, clean=False)
    has_docstring = doc is not None
    end_lineno = getattr(node, "end_lineno", node.lineno)
    
    parameters: List[Tuple[str, Optional[str]]] = []
    for arg in node.args.args:
        type_hint = None
        if arg.annotation:
            type_hint = _get_type_annotation(arg.annotation)
        parameters.append((arg.arg, type_hint))
    
    return_type = None
    if node.returns:
        return_type = _get_type_annotation(node.returns)
    
    decorators = _extract_decorator_names(node.decorator_list)
    
    return FunctionInfo(
        name=node.name,
        lineno=node.lineno,
        end_lineno=end_lineno,
        has_docstring=has_docstring,
        parent_class=parent_class,
        parameters=parameters,
        return_type=return_type,
        is_async=isinstance(node, ast.AsyncFunctionDef),
        decorators=decorators,
    )


def _infer_type_from_value(value: ast.expr) -> Optional[str]:
    if isinstance(value, ast.Call):
        if isinstance(value.func, ast.Name):
            return value.func.id
        elif isinstance(value.func, ast.Attribute):
            return value.func.attr
    elif isinstance(value, ast.List):
        return "list"
    elif isinstance(value, ast.Dict):
        return "dict"
    elif isinstance(value, ast.Set):
        return "set"
    elif isinstance(value, ast.Constant):
        if isinstance(value.value, str):
            return "str"
        elif isinstance(value.value, int):
            return "int"
        elif isinstance(value.value, float):
            return "float"
        elif isinstance(value.value, bool):
            return "bool"
    return None


def _extract_class_attributes(node: ast.ClassDef) -> List[AttributeInfo]:
    attributes: List[AttributeInfo] = []
    
    for item in node.body:
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            type_hint = _get_type_annotation(item.annotation) if item.annotation else None
            attributes.append(AttributeInfo(
                name=item.target.id,
                type_hint=type_hint,
                is_class_attribute=True,
            ))
        elif isinstance(item, ast.Assign):
            for target in item.targets:
                if isinstance(target, ast.Name):
                    type_hint = _infer_type_from_value(item.value) if item.value else None
                    attributes.append(AttributeInfo(
                        name=target.id,
                        type_hint=type_hint,
                        is_class_attribute=True,
                    ))
    
    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for stmt in ast.walk(item):
                if isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                            if target.value.id == "self":
                                type_hint = _infer_type_from_value(stmt.value) if stmt.value else None
                                attributes.append(AttributeInfo(
                                    name=target.attr,
                                    type_hint=type_hint,
                                    is_class_attribute=False,
                                ))
                elif isinstance(stmt, ast.AnnAssign):
                    if isinstance(stmt.target, ast.Attribute) and isinstance(stmt.target.value, ast.Name):
                        if stmt.target.value.id == "self":
                            type_hint = _get_type_annotation(stmt.annotation) if stmt.annotation else None
                            attributes.append(AttributeInfo(
                                name=stmt.target.attr,
                                type_hint=type_hint,
                                is_class_attribute=False,
                            ))
    
    seen = set()
    unique_attrs = []
    for attr in attributes:
        if attr.name not in seen:
            seen.add(attr.name)
            unique_attrs.append(attr)
    
    return unique_attrs


def _extract_base_classes(node: ast.ClassDef) -> List[str]:
    bases: List[str] = []
    for base in node.bases:
        if isinstance(base, ast.Name):
            bases.append(base.id)
        elif isinstance(base, ast.Attribute):
            bases.append(_get_type_annotation(base))
        elif isinstance(base, ast.Subscript):
            bases.append(_get_type_annotation(base))
    return bases


def _extract_imports(tree: ast.Module) -> List[ImportInfo]:
    imports: List[ImportInfo] = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(ImportInfo(
                    module=alias.name,
                    names=[alias.name],
                    alias=alias.asname,
                    is_from_import=False,
                    lineno=node.lineno,
                ))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = [alias.name for alias in node.names]
            imports.append(ImportInfo(
                module=module,
                names=names,
                is_from_import=True,
                lineno=node.lineno,
                level=node.level,
            ))
    
    return imports


def _extract_used_names(tree: ast.Module) -> Set[str]:
    used_names: Set[str] = set()
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used_names.add(node.id)
        elif isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name):
                used_names.add(node.value.id)
    
    return used_names


def _extract_top_level_functions(tree: ast.Module) -> List[FunctionInfo]:
    functions: List[FunctionInfo] = []
    
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(_extract_function_info(node))
    
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
                    methods.append(_extract_function_info(body_node, parent_class=node.name))
            
            base_classes = _extract_base_classes(node)
            attributes = _extract_class_attributes(node)
            decorators = _extract_decorator_names(node.decorator_list)
            
            classes.append(ClassInfo(
                name=node.name,
                lineno=node.lineno,
                end_lineno=class_end_lineno,
                has_docstring=class_has_docstring,
                methods=methods,
                base_classes=base_classes,
                attributes=attributes,
                decorators=decorators,
            ))
    
    return classes


def analyze_file(path: Path) -> FileAnalysis:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    
    functions = _extract_top_level_functions(tree)
    classes = _extract_classes(tree)
    imports = _extract_imports(tree)
    used_names = _extract_used_names(tree)
    
    module_docstring = ast.get_docstring(tree, clean=False)
    lines_of_code = len(source.splitlines())
    
    return FileAnalysis(
        path=path,
        functions=functions,
        classes=classes,
        imports=imports,
        module_docstring=module_docstring,
        lines_of_code=lines_of_code,
        used_names=used_names,
    )


def analyze_project(root: Path) -> List[FileAnalysis]:
    analyses: List[FileAnalysis] = []
    for py_file in root.rglob("*.py"):
        if ".venv" in py_file.parts or "venv" in py_file.parts:
            continue
        if "__pycache__" in py_file.parts:
            continue
        try:
            analyses.append(analyze_file(py_file))
        except SyntaxError as e:
            print(f"[WARNING] Skipping {py_file}: {e}")
    return analyses
