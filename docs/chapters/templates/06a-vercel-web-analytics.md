# Chapter 06a: Vercel Web Analytics: page views, switched on per environment

**Starts from:** tag `v06`. **Ends at:** tag `v06a`.
**Written against:** Python 3.14.10, uv 0.13.6, Django 5.2.18, and Vercel's Web Analytics documentation as read
on October 28, 2026 (the quickstart last updated June 8, 2026; pricing, August 25, 2026; privacy, June 26, 2026).
Dashboards change; every label below has its source in the references, and when the page and this text
disagree, the page wins.
**Goal:** the public pages count their visitors with Vercel Web Analytics, and only where the owner turned it
on. Two script tags in the base template, rendered when the app runs on Vercel and one variable says so. The
script's path comes from the project, through a variable, with a labeled fallback. The privacy page says what
is collected. Nothing is installed and nothing new runs.
**Time:** 30 to 45 minutes for the code and tests, then 10 minutes in the Vercel dashboard.

This is an addendum to chapter 06, numbered `06a` so that it sorts after the deploy chapter it belongs to and
before chapter 07, which it does not change. The listings are generated from tag `v06a` by
`scripts/render_chapter.py`, as in every chapter from 04 on.

## What you will learn

- **A switch that is on only on a server, and only when the owner says so:** two conditions in one
  setting, and tests for each combination.
- **A context processor:** the one place a value is handed to every template.
- **What a plain-HTML analytics snippet does:** a two-line queue, a deferred script, and why the order
  matters.
- **A value that belongs to the host:** the script's path is the project's, so it is copied, never typed; the
  fallback is labeled as one.
- **Reading a rendered page in a test:** counting tags, checking their order, and flipping a setting at
  request time with pytest-django's `settings` fixture.
- **Saying what a vendor collects, in your own words,** from the vendor's own page, with the date you read it.

## Before the code: what is counted, what it costs, and why this and not PostHog

**What it is.** Vercel Web Analytics counts page views with a script in the page. Each page view is an
event (Vercel, 2026b), recorded with the page, the referrer, the country and the browser among other things
(Vercel, 2026c). For plain HTML sites the quickstart gives two script tags and says there is no package to
install and no route support; this site is server-rendered pages with no router, so the plain-HTML
instructions are the ones to follow (Vercel, 2026a).

**What it costs.** The pricing page, read October 28, 2026: a Hobby team gets 50,000 events a month, shared
across every project in the team, and cannot buy more; past the limit "a three day grace period will start
before Vercel will stop capturing events", and collection resumes after seven days or on an upgrade. The
reporting window on Hobby is one month. A Pro team pays $0.03 per 1,000 events with a twelve-month window
(Vercel, 2026b). A landing page with a waitlist is far inside the free allowance; the numbers are here so that
the owner knows what a traffic spike does.

**What it collects.** The privacy page says the script uses no third-party cookies and tells visitors apart by
a hash made from the incoming request, discarded after 24 hours, and that a page view is not tied to an
individual or an IP address. A data point may hold the timestamp, the URL, the referrer, filtered query
parameters, the country, region and city, the operating system, the browser, the device type and the script
version (Vercel, 2026c). Section 06a.4 writes that into the privacy page.

**Why now, and why not PostHog.** The WitUS ecosystem's analytics standard is PostHog, one shared project with
per-app differentiation, chosen because Sign in with WitUS makes cross-app journeys possible (WitUS, 2026).
That value arrives with sign-in, so PostHog is a later chapter of this tutorial, after chapter 07. The
landing page is live before any of that, and it has one question: does anyone arrive, and from where. Vercel
Web Analytics answers it with no package, no new process and no key, and this chapter does not replace the
standard; it fills the gap until the standard's chapter.

**The rule for the path.** The quickstart's snippet reads `<script defer src="/<unique-path>/script.js">`, and
its note says that enabling Analytics "will add new routes (scoped at `/_vercel/insights/*` and
`/<unique-path>/*`) after your next deployment" (Vercel, 2026a). The unique path is the project's. By the
authoritative-values rule in `CLAUDE.md`, a value owned by Vercel is copied from Vercel, so the path comes in
through a variable. The code needs a value when none is set, and it uses the shared `/_vercel/insights/`
route the quickstart names, with the file name from the snippet. That is a fallback, labeled as one in the
settings, in the template and in `.env.example`; the text never claims it is what your dashboard shows. The
dashboard step says how to tell whether it works.

## Steps

### 06a.1 The tests

Listing 06a-1, Filename: `tests/test_ch06a.py`:

{{file:tests/test_ch06a.py}}

Things to notice:

