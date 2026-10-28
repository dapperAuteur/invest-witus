# Chapter 07: Sign in with WitUS

**Starts from:** tag `v06a`. **Ends at:** tag `v07`.
**Written against:** Python 3.14.10, uv 0.13.6, Django 5.2.18, httpx 0.28.1, PyJWT 2.15.1 with cryptography 50.0.2,
and the ecosystem identity provider's discovery document and key set as read on October 28, 2026. The provider
is a running service; when it and this text disagree, read its discovery document again.
**Goal:** "Sign in" in the header sends the browser to the WitUS identity provider and brings it back signed in.
The app does OpenID Connect with no auth framework: three HTTP calls with httpx, one signature check with PyJWT,
and every check the standard asks for written where you can read it. People are keyed by the WitUS user id,
never by email. The client is off until the owner sets a secret, so the site keeps deploying as before.
**Time:** 3 to 4 hours for the code and tests. The provider side is the owner's and takes 20 minutes.

The listings in this chapter are not typed in by hand. `scripts/render_chapter.py` pastes the real files from
tag `v07` into the chapter text, so what you read and what the tests run are the same bytes.

## What you will learn

- **The authorization code flow, step by step:** a redirect out with a state, a nonce and a PKCE challenge; a
  callback with a code; a server-to-server exchange of the code for tokens; an id token verified; a session.
- **Reading a provider's discovery document** and its key set, and what to do when the document is not where
  the standard says.
- **Verifying a JWT the way the standard asks:** signature, algorithm, issuer, audience, expiry, nonce, and
  why the algorithm is pinned to the one the provider uses.
- **PKCE with S256,** in eight lines, and the worked example from the RFC as a test.
- **Django sessions and `login()` / `logout()`:** what is in the session cookie (an id) and what is not.
- **A one-to-one profile keyed by an external id,** instead of a custom user model, and a linking rule written
  down before it runs.
- **A fake provider in a test,** with a real Ed25519 key, through httpx's `MockTransport`.
- **A POST-only view** and a form where a link would have been wrong.

## Before the code: what the provider says about itself, and what the client must check

**The flow.** The visitor clicks "Sign in". The app sends the browser to the provider's authorize endpoint
with a random `state`, a random `nonce` and a hash of a random `code_verifier`, and keeps all three in the
session. The provider signs the person in (a magic link, on WitUS) and sends the browser back to this app's
callback with a `code` and the `state`. The app checks the `state`, then, server to server, trades the `code`
plus the `code_verifier` for tokens. The id token is a signed JWT that names the person; the app verifies it,
finds or makes the Django user, and calls `login()`. Six steps, and each one has a test.

**What discovery said.** An OpenID provider publishes a JSON document about itself. Discovery 1.0 puts it at
the issuer plus `/.well-known/openid-configuration` and says the document's `issuer` must be identical to the
URL it was fetched under (OpenID Foundation, 2023). On October 28, 2026, that path on
`https://accounts.witus.online` answered 404 with the witus.online not-found page; the document lives at
`/api/idp/.well-known/openid-configuration`, because the provider is better-auth's OIDC plugin mounted at
`/api/idp` (WitUS, 2026d). The document itself says:

| Field | Value read October 28, 2026 |
|---|---|
| `issuer` | `https://accounts.witus.online` |
| `authorization_endpoint`, `token_endpoint`, `userinfo_endpoint` | `https://accounts.witus.online/api/idp/oauth2/` + `authorize`, `token`, `userinfo` |
| `jwks_uri` | `https://accounts.witus.online/api/idp/jwks` |
| `end_session_endpoint` | `https://accounts.witus.online/api/idp/oauth2/endsession` (present) |
| `id_token_signing_alg_values_supported` | `RS256`, `EdDSA` |
| `token_endpoint_auth_methods_supported` | `client_secret_basic`, `client_secret_post`, `none` |
| `code_challenge_methods_supported` | `S256` |
| `scopes_supported` | `openid`, `profile`, `email`, `offline_access` |
| `claims_supported` | includes `sub`, `email`, `email_verified`, `name` |

(WitUS, 2026a). The key set at `jwks_uri` holds one key: `kty` `OKP`, `crv` `Ed25519`, `alg` `EdDSA`, with a
`kid` (WitUS, 2026b). That is the whole story of the algorithm: the document lists RS256 because the standard
requires the list to include it, but there is no RSA key, so a client that defaults to RS256 fails at the
callback. The ecosystem's NextAuth apps hit exactly that and now pin EdDSA (WitUS, 2026c). This client accepts
EdDSA and refuses everything else, including `none`, which is not a signature.

