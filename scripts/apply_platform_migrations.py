"""Apply db/migrations/*.sql to DATABASE_URL, backfill profiles, seed admins.

Usage: DATABASE_URL=... PLATFORM_ADMIN_EMAILS=a@b.c .venv/bin/python scripts/apply_platform_migrations.py
Idempotent. Seeding only happens while no approved admin exists (bootstrap).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg

MIGRATIONS = Path(__file__).resolve().parents[1] / "db" / "migrations"
APPS = ("linkedin", "queue")
_META = ("coalesce(u.raw_user_meta_data->>'full_name', u.raw_user_meta_data->>'name'), "
         "coalesce(u.raw_user_meta_data->>'avatar_url', u.raw_user_meta_data->>'picture')")


def apply_migrations(conn: psycopg.Connection) -> list[str]:
    conn.execute("create schema if not exists platform")
    conn.execute("create table if not exists platform.schema_migrations ("
                 "version text primary key, applied_at timestamptz not null default now())")
    done = {r[0] for r in conn.execute("select version from platform.schema_migrations")}
    applied = []
    for path in sorted(MIGRATIONS.glob("*.sql")):
        if path.stem in done:
            continue
        with conn.transaction():
            conn.execute(path.read_text())
            conn.execute("insert into platform.schema_migrations (version) values (%s)", (path.stem,))
        applied.append(path.stem)
    return applied


def backfill_profiles(conn: psycopg.Connection) -> int:
    cur = conn.execute(
        "insert into platform.profiles (user_id, email, display_name, avatar_url, created_at) "
        f"select u.id, u.email, {_META}, u.created_at from auth.users u "
        "on conflict (user_id) do nothing")
    return cur.rowcount


def seed_admins(conn: psycopg.Connection, emails: list[str]) -> int:
    wanted = [e.strip().lower() for e in emails if e.strip()]
    with conn.transaction():
        if conn.execute("select 1 from platform.profiles where is_admin and status = 'approved'"
                        " limit 1").fetchone():
            return 0
        ids = [r[0] for r in conn.execute(
            "update platform.profiles set status = 'approved', is_admin = true, "
            "status_changed_at = now(), updated_at = now() "
            "where lower(email) = any(%s) returning user_id", (wanted,))]
        if ids:
            conn.execute(
                "insert into platform.app_memberships (user_id, app) "
                "select u, a from unnest(%s::uuid[]) u cross join unnest(%s::text[]) a "
                "on conflict do nothing", (ids, list(APPS)))
    return len(ids)


def main() -> int:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL is required", file=sys.stderr)
        return 2
    emails = os.environ.get("PLATFORM_ADMIN_EMAILS", "").split(",")
    with psycopg.connect(url, autocommit=True, prepare_threshold=None) as conn:
        print("applied:", apply_migrations(conn) or "nothing new")
        print("profiles backfilled:", backfill_profiles(conn))
        print("admins seeded:", seed_admins(conn, emails))
    return 0


if __name__ == "__main__":
    sys.exit(main())
