import base64
import dataclasses
import json
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from _platform_api import auth
from _platform_api.app import app, get_store
from _platform_api.config import settings
from tests.fakes import FakeStore

ADMIN, USER = str(uuid.uuid4()), str(uuid.uuid4())
P = "/api/platform"


def _token(exp_in=3600):
    payload = base64.urlsafe_b64encode(
        json.dumps({"exp": time.time() + exp_in}).encode()).decode().rstrip("=")
    return f"h.{payload}.s"


@pytest.fixture()
def store():
    s = FakeStore()
    s.add(ADMIN, "admin@example.com", status="approved", is_admin=True)
    s.add(USER, "asha@example.com")
    return s


@pytest.fixture()
def client(store, monkeypatch):
    monkeypatch.setattr(settings, "supabase_url", "https://proj.supabase.co")
    monkeypatch.setattr(settings, "supabase_publishable_key", "pk")
    who = {"id": ADMIN, "email": "admin@example.com"}

    async def fetch(token):
        who["calls"] = who.get("calls", 0) + 1
        return {"id": who["id"], "email": who["email"], "user_metadata": {"full_name": "N"}}

    monkeypatch.setattr(auth, "_fetch_supabase_user", fetch)
    app.dependency_overrides[get_store] = lambda: store
    auth.clear_cache()
    tc = TestClient(app, headers={"Authorization": f"Bearer {_token()}"})

    def as_user(user_id, email):
        who.update(id=user_id, email=email)
        auth.clear_cache()

    tc.as_user, tc.who = as_user, who
    yield tc
    app.dependency_overrides.clear()


def test_config_is_public(client):
    resp = client.get(f"{P}/config", headers={"Authorization": ""})
    assert resp.json() == {"supabase_url": "https://proj.supabase.co", "supabase_publishable_key": "pk"}


def test_everything_else_needs_a_session(client):
    for method, path in [("get", "/me"), ("get", "/users"), ("post", f"/users/{USER}/approve"),
                         ("post", f"/users/{USER}/admin")]:
        assert client.request(method, P + path, headers={"Authorization": ""}).status_code == 401


def test_me_for_a_new_account_self_heals_as_pending(client):
    newbie = str(uuid.uuid4())
    client.as_user(newbie, "new@example.com")
    me = client.get(f"{P}/me").json()
    assert (me["user_id"], me["status"], me["is_admin"], me["apps"]) == (newbie, "pending", False, [])


def test_admin_routes_are_403_for_non_admins(client):
    client.as_user(USER, "asha@example.com")
    assert client.get(f"{P}/users").status_code == 403
    assert client.post(f"{P}/users/{ADMIN}/suspend").status_code == 403


def test_suspended_admin_is_403(client, store):
    other = str(uuid.uuid4())
    store.add(other, "old@example.com", status="suspended", is_admin=True)
    client.as_user(other, "old@example.com")
    assert client.get(f"{P}/users").status_code == 403


def test_approve_then_me_lists_every_app(client):
    assert client.post(f"{P}/users/{USER}/approve").json()["status"] == "approved"
    client.as_user(USER, "asha@example.com")
    assert client.get(f"{P}/me").json()["apps"] == ["linkedin", "queue"]


def test_illegal_transition_and_safeguards_are_409(client):
    assert client.post(f"{P}/users/{USER}/suspend").status_code == 409            # pending
    assert client.post(f"{P}/users/{ADMIN}/suspend").status_code == 409           # self
    assert client.post(f"{P}/users/{ADMIN}/admin", json={"is_admin": False}).status_code == 409


def test_unknown_or_malformed_user_ids(client):
    assert client.post(f"{P}/users/{uuid.uuid4()}/approve").status_code == 404
    assert client.post(f"{P}/users/not-a-uuid/approve").status_code == 422
    assert client.post(f"{P}/users/{USER}/delete").status_code == 422


def test_users_list_pending_first_and_filter(client):
    rows = client.get(f"{P}/users").json()
    assert rows[0]["user_id"] == USER
    assert [r["status"] for r in client.get(f"{P}/users?status=pending").json()] == ["pending"]


def test_identity_is_cached_but_profile_is_read_fresh(client, store):
    client.get(f"{P}/me")
    store.profiles[ADMIN] = dataclasses.replace(store.profiles[ADMIN], status="suspended")
    assert client.get(f"{P}/me").json()["status"] == "suspended"
    assert client.who["calls"] == 1
