import re

import pytest
from playwright.sync_api import expect

from tests.browser.conftest import SUPABASE, mock_platform, sign_in


def test_signed_out_sees_google_first_and_email_behind_a_link(page, site):
    mock_platform(page)
    page.goto(f"{site}/login?next=/linkedin")
    expect(page.get_by_role("button", name="Continue with Google")).to_be_visible()
    expect(page.get_by_label("Password")).to_be_hidden()
    page.get_by_role("button", name="Sign in with email").click()
    expect(page.get_by_label("Password")).to_be_visible()


def test_google_returns_to_login_with_next(page, site):
    mock_platform(page)
    seen = []
    page.route(f"{SUPABASE}/auth/v1/authorize**",
               lambda r: (seen.append(r.request.url), r.fulfill(body="ok")))
    page.goto(f"{site}/login?next=/linkedin")
    page.get_by_role("button", name="Continue with Google").click()
    page.wait_for_url(re.compile("authorize"))
    assert "provider=google" in seen[0]
    assert "redirect_to=" + "http%3A%2F%2F127.0.0.1" in seen[0]
    assert "%2Flogin%3Fnext%3D%252Flinkedin" in seen[0]


def test_signed_in_goes_to_next(page, site):
    mock_platform(page)
    sign_in(page)
    page.route(f"{site}/linkedin", lambda r: r.fulfill(body="LinkedIn stub", content_type="text/html"))
    page.goto(f"{site}/login?next=/linkedin")
    page.wait_for_url(f"{site}/linkedin")


@pytest.mark.parametrize("bad", ["//evil.example", "https://evil.example/x",
                                 "/\\evil.example", "javascript:alert(1)"])
def test_unsafe_next_goes_home(page, site, bad):
    mock_platform(page)
    sign_in(page)
    page.goto(f"{site}/login?next={bad}")
    page.wait_for_url(f"{site}/")


def test_email_sign_in_then_next(page, site):
    mock_platform(page)
    page.route(f"{SUPABASE}/auth/v1/token**", lambda r: r.fulfill(
        content_type="application/json",
        body='{"access_token":"h.e30.s","token_type":"bearer","expires_in":3600,'
             '"refresh_token":"r","user":{"id":"u1","email":"a@example.com"}}'))
    page.route(f"{site}/account", lambda r: r.fulfill(body="Account stub", content_type="text/html"))
    page.goto(f"{site}/login?next=/account")
    page.get_by_role("button", name="Sign in with email").click()
    page.get_by_label("Email").fill("a@example.com")
    page.get_by_label("Password").fill("pw")
    page.get_by_role("button", name="Sign in", exact=True).click()
    page.wait_for_url(f"{site}/account")


def test_early_submit_never_puts_the_password_in_the_url(page, site):
    """Submitting before the Supabase client is ready (slow config fetch, fast
    typist or a password manager) must not fall back to a native GET form
    submit -- that would put the password in the URL (history, server logs).
    The sign-in completes once the client is ready."""
    import json

    held = []
    navigations = []
    page.on("framenavigated",
            lambda f: navigations.append(f.url) if f == page.main_frame else None)
    mock_platform(page)
    page.unroute("**/api/platform/config")

    page.route("**/api/platform/config", lambda r: held.append(r))  # answered after the submit
    page.route(f"{SUPABASE}/auth/v1/token**", lambda r: r.fulfill(
        content_type="application/json",
        body='{"access_token":"h.e30.s","token_type":"bearer","expires_in":3600,'
             '"refresh_token":"r","user":{"id":"u1","email":"a@example.com"}}'))
    page.route(f"{site}/account", lambda r: r.fulfill(body="Account stub", content_type="text/html"))
    page.goto(f"{site}/login?next=/account", wait_until="domcontentloaded")
    page.get_by_role("button", name="Sign in with email").click()
    page.get_by_label("Email").fill("a@example.com")
    page.get_by_label("Password").fill("pw-SECRET")
    page.get_by_role("button", name="Sign in", exact=True).click()
    page.wait_for_timeout(500)
    assert held, "the config request should still be pending"
    held[0].fulfill(content_type="application/json",
                    body=json.dumps({"supabase_url": SUPABASE, "supabase_publishable_key": "pk"}))
    page.wait_for_url(f"{site}/account")
    assert not any("SECRET" in url or "password=" in url for url in navigations), navigations
