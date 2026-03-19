from __future__ import annotations

import io
import tempfile
import zipfile
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Header, Depends
from fastapi.responses import Response

from ..core import analyze_project, build_class_relationships, get_metrics
from .auth import require_auth, get_user_id
from .usage import check_rate_limit, log_usage
from ..generators import generate_class_diagram, generate_dependency_graph, generate_inheritance_diagram
from ..generators.pdf import generate_pdf
from .github import get_user_repos, get_repo_python_files
from ..llm import LLMFactory
from . import supabase_service

from ..agents.engine import AgentEngine

from .schemas import (
    UMLResponse,
    RelationshipResponse,
    DocstringRequest,
    DocstringResponse,
    ProjectDocsResponse,
    HealthResponse,
    AnalyzeTextRequest,
    UnifiedAnalysisResponse,
    DocsTextRequest,
    UMLTextRequest,
    ExportPDFRequest,
    GitHubRepoRequest,
    ProjectSummaryResponse,
    ProjectDetailResponse,
    DocUpdateRequest,
    DocUpdateResponse,
    ManualDocUpdateRequest,
    ManualDocUpdateResponse,
    SummarizeRequest,
    SummarizeResponse,
    BatchSummarizeRequest,
    BatchSummarizeResponse,
    AgentRunRequest,
    AgentRunResponse,
    AgentTraceResponse,
    AgentStepResponse,
)

router = APIRouter()


async def _check_rate_limit(user_id: str, endpoint: str = "unknown") -> str:
    allowed, remaining = await check_rate_limit(user_id)

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Daily rate limit exceeded. Limit resets at midnight UTC.",
        )

    return user_id


def _sanitize_filename(filename: str) -> Optional[str]:
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


def _sanitize_filepath(filepath: str) -> Optional[str]:
    if not filepath:
        return None
    normalized = filepath.replace("\\", "/")
    if normalized.startswith("/") or ".." in normalized.split("/"):
        return None
    name = Path(normalized).name
    if not name or name.startswith("."):
        return None
    if not name.endswith(".py"):
        return None
    return normalized


def _safe_extract_zip(zip_ref: zipfile.ZipFile, dest_path: Path) -> bool:
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


def _trace_to_response(trace) -> AgentTraceResponse:
    return AgentTraceResponse(
        steps=[
            AgentStepResponse(
                step_number=s.step_number,
                agent_name=s.agent_name,
                role=s.role,
                input_preview=s.input_preview[:500],
                output=s.output,
                duration_seconds=round(s.duration_seconds, 2),
            )
            for s in trace.steps
        ],
        total_duration_seconds=round(trace.total_duration_seconds, 2),
        final_output=trace.final_output,
    )


def _build_project_outline(analyses, project_path: Path) -> str:
    outline_lines = []
    for analysis in analyses:
        rel_path = str(analysis.path.relative_to(project_path))
        outline_lines.append(f"\nFile: {rel_path}")
        if analysis.classes:
            for cls in analysis.classes:
                outline_lines.append(f"  Class: {cls.name}")
                for m in cls.methods:
                    outline_lines.append(f"    Method: {m.name}")
        if analysis.functions:
            for fn in analysis.functions:
                outline_lines.append(f"  Function: {fn.name}")
    return "\n".join(outline_lines)


def _collect_code_excerpts(analyses, project_path: Path) -> dict[str, str]:
    excerpts = {}
    for analysis in analyses:
        rel_path = str(analysis.path.relative_to(project_path))
        try:
            source = analysis.path.read_text(encoding="utf-8")
            excerpts[rel_path] = "\n".join(source.splitlines()[:120])
        except Exception:
            pass
    return excerpts


def _build_project_overview_agentic(analyses, project_path, metrics, uml_diagrams, provider):
    outline = _build_project_outline(analyses, project_path)
    metrics_str = "\n".join([f"- {k}: {v}" for k, v in metrics.items()])
    class_diagram = uml_diagrams.get("class_diagram", "")
    code_excerpts = _collect_code_excerpts(analyses, project_path)

    engine = AgentEngine(provider)
    trace = engine.run_doc_pipeline(
        project_outline=outline,
        metrics_str=metrics_str,
        code_excerpts=code_excerpts,
        class_diagram=class_diagram,
    )
    return trace.final_output, trace


