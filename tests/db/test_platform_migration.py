import psycopg
import pytest

from scripts.apply_platform_migrations import apply_migrations, backfill_profiles, seed_admins
from tests.db.conftest import TEST_DOMAIN


def _profile(conn, user_id):
    return conn.execute(
        "select email, display_name, avatar_url, status, is_admin from platform.profiles "
        "where user_id = %s", (user_id,)).fetchone()


def test_sign_up_creates_a_pending_profile_from_google_metadata(conn, make_user):
    uid = make_user("asha", {"full_name": "Asha K", "avatar_url": "https://lh3.googleusercontent.com/a"})
    assert _profile(conn, uid) == (f"asha@{TEST_DOMAIN}", "Asha K",
                                   "https://lh3.googleusercontent.com/a", "pending", False)


def test_trigger_falls_back_to_name_and_picture(conn, make_user):
    uid = make_user("ravi", {"name": "Ravi", "picture": "https://p/x"})
    assert _profile(conn, uid)[1:3] == ("Ravi", "https://p/x")


def test_backfill_recreates_missing_profiles_as_pending(conn, make_user):
    uid = make_user("old")
    conn.execute("delete from platform.profiles where user_id = %s", (uid,))
    assert backfill_profiles(conn) >= 1
    assert _profile(conn, uid)[3] == "pending"


def test_seed_admins_only_bootstraps_when_no_admin_exists(conn, make_user):
    conn.execute("update platform.profiles set is_admin = false, status = 'pending' "
                 "where email like %s", (f"%@{TEST_DOMAIN}",))
    first = make_user("boss")
    if conn.execute("select count(*) from platform.profiles where is_admin and status = 'approved'"
                    ).fetchone()[0]:
        pytest.skip("local DB already has a real admin; bootstrap path not testable here")
    assert seed_admins(conn, [f"BOSS@{TEST_DOMAIN}"]) == 1
    assert _profile(conn, first)[3:] == ("approved", True)
    apps = {r[0] for r in conn.execute(
        "select app from platform.app_memberships where user_id = %s", (first,))}
    assert apps == {"linkedin", "queue"}
    second = make_user("boss2")
    assert seed_admins(conn, [f"boss2@{TEST_DOMAIN}"]) == 0
    assert _profile(conn, second)[3:] == ("pending", False)


def test_status_is_constrained(conn, make_user):
    uid = make_user("x")
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("update platform.profiles set status = 'banana' where user_id = %s", (uid,))


@pytest.mark.parametrize("role", ["anon", "authenticated"])
def test_data_api_roles_cannot_read_platform(conn, role):
    conn.execute(f"set role {role}")
    try:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("select 1 from platform.profiles limit 1")
    finally:
        conn.execute("reset role")


def test_apply_is_idempotent(conn):
    assert apply_migrations(conn) == []
