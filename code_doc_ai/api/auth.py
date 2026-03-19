from __future__ import annotations

import os
import time
import logging
from typing import Optional

from fastapi import HTTPException, Header, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

import jwt
from jwt import PyJWKClient

logger = logging.getLogger(__name__)

_jwks_client: Optional[PyJWKClient] = None


def _get_jwt_secret():
    return os.getenv("SUPABASE_JWT_SECRET")


def _get_supabase_url():
    return os.getenv("SUPABASE_URL")


def _get_jwks_client() -> Optional[PyJWKClient]:
    global _jwks_client
    if _jwks_client is not None:
        return _jwks_client

    supabase_url = _get_supabase_url()
    if not supabase_url:
        return None

    supabase_url = supabase_url.rstrip("/")
    jwks_url = f"{supabase_url}/auth/v1/.well-known/jwks.json"
    try:
        _jwks_client = PyJWKClient(jwks_url, cache_keys=True, lifespan=3600)
        return _jwks_client
    except Exception as e:
        logger.warning("Failed to create JWKS client: %s", e)
        return None


security = HTTPBearer(auto_error=False)


def _detect_algorithm(token: str) -> str:
    try:
        header = jwt.get_unverified_header(token)
        return header.get("alg", "HS256")
    except Exception:
        return "HS256"


def _expected_issuer() -> Optional[str]:
    url = _get_supabase_url()
    if not url:
        return None
    return f"{url.rstrip('/')}/auth/v1"


def _decode_es256(token: str) -> Optional[dict]:
    client = _get_jwks_client()
    if not client:
        return None

    try:
        signing_key = client.get_signing_key_from_jwt(token)
        decode_opts = {
            "algorithms": ["ES256"],
            "audience": "authenticated",
        }
        issuer = _expected_issuer()
        if issuer:
            decode_opts["issuer"] = issuer
        payload = jwt.decode(token, signing_key.key, **decode_opts)
        return payload
    except jwt.ExpiredSignatureError:
        logger.debug("ES256 token expired")
        return None
    except jwt.InvalidIssuerError:
        logger.debug("ES256 token has invalid issuer")
        return None
    except jwt.InvalidAudienceError:
        logger.debug("ES256 token has invalid audience")
        return None
    except Exception as e:
        logger.debug("ES256 decode failed: %s", e)
        return None


def _decode_hs256(token: str) -> Optional[dict]:
    secret = _get_jwt_secret()
    if not secret:
        return None

    try:
        decode_opts = {
            "algorithms": ["HS256"],
            "audience": "authenticated",
        }
        issuer = _expected_issuer()
        if issuer:
            decode_opts["issuer"] = issuer
        payload = jwt.decode(token, secret, **decode_opts)
        return payload
    except jwt.ExpiredSignatureError:
        logger.debug("HS256 token expired")
        return None
    except jwt.InvalidIssuerError:
        logger.debug("HS256 token has invalid issuer")
        return None
    except jwt.InvalidAudienceError:
        logger.debug("HS256 token has invalid audience")
        return None
    except Exception as e:
        logger.debug("HS256 decode failed: %s", e)
        return None


def decode_supabase_token(token: str) -> Optional[dict]:
    alg = _detect_algorithm(token)

    if alg == "ES256":
        payload = _decode_es256(token)
        if payload is None:
            payload = _decode_hs256(token)
    else:
        payload = _decode_hs256(token)
        if payload is None:
            payload = _decode_es256(token)

    if payload is None:
        return None

    exp = payload.get("exp", 0)
    if exp < time.time():
        return None

    return payload


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
    secret = _get_jwt_secret()
    supabase_url = _get_supabase_url()
    if not secret and not supabase_url:
        raise HTTPException(
            status_code=503,
            detail="Authentication not configured. Set SUPABASE_JWT_SECRET or SUPABASE_URL."
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
