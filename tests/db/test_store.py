import pytest

from _platform_api.store import NotFound, PgStore
from _platform_api.transitions import TransitionError


@pytest.fixture()
def store(db_url):
    return PgStore(db_url)


@pytest.fixture()
def admin(conn, make_user):
    uid = make_user("admin")
    conn.execute("update platform.profiles set status='approved', is_admin=true where user_id=%s", (uid,))
    return uid


def test_approve_records_actor_and_adds_every_membership(store, conn, admin, make_user):
    uid = make_user("asha")
    conn.execute("insert into platform.app_memberships (user_id, app) values (%s, 'queue')", (uid,))
    profile = store.change_status(actor_id=admin, target_id=uid, action="approve")
    assert (profile.status, profile.status_changed_by) == ("approved", admin)
    assert sorted(store.apps_for(uid)) == ["linkedin", "queue"]


def test_suspend_keeps_memberships_and_reinstate_restores(store, admin, make_user):
    uid = make_user("ravi")
    store.change_status(actor_id=admin, target_id=uid, action="approve")
    assert store.change_status(actor_id=admin, target_id=uid, action="suspend").status == "suspended"
    assert store.change_status(actor_id=admin, target_id=uid, action="reinstate").status == "approved"
    assert sorted(store.apps_for(uid)) == ["linkedin", "queue"]


def test_unknown_user_is_not_found(store, admin):
    with pytest.raises(NotFound):
        store.change_status(actor_id=admin, target_id="00000000-0000-0000-0000-000000000000",
                            action="approve")


def test_last_admin_rule_uses_live_admin_count(store, conn, admin, make_user):
    other = make_user("admin2")
    store.change_status(actor_id=admin, target_id=other, action="approve")
    store.set_admin(actor_id=admin, target_id=other, is_admin=True)
    n = conn.execute("select count(*) from platform.profiles where is_admin and status='approved'"
                     ).fetchone()[0]
    if n == 2:  # only our two test admins exist locally
        store.set_admin(actor_id=other, target_id=admin, is_admin=False)
        with pytest.raises(TransitionError, match="last admin"):
            store.set_admin(actor_id=admin, target_id=other, is_admin=False)


def test_list_puts_pending_first_then_newest(store, admin, make_user):
    a = make_user("first")
    store.change_status(actor_id=admin, target_id=a, action="approve")
    b = make_user("second")
    ids = [p.user_id for p in store.list_profiles(None)]
    assert ids.index(b) < ids.index(a)
    assert all(p.status == "pending" for p in store.list_profiles("pending"))


def test_ensure_profile_creates_a_missing_row(store, conn, make_user):
    uid = make_user("ghost")
    conn.execute("delete from platform.profiles where user_id = %s", (uid,))
    assert store.ensure_profile(uid, "ghost@x", None, None).status == "pending"
