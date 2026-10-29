# Operations runbook: the commands the owner runs

Everything here runs from the repository root on the owner's machine. Nothing here prints a secret. Values come
from the dashboards named; this file never holds one.

## Where the secrets live

| Secret | Lives in | Read by |
|---|---|---|
| `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` | Vercel → invest-witus → Settings → Environment Variables (Production, Sensitive) | the deployed site |
| `STORAGE_DATABASE_URL`, `STORAGE_DATABASE_URL_UNPOOLED` and the other `STORAGE_*` names | written by the Neon integration on the same page (the connect dialog's prefix was `STORAGE`) | the site (pooled) and migrations (unpooled) |
| `WITUS_OIDC_CLIENT_ID`, `WITUS_OIDC_CLIENT_SECRET` | same page; the matching `WITUS_OIDC_SECRET__INVEST` sits on the witus-online project | Sign in with WitUS |
| `TIINGO_API_KEY`, `CRON_SECRET` | same page | the nightly pull and its cron route |
| `ALPACA_PAPER_KEY_ID`, `ALPACA_PAPER_SECRET_KEY` | same page; made in Alpaca's paper dashboard, API Keys, Generate New Key | Confirm, the paper page and the order sync (chapter 11) |
| `INBOX_INGEST_URL`, `INBOX_SOURCE_SLUG`, `INBOX_INGEST_SECRET` | same page; the secret matches this slug's `hmac_secret` in `INGEST_SOURCES` on the witus-inbox project | the in-app reporter and the waitlist's copy to WitUS Inbox (chapter 13) |
| the laptop's `.env` | gitignored, `DJANGO_DEBUG=1` and local values only | `uv run --env-file .env ...` |

Every variable on the Vercel project is marked Sensitive, so `vercel env pull` and `vercel env run` cannot
supply them to a local command. For anything that needs production values, make a one-line file as below.

## Automatic migrations (the usual way)

`.github/workflows/migrate-production.yml` migrates Neon after every push to `main` that changes a migration
file, and on demand (GitHub → Actions → **Migrate production database** → **Run workflow**). Its summary lists
every migration and whether it is applied. It needs one repository secret, set once, without the value ever
appearing on screen:

```sh
neon connection-string --project-id <invest-db project id> | gh secret set NEON_DIRECT_URL --repo dapperAuteur/invest-witus
```

(`neon connection-string` prints the direct, unpooled string by default; `--pooled` would print the pooler one,
which migrations should not use. `gh secret set` reads the value from the pipe.) Vercel deploys the same push in
parallel, so pages that need a brand-new table answer 500 for about a minute until the job finishes; the old
pages keep working because migrations here only add.

Cost: one short Linux job per migration-bearing merge. GitHub's included Actions usage for private repositories
on the Free plan is a monthly dollar amount (12 USD, about 2,000 Linux minutes); a Linux 2-core minute past that
is 0.006 USD (GitHub Docs, "GitHub Actions billing", read 2026-10-28). This job takes about a minute, a few times a
month: zero in practice. Neon wakes the compute for a few seconds per run.

## Production migrations by hand (fallback)

Run after every merge that adds a migration (the deploy itself never migrates; chapter 06 decided that).
Between the deploy and this command, pages that touch the new table answer 500.

1. Neon console → project `invest-db` → **Connect** → pooled connection **off** → copy the string (its host has
   no `-pooler` in it).
2. Create `.env.migrate` in the repository root (gitignored by `.env*`) with one line:
   ```
   STORAGE_DATABASE_URL_UNPOOLED=<the direct string>
   ```
3. ```sh
   cd /Users/bam/Code_NOiCloud/ai-builds/claude/invest-witus
   DJANGO_SECRET_KEY=only-for-this-shell-not-the-real-one VERCEL= \
     uv run --env-file .env.migrate python manage.py migrate --database direct
   rm .env.migrate
   ```
   Expected: `Applying <app>.<migration>... OK` lines, then nothing. The throwaway key is fine: `migrate` writes no
   signed data. `VERCEL=` (empty) keeps the settings in laptop mode. The default database in that shell is the
   laptop SQLite file; `--database direct` sends everything to Neon. Any "unapplied migrations" warning printed by
   another command in the same shell is about the laptop file, not Neon.

To see what Neon has: `... python manage.py showmigrations --database direct` with the same env file.

## The owner's login (once per database)

```sh
read -s DJANGO_SUPERUSER_PASSWORD && export DJANGO_SUPERUSER_PASSWORD
DJANGO_SUPERUSER_USERNAME=<username> DJANGO_SUPERUSER_EMAIL=<the address on your WitUS account> \
DJANGO_SECRET_KEY=only-for-this-shell-not-the-real-one VERCEL= \
  uv run --env-file .env.migrate python manage.py createsuperuser --noinput --database direct
unset DJANGO_SUPERUSER_PASSWORD
```
Use the WitUS account's email so chapter 07 links the two on the first sign-in. A second run says
`Error: That username is already taken.`

## The nightly price pull

- Scheduled: `vercel.json` runs `GET /api/cron/pull-prices/` at 06:00 UTC daily (Hobby: once a day, within the hour).
- From the site, signed in as the owner (the usual way since 2026-10-29, decisions 116 to 118):
  - **Fetch prices now**, on `/accounts/` and in each account page's **Watch list** section, runs the same pull
    for the symbols your own accounts hold or watch: the last seven days, a year for a symbol's first pull, at
    most 50 requests with the one-second pause, and a 240-second time limit so the page answers inside
    Vercel's 300-second maximum. The message reads `Fetched closes from tiingo for N symbols in R requests:
    I inserted, U updated, C unchanged, F refused, B backfilled, S skipped for budget.`, then one line per
    refused symbol, and, when the run stopped early, `Stopped by <reason>; not reached: ... The rest continue
    tonight.`
  - **Get history**, beside each watched symbol and on its history page, asks that one symbol's 1, 5 or 10
    years, or all available, in one request, and says how many days were added and the earliest close now
    stored. A range past a year also writes the symbol's **Price backfills** row.
  - Each button runs once every 10 minutes: per owner for Fetch prices now, per symbol for Get history. A
    second press says when it can run again. **Prices** → **Manual price runs** in the admin lists the last
    run of each; delete a row to lift its guard.
  - Nothing to run after the deploy: migration `prices/0003` (the guard's table, additive) is applied by the
    migrate workflow on merge.
- By hand on production: Vercel → invest-witus → Settings → **Cron Jobs** → **Run**, or
  `curl -H "Authorization: Bearer <CRON_SECRET>" https://invest.witus.online/api/cron/pull-prices/`
  (503 means the secret is unset on the project; 403 means the header does not match).
- By hand on the laptop against the local database (the fallback when the site is down or for a range the
  buttons do not offer): `uv run --env-file .env python manage.py pull_prices` (`--since YYYY-MM-DD`,
  `--symbols A,B`); with no `TIINGO_API_KEY` in `.env` it reads CSV files from `PRICES_CSV_DIR`. The command has
  no 10-minute guard and no time limit.
- A year of history (2026-10-29): a symbol's first pull asks for 365 days in its one request, then writes a
  **Price backfills** row (admin, under **Prices**). Nothing to run by hand: migration `prices/0002` is applied
  by the migrate workflow on merge, and the next nightly run backfills every held and watched symbol that has
  no row yet, up to the 50-request budget, the rest the night after. The cron JSON lists them under
  `backfilled`. To ask for a symbol's year again, delete its **Price backfills** row; to reach further back
  than a year, press **Get history** beside the symbol (or, as the fallback, `pull_prices --symbols A --since
  YYYY-MM-DD`).

## Paper orders (chapter 11)

Nothing new runs by hand after a deploy: chapter 11's three migrations are applied by the workflow above.

- The nightly cron reads open paper orders back after the price pull, once both Alpaca keys are set; its JSON
  gains an `orders` object (`checked`, `changed`, `filled`, `ended_part_filled`, `ended_unfilled`, `still_open`,
  `failed`).
- By hand on production: the paper page's **Check orders now** (signed in as the owner), or the cron by hand as
  above.
- By hand on the laptop: `uv run --env-file .env python manage.py sync_paper_orders`. With no keys in `.env` it
  prints `Alpaca paper keys are not set; nothing to sync.` and calls nothing.

## Reports and the waitlist's copies to WitUS Inbox (chapter 13)

Nothing to run after a deploy: migration `reports/0001` is applied by the migrate workflow on merge.

- Each report and each new waitlist signup is saved first, then sent to Inbox at once with a 5-second timeout.
  A row Inbox did not take keeps its reason in **Last error** (admin, **Reports and WitUS Inbox**).
- **The retry is automatic.** The nightly cron sends every unsent row after the price pull and the paper orders,
  oldest first, at most 25 a night, once the three `INBOX_` names are set; its JSON gains an `inbox` object
  (`checked`, `sent`, `failed`, `stopped`). A timeout or a 5xx stops that night's run; a 4xx is recorded on its
  row and the rest go on.
- **The manual fallback is "Send again".** Admin, **Reports** (or **Waitlist copies to Inbox**), select the rows,
  action **Send again to WitUS Inbox**, **Go**. A row already sent is left alone, so selecting everything is safe.
- By hand on the laptop against the local database: `uv run --env-file .env python manage.py reports --send`
  (without `--send` it only lists the reports not marked Done). With no `INBOX_` names in `.env` it says Inbox is
  off and sends nothing.
- A row that reads **Failed, will retry** with a 401: the slug is not in Inbox's `INGEST_SOURCES` for that
  environment, Inbox was not redeployed after its list changed, the two secrets differ, or the server clock is more
  than five minutes off. Inbox's own function log names which (`[ingest] unknown source` or `[ingest] hmac verify
  failed`).
- Registering this app with Inbox, or rotating the secret: one `openssl rand -hex 32` per environment, the entry
  `{"slug":"<INBOX_SOURCE_SLUG>","hmac_secret":"<secret>"}` appended to `INGEST_SOURCES` on the witus-inbox Vercel
  project for that environment (keep the other entries), redeploy Inbox, set the same secret here as
  `INBOX_INGEST_SECRET`, redeploy this app, then **Send again** on any waiting rows.

## The laptop copy

```sh
uv run --env-file .env python manage.py migrate        # the local SQLite file
uv run --env-file .env python manage.py runserver      # http://127.0.0.1:8000/
uv run pytest                                           # the whole suite
```

## Redeploy

Vercel → Deployments → the latest → **Redeploy** (needed after changing an environment variable; a merge to
`main` deploys on its own). `https://invest.witus.online/healthz/` reports `{"status": "ok", "database": true}`
when the site reaches Postgres.

## Vercel project settings that the ecosystem expects

Standard build machine, On-Demand Concurrent Builds off, Ignored Build Step = production and `bundle/*` only
(set 2026-10-28 with `npx tsx scripts/vercel-build-settings.ts --apply --ignore-step --only invest-witus` from
the witus repo), Deployment Protection off for Production, System Environment Variables enabled.
