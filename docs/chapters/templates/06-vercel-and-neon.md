# Chapter 06: Vercel and Neon: the app a server can run

**Starts from:** tag `v05`. **Ends at:** tag `v06`.
**Written against:** Python 3.14.10, uv 0.13.6, Django 5.2.18, psycopg 3.3.6, Vercel CLI 62.2.0, and the
Vercel and Neon documentation as read on October 28, 2026. Dashboards change; every dashboard name below has
its source in the references, and when the page and this text disagree, the page wins.
**Goal:** one settings file runs the app on your laptop with SQLite and on Vercel with Neon Postgres. It reads
everything that differs from the environment, refuses to start without what a server needs, and answers
`/healthz/` with its version and a database round trip. The code deploys nothing by itself; the last three
sections are the steps you take in the two dashboards.
**Time:** 2 to 3 hours for the code and tests, then 30 to 60 minutes in Vercel and Neon.

The listings in this chapter are not typed in by hand. `scripts/render_chapter.py` pastes the real files from
tag `v06` into the chapter text, so what you read and what the tests run are the same bytes.

## What you will learn

- **Settings that fail closed:** a secret key that must be set, a debug switch that must be off, and host
  names that must be listed, each refused with a message instead of a quiet default.
- **A `DATABASE_URL` parser:** forty lines that turn Neon's connection string into Django's `DATABASES`
  dictionary, and refuse anything else.
- **What a proxy changes:** why Django must be told that Vercel ends HTTPS in front of it, what a Secure
  cookie is, and why the CSRF check cares about the request's origin.
- **How Vercel runs Django:** it finds `manage.py`, reads your settings, turns `WSGI_APPLICATION` into a file
  path, installs your dependencies but not your project, and runs `collectstatic` for you. Each of those facts
  decides one line of code in this chapter.
- **A health route:** JSON, 200 or 503, with nothing in it a stranger should not read.
- **Two new kinds of test:** importing the settings module again with a controlled environment, and running
  `manage.py` in a separate process to stand in for a server.
- **The dashboards:** which values you type, and which values you copy from the page in front of you.

## Before the code: what a server changes

The app has run on your laptop since chapter 04, with a SQLite file under `data/private/` and Django's
`runserver`. A server differs in four ways, and each one is a line in `settings.py` by the end of the chapter:

| On your laptop | On Vercel | What the settings do about it |
|---|---|---|
| One process, your files, read and write | A function with a read-only filesystem, started fresh and often | The database is Postgres, named by `DATABASE_URL`; nothing is written to disk |
| `http://127.0.0.1:8000`, no proxy | HTTPS at Vercel's edge, plain HTTP from the edge to Django, with a header saying so | Trust that header on Vercel only; mark cookies Secure; list the host names |
| A dev-only secret key is fine | Anyone with the key can forge the admin's session | Refuse to start without `DJANGO_SECRET_KEY` |
| `runserver` serves CSS and images while debug is on | Nothing serves them | `collectstatic` into one folder, which Vercel serves from its CDN |

Two rules from the WitUS ecosystem shape the deploy files (WitUS, 2026):

- **Only production and `bundle/*` branches build on Vercel.** Every other push is skipped by an Ignored
  Build Step, so previews land where the owner reviews bundled work and nowhere else. The same command every
  ecosystem project uses goes into `vercel.json` here.
- **No preview may leave a paid resource behind.** The Neon integration makes a database branch per preview
  deployment and only deletes it when the deployment is deleted, which can be never. Every Neon repository
  carries the same GitHub workflow that deletes a `preview/<branch>` database once its git branch is merged or
  gone. This chapter copies it in unchanged.

And the chapter's own rule, from the authoritative-values rule in `CLAUDE.md`: a value owned by Vercel or
Neon (the DNS record, the connection string, the project id, a production URL) is copied from the page that
owns it, never typed from memory. The text says "copy" where that applies.

## Steps

### 06.1 The driver, the test settings, and the tests

Listing 06-1, Terminal:

```sh
uv add "psycopg[binary]>=3.2"
```

psycopg 3 is the PostgreSQL driver Django's documentation recommends (3.1.8 or newer; psycopg2 "is likely to be
deprecated") and the one Neon's Django guide installs, with the `binary` extra so no C compiler is needed
(Django Software Foundation, n.d.-b; Neon, n.d.-b). Neon's guide also explains why not psycopg2: older builds
of its libpq do not send the server name during the TLS handshake, and Neon's pooler needs it.

Two settings modules from now on. The real one is the next section's work; this one is for the tests:

Listing 06-2, Filename: `tests/settings.py`:

{{file:tests/settings.py}}

Here is the problem it solves. The settings file you are about to write refuses to start without a secret key
whenever debug is off, and the tests should run with debug off, so that the rules a server gets (Secure
cookies and the rest) are the rules the tests exercise. Something has to hand the suite a key, and
`conftest.py` is too late: pytest-django imports the settings module before any conftest loads. The settings
module itself is the one place that runs first. This module sets a key that is plainly not a secret and then
imports everything from the real settings, so the tests see the real values with one addition.

