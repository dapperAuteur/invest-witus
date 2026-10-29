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

## Credits

The project began from freeCodeCamp's course "Python Algorithmic Trading with SnapTrade, Massive, Alpaca"
(Carnes, 2026), which builds a momentum app in Django and invites learners to extend it. Invest.WitUS keeps
the idea (a rules-based method, run on a paper account) and builds its own stack and code.

## References

Carnes, B. (2026, September 29). *Python algorithmic trading with SnapTrade, Massive, Alpaca* [Video course
announcement]. freeCodeCamp. https://www.freecodecamp.org/news/python-algorithmic-trading-with-snaptrade-massive-alpaca/