def _build_module_doc_agentic(analysis, project_path, provider):
    rel_path = str(analysis.path.relative_to(project_path))
    short_name = analysis.path.stem

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

    try:
        source = analysis.path.read_text(encoding="utf-8")
        code_excerpt = "\n".join(source.splitlines()[:120])
    except Exception:
        code_excerpt = ""

    engine = AgentEngine(provider)
    trace = engine.run_module_pipeline(
        file_path=rel_path,
        code_excerpt=code_excerpt,
        outline=outline,
    )
    return trace.final_output, trace


@router.post("/docstring", response_model=DocstringResponse, tags=["Docstring"])
async def generate_docstring_endpoint(
    request: DocstringRequest,
    user: dict = Depends(require_auth),
):
    user_id = get_user_id(user)
    await _check_rate_limit(user_id, "docstring")

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

        await log_usage(user_id, "docstring", 1)

        return DocstringResponse(
            docstring=docstring,
            provider_used=provider.provider_name,
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
    user: dict = Depends(require_auth),
):
    user_id = get_user_id(user)
    await _check_rate_limit(user_id, "analyze-text")

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

        if result.success:
            await log_usage(user_id, "analyze-text", len(py_files))

        return result


@router.post("/upload-files", response_model=UnifiedAnalysisResponse, tags=["Upload"])
async def upload_files_endpoint(
    files: List[UploadFile] = File(..., description="Python files to analyze"),
    generate_docs: bool = Form(False, description="Generate AI documentation"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    user: dict = Depends(require_auth),
):
    user_id = get_user_id(user)
    await _check_rate_limit(user_id, "upload-files")

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

        if result.success:
            await log_usage(user_id, "upload-files", file_count)

        return result


@router.post("/upload-zip", response_model=UnifiedAnalysisResponse, tags=["Upload"])
async def upload_zip_endpoint(
    file: UploadFile = File(..., description="ZIP file containing Python project"),
    generate_docs: bool = Form(False, description="Generate AI documentation"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    user: dict = Depends(require_auth),
):
    user_id = get_user_id(user)
    await _check_rate_limit(user_id, "upload-zip")

    if not file.filename or not file.filename.endswith(".zip"):
        return UnifiedAnalysisResponse(success=False, error="File must be a .zip file")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        try:
            content = await file.read()
            zip_buffer = io.BytesIO(content)

            with zipfile.ZipFile(zip_buffer, "r") as zip_ref:
                if not _safe_extract_zip(zip_ref, temp_path):
                    return UnifiedAnalysisResponse(
                        success=False,
                        error="ZIP file contains unsafe paths"
                    )
        except zipfile.BadZipFile:
            return UnifiedAnalysisResponse(success=False, error="Invalid ZIP file")

        py_files = list(temp_path.rglob("*.py"))
        if not py_files:
            return UnifiedAnalysisResponse(success=False, error="No Python files in ZIP")

        analyses = analyze_project(temp_path)
        result = _build_unified_response(
            analyses, temp_path,
            generate_docs=generate_docs,
            api_key=x_api_key,
        )

        if result.success:
            await log_usage(user_id, "upload-zip", len(py_files))

        return result


@router.post("/docs-text", response_model=ProjectDocsResponse, tags=["Documentation"])
async def generate_docs_text_endpoint(
    request: DocsTextRequest,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    user: dict = Depends(require_auth),
):
    user_id = get_user_id(user)
    await _check_rate_limit(user_id, "docs-text")

    if not request.files:
        raise HTTPException(status_code=400, detail="No files provided")

    py_files = [f for f in request.files if f.filename.endswith(".py")]
    if not py_files:
        raise HTTPException(status_code=400, detail="No Python files found")

    provider = LLMFactory.get_provider(api_key=x_api_key)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        for file_input in py_files:
            safe_name = _sanitize_filename(file_input.filename)
            if not safe_name:
                continue
            file_path = temp_path / safe_name
            file_path.write_text(file_input.content, encoding="utf-8")

        analyses = analyze_project(temp_path)
        metrics = get_metrics(analyses)

        uml_diagrams = {}
        if request.include_uml:
            uml_diagrams["class_diagram"] = generate_class_diagram(analyses, temp_path)
            uml_diagrams["dependency_graph"] = generate_dependency_graph(analyses, temp_path)
            uml_diagrams["inheritance_diagram"] = generate_inheritance_diagram(analyses, temp_path)

        agent_trace = None
        if request.use_agents and provider:
            try:
                project_overview, trace = _build_project_overview_agentic(
                    analyses, temp_path, metrics, uml_diagrams, provider
                )
                agent_trace = _trace_to_response(trace)
            except Exception:
                project_overview = _build_project_overview(analyses, temp_path, metrics, uml_diagrams, provider)
        else:
            project_overview = _build_project_overview(analyses, temp_path, metrics, uml_diagrams, provider)

        module_docs = {}
        if request.include_module_docs:
            for analysis in analyses:
                rel_path = str(analysis.path.relative_to(temp_path))
                if request.use_agents and provider:
                    try:
                        doc, _ = _build_module_doc_agentic(analysis, temp_path, provider)
                        module_docs[rel_path] = doc
                    except Exception:
                        module_docs[rel_path] = _build_module_doc(analysis, temp_path, provider)
                else:
                    module_docs[rel_path] = _build_module_doc(analysis, temp_path, provider)

        await log_usage(user_id, "docs-text", len(py_files))

        return ProjectDocsResponse(
            project_overview=project_overview,
            module_docs=module_docs,
            uml_diagrams=uml_diagrams,
            metrics=metrics,
            agent_trace=agent_trace,
        )


@router.post("/uml-text", response_model=UMLResponse, tags=["UML"])
async def generate_uml_text_endpoint(
    request: UMLTextRequest,
    user: dict = Depends(require_auth),
):
    user_id = get_user_id(user)
    await _check_rate_limit(user_id, "uml-text")

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

        await log_usage(user_id, "uml-text", len(py_files))

        return UMLResponse(
            class_diagram=class_diagram,
            dependency_graph=dependency_graph,
            inheritance_diagram=inheritance_diagram,
            class_relationships=class_rels,
        )


@router.post("/export-pdf", tags=["Export"])
async def export_pdf_endpoint(
    request: ExportPDFRequest,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    user: dict = Depends(require_auth),
):
    user_id = get_user_id(user)
    await _check_rate_limit(user_id, "export-pdf")

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

            provider = LLMFactory.get_provider(api_key=x_api_key)
            documentation = None
            module_docs = None

            if provider:
                try:
                    documentation, _ = _build_project_overview_agentic(
                        analyses, temp_path, metrics, uml_data or {}, provider
                    )
                except Exception:
                    documentation = _build_project_overview(analyses, temp_path, metrics, uml_data or {}, provider)

                if request.include_module_docs:
                    module_docs = {}
                    for analysis in analyses:
                        rel_path = str(analysis.path.relative_to(temp_path))
                        try:
                            doc, _ = _build_module_doc_agentic(analysis, temp_path, provider)
                            module_docs[rel_path] = doc
                        except Exception:
                            module_docs[rel_path] = _build_module_doc(analysis, temp_path, provider)

            rel_data = [
                {"from_entity": r.from_class, "to_entity": r.to_class,
                 "relationship_type": r.relationship_type, "label": r.label}
                for r in relationships.class_relationships
            ]

            pdf_bytes = generate_pdf(
                project_name=request.project_name,
                analysis=analysis_data,
                uml=uml_data,
                documentation=documentation,
                module_docs=module_docs,
                relationships=rel_data,
                metrics=metrics,
            )

            await log_usage(user_id, "export-pdf", len(py_files))

            filename = f"{request.project_name}_documentation.pdf"
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/github/repos", tags=["GitHub"])
async def list_github_repos(
    x_github_token: Optional[str] = Header(None, alias="X-GitHub-Token"),
    user: dict = Depends(require_auth),
):
    if not x_github_token:
        raise HTTPException(
            status_code=400,
            detail="GitHub access token required. Provide X-GitHub-Token header."
        )

    try:
        repos = await get_user_repos(x_github_token)
        return {"repos": repos}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch repos: {str(e)}")


@router.post("/github/analyze", tags=["GitHub"])
async def analyze_github_repo(
    request: GitHubRepoRequest,
    x_github_token: Optional[str] = Header(None, alias="X-GitHub-Token"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    user: dict = Depends(require_auth),
):
    user_id = get_user_id(user)
    await _check_rate_limit(user_id, "github-analyze")

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
        raise HTTPException(
            status_code=404,
            detail=f"No Python files found in {request.repo_full_name} (branch: {request.branch})"
        )

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        valid_files = []
        for file_data in files:
            rel_file_path = file_data["filename"]
            safe_path = _sanitize_filepath(rel_file_path)
            if not safe_path:
                safe_name = _sanitize_filename(rel_file_path)
                if not safe_name:
                    continue
                safe_path = safe_name
            full_path = temp_path / safe_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(file_data["content"], encoding="utf-8")
            file_data["_safe_path"] = safe_path
            valid_files.append(file_data)

        if not valid_files:
            raise HTTPException(status_code=404, detail="No valid Python files found in repository")

        analyses = analyze_project(temp_path)
        metrics = get_metrics(analyses)
        relationships = build_class_relationships(analyses, temp_path)

        uml_diagrams = {}
        if request.include_uml:
            uml_diagrams = {
                "class": generate_class_diagram(analyses, temp_path),
                "dependency": generate_dependency_graph(analyses, temp_path),
                "inheritance": generate_inheritance_diagram(analyses, temp_path),
            }

        provider = LLMFactory.get_provider(api_key=x_api_key)
        docs_to_save = []
        documentation = None

        if request.generate_docs:
            uml_for_overview = {
                "class_diagram": uml_diagrams.get("class", ""),
                "dependency_graph": uml_diagrams.get("dependency", ""),
                "inheritance_diagram": uml_diagrams.get("inheritance", ""),
            }
            if provider:
                try:
                    documentation, _ = _build_project_overview_agentic(
                        analyses, temp_path, metrics, uml_for_overview, provider
                    )
                except Exception:
                    documentation = _build_project_overview(analyses, temp_path, metrics, uml_for_overview, provider)
            else:
                documentation = _build_project_overview(analyses, temp_path, metrics, uml_for_overview, provider)
            docs_to_save.append({
                "doc_type": "overview",
                "module_name": None,
                "content": documentation,
            })

            if request.include_module_docs:
                for analysis in analyses:
                    rel_path = str(analysis.path.relative_to(temp_path))
                    if provider:
                        try:
                            module_doc, _ = _build_module_doc_agentic(analysis, temp_path, provider)
                        except Exception:
                            module_doc = _build_module_doc(analysis, temp_path, provider)
                    else:
                        module_doc = _build_module_doc(analysis, temp_path, provider)
                    docs_to_save.append({
                        "doc_type": "module",
                        "module_name": rel_path,
                        "content": module_doc,
                    })

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

        class_rels = [
            RelationshipResponse(
                from_entity=rel.from_class,
                to_entity=rel.to_class,
                relationship_type=rel.relationship_type,
                label=rel.label,
            )
            for rel in relationships.class_relationships
        ]

        if request.save_to_project and supabase_service.is_configured():
            project = await supabase_service.create_project(
                user_id, project_name, f"GitHub: {request.repo_full_name} (branch: {request.branch})"
            )
            if not project:
                raise HTTPException(status_code=500, detail="Failed to create project in database")

            project_id = project["id"]

            try:
                saved_files = [
                    {"filename": Path(f["_safe_path"]).name, "content": f["content"], "file_path": f["_safe_path"]}
                    for f in valid_files
                ]
                await supabase_service.save_files(project_id, saved_files)

                if uml_diagrams:
                    await supabase_service.save_uml(project_id, uml_diagrams)

                if docs_to_save:
                    await supabase_service.save_docs(project_id, docs_to_save)

                await log_usage(user_id, "github-analyze", len(files))

                files_response = await supabase_service.get_project_files(project_id)
                docs_response = await supabase_service.get_project_docs(project_id)
                uml_response = await supabase_service.get_project_uml(project_id)

                return ProjectDetailResponse(
                    id=project_id,
                    name=project.get("name", project_name),
                    description=project.get("description", ""),
                    created_at=project.get("created_at", ""),
                    updated_at=project.get("updated_at", ""),
                    files=files_response,
                    docs=docs_response,
                    uml=uml_response,
                    analysis={"files": files_data, "metrics": metrics},
                    relationships=class_rels,
                )
            except HTTPException:
                raise
            except Exception as e:
                await supabase_service.delete_project(project_id, user_id)
                raise HTTPException(status_code=500, detail=f"Failed to save project: {str(e)}")

        await log_usage(user_id, "github-analyze", len(valid_files))

        uml_response_data = {
            "class_diagram": uml_diagrams.get("class", ""),
            "dependency_graph": uml_diagrams.get("dependency", ""),
            "inheritance_diagram": uml_diagrams.get("inheritance", ""),
        }

        return UnifiedAnalysisResponse(
            success=True,
            analysis={"files": files_data, "metrics": metrics},
            uml=uml_response_data,
            documentation=documentation,
            relationships=class_rels,
        )


@router.post("/github/export-pdf", tags=["GitHub"])
async def export_github_pdf(
    request: GitHubRepoRequest,
    x_github_token: Optional[str] = Header(None, alias="X-GitHub-Token"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    user: dict = Depends(require_auth),
):
    user_id = get_user_id(user)
    await _check_rate_limit(user_id, "github-export-pdf")

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

            await log_usage(user_id, "github-export-pdf", len(files))

            filename = f"{project_name}_documentation.pdf"
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


# =============================================
# Project CRUD Routes
# =============================================

@router.post("/projects", response_model=ProjectDetailResponse, tags=["Projects"])
async def create_project_endpoint(
    files: List[UploadFile] = File(..., description="Python files to analyze"),
    name: str = Form(..., description="Project name"),
    description: str = Form("", description="Project description"),
    generate_docs: bool = Form(True, description="Generate AI documentation"),
    include_uml: bool = Form(True, description="Include UML diagrams"),
    include_module_docs: bool = Form(True, description="Generate per-module docs"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    user: dict = Depends(require_auth),
):
    user_id = get_user_id(user)
    await _check_rate_limit(user_id, "create-project")

    if not supabase_service.is_configured():
        raise HTTPException(status_code=503, detail="Database not configured. Set SUPABASE_URL and SUPABASE_SERVICE_KEY.")

    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    project = await supabase_service.create_project(user_id, name, description)
    if not project:
        raise HTTPException(status_code=500, detail="Failed to create project in database")

    project_id = project["id"]

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            saved_files = []
            file_count = 0

            for upload_file in files:
                original_path = upload_file.filename or ""
                safe_path = _sanitize_filepath(original_path)
                safe_name = _sanitize_filename(original_path)
                if not safe_name:
                    continue
                content_bytes = await upload_file.read()
                content_str = content_bytes.decode("utf-8", errors="replace")
                if safe_path:
                    dest = temp_path / safe_path
                    dest.parent.mkdir(parents=True, exist_ok=True)
                else:
                    dest = temp_path / safe_name
                dest.write_text(content_str, encoding="utf-8")
                saved_files.append({
                    "filename": safe_name,
                    "content": content_str,
                    "file_path": safe_path or safe_name,
                })
                file_count += 1

            if file_count == 0:
                await supabase_service.delete_project(project_id, user_id)
                raise HTTPException(status_code=400, detail="No valid Python files found")

            files_saved = await supabase_service.save_files(project_id, saved_files)
            if not files_saved:
                await supabase_service.delete_project(project_id, user_id)
                raise HTTPException(status_code=500, detail="Failed to save files to database")

            analyses = analyze_project(temp_path)
            metrics = get_metrics(analyses)
            relationships = build_class_relationships(analyses, temp_path)

            uml_diagrams = {}
            if include_uml:
                uml_diagrams = {
                    "class": generate_class_diagram(analyses, temp_path),
                    "dependency": generate_dependency_graph(analyses, temp_path),
                    "inheritance": generate_inheritance_diagram(analyses, temp_path),
                }
                await supabase_service.save_uml(project_id, uml_diagrams)

            docs_to_save = []
            provider = LLMFactory.get_provider(api_key=x_api_key)

            if generate_docs:
                uml_for_overview = {
                    "class_diagram": uml_diagrams.get("class", ""),
                    "dependency_graph": uml_diagrams.get("dependency", ""),
                    "inheritance_diagram": uml_diagrams.get("inheritance", ""),
                }
                if provider:
                    try:
                        overview, _ = _build_project_overview_agentic(
                            analyses, temp_path, metrics, uml_for_overview, provider
                        )
                    except Exception:
                        overview = _build_project_overview(analyses, temp_path, metrics, uml_for_overview, provider)
                else:
                    overview = _build_project_overview(analyses, temp_path, metrics, uml_for_overview, provider)
                docs_to_save.append({
                    "doc_type": "overview",
                    "module_name": None,
                    "content": overview,
                })

                if include_module_docs:
                    for analysis in analyses:
                        rel_path = str(analysis.path.relative_to(temp_path))
                        if provider:
                            try:
                                module_doc, _ = _build_module_doc_agentic(analysis, temp_path, provider)
                            except Exception:
                                module_doc = _build_module_doc(analysis, temp_path, provider)
                        else:
                            module_doc = _build_module_doc(analysis, temp_path, provider)
                        docs_to_save.append({
                            "doc_type": "module",
                            "module_name": rel_path,
                            "content": module_doc,
                        })

            if docs_to_save:
                await supabase_service.save_docs(project_id, docs_to_save)

            await log_usage(user_id, "create-project", file_count)

            files_response = await supabase_service.get_project_files(project_id)
            docs_response = await supabase_service.get_project_docs(project_id)
            uml_response = await supabase_service.get_project_uml(project_id)

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

            class_rels = [
                RelationshipResponse(
                    from_entity=rel.from_class,
                    to_entity=rel.to_class,
                    relationship_type=rel.relationship_type,
                    label=rel.label,
                )
                for rel in relationships.class_relationships
            ]

            return ProjectDetailResponse(
                id=project_id,
                name=project.get("name", name),
                description=project.get("description", description),
                created_at=project.get("created_at", ""),
                updated_at=project.get("updated_at", ""),
                files=files_response,
                docs=docs_response,
                uml=uml_response,
                analysis={"files": files_data, "metrics": metrics},
                relationships=class_rels,
            )
    except HTTPException:
        raise
    except Exception as e:
        await supabase_service.delete_project(project_id, user_id)
        raise HTTPException(status_code=500, detail=f"Project creation failed: {str(e)}")


@router.get("/projects", response_model=List[ProjectSummaryResponse], tags=["Projects"])
async def list_projects_endpoint(
    user: dict = Depends(require_auth),
):
    user_id = get_user_id(user)
    projects = await supabase_service.list_user_projects(user_id)
    return [
        ProjectSummaryResponse(
            id=p["id"],
            name=p["name"],
            description=p.get("description", ""),
            created_at=p.get("created_at", ""),
            updated_at=p.get("updated_at", ""),
        )
        for p in projects
    ]


@router.get("/projects/{project_id}", response_model=ProjectDetailResponse, tags=["Projects"])
async def get_project_endpoint(
    project_id: str,
    user: dict = Depends(require_auth),
):
    user_id = get_user_id(user)

    project = await supabase_service.get_project(project_id, user_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    files = await supabase_service.get_project_files(project_id)
    docs = await supabase_service.get_project_docs(project_id)
    uml = await supabase_service.get_project_uml(project_id)

    return ProjectDetailResponse(
        id=project["id"],
        name=project["name"],
        description=project.get("description", ""),
        created_at=project.get("created_at", ""),
        updated_at=project.get("updated_at", ""),
        files=files,
        docs=docs,
        uml=uml,
    )


@router.delete("/projects/{project_id}", tags=["Projects"])
async def delete_project_endpoint(
    project_id: str,
    user: dict = Depends(require_auth),
):
    user_id = get_user_id(user)

    project = await supabase_service.get_project(project_id, user_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    deleted = await supabase_service.delete_project(project_id, user_id)
    if not deleted:
        raise HTTPException(status_code=500, detail="Failed to delete project")

    return {"message": "Project deleted successfully", "id": project_id}


# =============================================
# Documentation Update Endpoint (LLM Edit)
# =============================================

@router.post("/docs/update", response_model=DocUpdateResponse, tags=["Documentation"])
async def update_doc_endpoint(
    request: DocUpdateRequest,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    user: dict = Depends(require_auth),
):
    user_id = get_user_id(user)
    await _check_rate_limit(user_id, "docs-update")

    doc = await supabase_service.get_doc_by_id(request.doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Documentation not found")

    project_owner = await supabase_service.get_project_owner(doc["project_id"])
    if project_owner != user_id:
        raise HTTPException(status_code=403, detail="You don't have access to this document")

    provider = LLMFactory.get_provider(
        provider_name="gemini",
        api_key=x_api_key,
    )
    if not provider:
        provider = LLMFactory.get_provider(api_key=x_api_key)

    if not provider:
        raise HTTPException(
            status_code=400,
            detail="No LLM provider available. Set GOOGLE_API_KEY or GROQ_API_KEY, or provide X-API-Key header."
        )

    current_content = doc["content"]

    prompt = f"""You are an expert technical writer and documentation editor.

You are given existing documentation and a user instruction for how to update it.

EXISTING DOCUMENTATION:
---
{current_content}
---

USER INSTRUCTION:
{request.instruction}

RULES:
- Apply the user's instruction to update the documentation.
- Preserve the overall structure and formatting (Markdown) unless the instruction says otherwise.
- Only change what the user asks for. Keep everything else intact.
- Return ONLY the updated documentation text. No explanations, no wrapping.
- If the instruction is unclear, make your best reasonable interpretation."""

    try:
        updated_content = provider.generate(prompt).strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM generation failed: {str(e)}")

    new_version = doc.get("version", 1) + 1
    updated_doc = await supabase_service.update_doc_content(
        request.doc_id, updated_content, new_version
    )

    if not updated_doc:
        raise HTTPException(status_code=500, detail="Failed to save updated documentation")

    await log_usage(user_id, "docs-update", 1)

    return DocUpdateResponse(
        id=request.doc_id,
        content=updated_content,
        version=new_version,
        provider_used=provider.provider_name if hasattr(provider, 'provider_name') else None,
    )


@router.patch("/docs/{doc_id}", response_model=ManualDocUpdateResponse, tags=["Documentation"])
async def manual_update_doc_endpoint(
    doc_id: str,
    request: ManualDocUpdateRequest,
    user: dict = Depends(require_auth),
):
    user_id = get_user_id(user)

    doc = await supabase_service.get_doc_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Documentation not found")

    project_owner = await supabase_service.get_project_owner(doc["project_id"])
    if project_owner != user_id:
        raise HTTPException(status_code=403, detail="You don't have access to this document")

    new_version = doc.get("version", 1) + 1
    updated_doc = await supabase_service.update_doc_content(
        doc_id, request.content, new_version
    )

    if not updated_doc:
        raise HTTPException(status_code=500, detail="Failed to save updated documentation")

    return ManualDocUpdateResponse(
        id=doc_id,
        content=request.content,
        version=new_version,
    )


# =============================================
# Project PDF Export (from saved data)
# =============================================

@router.get("/projects/{project_id}/export-pdf", tags=["Projects"])
async def export_project_pdf_endpoint(
    project_id: str,
    user: dict = Depends(require_auth),
):
    user_id = get_user_id(user)

    if not supabase_service.is_configured():
        raise HTTPException(status_code=503, detail="Database not configured.")

    project = await supabase_service.get_project(project_id, user_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    files = await supabase_service.get_project_files(project_id)
    docs = await supabase_service.get_project_docs(project_id)
    uml_list = await supabase_service.get_project_uml(project_id)

    overview_doc = None
    module_docs_map = {}
    for doc in docs:
        if doc.get("doc_type") == "overview":
            overview_doc = doc.get("content", "")
        elif doc.get("doc_type") == "module":
            module_name = doc.get("module_name", "unknown")
            module_docs_map[module_name] = doc.get("content", "")

    uml_data = {}
    for u in uml_list:
        dtype = u.get("diagram_type", "")
        content = u.get("content", "")
        if dtype == "class":
            uml_data["class_diagram"] = content
        elif dtype == "dependency":
            uml_data["dependency_graph"] = content
        elif dtype == "inheritance":
            uml_data["inheritance_diagram"] = content

    files_data = []
    for f in files:
        files_data.append({
            "path": f.get("file_path") or f.get("filename", ""),
            "classes": [],
            "functions": [],
        })

    analysis_data = {"files": files_data, "metrics": {}} if files_data else None

    project_name = project.get("name", "Project")

    try:
        pdf_bytes = generate_pdf(
            project_name=project_name,
            analysis=analysis_data,
            uml=uml_data if uml_data else None,
            documentation=overview_doc,
            module_docs=module_docs_map if module_docs_map else None,
            relationships=None,
            metrics=None,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")

    filename = f"{project_name}_documentation.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# =============================================
# Code Summarization (Fine-tuned CodeT5 Model)
# =============================================

@router.post("/summarize", response_model=SummarizeResponse, tags=["Summarization"])
async def summarize_code_endpoint(
    request: SummarizeRequest,
    user: dict = Depends(require_auth),
):
    codet5 = LLMFactory.get_codet5()
    if not codet5:
        raise HTTPException(
            status_code=503,
            detail="Code summarization model not configured. Set HUGGINGFACE_API_TOKEN and HUGGINGFACE_MODEL_ID."
        )

    try:
        summary = codet5.generate(request.code)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Summarization failed: {str(e)}")

    model_id = codet5.default_model
    return SummarizeResponse(summary=summary, model_used=model_id)


@router.post("/summarize/batch", response_model=BatchSummarizeResponse, tags=["Summarization"])
async def batch_summarize_endpoint(
    request: BatchSummarizeRequest,
    user: dict = Depends(require_auth),
):
    codet5 = LLMFactory.get_codet5()
    if not codet5:
        raise HTTPException(
            status_code=503,
            detail="Code summarization model not configured. Set HUGGINGFACE_API_TOKEN and HUGGINGFACE_MODEL_ID."
        )

    summaries = {}
    for snippet in request.snippets:
        try:
            summary = codet5.generate(snippet.content)
            summaries[snippet.filename] = summary
        except Exception:
            summaries[snippet.filename] = "(summarization failed)"

    model_id = codet5.default_model
    return BatchSummarizeResponse(summaries=summaries, model_used=model_id)


# =============================================
# Agentic Pipeline (Multi-Agent Documentation)
# =============================================

@router.post("/agent/run", response_model=AgentRunResponse, tags=["Agentic Pipeline"])
async def agent_run_endpoint(
    request: AgentRunRequest,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    user: dict = Depends(require_auth),
):
    user_id = get_user_id(user)
    await _check_rate_limit(user_id, "agent-run")

    if not request.files:
        raise HTTPException(status_code=400, detail="No files provided")

    py_files = [f for f in request.files if f.filename.endswith(".py")]
    if not py_files:
        raise HTTPException(status_code=400, detail="No Python files found")

    provider = LLMFactory.get_provider(api_key=x_api_key)
    if not provider:
        raise HTTPException(status_code=503, detail="No LLM provider available. Set GROQ_API_KEY or GOOGLE_API_KEY.")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        written_count = 0
        for file_input in py_files:
            safe_name = _sanitize_filename(file_input.filename)
            if not safe_name:
                continue
            file_path = temp_path / safe_name
            file_path.write_text(file_input.content, encoding="utf-8")
            written_count += 1

        if written_count == 0:
            raise HTTPException(status_code=400, detail="No valid Python files found after sanitization")

        analyses = analyze_project(temp_path)
        metrics = get_metrics(analyses)

        uml_diagrams = {
            "class_diagram": generate_class_diagram(analyses, temp_path),
            "dependency_graph": generate_dependency_graph(analyses, temp_path),
            "inheritance_diagram": generate_inheritance_diagram(analyses, temp_path),
        }

        try:
            overview, trace = _build_project_overview_agentic(
                analyses, temp_path, metrics, uml_diagrams, provider
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Agent pipeline failed: {str(e)}")

        await log_usage(user_id, "agent-run", len(py_files))

        return AgentRunResponse(
            documentation=overview,
            trace=_trace_to_response(trace),
        )