Listing 06-3, Filename: `pyproject.toml`:

{{file:pyproject.toml}}

Two lines changed: pytest-django's `DJANGO_SETTINGS_MODULE` now names `tests.settings`, and pyright's
`include` lists `wsgi.py`, a file written in 06.5.

Listing 06-4, Filename: `tests/test_ch06.py`:

{{file:tests/test_ch06.py}}

Read it before you run it. Things to notice:

- **`fresh_settings`** removes every `DJANGO_*`, `VERCEL*` and `DATABASE_URL*` variable, sets exactly the ones
  a test names, drops the settings module from `sys.modules` and imports it again. The module runs top to
  bottom with that environment, so a test can assert what a server would get, or catch the refusal a server
  would hit. pytest's `monkeypatch` undoes all of it afterwards, and Django's own settings object, which was
  loaded once at startup, is never touched.
- **`manage`** runs `manage.py` in a separate process whose entire environment is the dictionary given. It
  stands in for a server. One test runs Django's own `check --deploy` that way; another strips `src/` from
  the import path first and loads both `manage.py` and `wsgi.py`, which is how Vercel sees the repository
  (06.5 explains why).
- **`mock.patch.object(BaseDatabaseWrapper, "cursor", ...)`** makes every database cursor raise for the
  length of one `with` block, which is how the 503 case is tested without a broken database.
- **`settings.STATIC_ROOT = tmp_path / "static"`** uses pytest-django's `settings` fixture and pytest's
  `tmp_path`, so `collectstatic` writes into a folder that disappears after the test.
- **`NEON_SHAPED`** is the shape of a Neon connection string with a made-up host. The test does not connect to
  anything; it checks that the parser reads the shape.

Run it:

Listing 06-5, Terminal:

```sh
uv run pytest tests/test_ch06.py
```

```text
ModuleNotFoundError: No module named 'invest_witus_site.database'
```

Red first, at import time: the test file imports the parser before anything else.

### 06.2 The database from a URL

Neon hands out one line, `postgresql://user:password@host/name?sslmode=require&channel_binding=require`, and
Django wants a dictionary with `ENGINE`, `NAME`, `USER`, `PASSWORD`, `HOST`, `PORT` and `OPTIONS`. The package
`dj-database-url` does this conversion. Forty lines do it too, and they keep the dependency list short and the
rules where you can read them:

Listing 06-6, Filename: `src/invest_witus_site/database.py`:

{{file:src/invest_witus_site/database.py}}

What the lines decide:

- **Two shapes, nothing else.** `postgres://` and `postgresql://` for Neon; `sqlite:///` for a laptop or a
  test. A third scheme, a missing host or database name, an unknown query option: each is a `ValueError`
  with a message that says what was wrong. A typo in a dashboard then fails when the function starts, where
  the log shows it, rather than at the first request.
- **`urlsplit` and `unquote`** come from the standard library. A password with `@` or `/` in it is
  percent-escaped in a URL, and `unquote` puts it back.
- **`sslmode` defaults to `require`,** the value in Neon's Django guide, and a URL may say otherwise; Neon's
  own strings also carry `channel_binding=require`, which the parser passes through (Neon, n.d.-b, n.d.-a).
- **The three extra keys** are for Neon's pooled connection. `DATABASE_URL` goes through PgBouncer in
  transaction mode, which cannot hold a server-side cursor across statements, so
  `DISABLE_SERVER_SIDE_CURSORS` is on (Django Software Foundation, n.d.-b; Neon, n.d.-c). Neon suspends an
  idle compute after five minutes; a connection kept for a minute with `CONN_HEALTH_CHECKS` is reused while
  it is alive and replaced, without failing a request, when it is not (Neon, n.d.-b).
- **A SQLite path is relative to the repository** unless it starts with `/`, which is what lets the tests
  point a database at a temporary folder.

### 06.3 The settings a server can run

Listing 06-7, Filename: `src/invest_witus_site/settings.py`:

{{file:src/invest_witus_site/settings.py}}

Read it top to bottom; it is the chapter. Block by block:

- **`env_list`** turns a comma-separated variable into a list and drops blanks, so `"a, b,"` is `["a", "b"]`.
- **`DEBUG` and `ON_VERCEL`.** Debug is on only with `DJANGO_DEBUG=1`, as before. `VERCEL=1` is one of the
  variables Vercel sets on its build machine and inside the function (Vercel, 2026h). The settings read it for
  one question, whether a proxy that ends HTTPS sits in front of Django, and refuse the combination of debug
  and Vercel outright: a debug page shows settings and source code to whoever triggers an error.
- **`secret_key`.** A key from the environment, or, with debug on, the labeled dev-only key from chapter 04.
  With debug off and no key, `ImproperlyConfigured` carries the command that makes one. Django's deployment
  checklist puts it first: "The secret key must be a large random value and it must be kept secret" (Django
  Software Foundation, n.d.-a). The practical consequence for your laptop: every `manage.py` command now runs
  with `--env-file .env`, where `DJANGO_DEBUG=1` lives. The tests have their own key (06.1).