The client reads the document at the standard's path first and at the provider's path second, and refuses a
document whose `issuer` is not the one configured. The default issuer in the settings is the host read that
day, labeled as such; the authoritative-values rule in `CLAUDE.md` is why the chapter copies these values from
the document instead of typing paths into the code.

**What the client must check.** Core 1.0, section 3.1.3.7: the issuer "MUST exactly match the value of the
`iss` (issuer) Claim"; the token "MUST be rejected if the ID Token does not list the Client as a valid
audience"; "The current time MUST be before the time represented by the `exp` Claim"; and "If a nonce value was
sent in the Authentication Request, a nonce Claim MUST be present" and match (Sakimura et al., 2023). The
nonce is a "String value used to associate a Client session with an ID Token, and to mitigate replay attacks"
(section 3.1.2.1). PKCE, RFC 7636, is for the code: the provider stores a hash of a secret the app made, and the
app sends the secret itself with the code, so an attacker who intercepts the code "cannot exchange it for
tokens, because they lack the code_verifier" (Sakimura et al., 2015). The S256 transform is
`BASE64URL-ENCODE(SHA256(ASCII(code_verifier)))`, and the RFC's appendix gives a worked example that the tests
use. This provider requires PKCE for every client (WitUS, 2026d), which is a good default to meet anyway.

**`sub`, never email.** Core 1.0, section 5.7: "the only guaranteed unique identifier for a given End-User is
the combination of the `iss` Claim and the `sub` Claim", and claims such as email "MUST NOT be used as unique
identifiers for the End-User" (Sakimura et al., 2023). Chapter 05 left `Account.witus_user_id` empty for
exactly this (decisions log, row 43); this chapter fills it. The one place email is read is the first sign-in,
to link the owner's existing superuser, and only when the provider says the address is verified.

**Why no framework, and why PyJWT.** The PRD and research 04 proposed Authlib's Django client. Its
`parse_id_token` takes the allowed algorithms from the discovery document's
`id_token_signing_alg_values_supported` (Authlib contributors, n.d.-a), which here lists RS256 too, so pinning
EdDSA would mean subclassing a client you did not write; its Django client page answered 404 on the day this
was written. More to the point, the flow is six steps and a learner should read all six. PyJWT does the one
part that should not be hand-written, the signature: it lists EdDSA with Ed25519 (PyJWT contributors, n.d.-b),
wants the `[crypto]` extra for it (PyJWT contributors, n.d.-c), and `jwt.decode` takes `algorithms`,
`audience`, `issuer`, `leeway` and `options={"require": [...]}` in one call, with a named exception for each
failure (PyJWT contributors, n.d.-a). Its API reference warns: "Do not compute the algorithms parameter based
on the alg from the token itself." The list is a constant in the code. Decisions log, row 62.

**Off until the owner says so.** The client is on exactly when `WITUS_OIDC_CLIENT_SECRET` is set. A copy of
the app with no secret serves the public site with chapter 04's stub page behind "Sign in", which is what your
copy does: the provider accepts first-party ecosystem apps only, registered in the witus repo, and a redirect
URI is matched exactly (WitUS, 2026c). Your checkpoint is the fake provider in the tests; exercise 2 opens the
client to a provider of your own.

## Steps

### 07.1 The tests

Listing 07-1, Filename: `tests/test_ch07.py`:

{{file:tests/test_ch07.py}}

Things to notice:

- **`FakeIdp` is a provider small enough to read.** It makes a real Ed25519 key, publishes it as a JWK with a
  `kid`, serves the discovery document under `/api/idp/` and a 404 at the standard's path (like the live host),
  checks the client id and secret and the PKCE verifier at its token endpoint, signs a real id token with the
  nonce it was sent, and answers userinfo. `handle` is an `httpx.MockTransport` handler: a function from a
  request to a response (Encode, n.d.). `authorize` plays the browser's part of the trip.
- **The overrides are the test cases.** `token_overrides` changes one claim (`aud`, `iss`, `exp`, `nonce`) or
  removes one (`OMIT`); `alg` makes a token that is not EdDSA; `kid` names a key the JWKS does not have;
  `end_session` and `discovery_at_root` change the document. Each refusal is one line of setup and one assert.
- **`sign_in` is the whole trip in three lines,** and every test of the callback goes through it, so the
  tests cannot pass by calling the callback with a shape the login never produces.
- **`ControlCollector` names buttons the way `LinkCollector` named links in chapter 04:** by their text. "Sign
  out" is a button in a form, so a link collector would miss it.
- **`fresh_settings`** is chapter 06's helper with `WITUS_` added to the names it clears.
- **The `settings` fixture** (pytest-django, n.d.) switches the client on for one test; the views read the
  settings when a request arrives, which is why that works.
