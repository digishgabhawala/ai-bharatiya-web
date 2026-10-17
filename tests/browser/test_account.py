import pytest
from playwright.sync_api import expect

from tests.browser.conftest import mock_platform, sign_in

ME = {"user_id": "u1", "email": "asha@example.com", "display_name": None, "avatar_url": None,
      "status": "approved", "is_admin": False, "apps": ["linkedin", "queue"]}


def test_signed_out_account_goes_to_login(page, site):
    mock_platform(page)
    page.goto(f"{site}/account")
    page.wait_for_url(f"{site}/login?next=%2Faccount")


@pytest.mark.parametrize("status,text", [
    ("pending", "waiting for approval"), ("rejected", "not approved"), ("suspended", "suspended")])
def test_account_explains_each_refused_status(page, site, status, text):
    mock_platform(page, me={**ME, "status": status, "apps": []})
    sign_in(page)
    page.goto(f"{site}/account")
    expect(page.get_by_role("status")).to_contain_text(text)
    expect(page.get_by_role("link", name="LinkedIn Content Agent")).to_have_count(0)


def test_approved_account_lists_apps_and_falls_back_to_email(page, site):
    mock_platform(page, me=ME)
    sign_in(page)
    page.goto(f"{site}/account")
    expect(page.get_by_role("heading", level=1)).to_contain_text("asha@example.com")
    expect(page.get_by_role("link", name="LinkedIn Content Agent")).to_have_attribute("href", "/linkedin")
    expect(page.get_by_role("link", name="Task Queue")).to_have_attribute("href", "/queue")
    expect(page.get_by_role("link", name="Admin")).to_have_count(0)


def test_admin_header_shows_pending_count_badge(page, site):
    pending = [{"user_id": f"p{i}", "status": "pending"} for i in range(2)]
    mock_platform(page, me={**ME, "is_admin": True}, users=pending)
    sign_in(page)
    page.goto(f"{site}/")
    expect(page.get_by_role("link", name="Admin 2 pending")).to_be_visible()


def test_header_sign_out_returns_to_login(page, site):
    mock_platform(page, me=ME)
    sign_in(page)
    page.goto(f"{site}/")
    page.get_by_role("button", name="Sign out").click()
    page.wait_for_url(f"{site}/login")
