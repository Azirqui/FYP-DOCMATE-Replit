from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set, Dict, Tuple


@dataclass
class AttributeInfo:
    name: str
    type_hint: Optional[str] = None
    is_class_attribute: bool = False


@dataclass
class FunctionInfo:
    name: str
    lineno: int
    end_lineno: int
    has_docstring: bool
    parent_class: Optional[str] = None
    parameters: List[Tuple[str, Optional[str]]] = field(default_factory=list)
    return_type: Optional[str] = None
    is_async: bool = False
    decorators: List[str] = field(default_factory=list)


@dataclass
class ClassInfo:
    name: str
    lineno: int
    end_lineno: int
    has_docstring: bool
    methods: List[FunctionInfo] = field(default_factory=list)
    base_classes: List[str] = field(default_factory=list)
    attributes: List[AttributeInfo] = field(default_factory=list)
    decorators: List[str] = field(default_factory=list)


@dataclass
class ImportInfo:
    module: str
    names: List[str]
    alias: Optional[str] = None
    is_from_import: bool = False
    lineno: int = 0
    level: int = 0


@dataclass
class FileAnalysis:
    path: Path
    functions: List[FunctionInfo] = field(default_factory=list)
    classes: List[ClassInfo] = field(default_factory=list)
    imports: List[ImportInfo] = field(default_factory=list)
    module_docstring: Optional[str] = None
    lines_of_code: int = 0
    used_names: Set[str] = field(default_factory=set)


@dataclass
class ClassRelationship:
    from_class: str
    to_class: str
    relationship_type: str
    label: Optional[str] = None


@dataclass
class FileRelationship:
    from_file: str
    to_file: str
    imported_names: List[str] = field(default_factory=list)


@dataclass
class ProjectRelationships:
    class_relationships: List[ClassRelationship] = field(default_factory=list)
    file_relationships: List[FileRelationship] = field(default_factory=list)
    class_to_file: Dict[str, str] = field(default_factory=dict)
    all_classes: Set[str] = field(default_factory=set)
    inheritance_hierarchy: Dict[str, List[str]] = field(default_factory=dict)
