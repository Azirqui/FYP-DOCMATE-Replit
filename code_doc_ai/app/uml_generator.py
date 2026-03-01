from __future__ import annotations

from typing import List, Dict, Set
from pathlib import Path

from .parser import FileAnalysis, ClassInfo, FunctionInfo, AttributeInfo
from .relationship_mapper import (
    ProjectRelationships,
    ClassRelationship,
    FileRelationship,
    build_class_relationships,
    build_file_relationships,
)


def _get_visibility_prefix(name: str) -> str:
    if name.startswith("__") and not name.endswith("__"):
        return "-"
    elif name.startswith("_"):
        return "#"
    else:
        return "+"


def _format_method_signature(method: FunctionInfo) -> str:
    visibility = _get_visibility_prefix(method.name)
    
    params = []
    for param_name, param_type in method.parameters:
        if param_name == "self" or param_name == "cls":
            continue
        if param_type:
            params.append(f"{param_name}: {param_type}")
        else:
            params.append(param_name)
    
    params_str = ", ".join(params)
    
    return_str = ""
    if method.return_type:
        return_str = f" {method.return_type}"
    
    return f"{visibility}{method.name}({params_str}){return_str}"


def _format_attribute(attr: AttributeInfo) -> str:
    visibility = _get_visibility_prefix(attr.name)
    
    if attr.type_hint:
        return f"{visibility}{attr.name}: {attr.type_hint}"
    else:
        return f"{visibility}{attr.name}"


def _escape_mermaid(text: str) -> str:
    return text.replace("<", "~").replace(">", "~").replace('"', "'")


def generate_class_diagram(
    analyses: List[FileAnalysis],
    root: Path,
    include_methods: bool = True,
    include_attributes: bool = True,
    max_methods: int = 10,
) -> str:
    relationships = build_class_relationships(analyses, root)
    
    lines = ["classDiagram"]
    
    for analysis in analyses:
        for cls in analysis.classes:
            lines.append(f"    class {cls.name} {{")
            
            if include_attributes and cls.attributes:
                for attr in cls.attributes[:max_methods]:
                    attr_str = _escape_mermaid(_format_attribute(attr))
                    lines.append(f"        {attr_str}")
            
            if include_methods and cls.methods:
                for method in cls.methods[:max_methods]:
                    method_str = _escape_mermaid(_format_method_signature(method))
                    lines.append(f"        {method_str}")
            
            lines.append("    }")
    
    for rel in relationships.class_relationships:
        if rel.relationship_type == "inheritance":
            lines.append(f"    {rel.from_class} --|> {rel.to_class}")
        elif rel.relationship_type == "composition":
            lines.append(f"    {rel.from_class} *-- {rel.to_class}")
        elif rel.relationship_type == "dependency":
            lines.append(f"    {rel.from_class} ..> {rel.to_class} : uses")
    
    return "\n".join(lines)


def generate_dependency_graph(
    analyses: List[FileAnalysis],
    root: Path,
) -> str:
    file_relationships = build_file_relationships(analyses, root)
    
    lines = ["graph TD"]
    
    node_ids: Dict[str, str] = {}
    for i, analysis in enumerate(analyses):
        rel_path = str(analysis.path.relative_to(root))
        node_id = f"F{i}"
        node_ids[rel_path] = node_id
        
        display_name = analysis.path.stem
        lines.append(f"    {node_id}[{display_name}]")
    
    for rel in file_relationships:
        from_id = node_ids.get(rel.from_file)
        to_id = node_ids.get(rel.to_file)
        
        if from_id and to_id:
            lines.append(f"    {from_id} --> {to_id}")
    
    return "\n".join(lines)


def generate_inheritance_diagram(
    analyses: List[FileAnalysis],
    root: Path,
) -> str:
    relationships = build_class_relationships(analyses, root)
    
    lines = ["graph BT"]
    
    classes_with_inheritance: Set[str] = set()
    for rel in relationships.class_relationships:
        if rel.relationship_type == "inheritance":
            classes_with_inheritance.add(rel.from_class)
            classes_with_inheritance.add(rel.to_class)
    
    node_ids: Dict[str, str] = {}
    for i, class_name in enumerate(sorted(classes_with_inheritance)):
        node_id = f"C{i}"
        node_ids[class_name] = node_id
        lines.append(f"    {node_id}[{class_name}]")
    
    for rel in relationships.class_relationships:
        if rel.relationship_type == "inheritance":
            from_id = node_ids.get(rel.from_class)
            to_id = node_ids.get(rel.to_class)
            if from_id and to_id:
                lines.append(f"    {from_id} --> {to_id}")
    
    if len(classes_with_inheritance) == 0:
        return ""
    
    return "\n".join(lines)


def generate_module_class_diagram(
    analysis: FileAnalysis,
    root: Path,
    include_methods: bool = True,
    include_attributes: bool = True,
) -> str:
    if not analysis.classes:
        return ""
    
    lines = ["classDiagram"]
    
    class_names = {cls.name for cls in analysis.classes}
    
    for cls in analysis.classes:
        lines.append(f"    class {cls.name} {{")
        
        if include_attributes and cls.attributes:
            for attr in cls.attributes:
                attr_str = _escape_mermaid(_format_attribute(attr))
                lines.append(f"        {attr_str}")
        
        if include_methods and cls.methods:
            for method in cls.methods:
                method_str = _escape_mermaid(_format_method_signature(method))
                lines.append(f"        {method_str}")
        
        lines.append("    }")
    
    for cls in analysis.classes:
        for base in cls.base_classes:
            base_name = base.split("[")[0].split(".")[-1]
            if base_name in class_names:
                lines.append(f"    {cls.name} --|> {base_name}")
    
    return "\n".join(lines)


def generate_all_diagrams(
    analyses: List[FileAnalysis],
    root: Path,
) -> Dict[str, str]:
    return {
        "class_diagram": generate_class_diagram(analyses, root),
        "dependency_graph": generate_dependency_graph(analyses, root),
        "inheritance_diagram": generate_inheritance_diagram(analyses, root),
    }
