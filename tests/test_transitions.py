import pytest

from _platform_api.transitions import Subject, TransitionError, admin_change, status_change

ME = "admin-1"


def _s(status="pending", is_admin=False, user_id="u-1"):
    return Subject(user_id=user_id, status=status, is_admin=is_admin)


@pytest.mark.parametrize("action,before,after", [
    ("approve", "pending", "approved"), ("approve", "rejected", "approved"),
    ("reject", "pending", "rejected"), ("suspend", "approved", "suspended"),
    ("reinstate", "suspended", "approved"),
])
def test_legal_transitions(action, before, after):
    assert status_change(action, actor_id=ME, target=_s(before), approved_admins=1) == after


@pytest.mark.parametrize("action,before", [
    ("approve", "approved"), ("approve", "suspended"), ("reject", "approved"),
    ("reject", "rejected"), ("suspend", "pending"), ("suspend", "suspended"),
    ("reinstate", "approved"), ("reinstate", "rejected"),
])
def test_illegal_transitions(action, before):
    with pytest.raises(TransitionError):
        status_change(action, actor_id=ME, target=_s(before), approved_admins=1)


def test_admin_cannot_change_own_status_or_flag():
    me = _s("approved", True, ME)
    with pytest.raises(TransitionError, match="own"):
        status_change("suspend", actor_id=ME, target=me, approved_admins=2)
    with pytest.raises(TransitionError, match="own"):
        admin_change(actor_id=ME, target=me, make_admin=False, approved_admins=2)


def test_last_admin_cannot_be_suspended_or_demoted():
    other = _s("approved", True, "admin-2")
    with pytest.raises(TransitionError, match="last admin"):
        status_change("suspend", actor_id=ME, target=other, approved_admins=1)
    with pytest.raises(TransitionError, match="last admin"):
        admin_change(actor_id=ME, target=other, make_admin=False, approved_admins=1)
    assert status_change("suspend", actor_id=ME, target=other, approved_admins=2) == "suspended"


def test_suspended_admins_do_not_count_as_remaining():
    # A suspended admin keeps is_admin=true but is not "an admin remaining":
    # demoting them is always allowed, even with a single approved admin.
    suspended_admin = _s("suspended", True, "admin-2")
    admin_change(actor_id=ME, target=suspended_admin, make_admin=False, approved_admins=1)


def test_only_approved_users_can_be_made_admin():
    with pytest.raises(TransitionError, match="approved"):
        admin_change(actor_id=ME, target=_s("pending"), make_admin=True, approved_admins=1)
    admin_change(actor_id=ME, target=_s("approved"), make_admin=True, approved_admins=1)


def test_admin_flag_change_is_idempotent():
    admin_change(actor_id=ME, target=_s("approved", True), make_admin=True, approved_admins=2)