- **`ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`.** With debug off, Django answers only the host names listed,
  and a request for any other name gets a 400 (Django Software Foundation, n.d.-a). Production lists
  `invest.witus.online` by hand. The names Vercel assigns a deployment, `VERCEL_URL`, `VERCEL_BRANCH_URL` and
  `VERCEL_PROJECT_PRODUCTION_URL`, are read from Vercel's variables (Vercel, 2026h), so a preview deployment
  answers on its own `*.vercel.app` name without anyone editing a list. The CSRF check compares a form POST's
  `Origin` header with the request's own origin; `CSRF_TRUSTED_ORIGINS` lists the HTTPS origins so that check
  passes on its own terms (Django Software Foundation, n.d.-c). `dict.fromkeys` keeps the order and drops a
  name that arrived twice.
- **`WSGI_APPLICATION = "wsgi.application"`.** It named `invest_witus_site.wsgi.application` until now. 06.5
  explains the change; the short version is that Vercel turns this string into a file path beside
  `manage.py`.
- **`DATABASES`.** No `DATABASE_URL` means the SQLite file from chapter 04, in the folder git ignores; the
  folder is created only in that case, and quietly not created on a read-only filesystem. On Vercel the Neon
  integration sets two variables (Neon, n.d.-d): `DATABASE_URL`, the pooled connection the app uses, and
  `DATABASE_URL_UNPOOLED`, the direct one. Neon's advice is that schema migrations take the direct connection
  (Neon, n.d.-c), so when the second variable exists it becomes a second alias, `direct`, and the owner runs
  `migrate --database direct`. Nothing routes to it on its own.
- **`STATIC_ROOT`.** The one folder `collectstatic` fills with every app's static files, the admin's
  included. Vercel's Django page: "When your Django project has `STATIC_ROOT` configured, Vercel automatically
  runs `collectstatic` during the build and serves the collected files from the Vercel CDN" at `STATIC_URL`
  (Vercel, 2026c). That sentence is why there is no WhiteNoise and no build script in this chapter: the page
  says WhiteNoise "is only active when running locally with `vercel dev`". The folder is gitignored.
- **The HTTPS block.** Vercel ends TLS at its CDN and calls the function over plain HTTP with
  `X-Forwarded-Proto: https` (Vercel, 2025). Django does not believe such a header by default, because a
  client could send one; `SECURE_PROXY_SSL_HEADER` tells it to, and the settings reference warns to set it
  only when "Your Django app is behind a proxy" that "strips the `X-Forwarded-Proto` header from all incoming
  requests" and sets its own (Django Software Foundation, n.d.-c). That is Vercel's situation and not your
  laptop's, so the setting follows `ON_VERCEL`. `SECURE_SSL_REDIRECT` follows it too, as a second line: Vercel's
  CDN already answers every plain-HTTP request with a 308 to HTTPS, and that "can't be disabled" (Vercel,
  2026d). The same page says Vercel sends `Strict-Transport-Security` on custom domains, which is why the
  `security.W004` check is silenced rather than satisfied with a setting of our own.
- **Secure cookies.** A cookie marked Secure is sent by the browser only over HTTPS, so a session cookie
  cannot be read off a plain connection (Django Software Foundation, n.d.-c). Both are on whenever debug is
  off. One consequence is worth knowing before it bites: `runserver` with debug off cannot sign you in at
  `http://127.0.0.1:8000/admin/`, because the browser keeps the Secure cookie off the plain connection. Sign
  in locally with debug on; the server is where debug is off.
- **`LOGGING`.** Django's default configuration prints to the console only while debug is on, so a server would
  show nothing when a view raises. This sends warnings and errors to stderr, which Vercel collects as the
  function's logs. A 500's traceback and a refused host name both appear there.

The names, with what each one is for, live in `.env.example`:

Listing 06-8, Filename: `.env.example`:

{{file:.env.example}}

### 06.4 The health route

Listing 06-9, Filename: `src/invest_witus_site/health.py`:

{{file:src/invest_witus_site/health.py}}

Listing 06-10, Filename: `src/invest_witus_site/urls.py`:

{{file:src/invest_witus_site/urls.py}}

A monitor, or you after a deploy, asks one URL three things: is the app up, which version is it, can it reach
its database. `SELECT 1` is the smallest query a database can run; if it raises any `DatabaseError`, the
answer is 503 and `"database": false`. The error's class name goes to the log, never its message, because the
message can name a host. The version comes from `pyproject.toml` with `tomllib`, read once and cached: the
project is not installed on Vercel (06.5), so `importlib.metadata` would not know it, but the file ships with
the function. `never_cache` keeps the CDN from answering for the app, and `require_GET` turns a POST into a
405.

### 06.5 The entry file and the import path