- **`fresh_settings` and `production_env`** are chapter 06's helpers, copied in so the file stands alone like
  every other checkpoint file. The first imports the settings module again with exactly the variables a test
  names; the second is a production-shaped environment with the analytics flag unset.
- **Seven tests for one switch.** A laptop, a laptop with debug on and the flag set, a server off Vercel with
  the flag set, Vercel without the flag, Vercel with the flag, the path override, and a path that is not a
  path. Each is a row in the table you would otherwise keep in your head.
- **The `settings` fixture** from pytest-django lets a test set a Django setting for its own duration and
  "automatically revert any changes made to the settings" afterwards (pytest-django, n.d.). The two rendering
  tests use it to flip the switch at request time without a server, which is also why the switch is read by a
  context processor on every request rather than once at import.
- **`html.count("<script") == 2`** says the public pages carry exactly the two tags when it is on, and the
  matching test with the switch off says they carry none at all. **`html.index`** three times gives the
  order: the queue first, then the deferred script, both before `</body>`.
- **`SHIM`** is the first tag's one line, byte for byte from the quickstart. If Vercel changes it, this
  constant and the template change together.

Run it:

Listing 06a-2, Terminal:

```sh
uv run pytest tests/test_ch06a.py
```

```text
E       AttributeError: 'Settings' object has no attribute 'VERCEL_ANALYTICS_ENABLED'
...
13 failed, 3 passed in 0.62s
```

Red first: the setting does not exist, so every test that reads it fails with an `AttributeError`, and the pages
that should carry two tags fail on the count. The three that pass say the pages carry no script, which was true
before this chapter as well.

### 06a.2 The switch, in the settings

The new block is at the end of the file; everything above it is chapter 06's.

Listing 06a-3, Filename: `src/invest_witus_site/settings.py`:

{{file:src/invest_witus_site/settings.py}}

Three lines of code and one refusal:

- **`VERCEL_ANALYTICS_ENABLED`** is true only when `ON_VERCEL` (chapter 06's reading of Vercel's own
  `VERCEL=1`) and `VERCEL_ANALYTICS=1` both hold. The second is a variable the owner sets per environment, so
  Production can count while Preview stays silent. `runserver` on a laptop has neither, so it never emits the
  tags; and debug on Vercel is refused higher in the file, so a debug server never does either.
- **`VERCEL_ANALYTICS_SCRIPT_PATH`** is the variable's value, or the fallback. The comment says what the
  fallback is and is not.
- **The refusal.** A value that does not start with `/` is not a path on this site; the settings refuse to
  start and the message says what to set, in the chapter 06 style: a typo in a dashboard fails when the
  function starts, where the log shows it.

### 06a.3 The context processor and the template

Listing 06a-4, Filename: `src/invest_witus_site/pages/context_processors.py`:

{{file:src/invest_witus_site/pages/context_processors.py}}

A context processor is a callable that takes "a request object as their argument and return[s] a dictionary
of items to be merged into the context", listed under `context_processors` in `TEMPLATES` (Django Software
Foundation, n.d.). Chapter 04 wrote this one for the footer's product list and the year; two keys join them.
Reading `settings` inside the function, on every request, is what lets a test flip the switch after the
module has loaded.

Listing 06a-5, Filename: `src/invest_witus_site/pages/templates/pages/base.html`:

{{file:src/invest_witus_site/pages/templates/pages/base.html}}

What the tags do, and where they sit:

- **The first tag** defines `window.va` as a function that pushes its arguments onto `window.vaq`, a queue,
  unless a `va` already exists. Nothing on this site calls it; the snippet defines it so that a call made
  before the script arrives (a custom event, on the plans that have them) is queued rather than lost. That
  is why it comes first.
- **The second tag** loads the script with `defer`: the browser fetches it while parsing goes on and runs it
  "after the document has been parsed, but before firing `DOMContentLoaded`" (MDN contributors, 2026). The
  page's own content never waits for it.
- **At the end of `<body>`,** after the footer, inside `{% if vercel_analytics_enabled %}`. With the switch
  off, the page has no `<script>` at all, which the tests check.
- **`{{ vercel_analytics_script_path }}`** is escaped by Django's template engine like any other variable, so
  the value can only ever land inside the quotes of `src`.
- **The comment** repeats, next to the tags, what the fallback is. Someone reading the page source in six
  months should not have to open the settings to learn that.

### 06a.4 The names, and the privacy page

Listing 06a-6, Filename: `.env.example`:

{{file:.env.example}}

Both names are listed with empty values, like the rest of the file: a laptop leaves them empty, and the
server's values are typed into Vercel's dashboard, never into a file.

Listing 06a-7, Filename: `docs/site/privacy.md`:

{{file:docs/site/privacy.md}}

