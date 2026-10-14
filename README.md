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

