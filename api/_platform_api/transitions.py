"""Who may move a profile where. Pure: the store supplies the facts."""
from __future__ import annotations

from dataclasses import dataclass

APPS = ("linkedin", "queue")
_RULES = {"approve": ({"pending", "rejected"}, "approved"),
          "reject": ({"pending"}, "rejected"),
          "suspend": ({"approved"}, "suspended"),
          "reinstate": ({"suspended"}, "approved")}


class TransitionError(Exception):
    pass


@dataclass(frozen=True)
class Subject:
    user_id: str
    status: str
    is_admin: bool

    @property
    def counts_as_admin(self) -> bool:
        return self.is_admin and self.status == "approved"


def _not_self(actor_id: str, target: Subject) -> None:
    if actor_id == target.user_id:
        raise TransitionError("admins can't change their own status or admin flag")


def status_change(action: str, *, actor_id: str, target: Subject, approved_admins: int) -> str:
    _not_self(actor_id, target)
    allowed_from, new_status = _RULES[action]
    if target.status not in allowed_from:
        raise TransitionError(f"can't {action} a user who is {target.status}")
    if new_status != "approved" and target.counts_as_admin and approved_admins <= 1:
        raise TransitionError("the last admin can't be suspended")
    return new_status


def admin_change(*, actor_id: str, target: Subject, make_admin: bool, approved_admins: int) -> None:
    _not_self(actor_id, target)
    if make_admin and target.status != "approved":
        raise TransitionError("only approved users can be made admin")
    if not make_admin and target.counts_as_admin and approved_admins <= 1:
        raise TransitionError("the last admin can't be demoted")
