# Chapter 13: Report a bug or ask a question: the in-app reporter

**Starts from:** tag `v12`. **Ends at:** tag `v13`.
**Written against:** Python 3.14.10, uv 0.13.6, Django 5.2.18, httpx 0.28.1, and WitUS Inbox's webhook contract
and ingest code as read on October 29, 2026.
**Goal:** every page gets a "Report a problem or ask a question" link, in the header and the footer, signed in
or not. The form takes a kind (a bug, an idea for a feature, or a question), a message and the page you were on,
filled in from the page you came from. The report is saved in the app's own database first, then sent to WitUS
Inbox, the operator's one inbox for every WitUS app, as a signed request. A send that fails never touches the
person who wrote the report: the row keeps the reason, and the nightly job or the admin's **Send again** tries
it later. Chapter 04's waitlist gets the same treatment, so a new signup reaches Inbox too.
**Time:** 4 to 5 hours for the code and tests. The laptop walk-through takes 10 minutes.

The listings in this chapter are not typed in by hand. `scripts/render_chapter.py` pastes the real files from
tag `v13` into the chapter text, so what you read and what the tests run are the same bytes.

## What you will learn

- **HMAC signing with `hmac` and `hashlib`:** a shared secret, a timestamp and the exact bytes of a body, and
  why the bytes you sign must be the bytes you send.
- **Reading a contract from the other side's code:** the receiver's schema, limits and answers, checked in its
  own source rather than in a summary of it.
- **Local first, then send:** a row that is the record, a copy that may fail, and the columns that say which.
- **Background work without a worker:** "later" as a step in a job that already runs every night, plus a button.
- **A lock around a network call:** `select_for_update` in a transaction, so two senders at once send once.
- **A rate limit with no shared memory:** counting rows in the database, keyed by a hash of the address, never
  the address.
- **Tests that never leave the process:** httpx's `MockTransport` with a fake that verifies the signature the way
  the receiver does, and a guard in `conftest.py` that fails any test that tries to reach the real thing.

## Before the code: what the PRD asks, and eight decisions

**What the PRD asks.** Section 7.8, the in-app reporter: a "Report" control that opens a short form with a kind,
a message, and automatically the page path, the method page's view (A, B or C), the app version and the
browser's user agent. "Stored locally first (the system of record), then mirrored to WitUS Inbox in the
background with a signed request. A failed mirror never blocks the user and is retried by the daily job." An
admin list with a status (new, triaged, done) and a management command that prints open reports. Acceptance: the
payload never carries keys, holdings, prices or journal text unless the person typed them; each kind has its own
`form_type`, a bug goes as `priority: "high"`; and "A test signs a body and verifies it with the Inbox contract's
algorithm." Doc 02, section 1, has the contract as the ecosystem report summarized it, and chapter 04 left a
`TODO(chapter 13)` in the waitlist view.

**Decision 1: the contract comes from Inbox's code, not from a summary of it.** Doc 02 was written from a report
about Inbox. This chapter reads Inbox's own files: `docs/webhook-contract.md`, the ingest route
`app/api/ingest/route.ts`, `lib/hmac.ts` and `lib/ingest-sources.ts` (WitUS Inbox, n.d.). Five things in the code
are not in the summary, and each changed the client. `submitter_name` must be at least one character, so an empty
name is left out of the body rather than sent as `""`. Inbox refuses a secret shorter than 32 characters for its
whole source list, so a shorter one here can never work and switches the client off with that reason. The
five-minute window is checked both ways (`|now - ts| > 300`), so a retry must sign again with a new timestamp:
a stored signature is worthless minutes later. A 500 means Inbox's database failed, which is worth retrying,
while a 401 lumps together an unknown source, a wrong secret and a clock more than five minutes off, and Inbox
says which only in its own logs. And a source is registered by adding `{"slug", "hmac_secret"}` to the
`INGEST_SOURCES` environment variable on the Inbox project and redeploying it: Inbox's `.env.example` mentions a
`webhook_source` table, but no code reads it. Decisions log, row 119.

