# Chapter 04: The first Django page: the public landing page

**Starts from:** tag `v03`. **Ends at:** tag `v04`.
**Written against:** Python 3.14.10, uv 0.13.6, Django 5.2.18, Markdown 3.11.2, pytest-django 4.14.0,
django-stubs 6.1.2 (October 27, 2026).
**Goal:** `uv run python manage.py runserver` serves the public site: the landing page with its waitlist, the
FAQ, the privacy and terms pages, a contact page, and a header whose "Sign in" link a test protects.
**Time:** 3 to 4 hours. The longest chapter so far, because a website is many small files.

The listings in this chapter are not typed in by hand. `scripts/render_chapter.py` pastes the real files from
tag `v04` into the chapter text, so what you read and what the tests run are the same bytes.

## What you will learn

- **Django's shape:** a *project* (settings and the root URL list) and *apps* (the code for one area of the
  site). If you know Next.js: the project is the app's config, the apps are its route groups.
- **Settings from the environment** with safe defaults, so one file serves your laptop and a server.
- **URLs, views and templates:** a URL pattern names a view function; the view returns a response, usually a
  rendered template. Templates extend a base and include partials, like layouts and components.
- **A model and its migration:** the first database table, the waitlist, and the file Django writes to create
  it.
- **Forms, CSRF and a honeypot:** validation on the server, the token that stops cross-site posts, and a hidden
  field that catches bots.
- **Static files and the test client:** how CSS and images are served, and how a test asks for a page without
  a browser.
- **Accessible names:** why a link's name is its text, and the one link in this app that is never renamed.

## Before the code: what the public site promises

The public site is the part of the app anyone can see, and the invariants from chapter 00 bind it hardest:
information, not advice. No public page recommends a security or shows a price, a chart, a return or a
testimonial, and none reads as "automated trading". The site says what the app is in the one sentence the PRD
fixes: *"Pick a method you learned. Practice it on paper. The app keeps you to its rules and shows you the
lesson behind each one."*

It also has a job the app itself does not have: pointing people who were cheated to the desks that take
reports. The FAQ (`docs/site/faq.md`, already written) opens with "Report a bad actor", and the landing page
and the footer both link to it.

Two rules from the WitUS ecosystem apply to every app, this one included (WitUS, 2026c):

- **The header carries a link whose accessible name is exactly "Sign in"** whenever a visitor is signed out.
  It is never renamed and never replaced by "Apps" or "Account"; a second link is added instead. A test
  tagged `smoke` fails if it changes. The rule exists because witus.online shipped for five months with the
  link renamed, and the ecosystem's owner reported "no login button" twice.
- **The footer is the ecosystem footer:** the same structure in every app, each in its own colors; the Rise
  Wellness callout and its disclaimer word for word; the sibling products from the ecosystem's registry; the
  copyright line verbatim (WitUS, 2026b).

The tests you copy first check all of this. They also check the promise above the way a machine can: no
public page contains a `<table>` element or a signed percentage like `+8.5%`. That is a narrow check on
purpose. It cannot judge wording, but it catches the two shapes a performance claim usually takes, and it lets
the FAQ's "$25,000" (a regulatory threshold, not a price) through.

## Steps

### 04.1 Add Django and the tools

Listing 04-1, Terminal:

```sh
uv add "django>=5.2,<6" "markdown>=3.11"
uv add --dev "pytest-django>=4.14" "django-stubs>=6.1" types-markdown
```

Four new names:

| Package | What it is | Node analogy |
|---|---|---|
| `django` | The web framework: routing, templates, forms, the ORM, the admin | Next.js plus Drizzle plus a form library |
| `markdown` | Python-Markdown, which renders the FAQ and the legal pages from `.md` files | `remark` |
| `pytest-django` | pytest fixtures: a test client and a test database rolled back after each test | `supertest` with a test database |
| `django-stubs`, `types-markdown` | Type information for pyright, which neither package ships itself | `@types/*` |