Here is how Vercel runs a Django project, from its documentation and from the builder's source (Vercel, 2026c,
2026i, n.d.):

1. It detects Django from the dependency list and looks for `manage.py` at the root or one level down.
2. It runs `manage.py` (with Django's command dispatch stubbed out) to learn `DJANGO_SETTINGS_MODULE`, then
   imports the settings and reads them.
3. It turns `WSGI_APPLICATION` into a file path relative to `manage.py`: `app.wsgi.application` means
   `app/wsgi.py`, which must define a top-level `application`.
4. It installs the packages from `uv.lock` into a vendor folder with `uv pip install --target`. It does not
   install your project. There is no `uv sync`, so the `src/` layout that `uv sync` makes importable on your
   laptop is not importable there.
5. With `STATIC_ROOT` set, it runs `manage.py collectstatic` and serves the result from its CDN.

Steps 3 and 4 are the problem. Our project lives in `src/invest_witus_site/`, the settings module is not on
the import path, and `invest_witus_site/wsgi.py` does not exist beside `manage.py`. Moving the project is out:
later chapters never move or rename earlier files (invariant 4 in `CLAUDE.md`). Two small files fix both
without a move.

Listing 06-11, Filename: `manage.py`:

{{file:manage.py}}

Three lines changed: `manage.py` puts `src/` at the front of `sys.path` before Django imports anything. On
your laptop that is harmless, because `uv sync` already made the project importable and the path points at the
same files. On Vercel it is what makes step 2 and step 5 work, since both run `manage.py`.

Listing 06-12, Filename: `wsgi.py` (repository root):

{{file:wsgi.py}}

The bridge. `WSGI_APPLICATION = "wsgi.application"` resolves, by Vercel's rule, to this file at the root;
the file adds `src/` to the path and hands over the project's own application object, unchanged, from
`src/invest_witus_site/wsgi.py`. `runserver` loads the same string, finds the same file (the folder holding
`manage.py` is first on the path when you run `python manage.py`), and gets the same object; a test checks
that. Another test proves the point of this section: it removes `src/` from the import path in a fresh
process, then runs `manage.py check` and loads `wsgi.py`, and both work.

### 06.6 The deploy files

Listing 06-13, Filename: `vercel.json`:

{{file:vercel.json|json}}

Two keys:

- **`ignoreCommand`** is the ecosystem's Ignored Build Step, word for word. Vercel runs it before a build; exit
  code 1 means build, 0 means skip, and the value in `vercel.json` "overrides the Ignored Build Step in Project
  Settings" (Vercel, 2026g). `VERCEL_ENV` and `VERCEL_GIT_COMMIT_REF` are two more of Vercel's own variables.
  Production always builds; a `bundle/*` branch builds a preview; anything else is skipped.
- **`functions`** is keyed by the entry file, `wsgi.py`, and its `excludeFiles` glob keeps the tests, the
  chapter and research text, the sample data, the scripts and the local plans out of the function. `docs/site/`
  is not excluded: the FAQ, privacy and terms pages read it at request time. The whole project is otherwise
  included, and the Python bundle limit is 500 MB (Vercel, 2026k). Two more limits to know and not fight: a
  request body of 4.5 MB, and 300 seconds per invocation on the Hobby plan.

Nothing here runs migrations. Vercel's Django page does not run them, and the ecosystem's practice is that the
owner runs production migrations by hand with the database URL in the shell (WitUS, 2026). 06.9 shows the
command.

Two things are not in the file, on purpose. There is no `crons` key yet: chapter 08 adds the one daily job, and
its shape is known now so nothing in this chapter has to change for it. A cron is an entry with a `path` and a
`schedule`, in UTC; on the Hobby plan it may run once a day, anywhere inside the scheduled hour, and a failed
run is not retried; Vercel sends the project's `CRON_SECRET` as a bearer token in the `Authorization` header,
which is how the route tells Vercel from a stranger (Vercel, 2026b, 2026e). And there is no Python version
here, because Vercel reads it from `.python-version` or `requires-python`, offers 3.12, 3.13 and 3.14, and
falls back to 3.12 for anything else (Vercel, 2026f). Both files have said 3.14 since chapter 00; the last test
in `tests/test_ch06.py` pins them, so a stray edit cannot move the function to an older interpreter without a
red test.

Listing 06-14, Filename: `.gitignore`:

{{file:.gitignore|text}}

Two new lines: `staticfiles/`, which `collectstatic` writes, and `.vercel/`, which `vercel link` writes.

Listing 06-15, Filename: `.github/workflows/neon-preview-cleanup.yml`:

{{file:.github/workflows/neon-preview-cleanup.yml|yaml}}

Copied from the ecosystem's template without a change. Its header comment is the explanation; the one thing
it needs from you is in 06.9: the repository variable `NEON_PROJECT_ID` and the secret `NEON_API_KEY`, without
which it fails loudly on every run.

### 06.7 Green on the laptop

Listing 06-16, Terminal:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

```text
140 passed in 2.66s
All checks passed!
77 files already formatted
0 errors, 0 warnings, 0 informations
```

Twenty-seven new tests. The run is a second longer than chapter 05's because two tests start a separate
Python process.

Now see the settings the way a server would, before any server exists. Set a production-shaped environment in
one shell (a key, a host, an absolute SQLite path somewhere temporary) and run Django's deployment checklist:

Listing 06-17, Terminal:

```sh
export DJANGO_SECRET_KEY="$(uv run python -c 'from django.core.management.utils import get_random_secret_key as k; print(k())')"
export DJANGO_ALLOWED_HOSTS=127.0.0.1 DATABASE_URL=sqlite:////tmp/invest-witus-check.sqlite3
VERCEL=1 uv run python manage.py check --deploy
```

```text
System check identified no issues (1 silenced).
```

Drop `VERCEL=1` and the same command reports one warning, `security.W008`, that `SECURE_SSL_REDIRECT` is off:
correct, because off Vercel nothing redirects for you. Drop the key and it refuses:

Listing 06-18, Terminal:

```sh
env -u DJANGO_SECRET_KEY uv run python manage.py check 2>&1 | tail -1
```

```text
django.core.exceptions.ImproperlyConfigured: DJANGO_SECRET_KEY is not set and DJANGO_DEBUG is not 1. A server needs a secret key. Make one with: uv run python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
```

Then the static files and a real server with debug off, in the same shell:

Listing 06-19, Terminal:

```sh
uv run python manage.py collectstatic --noinput | tail -1
uv run python manage.py migrate --verbosity 0
uv run python manage.py runserver --insecure
```

```text
134 static files copied to '/.../invest-witus/staticfiles'.
```

`--insecure` lets `runserver` serve the collected files with debug off, for this check only (Django Software
Foundation, n.d.-d); Vercel does that job with its CDN. In a second terminal:

Listing 06-20, Terminal:

```sh
curl -i http://127.0.0.1:8000/healthz/
curl -s -o /dev/null -w '%{http_code}\n' -H 'Host: evil.example' http://127.0.0.1:8000/
```

```text
HTTP/1.1 200 OK
Content-Type: application/json
Cache-Control: max-age=0, no-cache, no-store, must-revalidate, private

{"status": "ok", "version": "0.1.0", "database": true}
400
```

The second request shows `ALLOWED_HOSTS` doing its work, and the server's terminal shows the `DisallowedHost`
line that `LOGGING` now lets through. Stop the server, delete `staticfiles/` and the temporary database, and
`unset` the four variables. The dev loop from chapter 05 is unchanged: `uv run --env-file .env python
manage.py runserver`, with debug on.

### 06.8 The Vercel project

Everything from here on happens in a browser or with the Vercel CLI, against your own GitHub repository.
The reference repository's project is the owner's; your project is yours. Menu names are from Vercel's
documentation as read on October 28, 2026 (Vercel, 2026c, 2026h).

1. **Push your chapter 06 commit** to the branch Vercel will treat as production (`main`, unless you changed
   it). The Ignored Build Step builds production and `bundle/*` branches only, so a push to any other branch
   produces no deployment.
2. **Import the repository.** On the Vercel dashboard: **Add New** → **Project** → **Import** your repository
   (a private repository needs the Vercel GitHub app to have access to it; the import page offers to adjust
   that). On the import form, **Framework Preset** should read Django, detected from `manage.py`; pick it if
   it says Other. Leave **Root Directory** as `./` and leave every **Build and Output Settings** override off:
   there is no build command, because Vercel runs `collectstatic` itself, and dependencies install from
   `uv.lock`.
3. **Set the environment variables on the same form, before you press Deploy.** Open **Environment
   Variables** and add:

   | Name | Value | Environments |
   |---|---|---|
   | `DJANGO_SECRET_KEY` | the output of the command in `.env.example`; mark it Secret | Production, and a different value for Preview |
   | `DJANGO_ALLOWED_HOSTS` | your domain, or nothing yet: Vercel's `*.vercel.app` names are added on their own | Production |
   | `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://` and your domain, when you have one | Production |

   Do not set `DJANGO_DEBUG`. Do not set `DATABASE_URL`; 06.9 does. If you press Deploy first, the build stops
   with `DJANGO_SECRET_KEY is not set`: the guard from 06.3, doing on the build machine what it would do in
   the function. Add the variable and **Redeploy**.
4. **Press Deploy** and open the build log. You should see the dependencies install, then `collectstatic`.
5. **Two project settings** (the project → **Settings**):
   - **Environment Variables** → the checkbox **Enable access to System Environment Variables** is on. This is
     what makes `VERCEL=1` and the `VERCEL_*` host names reach the settings (Vercel, 2026h). With it off, the
     settings do not trust the proxy header, Django thinks every request is plain HTTP, and every form POST
     fails the CSRF check. That is a loud failure, not a quiet hole, but the site is unusable until the box is
     ticked.
   - **Build and Deployment** → build machine **Standard**, on-demand concurrent builds off, and **Deployment
     Retention Policy** → **Pre-Production Deployments** set to the shortest duration. These are the ecosystem's
     cost rules (WitUS, 2026); the Ignored Build Step needs no setting, since `vercel.json` carries it.
6. **Open `/healthz/` on the deployment URL.** Expect 503 with `"database": false`: the function is up and
   the database is not attached yet. That is the route doing its job.

### 06.9 Neon, the migration, and the owner

Neon can be attached two ways: from Neon's own console, pasting a connection string into Vercel, or through
the Vercel Marketplace integration, which creates the database, sets the variables on the project and makes a
database branch per preview deployment (Neon, n.d.-d). The ecosystem uses the integration in every Neon
repository, and the cleanup workflow from 06.6 assumes it, so that is the path here.

1. **Attach Neon.** The project → **Storage** → **Create Database** → **Neon**. In the **Install Neon** dialog,
   pick a region near Vercel's default function region (`iad1`, Washington, D.C.; Neon's list names its
   regions), the **Free** plan, and a database name. Then **Connect Project**: your project, the
   **Production** and **Preview** environments, and under **Create database branch for deployment** tick
   **Preview**. Leave **Custom Prefix** empty, so the names are exactly `DATABASE_URL` and
   `DATABASE_URL_UNPOOLED`. **Connect**.
