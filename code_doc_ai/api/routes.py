from __future__ import annotations

import io
import tempfile
import zipfile
import shutil
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Header, Depends
from fastapi.responses import Response

from ..core import analyze_project, analyze_file, build_class_relationships, get_metrics
from .auth import get_current_user, get_user_id
from .usage import check_rate_limit, log_usage
from ..generators import generate_class_diagram, generate_dependency_graph, generate_inheritance_diagram
from ..generators.pdf import generate_pdf
from .github import get_user_repos, get_repo_python_files
from ..llm import LLMFactory

from .schemas import (
    AnalyzeRequest,
    ProjectAnalysisResponse,
    FileAnalysisResponse,
    ClassInfoResponse,
    FunctionInfoResponse,
    UMLRequest,
    UMLResponse,
    RelationshipResponse,
    DocstringRequest,
    DocstringResponse,
    ProjectDocsRequest,
    ProjectDocsResponse,
    HealthResponse,
    ErrorResponse,
    AnalyzeTextRequest,
    CodeFileInput,
    UnifiedAnalysisResponse,
    DocsTextRequest,
    UMLTextRequest,
    ExportPDFRequest,
    GitHubRepoRequest,
)

router = APIRouter()


async def _check_auth_and_rate_limit(
    authorization: Optional[str] = None,
    endpoint: str = "unknown",
) -> Optional[str]:
    user = await get_current_user(authorization)
    if not user:
        return None
    
    user_id = get_user_id(user)
    allowed, remaining = await check_rate_limit(user_id)
    
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Daily rate limit exceeded. Limit resets at midnight UTC.",
        )
    
    return user_id


def _sanitize_filename(filename: str) -> Optional[str]:
    """Sanitize filename to prevent path traversal attacks."""
    if not filename:
        return None
    name = Path(filename).name
    if not name or name == ".." or "/" in name or "\\" in name:
        return None
    if name.startswith("."):
        return None
    if not name.endswith(".py"):
        return None
    return name


def _safe_extract_zip(zip_ref: zipfile.ZipFile, dest_path: Path) -> bool:
    """Safely extract ZIP contents, preventing path traversal (Zip Slip)."""
    dest_path = dest_path.resolve()
    for member in zip_ref.namelist():
        if member.startswith("/") or ".." in member:
            return False
        member_path = (dest_path / member).resolve()
        try:
            member_path.relative_to(dest_path)
        except ValueError:
            return False
    zip_ref.extractall(dest_path)
    return True


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    return HealthResponse(
        status="healthy",
        llm_available=LLMFactory.is_available(),
        available_providers=LLMFactory.list_providers(),
    )


