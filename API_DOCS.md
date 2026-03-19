# Code Documentation AI - API Reference

Base URL: `/api/v1`

## Authentication

All endpoints (except `/health`) require a Supabase JWT token in the `Authorization` header.

```
Authorization: Bearer <supabase_jwt_token>
```

### How to get a token (for Postman testing)

1. Use the Supabase Auth REST API to sign up or sign in:

```bash
# Sign up
curl -X POST 'https://YOUR_SUPABASE_URL/auth/v1/signup' \
  -H 'apikey: YOUR_SUPABASE_ANON_KEY' \
  -H 'Content-Type: application/json' \
  -d '{"email": "test@example.com", "password": "your_password"}'

# Sign in
curl -X POST 'https://YOUR_SUPABASE_URL/auth/v1/token?grant_type=password' \
  -H 'apikey: YOUR_SUPABASE_ANON_KEY' \
  -H 'Content-Type: application/json' \
  -d '{"email": "test@example.com", "password": "your_password"}'
```

2. Copy the `access_token` from the response
3. Use it in all API requests as `Authorization: Bearer <access_token>`

### Common Headers

| Header | Required | Description |
|--------|----------|-------------|
| `Authorization` | Yes | `Bearer <supabase_jwt>` |
| `X-API-Key` | No | LLM API key (Groq or Gemini). Optional if server has env vars set. |
| `X-GitHub-Token` | For GitHub endpoints | GitHub personal access token |

---

## Endpoints

### Health Check

```
GET /api/v1/health
```

No authentication required.

**Response:**
```json
{
  "status": "healthy",
  "llm_available": true,
  "available_providers": ["groq", "gemini"]
}
```

---

### Projects

#### Create Project

```
POST /api/v1/projects
Content-Type: multipart/form-data
```

Upload Python files, analyze them, generate documentation and UML, and save everything.

**Form Fields:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `files` | File[] | Yes | Python (.py) files to analyze |
| `name` | string | Yes | Project name |
| `description` | string | No | Project description |
| `generate_docs` | bool | No | Generate AI docs (default: true) |
| `include_uml` | bool | No | Generate UML diagrams (default: true) |
| `include_module_docs` | bool | No | Generate per-module docs (default: true) |

**Response:**
```json
{
  "id": "uuid",
  "name": "My Project",
  "description": "",
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2025-01-01T00:00:00Z",
  "files": [
    {"id": "uuid", "filename": "main.py", "content": "...", "created_at": "..."}
  ],
  "docs": [
    {"id": "uuid", "doc_type": "overview", "module_name": null, "content": "# Project Overview...", "version": 1},
    {"id": "uuid", "doc_type": "module", "module_name": "main.py", "content": "## main Module...", "version": 1}
  ],
  "uml": [
    {"id": "uuid", "diagram_type": "class", "content": "classDiagram\n..."},
    {"id": "uuid", "diagram_type": "dependency", "content": "graph TD\n..."},
    {"id": "uuid", "diagram_type": "inheritance", "content": "graph BT\n..."}
  ],
  "analysis": {
    "files": [...],
    "metrics": {"total_files": 4, "total_classes": 9, ...}
  },
  "relationships": [
    {"from_entity": "User", "to_entity": "Entity", "relationship_type": "inheritance", "label": null}
  ]
}
```

#### List Projects

```
GET /api/v1/projects
```

**Response:**
```json
[
  {
    "id": "uuid",
    "name": "My Project",
    "description": "",
    "created_at": "2025-01-01T00:00:00Z",
    "updated_at": "2025-01-01T00:00:00Z"
  }
]
```

#### Get Project Details

```
GET /api/v1/projects/{project_id}
```

Returns full project with files, docs, and UML diagrams.

**Response:** Same structure as Create Project response (without `analysis` and `relationships`).

#### Delete Project

```
DELETE /api/v1/projects/{project_id}
```

**Response:**
```json
{
  "message": "Project deleted successfully",
  "id": "uuid"
}
```

#### Export Project as PDF

```
GET /api/v1/projects/{project_id}/export-pdf
```

Downloads the current saved documentation, UML, and file info as a PDF. This uses whatever is currently stored in the database — so if docs were edited (manually or via LLM), the PDF reflects the edited versions.

**Response:** `application/pdf` binary file.

**Frontend usage:**
```javascript
const response = await fetch(`/api/v1/projects/${projectId}/export-pdf`, {
  headers: { Authorization: `Bearer ${token}` }
});
const blob = await response.blob();
const url = URL.createObjectURL(blob);
window.open(url); // or trigger download
```

---

### Documentation Update (LLM Edit)

```
POST /api/v1/docs/update
Content-Type: application/json
```

Update existing generated documentation using natural language instructions. Uses Gemini (preferred) or Groq.

**Request:**
```json
{
  "doc_id": "uuid-of-the-doc",
  "instruction": "Add a section about error handling"
}
```

**Response:**
```json
{
  "id": "uuid",
  "content": "# Updated documentation...",
  "version": 2,
  "provider_used": "gemini"
}
```