2. **Redeploy** the latest production deployment (**Deployments** → the menu on the deployment → **Redeploy**)
   so the function starts with the new variables, then open `/healthz/` again: 200, `"database": true`. The
   round trip works on an empty database; tables come next.
3. **Link the repository folder to the project:** `vercel link`, choosing your team and the project. It writes
   `.vercel/`, which is gitignored.
4. **Migrate, against the direct connection.** `vercel env run` runs a command with the project's variables
   without writing them to a file (Vercel, 2026j):

   Listing 06-21, Terminal:

   ```sh
   vercel env run -e production -- uv run python manage.py migrate --database direct
   ```

   ```text
   Operations to perform:
     Apply all migrations: admin, auth, contenttypes, holdings, pages, sessions
   Running migrations:
     ...
     Applying sessions.0001_initial... OK
   ```

   `--database direct` is the alias from 06.3, built from `DATABASE_URL_UNPOOLED`; the same command without it
   would go through the pooler, which works but is not what Neon advises for schema changes. If your CLI has
   no `env run`, the fallback is `vercel env pull .env.production --environment=production`, the same command
   with `uv run --env-file .env.production`, and then deleting that file; `.env.*` is gitignored.
5. **The owner, without a keyboard.** `createsuperuser --noinput` reads the username, the email and the
   password from `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_EMAIL` and `DJANGO_SUPERUSER_PASSWORD` (Django
   Software Foundation, n.d.-d). In that mode the password validators from chapter 05 do not run (the
   interactive prompt is where they live), so make the password long, and save it in your password manager
   before the command, not after. Set the three in the shell for that one command:

   Listing 06-22, Terminal:

   ```sh
   DJANGO_SUPERUSER_USERNAME=owner DJANGO_SUPERUSER_EMAIL=owner@example.com DJANGO_SUPERUSER_PASSWORD='...' \
     vercel env run -e production -- uv run python manage.py createsuperuser --noinput --database direct
   ```

   ```text
   Superuser created successfully.
   ```

   Run it twice and the second run says `Error: That username is already taken.`, which a test in 06.1
   checks on a laptop database.
