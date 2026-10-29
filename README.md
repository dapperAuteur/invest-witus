# Invest.WitUS

A Python app for learning to invest by following one method at a time. You pick a method taught in
Learn.WitUS or ElementaryMBA, run it on paper first, and the app holds you to the method's rules, with a link
from every rule back to the lesson that teaches it.

This repository is two things at once:

1. **The reference app**, built the way the other WitUS ecosystem tools are built.
2. **The finished code for a follow-along tutorial.** Each tutorial chapter ends at a git tag (`v00`, `v01`,
   ...). The chapter text lives in [`docs/chapters/`](docs/chapters/) and the table of chapters in
   [`docs/CHAPTERS.md`](docs/CHAPTERS.md). Learners build their own copy in their own repository and use the
   tags here to check their work.

The user guide and the screen-recording scripts for each feature, written for the person who uses the app rather
than the person who builds it, live in [`docs/guide/`](docs/guide/README.md).
The commands the owner runs against production (migrations, the superuser, the cron by hand) are in `docs/05-operations.md`.

Information, not advice. Invest.WitUS is a learning tool. It does not recommend securities and is not open to
other users yet.

## Quick start

```sh
uv sync            # install Python 3.14 and the tools from uv.lock
uv run pytest      # run every chapter's checkpoint tests
uv run invest-witus --help

cp .env.example .env                                   # names only; DJANGO_DEBUG=1 for your laptop
uv run --env-file .env python manage.py migrate        # SQLite under data/private/ (gitignored)
uv run --env-file .env python manage.py createsuperuser  # the owner's admin login (chapter 05)
uv run --env-file .env python manage.py runserver      # the public site at http://127.0.0.1:8000/, the admin at /admin/
```

Every `manage.py` command takes `--env-file .env` since chapter 06: with `DJANGO_DEBUG` unset the settings
refuse to start without a `DJANGO_SECRET_KEY`, which is what a server wants and a laptop gets from `.env`.
`GET /healthz/` answers with the version and a database round trip.

## Deploying

The repository deploys to Vercel's Python runtime with Neon Postgres (chapter 06): `vercel.json` carries the
entry file and the ecosystem's Ignored Build Step, `wsgi.py` at the root is what Vercel loads, `STATIC_ROOT`
lets Vercel run `collectstatic` itself, and `.github/workflows/neon-preview-cleanup.yml` deletes preview
databases. Environment variable names are in `.env.example`; the dashboard steps are in
[chapter 06](docs/chapters/06-vercel-and-neon.md), sections 06.8 to 06.10. Migrations run from the owner's
machine against Neon's direct connection: `vercel env run -e production -- uv run python manage.py migrate --database direct`.
Vercel Web Analytics (chapter 06a) renders its two script tags only with `VERCEL=1` and `VERCEL_ANALYTICS=1`;
the script path comes from `VERCEL_ANALYTICS_SCRIPT_PATH` (the project's own value; `.env.example` labels the
fallback), and the dashboard steps are in [chapter 06a](docs/chapters/06a-vercel-web-analytics.md).

## Sign in with WitUS

Chapter 07 adds OpenID Connect sign-in against the ecosystem's identity provider, with no auth framework:
`httpx` for discovery, the token exchange and userinfo, `PyJWT` for the EdDSA signature (the provider signs
with one Ed25519 key; RS256 and `none` are refused). The client is off until `WITUS_OIDC_CLIENT_SECRET` is
set, so a copy of the app with no secret serves the public site with a stub page behind "Sign in". The
owner mints the secret in the witus repo and sets it on Vercel ([chapter 07](docs/chapters/07-sign-in-with-witus.md),
section 07.8); the other three names (`WITUS_OIDC_ISSUER`, `WITUS_OIDC_CLIENT_ID`, `WITUS_OIDC_SCOPES`) have
defaults listed in `.env.example`. People are keyed by the WitUS user id (`sub`), never by email; the owner's
admin superuser links to their WitUS account on its first sign-in by verified email. A learner's copy is not
registered with the provider; its checkpoint runs against a fake provider in `tests/test_ch07.py`.

## Prices and the nightly pull

