from __future__ import annotations

import os
from typing import Optional, Any

import httpx


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")


def _headers() -> dict[str, str]:
    return {
        "apikey": SUPABASE_SERVICE_KEY or "",
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY or ''}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _url(table: str) -> str:
    return f"{SUPABASE_URL}/rest/v1/{table}"


def is_configured() -> bool:
    return bool(SUPABASE_URL and SUPABASE_SERVICE_KEY)


async def create_project(user_id: str, name: str, description: str = "") -> Optional[dict]:
    if not is_configured():
        return None
    async with httpx.AsyncClient() as client:
        response = await client.post(
            _url("projects"),
            headers=_headers(),
            json={"user_id": user_id, "name": name, "description": description},
        )
        if response.status_code in (200, 201):
            data = response.json()
            return data[0] if isinstance(data, list) else data
        return None


async def save_files(project_id: str, files: list[dict[str, str]]) -> bool:
    if not is_configured():
        return False
    rows = [
        {
            "project_id": project_id,
            "filename": f["filename"],
            "content": f["content"],
            "file_path": f.get("file_path", f["filename"]),
        }
        for f in files
    ]
    async with httpx.AsyncClient() as client:
        response = await client.post(
            _url("project_files"),
            headers=_headers(),
            json=rows,
        )
        return response.status_code in (200, 201)


async def save_docs(
    project_id: str,
    docs: list[dict[str, Any]],
) -> Optional[list[dict]]:
    if not is_configured():
        return None
    rows = [
        {
            "project_id": project_id,
            "doc_type": d["doc_type"],
            "module_name": d.get("module_name"),
            "content": d["content"],
            "version": 1,
        }
        for d in docs
    ]
    async with httpx.AsyncClient() as client:
        response = await client.post(
            _url("generated_docs"),
            headers=_headers(),
            json=rows,
        )
        if response.status_code in (200, 201):
            return response.json()
        return None


async def save_uml(project_id: str, diagrams: dict[str, str]) -> bool:
    if not is_configured():
        return False
    rows = [
        {"project_id": project_id, "diagram_type": dtype, "content": content}
        for dtype, content in diagrams.items()
        if content
    ]
    if not rows:
        return True
    async with httpx.AsyncClient() as client:
        response = await client.post(
            _url("generated_uml"),
            headers=_headers(),
            json=rows,
        )
        return response.status_code in (200, 201)


async def list_user_projects(user_id: str) -> list[dict]:
    if not is_configured():
        return []
    async with httpx.AsyncClient() as client:
        response = await client.get(
            _url("projects"),
            headers=_headers(),
            params={
                "user_id": f"eq.{user_id}",
                "select": "id,name,description,created_at,updated_at",
                "order": "created_at.desc",
            },
        )
        if response.status_code == 200:
            return response.json()
        return []


async def get_project(project_id: str, user_id: str) -> Optional[dict]:
    if not is_configured():
        return None
    async with httpx.AsyncClient() as client:
        response = await client.get(
            _url("projects"),
            headers=_headers(),
            params={
                "id": f"eq.{project_id}",
                "user_id": f"eq.{user_id}",
                "select": "*",
            },
        )
        if response.status_code == 200:
            data = response.json()
            return data[0] if data else None
        return None


async def get_project_files(project_id: str) -> list[dict]:
    if not is_configured():
        return []
    async with httpx.AsyncClient() as client:
        response = await client.get(
            _url("project_files"),
            headers=_headers(),
            params={
                "project_id": f"eq.{project_id}",
                "select": "id,filename,file_path,content,created_at",
                "order": "filename.asc",
            },
        )
        if response.status_code == 200:
            return response.json()
        return []


async def get_project_docs(project_id: str) -> list[dict]:
    if not is_configured():
        return []
    async with httpx.AsyncClient() as client:
        response = await client.get(
            _url("generated_docs"),
            headers=_headers(),
            params={
                "project_id": f"eq.{project_id}",
                "select": "id,doc_type,module_name,content,version,created_at,updated_at",
                "order": "doc_type.asc,module_name.asc",
            },
        )
        if response.status_code == 200:
            return response.json()
        return []


async def get_project_uml(project_id: str) -> list[dict]:
    if not is_configured():
        return []
    async with httpx.AsyncClient() as client:
        response = await client.get(
            _url("generated_uml"),
            headers=_headers(),
            params={
                "project_id": f"eq.{project_id}",
                "select": "id,diagram_type,content,created_at",
            },
        )
        if response.status_code == 200:
            return response.json()
        return []


async def get_doc_by_id(doc_id: str) -> Optional[dict]:
    if not is_configured():
        return None
    async with httpx.AsyncClient() as client:
        response = await client.get(
            _url("generated_docs"),
            headers=_headers(),
            params={
                "id": f"eq.{doc_id}",
                "select": "id,project_id,doc_type,module_name,content,version,created_at,updated_at",
            },
        )
        if response.status_code == 200:
            data = response.json()
            return data[0] if data else None
        return None


async def update_doc_content(doc_id: str, new_content: str, new_version: int) -> Optional[dict]:
    if not is_configured():
        return None
    async with httpx.AsyncClient() as client:
        response = await client.patch(
            _url("generated_docs") + f"?id=eq.{doc_id}",
            headers=_headers(),
            json={"content": new_content, "version": new_version},
        )
        if response.status_code in (200, 204):
            data = response.json() if response.status_code == 200 else None
            if isinstance(data, list) and data:
                return data[0]
            return {"id": doc_id, "content": new_content, "version": new_version}
        return None


async def delete_project(project_id: str, user_id: str) -> bool:
    if not is_configured():
        return False
    async with httpx.AsyncClient() as client:
        response = await client.delete(
            _url("projects") + f"?id=eq.{project_id}&user_id=eq.{user_id}",
            headers={
                "apikey": SUPABASE_SERVICE_KEY or "",
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY or ''}",
            },
        )
        return response.status_code in (200, 204)


async def get_project_owner(project_id: str) -> Optional[str]:
    if not is_configured():
        return None
    async with httpx.AsyncClient() as client:
        response = await client.get(
            _url("projects"),
            headers=_headers(),
            params={
                "id": f"eq.{project_id}",
                "select": "user_id",
            },
        )
        if response.status_code == 200:
            data = response.json()
            if data:
                return data[0].get("user_id")
        return None
