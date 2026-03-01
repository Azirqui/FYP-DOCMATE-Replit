#!/usr/bin/env python3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from code_doc_ai.app.parser import analyze_project, analyze_file
from code_doc_ai.app.uml_generator import (
    generate_class_diagram,
    generate_dependency_graph,
    generate_inheritance_diagram,
)
from code_doc_ai.app.relationship_mapper import (
    build_class_relationships,
    build_file_relationships,
    get_metrics,
)

def main():
    test_dir = Path("test_sample")
    
    if not test_dir.exists():
        print("Error: test_sample directory not found")
        return 1
    
    print("=" * 60)
    print("AI CODE DOCUMENTATION GENERATOR - UML DEMO")
    print("=" * 60)
    print()
    
    print("[1] Analyzing project structure...")
    analyses = analyze_project(test_dir)
    print(f"    Found {len(analyses)} Python files")
    
    for analysis in analyses:
        print(f"    - {analysis.path.name}: {len(analysis.classes)} classes, "
              f"{len(analysis.functions)} functions, {len(analysis.imports)} imports")
    print()
    
    print("[2] Extracting code metrics...")
    metrics = get_metrics(analyses)
    for key, value in metrics.items():
        if isinstance(value, float):
            print(f"    {key}: {value:.1f}")
        else:
            print(f"    {key}: {value}")
    print()
    
    print("[3] Building class relationships...")
    relationships = build_class_relationships(analyses, test_dir)
    print(f"    Found {len(relationships.all_classes)} classes")
    print(f"    Found {len(relationships.class_relationships)} relationships")
    
    for rel in relationships.class_relationships:
        print(f"      - {rel.from_class} --{rel.relationship_type}--> {rel.to_class}")
    print()
    
    print("[4] Generating Mermaid Class Diagram...")
    class_diagram = generate_class_diagram(analyses, test_dir)
    print()
    print("```mermaid")
    print(class_diagram)
    print("```")
    print()
    
    print("[5] Generating Mermaid Dependency Graph...")
    dep_graph = generate_dependency_graph(analyses, test_dir)
    print()
    print("```mermaid")
    print(dep_graph)
    print("```")
    print()
    
    print("[6] Generating Inheritance Diagram...")
    inheritance_diagram = generate_inheritance_diagram(analyses, test_dir)
    if inheritance_diagram:
        print()
        print("```mermaid")
        print(inheritance_diagram)
        print("```")
    else:
        print("    No inheritance relationships found")
    print()
    
    print("=" * 60)
    print("UML GENERATION COMPLETE!")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