- **The RFC's worked example** is a test of eight lines of code. When a test can be a published vector, it
  should be.

Add the two packages first (07.2), then run it:

Listing 07-2, Terminal:

```sh
uv run pytest tests/test_ch07.py
```

```text
tests/test_ch07.py:28: in <module>
    from invest_witus_site.accounts import oidc
E   ModuleNotFoundError: No module named 'invest_witus_site.accounts'
=========================== short test summary info ============================
ERROR tests/test_ch07.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.55s
```

Red first, at import: the app the tests describe does not exist.

### 07.2 Two packages and four names

Listing 07-3, Terminal:

```sh
uv add httpx "pyjwt[crypto]"
```

`httpx` makes the HTTP calls. `pyjwt[crypto]` is PyJWT with the `cryptography` library, which EdDSA needs; the
installation page recommends writing the extra this way so that a separate `cryptography` line is not "later
mistaken for an unused requirement and removed" (PyJWT contributors, n.d.-c). No test library is added: the
fake provider is plain httpx.

Listing 07-4, Filename: `pyproject.toml`:

{{file:pyproject.toml}}

The settings gain the four names at the end, the app in `INSTALLED_APPS`, one context processor, and
`LOGIN_URL`. Everything else is chapter 06's.

Listing 07-5, Filename: `src/invest_witus_site/settings.py`:

{{file:src/invest_witus_site/settings.py}}

- **`WITUS_OIDC_CLIENT_SECRET` is the switch.** Empty means off. There is no second flag to forget.
- **`WITUS_OIDC_ISSUER`** defaults to the host read on October 28, 2026, with the trailing slash dropped, and
  must be `https://`. The client compares it with the discovery document's own `issuer`, so a wrong value fails
  at the first sign-in with a message, not with a token from the wrong place.
- **`WITUS_OIDC_CLIENT_ID`** defaults to `witus-invest`, the registry's `witus-<slug>` form. **`WITUS_OIDC_SCOPES`**
  must include `openid`, or there is no id token to verify.
- **`LOGIN_URL = "sign-in"`.** The setting "accepts view function names and named URL patterns" (Django Software
  Foundation, n.d.-a), so when a later chapter puts a page behind `login_required`, the visitor lands on the
  WitUS sign-in, not on `/accounts/login/`.

### 07.3 The accounts app: who signed in

Listing 07-6, Filename: `src/invest_witus_site/accounts/apps.py`:

{{file:src/invest_witus_site/accounts/apps.py}}

Listing 07-7, Filename: `src/invest_witus_site/accounts/models.py`:

{{file:src/invest_witus_site/accounts/models.py}}

- **One table, one-to-one with `auth.User`.** `sub` is unique and is the key; `email` and `name` are a copy of
  what the provider said last time, for display and contact; `last_login_at` is written on every sign-in.
  Chapter 05 chose not to swap the user model after a production database existed (row 43), and this is the
  profile it promised instead.
- **`sign_in` is the linking rule, in order.** By `sub` first. Then, only when the provider says the email is
  verified, the one existing user without an identity whose email matches: that is how the owner's superuser
  from chapter 05 links on its first sign-in, and the only way an identity-less user exists is that the owner
  made it, with `createsuperuser` or in the admin. Otherwise a new ordinary user: not staff, no password
  (`create_user` with none sets an unusable one), a username built from the `sub` so it is unique and never an
  email. After the first sign-in, email is not consulted again; a changed address updates the row and matches
  nothing.
- **`Account.witus_user_id` is set on every sign-in,** for every account the user owns. The owner's accounts
  from chapter 05 carry the WitUS id after the first sign-in without anyone typing it.

Make the migration and read it:

Listing 07-8, Terminal:

```sh
uv run --env-file .env python manage.py makemigrations accounts
uv run ruff format src/invest_witus_site/accounts/migrations/
```

Listing 07-9, Filename: `src/invest_witus_site/accounts/migrations/0001_initial.py`:

{{file:src/invest_witus_site/accounts/migrations/0001_initial.py}}

Listing 07-10, Filename: `src/invest_witus_site/accounts/admin.py`:

{{file:src/invest_witus_site/accounts/admin.py}}

Rows are made by sign-ins, so the admin cannot add one. It can change `user`: if the owner's first sign-in made
a stray `witus-<sub>` user because the emails did not match, the owner points the identity at the superuser here
and deletes the stray.

### 07.4 The client

Listing 07-11, Filename: `src/invest_witus_site/accounts/oidc.py`:

{{file:src/invest_witus_site/accounts/oidc.py}}