**Why Django 5.2 and not 6.1.** On the day this was written, 6.1.2 was Django's newest release and 5.2.18 the
newest long-term-support (LTS) release. Both run on Python 3.14; 5.2 added it in 5.2.8 (Django Software
Foundation, n.d.-c). The LTS gets fixes until April 2028, 6.1 until December 2027 (Django Software Foundation,
n.d.-e). A tutorial people follow for a year or two wants the longer runway, so `"django>=5.2,<6"` pins the
series. The `<6` matters: without it, the next `uv lock --upgrade` would be free to pick 6.x.

Then three changes to `pyproject.toml`. The new tables tell uv to install both packages under `src/`, tell
pytest-django where the settings are, and tell pyright about two new folders:

Listing 04-2, Filename: `pyproject.toml`:

{{file:pyproject.toml}}

`module-name` is new. Chapter 00's `uv init --package` made one importable package, `invest_witus`. This
chapter adds a second one beside it, `invest_witus_site`, and uv's build backend installs only the names it is
given (Astral, n.d.-a). Run `uv sync` after the edit so the environment picks up the second package.

The `smoke` marker is declared so pytest does not warn about an unknown mark. `uv run pytest -m smoke` runs
only the tests that carry it.

### 04.2 Copy the checkpoint test

Listing 04-3, Filename: `tests/test_ch04.py`:

{{file:tests/test_ch04.py}}

Read it before you run it; it is the chapter's contract. Things to notice:

- `LinkCollector` is a small HTML parser from the standard library. It records every link as `(href, text)`,
  because a link's **accessible name**, the thing a screen reader announces, is computed from its content
  (W3C, 2026). The test for "Sign in" asks for that exact pair inside `<header>`; a link whose text is "Sign in
  to WitUS" or "Login" fails it.
- `client` is a pytest-django fixture: Django's test client, which calls your views directly, with no server
  and no network (pytest-dev, n.d.-b; Django Software Foundation, n.d.-k).
- `@pytest.mark.django_db` marks the tests that touch the database. pytest-django creates a throw-away test
  database and rolls back after each test; a test without the mark that touches a model fails on purpose.
- `Client(enforce_csrf_checks=True)` is the test client with CSRF checks turned **on**. They are off by
  default so ordinary tests can post without a token.
- The settings test reads `settings.DATA_DIR`, not the database name: pytest-django points SQLite at memory
  while tests run, so the file name would say nothing.

Run it:

Listing 04-4, Terminal:

```sh
uv run pytest tests/test_ch04.py
```

```text
ImportError: No module named 'invest_witus_site'
```

Red first. pytest-django reads `DJANGO_SETTINGS_MODULE` from `pyproject.toml` (pytest-dev, n.d.-a) and cannot
import it yet. The lines after that one vary; the first is the one that matters.

### 04.3 The project

Django's `django-admin startproject` would create these files beside `manage.py`. Ours live under `src/` with
the rest of the code, so write them by hand. Together they are shorter than this section makes them look.

Listing 04-5, Filename: `manage.py` (repository root):

{{file:manage.py}}

`manage.py` is Django's `npm run`: `uv run python manage.py migrate`, `runserver`, `makemigrations`, `check`.
Its one job is to name the settings module and hand the rest to Django. pytest-django also uses it as a
landmark: a folder with a `manage.py` is a Django project, and it adds that folder to the Python path.

Listing 04-6, Filename: `src/invest_witus_site/__init__.py`:

{{file:src/invest_witus_site/__init__.py}}

Listing 04-7, Filename: `src/invest_witus_site/settings.py`:

{{file:src/invest_witus_site/settings.py}}

Settings is a plain module; every uppercase name in it is a setting (Django Software Foundation, n.d.-d). What
differs from the file `startproject` would generate:

- **Nothing secret and nothing machine-specific is written down.** `SECRET_KEY`, `DEBUG` and `ALLOWED_HOSTS`
  come from the environment. The fallback key starts with `django-insecure-` so that `manage.py check --deploy`
  flags it (Django Software Foundation, n.d.-a), and `DEBUG` is off unless you say otherwise. A server that
  forgets a variable gets the safe value, not the convenient one.
- **Two installed apps, not seven.** The generated list has the admin, auth, sessions and more. We add each
  one in the chapter that uses it, so you see what each is for. Chapter 05 adds the admin; chapter 07 adds
  sessions.
- **The database is a SQLite file in `data/private/`,** the folder git already ignores from chapter 03.
  Chapter 06 swaps it for Postgres through `DATABASE_URL` without touching the rest.
- **`SITE_PAGES_DIR`** is our own setting. Django does not mind extra names; `settings.SITE_PAGES_DIR` works
  like a built-in one.

Listing 04-8, Filename: `.env.example`:

{{file:.env.example}}

Copy it to `.env` (git ignores `.env`; chapter 00's `.gitignore` already has the rule) and run commands with
`uv run --env-file .env ...`; uv loads the file into the environment for that one command (Astral, n.d.-b).
Nothing in the app reads `.env` itself, which is the point: on a server there is no file, only variables.

Listing 04-9, Filename: `src/invest_witus_site/urls.py`:

{{file:src/invest_witus_site/urls.py}}

The root URL list. `include` hands every path to the app's own list, so an app carries its own routes (Django
Software Foundation, n.d.-l).

Listing 04-10, Filename: `src/invest_witus_site/wsgi.py`:

{{file:src/invest_witus_site/wsgi.py}}

Listing 04-11, Filename: `src/invest_witus_site/asgi.py`:

{{file:src/invest_witus_site/asgi.py}}

Two entry points for two server protocols. `runserver` needs neither; chapter 06's host wants `wsgi.py`.

### 04.4 The app and its one table

An app is a Python package with a known layout: `models.py`, `views.py`, `urls.py`, `templates/`, `static/`,
`migrations/`. This chapter's app is `pages`: the public pages.

Listing 04-12, Filename: `src/invest_witus_site/pages/__init__.py`:

{{file:src/invest_witus_site/pages/__init__.py}}

Listing 04-13, Filename: `src/invest_witus_site/pages/apps.py`:

{{file:src/invest_witus_site/pages/apps.py}}

Listing 04-14, Filename: `src/invest_witus_site/pages/models.py`:

{{file:src/invest_witus_site/pages/models.py}}

A model is a class whose attributes are columns; Django makes the table and gives you `WaitlistEntry.objects`
to query it (Django Software Foundation, n.d.-i). Four things in this one:

- `unique=True` on `email` makes the database refuse a second row with the same address. `join` lowercases
  and trims the address first, so `Ada@Example.com ` and `ada@example.com` are one row; a test checks that.
- `get_or_create` finds the row or inserts it, and says which. The view does not care which: the thank-you
  page is the same either way, so the form never reveals who is already on the list.
- The `[str, str]` annotations are for pyright. django-stubs describes a field as a generic with two type
  parameters, the type you assign and the type you read back, and leaves its mypy plugin to fill them in.
  pyright has no plugin, so we write them, the way you would write `Field<string, string>` (typeddjango,
  n.d.). `created_at` reads back as a `datetime`.
- `tuple[WaitlistEntry, bool]` names the class inside its own body. Python 3.14 evaluates annotations lazily,
  so the forward reference needs no quotes; older code wrote `"WaitlistEntry"`.

Make the migrations package and let Django write the first migration:

Listing 04-15, Terminal:

```sh
mkdir -p src/invest_witus_site/pages/migrations
touch src/invest_witus_site/pages/migrations/__init__.py
uv run python manage.py makemigrations pages
uv run ruff format src/invest_witus_site/pages/migrations
```