**Flow:**
1. Frontend shows generated doc (from project creation)
2. User types an edit instruction in the side panel
3. Frontend sends `doc_id` + `instruction` to this endpoint
4. Backend fetches current doc, sends to LLM with instruction, saves updated version
5. Frontend shows updated doc

### Manual Documentation Edit

```
PATCH /api/v1/docs/{doc_id}
Content-Type: application/json
```

Directly save edited documentation content. No LLM is involved — the frontend sends the updated Markdown text and it's saved as-is. Use this when the user manually edits docs in a text editor on the frontend.

**Request:**
```json
{
  "content": "# Updated Project Overview\n\nThis project does..."
}
```

**Response:**
```json
{
  "id": "uuid",
  "content": "# Updated Project Overview\n\nThis project does...",
  "version": 2
}
```

**Frontend integration:**
- Use a Markdown editor (e.g., `react-markdown-editor-lite`, CodeMirror with Markdown mode, or a simple textarea)
- On save, send the full content to this endpoint
- Each save increments the version number

---

### Analysis Endpoints

#### Analyze Text (Code as JSON)

```
POST /api/v1/analyze-text
Content-Type: application/json
```

**Request:**
```json
{
  "files": [
    {"filename": "main.py", "content": "def hello():\n    return 'world'"},
    {"filename": "models.py", "content": "class User:\n    pass"}
  ],
  "generate_docs": true
}
```

**Response:**
```json
{
  "success": true,
  "analysis": {"files": [...], "metrics": {...}},
  "uml": {
    "class_diagram": "classDiagram\n...",
    "dependency_graph": "graph TD\n...",
    "inheritance_diagram": "graph BT\n..."
  },
  "documentation": "# Project Overview...",
  "relationships": [...]
}
```

#### Upload Files (Multipart)

```
POST /api/v1/upload-files
Content-Type: multipart/form-data
```

**Form Fields:**
- `files`: Python files (multipart upload)
- `generate_docs`: bool (default: false)

**Response:** Same as analyze-text.

#### Upload ZIP

```
POST /api/v1/upload-zip
Content-Type: multipart/form-data
```

**Form Fields:**
- `file`: ZIP file containing Python project
- `generate_docs`: bool (default: false)

**Response:** Same as analyze-text.

---

### Documentation Generation

#### Generate Docs from Text

```
POST /api/v1/docs-text
Content-Type: application/json
```

**Request:**
```json
{
  "files": [{"filename": "main.py", "content": "..."}],
  "include_uml": true,
  "include_module_docs": true
}
```

**Response:**
```json
{
  "project_overview": "# Project Overview...",
  "module_docs": {"main.py": "## main Module..."},
  "uml_diagrams": {"class_diagram": "...", "dependency_graph": "...", "inheritance_diagram": "..."},
  "metrics": {"total_files": 1, ...}
}
```

---

### UML Generation

#### Generate UML from Text

```
POST /api/v1/uml-text
Content-Type: application/json
```

**Request:**
```json
{
  "files": [{"filename": "models.py", "content": "class User:\n    pass"}],
  "include_methods": true,
  "include_attributes": true,
  "max_methods": 10
}
```

**Response:**
```json
{
  "class_diagram": "classDiagram\n    class User {\n    }",
  "dependency_graph": "graph TD\n    F0[models]",
  "inheritance_diagram": "graph BT\n    C0[User]",
  "class_relationships": []
}
```

**Frontend rendering:** Use the `mermaid` npm package or `react-mermaidjs` to render these diagram strings as SVG.

---

### Docstring Generation

```
POST /api/v1/docstring
Content-Type: application/json
```

**Request:**
```json
{
  "code": "def calculate_total(items: list, tax_rate: float = 0.1) -> float:\n    subtotal = sum(item.price for item in items)\n    return subtotal * (1 + tax_rate)",
  "docstring_type": "function"
}
```

**Response:**
```json
{
  "docstring": "Calculate the total price of items including tax.\n\nArgs:\n    items: List of items with a price attribute.\n    tax_rate: Tax rate to apply (default: 0.1 or 10%).\n\nReturns:\n    The total price including tax.",
  "provider_used": "groq"
}
```

---

### PDF Export

```
POST /api/v1/export-pdf
Content-Type: application/json
```

Returns a PDF file as binary response.

**Request:**
```json
{
  "files": [{"filename": "main.py", "content": "..."}],
  "project_name": "My Project",
  "include_uml": true,
  "include_module_docs": true,
  "include_analysis": true
}
```

**Response:** `application/pdf` binary file.

---

### GitHub Integration

#### List Repos

```
GET /api/v1/github/repos
X-GitHub-Token: ghp_xxx
```

#### Analyze GitHub Repo

```
POST /api/v1/github/analyze
X-GitHub-Token: ghp_xxx
```

Fetches Python files from a GitHub repo, analyzes them, and by default saves everything as a project in Supabase.

