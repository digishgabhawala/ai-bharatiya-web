-- Showrun joins the suite: memberships may now name it.
alter table platform.app_memberships drop constraint if exists app_memberships_app_check;
alter table platform.app_memberships
  add constraint app_memberships_app_check check (app in ('linkedin', 'queue', 'showrun'));