**Decision 2: sign the bytes you send.** `Submission.body()` serializes once, with `json.dumps(...,
ensure_ascii=True, separators=(",", ":"))`, into ASCII bytes, and `send()` signs those bytes and passes the same
object to httpx as `content=`. Never `json=`: httpx would serialize again, and any difference in spacing or key
order breaks the signature. `ensure_ascii` writes every other character as a `\u` escape, so the bytes are the
same whether Inbox reads them as bytes or as UTF-8 text. The signature is `hmac.new(secret, f"{ts}.".encode() +
raw, hashlib.sha256).hexdigest()` behind `sha256=` (Python Software Foundation, n.d.). The timestamp is an
argument, so a test can sign a fixed one and compare it with a value computed by hand outside Python. Row 120.

**Decision 3: the row is the record, and it says where its copy is.** `Report` and `WaitlistMirror` share an
abstract base, `InboxDelivery`, with `inbox_status` (not tried yet, sent, failed, off), `sent_at`, Inbox's id,
`attempts`, `last_tried_at` and `last_error`. A report is saved before anything is sent, so Inbox down,
unregistered or switched off loses nothing. With the three `INBOX_` names unset the report is still saved, its
status is "off" with the reason, the form says forwarding is off, and nothing is sent; a learner's copy works
this way for good, and the owner reads reports in the admin. Row 121.

**Decision 4: send now, retry nightly, and lock while sending.** On Vercel a function stops when its response
is sent, so there is no "after the response" to send in. The view sends inline with a five-second timeout and
redirects whatever happened. "Later" is a step in chapter 08's cron route, after the paper orders: every unsent
row, oldest first, at most 25 a night, the waitlist's copies with the reports. A 4xx is that row's own problem
and the run goes on; a timeout or a 5xx stops the run, because every following row would wait out the same
timeout. **Send again** in the admin and `manage.py reports --send` do the same by hand. `deliver()` reads the
row again with `select_for_update()` inside a transaction, so the cron and a click at the same moment send it
once; on SQLite the lock does nothing and one writer at a time does the same job (Django Software Foundation,
n.d.). Inbox has no idempotency key, so a send that times out after Inbox stored it can arrive twice; the payload
carries `report_id`, so the operator can see a repeat. Row 122.

**Decision 5: three kinds, three form types.** A bug is `invest-witus-bug-report` with `priority: "high"`, which
makes Inbox text the operator; a feature is `invest-witus-feature-request` and a question
`invest-witus-support-question`, both `normal`. The names follow doc 02 and Tour Manager OS's help bubble, so
the WitUS Triage agent's categories (bug report, feature request, support question) line up. PRD 7.8's fourth
kind, "other", is left out: a question covers it, and a form with fewer choices is quicker to fill in. The payload
holds the kind, the message, `report_id`, the page, the view letter, the version, the user agent, whether the
person was signed in, a link to the row's admin page and the time; nothing from an account. A waitlist copy is
`waitlist-signup`, the name Inbox and the Triage agent already use for signups, at `normal`. Row 123.

**Decision 6: the form knows who is asking.** Signed out, the form asks for an email and requires it, so a reply
can reach the person; signed in, there is no email box, and the WitUS identity's email and name (chapter 07) go
with the report. "What page were you on" starts as the path of the `Referer` when it is a page of this site and
not the form itself, with the query string dropped, and the person can change or clear it. On a method page the
session's view letter goes too. A honeypot keeps simple bots out with the same thank-you a person gets, and CSRF
comes with the form. The thank-you page promises no reply time. Row 124.

**Decision 7: the rate limit counts rows.** Five reports an hour from one address and five from one signed-in
person; the sixth gets the form back with a 429 and a sentence. The count is a query on `Report.created_at`,
because Vercel's functions share no memory (decision 117 said the same for the price buttons). The address is
never stored: `client_key` is an HMAC of it under the app's secret key, cut to 32 hex characters. On Vercel the
address is the first entry of `X-Forwarded-For`, which Vercel overwrites with the client's public IP to prevent
spoofing (Vercel, n.d.-a); anywhere else it is the connection's own address, and a header a client sends to your
laptop is not trusted. Row 125.

**Decision 8: the waitlist's copy is its own row.** `WaitlistMirror` is one-to-one with `WaitlistEntry`, made
only when `join` creates the entry, so joining twice makes one copy, and a bot makes none. The `TODO(chapter 13)`
line in `pages/views.py` is gone. Row 126.

## Steps

### 13.1 The tests

Listing 13-1, Filename: `tests/test_ch13.py`:

{{file:tests/test_ch13.py}}

Things to notice:

- **The reference signature was computed outside Python.** `BY_HAND` comes from `openssl dgst -sha256 -hmac`,
  the command Inbox's own contract uses in its `curl` example, so the test does not check the code against
  itself.
- **`FakeInbox` is Inbox, ported.** It checks the source, the five-minute window and the HMAC the way
  `lib/hmac.ts` does, with `hmac.compare_digest`, then the parts of the schema this app could get wrong. A
  request signed over different bytes, or a year-old timestamp, gets Inbox's 401.
- **`answer` forces a status.** Setting `fake.answer = 401` or `500` makes the fake answer like Inbox does when
  something fails: the status and `{"ok":false}`, nothing more.
- **The retry test counts requests.** One failure, one retry, then nothing: `send_unsent()` finds no row, and
  `deliver()` on a sent row answers "already sent" without a request.
- **The log test reads every line.** `caplog` at DEBUG, then the secret, the message, the email and each
  signature must be absent; the source, the form type and the status must be present.

The second file is the shared one. Since chapter 05 every test gets the fast password hasher from it; now every
test also gets Inbox switched off and a transport that fails the test if anything tries to leave the machine, so
a `.env` or a shell with the real names set can never send a test's report to the real Inbox:

Listing 13-2, Filename: `tests/conftest.py`:

{{file:tests/conftest.py}}

Run the tests:

Listing 13-3, Terminal:

```sh
uv run pytest tests/test_ch13.py
```

```text
ImportError while loading conftest '.../tests/conftest.py'.
tests/conftest.py:12: in <module>
    from invest_witus_site.reports import inbox
E   ModuleNotFoundError: No module named 'invest_witus_site.reports'
```

Red before a single test runs: the shared file imports the app this chapter writes, so every test file stops
here until it exists. No package is added this chapter: `hmac`, `hashlib` and `json` are the standard library,
and httpx has been a dependency since chapter 07.

### 13.2 The settings, the app and its URLs

Three names join the settings, read from the environment like every other value, plus the commit Vercel
deploys:

Listing 13-4, Filename: `src/invest_witus_site/settings.py`:

{{file:src/invest_witus_site/settings.py}}

The new lines are the last block and one entry in `INSTALLED_APPS`. None of the three has a default: an Inbox URL
or slug written into the code would be a guessed value for another app's system. `VERCEL_GIT_COMMIT_SHA` is one
of Vercel's system variables, "The git SHA of the commit the deployment was triggered by" (Vercel, n.d.-b); on a
laptop it is empty.

Make the folder `src/invest_witus_site/reports/` with an empty `__init__.py`, an empty `migrations/__init__.py`,
`management/__init__.py` and `management/commands/__init__.py`, then the app's config:

Listing 13-5, Filename: `src/invest_witus_site/reports/apps.py`:

{{file:src/invest_witus_site/reports/apps.py}}

Listing 13-6, Filename: `src/invest_witus_site/urls.py`:

{{file:src/invest_witus_site/urls.py}}

Listing 13-7, Filename: `src/invest_witus_site/reports/urls.py`:

{{file:src/invest_witus_site/reports/urls.py}}

### 13.3 The client

Listing 13-8, Filename: `src/invest_witus_site/reports/inbox.py`:

{{file:src/invest_witus_site/reports/inbox.py}}

Things to notice:

- **`load_config()` names variables, never values.** Each reason ("INBOX_INGEST_SECRET not set", "shorter than
  32 characters") is safe to show the owner in the admin and in the cron's JSON.
- **`InboxConfig.secret` has `field(repr=False)`.** A config in a traceback prints its URL and slug and no
  secret, which chapter 11 did by hand with `__repr__`.
- **`sign()` takes bytes and returns the header value.** The dot and the timestamp are encoded and joined to the
  raw bytes; nothing is decoded on the way.
- **`send()` passes `content=raw`.** Not `json=`, which would serialize a second time.
- **Three exceptions, one log line each.** `InboxRefused` for a 4xx (the same request will fail the same way),
  `InboxUnavailable` for a timeout, a dropped connection, a 5xx or a 2xx without an id (worth trying later),
  `InboxNotConfigured` before anything is sent. `failed()` logs the source, the form type and the status, and
  nothing else.
- **`transport` is the seam,** as in chapters 07, 08 and 11: `None` in production, a `MockTransport` in tests
  (Encode, n.d.).

### 13.4 The rows

Listing 13-9, Filename: `src/invest_witus_site/reports/models.py`:

{{file:src/invest_witus_site/reports/models.py}}

`InboxDelivery` is abstract, so it has no table: each model below gets its columns. Each child's `Meta` inherits
`InboxDelivery.Meta`, which Django turns back into a concrete table and pyright accepts as an override.
`submission()` is the one place a row becomes what Inbox receives, so the view, the cron and the admin all send
the same thing. `FORM_TYPES` sits at module level with string keys, so pyright reads the priority as the literal
`"normal"` or `"high"` the client expects.

Make the migration and format it:

Listing 13-10, Terminal:

```sh
uv run --env-file .env python manage.py makemigrations reports
uv run ruff format .
```

Listing 13-11, Filename: `src/invest_witus_site/reports/migrations/0001_initial.py`:

{{file:src/invest_witus_site/reports/migrations/0001_initial.py}}

Two new tables and no column on an old one, so the release before this one keeps working while the migrate
workflow runs.

### 13.5 Sending now, and sending later

Listing 13-12, Filename: `src/invest_witus_site/reports/delivery.py`:

{{file:src/invest_witus_site/reports/delivery.py}}

Things to notice:

- **`deliver()` never raises for Inbox.** Every answer becomes an `Outcome` and a few columns. The caller (the
  view, the cron, the admin) decides what to say.
- **The lock is a second read.** `locked_copy()` reads the row again with `select_for_update()` inside
  `transaction.atomic()`. On Postgres a second caller waits at that line, then sees `sent_at` and sends nothing.
  `of=("self",)` locks the mirror's row and not the waitlist entry `select_related` joins (Django Software
  Foundation, n.d.).
- **Off is not an attempt.** With Inbox off the row's status reads "Off, will retry" and `attempts` stays where
  it was; the count is of requests that left the app.
- **The nightly run stops on a timeout.** `send_unsent()` treats a refusal as that row's and goes on, and treats
  a timeout or a 5xx as Inbox's and stops, with the reason in `stopped`.

### 13.6 The form, the view and the links

Listing 13-13, Filename: `src/invest_witus_site/reports/forms.py`:

{{file:src/invest_witus_site/reports/forms.py}}

`__init__` takes `signed_in`: signed in, the email field is removed; signed out, it is required. `page_path`
keeps a path on this site without its query string, and keeps anything else as typed, because the person may mean
it.

Listing 13-14, Filename: `src/invest_witus_site/reports/views.py`:

{{file:src/invest_witus_site/reports/views.py}}

Things to notice:

- **Save, send, redirect.** `Report.objects.create(...)`, then `deliver(row)`, then the thank-you, whatever
  `deliver` returned.
- **The honeypot answers like a person's form.** A bot gets the same redirect, and nothing is saved or sent.
- **The limit runs before the save.** Five rows in the last hour from this `client_key`, or from this user,
  and the form comes back with status 429.
- **`client_key` trusts `X-Forwarded-For` only on Vercel,** where Vercel sets it. On a laptop anyone can send
  that header.
- **`who()` prefers the WitUS identity.** The owner's superuser before its first WitUS sign-in sends the user's
  own email and username.

The two templates:

Listing 13-15, Filename: `src/invest_witus_site/reports/templates/reports/report.html`:

{{file:src/invest_witus_site/reports/templates/reports/report.html}}

Listing 13-16, Filename: `src/invest_witus_site/reports/templates/reports/thanks.html`:

{{file:src/invest_witus_site/reports/templates/reports/thanks.html}}

Each help text has the id Django's widget names in `aria-describedby`, so a screen reader reads it with the
field. The link goes last in the header's list, so on a phone it folds with the others behind **Menu** when you
are signed in, and in the footer's Partners and Legal column beside **Report a bad actor**:

Listing 13-17, Filename: `src/invest_witus_site/pages/templates/pages/_header.html`:

{{file:src/invest_witus_site/pages/templates/pages/_header.html}}

Listing 13-18, Filename: `src/invest_witus_site/pages/templates/pages/_footer.html`:

{{file:src/invest_witus_site/pages/templates/pages/_footer.html}}

Five lines join the stylesheet, at the end: the text box, the three choices as 44-pixel targets, and the
"forwarding is off" note:

Listing 13-19, Filename: `src/invest_witus_site/pages/static/pages/site.css`:

{{file:src/invest_witus_site/pages/static/pages/site.css}}

### 13.7 The waitlist's copy

Listing 13-20, Filename: `src/invest_witus_site/pages/views.py`:

{{file:src/invest_witus_site/pages/views.py}}

`join` already returned whether the entry was new (chapter 04); the view now uses it. `mirror_waitlist`, in
`delivery.py` above, makes the copy and sends it. The thank-you is the same either way, as chapter 04 wanted, so
the page still never says whether an address was on the list.

### 13.8 The nightly retry, Send again and the command

Listing 13-21, Filename: `src/invest_witus_site/prices/views.py`:

{{file:src/invest_witus_site/prices/views.py}}

With Inbox configured, the cron's JSON gains an `inbox` object (`checked`, `sent`, `failed`, `stopped`). Without
it the body is chapter 08's, unchanged, which chapter 08's tests still check.

Listing 13-22, Filename: `src/invest_witus_site/reports/admin.py`:

{{file:src/invest_witus_site/reports/admin.py}}

What the person wrote and what Inbox answered are read-only; the triage status is the one field the owner edits.
There is no Add button: a report comes from the form. **Send again to WitUS Inbox** in the action menu sends the
selected rows and says what happened ("Send again: 1 sent, 1 already sent."), with each failure on its own line.

Listing 13-23, Filename: `src/invest_witus_site/reports/management/commands/reports.py`:

{{file:src/invest_witus_site/reports/management/commands/reports.py}}

### 13.9 The names in `.env.example`

Listing 13-24, Filename: `.env.example`:

{{file:.env.example}}

The privacy page gains a dated **Reports** item under "What we store, and why", and the waitlist item says a new
signup is copied to Inbox. It is prose, not code; take it from the reference with the command in "If you get
stuck".

### 13.10 Green, and a report on your laptop

Listing 13-25, Terminal:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

```text
558 passed in 28.15s
All checks passed!
202 files already formatted
0 errors, 0 warnings, 0 informations
```

Forty-three new tests. Migrate the laptop database:

Listing 13-26, Terminal:

```sh
uv run --env-file .env python manage.py migrate
```

```text
Operations to perform:
  Apply all migrations: accounts, admin, auth, contenttypes, holdings, methods, pages, paper, prices, reports, sessions, watchlist
Running migrations:
  Applying reports.0001_initial... OK
```

Your laptop has no Inbox, which is the first thing to see. Open the form as if from the FAQ, send a question, and
read the row:

Listing 13-27, Terminal:

```sh
DJANGO_DEBUG=1 DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
uv run python manage.py shell -v 0 -c "
from django.test import Client
from invest_witus_site.reports.models import Report
c = Client()
form = c.get('/report/', headers={'Referer': 'http://testserver/faq/?q=fees'}).content.decode()
print('Inbox off said:', 'Forwarding to WitUS Inbox is off.' in form, '| page filled in:', 'value=\"/faq/\"' in form)
answer = c.post('/report/', {'kind': 'question', 'message': 'Where does the logbook live?', 'page': '/faq/', 'email': 'you@example.com'})
print(answer.status_code, answer['Location'])
row = Report.objects.first()
print(row, '|', row.inbox_status, '|', row.attempts, '|', row.last_error)
"
uv run --env-file .env python manage.py reports
```

```text
Inbox off said: True | page filled in: True
302 /report/thanks/
A question #1 | off | 0 | WitUS Inbox is off: INBOX_INGEST_URL, INBOX_SOURCE_SLUG, INBOX_INGEST_SECRET not set.
#1 2026-10-29 18:26 question, new; Inbox: Off, will retry; page /faq/
    Where does the logbook live?
```

The page came from the referrer without its `?q=fees`. Your date and time are when you ran it, in UTC. Now point
the app at the tests' fake Inbox for one process, make it refuse once, then let the retry through:

Listing 13-28, Terminal:

