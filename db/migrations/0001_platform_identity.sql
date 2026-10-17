-- Shared identity for every AI Bharatiyaa app. Only backends (the table
-- owner) read it; the Data API roles get nothing.
create schema if not exists platform;
revoke all on schema platform from public, anon, authenticated;

create table if not exists platform.schema_migrations (
  version text primary key,
  applied_at timestamptz not null default now()
);

create table if not exists platform.profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  email text,
  display_name text,
  avatar_url text,
  status text not null default 'pending'
    check (status in ('pending', 'approved', 'rejected', 'suspended')),
  is_admin boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  status_changed_at timestamptz,
  status_changed_by uuid references platform.profiles(user_id) on delete set null
);
create index if not exists profiles_status_created_idx
  on platform.profiles (status, created_at desc);
create index if not exists profiles_email_idx on platform.profiles (lower(email));

create table if not exists platform.app_memberships (
  user_id uuid not null references platform.profiles(user_id) on delete cascade,
  app text not null check (app in ('linkedin', 'queue')),
  role text not null default 'member' check (role = 'member'),
  created_at timestamptz not null default now(),
  primary key (user_id, app)
);

alter table platform.schema_migrations enable row level security;
alter table platform.profiles enable row level security;
alter table platform.app_memberships enable row level security;
revoke all on all tables in schema platform from public, anon, authenticated;

create or replace function platform.handle_new_user() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  insert into platform.profiles (user_id, email, display_name, avatar_url)
  values (new.id, new.email,
          coalesce(new.raw_user_meta_data->>'full_name', new.raw_user_meta_data->>'name'),
          coalesce(new.raw_user_meta_data->>'avatar_url', new.raw_user_meta_data->>'picture'))
  on conflict (user_id) do nothing;
  return new;
end $$;
revoke execute on function platform.handle_new_user() from public, anon, authenticated;

drop trigger if exists on_auth_user_created_platform on auth.users;
create trigger on_auth_user_created_platform
  after insert on auth.users
  for each row execute function platform.handle_new_user();
