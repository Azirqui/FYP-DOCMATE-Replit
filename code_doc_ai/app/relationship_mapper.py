from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple

from .parser import FileAnalysis, ClassInfo, ImportInfo


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


def _extract_class_names_from_type(type_str: str, all_classes: Set[str]) -> Set[str]:
    import re
    found = set()
    identifiers = re.findall(r'\b([A-Z][a-zA-Z0-9_]*)\b', type_str)
    for ident in identifiers:
        base_name = ident.split(".")[-1]
        if base_name in all_classes:
            found.add(base_name)
    return found


def _find_class_usages_in_class(cls: ClassInfo, all_classes: Set[str]) -> List[Tuple[str, str]]:
    usages: List[Tuple[str, str]] = []
    
    for attr in cls.attributes:
        if attr.type_hint:
            found_classes = _extract_class_names_from_type(attr.type_hint, all_classes)
            for other_class in found_classes:
                if other_class != cls.name:
                    usages.append((other_class, "composition"))
    
    for method in cls.methods:
        for param_name, param_type in method.parameters:
            if param_type:
                found_classes = _extract_class_names_from_type(param_type, all_classes)
                for other_class in found_classes:
                    if other_class != cls.name:
                        usages.append((other_class, "dependency"))
        
        if method.return_type:
            found_classes = _extract_class_names_from_type(method.return_type, all_classes)
            for other_class in found_classes:
                if other_class != cls.name:
                    usages.append((other_class, "dependency"))
    
    return usages


def build_class_relationships(analyses: List[FileAnalysis], root: Path) -> ProjectRelationships:
    result = ProjectRelationships()
    
    for analysis in analyses:
        rel_path = str(analysis.path.relative_to(root))
        for cls in analysis.classes:
            result.all_classes.add(cls.name)
            result.class_to_file[cls.name] = rel_path
    
    for analysis in analyses:
        for cls in analysis.classes:
            for base in cls.base_classes:
                base_name = base.split("[")[0].split(".")[-1]
                
                if base_name in result.all_classes:
                    result.class_relationships.append(ClassRelationship(
                        from_class=cls.name,
                        to_class=base_name,
                        relationship_type="inheritance",
                        label="extends",
                    ))
                    
                    if base_name not in result.inheritance_hierarchy:
                        result.inheritance_hierarchy[base_name] = []
                    result.inheritance_hierarchy[base_name].append(cls.name)
            
            usages = _find_class_usages_in_class(cls, result.all_classes)
            seen_usages: Set[Tuple[str, str]] = set()
            
            for target_class, rel_type in usages:
                key = (target_class, rel_type)
                if key not in seen_usages:
                    seen_usages.add(key)
                    result.class_relationships.append(ClassRelationship(
                        from_class=cls.name,
                        to_class=target_class,
                        relationship_type=rel_type,
                        label="has" if rel_type == "composition" else "uses",
                    ))
    
    return result


def _resolve_relative_import(
    from_file: str, 
    imp: ImportInfo, 
    file_to_modules: Dict[str, str],
    name_to_files: Dict[str, List[str]]
) -> List[str]:
    from pathlib import PurePosixPath
    
    if imp.level == 0:
        return []
    
    resolved: List[str] = []
    from_path = PurePosixPath(from_file)
    
    current_package = from_path.parent
    for _ in range(imp.level - 1):
        current_package = current_package.parent
    
    package_prefix = str(current_package).replace("\\", "/")
    if package_prefix == ".":
        package_prefix = ""
    
    if imp.module:
        module_parts = imp.module.replace(".", "/")
        if package_prefix:
            target_base = f"{package_prefix}/{module_parts}"
        else:
            target_base = module_parts
        
        target_py = target_base + ".py"
        target_init = target_base + "/__init__.py"
        
        for file_path in file_to_modules.values():
            normalized = file_path.replace("\\", "/")
            if normalized == target_py or normalized == target_init:
                resolved.append(file_path)
                break
    
    for name in imp.names:
        if package_prefix:
            target_py = f"{package_prefix}/{name}.py"
        else:
            target_py = f"{name}.py"
        
        for file_path in file_to_modules.values():
            normalized = file_path.replace("\\", "/")
            if normalized == target_py:
                if file_path not in resolved:
                    resolved.append(file_path)
                break
        
        if name in name_to_files:
            for candidate in name_to_files[name]:
                cand_normalized = candidate.replace("\\", "/")
                if package_prefix and cand_normalized.startswith(package_prefix):
                    if candidate not in resolved:
                        resolved.append(candidate)
                    break
    
    return resolved