6. **Sign in** at `/admin/` on the deployment URL. The public site, the waitlist, the FAQ and the admin are
   all the chapter 04 and 05 pages, now on Postgres.
7. **The cleanup workflow's two values.** In the Neon console (**Open in Neon** from the Storage tab):
   **Project settings** → **General** → copy the **Project ID**; **Organization settings** → **API keys** →
   **Create new** → **Project-scoped**, this project. In GitHub: the repository → **Settings** → **Secrets and
   variables** → **Actions**: the variable `NEON_PROJECT_ID` and the secret `NEON_API_KEY`. Then **Actions**
   → **Cleanup Neon preview branches** → **Run workflow**; green with `Done: 0 deleted, 0 kept.` means both
   are right.

### 06.10 A domain, if you have one

The project → **Settings** → **Domains** → **Add Domain** → type the name. For a subdomain, the row that
appears shows a **CNAME** record, and "Each project has a unique CNAME record" (Vercel, 2026a): copy the
value from that row into your DNS host, as a CNAME at the subdomain's name. If the row shows a **TXT** record at
`_vercel` instead, the apex domain belongs to another Vercel account; add the TXT record first, then come
back. When the row reads **Valid Configuration**, add the name to `DJANGO_ALLOWED_HOSTS` and its HTTPS origin to
`DJANGO_CSRF_TRUSTED_ORIGINS` (if you did not in 06.8) and redeploy. `VERCEL_PROJECT_PRODUCTION_URL` now
carries the domain on its own.

