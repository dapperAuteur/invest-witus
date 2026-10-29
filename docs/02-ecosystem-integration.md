# Invest.WitUS: ecosystem integration contracts

**Last updated:** 2026-10-29 (WitUS Outbox: section 10, rows in sections 8 and 9) · Companion to [`01-prd.md`](01-prd.md).

Invest.WitUS is the first Python app in the WitUS ecosystem. Every other app is TypeScript, so nothing here is
shared code: each contract below is the ecosystem's existing contract, written for Django. Sources are the
ecosystem repos named in each section (read 2026-10-27). When a sibling repo changes its contract, the sibling
repo wins (authoritative-values rule); re-read it before building the chapter that uses it.

**Environment variables are listed by NAME only.** Values live in Vercel's environment settings and in a local
`.env` (gitignored); `.env.example` carries the names with empty values. Names marked *proposed* are owned by this
app and may change when the chapter is written; unmarked names are fixed by a sibling app's contract.

---

## 1. Signed webhook to WitUS Inbox (bug reporter and waitlist mirror)

**Contract source:** `claude/witus-inbox/docs/webhook-contract.md`. Reference senders:
`gemini/tour-manager-os/lib/feedback/inbox-mirror.ts` (help bubble with bug, feature, question) and
`claude/lang-chain/witus-triage-agent` (waitlist mirror).

**Request.** `POST` to the Inbox ingest URL with:

| Header | Value |
|---|---|
| `Content-Type` | `application/json` |
| `X-Witus-Source` | this app's source slug (lowercase kebab; must be registered in Inbox) |
| `X-Witus-Timestamp` | unix seconds, as a string |
| `X-Witus-Signature` | `sha256=` followed by the hex HMAC-SHA256 of `"{timestamp}.{raw_body}"` with the shared secret |

