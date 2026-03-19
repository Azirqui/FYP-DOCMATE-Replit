from __future__ import annotations

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    project_path: str = Field(..., description="Path to the project directory to analyze")


class ClassInfoResponse(BaseModel):
    name: str
    lineno: int
    end_lineno: int
    has_docstring: bool
    methods: List[str] = []
    base_classes: List[str] = []
    attributes: List[str] = []
    decorators: List[str] = []


class FunctionInfoResponse(BaseModel):
    name: str
    lineno: int
    end_lineno: int
    has_docstring: bool
    parameters: List[str] = []
    return_type: Optional[str] = None
    is_async: bool = False
    decorators: List[str] = []


class FileAnalysisResponse(BaseModel):
    path: str
    classes: List[ClassInfoResponse] = []
    functions: List[FunctionInfoResponse] = []
    module_docstring: Optional[str] = None
    lines_of_code: int = 0
    import_count: int = 0


class ProjectAnalysisResponse(BaseModel):
    project_path: str
    files: List[FileAnalysisResponse] = []
    metrics: Dict[str, Any] = {}


class RelationshipResponse(BaseModel):
    from_entity: str
    to_entity: str
    relationship_type: str
    label: Optional[str] = None


class UMLRequest(BaseModel):
    project_path: str = Field(..., description="Path to the project directory")
    include_methods: bool = Field(True, description="Include methods in class diagrams")
    include_attributes: bool = Field(True, description="Include attributes in class diagrams")
    max_methods: int = Field(10, description="Maximum methods per class")


class UMLResponse(BaseModel):
    class_diagram: str = ""
    dependency_graph: str = ""
    inheritance_diagram: str = ""
    class_relationships: List[RelationshipResponse] = []


class DocstringRequest(BaseModel):
    code: str = Field(..., description="Python code to generate docstring for")
    docstring_type: str = Field("function", description="Type: 'function' or 'class'")
    provider: Optional[str] = Field(None, description="LLM provider: 'groq' or 'gemini'")
    api_key: Optional[str] = Field(None, description="API key for the provider")


class DocstringResponse(BaseModel):
    docstring: str
    provider_used: Optional[str] = None


class ProjectDocsRequest(BaseModel):
    project_path: str = Field(..., description="Path to the project directory")
    output_dir: Optional[str] = Field(None, description="Output directory for docs")
    include_uml: bool = Field(True, description="Include UML diagrams")
    include_module_docs: bool = Field(True, description="Generate per-module docs")
    provider: Optional[str] = Field(None, description="LLM provider to use")
    api_key: Optional[str] = Field(None, description="API key for the provider")


class ProjectDocsResponse(BaseModel):
    project_overview: str
    module_docs: Dict[str, str] = {}
    uml_diagrams: Dict[str, str] = {}
    metrics: Dict[str, Any] = {}


class HealthResponse(BaseModel):
    status: str = "healthy"
    llm_available: bool = False
    available_providers: List[str] = []


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None


class CodeFileInput(BaseModel):
    filename: str = Field(..., description="Filename with .py extension")
    content: str = Field(..., description="Python source code content")


class AnalyzeTextRequest(BaseModel):
    files: List[CodeFileInput] = Field(..., description="List of Python files with content")
    generate_docs: bool = Field(False, description="Generate AI documentation (requires API key)")


class MetricsResponse(BaseModel):
    total_files: int = 0
    total_classes: int = 0
    total_functions: int = 0
    total_methods: int = 0
    total_lines_of_code: int = 0


class UnifiedAnalysisResponse(BaseModel):
    success: bool = True
    analysis: Optional[Dict[str, Any]] = None
    uml: Optional[Dict[str, str]] = None
    documentation: Optional[str] = None
    relationships: List[RelationshipResponse] = []
    error: Optional[str] = None


class DocsTextRequest(BaseModel):
    files: List[CodeFileInput] = Field(..., description="List of Python files with content")
    include_uml: bool = Field(True, description="Include UML diagrams")
    include_module_docs: bool = Field(True, description="Generate per-module docs")


class UMLTextRequest(BaseModel):
    files: List[CodeFileInput] = Field(..., description="List of Python files with content")
    include_methods: bool = Field(True, description="Include methods in class diagrams")
    include_attributes: bool = Field(True, description="Include attributes in class diagrams")
    max_methods: int = Field(10, description="Maximum methods per class")


class ExportPDFRequest(BaseModel):
    files: List[CodeFileInput] = Field(..., description="List of Python files with content")
    project_name: str = Field("Project", description="Name for the documentation")
    include_uml: bool = Field(True, description="Include UML diagrams")
    include_module_docs: bool = Field(True, description="Generate per-module docs")
    include_analysis: bool = Field(True, description="Include file analysis details")


class GitHubRepoRequest(BaseModel):
    repo_full_name: str = Field(..., description="Full repo name like 'owner/repo'")
    branch: str = Field("main", description="Branch to analyze")
    generate_docs: bool = Field(False, description="Generate AI documentation")
    include_uml: bool = Field(True, description="Include UML diagrams")
    export_pdf: bool = Field(False, description="Return PDF instead of JSON")
    project_name: Optional[str] = Field(None, description="Name for documentation (defaults to repo name)")
    save_to_project: bool = Field(True, description="Save results to Supabase as a project")
    include_module_docs: bool = Field(True, description="Generate per-module docs (when save_to_project and generate_docs are true)")


class CreateProjectRequest(BaseModel):
    name: str = Field(..., description="Project name")
    description: str = Field("", description="Project description")
    generate_docs: bool = Field(True, description="Generate AI documentation")
    include_uml: bool = Field(True, description="Include UML diagrams")
    include_module_docs: bool = Field(True, description="Generate per-module docs")


class ProjectSummaryResponse(BaseModel):
    id: str
    name: str
    description: str = ""
    created_at: str
    updated_at: str


class ProjectDetailResponse(BaseModel):
    id: str
    name: str
    description: str = ""
    created_at: str
    updated_at: str
    files: List[Dict[str, Any]] = []
    docs: List[Dict[str, Any]] = []
    uml: List[Dict[str, Any]] = []
    analysis: Optional[Dict[str, Any]] = None
    relationships: List[RelationshipResponse] = []


class DocUpdateRequest(BaseModel):
    doc_id: str = Field(..., description="UUID of the generated doc to update")
    instruction: str = Field(..., description="User instruction for how to update the documentation")


class DocUpdateResponse(BaseModel):
    id: str
    content: str
    version: int
    provider_used: Optional[str] = None


class ManualDocUpdateRequest(BaseModel):
    content: str = Field(..., description="Updated documentation content (Markdown)")


class ManualDocUpdateResponse(BaseModel):
    id: str
    content: str
    version: int


class SummarizeRequest(BaseModel):
    code: str = Field(..., description="Python code to summarize")


class SummarizeResponse(BaseModel):
    summary: str
    model_used: str


class BatchSummarizeRequest(BaseModel):
    snippets: List[CodeFileInput] = Field(..., description="List of code snippets to summarize")


class BatchSummarizeResponse(BaseModel):
    summaries: Dict[str, str] = Field(default_factory=dict, description="Filename -> summary mapping")
    model_used: str
