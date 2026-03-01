from __future__ import annotations

import os
import time
from typing import Optional
from functools import wraps

from fastapi import HTTPException, Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

import jwt


SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
SUPABASE_URL = os.getenv("SUPABASE_URL")


security = HTTPBearer(auto_error=False)


def decode_supabase_token(token: str) -> Optional[dict]:
    if not SUPABASE_JWT_SECRET:
        return None
    
    try:
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
        
        exp = payload.get("exp", 0)
        if exp < time.time():
            return None
        
        return payload
    except jwt.InvalidTokenError:
        return None


async def get_current_user(
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> Optional[dict]:
    if not authorization:
        return None
    
    if not authorization.startswith("Bearer "):
        return None
    
    token = authorization[7:]
    return decode_supabase_token(token)


async def require_auth(
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> dict:
    if not SUPABASE_JWT_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Authentication not configured. Set SUPABASE_JWT_SECRET."
        )
    
    user = await get_current_user(authorization)
    
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authentication token"
        )
    
    return user


def get_user_id(user: dict) -> str:
    return user.get("sub", "")


def get_user_email(user: dict) -> Optional[str]:
    return user.get("email")
