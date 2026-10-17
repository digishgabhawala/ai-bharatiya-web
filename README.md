# AI Bharatiyaa Web

The public front door for the AI Bharatiyaa product family.

This repository owns the suite homepage and, over time, the path-based product gateway:

- `/` — AI Bharatiyaa home and product directory
- `/queue` — Task Queue
- `/linkedin` — LinkedIn Content Agent

Task Queue and LinkedIn Content Agent are deployed independently and mounted
here through Vercel rewrites. Each product's UI and browser API are
product-scoped (`/queue/*` + `/api/queue/*`, `/linkedin/*` + `/api/linkedin/*`),
and machine clients use the matching product-scoped API on this same public
origin. For Task Queue, configure
`TASK_QUEUE_URL=https://ai-bharatiya-web.vercel.app/queue`; its clients map
that to `/api/queue`. The standalone service hostname appears only in this
gateway's rewrite configuration as an internal upstream. Both apps use the
same Supabase project with default session storage, so one sign-in on this
origin works in both. The Content-Security-Policy allows images from
`https://*.supabase.co` (LinkedIn's post images live in Supabase Storage).

## Local preview

```bash
python3 -m http.server 4173
```

Then open `http://localhost:4173`.

## Validate

```bash
python3 scripts/validate_site.py
```

## Shared design system

The site follows `ai-bharatiya-commons` v0.2. The checked-in token snapshot is pinned to commit `741e8ce` so production builds do not depend on a sibling repository.


## Platform API (`/api/platform/*`)

Shared identity for the suite: a `platform` schema in the Supabase project
(`profiles`, `app_memberships`, filled by a trigger on `auth.users`) and a
small FastAPI function, `api/identity.py` (package `api/_platform_api/`),
deployed in `hnd1` and reached through the `/api/platform/:path*` rewrite.

| Route | Who | Does |
|---|---|---|
| `GET /api/platform/config` | public | Supabase URL + publishable key for the pages |
| `GET /api/platform/me` | signed in | profile, status, admin flag, apps |
| `GET /api/platform/users?status=` | admin | profiles, pending first |
| `POST /api/platform/users/{id}/{approve,reject,suspend,reinstate}` | admin | status change (409 if illegal) |
| `POST /api/platform/users/{id}/admin` `{is_admin}` | admin | grant or revoke admin |

Settings (Vercel environment variables): `DATABASE_URL` (Supabase pooler),
`SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, and `PLATFORM_ADMIN_EMAILS`
(bootstrap only, read by the migration script).

### Migrations

SQL lives in `db/migrations/`. Apply it (idempotent), backfill a profile for
every existing auth user, and seed the bootstrap admins (only while no
approved admin exists):

```bash
DATABASE_URL='postgresql://…' PLATFORM_ADMIN_EMAILS=admin@example.com \
  .venv/bin/python scripts/apply_platform_migrations.py
```

### Tests

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/playwright install chromium

.venv/bin/pytest -q tests --ignore=tests/db --ignore=tests/browser   # pure, no Docker
(cd ../task-queue && supabase start)                                  # local Postgres + auth
.venv/bin/pytest -q tests/db                                          # local DB only
.venv/bin/pytest -q tests/browser                                     # headless Chromium
.venv/bin/ruff check api tests scripts
```

The DB tests refuse any database that is not on `127.0.0.1`/`localhost`.

## Platform TODO

- **Rotate shared secrets once the projects mature** (deferred by choice,
  2026-10-17, while development is active). Rotate the Supabase database
  password and the service/secret key, then update the local `.env` files
  and the Vercel env of all three projects (parent, LinkedIn, task-queue).
  Why: the database URL appeared in tool output during the 2026-10-16
  rollout, and 51 task-queue deployments made before its `.vercelignore`
  (14 Aug–17 Oct 2026) contain its `.env` (team-visible only). Delete those
  old deployments at the same time.
- Private image links (signed URLs) and an `approved` check in Storage
  policies; per-user limits; public character library; own-worker-first
  routing; account deletion / data export (see the user-management spec).
