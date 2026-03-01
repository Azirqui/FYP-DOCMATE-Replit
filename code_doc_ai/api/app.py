from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import router

app = FastAPI(
    title="Code Documentation AI",
    description="AI-powered code documentation generator with UML diagram support",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "name": "Code Documentation AI",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "health": "/api/v1/health",
            "analyze-text": "/api/v1/analyze-text",
            "upload-files": "/api/v1/upload-files",
            "upload-zip": "/api/v1/upload-zip",
            "docs-text": "/api/v1/docs-text",
            "uml-text": "/api/v1/uml-text",
            "docstring": "/api/v1/docstring",
            "export-pdf": "/api/v1/export-pdf",
            "github-repos": "/api/v1/github/repos",
            "github-analyze": "/api/v1/github/analyze",
            "github-export-pdf": "/api/v1/github/export-pdf",
        },
        "auth": "Bearer token in Authorization header (Supabase JWT)",
    }