The new section is the privacy page's summary of 06a's "What it collects", dated twice: once for the change,
once for the day the vendor's page was read. The "Last updated" line at the top moved with it, as the page's
own last section promises, and Vercel's entry in the vendors list now says what it does. The wording stays
inside what Vercel's page says: "no third-party cookies" rather than "no cookies", because that is the claim
the page makes.

### 06a.5 Green on the laptop

Listing 06a-8, Terminal:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

```text
156 passed in 3.49s
All checks passed!
80 files already formatted
0 errors, 0 warnings, 0 informations
```

Sixteen new tests. Then see the tags without a server. `VERCEL=1` turns on chapter 06's SSL redirect, so a
plain `curl` to `runserver` would get a 301; the test client can ask over HTTPS instead, from `manage.py
shell`, with the switch on:

Listing 06a-9, Terminal:

```sh
VERCEL=1 VERCEL_ANALYTICS=1 DJANGO_SECRET_KEY=not-a-secret-just-for-this-check \
DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:////tmp/invest-witus-06a.sqlite3 \
uv run python manage.py shell -c "from django.test import Client; r = Client().get('/', secure=True); print(r.status_code); print(r.content.decode()[-230:])"
```

```text
200
</div>
</footer>

  <script>
    window.va = window.va || function () { (window.vaq = window.vaq || []).push(arguments); };
  </script>
  <script defer src="/_vercel/insights/script.js"></script>

</body>
</html>
```

(The shell prints a line about objects imported, and the template's comments leave a few blank lines; both
are trimmed here.) Drop `VERCEL_ANALYTICS=1` from the same command and the tail is `</footer>`, `</body>`,
`</html>` with no script between them. Delete the temporary database afterwards. The path printed is the
fallback, because no `VERCEL_ANALYTICS_SCRIPT_PATH` was set; the dashboard decides the real one.

### 06a.6 The dashboard

Labels are from Vercel's quickstart as read on October 28, 2026 (Vercel, 2026a). Your project is your own;
the reference repository's is the owner's.

1. **Enable Web Analytics.** On the Vercel dashboard, open **Analytics** in the sidebar and select the
   project, then click the **Enable** button in the header. The quickstart's note: "Enabling Web Analytics
   will add new routes (scoped at `/_vercel/insights/*` and `/<unique-path>/*`) after your next deployment."
2. **Look for the path.** The quickstart writes the script's path as `/<unique-path>/script.js` and does not
   say where the dashboard shows the project's own value, so look on the project's Analytics page after
   enabling, and in the quickstart's HTML instructions opened from your project. If you find a path, it is
   the value of `VERCEL_ANALYTICS_SCRIPT_PATH` in the next step. If you find none, leave that variable unset;
   the fallback applies, and step 5 tells you whether it works.
3. **Set the variables.** The project → **Settings** → **Environment Variables**: `VERCEL_ANALYTICS` with the
   value `1` for **Production** (add **Preview** only if preview page views should count; they draw on the
   same allowance), and `VERCEL_ANALYTICS_SCRIPT_PATH` with the path from step 2, if there was one.
   Neither is a secret.
4. **Redeploy** the latest production deployment (**Deployments** → the menu on the deployment →
   **Redeploy**): the function reads its variables when it starts, and the routes from step 1 arrive with
   the next deployment.
5. **Verify in the browser.** Open the production URL with the developer tools' **Network** tab open. The
   quickstart: "you should be able to see a Fetch/XHR request in your browser's Network tab from
   `/<unique-path>/view` when you visit any page." View the page source as well: the two tags sit before
   `</body>`. If the request for `script.js` is a 404, the path is wrong; take the one the dashboard shows
   and repeat steps 3 and 4.
6. **View the data.** The dashboard → the project → **Analytics** in the sidebar. "After a few days of
   visitors, you'll be able to start exploring your data" (Vercel, 2026a).

## Checkpoint

- `uv run pytest` prints `156 passed`; ruff and pyright pass.
- `uv run --env-file .env python manage.py runserver` serves the public pages with no `<script>` in them.
- Listing 06a-9 prints the two tags; without `VERCEL_ANALYTICS=1` it prints none.
- `/privacy/` carries the Analytics section with both dates.
- On Vercel, after 06a.6: a request to `/…/view` in the Network tab, and no 404 for `script.js`.
- Commit and push: `git add -A && git commit -m "Chapter 06a: Vercel Web Analytics"`.

## Exercises

1. The admin's pages do not extend `base.html`, so the owner's back office is never counted. Write a test
   that proves it: sign in with `admin_client`, set the switch on, and assert that `/admin/` carries no
   `window.va`.
2. The settings refuse a path that does not start with `/`. Decide whether a path that does not end in
   `script.js` should be refused too, and write the test for the decision either way.
