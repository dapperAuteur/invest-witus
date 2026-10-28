# Invest.WitUS: v1 PRD

**Status:** building; tutorial chapters 00 to 04 tagged `v00` to `v04` (chapter 04 is the first Django page) · **Owner:** BAM ·
**Last updated:** 2026-10-27

> Tracked in `docs/` rather than `plans/` because `plans/` is gitignored ecosystem-wide and this document must
> survive a fresh clone. When building starts, planning moves here. Companion docs:
> [`02-ecosystem-integration.md`](02-ecosystem-integration.md) (contracts with the other WitUS apps),
> [`03-tutorial-roadmap.md`](03-tutorial-roadmap.md) (chapters and tags),
> [`04-decisions-log.md`](04-decisions-log.md) (dated decisions), and [`research/`](research/) (the research the
> decisions rest on, copied from the ecosystem's local planning notes).

Information, not advice. Nothing in this document recommends a security, a fund, a broker or a method for anyone.

---

## 1. Context

Invest.WitUS is a Python (Django) app in which a person picks an investing method taught in Learn.WitUS or
ElementaryMBA, practices it on a paper account first, and the app holds them to the method's rules, with a link
from every rule back to the lesson that teaches it. It is also the reference code for a follow-along Python
tutorial: one git tag per chapter, chapter text in `docs/chapters/`.

It is the first Python product in the WitUS ecosystem. Every other ecosystem app is TypeScript on Next.js and
Vercel, so no code is shared; the contracts (Sign in with WitUS, the signed Inbox webhook, signed events to
CentenarianOS, the footer, the header "Sign in" rule) are ported to Python. See
[`02-ecosystem-integration.md`](02-ecosystem-integration.md).

The project began from freeCodeCamp's course "Python Algorithmic Trading with SnapTrade, Massive, Alpaca"
(Carnes, 2026), which builds a momentum app in Django and invites learners to extend it. Per the course's own
notes, that demo has no scheduler, never sells or rebalances, places flat orders with no link to the balance, and
has no tests, deployment, login or risk language. Invest.WitUS keeps the idea (a rules-based method on a paper
account) and builds its own stack and code. BAM decided on 2026-10-27 that the original tutorial's stack
(Massive, SnapTrade) is not required.

The vetting analysis (ecosystem plan 38, rubric v1.2, 2026-10-27; local notes, summarized in section 4) scored the
idea **Test cheaply** for the portfolio and community goals and **Park** for business.

---

## 2. The one job

**Help a learner choose a taught investing method and stay with it, on paper first.**

Method adherence is the product; the broker is a commodity behind it. The app never picks securities: it applies
the method the user chose, to a universe and amounts the user set, and shows the lesson behind each rule.

---

## 3. Users

| Who | When | What they do | Notes |
|---|---|---|---|
| BAM | Phase 1 (now) | Investor and learner. Runs a method on his own Alpaca paper account, enters his real holdings by hand from statements, keeps a journal, does the monthly review. Builds a follow-along copy in his own repository from the tutorial. | The only user of phase 1. |
| Tutorial learners | Phase 1 for the code, phase 2 for the hosted app | Follow the Learn.WitUS Python tutorial in their own repositories, checking their work against this repo's tags. | The repo must read well in public; personal data stays out of git (invariant 6). |
| Learn.WitUS and ElementaryMBA learners | Phase 2, after the legal gate | Use the hosted app, education only, alongside the investing-methods course, to practice a method on paper. | Admitted from the waitlist. No access until gate G6 clears (section 13). |
| Waitlist sign-ups | Phase 1 onward | Leave a name and email. | Told plainly: a learning tool, not advice, not open to other users yet. |
| Readers of the repository | Always | Read it as a Python reference project. | Code quality and tests are part of the product. |

Vendors (Alpaca, the price provider) and regulators (SEC, the operator's state securities division, FINRA) bound
what each phase may do; see section 13 and [`research/03-law-and-vendor-terms.md`](research/03-law-and-vendor-terms.md).

**Design against:** a user trying to turn paper rules into live trades without the checklist; anyone wanting the
app to "pick stocks"; scraped or redistributed market data; leaked broker keys; gamified engagement. The UK FCA's
2024 experiment found push notifications and points or prize draws raised trading by 11% and 12%
([`research/01`](research/01-ux-benchmarks-and-three-directions.md), section 2).

---

## 4. Goals, verdicts, and the test

### 4.1 Goals per profile (plan 38 scores, first slice)

| Goal | Score | Verdict | What it means here |
|---|---|---|---|
| Portfolio / demo | 3.45 | Test cheaply | A credible, public, tested Python reference app, built chapter by chapter. |
| Community | 3.40 | Test cheaply | Students learn to code and to invest with it, education only, with the course. |
| Business | 2.90 | Park | No revenue in phase 1. Reopens at 100 waitlist sign-ups, or when a school or club asks to use it with students (which also triggers the minors research, gate G4). |

Why not Build: the white space is narrow (paid adherence journals and free trackers cover parts of the job), no
one but BAM has said yes yet, and the "other users" slice has an open legal gate. Gates G2 to G6 pass for the
first slice (own money, paper, waitlist) with the mitigations in section 6; G4 (minors) and G6 (adviser rules,
vendor terms) stay open for the later slice.

### 4.2 The cheapest honest test

1. Write method 1's rules as a rule block that both the lesson and the code read. **Method 1 is index investing
   with a fixed monthly contribution** (BAM, 2026-10-27, evening; this replaces plan 38's first draft, which
   started with 12-1 momentum). 12-1 momentum is method 2.
2. Tutorial chapters 00 to 03 (plain Python) with the same tags here; BAM follows in his own repository.
3. The reference app runs the method on BAM's paper account through one monthly review.
4. A waitlist: name and email only, no market data, no testimonials, no performance claims.
5. Re-score at the first review after chapter 03.

### 4.3 Kill criteria (written before the test runs)

| Assumption | Cheapest test | Kill threshold |
|---|---|---|
| BAM will follow the tutorial | Chapters 00 to 03 on a calendar | Chapter 01 not done in 3 weeks |
| Adherence features change behaviour | Two monthly reviews logged in the app | Two skipped reviews in a row |
| Lessons can state each rule unambiguously | Method 1's rules as a rule block before coding | A rule the lesson and the code read differently |
| Others want it | The waitlist | Fewer than 25 sign-ups in 60 days |
| Free tiers hold | Re-read vendor pages at each chapter | A free tier the first slice needs is removed |

**What flips it.** To Build (portfolio): BAM completes chapter 03 and runs two monthly reviews in the app without
skipping, and an outside reader judges the repo a credible Python reference. To Kill: BAM stops at chapter 01 for
three weeks, or stops using the app for two reviews in a row.

---

## 5. Decisions (summary; full dated list in [`04-decisions-log.md`](04-decisions-log.md))

All dated 2026-10-27 unless noted.

1. BAM's own accounts first; other users later, education only, with the course, from a waitlist.
2. All three goals scored (business, portfolio, community).
3. Python, as a learning project. This repo is the reference product; BAM builds a follow-along copy in his own
   repository.
4. The tutorial is a Learn.WitUS course. The investing-methods course goes to ElementaryMBA in full with a preview
   in Learn.WitUS.
5. Core idea: the user picks a taught method, the app holds them to it and links each rule to its lesson.
6. Research best-in-class UI, UX and DX and show at least three designs before code (done: research 01, the
   mockup).
7. Free and open-source tools preferred.
8. Credit and link freeCodeCamp's course; the course transcript stays out of the repo.
9. *Quantitative Momentum* (Gray & Vogel, 2016) is read for research and cited, never copied or committed.
10. Design: A (Plan and Logbook) as home, C (Lesson Lab) to start a method, B (Method Console) behind an Operator
    view, **and all three built as views the user can toggle between**.
11. Method order: index investing with a fixed monthly contribution first, then 12-1 momentum.
12. Repo `invest-witus` created, private for the test.
13. Waitlist wording approved: "Invest.WitUS is a learning tool, not advice, and not open to other users yet."
14. The original tutorial's stack is not required.
15. New requirements: in-app bug, feature and question reporter mirrored to WitUS Inbox; ecosystem footer, logo,
    privacy and terms pages; watch list per account; manual holdings entry with statement updates (CSV import
    later); live or updated prices for portfolio value; a trading journal in place of Edgewonk; other users only
    for education with the course.
16. Stack: Django 6.1 with django-ninja for the JSON API (research 04); pyright, ruff, pytest, uv; one annotated
    tag per chapter (research 02).

---

## 6. Invariants (from `CLAUDE.md`; these override any feature below)

1. **Information, not advice.** The app never recommends a security, never shows performance claims or
   testimonials on public pages, and never shows market data on public pages. Example symbols in the tutorial
   are placeholders (`INDEX`), not picks.
2. **Paper by default.** Live trading only behind an explicit checklist and separate keys. Never commit keys.
3. **Other users only for education, with the course,** and only after the legal gate in plan 38 (adviser
   registration question; vendor terms: Massive's individual plans and SnapTrade's free plan forbid serving other
   users; Alpaca accounts are self-directed).
4. **Tutorial tags are immutable.** A fix to a published chapter gets a new tag (`v03.1`) and the chapter page
   says which tag it was written against. Later chapters may add files but must not move or rename files from
   earlier chapters, so `compare/vNN-1...vNN` stays readable.
5. **Every chapter ends green:** its checkpoint test file `tests/test_chNN.py` passes, plus `ruff check`,
   `ruff format --check` and `pyright`.
6. **Personal data stays out of git:** real statements, journals and holdings go in `data/private/`
   (gitignored). The *Quantitative Momentum* book PDF is never copied, quoted at length or committed.
7. **Every method rule links to its lesson.** A rule without a published lesson says "lesson coming"; never
   invent a lesson URL (authoritative-values rule).

Added by this PRD, consistent with the above:

8. **No gamification on trading actions.** No points, prizes, streak counters, confetti or leaderboards. Nudges
   follow the calendar (a scheduled contribution or review), never price moves (research 01, FCA findings).
9. **The broker never holds the only copy.** Every order and fill is copied into the app's own tables when it
   happens (research 05: deleting an Alpaca paper account loses its keys and possibly its history).
10. **Every scheduled job is safe to run twice** and records its last run (Vercel Hobby cron has no retries).

---

## 7. Features and acceptance criteria

Phase 1 is BAM only. "Phase 2" items wait on the legal gate (section 13) unless marked otherwise.

### 7.1 Methods engine

A method is a **rule block**: a versioned TOML file (introduced in tutorial chapter 03) naming the method, its
parameters, and its rules. Each rule has an id, plain-words text, a check the engine can evaluate, and a
`lesson` field: the published lesson's URL, or empty until that lesson exists (shown as "lesson coming"). The
user's plan is separate: the method chosen plus the user's
own parameters (amount, day, universe, targets) and a one-sentence reason.

- **Method 1: index investing with a fixed monthly contribution** (`index-dca`, version 1, in
  `src/invest_witus/methods/index_dca.toml` at tag `v03`). Rules: buy once in every month of the plan; buy within
  the plan's buy window at the start of the month; buy the plan's fixed amount every time; buy only the funds named
  in the plan; no sell rule (a sale is a change of plan and needs a written reason). The plan file carries the
  start date, amount, symbols (placeholder `INDEX` in samples) and buy-window days.
- **Method 2: 12-1 momentum.** Rank the user's own universe by return from 12 months ago to 1 month ago (skipping
  the most recent month); hold the top N, equal weight; review monthly; trade only at a review. Built first on a
  CSV (chapter 14), then on stored data.
- **Any method taught in Learn.WitUS or ElementaryMBA can be added** as a new rule block plus any new check
  functions, without changing the engine. Candidate methods come from the course research (57 methods, kept in
  the ecosystem's local notes); none is added until its lesson states the rules.

Acceptance:
- The engine loads every rule block at startup and refuses one whose rule lacks the `lesson` key; a test asserts
  every shipped rule has the key and that every non-empty value is a URL listed as published (chapter 03 already
  tests that the rules file matches the checks).
- Lesson URLs are read from the rule block (or `docs/CHAPTERS.md` for tutorial links); none is typed into
  templates. A rule with "lesson coming" renders that text, not a link.
- Each evaluation produces one rule check per rule: status (pass, warn, fail) shown as text and icon, never color
  alone; the evidence (the number or date that decided it); the time evaluated; the lesson link.
- A deviation (a skip, an off-schedule order, drift past the method's band) cannot be recorded without a reason,
  and every deviation writes a journal entry.
- The app holds the user to their chosen rules; it never proposes a security outside the user's plan or
  universe.
- Method 2 warns before a sell-and-rebuy of the same security within 30 days (wash-sale rule, IRS Publication
  550) and teaches the rule with its date; it never teaches the retired $25,000 pattern-day-trader minimum as
  current (research 03, section 5).
- Changing a running plan's method or parameters creates a new plan version with a dated note; old reviews keep
  pointing at the version they judged.

### 7.2 Three views, all built, with a toggle

From [`research/01`](research/01-ux-benchmarks-and-three-directions.md) and the mockup
[`research/mockups/invest-witus-three-directions.html`](research/mockups/invest-witus-three-directions.html):

- **A, The Plan and the Logbook (home).** Environment band ("Paper account. Simulated money"), the next action
  with Confirm and Skip (Skip asks why), on-plan status with a short list of fixes, the plan's rules each with a
  "Why this rule" lesson link, target versus actual table, the last logbook entries, and performance kept small
  with the rule-following rate beside it.
- **B, Method Console (behind an "Operator" view).** Status bar (environment and host, equity, cash, last data
  pull, next job, last job result), rule checks table with evidence and lesson column, the order queue the rules
  produced (Approve or Hold with reason), drift table, paper results against the method's expected range (with
  the same data as a table and a sentence stating the result), deviation log, the live-promotion checklist.
  Read-only by default.
- **C, The Lesson Lab (to start a method).** The method's lessons in order; the current lesson's summary with
  "the rule this lesson gives you"; a lab panel that applies that rule to the paper account; a lab note that saves
  to the journal. Rules switch on one at a time as the learner reaches them. No points, streaks or completion
  rewards.

Acceptance:
- All three views render the same plan, rule checks and journal from the same queries; no view has data the
  others cannot reach.
- A toggle in the signed-in header switches A, B ("Operator") and C; the choice is saved per user and restored at
  the next sign-in; the toggle is keyboard operable and announces the current view.
- Starting a new method opens C by default; the everyday home is A.
- Every number in a table is right-aligned, tabular, with a caption and header `scope`; charts have a text
  summary and a data table (USWDS and GOV.UK guidance in research 01). Target: WCAG 2.2 AA.
- The paper or live environment is printed as text on every signed-in page.

### 7.3 Accounts, manual holdings and statement updates

- An **account** is one of: manual (any broker, entered by hand), Alpaca paper, or (later, behind the checklist)
  Alpaca live. Each has a label, a broker name, a type (for example taxable or retirement), and a currency (USD
  only in v1).
- **Manual holdings:** symbol, security kind (stock, ETF, mutual fund, cash), quantity, optional cost basis, and
  the statement's as-of date.
- **Statement update flow:** "New statement" asks for the as-of date, pre-fills the previous snapshot, lets the
  user edit quantities, add and remove holdings, and saves a new dated snapshot. History is kept; nothing is
  overwritten.
- **CSV import** of a statement or a broker export comes later (phase 1.5), with a column mapper.

Acceptance:
- Quantities and money are `Decimal` end to end (tutorial chapter 01); a test fails if a float reaches a money
  field.
- The holdings page shows each holding's value from the latest stored price with that price's date, and flags a
  price older than the expected update window as stale.
- Statement files are never uploaded to git; if the app stores an uploaded file at all, it is in private object
  storage, not the repository (open question 9).
- Each account's page lists its snapshots by date and shows the change between any two.

### 7.4 Prices and portfolio value

Per [`research/05`](research/05-prices-paper-balance-and-journals.md) (read 2026-10-27; every vendor term below is
from that file):

- **Phase 1 (BAM only, $0):**
  1. Alpaca accounts: read positions and the account from Alpaca's Trading API (`current_price`, `lastday_price`,
     `market_value`); no separate price feed for those holdings.
  2. Manual holdings and watch lists (including mutual funds): one nightly pull of end-of-day prices from Tiingo's
     free plan (its pages list US stocks, ETFs and mutual funds; mutual fund NAVs after 12 AM Eastern; free plan
     limits 50 requests an hour, 1,000 a day, 500 unique symbols a month; license "Internal Use Only").
  3. Backup for stocks and ETFs: Alpaca historical daily bars.
  4. Not used: yfinance (Yahoo's terms bar automated collection), Twelve Data's free key (licensed "non-display"),
     Alpha Vantage's free tier (25 requests a day; broad "commercial" definition).
- **Phase 2 (other users, education only):** no shared data key on any page another person sees. Each learner sees
  their own broker account's data, and brings their own Tiingo token for anything else (Tiingo's developer program
  allows this with clear "Tiingo" attribution and no handling of the user's Tiingo password). Written answers
  from Alpaca and Tiingo before launch.
- An on-page refresh re-reads Alpaca positions; it never calls the end-of-day provider per page view.

Acceptance:
- Closes are stored in the app's own table, so charts and values never re-fetch history.
- Every displayed price carries its date and source.
- No public page (landing, waitlist, privacy, terms) renders any price, chart of real quotes, or holding.
- The nightly pull is idempotent: running it twice for the same date leaves one row per security per date.

### 7.5 Watch list per account

- Each account can have one or more watch lists of symbols the user wants to follow; a watch list belongs to the
  user and one account.
- Shows the latest stored close with its date, and the change since the user added it.
- No buy button on a watch list. A symbol reaches a plan only by the user adding it to the plan's universe.

Acceptance: watch lists are private to their owner; adding a symbol the price provider does not know shows a
clear message instead of a zero price; removing a symbol keeps its history in the journal if it was ever traded.

### 7.6 Trading journal (the logbook)

Replaces paying for Edgewonk ($197 a year, read 2026-10-27). Research 05 recommends building the journal in
Django as direction A's logbook and taking ideas, not code, from Edgewonk, LuxAlgo Trade Journal (MIT) and Trading
Journal AI (MIT). If any code is ever copied, only from MIT-licensed projects, with their notices kept in a
`THIRD_PARTY_NOTICES` file. No GPL, AGPL or non-commercial-licensed code.

Phase 1 features:
- Automatic entries for every order and fill (copied as they happen) and every rule check that fails.
- Manual entries: note, exception (with the rule it breaks and a reason), skip (with a reason), lab note.
- Tags: small editable lists for mental state (confidence, focus, stress) and mistakes; rename and merge.
- Rule-following rate as the headline metric (share of scheduled actions done as the rules said).
- Plan versus actual for each scheduled action.
- Days and months marked by whether the rules were followed, not by profit or loss.
- A missed-action log kept out of performance numbers.
- Export to CSV.

Phase 2: read-only share of a journal with a course instructor or mentor, revocable.

Acceptance:
- The rule-following rate is computed from journal rows and reproducible in a test.
- Deleting a journal entry is a soft delete with a reason; automatic entries cannot be edited, only annotated.
- Personal journals never land in git (`data/private/` for any local export).

### 7.7 Alpaca paper trading and the monthly review

- Paper by default. Paper and live credentials are separate records (or separate env vars in phase 1); the host
  (`paper-api.alpaca.markets` for paper, per Alpaca's docs as read in research 01) is printed in the UI beside the
  environment.
- Orders the rules produce are **staged**, shown with the rule that produced each, and placed only when the user
  confirms. Hold requires a reason.
- **Practice budget:** Alpaca's paper account starts at a $100k default, and research 05 could not confirm that a
  different starting amount can be set (open question 2). The app keeps its own practice budget per plan: the
  user sets it, the app refuses staged orders that exceed the plan's remaining cash, and computes plan value from
  its own fills. The Alpaca balance behind it is ignored.
- The app states Alpaca's paper limits wherever paper results appear: no dividends, no slippage or market impact,
  no regulatory fees, random partial fills.
- **Live trading** is out of scope for phase 1 for anyone but BAM, and even for BAM stays locked behind a checklist:
  a minimum paper run, rule checks passing, results inside the method's expected range, a written incident plan,
  separate live keys added, and a typed confirmation. Live gets its own environment band.
- **Monthly review** (the test's unit): opens when the method's review day arrives; shows rule checks, scheduled
  actions done or skipped, exceptions with reasons and what they cost or saved, drift, and the lesson links;
  closing it writes a journal entry and (once connected) an event to CentenarianOS.

Acceptance:
- A paper key can never be sent to the live host: the client is built from the account's environment, and a test
  asserts it.
- Keys are read server-side only, never rendered in a page, never logged, never committed.
- A review cannot be closed with an unexplained skip.
- The daily job copies new Alpaca orders and fills into the app before evaluating rules.

### 7.8 In-app reporter: bug, feature, question

So BAM can send bugs and questions to Claude through the app. Pattern from Tour Manager OS (help bubble plus Inbox
mirror); contract in [`02-ecosystem-integration.md`](02-ecosystem-integration.md).

- A "Report" control on every signed-in page opens a short form: kind (bug, feature, question, other), message,
  and automatically the page path, current view (A, B or C), app version (git SHA) and browser user agent.
- Stored locally first (the system of record), then mirrored to WitUS Inbox in the background with a signed
  request. A failed mirror never blocks the user and is retried by the daily job.
- An admin list of reports with status (new, triaged, done) and a management command that prints open reports, so
  a coding session in this repo can read them.

Acceptance:
- The payload never includes keys, holdings, prices or journal text unless the user typed them into the message.
- Each kind maps to its own `form_type` (proposed names in doc 02); bugs are sent with `priority: "high"`.
- A test signs a body and verifies it with the Inbox contract's algorithm.

### 7.9 Ecosystem header, footer, logo, privacy and terms

- **Header:** whenever the visitor is not signed in (including while the session is loading), a link whose
  accessible name is exactly **"Sign in"**; when signed in, a **"Sign out"** control. Never renamed; add a second
  link if needed. A test tagged smoke asserts the link on the home page (shared UI/UX standard, 2026-10-16).
- **Footer:** the ecosystem footer recipe's structure, in this app's own palette: optional logo and one-line
  summary; the Rise Wellness callout verbatim with its disclaimer; three columns (Ecosystem siblings from the
  witus product list; This app: Roadmap, FAQ, Sign in; Partners and Legal: Rise Wellness, Terms, Privacy, Contact);
  the copyright line copied verbatim from the recipe.
- **Logo:** the WitUS brand assets copied from the witus repo's `public/brand/` (default variant `04-orbit-type`),
  drawn for dark backgrounds.
- **Privacy and Terms:** this app's own pages (not only witus.online's), dated, plain-language: education only,
  not advice; not a broker or an adviser; paper by default; what is stored (WitUS user id and email, plans,
  holdings entered, journal, waitlist name and email), where (Neon Postgres), who can see it (the owner only);
  broker keys server-side only; vendors named; no market data shown to others; how to delete your data; contact.
  Reviewed by a securities lawyer before any other user is admitted.
- **FAQ:** `docs/site/faq.md`, rendered at `/faq/` and linked from the footer and the landing page. Three parts:
  the questions a person should ask about any investing app, with this app's answers; the bodies that would
  govern it if it were a professional tool (SEC, FINRA, the Indiana Securities Division, SIPC, FDIC, CFPB, FTC,
  IRS; CFTC and NFA named as not applicable), with how to look a firm up and how to complain; and the laws and
  rules that would govern the app, each with its primary link. Every link was fetched the day the page was
  written; the page carries a "last checked" date. Information, never advice; no legal conclusions about this
  app, only what each law covers and that a lawyer is asked before other users are admitted.

Acceptance: every page carries "Not advice" and the paper notice where relevant; the smoke test fails if the
"Sign in" link is missing or renamed; footer links resolve.

### 7.10 Landing page and waitlist

The public home the domain will point to (domain is BAM's call, open question 1).

- Content: what the app is, in the positioning line "Pick a method you learned. Practice it on paper. The app
  keeps you to its rules and shows you the lesson behind each one."; that it is a learning tool built with the
  Learn.WitUS courses; the waitlist; links to the Learn.WitUS course pages ("lesson coming" until the URLs exist);
  the credit to freeCodeCamp's course.
- **Report a bad actor:** a visible callout on the landing page (and in the footer's Legal group) that links to
  `/faq/#report-a-bad-actor`, the FAQ's highlighted section listing the government desks that take reports
  (SEC, FINRA, the Indiana Securities Division, NASAA's regulator finder, CFPB, CFTC, the FBI's IC3, the FTC's
  ReportFraud). The app takes no complaints about other companies; it points people to the bodies that do.
- **Never on public pages:** market data, prices, charts of real quotes, performance claims, returns, testimonials,
  "risk-free", "automated trading", or anything that reads as which securities to buy.
- **Waitlist form:** name and email only, with the approved line "Invest.WitUS is a learning tool, not advice,
  and not open to other users yet." and a note that later access is for education with the course. Idempotent
  (one row per email), mirrored to Inbox as a waitlist signup, listed in the admin with status waiting or
  approved.

Acceptance: a test renders every public page and asserts none contains a price-like table or a performance
figure; submitting the same email twice keeps one row and shows the same thank-you.

### 7.11 Sign in with WitUS

OIDC against the ecosystem identity provider, with Authlib's Django client (research 04). Id tokens are EdDSA
(Ed25519); the client must accept EdDSA explicitly. Rows are keyed by the WitUS user id (`sub`). Details and
registration steps in doc 02.

Acceptance: sign-in, callback, sign-out (including global sign-out return) work on the production domain; a user
row is created on first sign-in and matched by `sub` after; no local passwords except the Django admin superuser
for operations.

### 7.12 Signed events to CentenarianOS and Learn.WitUS links

- **CentenarianOS:** signed events (HMAC-SHA256, the `X-Witus-*` headers) for a small set of owner-only facts,
  proposed: a monthly review closed, a scheduled contribution made or skipped. Needs a **new receiver route and
  secret in CentenarianOS** (doc 02). Sent with a deterministic event id so a resend is harmless; never blocks the
  user.
- **Learn.WitUS:** phase 1 is links only (rule to lesson; chapter to lesson via `docs/CHAPTERS.md`). Phase 2 adds
  an evidence endpoint (a learner's checkpoint or review posted to Learn), designed with the Learn.WitUS repo.

---

## 8. Non-goals (v1)

- Recommending securities, funds, brokers or methods; stock screening for picks; signals pushed to anyone.
- Live trading for anyone but BAM; any trading on other users' live accounts.
- SnapTrade or other aggregators in v1 (possible later, read-only, own accounts only).
- Options, crypto, margin, short selling, intraday trading.
- Tax advice or tax-lot accounting beyond showing the dated wash-sale rule.
- Social features, leaderboards, public profiles, sharing results publicly.
- Push notifications about prices; any engagement metric as a goal.
- A full backtesting platform (method 2 gets a CSV ranking and an expected range, not a strategy lab).
- Native mobile apps; multi-currency.
- Paid tiers (business is Parked).

---

## 9. Data model sketch

Django apps follow research 02's layout (`invest/core`, `accounts`, `methods`, `brokers`, `prices`, `adherence`,
`api`, `jobs`), adjusted as chapters land. Money and quantities are `Decimal`; times are UTC.

| Model | Key fields | Notes |
|---|---|---|
| `User` | WitUS `sub` (unique), email, display name, preferred view (A, B, C) | Created on first sign-in. |
| `Account` | owner, label, broker, kind (manual, alpaca_paper, alpaca_live), type, environment, currency | Live kind locked behind the checklist. |
| `BrokerCredential` | account, environment, key id reference, encrypted secret | Phase 2 only; phase 1 reads env vars. |
| `Security` | symbol, name, kind (stock, ETF, mutual fund, cash) | |
| `HoldingSnapshot` | account, as-of date, source (manual, statement, broker), note | One per statement or sync. |
| `Holding` | snapshot, security, quantity, cost basis (optional) | |
| `PriceClose` | security, date, close, source | Unique (security, date, source). |
| `WatchList`, `WatchItem` | owner, account, name; security, added at, added price | |
| `Method` | slug, version, name, rule-block source (TOML), lesson for the method | Loaded from files; versioned. |
| `Rule` | method, rule id, text, check kind, parameters, lesson URL or "lesson coming" | |
| `Plan`, `PlanVersion` | owner, account, method version, parameters (amount, day, universe, targets, N), practice budget, reason, start date | A change makes a new version. |
| `Order`, `Fill` | plan, broker ids, side, symbol, quantity, price, status, times | Copied from Alpaca as they happen. |
| `Review` | plan version, period, opened, closed, rule-following rate | Monthly. |
| `RuleCheck` | review or daily run, rule, status, evidence, evaluated at | |
| `JournalEntry` | owner, plan, kind (auto, note, exception, skip, lab), rule, order, body, tags, deleted reason | |
| `Tag` | owner, group (mental, mistake), name | Editable, mergeable. |
| `Report` | owner, kind, message, page, view, version, status, mirrored at, attempts | Bug reporter. |
| `WaitlistEntry` | name, email (unique), created, status (waiting, approved), consent text version, mirrored at | |
| `JobRun` | job name, run key (date), started, finished, status, detail | Idempotency and "last run" display. |
| `OutboundEvent` | destination, event id (unique), payload, attempts, sent at, last status | CentOS and Inbox retries. |

---

## 10. Stack

- **Language and tools:** Python 3.14 via uv; pytest (and pytest-django from the Django chapters); ruff; pyright.
- **Web:** Django 5.2 LTS (decision 33; 6.1 was planned) with django-ninja for the small JSON surface (cron route, event and evidence endpoints);
  server-rendered templates with htmx and django-htmx; pydantic-settings for settings; httpx for outbound calls;
  Authlib for OIDC.
- **Data:** Neon Postgres (`DATABASE_URL`), SQLite allowed only for local tests.
- **Hosting:** Vercel's Python runtime (Django detected from `manage.py`; one Vercel Function). **One daily cron**
  calling one route guarded by `CRON_SECRET`: Hobby cron runs once a day within the scheduled hour, in UTC, with
  no retries, so the job is idempotent and reconciles everything since its last successful run. Its steps: copy
  Alpaca orders and fills; pull end-of-day closes; evaluate rule checks; open a review when due; retry unsent
  Inbox mirrors and CentOS events.
- **Broker:** Alpaca Trading API, paper host by default.
- **Prices:** Alpaca positions; Tiingo end-of-day for everything else (section 7.4).
- **Later:** a FastAPI or Litestar sibling service in a late tutorial chapter, if an API framework is the point
  (research 04).
- **CI:** the ecosystem's Neon preview-branch cleanup workflow, once Neon is attached (doc 02).

---

## 11. Success measures

- Phase 1 (the test): chapters 00 to 03 done on schedule; two monthly reviews closed in the app without skipping;
  rule-following rate visible and reproducible; waitlist count at 60 days.
- Quality: every chapter ends green (invariant 5); no secret or personal data in git history.
- Never measured as success: time in app, sessions, trades placed, returns.

---

## 12. Phases

| Phase | Scope | Gate |
|---|---|---|
| 1 | BAM only: methods 1 then 2, three views, manual holdings, prices, watch lists, journal, Alpaca paper, monthly review, reporter, landing and waitlist, Sign in with WitUS, CentOS events, Learn links | None beyond the invariants |
| 1.5 | CSV statement import; journal attachments | Storage decision (open question 9) |
| 2 | Other users, education only, admitted from the waitlist with the course | Lawyer's answers (section 13), vendor written answers, minors research if students under 18, terms and privacy reviewed |

---

## 13. Legal and vendor constraints (summary)

From [`research/03-law-and-vendor-terms.md`](research/03-law-and-vendor-terms.md) and
[`research/05-prices-paper-balance-and-journals.md`](research/05-prices-paper-balance-and-journals.md). Not legal
advice; the open items are for a securities lawyer.

- **Adviser rules.** The federal definition (15 U.S.C. 80b-2(a)(11)) turns on advising **others** for
  **compensation**. Phase 1 (own money, no fee) is outside its words. Phase 2 signals or trades on identified
  users' accounts may be individualized advice; publishing the same rules to everyone on a schedule resembles the
  newsletters in *Lowe v. SEC* (1985). State registration (Form ADV, a Series 65 representative) would come long
  before any SEC threshold. Eleven questions for a lawyer are listed in research 03.
- **Alpaca.** Accounts are self-directed; no one else may trade for an account without Alpaca-approved trading
  authorization. Apps serving end users use the Broker API, listed for broker-dealers and RIAs. Alpaca's market
  data may not be distributed without written consent. Paper Only accounts get IEX data.
- **SnapTrade** (not used in v1): free plan is "testing and personal use only", one connected user; signals must be
  "pull-based"; no blanket trading authority.
- **Massive** (not used in v1): individual plans forbid "an application intended for use by end users other than
  you".
- **Tiingo:** free plan is internal and personal use only; phase 2 uses each user's own token under the developer
  program, with attribution.
- **Learner rules to teach, dated:** the pattern-day-trader $25,000 minimum was replaced (SEC order April 14,
  2026; brokers may phase in over 18 months); SIPC limits; the 30-day wash-sale rule. Paper accounts have no tax
  or SIPC effect.
- **Privacy:** phase 1 holds only the owner's data plus waitlist emails. Phase 2 may bring the FTC Safeguards
  Rule into play if the app is a "financial institution"; a lawyer decides. Minors (COPPA, school agreements) are
  not researched: required before any student under 18 is admitted.
- **Advertising:** FTC Endorsement Guides apply to anyone: no testimonials until there are real users, and then
  with any early-access connection disclosed; no performance claims.

---

## 14. Open questions

1. **Domain.** Which domain points at the landing page (for example `invest.witus.online`) is BAM's call. Blocks
   chapter 06 (deploy) only for the production domain, and the OIDC client registration (redirect URIs are exact
   match).
2. **Alpaca paper balance.** Can a new paper account start below $100k? Research 05: Alpaca's docs say "arbitrary
   amount" for the retired reset button; a staff reply (October 2025) says paper equity "cannot be changed"; no
   API was found. BAM to check the dashboard's "Open New Paper Account" dialog. The practice-budget design works
   either way.
3. **Price provider confirmation.** Tiingo's full Terms of Use page was blocked to the research fetcher; read it
   before chapter 08. Whether Tiingo's free plan includes IEX real-time is not stated.
4. **Alpaca data to users in phase 2.** May a third-party education app show users their own paper account's
   prices? Ask Alpaca in writing before phase 2.
5. **Lesson URLs.** Which Learn.WitUS and ElementaryMBA lessons exist for method 1's rules, and their URLs. Until
   then every rule says "lesson coming".
6. **Waitlist placement.** On this app's landing page, on the Learn.WitUS course preview, or both (plan 38 named
   the course preview; the landing page is the domain's target).
7. **CentenarianOS events.** Which events CentOS wants (proposed: review closed, contribution made or skipped),
   and whether any money amounts may cross.
8. **OIDC callback path and local development.** The Django callback path to register, and how to sign in
   locally given no localhost redirect is registered at the IdP (a dev-only admin login, or preview domains).
9. **File storage.** Whether statement uploads and journal attachments are stored at all in phase 1, and where
   (private object storage, never git).
10. **Spanish.** The shared UI/UX standard keeps English and Spanish strings for ecosystem apps; whether v1 ships
    Spanish via Django's translation framework, or English only until a translator reviews investing terms.
11. **Live trading for BAM.** The checklist's thresholds (minimum paper months; what "inside the expected range"
    means for method 1, which has no backtest envelope).
12. **Method 1's band.** The drift band or tolerance that turns a check from pass to warn, set with the lesson.

---

## References

Carnes, B. (2026, September 29). *Python algorithmic trading with SnapTrade, Massive, Alpaca* [Video course
announcement]. freeCodeCamp.
https://www.freecodecamp.org/news/python-algorithmic-trading-with-snaptrade-massive-alpaca/

Gray, W. R., & Vogel, J. R. (2016). *Quantitative momentum*. Wiley.

Internal Revenue Service. (2025). *Publication 550: Investment income and expenses*. Cited through
`research/03-law-and-vendor-terms.md`, which lists the full reference.

*Lowe v. SEC*, 472 U.S. 181 (1985). Cited through `research/03-law-and-vendor-terms.md`.

Vendor pages, statutes and design-system sources cited above are listed with retrieval dates in the References
sections of `research/01` to `research/05`.
