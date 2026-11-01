# AI Bharatiyaa: status

**MVP complete on 2026-11-01. Further work waits for real usage.**

The suite (this parent site, LinkedIn Content Agent and Task Queue) is a
portfolio and dogfood project, shared with a few friends. Everything below is
a deliberate decision to wait, not something that was missed. Each item names
what would bring it back.

The `mvp-1` git tag in each repository marks the shipped MVP.

## What the MVP includes

- One Google or email sign-in for the whole suite, with admin approval of new
  accounts and per-user data.
- LinkedIn Content Agent: brief → clarify → draft → judge/rewrite loop →
  scene → mascot image. Includes per-user writer profiles (with five role
  templates), mascots made in Character Studio, and backdrops.
- Every compute step runs as a Task Queue task on the owner's laptop worker
  (Ollama for text, ComfyUI for images).
- Storage stays small by itself: archiving a post (by hand, or automatically
  after 30 idle days) deletes its image, replaced renders and unpicked hero
  candidates are deleted, and a daily job retries and tidies up.

## Known limits, by design

- Drafts and images need the owner's laptop worker to be running. Without it
  they wait in the queue.
- Images are public to anyone with the link. Users are told this on the
  sign-in and account pages.
- Free tiers only (Vercel, Supabase). No backups beyond what Supabase's free
  tier provides, and data may be reset.

## Deferred

| Item | Why it waits | What would bring it back |
|---|---|---|
| **Platform** | | |
| Rotate shared secrets | Owner's choice while development is active (see README "Platform TODO") | Development settles, or before sharing beyond friends |
| Private image links (signed URLs) and an `approved` check in Storage policies | Friends-only use; images aren't sensitive | The first user outside the friend group, or any sensitive image |
| Per-user limits | A handful of users can't overload one worker | One user's load visibly slows others, or more than ~10 active users |
| Own-worker-first routing and gamification | Only the owner runs a worker | Friends start running their own workers |
| Account deletion and data export | Can be done by hand for a few users | The first request that's painful to handle by hand |
| Shared auth package across apps | Three apps, small duplication | A fourth app joins the suite |
| **LinkedIn Content Agent** | | |
| Use feedback in prompts; calibrate pillar weights | No body of real feedback yet; designing it now would be guessing | About 50 posts with feedback, or repeated complaints about draft quality |
| Update an existing profile from a template | Only new users need templates today (button shown as "Coming soon") | A user asks to switch role |
| Public mascot library | Users make their own mascot in Character Studio | New users get stuck creating a mascot |
| Distinct per-mascot personas | One personality field covers current use | A user wants several mascots with different points of view |
| Character Studio: card editing and versioning, retry one candidate, archive/delete | Core create → generate → lock flow works | Users keep more than one mascot, or ask for these |
| Scenes follow mood and setting more closely (prompt tuning) | Images are acceptable for now | Complaints about image relevance |
| Worker pause, drain and shutdown from the UI | The owner starts the worker by hand | Someone other than the owner runs a worker |
| **Task Queue** | | |
| Owner-aware producer keys and private artifact delivery | All producers are first-party apps | A third-party producer, or the queue offered as a service |
| Future admin UI backlog (`docs/future-ui-mvp.md`) | Only the owner uses the admin pages | Someone else needs to operate the queue |

## Revisiting

To pick something up: move its row into that repository's README TODO,
design it first (brainstorm → spec → plan), and compare against the `mvp-1`
tag.
