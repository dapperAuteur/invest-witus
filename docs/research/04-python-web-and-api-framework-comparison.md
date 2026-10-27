> Copied 2026-10-27 from the WitUS ecosystem's local planning notes, `gemini/witus/plans/future/invest-witus-research-2026-10-27/04-python-web-and-api-framework-comparison.md` (researched and written 2026-10-27). Paths to `plans/` files refer to those local notes and are not in this repo.

# Python web and API frameworks for Invest.WitUS: Django, Litestar, FastAPI and others (2026-10-27)

**Why this file:** BAM asked to consider Litestar against FastAPI, and other API tools, before the stack is fixed.
Read with `02-tutorial-and-python-dx.md` (the toolchain and tutorial structure) and the seed note.

**Sources, all read 2026-10-27:** PyPI's JSON API for each package (version, release date, Python requirement,
licence); the GitHub API for each repository (stars, open issues, last push, and the share of the last 12 months'
commits by the top author, from `/stats/contributors`); Vercel's Python runtime docs
(`/docs/functions/runtimes/python`); Litestar's README and docs tree; FastAPI's tutorial docs tree; Authlib's
`authlib/integrations` package listing. Stars and commit counts measure attention and activity, not quality.

## What the app needs from the framework

Pages a person uses (dashboard, method setup, journal, waitlist); an owner admin screen; a database with
migrations; Sign in with WitUS (OIDC, EdDSA id tokens); a small JSON API (signed events out to CentenarianOS, links
and later evidence to Learn.WitUS, maybe a read API); one scheduled route a day (Vercel Hobby cron: once a day,
plus or minus 59 minutes, no retries). Traffic: one owner, then a waitlist. And the overriding need: **a first
Python project for a learner**, followed through a public tutorial.

## The numbers

| Framework | Version (date) | Python | Licence | GitHub stars | Commits, last 12 months | Top author's share / top 3 | Authors with 5+ commits | Vercel |
|---|---|---|---|---|---|---|---|---|
| Django (+ django-ninja for the API) | 6.1.2 (2026-10-06); ninja 1.7.1 (2026-09-19) | 3.12+; ninja 3.7+ | BSD-3; ninja not stated on PyPI | 91,553; ninja 9,223 | 881; ninja 89 | 31% / 50%; ninja 52% / 65% | 26; ninja 3 | named preset |
| Django REST Framework | 3.18.3 (2026-10-06) | 3.10+ | BSD-3 | 30,218 | 150 | 38% / 77% | 4 | runs under Django |
| FastAPI | 0.162.0 (2026-10-23) | 3.10+ | MIT | 104,144 | 2,140 | 40% / 78% | 12 | named preset |
| Litestar | 2.25.0 (2026-10-18) | 3.8 to <4.0 | MIT | 8,532 | 272 | 38% / 67% | 7 | runs as ASGI (no named preset) |
| Starlette | 1.10.0 (2026-10-24) | 3.11+ | BSD-3 | 12,687 | not measured | not measured | not measured | runs as ASGI |
| Flask | 3.1.3 (2026-02-19) | 3.9+ | BSD-3 | 74,961 | 53 | 96% / 100% | 1 | named preset |
| Falcon | 4.4.0 (2026-09-30) | 3.9+ | Apache-2.0 | 9,809 | 99 | 73% / 82% | 2 | runs as ASGI or WSGI |
| Sanic | 25.12.1 (2026-05-31) | 3.10+ | MIT | 18,632 | not measured | not measured | not measured | last push 2026-07-29 |

Vercel: "Use the Python runtime to run ASGI ... and WSGI ... applications on Vercel"; "The Python framework presets
work with FastAPI, Flask, Django, and other Python web frameworks" (Vercel Python runtime docs).

## What each one gives you, and what you build yourself

| Need | Django + ninja | FastAPI | Litestar |
|---|---|---|---|
| Database and migrations | Built in (ORM, `makemigrations`) | Bring your own: SQLModel 0.0.48 or SQLAlchemy, plus Alembic | SQLAlchemy plugin (advanced-alchemy 1.12.0) or Piccolo; migrations through the plugin |
| Admin screen | Built in (Django admin) | Bring your own (a third-party admin package) | None in the framework; `litestar-fullstack` (618 stars) is a reference app, not an admin |
| HTML pages | Built-in templates; django-htmx | Jinja templates, documented | Templating and an htmx page in its docs |
| Validation | pydantic (ninja) | pydantic | msgspec by default; also pydantic v1 and v2, dataclasses, attrs |
| Auth | Sessions and users built in | Security tutorial; you assemble it | Guards, JWT and security backends in its docs |
| OIDC client (Sign in with WitUS) | Authlib `django_client` | Authlib `starlette_client` (FastAPI is built on Starlette) | No Authlib integration; Authlib's `httpx_client` plus your own callback route |
| API docs | OpenAPI from ninja | OpenAPI built in | OpenAPI 3.1 built in |
| Async | Optional | Async-first | Async-first |
| Learning material | The most: Django's own tutorial, Django Girls, and the freeCodeCamp course this app extends (which uses Django) | Very large; the official tutorial is long and good | Small; the docs are thorough but there are few beginner tutorials |

## Reading the evidence

- **Maintenance.** Django is the broadest-maintained project in the table (26 people with five or more commits in a
  year, no one above a third of commits). FastAPI is very active but concentrated (the top three wrote 78% of a
  year's commits). Litestar is genuinely community-run but small (seven regular authors). Flask is stable and
  almost one person's work this year (96%); Falcon is two people. django-ninja is the thinnest layer in the stack
  (three regular authors), which is acceptable only because it is thin: if it stalls, DRF or plain Django views
  replace it without touching the models.
- **Batteries.** For this app the expensive parts are the database, migrations, an admin, users and sessions.
  Django ships all of them. Litestar ships more than FastAPI (guards, JWT, DTOs, a database plugin) but no admin.
  FastAPI ships the least, by design: it is an API layer.
- **Speed and async** are where Litestar and FastAPI lead, and they do not matter here: one daily job and a few
  users.
- **Login.** Sign in with WitUS is OIDC. Django and FastAPI each have an Authlib integration; Litestar does not, so
  the login chapter would be hand-built (BAM has done that once already, in `wanderlearn-field-reporter`, with
  `jose` in TypeScript).

## Recommendation

**Keep Django, with django-ninja for the JSON API, for version 1 and the tutorial.** It is the shortest path to a
working, logged-in, database-backed app for a first Python project; the admin is free; the freeCodeCamp course
being extended is Django; and it is the healthiest project in the table.

**Where FastAPI or Litestar earn a place:** a later chapter or a small sibling service where an API framework is
the point, for example the public read API for other ecosystem apps or a signal service, so the tutorial teaches
both styles without making the first project carry two frameworks. Between the two for that role: FastAPI for the
larger community, its Vercel preset and its Authlib integration; Litestar for more built-ins and a broader
maintainer base relative to its size. Decide when that chapter is written, not now.

## Not measured

Starlette's and Sanic's commit concentration (not needed for the decision); runtime benchmarks (the app is not
throughput-bound, and benchmarks published by the projects themselves were not read).
