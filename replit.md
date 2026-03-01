# AI-Based Code Documentation Generator

## Project Overview
This is an AI-powered code documentation generator for a Final Year Project (FYP). The system analyzes Python source code and generates comprehensive documentation including:
- Function and class docstrings
- Module-level documentation
- Project-level README with architecture overview
- **UML diagrams** (Mermaid format) showing class relationships, inheritance, and dependencies
- **REST API** for integration with web interfaces
- **Supabase JWT authentication** with rate limiting

## Project Structure
```
code_doc_ai/                     # Main package (at root for Vercel)
├── __init__.py
├── api/                         # REST API layer
│   ├── app.py                   # FastAPI application setup
│   ├── routes.py                # API endpoints
│   ├── schemas.py               # Pydantic request/response models
│   ├── auth.py                  # Supabase JWT authentication
│   └── usage.py                 # Usage tracking & rate limiting
├── core/                        # Core analysis logic
│   ├── models.py                # Data models
│   ├── parser.py                # AST parser for Python code
│   └── relationships.py         # Class/file relationship mapping
├── generators/                  # Output generators
│   └── uml.py                   # Mermaid UML diagram generation
├── llm/                         # LLM provider abstraction
│   ├── base.py                  # Base LLM provider class
│   ├── factory.py               # LLM provider factory
│   ├── groq_provider.py         # Groq/Llama implementation
│   └── gemini_provider.py       # Google Gemini implementation
└── utils/
    └── config.py                # YAML config management

api/
├── index.py                     # Vercel serverless entry point
└── requirements.txt             # Dependencies for Vercel

src/
└── main.py                      # Local development entry point

test_sample/                     # Sample e-commerce code for testing
```

## API Endpoints

The server runs on port 5000 and provides these endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API info and available endpoints |
| `/docs` | GET | Interactive Swagger documentation |
| `/api/v1/health` | GET | Health check with LLM status |
| `/api/v1/analyze-text` | POST | **Analyze code as JSON text** |
| `/api/v1/upload-files` | POST | **Upload Python files (multipart)** |
| `/api/v1/upload-zip` | POST | **Upload ZIP project file** |
| `/api/v1/docs-text` | POST | **Generate full documentation from code text** |
| `/api/v1/uml-text` | POST | **Generate UML diagrams from code text** |
| `/api/v1/docstring` | POST | Generate docstring for code snippet |
| `/api/v1/export-pdf` | POST | **Export documentation as PDF** |
| `/api/v1/github/repos` | GET | **List user's GitHub repositories** |
| `/api/v1/github/analyze` | POST | **Analyze GitHub repo code** |
| `/api/v1/github/export-pdf` | POST | **Generate PDF from GitHub repo** |

### Authentication

The API supports optional Supabase JWT authentication for rate limiting:

```
Authorization: Bearer <supabase-jwt-token>
```

- **Without token**: API works but no usage tracking
- **With token**: Usage is tracked, rate limits apply (50 generations/day default)

For LLM-based features (docstrings, documentation), provide the LLM API key:
```
X-API-Key: <groq-or-gemini-api-key>
```

### Main Endpoints (For Web Frontend Integration)

**1. Analyze Text (paste code as JSON):**
```bash
curl -X POST https://your-app.vercel.app/api/v1/analyze-text \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <supabase-jwt>" \
  -H "X-API-Key: <llm-api-key>" \
  -d '{
    "files": [
      {"filename": "main.py", "content": "def hello(): pass"},
      {"filename": "utils.py", "content": "class Helper: pass"}
    ],
    "generate_docs": false
  }'
```

**2. Upload Files (multipart form):**
```bash
curl -X POST https://your-app.vercel.app/api/v1/upload-files \
  -H "Authorization: Bearer <supabase-jwt>" \
  -H "X-API-Key: <llm-api-key>" \
  -F "files=@main.py" \
  -F "files=@utils.py" \
  -F "generate_docs=false"
```

**3. Upload ZIP Project:**
```bash
curl -X POST https://your-app.vercel.app/api/v1/upload-zip \
  -H "Authorization: Bearer <supabase-jwt>" \
  -H "X-API-Key: <llm-api-key>" \
  -F "file=@project.zip" \
  -F "generate_docs=false"
```

**4. Generate Documentation (from code text):**
```bash
curl -X POST https://your-app.vercel.app/api/v1/docs-text \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <supabase-jwt>" \
  -H "X-API-Key: <llm-api-key>" \
  -d '{
    "files": [{"filename": "main.py", "content": "class User: pass"}],
    "include_uml": true,
    "include_module_docs": true
  }'
```

**5. Generate UML Only (no LLM needed):**
```bash
curl -X POST https://your-app.vercel.app/api/v1/uml-text \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <supabase-jwt>" \
  -d '{
    "files": [{"filename": "main.py", "content": "class User: pass\nclass Admin(User): pass"}],
    "include_methods": true,
    "include_attributes": true
  }'
```

