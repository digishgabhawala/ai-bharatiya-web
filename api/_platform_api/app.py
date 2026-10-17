"""/api/platform/*: who am I, and the admin's approval screen."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from pydantic import BaseModel

from _platform_api.auth import Identity, current_identity
from _platform_api.config import settings
from _platform_api.store import NotFound, PgStore, Profile, Store
from _platform_api.transitions import TransitionError

app = FastAPI(title="AI Bharatiyaa platform", docs_url=None, redoc_url=None, openapi_url=None)
router = APIRouter(prefix="/api/platform")

Status = Literal["pending", "approved", "rejected", "suspended"]


@lru_cache
def _pg() -> PgStore:
    return PgStore(settings.database_url)


def get_store() -> Store:
    return _pg()


def require_admin(identity: Identity = Depends(current_identity),
                  store: Store = Depends(get_store)) -> Identity:
    p = store.get_profile(identity.id)
    if p is None or not (p.is_admin and p.status == "approved"):
        raise HTTPException(403, "Admins only")
    return identity


def _iso(value):
    return value.isoformat() if value is not None else None


def _view(p: Profile) -> dict:
    return {"user_id": p.user_id, "email": p.email, "display_name": p.display_name,
            "avatar_url": p.avatar_url, "status": p.status, "is_admin": p.is_admin,
            "created_at": _iso(p.created_at), "status_changed_at": _iso(p.status_changed_at)}


class AdminFlag(BaseModel):
    is_admin: bool


@router.get("/config")
def config() -> dict:
    """Only values that are explicitly safe to expose to a browser."""
    return {"supabase_url": settings.supabase_url,
            "supabase_publishable_key": settings.supabase_publishable_key}


@router.get("/me")
def me(identity: Identity = Depends(current_identity), store: Store = Depends(get_store)) -> dict:
    # Self-heals a user who predates the sign-up trigger and missed the backfill.
    p = store.ensure_profile(identity.id, identity.email or None, identity.display_name,
                             identity.avatar_url)
    return {"user_id": p.user_id, "email": p.email, "display_name": p.display_name,
            "avatar_url": p.avatar_url, "status": p.status, "is_admin": p.is_admin,
            "apps": store.apps_for(p.user_id)}


@router.get("/users")
def users(status: Status | None = None, admin: Identity = Depends(require_admin),
          store: Store = Depends(get_store)) -> list[dict]:
    return [_view(p) for p in store.list_profiles(status)]


@router.post("/users/{user_id}/admin")
def set_admin(user_id: UUID, body: AdminFlag, admin: Identity = Depends(require_admin),
              store: Store = Depends(get_store)) -> dict:
    try:
        return _view(store.set_admin(actor_id=admin.id, target_id=str(user_id),
                                     is_admin=body.is_admin))
    except NotFound:
        raise HTTPException(404, "user not found") from None
    except TransitionError as e:
        raise HTTPException(409, str(e)) from None


@router.post("/users/{user_id}/{action}")
def change(user_id: UUID, action: Literal["approve", "reject", "suspend", "reinstate"],
           admin: Identity = Depends(require_admin), store: Store = Depends(get_store)) -> dict:
    try:
        return _view(store.change_status(actor_id=admin.id, target_id=str(user_id), action=action))
    except NotFound:
        raise HTTPException(404, "user not found") from None
    except TransitionError as e:
        raise HTTPException(409, str(e)) from None


app.include_router(router)