**Request:**
```json
{
  "repo_full_name": "owner/repo",
  "branch": "main",
  "generate_docs": true,
  "include_uml": true,
  "save_to_project": true,
  "include_module_docs": true
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `repo_full_name` | string | required | Format: `owner/repo` |
| `branch` | string | `"main"` | Branch to analyze |
| `generate_docs` | bool | `false` | Generate AI documentation |
| `include_uml` | bool | `true` | Generate UML diagrams |
| `save_to_project` | bool | `true` | Save as a project in Supabase |
| `include_module_docs` | bool | `true` | Generate per-module docs |
| `project_name` | string | repo name | Name for the project |

**Response (when `save_to_project=true`):** Same as Create Project response (ProjectDetailResponse).

**Response (when `save_to_project=false`):** Same as analyze-text (UnifiedAnalysisResponse).

#### Export GitHub Repo as PDF

```
POST /api/v1/github/export-pdf
X-GitHub-Token: ghp_xxx
```

Same request body as analyze (without `save_to_project`).

---

### Code Summarization (Fine-tuned CodeT5)

These endpoints use a fine-tuned CodeT5-small model trained on Python code summarization. They require `HUGGINGFACE_API_TOKEN` and optionally `HUGGINGFACE_MODEL_ID` to be configured on the server.

#### Summarize Single Code Snippet

```
POST /api/v1/summarize
Content-Type: application/json
```

**Request:**
```json
{
  "code": "def calculate_total(items: list, tax_rate: float = 0.1) -> float:\n    subtotal = sum(item.price for item in items)\n    return subtotal * (1 + tax_rate)"
}
```

**Response:**
```json
{
  "summary": "Calculate total price of items with tax applied",
  "model_used": "your-username/codet5-python-summarizer"
}
```

#### Batch Summarize Multiple Snippets

```
POST /api/v1/summarize/batch
Content-Type: application/json
```

**Request:**
```json
{
  "snippets": [
    {"filename": "auth.py", "content": "def verify_token(token: str) -> dict:\n    ..."},
    {"filename": "utils.py", "content": "def format_date(dt: datetime) -> str:\n    ..."}
  ]
}
```

**Response:**
```json
{
  "summaries": {
    "auth.py": "Verify and decode an authentication token",
    "utils.py": "Format a datetime object as a string"
  },
  "model_used": "your-username/codet5-python-summarizer"
}
```

**Notes:**
- Returns 503 if the CodeT5 model is not configured
- The model generates short one-line summaries optimized for Python code
- The same model is used internally during documentation generation to provide per-function summaries as context for the LLM

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message here"
}
```

| Status Code | Meaning |
|-------------|---------|
| 400 | Bad request (missing fields, invalid input) |
| 401 | Missing or invalid JWT token |
| 403 | Not authorized to access this resource |
| 404 | Resource not found |
| 429 | Rate limit exceeded |
| 500 | Server error |
| 503 | Service unavailable (auth or CodeT5 model not configured) |

---

## Frontend Integration Guide

### Rendering UML Diagrams

UML diagrams are returned as Mermaid.js text strings. To render them in React:

```bash
npm install mermaid
```

```jsx
import mermaid from 'mermaid';
import { useEffect, useRef } from 'react';

function MermaidDiagram({ content }) {
  const ref = useRef(null);

  useEffect(() => {
    if (ref.current && content) {
      mermaid.initialize({ startOnLoad: false });
      mermaid.render('diagram', content).then(({ svg }) => {
        ref.current.innerHTML = svg;
      });
    }
  }, [content]);

  return <div ref={ref} />;
}
```

### Side-by-Side Code + Docs View

1. Use `POST /api/v1/projects` to upload files and generate everything
2. Display `files[].content` on the left (use Monaco Editor or CodeMirror)
3. Display `docs[].content` on the right (render as Markdown)
4. Add a chat/input panel for doc editing via `POST /api/v1/docs/update`

### File Tree View

Project files include a `file_path` field with the full relative path (e.g., `src/utils/helpers.py`). Use this to build a tree view:

```javascript
function buildFileTree(files) {
  const root = {};
  for (const file of files) {
    const parts = (file.file_path || file.filename).split('/');
    let current = root;
    for (let i = 0; i < parts.length - 1; i++) {
      if (!current[parts[i]]) current[parts[i]] = {};
      current = current[parts[i]];
    }
    current[parts[parts.length - 1]] = file;
  }
  return root;
}
```

### Doc Update Flow

There are two ways to edit docs:

**1. LLM-Powered Edit (AI rewrites the doc based on instructions):**
1. User sees generated doc on the right panel
2. User types: "Add more detail about the User class"
3. Frontend sends: `POST /api/v1/docs/update` with `doc_id` and `instruction`
4. Backend returns updated doc content
5. Frontend replaces the doc panel with new content

**2. Manual Edit (user directly edits the Markdown):**
1. User clicks "Edit" on a doc — switch to a Markdown editor
2. User makes changes in the editor
3. On save, frontend sends: `PATCH /api/v1/docs/{doc_id}` with `{ "content": "..." }`
4. Backend saves and returns the new version

### PDF Download

To let users download the current project docs as a PDF:

```javascript
async function downloadPDF(projectId, token) {
  const res = await fetch(`/api/v1/projects/${projectId}/export-pdf`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'documentation.pdf';
  a.click();
}
```
