# AI Bharatiyaa Web

The public front door for the AI Bharatiyaa product family.

This repository owns the suite homepage and, over time, the path-based product gateway:

- `/` — AI Bharatiyaa home and product directory
- `/queue` — Task Queue
- `/linkedin` — LinkedIn Content Agent (managed separately)

Task Queue is deployed independently and mounted here through Vercel rewrites.
Its UI and browser API are both product-scoped (`/queue/*` and
`/api/queue/*`), while machine clients continue to call the service directly.

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