```sh
DJANGO_DEBUG=1 DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
uv run python manage.py shell -v 0 -c "
import httpx, json
from django.conf import settings
from invest_witus_site.reports import inbox
from invest_witus_site.reports.delivery import send_unsent
from invest_witus_site.reports.models import Report
from tests.test_ch13 import SECRET, SOURCE, URL, FakeInbox
settings.INBOX_INGEST_URL, settings.INBOX_SOURCE_SLUG, settings.INBOX_INGEST_SECRET = URL, SOURCE, SECRET
fake = FakeInbox(); inbox.transport = httpx.MockTransport(fake.handle)
fake.answer = 401
print(send_unsent().as_dict())
print(Report.objects.first().last_error)
fake.answer = None
print(send_unsent().as_dict())
sent = fake.requests[-1]
print(sent.headers['x-witus-source'], sent.headers['x-witus-signature'][:7] + '...', len(sent.headers['x-witus-signature']))
body = json.loads(sent.content)
print(body['form_type'], body['priority'], body['submitter_email'], sorted(body['payload']))
row = Report.objects.first()
print(row.inbox_status, row.attempts, row.inbox_id)
print(send_unsent().as_dict())
"
```

```text
inbox: failed source=invest-witus form_type=invest-witus-support-question status=401
{'checked': 1, 'sent': 0, 'failed': 1, 'stopped': ''}
Inbox answered 401: the source slug is not registered there, the secret differs from Inbox's, or this server's clock is more than 5 minutes off. Inbox does not say which.
{'checked': 1, 'sent': 1, 'failed': 0, 'stopped': ''}
invest-witus sha256=... 71
invest-witus-support-question normal you@example.com ['admin_url', 'app_version', 'created_at', 'kind', 'message', 'page', 'report_id', 'signed_in', 'user_agent', 'view']
sent 2 inbox-2
{'checked': 0, 'sent': 0, 'failed': 0, 'stopped': ''}
```

The first line is the client's one log line for a failure: source, form type, status. The header is `sha256=`
and 64 hex characters, 71 in all. Two attempts, one sent, and a third run finds nothing to send. In a browser,
the same report is **Report a problem or ask a question** in the footer of any page, and the owner's list is
**Reports and WitUS Inbox**, **Reports** in the admin.

### 13.11 What the owner does outside the editor

The reference app's steps are task 21 in the owner's queue. A learner with a Vercel project and an Inbox of their
own does the same:

1. **Merge the chapter.** The push to `main` runs the migrate workflow (`docs/05-operations.md`), which applies
   `reports.0001`. Check that the run is green.
2. **Register the source in Inbox.** Make one secret per environment (`openssl rand -hex 32`), add
   `{"slug": "<your slug>", "hmac_secret": "<that secret>"}` to the `INGEST_SOURCES` variable of the Inbox
   project for that environment without removing the other entries, and redeploy Inbox: it reads the list when
   it starts.
3. **Set the three names on this app's project** (`INBOX_INGEST_URL`, `INBOX_SOURCE_SLUG`,
   `INBOX_INGEST_SECRET`), Sensitive, the secret identical to Inbox's for that environment, and redeploy.
4. **Send one report** from the live site's footer, and find it in Inbox's list under your slug. If the row in
   this app's admin reads "Failed, will retry" with a 401, compare the slug and the secret on both projects.

## Checkpoint

- `uv run pytest` prints `558 passed`; ruff and pyright pass.
- Every public page has **Report a problem or ask a question** in its header and its footer; signed in, it sits
  in the folding menu.
- Listing 13-27 saves a report with Inbox off and says so, and `manage.py reports` lists it.
- Listing 13-28 refuses once with Inbox's 401, sends on the retry, and finds nothing on the third run.
- No test reaches the network: `tests/conftest.py` fails any that tries.
- Commit and push: `git add -A && git commit -m "Chapter 13: the in-app reporter"`.

## Exercises

1. **Mark it done from Inbox.** The triage status here and Inbox's own status drift apart. Add a management
   command that, given an Inbox id, marks the matching report done, and decide which side is the record for
   triage. Write the reason in the decisions log.
2. **Your reports, signed in.** Add a page that lists the signed-in person's own reports with their kind, date and
   triage status, and nothing from anyone else. A test signs in as a second user and finds none of the first
   user's rows.
3. **A screenshot.** Add an optional image to the form, stored where chapter 06's deploy can keep it, with a size
   limit and a type check, and a link to it in the payload rather than the image itself. Decide what the privacy
   page must say.
4. **Stop retrying a refusal.** A 400 will fail every night until the code changes. Stop retrying a row after
   five refusals, show it in the admin with a filter, and keep **Send again** able to try it.

## If you get stuck