### Response Formats

**Unified Analysis Response (analyze-text, upload-files, upload-zip):**
```json
{
  "success": true,
  "analysis": {
    "files": [...],
    "metrics": {"total_files": 3, "total_classes": 5, ...}
  },
  "uml": {
    "class_diagram": "classDiagram...",
    "dependency_graph": "graph TD...",
    "inheritance_diagram": "graph BT..."
  },
  "relationships": [...],
  "documentation": null,
  "error": null
}
```

**Documentation Response (docs-text):**
```json
{
  "project_overview": "# Project Overview...",
  "module_docs": {"main.py": "## main Module..."},
  "uml_diagrams": {"class_diagram": "classDiagram..."},
  "metrics": {"total_files": 1, ...}
}
```

**UML Response (uml-text):**
```json
{
  "class_diagram": "classDiagram\n    class User {...}",
  "dependency_graph": "graph TD\n    F0[main]",
  "inheritance_diagram": "graph BT\n    C0[Admin] --> C1[User]",
  "class_relationships": [...]
}
```

## Key Features

### 1. REST API (FastAPI)
- Clean RESTful interface for all functionality
- Swagger/OpenAPI documentation at `/docs`
- Pydantic validation for requests/responses
- CORS enabled for web integration

### 2. Authentication & Rate Limiting
- Supabase JWT token validation
- Daily rate limits (configurable, default 50/day)
- Usage tracking per user in Supabase

### 3. LLM Provider Abstraction
- Pluggable LLM providers (Groq, Gemini)
- Factory pattern for provider selection
- API key passed via X-API-Key header

### 4. PDF Export
- Generate downloadable PDF documentation from code
- Includes project overview, file analysis, UML diagrams, relationships
- Professional formatting with title page and metrics
- Works with uploaded code or GitHub repos

### 5. GitHub Integration
- List user's GitHub repositories
- Fetch and analyze repo Python files directly
- Generate documentation or PDF from any GitHub repo
- Uses GitHub access token (from Supabase OAuth or personal token)

### 6. Code Analysis
- Python AST-based parsing (code is never executed)
- Class/function/method extraction
- Type hint and docstring detection
- Import relationship tracking

### 7. UML Generation
- **Class Diagrams**: Mermaid syntax with visibility markers
- **Dependency Graphs**: File-level import relationships
- **Inheritance Diagrams**: Class hierarchy visualization
- No LLM needed - pure AST parsing

## Running the Server

```bash
cd src && python main.py
```

Or use the workflow "API Server" which is configured to run automatically.

## Environment Variables

### Required for LLM Features
- `GROQ_API_KEY` - For Groq/Llama LLM access
- `GOOGLE_API_KEY` - For Google Gemini LLM access

### Required for Authentication (Optional)
- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_JWT_SECRET` - JWT secret for token validation
- `SUPABASE_SERVICE_KEY` - Service key for usage tracking
- `DAILY_GENERATION_LIMIT` - Rate limit per user (default: 50)

## Supabase Setup

1. Create a Supabase project
2. Create the usage_logs table:
```sql
CREATE TABLE usage_logs (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id TEXT NOT NULL,
  endpoint TEXT NOT NULL,
  files_count INTEGER DEFAULT 0,
  success BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_usage_logs_user_date ON usage_logs(user_id, created_at);
```

3. Add environment variables to Vercel

## Dependencies
- fastapi
- uvicorn
- langchain-core
- langchain-groq
- langchain-google-genai
- pyyaml
- python-dotenv
- PyJWT
- httpx

## Web Integration

Your teammates can integrate with this API:

1. **Frontend**: Use Supabase Auth for user login
2. **API calls**: Pass JWT token in Authorization header
3. **LLM features**: Pass LLM API key in X-API-Key header
4. **Documentation**: Access Swagger docs at `/docs`

## Vercel Deployment
See `DEPLOY.md` for full instructions. Quick summary:
1. Push to GitHub (production-ai-backend branch)
2. Create project on vercel.com
3. Import repo (auto-detects `vercel.json`)
4. Add environment variables in Vercel Settings

## Recent Changes (January 2026)
- Added `/api/v1/docs-text` - Generate documentation from code text
- Added `/api/v1/uml-text` - Generate UML from code text
- Added Supabase JWT authentication support
- Added usage tracking and rate limiting
- Removed Mangum wrapper for native Vercel ASGI support
- All endpoints now accept uploaded code instead of server paths

## User Preferences
- Google-style docstrings
- Mermaid format for UML diagrams
- Support for both Groq and Google Gemini APIs
- REST API for web interface integration
- Supabase for authentication and usage tracking
