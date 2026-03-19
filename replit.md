# AI-Based Code Documentation Generator

## Project Overview
This is an AI-powered code documentation generator for a Final Year Project (FYP). The system analyzes Python source code and generates comprehensive documentation including:
- Function and class docstrings
- Module-level documentation
- Project-level README with architecture overview
- **UML diagrams** (Mermaid format) showing class relationships, inheritance, and dependencies
- **REST API** for integration with web interfaces
- **Supabase JWT authentication** (mandatory on all routes except health)
- **Project persistence** — save projects, files, docs, and UML to Supabase
- **LLM-powered doc editing** — update generated docs via natural language instructions

## Project Structure
```
code_doc_ai/                     # Main package (at root for Vercel)
├── __init__.py
├── api/                         # REST API layer
│   ├── app.py                   # FastAPI application setup
│   ├── routes.py                # API endpoints (analysis, projects, docs, UML, GitHub)
│   ├── schemas.py               # Pydantic request/response models
│   ├── auth.py                  # Supabase JWT authentication (mandatory)
│   ├── usage.py                 # Usage tracking & rate limiting
│   ├── supabase_service.py      # Supabase database CRUD operations
│   └── github.py                # GitHub API integration
├── core/                        # Core analysis logic
│   ├── models.py                # Data models
│   ├── parser.py                # AST parser for Python code
│   └── relationships.py         # Class/file relationship mapping
├── generators/                  # Output generators
│   ├── uml.py                   # Mermaid UML diagram generation
│   └── pdf.py                   # PDF documentation export
├── llm/                         # LLM provider abstraction
│   ├── base.py                  # Base LLM provider class
│   ├── factory.py               # LLM provider factory
│   ├── groq_provider.py         # Groq/Llama implementation (doc generation)
│   ├── gemini_provider.py       # Google Gemini implementation (doc editing)
│   └── codet5_provider.py       # Fine-tuned CodeT5 (code summarization via HF API)
├── app/                         # Higher-level orchestration
│   ├── parser.py                # File/project parsing
│   ├── uml_generator.py         # UML generation logic
│   ├── docstring_generator.py   # LLM prompt templates
│   ├── project_docs.py          # Project documentation builder
│   └── relationship_mapper.py   # Cross-file relationship mapper
└── utils/
    └── config.py                # YAML config management

api/
├── index.py                     # Vercel serverless entry point
└── requirements.txt             # Dependencies for Vercel

src/
└── main.py                      # Local development entry point (uvicorn, port 5000)

migrations/
├── 001_create_tables.sql        # Supabase database schema
└── 002_add_filepath.sql         # Adds file_path column to project_files

training/
├── codet5_training.py           # Google Colab script for fine-tuning CodeT5-small
└── README_TRAINING.md           # Step-by-step Colab training instructions

test_sample/                     # Sample e-commerce code for testing
API_DOCS.md                      # Full API reference for frontend team
DEPLOY.md                        # Vercel deployment instructions
```

## API Endpoints

The server runs on port 5000. All endpoints except `/api/v1/health` require JWT auth.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Health check (no auth) |
| `/api/v1/projects` | POST | Create project (upload files, analyze, generate docs+UML) |
| `/api/v1/projects` | GET | List user's projects |
| `/api/v1/projects/{id}` | GET | Get project details with files, docs, UML |
| `/api/v1/projects/{id}` | DELETE | Delete a project |
| `/api/v1/projects/{id}/export-pdf` | GET | Download project docs as PDF (from saved data) |
| `/api/v1/docs/update` | POST | Update documentation via LLM (Gemini) |
| `/api/v1/docs/{doc_id}` | PATCH | Manual doc edit (save directly, no LLM) |
| `/api/v1/analyze-text` | POST | Analyze code as JSON text |
| `/api/v1/upload-files` | POST | Upload Python files (multipart) |
| `/api/v1/upload-zip` | POST | Upload ZIP project |
| `/api/v1/docs-text` | POST | Generate full docs from code text |
| `/api/v1/uml-text` | POST | Generate UML from code text |
| `/api/v1/docstring` | POST | Generate docstring for code snippet |
| `/api/v1/export-pdf` | POST | Export documentation as PDF |
| `/api/v1/summarize` | POST | Summarize code snippet (CodeT5 model) |
| `/api/v1/summarize/batch` | POST | Batch summarize multiple snippets (CodeT5) |
| `/api/v1/github/repos` | GET | List GitHub repos |
| `/api/v1/github/analyze` | POST | Analyze GitHub repo (saves to Supabase by default) |
| `/api/v1/github/export-pdf` | POST | PDF from GitHub repo |