Chapter 08 adds a `prices` app that keeps one closing price per symbol per day in the app's own table, so no
page ever asks a vendor. The pull runs two ways: `manage.py pull_prices [--since YYYY-MM-DD] [--symbols A,B]`
by hand, and `GET /api/cron/pull-prices/` once a day from Vercel's cron (`vercel.json`, `0 6 * * *` UTC), which
must carry `Authorization: Bearer <CRON_SECRET>` and answers 503 while the secret is unset. Both are idempotent:
a repeated run changes nothing, a vendor's correction replaces its row, and one symbol the vendor refuses is
recorded while the others continue. With `TIINGO_API_KEY` set the closes come from Tiingo's end-of-day endpoint
with the owner's own key (the free plan is for internal use only, so values are shown to the signed-in owner and
to no one else); without it the pull reads `<SYMBOL>.csv` files in chapter 02's format from `data/private/prices/`:

```sh
mkdir -p data/private/prices && cp data/sample/illustrative-daily-prices.csv data/private/prices/INDEX.csv
uv run --env-file .env python manage.py pull_prices --symbols INDEX --since 2026-09-22
```

The signed-in owner's accounts are listed at `/accounts/`, and each account's page values its latest statement
at the latest stored close, with the close's date and source beside every line. The owner's Tiingo key and the
cron secret are dashboard steps in [chapter 08](docs/chapters/08-prices-and-the-nightly-pull.md), section 08.10.

## The watch list

Chapter 09 adds a `watchlist` app: symbols the signed-in owner follows in an account without holding them. On
each account's page (`/accounts/<id>/`) a Watch list section lists them with the latest stored close and its
date ("no price yet" until the nightly pull has run), takes one symbol or a comma- or space-separated list in
one box and reports what was added, what was already there and what was refused, and removes a row with a
button (a POST, CSRF-checked; another owner's account is a 404). A symbol is trimmed and upper-cased and must be
letters, digits, a dot or a hyphen, one to twelve characters; anything else is refused with the reason and never
stored. Every watched symbol joins the nightly pull's universe inside chapter 08's budget, so `pull_prices` and
the cron fetch it with the held ones. There is no buy button: watching places no order. The walk-through is
[chapter 09](docs/chapters/09-the-watch-list.md), section 09.8.

Since 2026-10-29 each watched symbol has a history page (`/accounts/<id>/watch/<SYMBOL>/?days=30|90|365|5y|10y|all`,
or `?from=YYYY-MM-DD&to=YYYY-MM-DD`; over 1,000 days the chart is thinned for drawing and the table paged): a
server-drawn chart with a title, dollar and date axes, a key, split and dividend markers, the source and the
"as of" date, and the same days as a table; the adjusted close when every day in the range has one, else the
close, labelled. `/accounts/<id>/compare/?symbols=A,B,C&days=365` puts up to six of the account's watched or held
symbols on one chart, each rebased to 100 at its first day in the range. On those two pages only, a small script
(`prices/static/prices/chart.js`, no library) reads out the day nearest the pointer or the arrow keys; public
pages carry no script. The Watch list section can fetch history for several symbols in one press (ticked or typed), and the add form
can fetch the new symbols' history as it adds them. The statements
comparison in the admin notes a stored split between the two dates. How to use them:
[the user guide](docs/guide/using-invest-witus.md).

## The method engine and the three views

Chapter 10 puts the product's core on the web: a `methods` app whose `MethodPlan` row is chapter 03's `Plan`
for one account (the method's id, the amount, the buy window, the symbols, the start; one active plan per
account, an ended one kept as history) and whose `JournalEntry` row is chapter 03's `Entry` (a buy or a sell,
the symbol, the amount, the shares if known, a note). The rules are never copied into a row: `load_method`
reads the package's TOML file at request time, so every rule prints its text with the lesson that explains it,
or the words "lesson coming" when the file has no link yet. Chapter 03's `review()` runs unchanged against the
rows, and the signed-in owner reads it at `/accounts/<id>/method/` in three views of one context, named as the
research named them: A, The Plan and the Logbook (the home: the next window, the on-plan status with its
findings, the rules, the logbook); B, Method Console (rule checks with status, evidence and a lesson column,
every month of the plan done, missed or open with amounts and shares, the findings and the journal as tables);
C, The Lesson Lab (the rules read before the start form, then each rule's lesson and how often it was flagged).
The switch is three links, `?view=a|b|c`, remembered in the session; the page opens on C until a method runs and
on A after. Starting a method and logging an entry are POST forms behind the sign-in and the ownership check;
nothing on the page is a price, and no public page links it. The walk-through is
[chapter 10](docs/chapters/10-the-method-engine-and-the-three-views.md), section 10.10.

## Alpaca paper trading

Chapter 11 adds a `paper` app. An account linked to Alpaca's paper environment (the admin's **Alpaca** field;
paper accounts only, one per owner) gets "This month's buys" on its method page: the plan's amount split across
its symbols to the cent, the practice budget the app keeps beside Alpaca's own balance (which cannot be set), and
a **Confirm** button that sends one notional market day order per symbol to `https://paper-api.alpaca.markets`
with a `client_order_id` made of the account, the plan, the month and the symbol, so a second click or a retry
never buys twice. Each order goes into the journal at once; `manage.py sync_paper_orders`, the paper page's
"Check orders now" and a step in the nightly cron read the orders back and fill in the shares. With the market
closed the button reads "Confirm: queue for the open". The client is built for the paper host only and refuses
the live one, and the settings refuse to start if `APCA_API_BASE_URL` names another host; live trading is not
built. The keys are `ALPACA_PAPER_KEY_ID` and `ALPACA_PAPER_SECRET_KEY` (`.env.example`); without them nothing
calls Alpaca. Everything here is for the site owner's superuser only. The walk-through is
[chapter 11](docs/chapters/11-alpaca-paper-and-the-monthly-review.md), sections 11.9 and 11.10.