```text
Migrations for 'pages':
  src/invest_witus_site/pages/migrations/0001_initial.py
    + Create model WaitlistEntry
```

Listing 04-16, Filename: `src/invest_witus_site/pages/migrations/0001_initial.py`:

{{file:src/invest_witus_site/pages/migrations/0001_initial.py}}

A migration is the difference between the models and the database, written as Python so it can be reviewed
and run on any machine (Django Software Foundation, n.d.-h). Django wrote it; `ruff format` only changed
quotes and line breaks to match the project. Commit migrations, and never edit one that has run somewhere.
Your timestamp in the first line will differ; keep yours.

### 04.5 The form

Listing 04-17, Filename: `src/invest_witus_site/pages/forms.py`:

{{file:src/invest_witus_site/pages/forms.py}}

A Django form declares fields and validates a POST body against them (Django Software Foundation, n.d.-m):
`EmailField` rejects `not-an-email` with the message the test looks for, and `max_length` matches the model.
The `website` field is the honeypot. The stylesheet moves it off screen and `tabindex="-1"` keeps the keyboard
away from it, so a person never fills it in and a form-filling bot usually does. The view treats a filled
honeypot as "say thank you, store nothing".

### 04.6 Pages from Markdown

The FAQ, privacy and terms pages are Markdown files in `docs/site/`. A wording change is a commit with a
readable diff, and the same file reads well on GitHub.

Listing 04-18, Filename: `src/invest_witus_site/pages/markdown_pages.py`:

{{file:src/invest_witus_site/pages/markdown_pages.py}}

Two things Python-Markdown does not do on its own:

- **Heading ids.** The `toc` extension gives each heading an `id` made from its text (Python-Markdown,
  n.d.-b), so `## Report a bad actor` becomes `<h2 id="report-a-bad-actor">` and the landing page can link
  straight to it.
- **Bare URLs.** Markdown links only `<https://...>` in angle brackets or `[text](url)`. The FAQ writes its
  sources as plain URLs, so `BareUrlProcessor` is a small inline extension (Python-Markdown, n.d.-a): a regular
  expression finds `https://...`, `trim_url` drops the sentence punctuation that follows a URL, and the
  processor returns an `<a>` element plus the span of text it replaces. The balanced-parentheses rule exists
  for one real link, the SEC marketing rule at `.../section=275.206(4)-1`, whose `(4)` is part of the address.
  A test checks that exact link renders.

`PAGES` is a fixed table from slug to file name. The URL never names a file, so a request cannot reach
outside `docs/site/`.

Now write the two pages the FAQ does not cover. The PRD lists what they must say (education only, not advice;
not a broker or an adviser; paper by default; what is stored, where, and who sees it; keys server-side;
vendors named; no market data shown to others; how to delete your data; contact; a lawyer reviews both before
other users are admitted). Copy ours or write your own to that list; the tests look only for the headings.

Listing 04-19, Filename: `docs/site/privacy.md`:

{{file:docs/site/privacy.md}}

Listing 04-20, Filename: `docs/site/terms.md`:

{{file:docs/site/terms.md}}

### 04.7 Views and URLs

Listing 04-21, Filename: `src/invest_witus_site/pages/views.py`:

{{file:src/invest_witus_site/pages/views.py}}

A view is a function from `HttpRequest` to `HttpResponse`. `render` loads a template, fills it from the
dictionary you pass (the *context*) and wraps the result in a response. Notes:

- `waitlist` is the one view that handles two methods. After a valid POST it **redirects** instead of
  rendering: if it rendered, a browser refresh would post the form again. With the redirect, a refresh
  repeats a harmless GET of the thank-you page. The test checks the redirect chain.
- `mark_safe` is the only place HTML skips escaping. Django escapes every value a template prints, which is
  what makes templates safe with user input; the Markdown HTML is ours, from a file in the repo, so this one
  value is marked safe where it is made.
- `sign_in_stub` exists so the header's "Sign in" link goes somewhere true. A 404 would pass no test and
  would mislead a visitor. Chapter 07 replaces it.
