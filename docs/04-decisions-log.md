# Invest.WitUS: decisions log

Dated decisions, newest last within each day. "BAM" marks a decision BAM made; "Research" marks a recommendation
from a research file that BAM has not yet ruled on; "Vetting" marks the rubric verdict. Sources: the ecosystem's
local seed note and vetting analysis (plan 38), and [`research/`](research/). Add new rows at the bottom; never
rewrite an old row, add a superseding one.

| # | Date | Who | Decision | Source |
|---|---|---|---|---|
| 1 | 2026-10-27 | BAM | Whose money: BAM's own accounts first. Other users later, with a waitlist from day one. | Seed note, decision 1 |
| 2 | 2026-10-27 | BAM | Goal: all three profiles (business, portfolio, community). Students should be able to use it to learn to code, to invest, or both. | Seed note, decision 2 |
| 3 | 2026-10-27 | BAM | Language: Python, as a learning project for BAM. | Seed note, decision 3 |
| 4 | 2026-10-27 | BAM | `invest-witus` is the reference product, built by Claude like the other ecosystem tools. BAM builds a follow-along version in a separate repository of his own, uses and tests the real app while learning, and reports tutorial bugs. | Seed note, decision 4 |
| 5 | 2026-10-27 | BAM | The tutorial is a Learn.WitUS course followed chapter by chapter. The investing-methods course goes to ElementaryMBA in full, with a preview in Learn.WitUS. | Seed note, decision 5 |
| 6 | 2026-10-27 | BAM | Core idea: the user picks any method taught in Learn.WitUS or ElementaryMBA; the app helps them stay with it and links each rule to the course content. Method adherence is the product; the broker is a commodity. | Seed note, decision 6 |
| 7 | 2026-10-27 | BAM | Before any code: research best-in-class UI, UX and DX, and show at least three designs. | Seed note, decision 7 |
| 8 | 2026-10-27 | BAM | Free and open-source tools preferred. | Seed note, decision 8 |
| 9 | 2026-10-27 | BAM | Cite and link freeCodeCamp's course. The course transcript stays out of the repo. | Seed note, decision 9 |
| 10 | 2026-10-27 | BAM | Gray and Vogel, *Quantitative Momentum* (Wiley, 2016): read for research and cite; never copy or commit. | Seed note, decision 10 |
| 11 | 2026-10-27 | BAM | Priority: this Python tutorial app comes before the REIT-versus-trust and money-history course ideas. | Seed note, decision 11 |
| 12 | 2026-10-27 | Vetting | Rubric v1.2 scores for the first slice: portfolio 3.45 Test cheaply; community 3.40 Test cheaply; business 2.90 Park (reopens at 100 waitlist sign-ups or a school or club asking). Kill criteria in PRD 4.3. | Plan 38 |
| 13 | 2026-10-27 | Research | Framework: Django 6.1 with django-ninja for the JSON API for version 1 and the tutorial; FastAPI or Litestar later as a sibling service chapter if an API framework is the point. | Research 04 |
| 14 | 2026-10-27 | Research | Toolchain: Python 3.14 via uv, pytest, ruff, pyright (not mypy); htmx with django-htmx for pages; one annotated tag per chapter (`vNN`), not branches or solution folders. | Research 02 |
| 15 | 2026-10-27 | BAM | Design: A (Plan and Logbook) as the everyday home, C (Lesson Lab) to start a method, B (Method Console) behind an Operator view, **and all three built as views the user can toggle between**. | Task 123 answer 1 |
| 16 | 2026-10-27 | BAM | Method order: index investing with a fixed monthly contribution first, then 12-1 momentum. Supersedes plan 38's first draft, which started with 12-1 momentum. | Task 123 answer 2 |
| 17 | 2026-10-27 | BAM | Create the `invest-witus` repository, private for the test. | Task 123 answer 3 |
| 18 | 2026-10-27 | BAM | Waitlist wording approved: "Invest.WitUS is a learning tool, not advice, and not open to other users yet." | Task 123 answer 4 |
| 19 | 2026-10-27 | BAM | The original tutorial's stack (Massive, SnapTrade, Alpaca) is not required. | Seed note, evening answers |
| 20 | 2026-10-27 | BAM | Add an in-app bug, feature and question reporter that uses the ecosystem pattern (Inbox), so BAM can send bugs and questions to Claude through the app. | Seed note, evening answers |
| 21 | 2026-10-27 | BAM | Add the ecosystem footer, logo, privacy page and terms; the header Sign in control is never removed. | Seed note, evening answers |
| 22 | 2026-10-27 | BAM | Add a watch list per account. | Seed note, evening answers |
| 23 | 2026-10-27 | BAM | Manual holdings entry: BAM enters his real investments and updates them when statements arrive; CSV import later. | Seed note, evening answers |
| 24 | 2026-10-27 | BAM | Live or updated prices for portfolio value from a price API; free or open preferred; check each vendor's terms for other users. | Seed note, evening answers |
| 25 | 2026-10-27 | BAM | A trading journal in the app instead of paying for Edgewonk ($197 a year): adapt an open-source journal or build it as direction A's logbook, per the license research. | Seed note, evening answers |
| 26 | 2026-10-27 | BAM | Other users allowed only for educational purposes with the course; the terms and the waitlist copy say so; the plan 38 legal gate still applies. | Seed note, evening answers |
| 27 | 2026-10-27 | Research | Alpaca paper balance: a custom starting amount could not be confirmed (staff reply: paper equity "cannot be changed"; no API). The app keeps its own practice budget per plan and ignores the $100k behind it; BAM checks the dashboard's new-account dialog. | Research 05, section 1 |
| 28 | 2026-10-27 | Research | Prices, phase 1: Alpaca positions for Alpaca accounts plus a nightly Tiingo end-of-day pull for everything else (including mutual funds); Alpaca daily bars as backup; not yfinance, Twelve Data free or Alpha Vantage free. | Research 05, section 2.13 |
| 29 | 2026-10-27 | Research | Prices, phase 2: no shared data key on any page another person sees; each user sees their own broker account's data or uses their own Tiingo token, with Tiingo credited; written answers from Alpaca and Tiingo before launch. | Research 05, section 2.13 |
| 30 | 2026-10-27 | Research | Journal: build it in Django as the logbook; take ideas, not code, from Edgewonk, LuxAlgo Trade Journal (MIT) and Trading Journal AI (MIT). TradeNote is GPL-3.0; no GPL, AGPL or non-commercial code. Any copied MIT code keeps its notice. | Research 05, section 3.5 |
| 31 | 2026-10-27 | Claude | Tutorial chapters 00 to 03 written and tagged `v00` to `v03` (plain Python: setup, Decimal plan math, prices from CSV and the `plan` command, the rule block, plan, journal and the `review` command). | Tutorial branch |
| 32 | 2026-10-27 | Claude | PRD, integration contracts, roadmap and research copies moved into `docs/` so planning can live in the repo. | This branch |

## 2026-10-27 (evening)

- **Domain:** `invest.witus.online` (Invest.WitUS.Online / Invest.WitUS). BAM.
- **Owner's usage dashboard** added to the PRD (7.13) and the roadmap (chapter 16). BAM: "app should have admin
  dashboard for me to track usage."
- **OIDC routes:** `/auth/witus/login/`, `/auth/witus/callback/`, `/auth/witus/logout/`. Claude, recorded in the
  registry entry.
- **Not on Vercel yet:** nothing deployable exists until chapter 04 (the Django landing page); the Vercel
  project and DNS record come with chapter 06.

