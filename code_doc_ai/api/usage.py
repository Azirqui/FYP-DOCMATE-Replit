from __future__ import annotations

import os
import time
from typing import Optional
from datetime import datetime, timedelta

import httpx


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

DAILY_LIMIT = int(os.getenv("DAILY_GENERATION_LIMIT", "50"))


async def get_user_usage_today(user_id: str) -> int:
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return 0
    
    today = datetime.utcnow().date().isoformat()
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{SUPABASE_URL}/rest/v1/usage_logs",
                headers={
                    "apikey": SUPABASE_SERVICE_KEY,
                    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                },
                params={
                    "user_id": f"eq.{user_id}",
                    "created_at": f"gte.{today}T00:00:00Z",
                    "select": "id",
                },
            )
            
            if response.status_code == 200:
                return len(response.json())
    except Exception:
        pass
    
    return 0


async def log_usage(
    user_id: str,
    endpoint: str,
    files_count: int = 0,
    success: bool = True,
) -> bool:
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return True
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{SUPABASE_URL}/rest/v1/usage_logs",
                headers={
                    "apikey": SUPABASE_SERVICE_KEY,
                    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal",
                },
                json={
                    "user_id": user_id,
                    "endpoint": endpoint,
                    "files_count": files_count,
                    "success": success,
                },
            )
            return response.status_code in (200, 201)
    except Exception:
        return False


async def check_rate_limit(user_id: str) -> tuple[bool, int]:
    usage = await get_user_usage_today(user_id)
    remaining = max(0, DAILY_LIMIT - usage)
    return usage < DAILY_LIMIT, remaining
