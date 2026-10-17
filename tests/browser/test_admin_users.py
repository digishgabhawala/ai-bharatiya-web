import json

from playwright.sync_api import expect

from tests.browser.conftest import mock_platform, sign_in

ADMIN = {"user_id": "a1", "email": "admin@example.com", "display_name": "Admin", "avatar_url": None,
         "status": "approved", "is_admin": True, "apps": ["linkedin", "queue"]}
ROWS = [
    {"user_id": "p1", "email": "p@x", "display_name": "Pending P", "status": "pending",
     "is_admin": False, "created_at": "2026-10-16T10:00:00Z"},
    {"user_id": "s1", "email": "s@x", "display_name": None, "status": "suspended",
     "is_admin": False, "created_at": "2026-10-15T10:00:00Z"},
    {"user_id": "a1", "email": "admin@example.com", "display_name": "Admin", "status": "approved",
     "is_admin": True, "created_at": "2026-10-01T10:00:00Z"},
]


def test_non_admin_sees_admins_only(page, site):
    mock_platform(page, me={**ADMIN, "is_admin": False})
    sign_in(page)
    page.goto(f"{site}/admin/users")
    expect(page.get_by_role("status")).to_contain_text("Admins only")
    expect(page.get_by_role("table")).to_have_count(0)


def test_actions_match_each_status_and_own_row_has_none(page, site):
    mock_platform(page, me=ADMIN, users=ROWS)
    sign_in(page)
    page.goto(f"{site}/admin/users")
    pending = page.get_by_role("row", name="Pending P")
    expect(pending.get_by_role("button")).to_have_text(["Approve", "Reject"])
    expect(page.get_by_role("row", name="s@x").get_by_role("button")).to_have_text(["Reinstate"])
    expect(page.get_by_role("row", name="admin@example.com").get_by_role("button")).to_have_count(0)


def test_approved_and_rejected_rows_offer_only_legal_actions(page, site):
    rows = ROWS + [
        {"user_id": "u2", "email": "u@x", "display_name": None, "status": "approved",
         "is_admin": False, "created_at": "2026-10-14T10:00:00Z"},
        {"user_id": "a2", "email": "a2@x", "display_name": None, "status": "approved",
         "is_admin": True, "created_at": "2026-10-13T10:00:00Z"},
        {"user_id": "r1", "email": "r@x", "display_name": None, "status": "rejected",
         "is_admin": False, "created_at": "2026-10-12T10:00:00Z"},
    ]
    mock_platform(page, me=ADMIN, users=rows)
    sign_in(page)
    page.goto(f"{site}/admin/users")
    expect(page.get_by_role("row", name="u@x").get_by_role("button")).to_have_text(
        ["Suspend", "Make admin"])
    expect(page.get_by_role("row", name="a2@x").get_by_role("button")).to_have_text(
        ["Suspend", "Remove admin"])
    expect(page.get_by_role("row", name="r@x").get_by_role("button")).to_have_text(["Approve"])


def test_make_admin_posts_the_flag(page, site):
    rows = [*ROWS, {"user_id": "u2", "email": "u@x", "display_name": None, "status": "approved",
                    "is_admin": False, "created_at": "2026-10-14T10:00:00Z"}]
    mock_platform(page, me=ADMIN, users=rows)
    bodies = []
    page.route("**/api/platform/users/u2/admin", lambda r: (
        bodies.append(r.request.post_data_json),
        r.fulfill(content_type="application/json", body=json.dumps({**rows[-1], "is_admin": True}))))
    sign_in(page)
    page.goto(f"{site}/admin/users")
    page.get_by_role("row", name="u@x").get_by_role("button", name="Make admin").click()
    for _ in range(60):
        if bodies:
            break
        page.wait_for_timeout(50)
    assert bodies == [{"is_admin": True}]


def test_approve_posts_and_conflicts_are_shown(page, site):
    calls = mock_platform(page, me=ADMIN, users=ROWS)
    page.route("**/api/platform/users/p1/approve", lambda r: (
        calls.append(("POST", r.request.url)),
        r.fulfill(status=409, content_type="application/json",
                  body=json.dumps({"detail": "can't approve a user who is approved"}))))
    sign_in(page)
    page.goto(f"{site}/admin/users")
    page.get_by_role("row", name="Pending P").get_by_role("button", name="Approve").click()
    expect(page.get_by_role("alert")).to_contain_text("can't approve")
    assert any(u.endswith("/p1/approve") for _, u in calls)