Body: `form_type` (kebab string, required), `submitter_email` (optional), `submitter_name` (optional), `priority`
(`"normal"` or `"high"`; high triggers Inbox's SMS path), `payload` (object, required).

Receiver behaviour: a timestamp more than 5 minutes from the receiver's clock is rejected; an unknown source or a
bad signature returns 401; a schema-invalid body returns 400. Failures return a bare `{"ok":false}`.

Checked against Inbox's code on 2026-10-29 for chapter 13 (decisions log, row 119): `submitter_name` must be 1 to
255 characters and `submitter_email` a valid address, so empty ones are left out; a `hmac_secret` under 32
characters empties Inbox's whole source list; the window applies both ways, so a retry signs again; a 500 is
Inbox's database failing; success is `{"ok":true,"id":"<uuid>"}`; there is no idempotency key. A source is
registered by appending `{"slug","hmac_secret"}` to the `INGEST_SOURCES` variable on the witus-inbox project, per
environment, and redeploying Inbox.

**Django implementation.**

- Serialize the body once to bytes, sign those exact bytes, and send those exact bytes (`httpx.post(url,
  content=raw, headers=...)`); never re-serialize after signing.
- `hmac.new(secret.encode(), f"{ts}.".encode() + raw, hashlib.sha256).hexdigest()`; compare nothing on the sender
  side, but use `hmac.compare_digest` in the test that verifies the round trip.
- Store first (the `Report` row, or a `WaitlistMirror` row for a waitlist entry, is the system of record), then
  send at once with a short timeout; a failure sets `attempts` and `last_error` and the daily job retries. Never
  fail the user's request on Inbox. Built in chapter 13 (`reports/inbox.py`, `reports/delivery.py`).
- Log only source, `form_type` and HTTP status. Never log the secret, the signature input, or the payload.

**Form types (proposed):**

| In-app action | `form_type` | `priority` |
|---|---|---|
| Report a bug | `invest-witus-bug-report` | `high` |
| Request a feature | `invest-witus-feature-request` | `normal` |
| Ask a question | `invest-witus-support-question` | `normal` |
| Other feedback | `invest-witus-feedback` | `normal` |
| Waitlist signup | `waitlist-signup` (the triage agent's existing name) | `normal` |

Payload for reports: `kind`, `message`, `report_id`, `page`, `view` (A, B or C), `app_version`, `user_agent`,
`admin_url`. Tour Manager OS maps the same kinds to its own `tour-*` form types, which is what lets the WitUS
Triage agent sort them; confirm the categories against `claude/lang-chain/witus-triage-agent/agent/schemas.ts`
before shipping chapter 13.

**Env (sender):** `INBOX_INGEST_URL`, `INBOX_SOURCE_SLUG`, `INBOX_INGEST_SECRET`.

---

## 2. Sign in with WitUS (OIDC)

**Source:** `gemini/witus/lib/identity/` (identity provider, client registry, id-token algorithm) and
`gemini/witus/scripts/gen-oidc-client.mjs`. Closest hand-built client:
`claude/lang-chain/wanderlearn-field-reporter` (`src/lib/witus-sso.ts` and its authorize and callback routes).

**Provider facts (from the witus repo):**

- The identity provider is better-auth's OIDC provider mounted at base path `/api/idp` on the accounts host. The
  discovery document is at `https://accounts.witus.online/api/idp/.well-known/openid-configuration` (read
  2026-10-28; the spec's path under the issuer, `/.well-known/openid-configuration`, answers 404 there). Read
  every endpoint from discovery rather than hardcoding paths; the document's `issuer` is
  `https://accounts.witus.online` and it lists an `end_session_endpoint`.
- **Id tokens are signed EdDSA (Ed25519).** Discovery also lists RS256 but no RSA key exists, so a client that
  defaults to RS256 fails at the callback. Configure the client to expect EdDSA.
- Redirect URIs match **exactly**. No localhost redirect is registered for any app.
- First-party clients skip the consent screen. Client id form: `witus-<slug>`.

**Django implementation (chapter 07, built 2026-10-28; decisions log rows 62 to 69):**

- No auth framework. `src/invest_witus_site/accounts/oidc.py`: httpx for discovery (tried at the spec's path,
  then `/api/idp/`, cached an hour), the token exchange (`client_secret_post`, PKCE S256) and userinfo; PyJWT
  for the id token, `algorithms=["EdDSA"]` only, keys fetched from `jwks_uri` and cached by `kid`; `iss`,
  `aud`, `exp` and `nonce` checked. Research 04's Authlib was not used: it takes its allowed algorithms from
  the discovery document, which lists RS256 too.
- Routes: `/auth/witus/login/` (name `sign-in`), `/auth/witus/callback/` (what the registry holds),
  `/auth/witus/logout/` (name `sign-out`, POST; ends the Django session only and goes home, never to the
  provider), and `/auth/witus/sign-out-everywhere/` (name `sign-out-everywhere`, POST; ends the Django session
  first, then sends the browser to `end_session_endpoint` with `client_id` and `post_logout_redirect_uri` = the
  site root, which the registry registers by default). The header and footer show "Sign out" always and the
  secondary "Sign out of WitUS everywhere", with its help text, while the client is on (BAM, 2026-10-29,
  witus task 128 option (b); decision 152).
- Rows key off the WitUS user id (`sub`), never the email: `accounts.WitusIdentity` (one-to-one to
  `auth.User`); the owner's superuser links once by verified email; `Account.witus_user_id` is filled.

**Env (app):** `WITUS_OIDC_CLIENT_SECRET` (the switch: off when unset), `WITUS_OIDC_ISSUER` (default
`https://accounts.witus.online`), `WITUS_OIDC_CLIENT_ID` (default `witus-invest`), `WITUS_OIDC_SCOPES` (default
`openid email profile`). Names and defaults in `.env.example`.

**Registration (BAM, in the witus repo):**

1. Choose the slug (proposed: `invest-witus`) and the production origin (the domain decision, PRD open question 1).
2. Add an entry to `ECOSYSTEM_APPS` in `gemini/witus/lib/identity/clients.ts`: slug, name, origin, `callbackPath`
   (the Django callback path chosen in chapter 07), any `extraRedirectUris` (apex and `www`, preview domains), and
   the post-logout path if not `/`.
3. Add the product to `gemini/witus/lib/products.ts` with its `oidcSlug` (this also feeds the ecosystem footer's
   sibling list).
4. Mint the client secret with `node scripts/gen-oidc-client.mjs <slug>`; set the IdP's per-slug secret env var
   (`WITUS_OIDC_SECRET__<SLUG>`, naming per that script) on the witus deployment, and the same value as
   `WITUS_OIDC_CLIENT_SECRET` on this app. Audit with `node scripts/check-oidc-env.mjs`.
5. Redeploy the identity provider after both env vars are set.

---

## 3. Signed events to CentenarianOS

**Sources:** sender `gemini/contractor-os/lib/events/income-emitter.ts`; receivers
`gemini/centenarian-os/app/api/events/income/route.ts` with `lib/events/verify-signature.ts`; a simpler pair is
`gemini/witus/lib/costs/centos-sender.ts` to CentOS `/api/events/vendor-bills`, whose receiver sets the owner from
an env var.

**Contract:** the same `X-Witus-*` HMAC headers as Inbox (section 1); body `{"events": [...]}`; a short timeout
(the sender uses 5 seconds); the sender never throws to its caller; each event carries a deterministic `event_id`
of the form `"{source_type}:{source_id}"` so the receiver can upsert on (user, event id) and a resend is harmless.
One secret per receiver route.

**What Invest.WitUS needs: a NEW receiver in CentenarianOS.** None of the existing CentOS routes accepts these
events. Proposed events (PRD open question 7 decides):

| `source_type` (proposed) | When | Fields |
|---|---|---|
| `invest_review` | A monthly review closes | review id, plan label, period, rule-following rate, closed at |
| `invest_contribution` | A scheduled contribution is made or skipped | plan label, scheduled date, done or skipped, skip reason present (yes or no) |

Owner mapping: phase 1 has one owner, so the receiver can set the owner from its own env var (the vendor-bills
pattern). Money amounts are left out until BAM decides they may cross.

**Env (sender, all *proposed*):** `CENTOS_EVENTS_URL`, `CENTOS_EVENTS_SECRET`, `CENTOS_EVENTS_SOURCE_SLUG`.

---

## 4. Learn.WitUS and ElementaryMBA links

- **Phase 1: links only.** Each rule in a rule block carries its lesson URL or the literal "lesson coming".
  Tutorial chapters map to lessons in `docs/CHAPTERS.md`. No URL is guessed: a lesson URL enters the repo only
  after the lesson is published and the URL has been opened.
- **Tutorial chapter pages** link Browse (`tree/vNN`), Diff (`compare/vNN-1...vNN`) and Zip (`archive/vNN.zip`)
  on GitHub; verify each resolves before a lesson is published (research 02, section C5).
- **Phase 2: evidence endpoint.** A learner's checkpoint result or closed review posted to Learn.WitUS. Designed
  with the `claude/witus-learn` repo when it is needed; nothing assumed here about its shape.

---

## 5. Header, footer, logo, legal pages

**Sources:** `gemini/witus/docs/shared-ui-ux-dx.md` (sign-in control rule, 2026-10-16),
`gemini/witus/public/brand/footer-recipe.md` (structure; reference implementation
`claude/fly-witus/src/components/site-footer.tsx`), `gemini/witus/public/brand/README.md` (logo variants).

- **Header "Sign in" rule.** Signed out (including while the session is loading): a link whose accessible name
  is exactly "Sign in", to the sign-in route. Signed in: a "Sign out" control. Never rename it; add a second link
  instead. Keep a smoke-tagged end-to-end test asserting the link on the home page (for this repo: a pytest
  marker `smoke`, with Django's test client for the markup and a browser test once Playwright for Python is
  added).
- **Footer.** Same structure as every ecosystem app, this app's own colors: optional logo, name and one-line
  summary; the Rise Wellness callout **verbatim**, disclaimer byte-identical; three columns (Ecosystem: siblings
  from `gemini/witus/lib/products.ts`; This app: Roadmap, Sign in; Partners and Legal: Rise Wellness, Terms,
  Privacy, Contact); the copyright line copied verbatim from the recipe. Collapses to one column on mobile; focus
  visible on every link. Implement as a Django template include fed by a small Python list that mirrors the
  products file (the recipe accepts the copy-paste cost).
- **Logo.** Copy the chosen variant's files (default `04-orbit-type`: favicon SVG, 16, 32 and 180 PNGs, logomark,
  wordmark) from `gemini/witus/public/brand/` into `static/brand/witus/`. They are drawn for dark backgrounds.
- **Legal pages.** Many ecosystem apps link witus.online's terms and privacy; Invest.WitUS hosts its own (PRD
  7.9) because it needs education-only, not-advice and broker-key language. The footer's Terms and Privacy point
  at this app's pages.

---

## 6. Waitlist

**Sources:** `claude/lang-chain/witus-triage-agent` (`lib/waitlist.ts`: idempotent insert on a unique email;
`app/api/waitlist/route.ts`: background Inbox mirror with `form_type` `waitlist-signup` and payload `{email,
submitted_at}`; an admin list), and `stream-witus` (waitlist status waiting or approved, an owner email, a
signups-open switch).

For Django: a `WaitlistEntry` model with a unique email, a form view that always shows the same thank-you (so it
does not reveal whether an email was already on the list), the Inbox mirror from section 1, and the Django admin
as the list. Fields collected: name and email only.

---

## 7. Repo conventions to apply at onboarding

- **Shared rules block.** Add `invest-witus` to `targets` in `gemini/witus/docs/ecosystem-repos.json` and run
  `node scripts/propagate-claude-rules.mjs --write` from the witus repo; the managed block lands below this repo's
  hand-written identity section in `CLAUDE.md`.
- **Branch guard.** `.githooks/pre-commit` (present); each clone runs `git config core.hooksPath .githooks` once.
- **Neon preview cleanup.** The workflow from `gemini/witus/.github/templates/` is in `.github/workflows/` since
  chapter 06; the `NEON_PROJECT_ID` repository variable and the `NEON_API_KEY` secret are task 05.
- **Plans.** `./plans/NN-description.md` and `./plans/user-tasks/` (gitignored); this PRD and its companions stay
  in `docs/`.

---

## 8. Other env var names (this app)

| Name | Used for | Status |
|---|---|---|
| `DJANGO_SECRET_KEY` | Django signing | Vercel's Django example's name |
| `DJANGO_DEBUG` | `"1"` locally only | Vercel's Django example's name |
| `DATABASE_URL` | Neon Postgres, the pooled connection the app uses | Set by the Neon integration (chapter 06) |
| `DATABASE_URL_UNPOOLED` | Neon's direct connection; the settings' `direct` alias for `migrate --database direct` | Set by the Neon integration (chapter 06) |
| `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` | `invest.witus.online` and `https://invest.witus.online`; Vercel's own host names are added from `VERCEL_URL`, `VERCEL_BRANCH_URL`, `VERCEL_PROJECT_PRODUCTION_URL` | This app's names (chapter 06) |
| `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_EMAIL`, `DJANGO_SUPERUSER_PASSWORD` | `createsuperuser --noinput`, once, in the owner's shell | Django's names (chapter 06) |
| `CRON_SECRET` | Bearer token Vercel cron sends to `/api/cron/pull-prices/` once a day (chapter 08); unset, the route answers 503 | Vercel's name |
| `ALPACA_PAPER_KEY_ID`, `ALPACA_PAPER_SECRET_KEY` | Alpaca paper Trading API, phase 1 | used since chapter 11 (2026-10-29) |
| `ALPACA_LIVE_KEY_ID`, `ALPACA_LIVE_SECRET_KEY` | Alpaca live, only after the checklist | *proposed*; absent by default |
| `TIINGO_API_KEY` | End-of-day prices, phase 1 (owner's own key); unset, the pull reads `PRICES_CSV_DIR` | This app's name (chapter 08; this table said `TIINGO_API_TOKEN` until then) |
| `OUTBOX_TRIGGER_ENABLED` | WitUS Outbox's kill switch (section 10): exactly `true` sends the owner's drafts, anything else keeps them here | The guide's name |
| `OUTBOX_INGEST_URL`, `OUTBOX_SOURCE_SLUG`, `OUTBOX_INGEST_SECRET` | WitUS Outbox's ingest URL, this app's slug in Outbox's `INGEST_SOURCES`, its secret (section 10) | The guide's names |
| `OWNER_WITUS_SUB` | The phase 1 owner's WitUS user id; everyone else sees the landing page | *proposed* |

---

## 9. What BAM must do outside the editor (registration checklist)

Each item becomes a task file in `plans/user-tasks/` when its chapter is next (operator-task rule).

| # | Action | Where | Blocks |
|---|---|---|---|
| 1 | Decide the production domain and point it at the Vercel project | DNS and Vercel | Chapter 06 production deploy; item 3's redirect URIs |
| 2 | Create the Vercel project and attach Neon; set `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`; migrate and make the owner (`plans/user-tasks/04`); `NEON_PROJECT_ID` and `NEON_API_KEY` (`05`); `CRON_SECRET` is task 09 | Vercel, Neon, GitHub | The live site; chapter 07's origin; chapter 08 |
| 3 | Register the OIDC client (section 2, steps 1 to 5) and set `WITUS_OIDC_*` on this app. Steps 1 to 4's IdP half done 2026-10-28 (`invest` entry, `WITUS_OIDC_SECRET__INVEST` on witus-online); the rest is task 07 | witus repo and both Vercel projects | Chapter 07's first real sign-in |
| 4 | Create Alpaca paper API keys; set `ALPACA_PAPER_*`; check whether "Open New Paper Account" asks for a starting amount | Alpaca dashboard, Vercel | Chapter 11 |
| 5 | Create a Tiingo account and token; set `TIINGO_API_KEY` and `CRON_SECRET` (done 2026-10-28); read Tiingo's full Terms of Use; merge, migrate and run the cron once (task 09) | Tiingo, Vercel | Real closes on production and the owner's valued pages (chapter 08) |
| 6 | Register the Inbox source: `openssl rand -hex 32` per environment (or `python -c "import secrets; print(secrets.token_hex(32))"`), append `{"slug": "invest-witus", "hmac_secret": "..."}` to witus-inbox's `INGEST_SOURCES`, redeploy Inbox, set `INBOX_*` here | witus-inbox Vercel, this app's Vercel | Chapter 13 and the waitlist mirror (chapter 04) |
| 7 | Approve and build the new CentenarianOS receiver route; mint its secret; set `CENTOS_EVENTS_*` here | centenarian-os repo and Vercel | Chapter 15 |
| 8 | Add `invest-witus` to `ecosystem-repos.json` and run the propagate script | witus repo | Shared rules in this repo's `CLAUDE.md` |
| 9 | Before phase 2: a securities lawyer's answers (research 03), written answers from Alpaca and Tiingo, minors research | Outside counsel, vendors | Any other user |
| 10 | Register the Outbox source: one secret per environment, `{"slug","hmac_secret","workspace_name"}` appended to witus-outbox's `INGEST_SOURCES`, redeploy Outbox, the same secret here, then `OUTBOX_TRIGGER_ENABLED=true` when ready (task 22) | witus-outbox Vercel, this app's Vercel | Section 10: the owner's post drafts reaching Outbox |

---

## 10. Signed drafts to WitUS Outbox (the owner's posts)

**Contract source:** the integration guide `examples/INTEGRATE.md`, the contract `examples/README.md` and the
reference sender `examples/sender.ts` in `claude/witus-outbox` (fetched from its `main` on 2026-10-29), checked
against Outbox's `app/api/ingest/route.ts`, `lib/hmac.ts` and `lib/ingest-sources.ts`. Outbox has no recipe for
this app under `examples/triggers/`; the nearest is `witus-online.md`. The guide does not ask a publisher to
contribute a recipe.

**What it is.** WitUS Outbox is the ecosystem's human-reviewed social-publishing queue. A publisher app posts a
signed draft; the owner edits, schedules, approves or rejects it in Outbox, and Outbox posts it. This app sends
one thing: a post the site owner writes by hand in the admin (**Draft a post**), for the site launch (once) or a
milestone of their choosing. No event in the app writes a post by itself.

**Request.** The same four headers and signature as section 1 (`invest_witus_site/signing.py`, shared by both
clients). Body, serialized once and signed as sent:

| Field | This app sends |
|---|---|
| `external_ref` | `site-launch-<platform>` or `milestone-<draft id>-<platform>`; Outbox is idempotent on `(source, external_ref)`, so a resend answers with the row it already has |
| `platform` | `linkedin`, `twitter`, `bluesky` (the guide's default three; Outbox accepts eight, the others need an image) |
| `caption` | the owner's text, at most 280 characters for every platform |
| `media_urls` | always `[]` |
| `scheduled_at` | a placeholder a week ahead (the guide's), UTC with `Z` |
| `as_draft` | always `true`: nothing is posted until the owner approves it in Outbox |

No `links` and no `social_profile_ids`: Outbox picks profiles from the slug's workspace when the draft is promoted.
Answers: 200 `{"ok":true,"id":"<uuid>","status":"draft"}` (or the existing row's status on a repeat); 401 for a
missing header, an unknown slug, a bad signature or a stale timestamp, not told apart; 400 for a body that is not
JSON or not the schema; 500 for Outbox's database.

**The guide's gates, in Python.**

1. *Kill switch:* `OUTBOX_TRIGGER_ENABLED` must be exactly `true`, as the guide's helper checks; unset, `1` or
   `True` keep everything off and the row reads "Off, will retry".
2. *Owner only:* the admin pages are superuser only, and a draft not written by a superuser is blocked at send.
   The guide reads an owner id from an env var; this app's owner is its superuser (chapter 11's rule).
3. *Per-user opt-in:* not built. There are no other users until the legal gate (PRD, invariant 3).

**Never account data.** `outbox/guard.py` checks every field of every body before it is signed, and the admin
form checks the text before it is saved: only the six fields above, no media, always a draft, and no money
amount, percentage, share count, cashtag or symbol that any table in the app records (held, on a statement,
watched, in a plan, journaled, ordered on paper or priced). A blocked row is never sent or retried.

**Where this app differs from the guide, and why.**

- The guide says to copy `sender.ts` byte for byte. This is Python, so `outbox/client.py` ports its contract and
  the tests check the signature against one computed with `openssl` and against Outbox's verification, ported.
- The guide sends after the response with Next.js `after()` and does not retry. Vercel's Python runtime has no
  `after()`, so the send is inline with a 5-second timeout after the row is saved (chapter 13's pattern). A draft
  that never reached Outbox is retried by the nightly cron and by **Send again**; that is safe because Outbox
  answers a repeated `external_ref` with its existing row. Posting to the networks stays Outbox's job.
- The guide logs `source`, `platform`, `external_ref` and status; so does this app, and never the caption.

**Triggers considered** (decisions log, row 129): built, the owner's **Draft a post** (launch once, or a
milestone). Declined: a tutorial chapter tagged (the tutorial is private and tags are pushed from git, not from
the app); a blog post about Invest (bam-landing-page publishes the blog and has its own Outbox recipe); an
automatic launch post (no event in the app marks a launch, so the owner drafts it); anything from an account.

**Env (sender):** `OUTBOX_TRIGGER_ENABLED`, `OUTBOX_INGEST_URL`, `OUTBOX_SOURCE_SLUG`, `OUTBOX_INGEST_SECRET`.
