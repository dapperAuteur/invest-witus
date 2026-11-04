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
| `ALPACA_PAPER_KEY_ID`, `ALPACA_PAPER_SECRET_KEY` | same page; made in Alpaca's paper dashboard, API Keys, Generate New Key | the DEFAULT key slot: Confirm, the paper page and the order sync for accounts linked through it (chapter 11) |
| `ALPACA_PAPER_KEY_ID__<SLOT>`, `ALPACA_PAPER_SECRET_KEY__<SLOT>`, any number of pairs | same page; each pair made in its own Alpaca paper account (see [Alpaca key slots](#alpaca-key-slots-one-paper-account-per-method)) | the same, for the accounts linked through that slot (decision 159) |
| `INBOX_INGEST_URL`, `INBOX_SOURCE_SLUG`, `INBOX_INGEST_SECRET` | same page; the secret matches this slug's `hmac_secret` in `INGEST_SOURCES` on the witus-inbox project | the in-app reporter and the waitlist's copy to WitUS Inbox (chapter 13) |
| `OUTBOX_TRIGGER_ENABLED`, `OUTBOX_INGEST_URL`, `OUTBOX_SOURCE_SLUG`, `OUTBOX_INGEST_SECRET` | same page; the secret matches this slug's `hmac_secret` in `INGEST_SOURCES` on the witus-outbox project | **Draft a post** and its copies to WitUS Outbox |
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
    for the symbols your own accounts hold or watch: the last seven days, two years for a symbol's first pull, at
    most 50 requests with the one-second pause, and a 240-second time limit so the page answers inside
    Vercel's 300-second maximum. The message reads `Fetched closes from tiingo for N symbols in R requests:
    I inserted, U updated, C unchanged, F refused, B backfilled, S skipped for budget.`, then one line per
    refused symbol, and, when the run stopped early, `Stopped by <reason>; not reached: ... The rest continue
    tonight.`
  - **Get history**, beside each watched symbol and on its history page, asks that one symbol's 1, 5 or 10
    years (or 2 since 2026-10-30), or all available, in one request, and says how many days were added and the earliest close now
    stored. A range of two years or more also writes the symbol's **Price backfills** row.
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
- Two years of history (2026-10-29, two years since 2026-10-30, decision 149): a symbol's first pull asks for
  730 days in its one request, then writes a
  **Price backfills** row (admin, under **Prices**). Nothing to run by hand: migration `prices/0002` is applied
  by the migrate workflow on merge, and the next nightly run backfills every held and watched symbol that has
  no row yet, up to the 50-request budget, the rest the night after. The cron JSON lists them under
  `backfilled`. After the two-year change merges, each symbol backfilled under the one-year rule asks once
  more for two years on its next pull (one request each, inside the budget); nothing to run by hand. To ask
  for a symbol's two years again, delete its **Price backfills** row; to reach further back, press **Get history** beside the symbol (or, as the fallback, `pull_prices --symbols A --since
  YYYY-MM-DD`).
- Adjusted closes, splits and dividends (2026-10-29, decisions 134, 137 and 138): migration
  `prices/0004_daily_close_adjustments` adds `adj_close`, `split_factor` and `div_cash` to the closes table
  (nullable, database default NULL, additive), applied by the migrate workflow on merge. Every pull and every
  Get history stores them from then on. Rows stored before have none, so once after the merge press **Fetch
  history for all** with **All available** in each account's **Watch list** section (or Get history per symbol;
  a held symbol that is not watched can be refilled the same way after adding it to the watch list, or by
  `pull_prices --symbols A --since 1900-01-01`). The message counts the refilled days as **updated**. Until a
  symbol is refilled, its chart uses the unadjusted close and says so. When a later nightly week brings a new
  split or dividend, `DailyClose.upsert` rescales the stored adjusted closes the week did not cover by the same
  ratio; the pull's log line ends with `rescaled N` when that happens.
- Symbol profiles (2026-10-30, decision 150): migration `prices/0005_symbol_profile` adds the `SymbolProfile`
  table (a new table, additive; it also lists **Get description** as a manual run kind, no column change),
  applied by the migrate workflow on merge. After the closes, the nightly cron fetches Tiingo's ticker metadata
  (`GET /tiingo/daily/<ticker>`) for each symbol with no profile or one older than 7 days, inside what the
  closes left of the 50-request budget and at most 10 a night, and adds `profiles` (`requests`, `fetched`,
  `failed`, `skipped`) to its JSON; with no `TIINGO_API_KEY`, or after a 429, the body has no `profiles`. The
  symbol page's **Get description** button fetches one now (10-minute guard per symbol, under **Manual price
  runs**). **Prices** → **Symbol profiles** in the admin lists them; delete a row to fetch it again. Nothing to
  run by hand: the first night after the merge fetches up to 10, the rest over the next nights.
- **Fetch history for selected** and **Fetch history for all** (2026-10-29, decision 139), under the Watch list
  table, run Get history for several watched symbols in one press: one request each, at most 50, the one-second
  pause, the 240-second limit, a symbol inside its 10-minute guard skipped and named, and `The rest: press
  again in N minutes: ...` when the budget, a 429 or the time stopped it.

## Paper orders (chapter 11)

Nothing new runs by hand after a deploy: chapter 11's three migrations are applied by the workflow above.

- The nightly cron reads open paper orders back after the price pull, once both Alpaca keys are set; its JSON
  gains an `orders` object (`checked`, `changed`, `filled`, `ended_part_filled`, `ended_unfilled`, `still_open`,
  `failed`).
- By hand on production: the paper page's **Check orders now** (signed in as the owner), or the cron by hand as
  above.
- By hand on the laptop: `uv run --env-file .env python manage.py sync_paper_orders`. With no complete key slot
  in `.env` it prints `Alpaca paper keys are not set; nothing to sync.` and calls nothing. Since decision 159 it
  reads each account's orders with that account's key slot, and prints an account whose slot is missing on
  stderr.

- Default view, plan edit and delete (2026-11-02, decisions 155 to 158): migration
  `methods/0005_view_preference` adds the `ViewPreference` table (a new table, additive, safe to run twice),
  applied by the migrate workflow on merge; by hand, the fallback above. Until it runs, method pages answer 500
  for about a minute, because they read the table. Edit and Delete call Alpaca only on the owner's click, and only
  for a plan with orders still open: `DELETE /v2/orders/{id}` to cancel, then `GET /v2/orders/{id}` to read it
  back. A cancel Alpaca has not finished (`pending_cancel`) stops the edit or delete with nothing changed; **Check
  orders now** or the nightly cron finishes the row, then the owner presses Save or Delete again.

- The plan's amount as a total, Settings, striped tables and the Help bubble's draft (2026-11-03, decisions 161
  to 165): no migration and nothing to run after the deploy. `/settings/` is a new signed-in route; the Help
  bubble's **Open the full form** keeps the draft in the session (`report_draft`, the database session table
  already in use), read once by the next `GET /report/`. A month whose ranking changed after its buys were placed
  now keeps those buys (decision 162): to buy a newcomer anyway, buy it by hand at Alpaca and log it, or wait for
  next month's ranking.

- Stronger table stripes and a line under every row (2026-11-04, decision 175): `site.css` only, no migration and
  nothing to run after the deploy. If a page still shows the faint stripes, the browser cached the old stylesheet:
  reload once.

## Alpaca key slots: one paper account per method

Decisions 159 and 160 (2026-11-02). Each method runs in its own Invest account, and each Invest account that
trades on paper is linked to its own Alpaca paper account, because two plans in one Alpaca account would spend one
pool of cash. Alpaca gives every paper account its own keys, so the server holds one pair per Alpaca account,
called a **slot**: `ALPACA_PAPER_KEY_ID__<SLOT>` and `ALPACA_PAPER_SECRET_KEY__<SLOT>`, where `<SLOT>` is 1 to 40
of `A-Z`, `0-9` and `_`, not starting with `_` (for example `MOMENTUM`). One underscore before the name
(`ALPACA_PAPER_KEY_ID_MOMENTUM`) is read as the same slot since decision 166, but the commands below use two; a
slot set in both forms with different values is **conflicting** and not used. The unsuffixed pair is the slot `DEFAULT`; the account linked
before slots existed uses it and needs nothing done. The app stores only the slot's name and the Alpaca account
number on the account, never a key.

**After the merge:** migration `holdings/0003_account_alpaca_slot_and_number` (two columns with database
defaults, chapter 11's one-per-owner constraint swapped for two new ones) is applied by the migrate workflow; by
hand, the fallback above. Nothing else runs after a deploy.

**Add a slot for a new method** (repeat per method):

1. Alpaca → log in at https://app.alpaca.markets → switch to paper in the top bar. Create another paper account
   from the account menu in the dashboard's upper left, where the paper account number is shown (Alpaca's
   paper-trading page: "Don't forget to generate new API keys for any newly created account",
   https://docs.alpaca.markets/docs/paper-trading, read 2026-11-02). Note the new account's number. Alpaca's
   article https://alpaca.markets/learn/start-paper-trading (read 2026-11-03) says paper trading "allows up to 3
   distinct simulated accounts"; the docs page gives no number.
2. With that new paper account selected, **API Keys** → **Generate New Key**. Alpaca shows the secret once; keep
   the dialog open for step 3.
3. In the repository folder (the Vercel project is linked there), add the two variables for Production, one at a
   time. The CLI asks for each value at a prompt, so the value never goes into the shell's history, a file or a
   chat; copy it from Alpaca's dialog into the prompt:
   ```sh
   cd /Users/bam/Code_NOiCloud/ai-builds/claude/invest-witus
   vercel env add ALPACA_PAPER_KEY_ID__MOMENTUM --environment production --sensitive
   vercel env add ALPACA_PAPER_SECRET_KEY__MOMENTUM --environment production --sensitive
   ```
   (Flags as `vercel env add --help` lists them in Vercel CLI 65.5.0, read 2026-11-02. Whether the prompt hides
   what is typed was not checked; clear the screen afterwards if it shows the value. Never use `--value` or
   `echo ... |`, which put the secret in the shell's history.) Then copy something harmless to empty the clipboard.
4. **Redeploy** (below): the settings find slots when they load, so a new pair is seen only by a new deployment.
5. Signed in as the owner: **Accounts** → **Alpaca key slots** shows `MOMENTUM` with the last four characters of
   its key id and **complete**. If it says **keys incomplete**, one of the two names is missing or misspelled.
   If the slot is not listed at all, or says **conflicting**, read **Variables the app could not use** below the
   table: every variable starting `ALPACA_PAPER_` that no slot reads is there by name with the reason. Fix a name
   by adding the right one (step 3), removing the wrong one with `vercel env rm <NAME> production`, and
   redeploying. For a conflicting slot, remove whichever form holds the old keys.
6. Make or pick the Invest account for the method (admin → Accounts → add, **Kind** Paper (practice)), open it,
   **Link to Alpaca paper** → choose the slot → **Check this slot**: the number shown must be the new Alpaca
   account's number from step 1. Then **Link**. A refusal that the account "is already linked" means these keys
   belong to an Alpaca account another Invest account trades in: generate keys in the right paper account.
7. Start the method on that account's method page, set its practice budget, and Confirm as usual.

**Replacing a slot's keys** (Alpaca keys regenerated): step 3 with `--force`, then redeploy. If the new keys
belong to a different Alpaca account, Confirm stops and the paper page says the keys now reach another account;
link the Invest account again to choose.

**Removing a slot:** unlink every account on it first (Link to Alpaca paper → **Unlink**, allowed once no order
is open), then `vercel env rm ALPACA_PAPER_KEY_ID__MOMENTUM production` and the secret's name, and redeploy. An
account whose slot is gone shows "Keys for slot MOMENTUM are not set on the server." and trades nothing; it never
falls back to DEFAULT.

**The nightly check** reads each account's open orders with its own slot. An account whose slot is missing lists
each of its open orders under `orders.failed` in the cron's JSON with that sentence; the others go on.

## Index rules version 2 (decisions 173 and 174)

**Migration:** `methods.0006_monthlyreview_rules_version`: one nullable column on `methods_monthlyreview` and a
data step that writes 1 on every month review that is closed or was closed and reopened. It runs with the usual
workflow on the merge (section above); by hand, the fallback above. Running it twice changes nothing (it only
writes where the column is empty). Until it has run, method pages, month reviews and Compare answer 500.

To see what it did, read-only, from the laptop with the same `.env.migrate`:

```sh
DJANGO_SECRET_KEY=only-for-this-shell-not-the-real-one VERCEL= \
  uv run --env-file .env.migrate python manage.py shell -c \
  "from invest_witus_site.methods.models import MonthlyReview as R; from django.db.models import Count; print(list(R.objects.using('direct').values('rules_version').annotate(n=Count('id')).order_by('rules_version')))"
```

Expected: one count for `1` (the months closed before version 2) and one for `None` (months never closed); `2`
appears once a month is closed after the deploy. No variable and no other post-deploy step.

After the deploy, signed in as the owner, on an index account with several funds (B_INDEX):

1. The method page lists no `fixed-amount` or "3 buys" finding for a month whose buys were placed by Confirm and
   filled; view B's Method line reads "version 2 (index-dca)".
2. A month closed before the deploy still shows its old findings, and the page says "Judged by version 1 of the
   rules, the version they were closed under: <months>."
3. **Compare methods** counts the months closed from now on as followed when their buys match.

## Compare methods (chapter 15)

No migration, no variable, no post-deploy step: the page reads the journal, the paper orders and the stored closes.
The one outside call is Alpaca's `GET /v2/account` for each account the site owner linked to Alpaca paper, read
when `/compare/` opens, all at once, with a 5-second timeout (`compare/records.py`, `ALPACA_TIMEOUT_SECONDS`), using
that account's key slot through `client_for`. A slow or refused answer is one sentence in the cross-check table;
the page still draws.

After a deploy, signed in as the owner:

1. Open **Compare methods**. The accounts with a plan are ticked; the chart has one line per account, plus the
   yardstick if a fund such as SPY or VOO is on a watch list with closes.
2. If the page says "No closes stored for VOO ...", press its **Get history** (2 years); the redirect comes back to
   the same comparison.
3. In **Cross-check: Alpaca's own numbers**, "Alpaca: holdings now" should be within a few percent of "Value here".
   A larger gap: run **Check orders now** on the account's paper page (an unsynced fill), then **Fetch prices now**
   (a missing close). "Keys for slot X are not set on the server." means the slot's keys are missing on Vercel
   (the section above).

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

## Post drafts to WitUS Outbox

Nothing to run after a deploy: migration `outbox/0001` is applied by the migrate workflow on merge.

- **Draft a post** (admin, **Posts to WitUS Outbox**, **Post drafts for WitUS Outbox**, superuser only) saves the
  text, makes one row per ticked platform and sends each to Outbox as a draft at once, 5-second timeout. The
  message says how many Outbox took. Approve, edit, schedule or reject them in Outbox; nothing is posted from here.
- **Off by default.** Nothing is sent unless `OUTBOX_TRIGGER_ENABLED` is exactly `true` and the three `OUTBOX_`
  names are set. Off, each row reads **Off, will retry** with the reason. To stop everything at once, set the
  switch to anything else (or delete it) on the Vercel project and redeploy: rows wait here.
- **The retry is automatic.** The nightly cron sends every row Outbox has not taken, after the Inbox step, oldest
  first, at most 25 a night, once the switch is on; its JSON gains an `outbox` object (`checked`, `sent`, `failed`,
  `stopped`). A timeout or a 5xx stops that night's run; a 4xx is recorded on its row and the rest go on. A resend
  is harmless: Outbox answers a repeated `external_ref` with the row it already has.
- **The manual fallback is "Send again".** Admin, **Post drafts for WitUS Outbox**, select the drafts, action
  **Send again to WitUS Outbox**, **Go**. Rows already in Outbox and blocked rows are left alone.
- By hand on the laptop against the local database: `uv run --env-file .env python manage.py send_outbox`. With the
  switch off in `.env` it prints `Stopped: WitUS Outbox is off: ...` and sends nothing.
- **Blocked, not sent:** the text named a symbol the app records, an amount, a percentage, a share count or a
  cashtag, or the draft was not written by a superuser. Blocked rows are never retried; write a new draft.
- **Failed, will retry** with a 401: the slug is not in Outbox's `INGEST_SOURCES` for that environment, Outbox was
  not redeployed after its list changed, the two secrets differ, or the clock is more than five minutes off.
  Outbox's function log says `[ingest] unknown source` or `[ingest] hmac verify failed`.
- Registering this app with Outbox, or rotating the secret: one `openssl rand -hex 32` per environment, the entry
  `{"slug":"<OUTBOX_SOURCE_SLUG>","hmac_secret":"<secret>","workspace_name":"<Ocoya workspace name>"}` appended to
  `INGEST_SOURCES` on the witus-outbox Vercel project for that environment (keep the other entries), redeploy
  Outbox, set the same secret here as `OUTBOX_INGEST_SECRET`, redeploy this app, then **Send again**.

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
