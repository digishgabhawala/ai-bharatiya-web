"""Who is calling: a Supabase session token, checked against Supabase.

Same approach as LinkedIn and task-queue: ask Supabase `/auth/v1/user` who the
token belongs to, and cache the answer briefly -- never past the token's own
expiry. Only the identity is cached; the profile is read fresh per request.
There is no allow list and no disabled mode: this API always needs a session.
"""
from __future__ import annotations

import base64
import hashlib
import json
import time
from dataclasses import dataclass

import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from _platform_api.config import settings

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Identity:
    id: str
    email: str
    display_name: str | None = None
    avatar_url: str | None = None


# sha256(token) -> (identity, expiry as epoch seconds)
_cache: dict[str, tuple[Identity, float]] = {}


def clear_cache() -> None:
    _cache.clear()


def _unauthorized() -> HTTPException:
    return HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})


async def _fetch_supabase_user(token: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.supabase_url.rstrip('/')}/auth/v1/user",
                                    headers={"apikey": settings.supabase_publishable_key,
                                             "Authorization": f"Bearer {token}"})
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Identity service is temporarily unavailable") from exc
    if resp.status_code != 200:
        raise _unauthorized()
    return resp.json()


def _token_expiry(token: str) -> float:
    """The JWT's `exp`, read without verifying (Supabase already did that).
    0 when unreadable, so such a token is never cached."""
    try:
        payload = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        return float(claims["exp"])
    except (IndexError, KeyError, TypeError, ValueError):
        return 0.0


async def current_identity(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Identity:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise _unauthorized()

    token = credentials.credentials
    key = hashlib.sha256(token.encode()).hexdigest()
    now = time.time()
    cached = _cache.get(key)
    if cached and cached[1] > now:
        return cached[0]

    payload = await _fetch_supabase_user(token)
    user_id = str(payload.get("id") or "")
    if not user_id:
        raise _unauthorized()
    meta = payload.get("user_metadata") or {}
    identity = Identity(id=user_id,
                        email=str(payload.get("email") or "").strip().casefold(),
                        display_name=meta.get("full_name") or meta.get("name"),
                        avatar_url=meta.get("avatar_url") or meta.get("picture"))
    _cache[key] = (identity, min(now + settings.auth_cache_minutes * 60, _token_expiry(token)))
    return identity