- Browse: https://github.com/dapperAuteur/invest-witus/tree/v13
- Diff for this chapter: https://github.com/dapperAuteur/invest-witus/compare/v12...v13
- Zip: https://github.com/dapperAuteur/invest-witus/archive/v13.zip
- Take the reference's files. Chapter 13 changed `src/invest_witus_site/settings.py`,
  `src/invest_witus_site/urls.py`, `pages/views.py`, `prices/views.py`, the templates `pages/_header.html` and
  `pages/_footer.html`, `pages/static/pages/site.css`, `docs/site/privacy.md`, `.env.example` and
  `tests/conftest.py`, and added the folder `src/invest_witus_site/reports/` (`apps.py`, `inbox.py`,
  `models.py`, `delivery.py`, `forms.py`, `views.py`, `urls.py`, `admin.py`, the command
  `management/commands/reports.py`, the templates `reports/report.html` and `reports/thanks.html`, and
  `migrations/0001_initial.py`) and `tests/test_ch13.py`. No package changed and nothing moved:
  `git fetch reference --tags && git checkout v13 -- src tests docs/site/privacy.md .env.example`.
- `test_the_signature_matches_one_computed_by_hand` fails: `sign` hashed `f"{timestamp}{raw}"` without the dot,
  or decoded the bytes and hashed a `str` built with `json.dumps` a second time.
- `test_the_request_carries_the_headers_and_the_signed_bytes` finds different bytes: `send` passed `json=` to
  httpx instead of `content=raw`.
- `test_the_body_leaves_out_an_empty_name_and_email_and_is_plain_ascii` fails on `isascii`: `ensure_ascii=False`.
- A test fails with `AssertionError: a test tried to reach inbox.example.test`: it set the three names itself
  without asking for the `fake` fixture, so the guard's transport from `conftest.py` is still in place.
- `test_a_retry_sends_once_and_marks_the_report_sent` sends three times: `deliver` checked `sent_at` on the row it
  was given instead of the copy it read with the lock.
- `test_the_rate_limit_counts_reports_in_the_database` lets the sixth through: the limit counts with `>` instead
  of `>=`, or runs after `create`.
- `test_signed_in_the_witus_identity_is_the_sender` finds `name="email"`: the form's `__init__` did not delete
  the field when signed in.
- The cron tests of chapter 08 fail with an extra `inbox` key: the cron adds it even with Inbox off. Guard it with
  `inbox_configured()`.
- On Vercel after the merge, a report's row reads "Failed, will retry" with a 401: the slug is not in Inbox's
  `INGEST_SOURCES` for that environment, Inbox was not redeployed after the change, or the two secrets differ.

## What we learned

- A signature is over bytes. Serialize once, sign that, send that.
- Read the receiver's code before you trust a summary of it: the schema, the limits and the answers are there,
  and a few of them change the sender.
- Saving first and sending second turns a failure into a column, and a column can be retried.
- A job that already runs every night is a queue with one worker; a button beside it is the fallback.
- A lock around a network call keeps two senders from sending twice, and a short timeout keeps the lock short.
- A limit can count rows, and an address can be counted without being kept.

## Next

Chapter 14 adds the second method, 12-1 momentum: rank your universe by its 12-month return without the last
month, hold the top few, and review it with the same engine.

## References

Django Software Foundation. (n.d.). *QuerySet API reference: select_for_update()*. Django 5.2 documentation.
Retrieved October 29, 2026, from https://docs.djangoproject.com/en/5.2/ref/models/querysets/

Encode. (n.d.). *Transports*. HTTPX. Retrieved October 29, 2026, from
https://www.python-httpx.org/advanced/transports/

Python Software Foundation. (n.d.). *hmac: Keyed-hashing for message authentication*. Python documentation.
Retrieved October 29, 2026, from https://docs.python.org/3/library/hmac.html

Vercel. (n.d.-a). *Request headers*. Vercel documentation. Retrieved October 29, 2026, from
https://vercel.com/docs/headers/request-headers

Vercel. (n.d.-b). *System environment variables*. Vercel documentation. Retrieved October 29, 2026, from
https://vercel.com/docs/environment-variables/system-environment-variables

WitUS Inbox. (n.d.). *Signed-webhook contract* [Source code documentation]. GitHub. Retrieved October 29, 2026,
from https://github.com/dapperAuteur/witus-inbox/blob/main/docs/webhook-contract.md
