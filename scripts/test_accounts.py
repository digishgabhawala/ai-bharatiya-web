"""Create and delete throwaway test accounts in a Supabase project.

Used by the production journey checks (tests/production/test_journeys.py),
which import ``create_accounts`` / ``delete_accounts`` so the random passwords
only ever live in that process's memory.

    python scripts/test_accounts.py create   # prints the two accounts as JSON once
    python scripts/test_accounts.py delete   # deletes every e2e-*@example.com account

Environment (never written to disk by this script):
    SUPABASE_URL, SUPABASE_SERVICE_KEY   Auth admin API (create/delete users)
    DATABASE_URL                         verify profiles; delete app rows the
                                         test accounts created (optional for create)

Both accounts are created with ``email_confirm: true`` and start ``pending``
through the sign-up trigger. Approving one is the caller's job, through the
real admin API, so the journey also proves the admin flow.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import sys
import time

import httpx

EMAIL_PATTERN = re.compile(r"^e2e-(approved|pending)\+\d+@example\.com$")

# Rows that app code creates per user. Order matters: children before parents.
# post_drafts / feedback hang off posts; hero rows hang off characters.
_OWNED_ROW_DELETES = (
    ("delete from linkedin.post_drafts where post_id in "
    "(select id from linkedin.posts where owner_id = any(%(ids)s))"),
    ("delete from linkedin.feedback where post_id in "
    "(select id from linkedin.posts where owner_id = any(%(ids)s))"),
    "delete from linkedin.posts where owner_id = any(%(ids)s)",
    ("delete from linkedin.hero_candidates where run_id in (select r.id from "
    "linkedin.hero_generation_runs r join linkedin.characters c using (character_id) "
    "where c.owner_id = any(%(ids)s))"),
    ("delete from linkedin.hero_generation_runs where character_id in "
    "(select character_id from linkedin.characters where owner_id = any(%(ids)s))"),
    "delete from linkedin.characters where owner_id = any(%(ids)s)",
    "delete from linkedin.scene_asset_versions where owner_id = any(%(ids)s)",
    "delete from linkedin.scene_assets where owner_id = any(%(ids)s)",
    "delete from linkedin.writer_profiles where owner_id = any(%(ids)s)",
    "delete from public.worker_keys where user_id::text = any(%(ids)s)",
)


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is not set")
    return value


def _pg_url() -> str:
    return re.sub(r"^postgresql\+\w+://", "postgresql://", _env("DATABASE_URL"))


def _admin_client() -> httpx.Client:
    key = _env("SUPABASE_SERVICE_KEY")
    return httpx.Client(base_url=_env("SUPABASE_URL").rstrip("/") + "/auth/v1",
                        headers={"apikey": key, "Authorization": f"Bearer {key}"},
                        timeout=30)


def _password() -> str:
    return secrets.token_urlsafe(24) + "!a9"


def create_accounts() -> dict[str, dict[str, str]]:
    """Create ``approved`` and ``pending`` accounts (both start pending)."""
    stamp = str(int(time.time()))
    accounts: dict[str, dict[str, str]] = {}
    with _admin_client() as client:
        for role in ("approved", "pending"):
            email = f"e2e-{role}+{stamp}@example.com"
            password = _password()
            resp = client.post("/admin/users", json={
                "email": email, "password": password, "email_confirm": True})
            if resp.status_code not in (200, 201):
                raise SystemExit(f"creating {email} failed: HTTP {resp.status_code}")
            accounts[role] = {"id": resp.json()["id"], "email": email, "password": password}
    return accounts


def profile_statuses(user_ids: list[str]) -> dict[str, str]:
    import psycopg
    with psycopg.connect(_pg_url()) as conn:
        rows = conn.execute("select user_id::text, status from platform.profiles "
                            "where user_id::text = any(%s)", (user_ids,)).fetchall()
    return dict(rows)


def _list_test_users(client: httpx.Client) -> list[dict]:
    found, page = [], 1
    while True:
        resp = client.get("/admin/users", params={"page": page, "per_page": 200})
        resp.raise_for_status()
        users = resp.json().get("users", [])
        found += [u for u in users if EMAIL_PATTERN.match(u.get("email") or "")]
        if len(users) < 200:
            return found
        page += 1


def delete_accounts(user_ids: list[str] | None = None) -> list[str]:
    """Delete the given test users (default: every e2e-*@example.com user).

    App rows they own go first (when DATABASE_URL is set); deleting the auth
    user then cascades to platform.profiles / platform.app_memberships.
    """
    with _admin_client() as client:
        if user_ids is None:
            user_ids = [u["id"] for u in _list_test_users(client)]
        if user_ids and os.environ.get("DATABASE_URL"):
            import psycopg
            with psycopg.connect(_pg_url()) as conn:
                for sql in _OWNED_ROW_DELETES:
                    conn.execute(sql, {"ids": user_ids})
        for user_id in user_ids:
            resp = client.delete(f"/admin/users/{user_id}")
            if resp.status_code not in (200, 204, 404):
                raise SystemExit(f"deleting {user_id} failed: HTTP {resp.status_code}")
    return user_ids


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=["create", "delete"])
    args = parser.parse_args(argv)
    if args.command == "create":
        print(json.dumps(create_accounts(), indent=2))
    else:
        deleted = delete_accounts()
        print(f"deleted {len(deleted)} test account(s)")


if __name__ == "__main__":
    main(sys.argv[1:])