## The journal and the monthly close

Chapter 12 turns the journal into a logbook. An entry is a trade, a hold or a skip; a hold or a skip needs a
reason, and any entry may carry a state of mind (one of six words) and up to five tags. A skip with its reason
explains a month with no buy: the review keeps the finding, shows the reason beside it, and marks the rule
"explained". Each month whose buy window has closed gets a review, closed on its own page with three short answers
(what I did, what the rules said, what I'll do next month); a closed month's entries are read-only until the review
is reopened with a reason, and every close and reopen is kept. **Change or end this plan** on the method page writes
a new dated version with its reason, and each month is judged by the version in force then. On a paper account, a
month whose order ended unfilled offers **Place again**. The logbook at `/accounts/<id>/logbook/` filters by month,
kind and tag and exports CSV (the columns are in [chapter 12](docs/chapters/12-the-journal-and-closing-the-month.md),
decision 9). Migrations run from the merge workflow; the walk-through is chapter 12, section 12.10.

## The in-app reporter

Chapter 13 adds **Report a problem or ask a question** to the header and the footer of every page, signed in or
out: a kind (bug, feature or question), a message and the page, filled in from the referrer. Each report is saved
in a `reports` app first, then sent to WitUS Inbox as a signed request (`X-Witus-Source`, `X-Witus-Timestamp`,
and `X-Witus-Signature`, an HMAC-SHA256 of the timestamp and the exact body, per Inbox's
`docs/webhook-contract.md`); a new waitlist signup is copied the same way. A send that fails keeps its reason on
the row and is retried by the nightly cron, or by **Send again** in the admin. Five reports an hour per address
and per person, counted in the database; a honeypot; CSRF. The names are `INBOX_INGEST_URL`, `INBOX_SOURCE_SLUG`
and `INBOX_INGEST_SECRET` (`.env.example`); without them reports are kept in the admin and nothing is sent. The
walk-through is [chapter 13](docs/chapters/13-the-in-app-reporter.md), section 13.10.

## Post drafts to WitUS Outbox

Not a chapter. The site owner's **Draft a post** in the admin sends a short post (the launch, once, or a
milestone) to WitUS Outbox as a draft per platform, where the owner approves it; the app posts nothing itself and
no event writes a post. It follows Outbox's `examples/INTEGRATE.md` in Python: the same signature as Inbox (now
in `invest_witus_site/signing.py`), off unless `OUTBOX_TRIGGER_ENABLED` is exactly `true`, superuser only, and a
guard that refuses any amount, percentage, share count, cashtag or symbol from the owner's accounts. Saved first,
retried nightly and by **Send again**. Details: [doc 02, section 10](docs/02-ecosystem-integration.md) and the
[runbook](docs/05-operations.md).

## Credits

The project began from freeCodeCamp's course "Python Algorithmic Trading with SnapTrade, Massive, Alpaca"
(Carnes, 2026), which builds a momentum app in Django and invites learners to extend it. Invest.WitUS keeps
the idea (a rules-based method, run on a paper account) and builds its own stack and code.

## References

Carnes, B. (2026, September 29). *Python algorithmic trading with SnapTrade, Massive, Alpaca* [Video course
announcement]. freeCodeCamp. https://www.freecodecamp.org/news/python-algorithmic-trading-with-snaptrade-massive-alpaca/