- The `TODO(chapter 13)` is the whole Inbox mirror for now. The ecosystem contract (doc 02) says store first,
  mirror later, never block the person; the storing is done.

Listing 04-22, Filename: `src/invest_witus_site/pages/urls.py`:

{{file:src/invest_witus_site/pages/urls.py}}

Every path has a `name`, so templates write `{% url 'faq' %}` and a path can change in one place. The three
Markdown pages share one view and pass the slug as a keyword argument. The sign-in path is the one the
ecosystem registry already lists for this app (`signInHref` in `products.ts`); the app matches the registry,
not the other way round.

### 04.8 Templates: base, header, footer

Django's template language is HTML with `{{ variables }}`, `{% tags %}` and inheritance: a child template names
its parent with `{% extends %}` and fills the parent's `{% block %}`s (Django Software Foundation, n.d.-j).
With `APP_DIRS` on, Django looks in each app's `templates/` folder, so the files go under
`pages/templates/pages/`; the repeated `pages/` keeps names unique across apps.

Listing 04-23, Filename: `src/invest_witus_site/pages/templates/pages/base.html`:

{{file:src/invest_witus_site/pages/templates/pages/base.html}}

`{% load static %}` enables the `{% static %}` tag, which turns `brand/witus/favicon.svg` into its URL. The skip
link and `<main id="main" tabindex="-1">` are the smallest keyboard-accessibility shape: press Tab once at the
top of any page, press Enter, and focus lands on the content.

Listing 04-24, Filename: `src/invest_witus_site/pages/templates/pages/_header.html`:

{{file:src/invest_witus_site/pages/templates/pages/_header.html}}

The logo's `alt` is empty on purpose: the link's name is the text beside it, "Invest.WitUS", and a screen
reader would otherwise announce an image name and then the text. The sign-in link is the one the tests guard.
`{# ... #}` is a template comment; it never reaches the browser.

The footer needs two things every page shares: the ecosystem products and the year. Rather than passing them
from every view, a **context processor** adds them to every template's context:

Listing 04-25, Filename: `src/invest_witus_site/pages/ecosystem.py`:

{{file:src/invest_witus_site/pages/ecosystem.py}}

Listing 04-26, Filename: `src/invest_witus_site/pages/context_processors.py`:

{{file:src/invest_witus_site/pages/context_processors.py}}

The products are copied, as data, from the ecosystem's registry file; the footer recipe accepts that cost so
each app stays its own repository. Products marked "coming soon" are shown without a link, the way
witus.online's own footer shows them, because a link to a site that does not exist yet is a broken promise.
`settings.py` already names the processor in `TEMPLATES`.

Listing 04-27, Filename: `src/invest_witus_site/pages/templates/pages/_footer.html`:

{{file:src/invest_witus_site/pages/templates/pages/_footer.html}}

This is the ecosystem footer from the brand package's recipe (WitUS, 2026b): an optional logo and one-line
summary, the Rise Wellness callout, three columns, the copyright line. Two pieces are copied word for word and
stay that way: the callout, whose disclaimer was cleared with the partner (only the app name token changed),
and the copyright line. Their dashes are written as `&mdash;` and `&ndash;` so the source stays free of dash
characters, which this project's writing rule bans, while the page shows the recipe's exact text. The "Not
advice" line at the top of the footer is what puts those words on every page, which the PRD requires and a
test checks.

`<span class="sr-only">` holds text only screen readers get: "(opens in new tab)" after each external link,
because `target="_blank"` is otherwise a surprise.

### 04.9 The pages

Listing 04-28, Filename: `src/invest_witus_site/pages/templates/pages/home.html`:

{{file:src/invest_witus_site/pages/templates/pages/home.html}}

