# Deploying the dashboard (Cloudflare Pages)

The dashboard is a **pre-built static site** — `web/index.html` is complete and
self-contained (all data embedded, no external requests). There is **nothing to
build** on the host; Cloudflare only needs to *serve* the `web/` folder.

The "build fail" happens when Cloudflare tries to run a build command. The fix is
to tell it there is no build.

## Cloudflare Pages settings

1. Cloudflare dashboard → **Workers & Pages** → **Create** → **Pages** →
   **Connect to Git**.
2. Pick the **`techmuns/screener-scrape`** repository.
3. On the setup screen, use **exactly** these:

   | Setting | Value |
   |---|---|
   | Production branch | `main` |
   | Framework preset | **None** |
   | Build command | **leave empty** |
   | Build output directory | **`web`** |
   | Root directory | `/` (leave default) |

4. **Save and Deploy.**

That's it. Cloudflare uploads `web/` and serves `web/index.html` at your site
root. Because the build command is empty, it never tries (and fails) to build.

> If you already created the project with a build command, go to
> **Settings → Builds & deployments → Build configuration → Edit**, clear the
> build command, set the output directory to `web`, then **Retry deployment**.

## Why not let Cloudflare build it?

The dashboard's data is produced by the Python pipeline in `pipeline/`, which
needs to fetch screener.in and run a database — Cloudflare's build sandbox can't
do that. So we build locally / in CI, commit the finished `web/index.html`, and
Cloudflare just serves it.

## Next step: daily refresh (planned)

To refresh the numbers every day we'll run the pipeline on a schedule (e.g. a
GitHub Action): fetch → recompute → rebuild `web/` → commit. Cloudflare Pages
auto-redeploys on every push to `main`, so a fresh commit = a fresh live site,
with no manual step.