Without a domain, the `*.vercel.app` name Vercel gave the project is the production host, and nothing above
needs changing.

## Checkpoint

- `uv run pytest` prints `140 passed`; ruff and pyright pass.
- With a key, a host and a temporary `DATABASE_URL` in the shell, `VERCEL=1 uv run python manage.py check
  --deploy` reports no issues; without the key, `manage.py` refuses with the message that names the fix.
- `uv run --env-file .env python manage.py runserver` still serves the site with debug on, and
  `/healthz/` answers `{"status": "ok", "version": "0.1.0", "database": true}`.
- On Vercel: `/healthz/` is 200 on the production URL, the landing page has its styles, `/admin/` signs the
  owner in, and the cleanup workflow has run green once.
- `git status` shows no `.env*` file but `.env.example`, no `staticfiles/`, no `.vercel/`.
- Commit and push: `git add -A && git commit -m "Chapter 06: Vercel and Neon"`.

## Exercises

1. `/healthz/` reports the database. Add a second check that the static files were collected: with
   `STATIC_ROOT` set and `DEBUG` off, does `staticfiles/pages/site.css` exist? Decide whether a missing file
   should be a 503, and write the test either way.
2. The parser refuses an unknown query option. Neon's console also offers `?sslmode=verify-full` (Neon,
   n.d.-a). Add a test that the parser passes it through, and read in Neon's page what `verify-full` checks that
   `require` does not.
3. `fresh_settings` re-imports the whole settings module. Write a test that uses it to show that
   `DJANGO_ALLOWED_HOSTS="a.example, ,b.example,"` yields exactly `["a.example", "b.example"]` plus Vercel's
   names, and nothing blank.

## If you get stuck

- Browse: https://github.com/dapperAuteur/invest-witus/tree/v06
- Diff for this chapter: https://github.com/dapperAuteur/invest-witus/compare/v05...v06
- Zip: https://github.com/dapperAuteur/invest-witus/archive/v06.zip
- Take the reference's files. Chapter 06 changed `pyproject.toml` and `uv.lock` (psycopg), `.env.example`,
  `.gitignore`, `manage.py`, `src/invest_witus_site/settings.py` and `src/invest_witus_site/urls.py`, and added
  `wsgi.py`, `vercel.json`, `.github/workflows/neon-preview-cleanup.yml`, `src/invest_witus_site/database.py`,
  `src/invest_witus_site/health.py`, `tests/settings.py` and `tests/test_ch06.py`. Nothing moved:
  `git fetch reference --tags && git checkout v06 -- src tests manage.py wsgi.py vercel.json .github .env.example .gitignore pyproject.toml uv.lock`,
  then `uv sync`.
- `ImproperlyConfigured: DJANGO_SECRET_KEY is not set and DJANGO_DEBUG is not 1` on your laptop: run the
  command with `--env-file .env`, and check that `.env` has `DJANGO_DEBUG=1`.
- `uv run pytest` fails at startup with the same message: `pyproject.toml` still names
  `invest_witus_site.settings` under `[tool.pytest]`, or `tests/settings.py` is missing.
- `ValueError: DATABASE_URL must start with postgresql:// or sqlite:///`: the variable holds something else,
  often an empty string with quotes, or a `postgres:` URL with one slash.
- The build on Vercel fails with `ModuleNotFoundError: No module named 'invest_witus_site'`: `manage.py` does
  not add `src/` to `sys.path` before importing Django, or the file is not at the repository root.
- The deployment answers 500 and the log says `Invalid HTTP_HOST header`: the host is not in
  `DJANGO_ALLOWED_HOSTS`, or system environment variables are off (06.8, step 5), so Vercel's own names never
  arrived.
- Every form POST on Vercel is a 403 `CSRF verification failed`: the same checkbox, or
  `DJANGO_CSRF_TRUSTED_ORIGINS` names `http://` instead of `https://`.
- `/healthz/` says `"database": false` after Neon is attached: the function started before the variables
  existed; redeploy. If it persists, open the Storage tab and check that the project is connected to the
  Production environment.
- `migrate --database direct` says `The connection 'direct' doesn't exist`: `DATABASE_URL_UNPOOLED` is not in
  the environment you ran with; `vercel env run -e production` or the pulled file is missing it, which means
  the integration was connected with a custom prefix.
- Signing in to the admin on your laptop with debug off loops back to the login form: Secure cookies, as
  06.3 says. Use `--env-file .env`.
- The cleanup workflow fails at its first step: the variable and secret from 06.9 step 7 are not set, or are
  set as the wrong kind (`NEON_PROJECT_ID` is a variable, `NEON_API_KEY` a secret).

## What we learned

- Settings that fail closed: no key, no start; debug on Vercel, no start; an unknown host, a 400; an unknown
  database option, a `ValueError` that names it.
- One function turns a connection string into Django's dictionary, with the pooler's needs
  (`DISABLE_SERVER_SIDE_CURSORS`, a health-checked connection) as data.