## Authentication

All routes (except health) require Supabase JWT:
```
Authorization: Bearer <supabase_jwt_token>
```

## Database Tables (Supabase)

| Table | Purpose |
|-------|---------|
| `usage_logs` | API usage tracking and rate limiting |
| `projects` | User projects (name, description) |
| `project_files` | Uploaded Python files per project |
| `generated_docs` | Generated documentation (overview, module, docstring) with versioning |
| `generated_uml` | Generated UML diagrams (class, dependency, inheritance) |

Run migrations in Supabase SQL Editor:
1. `migrations/001_create_tables.sql` — creates all tables
2. `migrations/002_add_filepath.sql` — adds `file_path` column to `project_files`

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Yes* | Groq API key for doc generation |
| `GOOGLE_API_KEY` | Yes* | Gemini API key for doc editing |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_JWT_SECRET` | Yes | JWT secret for auth |
| `SUPABASE_SERVICE_KEY` | Yes | Service role key for DB access |
| `HUGGINGFACE_API_TOKEN` | No | HuggingFace API token for CodeT5 model |
| `HUGGINGFACE_MODEL_ID` | No | HuggingFace model ID (default: Salesforce/codet5-small) |
| `DAILY_GENERATION_LIMIT` | No | Rate limit per user (default: 50) |

*At least one LLM key needed for AI features. HuggingFace token enables the fine-tuned CodeT5 summarization model.

## Key Architecture Decisions
- **Hybrid AI Pipeline**: Fine-tuned CodeT5 generates per-function/class summaries → summaries fed as context to LLM → LLM writes full project/module documentation
- **Groq** (Llama 3.3 70B) for initial documentation generation (fast, good quality)
- **Gemini** (1.5 Flash) for documentation editing/updates (good at following instructions)
- **CodeT5-small** (fine-tuned on CodeSearchNet Python) for code summarization — runs via HuggingFace Inference API (no local GPU needed)
- **Supabase** for auth, database, and usage tracking
- **Mermaid.js** for UML — frontend renders using `mermaid` npm package
- **Dual deployment**: Local dev (uvicorn) + Vercel serverless (same codebase)

## Hybrid Documentation Pipeline
1. User uploads Python code (files, ZIP, or GitHub repo)
2. AST parser extracts classes, functions, imports, and metrics
3. If CodeT5 is configured: each function/class is sent to the fine-tuned model for a one-line summary
4. LLM (Groq/Gemini) receives the code outline + CodeT5 summaries as context → generates full module documentation
5. LLM generates project overview combining all module analyses
6. UML diagrams generated from AST data (no LLM needed)
7. Everything saved to Supabase for persistence and later editing

## Dependencies
- fastapi, uvicorn
- langchain-core, langchain-groq, langchain-google-genai
- PyJWT, httpx, requests
- fpdf2, pyyaml, python-dotenv, python-multipart

## Development Note
The API Server workflow on Replit should only be started during active development/testing. Stop it when not in use to avoid consuming Replit credits. For production, deploy to Vercel (serverless, free tier).

## Deployment
See `DEPLOY.md` for Vercel deployment. See `API_DOCS.md` for full API reference.
