# OOS-AQUA — Water Management App on Netlify

OOS AQUA is a water-supplier management app (customers, daily jar entries,
monthly billing, dues & security deposits, printable PDF invoices).

It is hosted on **Netlify** as a **static frontend + Netlify Functions backend**,
with the database on **Neon Postgres (cloud)**. The data never lives on the
web host — it stays in your own Postgres database, so it is safe.

## Architecture

```
netlify/functions/*.mjs   → API (Node.js, one function per route)
public/                   → static site (index.html, logo, QR)
  └── index.html          → the app UI (mobile-first)
Neon Postgres (cloud)     → customers, entries, backups tables
```

Netlify runs JavaScript/TypeScript/Go functions only (not Python), so the old
Flask server (`server.py`) has been mirrored as Netlify Functions. `server.py`
is kept only for local development.

## Data safety (important)

The app now does **real** backups (the old `backup_database()` was a no-op):

- A **full snapshot table** (`backups`) stores a JSON copy of the whole DB.
- Snapshot is taken **before every destructive action**
  (delete customer/entry, payment, import).
- An **automatic snapshot every ~6 hours** on any write (no cron needed —
  works on free Netlify plan).
- A **daily scheduled snapshot** at 00:00 UTC (`backup_schedule.mjs`).
- Keep-last-60 pruning keeps storage small.
- Everything is **soft-delete** — records are hidden, never erased.
- `GET /api/export` downloads a full JSON backup any time.

Restore path:
- Records are never hard-deleted, so **recovering hidden (soft-deleted) data is easy**.
- `POST /api/import` (paste an exported JSON) restores records that are missing.
- `POST /api/restore` (no body restores *all* soft-deleted records) re-shows
  records that are hidden. It always snapshots the DB first:
  ```
  curl -X POST https://YOUR-SITE.netlify.app/api/restore
  ```
- `GET /api/backups` lists the stored snapshots in the `backups` table.

## Deploying to Netlify

1. Push this repo to GitHub.
2. Netlify → "Add new site" → Import from Git → choose the repo.
3. Build settings (auto-detected from `netlify.toml`):
   - Build command: `echo 'static site + functions'`
   - Publish directory: `public`
4. **Set the environment variable** (critical — without it the API won't work):
   - Netlify dashboard → Site settings → Environment variables →
     add `DATABASE_URL` → value = your Neon Postgres connection string, e.g.
     `postgresql://USER:PASSWORD@ep-XXXX-pooler.c-3.ap-southeast-1.aws.neon.tech/neondb?sslmode=require`
   - (Only the `postgresql://` URL is needed. The app sets TLS itself.)
5. Deploy. Open the site URL — the app works with all existing data, because
   it points at the same Neon database.

> Tip: enable scheduled daily backups by confirming the "Scheduled functions"
> feature is available on your plan. Even if it is not, the every-6-hours guard +
> before-delete snapshots still protect your data.

## Local development

```bash
# Python/Flask version (still works, uses the same Neon DB)
pip install -r requirements.txt
$env:DATABASE_URL = "postgresql://USER:PASSWORD@ep-XXXX-pooler.c-3.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
python server.py

# Netlify Functions locally
npm install
$env:DATABASE_URL = "postgresql://USER:PASSWORD@ep-XXXX-pooler.c-3.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
netlify dev
```

## What changed vs the original repo

- Flask API → Netlify Functions (Node.js) so it can run on Netlify.
- DB credentials moved to the `DATABASE_URL` environment variable.
- Connection **pooling** replaces opening a new DB connection per request
  (was the main source of lag).
- Billing page rewritten from N+1 queries to **one** SQL query.
- Dashboard no longer rebuilds invisible tab lists on every data load.
- Real, inspectable, restorable backups (see above).