Read it top to bottom; the functions sit in the order the flow calls them.

- **`transport`** is the seam. The views never pass it; `http()` reads it. In production it is `None` and
  httpx talks to the network; in the tests it is a `MockTransport` and nothing leaves the process.
- **`config()` reads the settings on every call,** so a test can switch the client on and the pytest-django
  fixture can switch it off again. `enabled` is derived from the secret, not stored twice.
- **`Provider.from_document`** refuses a document with another `issuer` and a document missing an endpoint,
  with a message that names the field. `end_session_endpoint` is optional in the standard, so it is optional
  here, and the logout view behaves either way.
- **`provider()` and `fetch_provider()`:** the document is fetched once an hour per process. The two paths are
  tried in order, and the first 200 wins. A Vercel function is short-lived, so the hour is a ceiling, not a
  promise.
- **`signing_key()` and `fetch_keys()`:** keys are cached by `kid`. A token that names a key not in the cache
  causes one fetch of the key set; if the key is still missing, the token is refused. Only keys whose algorithm
  is allowed are kept, so an RSA key the provider might add one day is skipped with a log line.
- **`begin()`** makes three random strings and the authorize URL. `secrets.token_urlsafe(48)` gives 64
  characters from the unreserved set, inside RFC 7636's 43 to 128. The verifier never leaves the server; its
  hash does.
- **`flight_from_session()`** reads the session back as data: four strings, or nothing. Session data is the
  app's own, and it is still read, not unpacked.
- **`exchange_code()`** posts the form. The secret goes in the body (`client_secret_post`): the ecosystem's
  reference client does the same against this provider (WitUS, 2026f), the provider's token endpoint reads
  `client_secret` from the body and falls back to HTTP Basic (WitUS, 2026d), and discovery lists both. A non-200
  answer is an error with the status and the first 200 characters of the body, which names the OAuth error and
  never the secret.
- **`verify_id_token()`** is the section-3.1.3.7 list. The header is read unverified first, for two fields: the
  `alg`, which must be in `ALLOWED_ALGORITHMS` before anything else happens, and the `kid`, which picks the
  key. Then one `jwt.decode` call checks the signature, the algorithm again, `iss`, `aud`, `exp` with a minute
  of leeway and the presence of the required claims, each with its own exception class (PyJWT contributors,
  n.d.-a), and the function turns any of them into an `OidcError` that carries the class name. The `nonce` is
  the last check and the only one PyJWT does not know about.
- **`claims_for()`** takes the person from the id token. This provider puts `email`, `email_verified` and
  `name` in the token when the `email` and `profile` scopes were asked for (WitUS, 2026d), so userinfo is a
  fallback: called only when the token has no email, and its `sub` must match the token's, as Core 5.3.2 asks.
  The email is lower-cased for matching; the name is trimmed.
- **`end_session_url()`** builds the RP-initiated logout URL: `client_id` "is most commonly needed when
  `post_logout_redirect_uri` is used without `id_token_hint`", and the URI must be one registered with the
  provider, matched exactly (OpenID Foundation, 2022). The registry registers each app's root for this (WitUS,
  2026c), which is why the view sends the home page's absolute URL and nothing cleverer.

### 07.5 The three views and their routes

Listing 07-12, Filename: `src/invest_witus_site/accounts/views.py`:

{{file:src/invest_witus_site/accounts/views.py}}

- **`login`** renders the stub when the client is off, sends a signed-in visitor home, and otherwise stores the
  flight in the session and redirects. The session is database-backed by default
  (`django.contrib.sessions.backends.db`); the browser gets a cookie with "a session ID, not the data itself"
  (Django Software Foundation, n.d.-b), so the verifier is never in the browser. `redirect_uri` is built from
  the request, which on Vercel is the production origin behind chapter 06's proxy header: exactly the URI the
  registry holds.
