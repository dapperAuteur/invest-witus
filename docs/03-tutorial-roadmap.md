# Invest.WitUS: tutorial roadmap (chapters and tags)

**Last updated:** 2026-10-29 (chapter 11 built) · Companion to [`01-prd.md`](01-prd.md). The live chapter table, with links to each
chapter's text and its Learn.WitUS lesson, is [`CHAPTERS.md`](CHAPTERS.md); this file is the plan for the chapters
not yet written.

## How chapters work (from research 02)

- **One chapter = one annotated tag = one Learn.WitUS lesson.** Tags are `vNN`, two digits, so they sort in
  chapter order. A fix to a published chapter gets a new tag (`vNN.1`); tags never move.
- **Every chapter starts red and ends green.** Its first step copies in `tests/test_chNN.py`; the chapter ends
  when that file passes with `ruff check`, `ruff format --check` and `pyright` clean.
- **Each chapter page links** Browse (`tree/vNN`), Diff (`compare/vNN-1...vNN`) and Zip (`archive/vNN.zip`), and
  says which tag and tool versions it was written against.
- **Later chapters add files; they never move or rename earlier ones,** so every diff stays readable.
- **Learners build their own repository** and use the tags here to check their work; they never need to clone
  this one.
- **No real symbols as picks.** Samples use the placeholder `INDEX` and illustrative prices.

## Chapters

Status: **tagged** means the tag exists on GitHub's `main`; **built** means the chapter text, code and tag exist on a
branch awaiting merge; **proposed** means the chapter is planned and may change.

