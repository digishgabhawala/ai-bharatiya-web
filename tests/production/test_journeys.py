"""Production journey checks for user management (plan task F1 / F-R).

PRODUCTION: creates two throwaway accounts, uses the real admin API and UI,
then deletes everything the accounts created. Run only when named explicitly
(pytest.ini ignores tests/production):

    .venv/bin/pytest -q -p no:cacheprovider tests/production

Environment: SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, SUPABASE_SERVICE_KEY,
DATABASE_URL, E2E_LOGIN_EMAIL / E2E_LOGIN_PASSWORD (an approved admin).
Optional JOURNEY_BASE_URL (default https://ai-bharatiya-web.vercel.app).

Every test takes ``page`` so pytest-playwright keeps file order (it otherwise
runs browser tests first). Tests share state through the module-scoped ``ctx``.
Test-account passwords exist only in this process's memory.
"""
from __future__ import annotations

import os
import re
import time

import httpx
import psycopg
import pytest
from playwright.sync_api import Page, expect

from scripts import test_accounts as accounts_script

BASE = os.environ.get("JOURNEY_BASE_URL", "https://ai-bharatiya-web.vercel.app").rstrip("/")
SUSPEND_PROPAGATION_SECONDS = 120
BRIEF_MARKER = "e2e journey check"  # in every brief this module submits


def _db(sql: str, params=None):
    with psycopg.connect(accounts_script._pg_url()) as conn:
        cur = conn.execute(sql, params)
        return cur.fetchall() if cur.description else cur.rowcount


def _token(email: str, password: str) -> str:
    resp = httpx.post(
        f"{os.environ['SUPABASE_URL'].rstrip('/')}/auth/v1/token",
        params={"grant_type": "password"},
        headers={"apikey": os.environ["SUPABASE_PUBLISHABLE_KEY"]},
        json={"email": email, "password": password}, timeout=30)
    assert resp.status_code == 200, f"password sign-in failed for {email}: {resp.status_code}"
    return resp.json()["access_token"]


def _api(method: str, path: str, token: str, **kw) -> httpx.Response:
    return httpx.request(method, f"{BASE}{path}", headers={"Authorization": f"Bearer {token}"},
                         timeout=60, **kw)


def _reason(resp: httpx.Response) -> str | None:
    try:
        body = resp.json()
    except ValueError:
        return None
    detail = body.get("detail")
    return body.get("reason") or (detail.get("reason") if isinstance(detail, dict) else None)


def _sign_in(page: Page, email: str, password: str, next_path: str) -> None:
    page.goto(f"{BASE}/login?next={next_path}")
    page.click("#email-toggle")
    page.fill("#login-email", email)
    page.fill("#login-password", password)
    page.click("#email-form button[type=submit]")
    page.wait_for_url(re.compile(re.escape(BASE + next_path)), timeout=30_000)


class _Secrets(dict):
    """Keeps passwords and tokens out of pytest's failure output."""

    def __repr__(self) -> str:
        return "<redacted>"


@pytest.fixture(scope="module")
def ctx():
    for name in ("E2E_LOGIN_EMAIL", "E2E_LOGIN_PASSWORD", "SUPABASE_PUBLISHABLE_KEY"):
        assert os.environ.get(name), f"{name} is not set"
    state = _Secrets({"accounts": accounts_script.create_accounts()})
    state["ids"] = [a["id"] for a in state["accounts"].values()]
    state["tasks_before"] = {r[0] for r in _db("select id::text from public.tasks")}
    state["admin_token"] = _token(os.environ["E2E_LOGIN_EMAIL"], os.environ["E2E_LOGIN_PASSWORD"])
    try:
        yield state
    finally:
        _cleanup(state)


def _cleanup(state: dict) -> None:
    ids = state["ids"]
    # Queue tasks this run's posts submitted (tasks have no owner column).
    post_ids = [r[0] for r in _db("select id from linkedin.posts where owner_id = any(%s)", (ids,))]
    new_tasks = [r[0] for r in _db("select id::text from public.tasks")
                 if r[0] not in state["tasks_before"]]
    referenced = [t for t in new_tasks if _db(
        "select 1 from linkedin.posts where id = any(%s) and "
        "(active_step::text like %s or step_context::text like %s or image_task_id::text = %s)",
        (post_ids, f"%{t}%", f"%{t}%", t))]
    # A worker may finish a step before cleanup and the post move on, so the
    # post no longer names the task; the journey's briefs carry BRIEF_MARKER.
    referenced += [r[0] for r in _db(
        "select id::text from public.tasks where id::text = any(%s) and payload::text like %s",
        (new_tasks, f"%{BRIEF_MARKER}%")) if r[0] not in referenced]
    if referenced:
        _db("delete from public.tasks where id::text = any(%s)", (referenced,))
    state["deleted_tasks"] = referenced
    accounts_script.delete_accounts(ids)


@pytest.fixture(scope="module")
def tokens(ctx):
    a = ctx["accounts"]
    return _Secrets({role: _token(a[role]["email"], a[role]["password"]) for role in a})


