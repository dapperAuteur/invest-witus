# Invest.WitUS: tutorial roadmap (chapters and tags)

**Last updated:** 2026-10-27 · Companion to [`01-prd.md`](01-prd.md). The live chapter table, with links to each
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

Status: **tagged** means the tag exists on GitHub; **proposed** means the chapter is planned and may change.

| # | Title | Tag | Status | What it builds | New Python or web ideas |
|---|---|---|---|---|---|
| 00 | Set up your machine and your repository | `v00` | tagged | A uv project with one passing test, ruff and pyright wired in, pushed to the learner's own GitHub | uv, `pyproject.toml`, lockfile, pytest, ruff, pyright |
| 01 | Money in Python, and the math of a monthly plan | `v01` | tagged | `Decimal` money; buying a fixed amount at each price; the plan summary (shares, average cost, value) | `Decimal`, modules and packages, frozen dataclasses, type hints, `parametrize`, `raises` |
| 02 | Read a price history and give the app its first command | `v02` | tagged | Load daily prices from a CSV with clear errors; find the first trading day of each month; the `plan` CLI command | `csv`, `datetime`, iterators, a console entry point |
| 03 | Write the method down, and review yourself against it | `v03` | tagged | The method's rule block in TOML (`index_dca.toml`), the user's plan in TOML, a journal CSV, and `review`, which reports where the journal broke the method's rules, with a lesson link per rule ("lesson coming" until published) | `tomllib`, validation at the boundary, a rulebook that must match its checks |
| 04 | The first Django page: the public landing page | `v04` | proposed | Django project in the same repo; the landing page the domain will point at; the waitlist form (name and email, idempotent); the ecosystem footer, WitUS logo, privacy and terms pages; the header "Sign in" link and its smoke test | Django project and app, URLconf, views, templates, forms, static files, the Django test client |
| 05 | Models and the admin | `v05` | proposed | Accounts, securities, holding snapshots and holdings; manual entry from a statement, kept as dated snapshots; the Django admin as the first back office | Models, migrations, the ORM, `DecimalField`, admin, pytest-django |
| 06 | Deploy to Vercel and Neon | `v06` | proposed | The app live on a preview and on the production domain (BAM's choice), on Neon Postgres, with settings from env vars | Vercel Python runtime, `DATABASE_URL`, pydantic-settings, `collectstatic`, secrets handling |
| 07 | Sign in with WitUS | `v07` | proposed | OIDC sign-in, callback and sign-out against the ecosystem identity provider, EdDSA id tokens, users keyed by the WitUS user id; the landing page for everyone else | Authlib's Django client, sessions, middleware, `login_required` |
| 08 | Prices: a daily pull, a cron, a portfolio value | `v08` | proposed | End-of-day closes stored in the app's own table; one daily cron route guarded by `CRON_SECRET`, idempotent, recording its last run; holdings valued with the price date shown | httpx, django-ninja for the cron route, idempotent jobs, `vercel.json` crons |
| 09 | The watch list | `v09` | proposed | Watch lists per account with the latest stored close and its date; no buy button | Model relations, htmx partials (django-htmx) |
| 10 | The method engine in the app, and the three views | `v10` | proposed | Rule blocks loaded into the app; daily rule checks with evidence and lesson links; views A (Plan and Logbook), B (Operator console) and C (Lesson Lab) over the same data, with a saved per-user toggle | Service layer, template inheritance, accessible tables, per-user settings |
| 11 | Alpaca paper trading and the monthly review | `v11` | proposed | Paper orders staged and placed on confirm; orders and fills copied into the app; the practice budget; the monthly review that closes with a journal entry | A broker client behind a `Protocol`, pydantic models at the boundary, transactions |
| 12 | The journal | `v12` | proposed | The logbook: automatic and manual entries, mental and mistake tags, skips and exceptions with reasons, rule-following rate, CSV export | Aggregation queries, forms with validation, CSV writing |
| 13 | Report a bug, ask a question | `v13` | proposed | The in-app reporter stored locally and mirrored to WitUS Inbox with a signed request; retries in the daily job | HMAC signing with `hmac` and `hashlib`, background work without a worker |
| 14 | 12-1 momentum | `v14` | proposed | Method 2: rank the user's universe by 12-month return skipping the last month, first on a CSV, then on stored data; hold top N; monthly review; wash-sale warning | Sorting and windowing, maybe pandas, a second rule block on the same engine |
| 15 | Events to CentenarianOS, links to Learn | `v15` | proposed | Signed events to a new CentenarianOS receiver for closed reviews and contributions; lesson links checked against `CHAPTERS.md` | Outbound webhooks, deterministic event ids |
| 16 | The owner's dashboard: usage | `v16` | proposed | Owner-only `/admin/usage/`: sign-ins, active users, reviews on time or late or skipped, rule-following rate per method, the most-broken rule, cron health, hand-entered vendor costs; PostHog with the ecosystem's shared project (PRD 7.13) | Aggregation over every earlier table, owner gate, PostHog server-side events, an empty-state test |
| later | A sibling API service | proposed | proposed | A small FastAPI or Litestar service (for example a read API for other ecosystem apps), so the course teaches a second framework without the first project carrying two | ASGI, a second framework compared with Django |

## Open items for the roadmap

- The production domain (chapter 06) and the OIDC registration (chapter 07) need BAM's actions first; see
  [`02-ecosystem-integration.md`](02-ecosystem-integration.md), section 9.
- Whether chapter 04 moves the CLI code from `src/invest_witus/` under the Django project or keeps it as a library
  the Django app imports. Keeping it as a library honours the no-move rule; decide when chapter 04 is written.
- Lesson URLs: every chapter row in `CHAPTERS.md` says "lesson coming" until its Learn.WitUS lesson is published.
