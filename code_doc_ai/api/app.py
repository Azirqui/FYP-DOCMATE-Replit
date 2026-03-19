from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import router

app = FastAPI(
    title="Code Documentation AI",
    description="AI-powered code documentation generator with UML diagram support",
    version="2.0.0",
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
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/api/v1/health",
        "auth": "All endpoints require Bearer token in Authorization header (Supabase JWT), except /api/v1/health",
    }