- A proxy changes what Django can see: `SECURE_PROXY_SSL_HEADER` only behind one, Secure cookies whenever
  debug is off, trusted origins for the CSRF check, and host names read from the host's own variables.
- Vercel finds `manage.py`, reads the settings, maps `WSGI_APPLICATION` to a file, vendors the lock's packages
  and not the project, and runs `collectstatic` when `STATIC_ROOT` exists. A `sys.path` line in `manage.py`
  and a two-line bridge file meet it without moving anything.
- A health route answers three questions and nothing more; `never_cache` and `require_GET` are one line each.
- Tests can re-import a settings module with a controlled environment, or run `manage.py` in a separate
  process to stand in for a server.
- Migrations and the first superuser run from the owner's machine, through `vercel env run`, against the
  direct connection; nothing migrates at build time.
- The values that belong to Vercel and Neon are copied from the page that owns them.

## Next

Chapter 07 replaces the stub at `/auth/witus/login/` with Sign in with WitUS: OIDC against the ecosystem's
identity provider, EdDSA id tokens, a callback that matches a user by the WitUS user id and never by email, and
a sign-out. It needs the production origin from this chapter, because the identity provider matches redirect
URIs exactly.

## References

Django Software Foundation. (n.d.-a). *Deployment checklist*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/ (retrieved October 28, 2026)

Django Software Foundation. (n.d.-b). *Databases*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/ref/databases/ (retrieved October 28, 2026)

Django Software Foundation. (n.d.-c). *Settings*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/ref/settings/ (retrieved October 28, 2026)

Django Software Foundation. (n.d.-d). *django-admin and manage.py*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/ref/django-admin/ (retrieved October 28, 2026)

Neon. (n.d.-a). *Connect to Neon securely*. Neon documentation. https://neon.com/docs/connect/connect-securely
(retrieved October 28, 2026)

Neon. (n.d.-b). *Connect a Django application to Neon*. Neon documentation. https://neon.com/docs/guides/django
(retrieved October 28, 2026)

Neon. (n.d.-c). *Connection pooling*. Neon documentation. https://neon.com/docs/connect/connection-pooling
(retrieved October 28, 2026)

Neon. (n.d.-d). *Vercel-managed integration*. Neon documentation.
https://neon.com/docs/guides/vercel-managed-integration (retrieved October 28, 2026)

Vercel. (n.d.). *vercel/vercel: packages/python/src* [Source code]. GitHub.
https://github.com/vercel/vercel/tree/main/packages/python/src (retrieved October 28, 2026)

Vercel. (2025, December 13). *Request headers*. Vercel documentation.
https://vercel.com/docs/headers/request-headers (retrieved October 28, 2026)

Vercel. (2026a, September 16). *Adding and configuring a custom domain*. Vercel documentation.
https://vercel.com/docs/domains/working-with-domains/add-a-domain (retrieved October 28, 2026)

Vercel. (2026b, September 16). *Cron jobs*. Vercel documentation. https://vercel.com/docs/cron-jobs (retrieved
October 28, 2026)

Vercel. (2026c, July 24). *Deploy a Django app on Vercel*. Vercel documentation.
https://vercel.com/docs/frameworks/full-stack/django (retrieved October 28, 2026)

Vercel. (2026d, September 15). *Encryption and TLS*. Vercel documentation.
https://vercel.com/docs/cdn-security/encryption (retrieved October 28, 2026)

Vercel. (2026e, August 11). *Managing cron jobs*. Vercel documentation.
https://vercel.com/docs/cron-jobs/manage-cron-jobs (retrieved October 28, 2026)

Vercel. (2026f, April 10). *Set the Python version for your Vercel project*. Vercel documentation.
https://vercel.com/docs/functions/runtimes/python/python-version (retrieved October 28, 2026)

Vercel. (2026g, August 14). *Static configuration with vercel.json*. Vercel documentation.
https://vercel.com/docs/project-configuration/vercel-json (retrieved October 28, 2026)

Vercel. (2026h, July 15). *System environment variables*. Vercel documentation.
https://vercel.com/docs/environment-variables/system-environment-variables (retrieved October 28, 2026)

Vercel. (2026i, August 12). *Using the Python runtime with Vercel Functions*. Vercel documentation.
https://vercel.com/docs/functions/runtimes/python (retrieved October 28, 2026)

Vercel. (2026j, August 20). *vercel env*. Vercel documentation. https://vercel.com/docs/cli/env (retrieved
October 28, 2026)

Vercel. (2026k, August 24). *Vercel Functions limits*. Vercel documentation.
https://vercel.com/docs/functions/limitations (retrieved October 28, 2026)

WitUS. (2026). *Shared rules for ecosystem repositories* (v8) [Internal document: the Ignored Build Step, the
preview-branch cleanup rule, and the migration gate]. `gemini/witus/docs/shared-rules.md` and
`docs/shared-ui-ux-dx.md` (read October 28, 2026)