# --- setup ---------------------------------------------------------------

def test_signup_trigger_creates_pending_profiles(ctx, page: Page):
    statuses = accounts_script.profile_statuses(ctx["ids"])
    assert statuses == {i: "pending" for i in ctx["ids"]}


def test_admin_api_approves_first_account(ctx, page: Page):
    approved = ctx["accounts"]["approved"]
    resp = _api("POST", f"/api/platform/users/{approved['id']}/approve", ctx["admin_token"])
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "approved"
    assert accounts_script.profile_statuses([approved["id"]]) == {approved["id"]: "approved"}


# --- pending user ----------------------------------------------------------

def test_pending_user_pages(ctx, page: Page):
    acc = ctx["accounts"]["pending"]
    _sign_in(page, acc["email"], acc["password"], "/account")
    expect(page.locator("#account-status")).to_contain_text("waiting for approval", timeout=20_000)

    page.goto(f"{BASE}/linkedin")
    expect(page.get_by_role("status").filter(has_text="waiting for approval")).to_be_visible(
        timeout=20_000)
    assert "/linkedin" in page.url

    navigations: list[str] = []
    page.on("framenavigated", lambda f: navigations.append(f.url) if f == page.main_frame else None)
    page.goto(f"{BASE}/queue")
    expect(page.get_by_text("does not have Task Queue admin access")).to_be_visible(timeout=20_000)
    page.wait_for_timeout(3_000)
    assert page.url.startswith(f"{BASE}/queue") and len(navigations) <= 2, navigations


def test_pending_user_api_refused(ctx, tokens, page: Page):
    resp = _api("GET", "/api/linkedin/posts", tokens["pending"])
    assert resp.status_code == 403 and _reason(resp) == "pending", resp.text


# --- approved user -----------------------------------------------------------

def test_approved_user_isolation_before_profile(ctx, tokens, page: Page):
    t = tokens["approved"]
    resp = _api("GET", "/api/linkedin/posts", t)
    assert resp.status_code == 200 and resp.json() == [], resp.text
    resp = _api("POST", "/api/linkedin/posts", t, json={"brief": BRIEF_MARKER})
    assert resp.status_code == 409 and _reason(resp) == "profile_required", resp.text
    assert _api("GET", "/api/linkedin/scene-assets", t).json() == []
    assert _api("GET", "/api/linkedin/characters", t).json() == []


def test_approved_user_onboarding_and_profile(ctx, page: Page):
    acc = ctx["accounts"]["approved"]
    _sign_in(page, acc["email"], acc["password"], "/linkedin")
    page.wait_for_url(re.compile(r"/linkedin.*#profile"), timeout=30_000)
    textarea = page.locator("textarea").first
    expect(textarea).to_be_visible(timeout=20_000)
    textarea.fill("I am an end-to-end test account. I write short, plain posts about testing.")
    page.get_by_role("button", name="Save profile").click()
    expect(page.get_by_role("button", name="Save profile")).to_be_enabled(timeout=20_000)
    page.wait_for_timeout(1_000)
    rows = _db("select 1 from linkedin.writer_profiles where owner_id = %s", (acc["id"],))
    assert rows, "writer profile was not saved"

    page.goto(f"{BASE}/linkedin#backdrops")
    page.wait_for_timeout(3_000)
    page.goto(f"{BASE}/linkedin#characters")
    page.wait_for_timeout(3_000)

    # Onboarding step 2: with a profile but no mascot, the new-post screen
    # asks for one instead of showing the brief form.
    page.goto(f"{BASE}/linkedin#posts")
    expect(page.get_by_role("heading", name="Create your mascot first")).to_be_visible(
        timeout=20_000)
    expect(page.get_by_label("Your work update")).to_have_count(0)


def _give_mascot(owner_id: str) -> str:
    """A locked-hero character for a test user, inserted directly (rendering a
    real hero is out of scope). It reuses the admin's gtee_dev public hero
    image URL (read only); cleanup deletes it with the user's other characters."""
    hero = _db("select hero_image_url, hero_asset_id, card_json from linkedin.characters "
               "where character_id = 'gtee_dev' and hero_image_url is not null")
    assert hero, "the admin's gtee_dev hero is missing"
    hero_url, asset_id, card_json = hero[0]
    character_id = f"e2e_mascot_{owner_id.replace('-', '')[:12]}"
    _db("insert into linkedin.characters (character_id, owner_id, display_name, card_json, "
        "hero_asset_id, hero_version, hero_image_url, updated_at) "
        "values (%s, %s, 'E2E mascot', %s, %s, 1, %s, now() at time zone 'utc')",
        (character_id, owner_id, card_json, asset_id, hero_url))
    return character_id