| # | Title | Tag | Status | What it builds | New Python or web ideas |
|---|---|---|---|---|---|
| 00 | Set up your machine and your repository | `v00` | tagged | A uv project with one passing test, ruff and pyright wired in, pushed to the learner's own GitHub | uv, `pyproject.toml`, lockfile, pytest, ruff, pyright |
| 01 | Money in Python, and the math of a monthly plan | `v01` | tagged | `Decimal` money; buying a fixed amount at each price; the plan summary (shares, average cost, value) | `Decimal`, modules and packages, frozen dataclasses, type hints, `parametrize`, `raises` |
| 02 | Read a price history and give the app its first command | `v02` | tagged | Load daily prices from a CSV with clear errors; find the first trading day of each month; the `plan` CLI command | `csv`, `datetime`, iterators, a console entry point |
| 03 | Write the method down, and review yourself against it | `v03` | tagged | The method's rule block in TOML (`index_dca.toml`), the user's plan in TOML, a journal CSV, and `review`, which reports where the journal broke the method's rules, with a lesson link per rule ("lesson coming" until published) | `tomllib`, validation at the boundary, a rulebook that must match its checks |
| 04 | The first Django page: the public landing page | `v04` | built | Django project in the same repo; the landing page the domain will point at; the waitlist form (name and email, idempotent); the ecosystem footer, WitUS logo, privacy, terms and FAQ pages (the FAQ text is `docs/site/faq.md`, rendered at `/faq/`); the header "Sign in" link and its smoke test | Django project and app, URLconf, views, templates, forms, static files, the Django test client |
| 05 | Models and the admin | `v05` | built | The Django admin at `/admin/` as the owner's back office (auth, sessions, messages installed; one superuser); the waitlist listed with a waiting or approved status and an approve action; accounts, holdings (one row per account and symbol, kind set by the owner), dated statement snapshots and their lines in exact `Decimal` (shares to six places, money to the cent, floats refused); the change between any two statements per symbol on an admin page; no prices, no values, no CSV import, nothing public | Models, migrations, `DecimalField`, `TextChoices`, `UniqueConstraint`, `on_delete`, the admin (inlines, actions, a custom page), template filters, pytest-django's `admin_client`, `conftest.py` |
| 06 | Vercel and Neon: the app a server can run | `v06` | built | One settings file for the laptop (SQLite) and Vercel (Neon Postgres through `DATABASE_URL`, a `direct` alias from `DATABASE_URL_UNPOOLED` for migrations); the secret key required with debug off; Secure cookies, the proxy header and SSL redirect on Vercel only; host names from env plus Vercel's own; `STATIC_ROOT` for Vercel's automatic `collectstatic`; `/healthz/`; `manage.py` and a root `wsgi.py` that put `src/` on the path; `vercel.json` with the ecosystem's Ignored Build Step; the Neon preview cleanup workflow; the dashboard steps for the project, Neon, the migration, the non-interactive superuser and the domain (the deploy itself is the owner's: tasks 03 to 05) | Vercel Python runtime and how it finds Django, `DATABASE_URL` parsing with `urllib.parse`, `ImproperlyConfigured`, Secure cookies and `X-Forwarded-Proto`, `collectstatic`, `tomllib`, re-importing a module under `monkeypatch`, `subprocess` tests |
| 06a | Vercel Web Analytics: page views, switched on per environment | `v06a` | built | Vercel's plain-HTML snippet (two script tags, no package) at the end of the base template, rendered only with `VERCEL=1` and `VERCEL_ANALYTICS=1` so Production and Preview can differ and `runserver` never emits it; the script path from `VERCEL_ANALYTICS_SCRIPT_PATH` with `/_vercel/insights/script.js` as a labeled fallback and a non-path refused; the privacy page's dated Analytics section; the dashboard steps (Enable, the path, the variables, Redeploy, the `view` request); the ecosystem's PostHog standard stays a later chapter | A two-condition switch, a context processor read per request, `defer` and a call queue, the pytest-django `settings` fixture, reading a rendered page for tag order |
| 07 | Sign in with WitUS | `v07` | built | An `accounts` app with an OpenID Connect client written out (httpx for discovery, the token exchange and userinfo; PyJWT for the EdDSA signature, RS256 and `none` refused): `/auth/witus/login/` with PKCE S256, `state` and `nonce` in the session; `/auth/witus/callback/` checking state, `iss`, `aud`, `exp` and `nonce`, then `WitusIdentity` keyed by `sub` (the owner's superuser linked once by verified email, anyone else a new non-staff user) and `Account.witus_user_id` filled; `/auth/witus/logout/` (POST) ending the session and the provider's; the header's "Sign out" and name, "Signed in as" on the home page; off without `WITUS_OIDC_CLIENT_SECRET`, so the stub stays; the dashboard steps are the owner's (task 07) | httpx, PyJWT and JWKS, PKCE, `state` and `nonce`, Django sessions, `login()` and `logout()`, a context processor, a fake provider through httpx's `MockTransport`, a POST-only view |
| 08 | Prices and the nightly pull | `v08` | built | A `prices` app: `DailyClose`, one row per symbol per day (unique on symbol and date, six places, the source and when it was fetched), written by an idempotent upsert (a rerun changes nothing, a corrected close replaces its row); a `PriceSource` Protocol with `TiingoEod` (httpx, the token in the `Authorization` header, JSON decoded with `parse_float=Decimal`) and `CsvPrices` (chapter 02's files, for a laptop and the tests), chosen by `TIINGO_API_KEY`; the symbol universe (every held symbol but cash, plus chapter 09's `watch_symbols()` placeholder); `manage.py pull_prices [--since] [--symbols]`, which records a vendor's refusal per symbol and goes on, stops on a 429, keeps inside the free plan's 50 requests an hour and pauses a second between symbols; `GET /api/cron/pull-prices/` behind `CRON_SECRET` as a bearer (503 unset, 403 wrong, JSON counts for the last seven days), scheduled in `vercel.json` at `0 6 * * *` UTC; the owner's pages `/accounts/` and `/accounts/<id>/` behind `login_required` and an ownership check, each line valued at the latest close with its date and source, cash at face, stale after five days, "no price yet" otherwise; no public page shows a price or links the pages; the owner's Tiingo key and the cron secret are task 09 | A `Protocol` as a seam, idempotent jobs and upserts, `parse_float=Decimal`, a management command with arguments, `vercel.json` crons and Vercel's Hobby rules, a bearer compared in constant time, `login_required` and `LOGIN_URL`, `values().annotate(Max())`, a fake vendor from JSON fixtures, a template filter |
| 09 | The watch list | `v09` | built | A `watchlist` app: `WatchItem(account, symbol, note, added_at)`, unique on the account and symbol; the symbol rule (trimmed, upper-cased; letters, digits, a dot and a hyphen; one to twelve characters) in one function used by a field validator, the form's parser and `save()`; on the signed-in owner's account page a Watch list section with the latest stored close and its date per row ("no price yet" and "prices arrive after the nightly pull" until a run has stored one), an add box that takes one symbol or many and reports added, already there and refused, a remove button per row (POST, CSRF, another owner's account a 404); `watch_symbols()` filled so every watched symbol joins the pull's universe inside chapter 08's budget; Django's messages printed by the base template; the admin registration; no buy button; the owner's migration and first symbols are task 10 | A rule function reused as a validator, in a form's `clean_<field>()` and in `save()`; `re.fullmatch`; `get_or_create`; the messages framework; `require_POST` with `login_required`; an include and a context builder across apps without an import cycle; a test reader that keeps two tables apart |
| 10 | The method engine in the app, and the three views | `v10` | built | A `methods` app: `MethodPlan(account, method_id, amount, buy_window_days, symbols, started_on, active)`, one active per account by a partial unique constraint, round-tripping to chapter 03's `Plan`; `JournalEntry(account, date, action from chapter 03's enum, symbol, amount, shares optional, note)` round-tripping to `Entry`; the rules read from the package's TOML at request time through `load_method`, never copied into rows, each with its lesson link or "lesson coming"; `available_methods()` added to the library so the start form reads the list; chapter 03's `review()` run unchanged behind `methods/engine.py`, which arranges it per rule (status and evidence in words), per month (done, missed or open, with amounts and shares) and as the next window; the signed-in page `/accounts/<id>/method/` in three views, A (The Plan and the Logbook, the home), B (Method Console, read-only tables) and C (The Lesson Lab, the rules read before the start form), one context, `?view=` remembered in the session, C by default without a plan and A with one; the start and log forms (POST, CSRF, another owner's account a 404); one Method line on the account page; no price on the method page; the owner's migration and first method are task 13 | A row that is a value, with converters; `UniqueConstraint` with a `condition` and a `CheckConstraint`; a `ModelForm`; a `ChoiceField` with callable choices; `request.session`; `{% include %}` with a variable name and `with`; `aria-current`; a `Protocol` in a test |
| 11 | Alpaca paper trading and the monthly review | `v11` | built | A `paper` app: an httpx client for Alpaca's paper Trading API (account, positions, clock, a notional market day buy, an order by id or by `client_order_id`) built for `paper-api.alpaca.markets` only, the live host refused by the client and a live `APCA_API_BASE_URL` refused by the settings, keys from `ALPACA_PAPER_KEY_ID` and `ALPACA_PAPER_SECRET_KEY`, a timeout on every call and typed errors with Alpaca's words; `Account.alpaca` (paper only, one per owner) and `MethodPlan.practice_budget`; on a linked account's method page "This month's buys", the plan's amount split to the cent, the budget spent and left, and Confirm (a one-symbol plan, inside the window, within the budget), which places each buy once by a deterministic `client_order_id` and writes a journal entry per order; a closed market said and the order queued for the open; `PaperOrder` rows; `manage.py sync_paper_orders`, a "Check orders now" button and a step in the nightly cron that fill in the journal; the paper page with Alpaca's cash and positions beside the budget and the line about live trading; site owner only; the owner's merge, link, budget and first Confirm are task 16 | httpx with typed exceptions, a constructor that refuses a host, idempotency keys, `select_for_update` and a transaction around a network call, `violation_error_message`, a fake vendor behind `MockTransport` |
| 12 | The journal | `v12` | proposed | The logbook: automatic and manual entries, mental and mistake tags, skips and exceptions with reasons, rule-following rate, CSV export | Aggregation queries, forms with validation, CSV writing |
| 13 | Report a bug, ask a question | `v13` | proposed | The in-app reporter stored locally and mirrored to WitUS Inbox with a signed request; retries in the daily job | HMAC signing with `hmac` and `hashlib`, background work without a worker |
| 14 | 12-1 momentum | `v14` | proposed | Method 2: rank the user's universe by 12-month return skipping the last month, first on a CSV, then on stored data; hold top N; monthly review; wash-sale warning | Sorting and windowing, maybe pandas, a second rule block on the same engine |
| 15 | Events to CentenarianOS, links to Learn | `v15` | proposed | Signed events to a new CentenarianOS receiver for closed reviews and contributions; lesson links checked against `CHAPTERS.md` | Outbound webhooks, deterministic event ids |
| later | A sibling API service | proposed | proposed | A small FastAPI or Litestar service (for example a read API for other ecosystem apps), so the course teaches a second framework without the first project carrying two | ASGI, a second framework compared with Django |

## Open items for the roadmap

- The production domain (chapter 06) and the OIDC registration (chapter 07) need BAM's actions first; see
  [`02-ecosystem-integration.md`](02-ecosystem-integration.md), section 9. Chapter 06's code is built and the
  deploy is the owner's: tasks 03 (domain), 04 (Vercel project, Neon, first deploy, superuser) and 05 (the
  cleanup workflow's variable and secret) in `plans/user-tasks/`. Chapter 07's client is built and off until
  the secret is set: the IdP side was done on 2026-10-28; task 07 holds the rest (the invest project's
  `WITUS_OIDC_CLIENT_SECRET`, the migration, a redeploy, one sign-in; done 2026-10-28). Chapter 08's pull is
  built; `TIINGO_API_KEY` and `CRON_SECRET` were set on the Vercel project on 2026-10-28, and task 09 holds
  the merge, the migration and one run by hand. Chapter 09's watch list is built on `feat/tutorial-ch09`
  (tag `v09`), starting from chapter 08's merge; task 10 holds its merge, its migration and the first symbols.
  Chapter 10's method engine is built on `feat/tutorial-ch10` (tag `v10`), starting from chapter 09's bundle
  merge; task 13 holds its merge, its migration and the first method. Chapter 11's paper trading is built on
  `feat/tutorial-ch11` (tag `v11`), starting from `main` after the migrate-on-merge workflow; the owner's paper
  keys were set on Vercel before it; task 16 holds the merge (the workflow migrates), the link, the budget and
  the first Confirm.
- Decided in chapter 11: Alpaca's pages as read on 2026-10-29 (decisions log, row 94); a `paper` app with the
  client written out in httpx, no pydantic and no `Protocol`, the host a constant and the live host refused twice
  (row 95); `Account.alpaca`, paper only and one per owner, site owner only (row 96); the practice budget on the
  plan, spent from the journal (row 97); this month's buys split to the cent, Confirm for a one-symbol plan, the
  refusals in words and checked again on the server, the box on every view (row 98); placed once by
  `client_order_id`, a unique row, a lock, a look-first retry and Alpaca's 422 read back (row 99); one journal
  entry per order dated the day of the click, fixed by the sync, removed for an order that ended unfilled, the
  closed market and its queue (row 100); the sync as a command, a button and a cron step that leaves chapter
  08's body alone without keys (row 101); the deferred list (row 102).
- Decided in chapter 10: a `methods` app that wraps the chapter 03 engine and reads the rules from the
  package's TOML at request time, with one function added to the library (decisions log, row 86); the plan row
  as chapter 03's `Plan` with symbols as text and one active plan per account by a partial unique constraint,
  ending a plan an admin step until chapter 12 (row 87); the journal row as `Entry` plus optional shares and a
  note, the action's choices from the enum (row 88); `review()` unchanged behind an engine module that arranges
  per rule, per month and as the next action, `?through=` as the CLI's (row 89); three templates over one
  context with a switch of plain links kept in the session, C without a plan and A with one, the PRD's
  per-user preference and header placement deferred (row 90); what each view leaves out, the order queue, the
  envelope chart, the promotion checklist, Confirm and Skip, rules switching on one at a time (row 91); no price
  on the method page (row 92); the deferred list (row 93).
- Decided in chapter 09: a separate `watchlist` app with an import graph that has no cycle (decisions log,
  row 79); one list per account and no "change since added" column, which is derivable later (row 80); the
  symbol rule, twelve characters of letters, digits, a dot and a hyphen (row 81); a refused token beside a valid
  one does not block it, and a submission with nothing valid is a form error (row 82); plain forms, a redirect
  and Django's messages instead of the django-htmx partials this row had proposed (row 83).
- Decided in chapter 08: no django-ninja for one GET route (a plain view; decisions log, row 76); Tiingo's
  end-of-day endpoint through the owner's own key with a CSV source for laptops, Alpaca's positions left to
  chapter 11 (rows 70 to 71); the cron at 06:00 UTC, after Tiingo's mutual fund NAV time in both halves of the
  year, with a seven-day window because Hobby cron has no retries and may miss or repeat a run (row 72); one
  close per symbol per day, the source as a column, no `Security` table yet (row 73); the owner's pages in the
  holdings app at `/accounts/`, behind `login_required`, with the admin's Statements page untouched (row 77).
- Decided in chapter 07: httpx and PyJWT, not Authlib (decisions log, rows 62 to 69); the discovery document
  lives under `/api/idp/`, not at the spec's path; users keyed by `sub` in a one-to-one `WitusIdentity`, the
  owner linked once by verified email; a learner's copy cannot register with the ecosystem's provider, so the
  chapter's fake provider is its checkpoint and exercise 2 opens the client to a provider of the learner's own.
- Decided in chapter 06a: Vercel Web Analytics on the public pages now, switched on per environment, with the
  script path from a variable and a labeled fallback (decisions log, row 61). The ecosystem's analytics standard
  stays PostHog (witus plan 26); it is a later chapter, after sign-in, and is not replaced.
- Decided in chapter 06: settings read `os.environ` directly with a forty-line `DATABASE_URL` parser; the
  PRD's pydantic-settings was not needed (decisions log, row 53). Migrations run by hand against Neon's direct
  connection, never at build (row 54).
- Decided in chapter 05: `Account.kind` is one field (brokerage, retirement, paper) where PRD 7.3 sketches a kind (manual, Alpaca paper, Alpaca live) and a type (taxable, retirement); chapter 11 adds the broker environment when Alpaca arrives (decisions log, row 45). The WitUS user id lives on the account as a nullable field until chapter 07 fills it; no custom user model (row 43).
- Decided in chapter 04: the CLI code stays a library in `src/invest_witus/` and the Django project lives beside it in
  `src/invest_witus_site/` (decisions log, row 34). Nothing from chapters 01 to 03 moved.
- Lesson URLs: every chapter row in `CHAPTERS.md` says "lesson coming" until its Learn.WitUS lesson is published.
