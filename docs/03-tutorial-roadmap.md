# Invest.WitUS: tutorial roadmap (chapters and tags)

**Last updated:** 2026-10-28 (chapter 07 built) · Companion to [`01-prd.md`](01-prd.md). The live chapter table, with links to each
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
| 08 | Prices: a daily pull, a cron, a portfolio value | `v08` | proposed | End-of-day closes stored in the app's own table; one daily cron route guarded by `CRON_SECRET`, idempotent, recording its last run; holdings valued with the price date shown | httpx, django-ninja for the cron route, idempotent jobs, `vercel.json` crons |
| 09 | The watch list | `v09` | proposed | Watch lists per account with the latest stored close and its date; no buy button | Model relations, htmx partials (django-htmx) |
| 10 | The method engine in the app, and the three views | `v10` | proposed | Rule blocks loaded into the app; daily rule checks with evidence and lesson links; views A (Plan and Logbook), B (Operator console) and C (Lesson Lab) over the same data, with a saved per-user toggle | Service layer, template inheritance, accessible tables, per-user settings |
| 11 | Alpaca paper trading and the monthly review | `v11` | proposed | Paper orders staged and placed on confirm; orders and fills copied into the app; the practice budget; the monthly review that closes with a journal entry | A broker client behind a `Protocol`, pydantic models at the boundary, transactions |
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
  `WITUS_OIDC_CLIENT_SECRET`, the migration, a redeploy, one sign-in).
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