@router.post("/analyze", response_model=ProjectAnalysisResponse, tags=["Analysis"])
async def analyze_project_endpoint(request: AnalyzeRequest):
    project_path = Path(request.project_path).resolve()
    
    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project path not found: {project_path}")
    
    if not project_path.is_dir():
        raise HTTPException(status_code=400, detail="Project path must be a directory")
    
    try:
        analyses = analyze_project(project_path)
        metrics = get_metrics(analyses)
        
        files = []
        for analysis in analyses:
            classes = [
                ClassInfoResponse(
                    name=cls.name,
                    lineno=cls.lineno,
                    end_lineno=cls.end_lineno,
                    has_docstring=cls.has_docstring,
                    methods=[m.name for m in cls.methods],
                    base_classes=cls.base_classes,
                    attributes=[a.name for a in cls.attributes],
                    decorators=cls.decorators,
                )
                for cls in analysis.classes
            ]
            
            functions = [
                FunctionInfoResponse(
                    name=fn.name,
                    lineno=fn.lineno,
                    end_lineno=fn.end_lineno,
                    has_docstring=fn.has_docstring,
                    parameters=[f"{p[0]}: {p[1]}" if p[1] else p[0] for p in fn.parameters],
                    return_type=fn.return_type,
                    is_async=fn.is_async,
                    decorators=fn.decorators,
                )
                for fn in analysis.functions
            ]
            
            files.append(FileAnalysisResponse(
                path=str(analysis.path.relative_to(project_path)),
                classes=classes,
                functions=functions,
                module_docstring=analysis.module_docstring,
                lines_of_code=analysis.lines_of_code,
                import_count=len(analysis.imports),
            ))
        
        return ProjectAnalysisResponse(
            project_path=str(project_path),
            files=files,
            metrics=metrics,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/uml", response_model=UMLResponse, tags=["UML"])
async def generate_uml_endpoint(request: UMLRequest):
    project_path = Path(request.project_path).resolve()
    
    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project path not found: {project_path}")
    
    try:
        analyses = analyze_project(project_path)
        relationships = build_class_relationships(analyses, project_path)
        
        class_diagram = generate_class_diagram(
            analyses, project_path,
            include_methods=request.include_methods,
            include_attributes=request.include_attributes,
            max_methods=request.max_methods,
        )
        dependency_graph = generate_dependency_graph(analyses, project_path)
        inheritance_diagram = generate_inheritance_diagram(analyses, project_path)
        
        class_rels = [
            RelationshipResponse(
                from_entity=rel.from_class,
                to_entity=rel.to_class,
                relationship_type=rel.relationship_type,
                label=rel.label,
            )
            for rel in relationships.class_relationships
        ]
        
        return UMLResponse(
            class_diagram=class_diagram,
            dependency_graph=dependency_graph,
            inheritance_diagram=inheritance_diagram,
            class_relationships=class_rels,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/docstring", response_model=DocstringResponse, tags=["Docstring"])
async def generate_docstring_endpoint(request: DocstringRequest):
    provider = LLMFactory.get_provider(
        provider_name=request.provider,
        api_key=request.api_key,
    )
    
    if not provider:
        raise HTTPException(
            status_code=400,
            detail="No LLM provider available. Provide API key or set GROQ_API_KEY/GOOGLE_API_KEY environment variable."
        )
    
    try:
        if request.docstring_type == "function":
            prompt = f"""You are an expert Python developer.

Write a concise, accurate docstring for the following Python function or method.

Requirements:
- Google-style docstring.
- Describe purpose, arguments, return value, and side effects (if any).
- Be strictly consistent with the code (no hallucinations).
- DO NOT include the function signature.
- DO NOT wrap the docstring in quotes. Return ONLY the inner text.

Code:
```python
{request.code}
```"""
        else:
            prompt = f"""You are an expert Python developer.

Write a concise, accurate docstring for the following Python class.

Requirements:
- Google-style docstring.
- Describe the purpose of the class, its main responsibilities, and important attributes or methods.
- Be strictly consistent with the code (no hallucinations).
- DO NOT include the class signature.
- DO NOT wrap the docstring in quotes. Return ONLY the inner text.

Code:
```python
{request.code}
```"""
        
        docstring = provider.generate(prompt).strip()
        
        return DocstringResponse(
            docstring=docstring,
            provider_used=provider.provider_name,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/docs", response_model=ProjectDocsResponse, tags=["Documentation"])
async def generate_docs_endpoint(request: ProjectDocsRequest):
    project_path = Path(request.project_path).resolve()
    
    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project path not found: {project_path}")
    
    provider = LLMFactory.get_provider(
        provider_name=request.provider,
        api_key=request.api_key,
    )
    
    try:
        analyses = analyze_project(project_path)
        metrics = get_metrics(analyses)
        
        uml_diagrams = {}
        if request.include_uml:
            uml_diagrams["class_diagram"] = generate_class_diagram(analyses, project_path)
            uml_diagrams["dependency_graph"] = generate_dependency_graph(analyses, project_path)
            uml_diagrams["inheritance_diagram"] = generate_inheritance_diagram(analyses, project_path)
        
        project_overview = _build_project_overview(analyses, project_path, metrics, uml_diagrams, provider)
        
        module_docs = {}
        if request.include_module_docs:
            for analysis in analyses:
                rel_path = str(analysis.path.relative_to(project_path))
                module_docs[rel_path] = _build_module_doc(analysis, project_path, provider)
        
        return ProjectDocsResponse(
            project_overview=project_overview,
            module_docs=module_docs,
            uml_diagrams=uml_diagrams,
            metrics=metrics,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _build_project_overview(analyses, project_path, metrics, uml_diagrams, provider) -> str:
    outline_lines = []
    for analysis in analyses:
        rel_path = analysis.path.relative_to(project_path)
        outline_lines.append(f"File: {rel_path}")
        if analysis.classes:
            outline_lines.append("  Classes:")
            for cls in analysis.classes:
                outline_lines.append(f"    - {cls.name}")
        if analysis.functions:
            outline_lines.append("  Functions:")
            for fn in analysis.functions:
                outline_lines.append(f"    - {fn.name}")
    outline = "\n".join(outline_lines)
    
    metrics_str = "\n".join([f"- {k}: {v}" for k, v in metrics.items()])
    class_diagram = uml_diagrams.get("class_diagram", "")
    
    if provider:
        prompt = f"""You are an expert software architect.

You are given a high-level outline of a Python project:

Project outline:
{outline}

Project metrics:
{metrics_str}

UML Class Diagram (Mermaid):
```mermaid
{class_diagram}
```

Write a Markdown documentation page for this project.

Structure it as:

# Project Overview
Short description of what the project does.

# Architecture
How the project is structured (modules, layers, responsibilities).

# Class Diagram
Include the Mermaid diagram in a code block.

# Modules
Brief bullet-point description of the main modules and what they do.

# Metrics
Summary of the project metrics.

Keep it concise, accurate, and helpful to a new developer joining the project."""
        
        try:
            return provider.generate(prompt).strip()
        except Exception:
            pass
    
    return f"""# Project Overview

*Documentation generation requires API key.*

## Metrics
{metrics_str}

## Class Diagram
```mermaid
{class_diagram}
```
"""


def _build_module_doc(analysis, project_path, provider) -> str:
    rel_path = analysis.path.relative_to(project_path)
    short_name = rel_path.stem
    
    outline_lines = [f"File: {rel_path}"]
    if analysis.classes:
        outline_lines.append("Classes:")
        for cls in analysis.classes:
            outline_lines.append(f"  - {cls.name}")
            for m in cls.methods:
                outline_lines.append(f"    * {m.name}")
    if analysis.functions:
        outline_lines.append("Functions:")
        for fn in analysis.functions:
            outline_lines.append(f"  - {fn.name}")
    outline = "\n".join(outline_lines)
    
    if provider:
        source = analysis.path.read_text(encoding="utf-8")
        excerpt = "\n".join(source.splitlines()[:120])
        
        prompt = f"""You are an expert software engineer and technical writer.

You are given information about a single Python module.

File path: {rel_path}

High-level outline of its contents:
{outline}

Code excerpt (may be truncated):
```python
{excerpt}
```

Write clear, helpful documentation for this module in Markdown.

Requirements:
- Start with a level-2 heading: "## {short_name} Module"
- Provide a short overview paragraph of what this module does.
- Add a "Key Classes and Functions" section with bullet points.
- Add a "Usage Notes" section if there are any important behaviors or edge cases.
- Do NOT repeat the full code."""
        
        try:
            return provider.generate(prompt).strip()
        except Exception:
            pass
    
    return f"""## {short_name} Module

*Documentation generation requires API key.*

{outline}
"""


def _generate_class_description(cls_data: dict, provider) -> str:
    name = cls_data.get("name", "")
    methods = cls_data.get("methods", [])
    attrs = cls_data.get("attributes", [])
    bases = cls_data.get("base_classes", [])

    prompt = f"""You are a technical documentation writer. Write a concise 1-2 sentence description of this Python class.

Class: {name}
Base classes: {', '.join(bases) if bases else 'None'}
Methods: {', '.join(methods[:10])}
Attributes: {', '.join(attrs[:10])}

Write only the description, no formatting or markdown. Be specific about what this class does based on its name, methods, and attributes."""

    try:
        return provider.generate(prompt).strip()
    except Exception:
        return ""


def _generate_function_description(fn_data: dict, provider) -> str:
    name = fn_data.get("name", "")
    params = fn_data.get("parameters", [])
    ret = fn_data.get("return_type", "")

    prompt = f"""You are a technical documentation writer. Write a concise 1-2 sentence description of this Python function.

Function: {name}
Parameters: {', '.join(params[:8])}
Return type: {ret or 'None'}

Write only the description, no formatting or markdown. Be specific about what this function does based on its name and parameters."""

    try:
        return provider.generate(prompt).strip()
    except Exception:
        return ""


def _build_unified_response(
    analyses,
    project_path: Path,
    generate_docs: bool = False,
    api_key: Optional[str] = None,
) -> UnifiedAnalysisResponse:
    try:
        metrics = get_metrics(analyses)
        relationships = build_class_relationships(analyses, project_path)
        
        class_diagram = generate_class_diagram(analyses, project_path)
        dependency_graph = generate_dependency_graph(analyses, project_path)
        inheritance_diagram = generate_inheritance_diagram(analyses, project_path)
        
        files_data = []
        for analysis in analyses:
            rel_path = str(analysis.path.relative_to(project_path))
            classes = [
                {
                    "name": cls.name,
                    "methods": [m.name for m in cls.methods],
                    "attributes": [a.name for a in cls.attributes],
                    "base_classes": cls.base_classes,
                }
                for cls in analysis.classes
            ]
            functions = [
                {
                    "name": fn.name,
                    "parameters": [f"{p[0]}: {p[1]}" if p[1] else p[0] for p in fn.parameters],
                    "return_type": fn.return_type,
                }
                for fn in analysis.functions
            ]
            files_data.append({
                "path": rel_path,
                "classes": classes,
                "functions": functions,
            })
        
        analysis_data = {
            "files": files_data,
            "metrics": metrics,
        }
        
        uml_data = {
            "class_diagram": class_diagram,
            "dependency_graph": dependency_graph,
            "inheritance_diagram": inheritance_diagram,
        }
        
        class_rels = [
            RelationshipResponse(
                from_entity=rel.from_class,
                to_entity=rel.to_class,
                relationship_type=rel.relationship_type,
                label=rel.label,
            )
            for rel in relationships.class_relationships
        ]
        
        documentation = None
        if generate_docs:
            provider = LLMFactory.get_provider(api_key=api_key)
            if provider:
                documentation = _build_project_overview(
                    analyses, project_path, metrics, uml_data, provider
                )
        
        return UnifiedAnalysisResponse(
            success=True,
            analysis=analysis_data,
            uml=uml_data,
            documentation=documentation,
            relationships=class_rels,
        )
    except Exception as e:
        return UnifiedAnalysisResponse(
            success=False,
            error=str(e),
        )


@router.post("/analyze-text", response_model=UnifiedAnalysisResponse, tags=["Upload"])
async def analyze_text_endpoint(
    request: AnalyzeTextRequest,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    """
    Analyze Python code submitted as text.
    
    Pass code content directly without needing file uploads.
    For AI documentation, provide LLM API key in X-API-Key header.
    For rate limiting (optional), provide Supabase JWT in Authorization header.
    """
    user_id = await _check_auth_and_rate_limit(authorization, "analyze-text")
    
    if not request.files:
        return UnifiedAnalysisResponse(success=False, error="No files provided")
    
    py_files = [f for f in request.files if f.filename.endswith(".py")]
    if not py_files:
        return UnifiedAnalysisResponse(success=False, error="No Python files found")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        for file_input in py_files:
            safe_name = _sanitize_filename(file_input.filename)
            if not safe_name:
                continue
            file_path = temp_path / safe_name
            file_path.write_text(file_input.content, encoding="utf-8")
        
        analyses = analyze_project(temp_path)
        result = _build_unified_response(
            analyses, temp_path,
            generate_docs=request.generate_docs,
            api_key=x_api_key,
        )
        
        if user_id and result.success:
            await log_usage(user_id, "analyze-text", len(py_files))
        
        return result


@router.post("/upload-files", response_model=UnifiedAnalysisResponse, tags=["Upload"])
async def upload_files_endpoint(
    files: List[UploadFile] = File(..., description="Python files to analyze"),
    generate_docs: bool = Form(False, description="Generate AI documentation"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    """
    Upload Python files for analysis.
    
    Upload multiple .py files using multipart/form-data.
    For AI documentation, provide LLM API key in X-API-Key header.
    For rate limiting (optional), provide Supabase JWT in Authorization header.
    """
    user_id = await _check_auth_and_rate_limit(authorization, "upload-files")
    
    if not files:
        return UnifiedAnalysisResponse(success=False, error="No files uploaded")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        file_count = 0
        
        for upload_file in files:
            safe_name = _sanitize_filename(upload_file.filename or "")
            if not safe_name:
                continue
            content = await upload_file.read()
            file_path = temp_path / safe_name
            file_path.write_bytes(content)
            file_count += 1
        
        if file_count == 0:
            return UnifiedAnalysisResponse(success=False, error="No valid Python files found")
        
        analyses = analyze_project(temp_path)
        result = _build_unified_response(
            analyses, temp_path,
            generate_docs=generate_docs,
            api_key=x_api_key,
        )
        
        if user_id and result.success:
            await log_usage(user_id, "upload-files", file_count)
        
        return result


@router.post("/upload-zip", response_model=UnifiedAnalysisResponse, tags=["Upload"])
async def upload_zip_endpoint(
    file: UploadFile = File(..., description="ZIP file containing Python project"),
    generate_docs: bool = Form(False, description="Generate AI documentation"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    """
    Upload a ZIP file containing a Python project.
    
    The ZIP will be extracted and all .py files analyzed.
    For AI documentation, provide LLM API key in X-API-Key header.
    For rate limiting (optional), provide Supabase JWT in Authorization header.
    """
    user_id = await _check_auth_and_rate_limit(authorization, "upload-zip")
    
    if not file.filename or not file.filename.endswith(".zip"):
        return UnifiedAnalysisResponse(success=False, error="File must be a .zip file")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        try:
            content = await file.read()
            with zipfile.ZipFile(io.BytesIO(content), 'r') as zip_ref:
                if not _safe_extract_zip(zip_ref, temp_path):
                    return UnifiedAnalysisResponse(
                        success=False, 
                        error="Invalid ZIP file: contains path traversal"
                    )
        except zipfile.BadZipFile:
            return UnifiedAnalysisResponse(success=False, error="Invalid ZIP file")
        
        py_files = list(temp_path.rglob("*.py"))
        if not py_files:
            return UnifiedAnalysisResponse(success=False, error="No Python files found in ZIP")
        
        analyses = analyze_project(temp_path)
        result = _build_unified_response(
            analyses, temp_path,
            generate_docs=generate_docs,
            api_key=x_api_key,
        )
        
        if user_id and result.success:
            await log_usage(user_id, "upload-zip", len(py_files))
        
        return result


@router.post("/docs-text", response_model=ProjectDocsResponse, tags=["Upload"])
async def docs_text_endpoint(
    request: DocsTextRequest,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    """
    Generate documentation from code submitted as text.
    
    Pass code content directly without needing server file paths.
    Requires LLM API key in X-API-Key header for AI documentation.
    For rate limiting (optional), provide Supabase JWT in Authorization header.
    """
    user_id = await _check_auth_and_rate_limit(authorization, "docs-text")
    
    if not request.files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    py_files = [f for f in request.files if f.filename.endswith(".py")]
    if not py_files:
        raise HTTPException(status_code=400, detail="No Python files found")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        for file_input in py_files:
            safe_name = _sanitize_filename(file_input.filename)
            if not safe_name:
                continue
            file_path = temp_path / safe_name
            file_path.write_text(file_input.content, encoding="utf-8")
        
        provider = LLMFactory.get_provider(api_key=x_api_key)
        
        try:
            analyses = analyze_project(temp_path)
            metrics = get_metrics(analyses)
            
            uml_diagrams = {}
            if request.include_uml:
                uml_diagrams["class_diagram"] = generate_class_diagram(analyses, temp_path)
                uml_diagrams["dependency_graph"] = generate_dependency_graph(analyses, temp_path)
                uml_diagrams["inheritance_diagram"] = generate_inheritance_diagram(analyses, temp_path)
            
            project_overview = _build_project_overview(analyses, temp_path, metrics, uml_diagrams, provider)
            
            module_docs = {}
            if request.include_module_docs:
                for analysis in analyses:
                    rel_path = str(analysis.path.relative_to(temp_path))
                    module_docs[rel_path] = _build_module_doc(analysis, temp_path, provider)
            
            if user_id:
                await log_usage(user_id, "docs-text", len(py_files))
            
            return ProjectDocsResponse(
                project_overview=project_overview,
                module_docs=module_docs,
                uml_diagrams=uml_diagrams,
                metrics=metrics,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/uml-text", response_model=UMLResponse, tags=["Upload"])
async def uml_text_endpoint(
    request: UMLTextRequest,
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    """
    Generate UML diagrams from code submitted as text.
    
    Pass code content directly without needing server file paths.
    No LLM API key required - UML generation is done locally with AST parsing.
    For rate limiting (optional), provide Supabase JWT in Authorization header.
    """
    user_id = await _check_auth_and_rate_limit(authorization, "uml-text")
    
    if not request.files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    py_files = [f for f in request.files if f.filename.endswith(".py")]
    if not py_files:
        raise HTTPException(status_code=400, detail="No Python files found")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        for file_input in py_files:
            safe_name = _sanitize_filename(file_input.filename)
            if not safe_name:
                continue
            file_path = temp_path / safe_name
            file_path.write_text(file_input.content, encoding="utf-8")
        
        try:
            analyses = analyze_project(temp_path)
            relationships = build_class_relationships(analyses, temp_path)
            
            class_diagram = generate_class_diagram(
                analyses, temp_path,
                include_methods=request.include_methods,
                include_attributes=request.include_attributes,
                max_methods=request.max_methods,
            )
            dependency_graph = generate_dependency_graph(analyses, temp_path)
            inheritance_diagram = generate_inheritance_diagram(analyses, temp_path)
            
            class_rels = [
                RelationshipResponse(
                    from_entity=rel.from_class,
                    to_entity=rel.to_class,
                    relationship_type=rel.relationship_type,
                    label=rel.label,
                )
                for rel in relationships.class_relationships
            ]
            
            if user_id:
                await log_usage(user_id, "uml-text", len(py_files))
            
            return UMLResponse(
                class_diagram=class_diagram,
                dependency_graph=dependency_graph,
                inheritance_diagram=inheritance_diagram,
                class_relationships=class_rels,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/export-pdf", tags=["Export"])
async def export_pdf_endpoint(
    request: ExportPDFRequest,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_llm_provider: Optional[str] = Header(None, alias="X-LLM-Provider"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    """
    Generate a PDF document from uploaded Python code.
    
    Analyzes code, generates documentation and UML, returns a downloadable PDF.
    Provide LLM API key via X-API-Key header for AI-enhanced documentation.
    Optionally specify provider via X-LLM-Provider header (groq or gemini).
    """
    user_id = await _check_auth_and_rate_limit(authorization, "export-pdf")
    
    if not request.files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    py_files = [f for f in request.files if f.filename.endswith(".py")]
    if not py_files:
        raise HTTPException(status_code=400, detail="No Python files found")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        for file_input in py_files:
            safe_name = _sanitize_filename(file_input.filename)
            if not safe_name:
                continue
            file_path = temp_path / safe_name
            file_path.write_text(file_input.content, encoding="utf-8")
        
        try:
            analyses = analyze_project(temp_path)
            metrics = get_metrics(analyses)
            
            uml_data = None
            if request.include_uml:
                uml_data = {
                    "class_diagram": generate_class_diagram(analyses, temp_path),
                    "dependency_graph": generate_dependency_graph(analyses, temp_path),
                    "inheritance_diagram": generate_inheritance_diagram(analyses, temp_path),
                }
            
            analysis_data = None
            relationships_data = None
            if request.include_analysis:
                relationships = build_class_relationships(analyses, temp_path)
                files_data = []
                for analysis in analyses:
                    rel_path = str(analysis.path.relative_to(temp_path))
                    classes = [
                        {
                            "name": cls.name,
                            "methods": [m.name for m in cls.methods],
                            "attributes": [a.name for a in cls.attributes],
                            "base_classes": cls.base_classes,
                        }
                        for cls in analysis.classes
                    ]
                    functions = [
                        {
                            "name": fn.name,
                            "parameters": [f"{p[0]}: {p[1]}" if p[1] else p[0] for p in fn.parameters],
                            "return_type": fn.return_type,
                        }
                        for fn in analysis.functions
                    ]
                    files_data.append({"path": rel_path, "classes": classes, "functions": functions})
                
                analysis_data = {"files": files_data, "metrics": metrics}
                relationships_data = [
                    {
                        "from_entity": r.from_class,
                        "to_entity": r.to_class,
                        "relationship_type": r.relationship_type,
                        "label": r.label,
                    }
                    for r in relationships.class_relationships
                ]
            
            documentation = None
            module_docs = None
            provider = LLMFactory.get_provider(provider_name=x_llm_provider, api_key=x_api_key)
            llm_used = False
            if provider:
                llm_used = True
                documentation = _build_project_overview(analyses, temp_path, metrics, uml_data or {}, provider)
                if request.include_module_docs:
                    module_docs = {}
                    for analysis in analyses:
                        rel_path = str(analysis.path.relative_to(temp_path))
                        module_docs[rel_path] = _build_module_doc(analysis, temp_path, provider)
                if analysis_data and analysis_data.get("files"):
                    for file_data in analysis_data["files"]:
                        for cls in file_data.get("classes", []):
                            cls["description"] = _generate_class_description(cls, provider)
                        for fn in file_data.get("functions", []):
                            fn["description"] = _generate_function_description(fn, provider)
            
            pdf_bytes = generate_pdf(
                project_name=request.project_name,
                analysis=analysis_data,
                uml=uml_data,
                documentation=documentation,
                module_docs=module_docs,
                relationships=relationships_data,
                metrics=metrics,
            )
            
            if user_id:
                await log_usage(user_id, "export-pdf", len(py_files))
            
            filename = f"{request.project_name.replace(' ', '_')}_documentation.pdf"
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/github/repos", tags=["GitHub"])
async def list_github_repos(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_github_token: Optional[str] = Header(None, alias="X-GitHub-Token"),
    page: int = 1,
    per_page: int = 30,
):
    """
    List the authenticated user's GitHub repositories.
    
    Requires GitHub access token in X-GitHub-Token header.
    The token can come from Supabase GitHub OAuth or a personal access token.
    """
    if not x_github_token:
        raise HTTPException(
            status_code=400,
            detail="GitHub access token required. Provide X-GitHub-Token header."
        )
    
    try:
        repos = await get_user_repos(x_github_token, page, per_page)
        return {"repos": repos, "page": page, "per_page": per_page}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/github/analyze", response_model=UnifiedAnalysisResponse, tags=["GitHub"])
async def analyze_github_repo(
    request: GitHubRepoRequest,
    x_github_token: Optional[str] = Header(None, alias="X-GitHub-Token"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    """
    Fetch and analyze a GitHub repository's Python code.
    
    Requires GitHub access token in X-GitHub-Token header.
    For AI documentation, provide LLM API key in X-API-Key header.
    """
    user_id = await _check_auth_and_rate_limit(authorization, "github-analyze")
    
    if not x_github_token:
        raise HTTPException(
            status_code=400,
            detail="GitHub access token required. Provide X-GitHub-Token header."
        )
    
    parts = request.repo_full_name.split("/")
    if len(parts) != 2:
        raise HTTPException(
            status_code=400,
            detail="repo_full_name must be in format 'owner/repo'"
        )
    
    owner, repo = parts
    project_name = request.project_name or repo
    
    try:
        files = await get_repo_python_files(
            x_github_token, owner, repo, request.branch
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch GitHub repo: {str(e)}")
    
    if not files:
        return UnifiedAnalysisResponse(
            success=False,
            error=f"No Python files found in {request.repo_full_name} (branch: {request.branch})"
        )
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        for file_data in files:
            file_path = temp_path / Path(file_data["filename"]).name
            file_path.write_text(file_data["content"], encoding="utf-8")
        
        result = _build_unified_response(
            analyze_project(temp_path),
            temp_path,
            generate_docs=request.generate_docs,
            api_key=x_api_key,
        )
        
        if user_id and result.success:
            await log_usage(user_id, "github-analyze", len(files))
        
        return result


@router.post("/github/export-pdf", tags=["GitHub"])
async def export_github_pdf(
    request: GitHubRepoRequest,
    x_github_token: Optional[str] = Header(None, alias="X-GitHub-Token"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    """
    Fetch a GitHub repo and generate a PDF documentation.
    
    Requires GitHub access token in X-GitHub-Token header.
    For AI documentation, provide LLM API key in X-API-Key header.
    """
    user_id = await _check_auth_and_rate_limit(authorization, "github-export-pdf")
    
    if not x_github_token:
        raise HTTPException(
            status_code=400,
            detail="GitHub access token required. Provide X-GitHub-Token header."
        )
    
    parts = request.repo_full_name.split("/")
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="repo_full_name must be 'owner/repo'")
    
    owner, repo = parts
    project_name = request.project_name or repo
    
    try:
        files = await get_repo_python_files(
            x_github_token, owner, repo, request.branch
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch GitHub repo: {str(e)}")
    
    if not files:
        raise HTTPException(status_code=404, detail="No Python files found in repository")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        for file_data in files:
            file_path = temp_path / Path(file_data["filename"]).name
            file_path.write_text(file_data["content"], encoding="utf-8")
        
        try:
            analyses = analyze_project(temp_path)
            metrics = get_metrics(analyses)
            relationships = build_class_relationships(analyses, temp_path)
            
            uml_data = None
            if request.include_uml:
                uml_data = {
                    "class_diagram": generate_class_diagram(analyses, temp_path),
                    "dependency_graph": generate_dependency_graph(analyses, temp_path),
                    "inheritance_diagram": generate_inheritance_diagram(analyses, temp_path),
                }
            
            files_data = []
            for analysis in analyses:
                rel_path = str(analysis.path.relative_to(temp_path))
                classes = [
                    {"name": cls.name, "methods": [m.name for m in cls.methods],
                     "attributes": [a.name for a in cls.attributes], "base_classes": cls.base_classes}
                    for cls in analysis.classes
                ]
                functions = [
                    {"name": fn.name, "parameters": [f"{p[0]}: {p[1]}" if p[1] else p[0] for p in fn.parameters],
                     "return_type": fn.return_type}
                    for fn in analysis.functions
                ]
                files_data.append({"path": rel_path, "classes": classes, "functions": functions})
            
            analysis_data = {"files": files_data, "metrics": metrics}
            
            documentation = None
            module_docs = None
            provider = LLMFactory.get_provider(api_key=x_api_key)
            if provider and request.generate_docs:
                documentation = _build_project_overview(analyses, temp_path, metrics, uml_data or {}, provider)
            
            rel_data = [
                {"from_entity": r.from_class, "to_entity": r.to_class,
                 "relationship_type": r.relationship_type, "label": r.label}
                for r in relationships.class_relationships
            ]
            
            pdf_bytes = generate_pdf(
                project_name=project_name,
                analysis=analysis_data,
                uml=uml_data,
                documentation=documentation,
                module_docs=module_docs,
                relationships=rel_data,
                metrics=metrics,
            )
            
            if user_id:
                await log_usage(user_id, "github-export-pdf", len(files))
            
            filename = f"{project_name}_documentation.pdf"
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
