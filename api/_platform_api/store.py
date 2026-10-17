"""Postgres access to platform.profiles / platform.app_memberships.

One short connection per call: this runs in a serverless function behind the
Supabase transaction pooler, so no pool and no prepared statements.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

import psycopg

from _platform_api import transitions
from _platform_api.transitions import Subject


@dataclass(frozen=True)
class Profile:
    user_id: str
    email: str | None
    display_name: str | None
    avatar_url: str | None
    status: str
    is_admin: bool
    created_at: datetime
    updated_at: datetime
    status_changed_at: datetime | None
    status_changed_by: str | None


class NotFound(Exception):
    pass


class Store(Protocol):
    def get_profile(self, user_id: str) -> Profile | None: ...
    def ensure_profile(self, user_id: str, email: str | None, display_name: str | None,
                       avatar_url: str | None) -> Profile: ...
    def apps_for(self, user_id: str) -> list[str]: ...
    def list_profiles(self, status: str | None) -> list[Profile]: ...
    def change_status(self, *, actor_id: str, target_id: str, action: str) -> Profile: ...
    def set_admin(self, *, actor_id: str, target_id: str, is_admin: bool) -> Profile: ...


_COLS = ("user_id::text, email, display_name, avatar_url, status, is_admin, created_at, "
         "updated_at, status_changed_at, status_changed_by::text")
_APPROVED_ADMINS = ("select user_id from platform.profiles where is_admin and status = 'approved' "
                    "order by user_id for update")


class PgStore:
    def __init__(self, dsn: str):
        self._dsn = dsn

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self._dsn, prepare_threshold=None)  # `with` commits on exit

    @staticmethod
    def _get(conn: psycopg.Connection, user_id: str, *, lock: bool = False) -> Profile | None:
        sql = f"select {_COLS} from platform.profiles where user_id = %s"
        row = conn.execute(sql + (" for update" if lock else ""), (user_id,)).fetchone()
        return Profile(*row) if row else None

    def _locked(self, conn: psycopg.Connection, user_id: str) -> tuple[Profile, int]:
        admins = conn.execute(_APPROVED_ADMINS).fetchall()
        target = self._get(conn, user_id, lock=True)
        if target is None:
            raise NotFound(user_id)
        return target, len(admins)

    def get_profile(self, user_id: str) -> Profile | None:
        with self._connect() as conn:
            return self._get(conn, user_id)

    def ensure_profile(self, user_id, email, display_name, avatar_url) -> Profile:
        with self._connect() as conn:
            conn.execute("insert into platform.profiles (user_id, email, display_name, avatar_url) "
                         "values (%s, %s, %s, %s) on conflict (user_id) do nothing",
                         (user_id, email, display_name, avatar_url))
            return self._get(conn, user_id)

    def apps_for(self, user_id: str) -> list[str]:
        with self._connect() as conn:
            return [r[0] for r in conn.execute(
                "select app from platform.app_memberships where user_id = %s order by app",
                (user_id,))]

    def list_profiles(self, status: str | None = None) -> list[Profile]:
        where, args = ("where status = %s", (status,)) if status else ("", ())
        with self._connect() as conn:
            rows = conn.execute(
                f"select {_COLS} from platform.profiles {where} "
                "order by (status = 'pending') desc, created_at desc limit 500", args).fetchall()
        return [Profile(*r) for r in rows]

    def change_status(self, *, actor_id: str, target_id: str, action: str) -> Profile:
        with self._connect() as conn:
            target, admins = self._locked(conn, target_id)
            new = transitions.status_change(
                action, actor_id=actor_id, approved_admins=admins,
                target=Subject(target.user_id, target.status, target.is_admin))
            conn.execute("update platform.profiles set status = %s, status_changed_at = now(), "
                         "status_changed_by = %s, updated_at = now() where user_id = %s",
                         (new, actor_id, target_id))
            if new == "approved":
                conn.execute("insert into platform.app_memberships (user_id, app) "
                             "select %s, unnest(%s::text[]) on conflict do nothing",
                             (target_id, list(transitions.APPS)))
            return self._get(conn, target_id)

    def set_admin(self, *, actor_id: str, target_id: str, is_admin: bool) -> Profile:
        with self._connect() as conn:
            target, admins = self._locked(conn, target_id)
            transitions.admin_change(
                actor_id=actor_id, make_admin=is_admin, approved_admins=admins,
                target=Subject(target.user_id, target.status, target.is_admin))
            conn.execute("update platform.profiles set is_admin = %s, updated_at = now() "
                         "where user_id = %s", (is_admin, target_id))
            return self._get(conn, target_id)