- **`callback`** pops the flight. Popped, not read: the callback is good for one attempt, and a replayed URL
  fails on `state` before the app talks to the provider. Then the provider's own `error` parameter, then the
  code, then the four calls from 07.4 inside one `try`. Every `OidcError` becomes a 400 whose page shows one word
  (`state`, `code`, `refused`, or the provider's error code) and whose log line has the rest.
- **`auth_login(request, user, backend=...)`.** `login()` "saves the user's ID in the session" and needs to know
  which backend to record; it takes the `backend` argument, or `user.backend` as set by `authenticate()`, or
  the only backend configured (Django Software Foundation, n.d.-a). This user did not come through
  `authenticate()`, so the backend is named. `login()` also cycles the session key against session fixation
  (Django Software Foundation, n.d.-b).
- **`logout` is POST only.** `auth_logout()` flushes the session: "the session data for the current request is
  completely cleaned out" (Django Software Foundation, n.d.-a). Django 5.0 removed GET from its own
  `LogoutView` (Django Software Foundation, n.d.-d); a link can be followed by a prefetch or a cross-site image
  tag, and a sign-out should happen when the person asked. After the local sign-out, the browser goes to the
  provider's end-session endpoint so the WitUS session ends too, and comes back to the home page.
- **Why the callback's cookie survives the trip.** The session cookie's `SameSite` is `Lax` by default, which
  allows the cookie "when following a regular link from an external website" and blocks it on cross-site POSTs
  (Django Software Foundation, n.d.-c). The provider sends the browser back with a GET, so the session, and
  the flight in it, are there. It is also why the sign-out form posts from this site and not from anywhere
  else.

Listing 07-13, Filename: `src/invest_witus_site/accounts/urls.py`:

{{file:src/invest_witus_site/accounts/urls.py}}

Listing 07-14, Filename: `src/invest_witus_site/urls.py`:

{{file:src/invest_witus_site/urls.py}}

The stub route leaves `pages/urls.py`; its name, `sign-in`, is unchanged, so every `{% url 'sign-in' %}` in
the templates and the ecosystem registry's link to `/auth/witus/login/` still point at the same place.

Listing 07-15, Filename: `src/invest_witus_site/pages/urls.py`:

{{file:src/invest_witus_site/pages/urls.py}}

The stub page's text changes, and still names chapter 07, because tag `v04`'s test looks for those words and
tags are immutable:

Listing 07-16, Filename: `src/invest_witus_site/pages/templates/pages/sign_in_stub.html`:

{{file:src/invest_witus_site/pages/templates/pages/sign_in_stub.html}}

Listing 07-17, Filename: `src/invest_witus_site/accounts/templates/accounts/sign_in_failed.html`:

{{file:src/invest_witus_site/accounts/templates/accounts/sign_in_failed.html}}

### 07.6 The header's two states

Listing 07-18, Filename: `src/invest_witus_site/accounts/templates/accounts/_sign_out_form.html`:

{{file:src/invest_witus_site/accounts/templates/accounts/_sign_out_form.html}}

Listing 07-19, Filename: `src/invest_witus_site/pages/templates/pages/_header.html`:

{{file:src/invest_witus_site/pages/templates/pages/_header.html}}

Signed out, the header is chapter 04's, byte for byte in the part that matters: the link whose accessible name
is "Sign in", which the smoke test protects and which the PRD says is never renamed. Signed in, the same spot
holds the person's name and the "Sign out" button. The footer's "Sign in" item gets the same `{% if %}`, with
the same include in the other branch.

Listing 07-20, Filename: `src/invest_witus_site/accounts/context_processors.py`:

{{file:src/invest_witus_site/accounts/context_processors.py}}

One query per request for a signed-in visitor, none for anyone else. The owner signed in at `/admin/` with a
password has no identity until their first WitUS sign-in, so the username stands in, and the header reads
"Sign out" for them as well: a login is a login.

Listing 07-21, Filename: `src/invest_witus_site/pages/templates/pages/home.html`:

{{file:src/invest_witus_site/pages/templates/pages/home.html}}

One line at the top of the home page for a signed-in person, with the admin link only for staff. Five short
rules in `site.css` let the form sit in the header's row and the footer's list like the links around them
(`.site-header nav form`, `.site-header .who`, `.site-footer form`, the footer's button, `.signed-in`).

### 07.7 Green, and a look at the real provider

Listing 07-22, Terminal:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

```text
190 passed in 4.52s
All checks passed!
95 files already formatted
0 errors, 0 warnings, 0 informations
```

Thirty-four new tests. The four names go in `.env.example`, with the switch first:

Listing 07-23, Filename: `.env.example`:

{{file:.env.example}}

Now see the first step against the real provider, without a server and without a secret of your own: any
non-empty value switches the client on, discovery is fetched from accounts.witus.online, and the redirect is
built. The provider is not contacted with anything but two GETs for public documents.

Listing 07-24, Terminal:

```sh
DJANGO_DEBUG=1 DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:////tmp/invest-witus-07.sqlite3 \
uv run python manage.py migrate -v 0
DJANGO_DEBUG=1 DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:////tmp/invest-witus-07.sqlite3 \
WITUS_OIDC_CLIENT_SECRET=not-the-real-secret-just-for-this-check \
uv run python manage.py shell -c "from django.test import Client; r = Client().get('/auth/witus/login/'); print(r.status_code); print(r['Location'])"
```

```text
302
https://accounts.witus.online/api/idp/oauth2/authorize?response_type=code&client_id=witus-invest&redirect_uri=http%3A%2F%2Ftestserver%2Fauth%2Fwitus%2Fcallback%2F&scope=openid+email+profile&state=ZNhXesuS0TiluB-7aeGM6aLlVF11tLmTxUWW9HF83VM&nonce=gyMfbPluzSuwMPNYo__aUypOFfAyYxzMOnDQahR2ExY&code_challenge=eSrVMyFlPYiapJ8Go4rRrrGVVWYtZaK9n4ttmEeLd5I&code_challenge_method=S256
```

(The shell's line about imported objects is trimmed; your `state`, `nonce` and `code_challenge` are different
random strings.) The discovery document was read from the second path, its issuer matched, and the authorize
endpoint came from it. Follow that URL in a browser and the provider answers 400 "Invalid redirect URI", since
`http://testserver/...` is registered nowhere: the provider doing its job. Drop `WITUS_OIDC_CLIENT_SECRET` from
the command and the status is 200 with the stub page. Delete the temporary database afterwards.

### 07.8 What the owner does outside the editor

The reference app's registration is the owner's, in the witus repo, where the provider's client registry lives
(WitUS, 2026c); task 07 in the owner's queue has the dashboard steps. A learner's copy cannot do this: the
provider accepts first-party ecosystem apps only, and each one's redirect URI is matched exactly. What the
steps are, so the chapter is complete:

1. **The registry entry.** `lib/identity/clients.ts` holds slug `invest`, origin
   `https://invest.witus.online` and `callbackPath` `/auth/witus/callback/`; the registry registers the root
   `https://invest.witus.online/` as the post-logout URI by default. The client id is `witus-invest`.
2. **Mint the secret.** `node scripts/gen-oidc-client.mjs invest` refuses a slug that is not registered, makes
   a 32-byte secret, and prints two blocks: one for the provider's own Vercel project
   (`WITUS_OIDC_SECRET__INVEST`) and one, marked as belonging to the app's project and not the provider's, with
   `WITUS_OIDC_CLIENT_ID` and `WITUS_OIDC_CLIENT_SECRET` (WitUS, 2026e). It stores nothing; the secret is shown
   once and goes in a password manager. The provider ignores the `invest` client until its variable exists and
   the provider's function has restarted with it. This step was done on October 28, 2026.
3. **Set the secret on this app's Vercel project:** `WITUS_OIDC_CLIENT_SECRET`, marked sensitive, Production
   and Preview. The other three names keep their defaults. A preview deployment can show the header but not
   finish a sign-in, because its host is not the registered origin.
4. **Migrate and redeploy.** `vercel env run -e production -- uv run python manage.py migrate --database direct`
   adds the identity table (chapter 06's recipe); then Redeploy, so the function starts with the secret.
5. **Sign in once and check:** `/auth/witus/login/` answers 302 to `accounts.witus.online/api/idp/oauth2/authorize`;
   the callback lands on the home page with "Signed in as" and a header that reads "Sign out"; the admin's
   WitUS identities list has one row, attached to the superuser if the emails matched and the provider marked
   the email verified, or to a new `witus-<sub>` user otherwise (the admin re-points it); each of the owner's
   accounts shows the WitUS user id; "Sign out" passes through the provider's end-session endpoint and returns
   to the home page.

## Checkpoint

- `uv run pytest` prints `190 passed`; ruff and pyright pass.
- With `.env` as before (no secret), `/auth/witus/login/` is the stub page and every public page has the "Sign
  in" link.
- Listing 07-24 prints a 302 to the provider's authorize endpoint with `code_challenge_method=S256`.
- `test_code_challenge_is_s256_of_the_verifier` passes against the RFC's own numbers.
- On the reference app, after 07.8: a sign-in lands with "Signed in as", and "Sign out" returns to the home
  page signed out.
- Commit and push: `git add -A && git commit -m "Chapter 07: Sign in with WitUS"`.

## Exercises

1. The callback refuses a token whose `exp` is an hour old. Write the test for a token whose `iat` is an hour in
   the future, decide what the client should do about it (PyJWT has a `verify_iat` option and `leeway` applies
   to it), and change `verify_id_token` or leave it, with a sentence in your notes saying why.
2. Make the allowed algorithm a setting, `WITUS_OIDC_ID_TOKEN_ALG`, defaulting to `EdDSA`, so your copy can talk
   to a provider of your own that signs RS256. Keep `none` refused whatever the setting says, and keep the test
   that proves it. Then register your copy with that provider and sign in from your laptop.
3. The sign-out form appears twice on every signed-in page. Write the test that counts the forms and asserts
   both post to `/auth/witus/logout/`, then decide whether the footer's copy earns its place.

## If you get stuck

- Browse: https://github.com/dapperAuteur/invest-witus/tree/v07
- Diff for this chapter: https://github.com/dapperAuteur/invest-witus/compare/v06a...v07
- Zip: https://github.com/dapperAuteur/invest-witus/archive/v07.zip
- Take the reference's files. Chapter 07 changed `pyproject.toml` and `uv.lock` (httpx, PyJWT), `.env.example`,
  `src/invest_witus_site/settings.py`, `src/invest_witus_site/urls.py`, `src/invest_witus_site/pages/urls.py`,
  `src/invest_witus_site/pages/views.py`, the templates `pages/_header.html`, `pages/_footer.html`,
  `pages/home.html` and `pages/sign_in_stub.html`, `pages/static/pages/site.css` and `docs/site/privacy.md`,
  and added `src/invest_witus_site/accounts/` (the whole app) and `tests/test_ch07.py`. Nothing moved:
  `git fetch reference --tags && git checkout v07 -- src tests .env.example pyproject.toml uv.lock docs/site/privacy.md`,
  then `uv sync`.
- `ModuleNotFoundError: No module named 'httpx'` or `'jwt'`: 07.2's `uv add` did not run, or the test is being
  run with another Python; use `uv run pytest`.
- `No module named 'invest_witus_site.accounts'` after 07.3: the app folder is missing its `__init__.py`, or sits
  outside `src/invest_witus_site/`.
- `ImproperlyConfigured: WITUS_OIDC_ISSUER must be the provider's https:// issuer`: the variable holds a path or
  a plain-http URL; it wants the origin the discovery document names.
- `test_discovery_falls_back_to_the_api_idp_path_and_is_cached` fails on the second path: `DISCOVERY_PATHS`
  is in the wrong order, or `fetch_provider` stops at the first non-200 instead of trying the next path.
- `test_callback_rejects_a_token_that_is_not_eddsa` fails with the JWKS fetched: the `alg` check sits after
  `signing_key()`; it must come first, on the unverified header.
- `test_a_good_callback_creates_the_identity_and_signs_the_person_in` fails on `has_usable_password`:
  `new_user` passed a password; `create_user(username=..., email=...)` with no password is the point.
- `test_the_owners_superuser_links_by_verified_email` makes two users: `existing_user` filters on
  `witus_identity__isnull=True` and `email__iexact`; check the related name on the `OneToOneField`.
- `test_logout_is_a_post_and_goes_home_with_the_client_off` gets 302 for the GET: `@require_POST` is missing
  from `logout`.
- `ValueError: ... backend` from `auth_login`: the `backend=` argument is missing; this user did not come
  through `authenticate()`.
- On the reference app, the provider's page says "Invalid redirect URI": the host is not the registered
  origin, or the registry's `callbackPath` differs from `/auth/witus/callback/`.
- The callback page says `refused` and the log says `token endpoint answered 401`: the two secrets differ, or
  the provider has not restarted since its variable was set.
- The callback page says `state`: the session cookie did not survive the trip. Over plain HTTP with debug off,
  chapter 06's Secure cookie is never sent; use `--env-file .env` on a laptop. On Vercel, a callback opened in
  another browser or after the session expired fails the same way, on purpose.

## What we learned

- The authorization code flow is six steps, and each is a function a test can call: out with `state`, `nonce`
  and a challenge; back with a code; the exchange with the verifier; the id token's checks; the person; the
  session.
- A provider's discovery document is read, not assumed, and its `issuer` is checked against the configured one;
  when the document is not at the standard's path, the code says where it looked and why.
- The algorithm a client accepts is a constant, never the token's own header; `kid` picks the key, the key set
  is cached and refetched once; `iss`, `aud`, `exp` and `nonce` each have a test that fails them.
- PKCE is a hash on the way out and the secret on the way back, and the RFC's worked example is a test.
- The session holds the sign-in in progress on the server; the browser holds an id; `Lax` is why the callback
  still sees it and why the sign-out is a POST.
- People are keyed by `sub`. Email links an existing user once, only when verified, and the rule is written
  before it runs.
- The client is on exactly when its secret is set, so a copy of the app without one is the chapter 06 site with
  a stub, and the owner's registration is a dashboard task with its checks written down.

## Next

Chapter 08 adds prices: end-of-day closes in the app's own table, one daily cron route guarded by `CRON_SECRET`,
idempotent and recording its last run, and the owner's holdings valued with the price date shown. Nothing from
this chapter changes for it; the signed-in owner is who those values are for.

## References

Authlib contributors. (n.d.-a). *sync_openid.py* [Source code, `main` branch]. GitHub.
https://raw.githubusercontent.com/authlib/authlib/main/authlib/integrations/base_client/sync_openid.py
(retrieved October 28, 2026)

Authlib contributors. (n.d.-b). *JSON Web Signature (JWS)*. Authlib documentation.
https://docs.authlib.org/en/latest/jose/jws.html (retrieved October 28, 2026)

better-auth. (n.d.). *JWT*. better-auth documentation. https://www.better-auth.com/docs/plugins/jwt (retrieved
October 28, 2026)

Django Software Foundation. (n.d.-a). *Using the Django authentication system*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/topics/auth/default/ (retrieved October 28, 2026)

Django Software Foundation. (n.d.-b). *How to use sessions*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/topics/http/sessions/ (retrieved October 28, 2026)

Django Software Foundation. (n.d.-c). *Settings*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/ref/settings/ (retrieved October 28, 2026)

Django Software Foundation. (n.d.-d). *Django 5.0 release notes*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/releases/5.0/ (retrieved October 28, 2026)

Encode. (n.d.). *Transports*. HTTPX documentation. https://www.python-httpx.org/advanced/transports/ (retrieved
October 28, 2026)

Liusvaara, I. (2017). *CFRG elliptic curve Diffie-Hellman (ECDH) and signatures in JSON Object Signing and
Encryption (JOSE)* (RFC 8037). RFC Editor. https://www.rfc-editor.org/rfc/rfc8037 (retrieved October 28, 2026)

OpenID Foundation. (2022). *OpenID Connect RP-Initiated Logout 1.0*.
https://openid.net/specs/openid-connect-rpinitiated-1_0.html (retrieved October 28, 2026)

OpenID Foundation. (2023). *OpenID Connect Discovery 1.0 incorporating errata set 2*.
https://openid.net/specs/openid-connect-discovery-1_0.html (retrieved October 28, 2026)

PyJWT contributors. (n.d.-a). *API reference*. PyJWT documentation.
https://pyjwt.readthedocs.io/en/stable/api.html (retrieved October 28, 2026)

PyJWT contributors. (n.d.-b). *Digital signature algorithms*. PyJWT documentation.
https://pyjwt.readthedocs.io/en/stable/algorithms.html (retrieved October 28, 2026)

PyJWT contributors. (n.d.-c). *Installation*. PyJWT documentation.
https://pyjwt.readthedocs.io/en/stable/installation.html (retrieved October 28, 2026)

pytest-django. (n.d.). *Django helpers*. pytest-django documentation.
https://pytest-django.readthedocs.io/en/latest/helpers.html (retrieved October 28, 2026)

Sakimura, N., Bradley, J., & Agarwal, N. (2015). *Proof Key for Code Exchange by OAuth public clients* (RFC
7636). RFC Editor. https://www.rfc-editor.org/rfc/rfc7636 (retrieved October 28, 2026)

Sakimura, N., Bradley, J., Jones, M., de Medeiros, B., & Mortimore, C. (2023). *OpenID Connect Core 1.0
incorporating errata set 2*. OpenID Foundation. https://openid.net/specs/openid-connect-core-1_0.html
(retrieved October 28, 2026)

WitUS. (2026a). *OpenID provider configuration* [Discovery document].
https://accounts.witus.online/api/idp/.well-known/openid-configuration (read October 28, 2026)

WitUS. (2026b). *JSON Web Key Set*. https://accounts.witus.online/api/idp/jwks (read October 28, 2026)

WitUS. (2026c). *WitUS Accounts: first-party OAuth/OIDC client registry* [Source code].
`gemini/witus/lib/identity/clients.ts` and `lib/identity/id-token-alg.ts` (read October 28, 2026)

WitUS. (2026d). *WitUS Accounts: the ecosystem identity provider* [Source code]. `gemini/witus/lib/identity/auth.ts`,
`lib/identity/env.ts` and `node_modules/better-auth/dist/plugins/oidc-provider/index.mjs` (better-auth 1.6;
read October 28, 2026)

WitUS. (2026e). *gen-oidc-client.mjs* [Source code]. `gemini/witus/scripts/gen-oidc-client.mjs` (read October
28, 2026)

WitUS. (2026f). *Ecosystem SSO helpers and the authorize and callback routes* [Source code].
`claude/lang-chain/wanderlearn-field-reporter/src/lib/witus-sso.ts`, `src/lib/witus-sso-config.ts`,
`src/app/api/auth/witus/authorize/route.ts` and `callback/route.ts` (read October 28, 2026)