3. The pricing page lists custom events for Pro and Enterprise only. Read the custom-events page the quickstart
   links to and write,
   in one paragraph in your own notes, which single event this site would send if it could, and why the
   waitlist's thank-you page is a better signal than a button click.

## If you get stuck

- Browse: https://github.com/dapperAuteur/invest-witus/tree/v06a
- Diff for this chapter: https://github.com/dapperAuteur/invest-witus/compare/v06...v06a
- Zip: https://github.com/dapperAuteur/invest-witus/archive/v06a.zip
- Take the reference's files. Chapter 06a changed `src/invest_witus_site/settings.py`,
  `src/invest_witus_site/pages/context_processors.py`, `src/invest_witus_site/pages/templates/pages/base.html`,
  `.env.example` and `docs/site/privacy.md`, and added `tests/test_ch06a.py`. Nothing moved:
  `git fetch reference --tags && git checkout v06a -- src/invest_witus_site/settings.py src/invest_witus_site/pages/context_processors.py src/invest_witus_site/pages/templates/pages/base.html .env.example docs/site/privacy.md tests/test_ch06a.py`.
- `AttributeError: 'Settings' object has no attribute 'VERCEL_ANALYTICS_ENABLED'`: the block from 06a.2 is
  missing, or sits above `ON_VERCEL` in the file and raised a `NameError` that the test run shows earlier.
- `test_the_two_tags_render_when_analytics_is_on` fails on the count: the tags are outside the
  `{% if %}`, or the context processor does not pass `vercel_analytics_enabled` (check the key's spelling in
  both files).
- `test_no_tags_render_while_analytics_is_off` fails: a `<script>` from somewhere else on the page; this
  site has none, so look for a pasted snippet in another template.
- `ImproperlyConfigured: VERCEL_ANALYTICS_SCRIPT_PATH must be a path` on Vercel: the variable holds a full
  URL or a value with quotes around it; it wants a path such as `/<unique-path>/script.js`.
- On Vercel the tags are missing from the page source: `VERCEL_ANALYTICS` is not `1` on that environment, or
  the deployment was built before the variable existed; redeploy. If system environment variables are off
  (chapter 06, 06.8 step 5), `VERCEL=1` never arrives and the switch stays off.
- The script request is a 404 and the Network tab shows no `/…/view`: the fallback path is not what your
  project serves; find the path on the Analytics page and set the variable.

## What we learned

- A switch with two conditions, one from the host and one from the owner, covers laptop, preview and
  production with no code change between them, and seven short tests cover the table.
- A context processor hands a value to every template; reading settings inside it keeps the value live for
  tests.
- The plain-HTML snippet is a queue and a deferred script; the queue comes first, the script never blocks the
  page, and with the switch off the page has no script at all.
- A value the host owns comes in through a variable; a fallback may exist, labeled as a fallback, with a
  behavior check (the `view` request) rather than a guess deciding whether it is right.
- A privacy page repeats the vendor's claims and no more, with the date they were read.
- The ecosystem's PostHog standard is not replaced; it waits for sign-in, when it has something to join.

## Next

Chapter 07 replaces the stub at `/auth/witus/login/` with Sign in with WitUS: OIDC against the ecosystem's
identity provider, EdDSA id tokens, a callback that matches a user by the WitUS user id and never by email, and
a sign-out. Nothing in this chapter changes for it.

## References

Django Software Foundation. (n.d.). *The Django template language: For Python programmers*. Django 5.2
documentation. https://docs.djangoproject.com/en/5.2/ref/templates/api/ (retrieved October 28, 2026)

MDN contributors. (2026, May 9). *<script>: The script element*. MDN Web Docs.
https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/script (retrieved October 28, 2026)

pytest-django. (n.d.). *Django helpers*. pytest-django documentation.
https://pytest-django.readthedocs.io/en/latest/helpers.html (retrieved October 28, 2026)

Vercel. (2026a, June 8). *Getting started with Vercel Web Analytics*. Vercel documentation.
https://vercel.com/docs/analytics/quickstart (retrieved October 28, 2026)

Vercel. (2026b, August 25). *Pricing for Web Analytics*. Vercel documentation.
https://vercel.com/docs/analytics/limits-and-pricing (retrieved October 28, 2026)

Vercel. (2026c, June 26). *Privacy and compliance*. Vercel documentation.
https://vercel.com/docs/analytics/privacy-policy (retrieved October 28, 2026)

WitUS. (2026). *PostHog across the ecosystem: One shared project, per-app differentiation* [Internal plan 26,
decisions locked July 28, 2026]. `gemini/witus/plans/26-posthog-ecosystem-rollout.md` (read October 28, 2026)
