# AI Bharatiyaa: status

**MVP complete on 2026-11-01; Showrun joined on 2026-11-09. Further work waits
for real usage.**

The suite (this parent site, LinkedIn Content Agent, Task Queue and Showrun) is
a portfolio and dogfood project, shared with a few friends. Everything below is
a deliberate decision to wait, not something that was missed. Each item names
what would bring it back.

The `mvp-1` git tag in each repository marks the shipped MVP.

## What the MVP includes

- One Google or email sign-in for the whole suite, with admin approval of new
  accounts and per-user data.
- LinkedIn Content Agent: brief → clarify → draft → judge/rewrite loop →
  scene → mascot image. Includes per-user writer profiles (with five role
  templates), mascots made in Character Studio, and backdrops.
- Showrun: check a Playwright script → record it locally → upload the
  recording and its HTML report → review the director's plan (narration, tone,
  pacing, zoom) → produce a narrated, captioned MP4 in the user's own voice.
  Includes three-tone voice setup with consent, re-roll of single lines, and
  automatic deletion of recordings and videos after 7 days. The home page shows
  a sample made from LinkedIn Content Agent's own browser test.
- Every compute step runs as a Task Queue task on the owner's laptop worker
  (Ollama for text, ComfyUI for images, a Showrun worker for voice, captions and
  video).
- Storage stays small by itself: archiving a post (by hand, or automatically
  after 30 idle days) deletes its image, replaced renders and unpicked hero
  candidates are deleted, and a daily job retries and tidies up.

## Known limits, by design

- Drafts and images need the owner's laptop worker to be running. Without it
  they wait in the queue.
- Showrun accepts Playwright Test specs for Chromium only, one spec per
  project, and makes videos of at most 5 minutes. Recordings, voices and videos
  are private, behind short-lived links; download a video within 7 days to keep
  it.
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
| **Showrun** | | |
| Cancel a running production | Producing again or deleting covers it; a run takes about 8 minutes | Someone waits on a production they started by mistake |
| Replace Chatterbox, which is no longer maintained (risk R1 in Showrun's `docs/RISKS.md`) | It works today on the owner's worker | Before selling Showrun, or the first failed install |
| Ready-made licensed voices (Kokoro is the best local option) | Owner's choice: users narrate in their own voice, or make a silent captioned video | A user wants narration without recording their voice |
| Local video check by a vision model (T16 in Showrun's plan) | Optional; the owner reviews each video | Videos ship with mistakes a frame check would catch |
| A record of when the daily clean-up last ran | Vercel's free plan keeps logs for one hour | A file is found in storage after its deletion date |
| Other test tools and browsers (Cypress, Firefox, WebKit) | Playwright on Chromium covers the owner's tests | A user asks for one |
| **Task Queue** | | |
| Owner-aware producer keys and private artifact delivery | All producers are first-party apps | A third-party producer, or the queue offered as a service |
| Future admin UI backlog (`docs/future-ui-mvp.md`) | Only the owner uses the admin pages | Someone else needs to operate the queue |

## Revisiting

To pick something up: move its row into that repository's README TODO,
design it first (brainstorm → spec → plan), and compare against the `mvp-1`
tag.