The landing page, section by section: the positioning line as the `<h1>`; what the app is; how it works; the
two courses, each marked "lesson coming" because no lesson URL exists yet (the authoritative-values rule:
never invent one); the "Report a bad actor" callout; the waitlist; a two-line roadmap, which is where the
footer's Roadmap link points; and the freeCodeCamp credit with its reference. There is no price, chart,
return or promise on it, and the test will tell you if one creeps in.

Listing 04-29, Filename: `src/invest_witus_site/pages/templates/pages/_waitlist_form.html`:

{{file:src/invest_witus_site/pages/templates/pages/_waitlist_form.html}}

`{% csrf_token %}` renders a hidden input holding a token tied to a cookie; `CsrfViewMiddleware` rejects any
POST without a matching pair (Django Software Foundation, n.d.-g). That is what the 403 test checks. Each field
is rendered with its own `<label for=...>`. Django adds `aria-invalid` and `aria-describedby` to a field with
errors on its own (Django Software Foundation, n.d.-b), so the error list is announced with the field.
`novalidate` turns off the browser's built-in checks, so the server's messages are the ones people see, which
is also what the tests see.

Listing 04-30, Filename: `src/invest_witus_site/pages/templates/pages/waitlist.html`:

{{file:src/invest_witus_site/pages/templates/pages/waitlist.html}}

Listing 04-31, Filename: `src/invest_witus_site/pages/templates/pages/waitlist_thanks.html`:

{{file:src/invest_witus_site/pages/templates/pages/waitlist_thanks.html}}

Listing 04-32, Filename: `src/invest_witus_site/pages/templates/pages/markdown_page.html`:

{{file:src/invest_witus_site/pages/templates/pages/markdown_page.html}}

Listing 04-33, Filename: `src/invest_witus_site/pages/templates/pages/contact.html`:

{{file:src/invest_witus_site/pages/templates/pages/contact.html}}

The contact address is the ecosystem's, from the footer recipe, not a guess; in this phase email is the only
route, and chapter 13 adds the in-app form.

Listing 04-34, Filename: `src/invest_witus_site/pages/templates/pages/sign_in_stub.html`:

{{file:src/invest_witus_site/pages/templates/pages/sign_in_stub.html}}

### 04.10 Static files: the logo and the stylesheet

Static files live in each app's `static/` folder and `runserver` serves them at `STATIC_URL` while `DEBUG` is
on (Django Software Foundation, n.d.-f). A server needs `collectstatic` and a file server; that is chapter 06.

Copy the WitUS logo files. The ecosystem keeps one brand package and each app copies the variant it uses
(WitUS, 2026a). This app uses the default, `04-orbit-type`, which is drawn for dark backgrounds, so the site is
dark. The six files (`favicon.svg`, `favicon-16.png`, `favicon-32.png`, `favicon-180.png`, `logomark.svg`,
`wordmark.svg`) go into `src/invest_witus_site/pages/static/brand/witus/`. Take them from the reference
repository's tree at `v04` (Browse link below) or from the raw URLs the brand package's README lists.

Listing 04-35, Filename: `src/invest_witus_site/pages/static/pages/site.css`:

{{file:src/invest_witus_site/pages/static/pages/site.css}}

One hand-written stylesheet. The ecosystem's TypeScript apps use Tailwind; this repository has no Node
toolchain, and a Python tutorial should not grow one for a landing page, so plain CSS with a few custom
properties does the job. The parts that matter for accessibility: a visible focus outline on every control,
link and button targets at least 2.75rem tall, muted text that still reads against the dark surface, and
`.sr-only` and `.honeypot`, which hide things the right way for the right audience.

### 04.11 Run it

Listing 04-36, Terminal:

```sh
cp .env.example .env
uv run python manage.py migrate
uv run --env-file .env python manage.py runserver
```

```text
Operations to perform:
  Apply all migrations: pages
Running migrations:
  Applying pages.0001_initial... OK
...
Starting development server at http://127.0.0.1:8000/
```

