import json
import threading
import time
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from tests.browser.static_server import CleanUrlHandler

ROOT = Path(__file__).resolve().parents[2]
SUPABASE = "https://proj.supabase.co"


@pytest.fixture(scope="session")
def site():
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(CleanUrlHandler, directory=str(ROOT)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def _json(route, body, status=200):
    route.fulfill(status=status, content_type="application/json", body=json.dumps(body))


def mock_platform(page, me=None, users=None, calls=None):
    calls = calls if calls is not None else []
    page.route("**/api/platform/config", lambda r: _json(
        r, {"supabase_url": SUPABASE, "supabase_publishable_key": "pk"}))
    page.route("**/api/platform/me", lambda r: _json(r, me) if me else _json(
        r, {"detail": "Authentication required"}, 401))

    def users_route(route):
        calls.append((route.request.method, route.request.url))
        _json(route, users or [])
    page.route("**/api/platform/users**", users_route)
    page.route(f"{SUPABASE}/**", lambda r: _json(r, {}))
    return calls


def sign_in(page, user_id="u1", email="a@example.com"):
    session = {"access_token": "h.e30.s", "token_type": "bearer", "expires_in": 3600,
               "expires_at": int(time.time()) + 3600, "refresh_token": "r",
               "user": {"id": user_id, "email": email, "aud": "authenticated",
                        "role": "authenticated", "app_metadata": {}, "user_metadata": {},
                        "created_at": "2026-10-16T00:00:00Z"}}
    page.add_init_script(
        f"localStorage.setItem('sb-proj-auth-token', {json.dumps(json.dumps(session))})")