def test_approved_user_creates_post_and_cannot_see_admins(ctx, tokens, page: Page):
    t, admin = tokens["approved"], ctx["admin_token"]
    brief = {"brief": f"{BRIEF_MARKER}: one line"}
    resp = _api("POST", "/api/linkedin/posts", t, json=brief)  # profile, but no mascot yet
    assert resp.status_code == 409 and _reason(resp) == "character_required", resp.text
    assert _api("GET", "/api/linkedin/posts", t).json() == []

    mascot = _give_mascot(ctx["accounts"]["approved"]["id"])
    resp = _api("POST", "/api/linkedin/posts", t, json=brief)
    assert resp.status_code == 200, resp.text
    assert resp.json()["character_id"] == mascot
    own_id = resp.json()["id"]
    listed = [p["id"] for p in _api("GET", "/api/linkedin/posts", t).json()]
    assert listed == [own_id]

    admin_posts = _api("GET", "/api/linkedin/posts", admin).json()
    assert own_id not in [p["id"] for p in admin_posts]
    assert _api("GET", f"/api/linkedin/posts/{admin_posts[0]['id']}", t).status_code == 404

    admin_chars = _api("GET", "/api/linkedin/characters", admin).json()
    assert _api("GET", f"/api/linkedin/characters/{admin_chars[0]['character_id']}",
                t).status_code == 404
    admin_assets = _api("GET", "/api/linkedin/scene-assets", admin).json()
    assert _api("GET", "/api/linkedin/scene-assets", t).json() == []
    versions = _api("GET", f"/api/linkedin/scene-assets/{admin_assets[0]['name']}/versions", t)
    assert versions.status_code in (200, 404) and (versions.status_code == 404
                                                   or versions.json() == [])


def test_approved_user_worker_key_shown_once_and_revoked(ctx, page: Page):
    acc = ctx["accounts"]["approved"]
    page.on("dialog", lambda d: d.accept())
    _sign_in(page, acc["email"], acc["password"], "/account")
    expect(page.locator("#worker-keys")).to_be_visible(timeout=20_000)
    page.fill("#worker-key-name", "e2e journey key")
    page.click("#worker-key-create")
    expect(page.locator("#new-key-value")).not_to_be_empty(timeout=20_000)
    page.click("#new-key-done")
    page.reload()
    expect(page.locator("#worker-keys-table")).to_contain_text("e2e journey key", timeout=20_000)
    assert not page.locator("#new-key-value").inner_text().strip()
    page.locator("#worker-keys-table").get_by_role("button", name="Revoke").click()
    page.locator("#worker-keys-table").get_by_role("button", name="Yes, revoke").click()
    expect(page.locator("#worker-keys-table")).to_contain_text("Revoked", timeout=20_000)
    rows = _db("select revoked_at is not null from public.worker_keys where user_id::text = %s",
               (acc["id"],))
    assert rows == [(True,)], rows


# --- admin ------------------------------------------------------------------

def _row(page: Page, email: str):
    return page.locator("#users-table tr", has_text=email)


def test_admin_users_page_suspend_and_reinstate(ctx, tokens, page: Page):
    a = ctx["accounts"]
    page.on("dialog", lambda d: d.accept())
    _sign_in(page, os.environ["E2E_LOGIN_EMAIL"], os.environ["E2E_LOGIN_PASSWORD"],
             "/admin/users")
    pending_row, approved_row = _row(page, a["pending"]["email"]), _row(page, a["approved"]["email"])
    expect(pending_row.get_by_role("button", name="Approve")).to_be_visible(timeout=20_000)
    expect(pending_row.get_by_role("button", name="Reject")).to_be_visible()
    expect(approved_row.get_by_role("button", name="Suspend")).to_be_visible()

    approved_row.get_by_role("button", name="Suspend").click()
    expect(approved_row.get_by_role("button", name="Reinstate")).to_be_visible(timeout=20_000)
    started = time.monotonic()
    while True:
        resp = _api("GET", "/api/linkedin/posts", tokens["approved"])
        if resp.status_code == 403 and _reason(resp) == "suspended":
            break
        assert time.monotonic() - started < SUSPEND_PROPAGATION_SECONDS, resp.text
        time.sleep(5)
    ctx["suspend_seconds"] = round(time.monotonic() - started)
    me = _api("GET", "/api/platform/me", tokens["approved"])
    assert me.status_code == 200 and me.json()["status"] == "suspended", me.text

    approved_row.get_by_role("button", name="Reinstate").click()
    expect(approved_row.get_by_role("button", name="Suspend")).to_be_visible(timeout=20_000)
    started = time.monotonic()
    while _api("GET", "/api/linkedin/posts", tokens["approved"]).status_code != 200:
        assert time.monotonic() - started < SUSPEND_PROPAGATION_SECONDS
        time.sleep(5)
    ctx["reinstate_seconds"] = round(time.monotonic() - started)
    print(f"suspend took effect in ~{ctx['suspend_seconds']}s, reinstate in ~{ctx['reinstate_seconds']}s")


def test_admin_view_unaffected(ctx, page: Page):
    posts = _api("GET", "/api/linkedin/posts", ctx["admin_token"]).json()
    assert len(posts) == 10, len(posts)
    _sign_in(page, os.environ["E2E_LOGIN_EMAIL"], os.environ["E2E_LOGIN_PASSWORD"], "/linkedin")
    expect(page.get_by_role("link", name="Posts")).to_be_visible(timeout=20_000)