def build_file_relationships(analyses: List[FileAnalysis], root: Path) -> List[FileRelationship]:
    relationships: List[FileRelationship] = []
    
    file_to_modules: Dict[str, str] = {}
    name_to_files: Dict[str, List[str]] = {}
    
    for analysis in analyses:
        rel_path = analysis.path.relative_to(root)
        rel_path_str = str(rel_path).replace("\\", "/")
        module_path = str(rel_path.with_suffix("")).replace("/", ".").replace("\\", ".")
        file_to_modules[module_path] = rel_path_str
        
        stem = rel_path.stem
        file_to_modules[stem] = rel_path_str
        
        if stem not in name_to_files:
            name_to_files[stem] = []
        name_to_files[stem].append(rel_path_str)
    
    for analysis in analyses:
        from_file = str(analysis.path.relative_to(root)).replace("\\", "/")
        
        for imp in analysis.imports:
            target_file: Optional[str] = None
            
            if imp.level > 0:
                resolved_files = _resolve_relative_import(from_file, imp, file_to_modules, name_to_files)
                for target_file in resolved_files:
                    if target_file != from_file:
                        existing = next(
                            (r for r in relationships if r.from_file == from_file and r.to_file == target_file),
                            None
                        )
                        if existing:
                            existing.imported_names.extend(imp.names)
                        else:
                            relationships.append(FileRelationship(
                                from_file=from_file,
                                to_file=target_file,
                                imported_names=imp.names.copy(),
                            ))
                continue
            
            target_file: Optional[str] = None
            
            if not target_file and imp.module:
                if imp.module in file_to_modules:
                    target_file = file_to_modules[imp.module]
                else:
                    module_parts = imp.module.split(".")
                    for i in range(len(module_parts), 0, -1):
                        partial = ".".join(module_parts[:i])
                        if partial in file_to_modules:
                            target_file = file_to_modules[partial]
                            break
            
            if not target_file and imp.is_from_import:
                for name in imp.names:
                    if name in name_to_files:
                        candidates = name_to_files[name]
                        if len(candidates) == 1:
                            target_file = candidates[0]
                            break
                        from_dir = str(Path(from_file).parent).replace("\\", "/")
                        for candidate in candidates:
                            if candidate.startswith(from_dir):
                                target_file = candidate
                                break
            
            if target_file and target_file != from_file:
                existing = next(
                    (r for r in relationships if r.from_file == from_file and r.to_file == target_file),
                    None
                )
                if existing:
                    existing.imported_names.extend(imp.names)
                else:
                    relationships.append(FileRelationship(
                        from_file=from_file,
                        to_file=target_file,
                        imported_names=imp.names.copy(),
                    ))
    
    return relationships


def get_class_hierarchy_depth(class_name: str, inheritance_hierarchy: Dict[str, List[str]], depth: int = 0) -> int:
    if class_name not in inheritance_hierarchy:
        return depth
    
    max_depth = depth
    for child in inheritance_hierarchy[class_name]:
        child_depth = get_class_hierarchy_depth(child, inheritance_hierarchy, depth + 1)
        max_depth = max(max_depth, child_depth)
    
    return max_depth


def get_metrics(analyses: List[FileAnalysis]) -> Dict[str, int | float]:
    total_files = len(analyses)
    total_classes = sum(len(a.classes) for a in analyses)
    total_functions = sum(len(a.functions) for a in analyses)
    total_methods = sum(sum(len(c.methods) for c in a.classes) for a in analyses)
    total_lines = sum(a.lines_of_code for a in analyses)
    
    return {
        "total_files": total_files,
        "total_classes": total_classes,
        "total_functions": total_functions,
        "total_methods": total_methods,
        "total_lines_of_code": total_lines,
        "avg_lines_per_file": total_lines / total_files if total_files > 0 else 0,
    }
