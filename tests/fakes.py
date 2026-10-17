import dataclasses
from datetime import UTC, datetime

from _platform_api import transitions
from _platform_api.store import NotFound, Profile


class FakeStore:
    def __init__(self):
        self.profiles: dict[str, Profile] = {}
        self.apps: dict[str, set[str]] = {}

    def add(self, user_id, email, status="pending", is_admin=False):
        now = datetime.now(UTC)
        self.profiles[user_id] = Profile(user_id, email, None, None, status, is_admin,
                                         now, now, None, None)

    def get_profile(self, user_id):
        return self.profiles.get(user_id)

    def ensure_profile(self, user_id, email, display_name, avatar_url):
        if user_id not in self.profiles:
            self.add(user_id, email)
        return self.profiles[user_id]

    def apps_for(self, user_id):
        return sorted(self.apps.get(user_id, set()))

    def list_profiles(self, status=None):
        rows = [p for p in self.profiles.values() if status in (None, p.status)]
        rows.sort(key=lambda p: p.created_at, reverse=True)
        return sorted(rows, key=lambda p: p.status != "pending")

    def _target(self, user_id):
        if user_id not in self.profiles:
            raise NotFound(user_id)
        p = self.profiles[user_id]
        admins = sum(1 for q in self.profiles.values() if q.is_admin and q.status == "approved")
        return p, transitions.Subject(p.user_id, p.status, p.is_admin), admins

    def change_status(self, *, actor_id, target_id, action):
        p, subject, admins = self._target(target_id)
        new = transitions.status_change(action, actor_id=actor_id, target=subject,
                                        approved_admins=admins)
        self.profiles[target_id] = dataclasses.replace(p, status=new, status_changed_by=actor_id)
        if new == "approved":
            self.apps.setdefault(target_id, set()).update(transitions.APPS)
        return self.profiles[target_id]

    def set_admin(self, *, actor_id, target_id, is_admin):
        p, subject, admins = self._target(target_id)
        transitions.admin_change(actor_id=actor_id, target=subject, make_admin=is_admin,
                                 approved_admins=admins)
        self.profiles[target_id] = dataclasses.replace(p, is_admin=is_admin)
        return self.profiles[target_id]
