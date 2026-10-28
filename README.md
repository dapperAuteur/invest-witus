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

## Credits

The project began from freeCodeCamp's course "Python Algorithmic Trading with SnapTrade, Massive, Alpaca"
(Carnes, 2026), which builds a momentum app in Django and invites learners to extend it. Invest.WitUS keeps
the idea (a rules-based method, run on a paper account) and builds its own stack and code.

## References

Carnes, B. (2026, September 29). *Python algorithmic trading with SnapTrade, Massive, Alpaca* [Video course
announcement]. freeCodeCamp. https://www.freecodecamp.org/news/python-algorithmic-trading-with-snaptrade-massive-alpaca/
