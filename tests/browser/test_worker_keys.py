import json

from playwright.sync_api import expect

from tests.browser.conftest import mock_platform, sign_in

ME = {"user_id": "u1", "email": "asha@example.com", "display_name": "Asha", "avatar_url": None,
      "status": "approved", "is_admin": False, "apps": ["linkedin", "queue"]}
KEY = {"id": "k1", "name": "Asha's MacBook", "prefix": "tqw_AbCd", "created_at": "2026-10-16T10:00:00Z",
       "last_used_at": None, "revoked_at": None}
RAW = "tqw_AbCdSECRET"
ENV_LINES = f"WORKER_API_KEY={RAW}\nTASK_QUEUE_URL=https://ai-bharatiya-web.vercel.app/queue"


def _keys(page, listing, calls, post_status=201, post_body=None):
    def handle(route):
        req = route.request
        calls.append((req.method, req.url, req.post_data, req.headers.get("authorization")))
        if req.method == "POST":
            body = post_body if post_body is not None else {**KEY, "key": RAW}
            if post_status == 201:
                listing.append({k: v for k, v in body.items() if k != "key"}
                               | {"last_used_at": None, "revoked_at": None})
            return route.fulfill(status=post_status, content_type="application/json",
                                 body=json.dumps(body))
        if req.method == "DELETE":
            listing[:] = [{**k, "revoked_at": "2026-10-16T11:00:00Z"} for k in listing]
            return route.fulfill(content_type="application/json", body=json.dumps(listing[0]))
        return route.fulfill(content_type="application/json", body=json.dumps(listing))
    page.route("**/api/queue/worker-keys**", handle)


def _record_clipboard(page):
    page.add_init_script(
        "window.__copied = [];"
        "Object.defineProperty(navigator, 'clipboard', {value: {writeText: async (t) => {"
        " window.__copied.push(t) }}});")


def test_create_shows_the_key_once_with_env_lines(page, site):
    calls = []
    mock_platform(page, me=ME)
    _keys(page, [], calls)
    _record_clipboard(page)
    sign_in(page)
    page.goto(f"{site}/account")
    expect(page.get_by_role("heading", name="Worker keys")).to_be_visible()
    page.get_by_label("Name").fill("Asha's MacBook")
    page.get_by_role("button", name="Create").click()
    panel = page.get_by_role("region", name="New worker key")
    expect(panel).to_contain_text("WORKER_API_KEY=tqw_AbCdSECRET")
    expect(panel).to_contain_text("TASK_QUEUE_URL=https://ai-bharatiya-web.vercel.app/queue")
    expect(panel).to_contain_text("won't be shown again")
    assert panel.locator("pre").inner_text() == ENV_LINES
    post = next(c for c in calls if c[0] == "POST")
    assert json.loads(post[2]) == {"name": "Asha's MacBook"} and post[3] == "Bearer h.e30.s"
    panel.get_by_role("button", name="Copy key").click()
    panel.get_by_role("button", name="Copy .env lines").click()
    expect(panel.get_by_role("status")).to_have_text(".env lines copied.")
    assert page.evaluate("window.__copied") == [RAW, ENV_LINES]
    expect(page.get_by_role("row", name="Asha's MacBook")).to_contain_text("tqw_AbCd…")
    expect(page.get_by_label("Name")).to_have_value("")
    panel.get_by_role("button", name="Done").click()
    expect(page.get_by_text("tqw_AbCdSECRET")).to_have_count(0)
    assert "SECRET" not in page.content()


def test_list_shows_prefix_dates_and_status(page, site):
    mock_platform(page, me=ME)
    _keys(page, [KEY, {**KEY, "id": "k2", "name": "Old box", "last_used_at": "2026-10-15T08:00:00Z",
                       "revoked_at": "2026-10-16T09:00:00Z"}], [])
    sign_in(page)
    page.goto(f"{site}/account")
    active = page.get_by_role("row", name="Asha's MacBook")
    expect(active).to_contain_text("tqw_AbCd…")
    expect(active).to_contain_text("Never")
    expect(active).to_contain_text("Active")
    revoked = page.get_by_role("row", name="Old box")
    expect(revoked).to_contain_text("Revoked")
    expect(revoked.get_by_role("button", name="Revoke")).to_have_count(0)


def test_revoke_asks_for_confirmation_then_calls_delete(page, site):
    calls = []
    mock_platform(page, me=ME)
    _keys(page, [KEY], calls)
    sign_in(page)
    page.goto(f"{site}/account")
    row = page.get_by_role("row", name="Asha's MacBook")
    row.get_by_role("button", name="Revoke").click()
    confirm = row.get_by_role("group", name="Revoke Asha's MacBook?")
    expect(confirm).to_contain_text("Revoke this key?")
    expect(confirm.get_by_role("button", name="Cancel")).to_be_focused()
    assert not any(c[0] == "DELETE" for c in calls)            # nothing revoked yet
    with page.expect_request(lambda r: r.method == "DELETE" and r.url.endswith("/worker-keys/k1")):
        confirm.get_by_role("button", name="Yes, revoke").click()
    expect(row).to_contain_text("Revoked")                      # list re-fetched
    expect(row.get_by_role("button", name="Revoke")).to_have_count(0)


def test_revoke_can_be_cancelled(page, site):
    calls = []
    mock_platform(page, me=ME)
    _keys(page, [KEY], calls)
    sign_in(page)
    page.goto(f"{site}/account")
    row = page.get_by_role("row", name="Asha's MacBook")
    row.get_by_role("button", name="Revoke").click()
    row.get_by_role("button", name="Cancel").click()
    expect(row.get_by_role("group")).to_have_count(0)
    expect(row.get_by_role("button", name="Revoke")).to_be_focused()
    row.get_by_role("button", name="Revoke").click()
    page.keyboard.press("Escape")                               # Escape cancels too
    expect(row.get_by_role("button", name="Revoke")).to_be_focused()
    expect(row).to_contain_text("Active")
    assert not any(c[0] == "DELETE" for c in calls)


def test_api_errors_show_their_detail(page, site):
    mock_platform(page, me=ME)
    _keys(page, [], [], post_status=409,
          post_body={"detail": "At most 10 active worker keys; revoke one first"})
    sign_in(page)
    page.goto(f"{site}/account")
    page.get_by_label("Name").fill("eleventh")
    page.get_by_role("button", name="Create").click()
    expect(page.get_by_role("alert")).to_contain_text("At most 10 active worker keys")
    expect(page.get_by_role("region", name="New worker key")).to_have_count(0)


def test_hidden_for_unapproved_accounts(page, site):
    calls = []
    mock_platform(page, me={**ME, "status": "pending", "apps": []})
    _keys(page, [], calls)
    sign_in(page)
    page.goto(f"{site}/account")
    expect(page.get_by_role("status")).to_contain_text("waiting for approval")
    expect(page.get_by_role("heading", name="Worker keys")).to_have_count(0)
    assert calls == []


def test_new_key_panel_fits_a_phone_screen(page, site):
    mock_platform(page, me=ME)
    _keys(page, [KEY], [])
    sign_in(page)
    page.set_viewport_size({"width": 390, "height": 900})
    page.goto(f"{site}/account")
    page.get_by_label("Name").fill("Asha's MacBook")
    page.get_by_role("button", name="Create").click()
    page.get_by_role("region", name="New worker key").wait_for()
    assert page.evaluate("document.documentElement.scrollWidth") <= 390