Open http://127.0.0.1:8000/. Press Tab through the header; its last stop is "Sign in". Join the waitlist
twice with the same address in different capitals; the thank-you page is the same both times. Read `/faq/`,
`/privacy/` and `/terms/`; press "Where to report" and watch the page jump to the heading. `/nope/` is a 404.

`migrate` created `data/private/invest-witus.sqlite3`. `git status` must list neither it nor `.env`.

### 04.12 Green

Listing 04-37, Terminal:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

```text
90 passed in 0.77s
All checks passed!
57 files already formatted
0 errors, 0 warnings, 0 informations
```

Forty-two new tests and the forty-eight from before. `uv run pytest -m smoke` runs the eight sign-in checks
alone; chapter 06 runs that set against every deployment.

## Checkpoint

- `uv run pytest` prints `90 passed`; ruff and pyright pass.
- `uv run --env-file .env python manage.py runserver` serves `/`, `/faq/`, `/privacy/`, `/terms/`, `/contact/`
  and `/auth/witus/login/`, each with the header and the footer.
- Joining the waitlist twice keeps one row:
  `uv run python manage.py shell -c "from invest_witus_site.pages.models import WaitlistEntry; print(WaitlistEntry.objects.count())"`.
- `git status` shows neither `.env` nor anything under `data/private/`.
- Commit and push: `git add -A && git commit -m "Chapter 04: the public landing page"`.

## Exercises

1. The FAQ's headings have ids now. Python-Markdown's `toc` extension also builds a table of contents
   (`converter.toc`, after `convert`). Render it at the top of `/faq/` as an "On this page" list. Keep every
   chapter 04 test green.
2. Move the roadmap off the landing page: write `docs/site/roadmap.md`, add it to `PAGES` and to `urls.py` at
   `/roadmap/`, and point the footer's Roadmap link at it. Which test tells you the footer still works?
3. A person who types their email with a trailing period (`ada@example.com.`) is told "Enter a valid email
   address." Decide whether the form should fix it for them or tell them, write the test for your answer, then
   make it pass.

## If you get stuck

- Browse: https://github.com/dapperAuteur/invest-witus/tree/v04
- Diff for this chapter: https://github.com/dapperAuteur/invest-witus/compare/v03...v04
- Zip: https://github.com/dapperAuteur/invest-witus/archive/v04.zip
- Take the reference's files:
  `git fetch reference --tags && git checkout v04 -- src tests docs/site manage.py pyproject.toml .env.example scripts`,
  then `uv sync`.
- `ImportError: No module named 'invest_witus_site'` after the files exist: `module-name` in `pyproject.toml`
  does not list it, or you did not run `uv sync` after adding it.
- `TemplateDoesNotExist: pages/home.html`: the app is missing from `INSTALLED_APPS`, or the file is at
  `templates/home.html` instead of `templates/pages/home.html`.
- `DisallowedHost`: the host you opened is not in `DJANGO_ALLOWED_HOSTS` (the default covers `localhost` and
  `127.0.0.1`).
- `CSRF verification failed`: the form is missing `{% csrf_token %}`.
- The page is unstyled and the logo is missing under `runserver`: `DJANGO_DEBUG` is not `1`. With debug off,
  Django does not serve static files; chapter 06 handles that for a server.
- `no such table: pages_waitlistentry`: run `uv run python manage.py migrate`.
- pyright says a field's type is "partially unknown": the `[str, str]` annotation is missing on that field.

## What we learned

- A Django project is settings plus a root URL list; an app is a package with models, views, URLs, templates
  and static files.
- Settings read the environment and default to the safe value, never the convenient one.
- A URL pattern names a view; a view returns a response; templates extend a base and include partials; a
  context processor adds the same values to every page.
- A model is a table; a migration is the reviewed, versioned change that creates it.
- Forms validate on the server; CSRF tokens stop cross-site posts; a redirect after POST stops double
  submits; a honeypot catches bots.
