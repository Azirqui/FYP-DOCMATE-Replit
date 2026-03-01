from __future__ import annotations

import base64
from typing import Optional, List, Dict

import httpx


GITHUB_API = "https://api.github.com"


async def get_user_repos(
    access_token: str,
    page: int = 1,
    per_page: int = 30,
) -> List[Dict]:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{GITHUB_API}/user/repos",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
            },
            params={
                "sort": "updated",
                "direction": "desc",
                "page": page,
                "per_page": per_page,
                "type": "all",
            },
            timeout=30,
        )
        
        if response.status_code != 200:
            raise Exception(f"GitHub API error: {response.status_code} - {response.text}")
        
        repos = response.json()
        return [
            {
                "id": repo["id"],
                "name": repo["name"],
                "full_name": repo["full_name"],
                "description": repo.get("description", ""),
                "language": repo.get("language", ""),
                "default_branch": repo.get("default_branch", "main"),
                "private": repo["private"],
                "updated_at": repo.get("updated_at", ""),
                "html_url": repo.get("html_url", ""),
            }
            for repo in repos
        ]


async def get_repo_python_files(
    access_token: str,
    owner: str,
    repo: str,
    branch: str = "main",
    max_files: int = 50,
) -> List[Dict[str, str]]:
    tree = await _get_repo_tree(access_token, owner, repo, branch)
    
    py_files = [
        item for item in tree
        if item.get("path", "").endswith(".py")
        and item.get("type") == "blob"
        and item.get("size", 0) < 500000
    ]
    
    py_files = py_files[:max_files]
    
    files = []
    for file_info in py_files:
        content = await _get_file_content(
            access_token, owner, repo, file_info["path"], branch
        )
        if content is not None:
            files.append({
                "filename": file_info["path"],
                "content": content,
            })
    
    return files


async def _get_repo_tree(
    access_token: str,
    owner: str,
    repo: str,
    branch: str,
) -> List[Dict]:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{branch}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
            },
            params={"recursive": "1"},
            timeout=30,
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to get repo tree: {response.status_code}")
        
        return response.json().get("tree", [])


async def _get_file_content(
    access_token: str,
    owner: str,
    repo: str,
    path: str,
    branch: str,
) -> Optional[str]:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
            },
            params={"ref": branch},
            timeout=30,
        )
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        
        if data.get("encoding") == "base64" and data.get("content"):
            try:
                return base64.b64decode(data["content"]).decode("utf-8")
            except (UnicodeDecodeError, Exception):
                return None
        
        return None