- A link's accessible name is its text. One link in this app is named "Sign in", and a test keeps it so.
- Public pages are information, not advice, and a narrow test keeps tables and percentages off them.

## Next

Chapter 05 starts from tag `v04` and adds the data behind the app: accounts, securities and holdings entered
from statements, with the Django admin as the first back office, where the waitlist becomes a list you can
read.

## References

Astral. (n.d.-a). *Build backend*. uv documentation. https://docs.astral.sh/uv/concepts/build-backend/
(retrieved October 27, 2026)

Astral. (n.d.-b). *Command-line reference*. uv documentation. https://docs.astral.sh/uv/reference/cli/
(retrieved October 27, 2026)

Django Software Foundation. (n.d.-a). *Deployment checklist*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/ (retrieved October 27, 2026)

Django Software Foundation. (n.d.-b). *Django 5.0 release notes*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/releases/5.0/ (retrieved October 27, 2026)

Django Software Foundation. (n.d.-c). *Django 5.2 release notes*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/releases/5.2/ (retrieved October 27, 2026)

Django Software Foundation. (n.d.-d). *Django settings*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/topics/settings/ (retrieved October 27, 2026)

Django Software Foundation. (n.d.-e). *Download Django* [Supported versions]. https://www.djangoproject.com/download/
(retrieved October 27, 2026)

Django Software Foundation. (n.d.-f). *How to manage static files (e.g. images, JavaScript, CSS)*. Django 5.2
documentation. https://docs.djangoproject.com/en/5.2/howto/static-files/ (retrieved October 27, 2026)

Django Software Foundation. (n.d.-g). *How to use Django's CSRF protection*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/howto/csrf/ (retrieved October 27, 2026)

Django Software Foundation. (n.d.-h). *Migrations*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/topics/migrations/ (retrieved October 27, 2026)

Django Software Foundation. (n.d.-i). *Models*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/topics/db/models/ (retrieved October 27, 2026)

Django Software Foundation. (n.d.-j). *Templates*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/topics/templates/ (retrieved October 27, 2026)

Django Software Foundation. (n.d.-k). *Testing tools*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/topics/testing/tools/ (retrieved October 27, 2026)

Django Software Foundation. (n.d.-l). *URL dispatcher*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/topics/http/urls/ (retrieved October 27, 2026)

Django Software Foundation. (n.d.-m). *Working with forms*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/topics/forms/ (retrieved October 27, 2026)

pytest-dev. (n.d.-a). *Configuring Django settings*. pytest-django documentation.
https://pytest-django.readthedocs.io/en/latest/configuring_django.html (retrieved October 27, 2026)

pytest-dev. (n.d.-b). *Django helpers*. pytest-django documentation.
https://pytest-django.readthedocs.io/en/latest/helpers.html (retrieved October 27, 2026)

Python-Markdown. (n.d.-a). *Extensions API*. https://python-markdown.github.io/extensions/api/ (retrieved
October 27, 2026)

Python-Markdown. (n.d.-b). *Table of Contents extension*. https://python-markdown.github.io/extensions/toc/
(retrieved October 27, 2026)

typeddjango. (n.d.). *django-stubs* [README]. GitHub. https://github.com/typeddjango/django-stubs (retrieved
October 27, 2026)

W3C. (2026, October 21). *Accessible name and description computation 1.2* [W3C Working Draft].
https://www.w3.org/TR/accname-1.2/ (retrieved October 27, 2026)

WitUS. (2026a). *WitUS ecosystem brand package* [README]. Internal document, `gemini/witus/public/brand/README.md`
(read October 27, 2026)

WitUS. (2026b). *Ecosystem footer recipe*. Internal document, `gemini/witus/public/brand/footer-recipe.md` (read
October 27, 2026)

WitUS. (2026c). *Shared UI, UX and DX standard*. Internal document, `gemini/witus/docs/shared-ui-ux-dx.md` (read
October 27, 2026)
