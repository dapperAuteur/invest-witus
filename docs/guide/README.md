# Invest.WitUS user guide: the map

This folder is the owner's manual for the app as it runs today at https://invest.witus.online (chapters 00 to
08 of the tutorial, tag `v08`). It is written for the person who uses the app, not the person who builds it;
the chapters in [`../chapters/`](../chapters/) are the build.

Three files:

| File | What it is for |
|---|---|
| [`using-invest-witus.md`](using-invest-witus.md) | The user guide: one section per feature, with the exact labels, what you should see, and what can go wrong. |
| [`recording-scripts.md`](recording-scripts.md) | One screen-recording script per feature, in the house format from the ecosystem's tutorial plans: steps, narration lines, retake notes. |
| [`recording-checklist.md`](recording-checklist.md) | The pre-flight list before any recording session, and where each clip is published. |

## What the app is for

Invest.WitUS helps a learner pick an investing method taught in Learn.WitUS or ElementaryMBA and stay with it,
on paper first. It holds statements typed in from a brokerage, values them at stored end-of-day closes, and
(in later chapters) checks what you did against the method's rules, with a link from every rule to its lesson.

Two sentences govern every page:

- **Information, not advice.** The app recommends nothing, shows no market data on public pages, and makes no
  performance claims. The example symbols throughout these files (`INDEX`, `OTHER`, `FUNDX`) are placeholders,
  and every number is made up.
- **Paper first.** The app holds no money and moves none. Live trading is a later chapter, behind a checklist
  and separate keys.

## Who can sign in today

The owner. Sign in with WitUS works on the production domain for the owner's WitUS account (chapter 07); the
owner also has a password login for the admin at `/admin/` (chapter 05). Everyone else sees the public pages and
can join the waitlist. Approving a waitlist entry changes its status and nothing else: the app opens to other
learners only after the legal gate in the PRD, and it sends no email in this phase.

## The pages

| Path | What it is | Who sees it |
|---|---|---|
| `/` | The landing page: the positioning line, how it works, the courses, the "Report a bad actor" callout, the waitlist form, the roadmap, the credit | Everyone |
| `/faq/` | The FAQ, opening with "Report a bad actor" | Everyone |
| `/privacy/` | The privacy page | Everyone |
| `/terms/` | The terms of use | Everyone |
| `/contact/` | How to reach the operator (email only in this phase) | Everyone |
| `/waitlist/` | The waitlist form on its own page; `/waitlist/thanks/` is the thank-you | Everyone |
| `/healthz/` | Up, version, database: JSON for a monitor | Everyone |
| `/auth/witus/login/` | Sign in with WitUS (the header's "Sign in" link goes here) | Everyone; signed-in people are sent home |
| `/admin/` | The owner's back office: accounts, statements, holdings, waitlist entries, daily closes, WitUS identities | Staff, with the password login |
| `/accounts/` | Your accounts, each valued at the latest stored close | Signed in; a visitor is sent to the sign-in |
| `/accounts/<id>/` | One account: the latest statement, each line valued, with the close's date and source | The account's owner only |
| `/api/cron/pull-prices/` | The nightly price pull, called by Vercel's cron with a bearer secret | Vercel's cron, or the owner with the secret |

## The features

In the order a new owner meets them. Each row links the guide section and the recording script.

| # | Feature | Guide | Script |
|---|---|---|---|
| 1 | The landing page and the waitlist | [The waitlist](using-invest-witus.md#the-waitlist) | [Script 1](recording-scripts.md#script-1-the-landing-page-and-the-waitlist) |
| 2 | Sign in with WitUS and sign out | [Sign in and sign out](using-invest-witus.md#sign-in-and-sign-out) | [Script 2](recording-scripts.md#script-2-sign-in-with-witus-and-sign-out) |
| 3 | Add an account and enter a statement | [Accounts](using-invest-witus.md#accounts) and [Statements](using-invest-witus.md#statements) | [Script 3](recording-scripts.md#script-3-add-an-account-and-enter-a-statement) |
| 4 | Compare two statements | [Statements](using-invest-witus.md#statements) | [Script 4](recording-scripts.md#script-4-compare-two-statements) |
| 5 | Account values and the nightly pull | [Account values](using-invest-witus.md#account-values) and [The nightly price pull](using-invest-witus.md#the-nightly-price-pull) | [Script 5](recording-scripts.md#script-5-account-values-after-the-nightly-pull) |
| 6 | The watch list (chapter 09, on its branch, not merged) | [The watch list](using-invest-witus.md#the-watch-list-when-chapter-09-lands) | [Script 6](recording-scripts.md#script-6-the-watch-list-when-chapter-09-lands) |
| 7 | The FAQ and "Report a bad actor" | [The FAQ and Report a bad actor](using-invest-witus.md#the-faq-and-report-a-bad-actor) | [Script 7](recording-scripts.md#script-7-the-faq-and-reporting-a-bad-actor) |
| 8 | Skip a month, close it, and export the logbook | [The journal and the monthly close](using-invest-witus.md#the-journal-and-the-monthly-close-chapter-12) | [Script 8](recording-scripts.md#script-8-skip-a-month-close-it-and-export-the-logbook) |
| 9 | Report a problem or ask a question | [Report a problem or ask a question](using-invest-witus.md#report-a-problem-or-ask-a-question-chapter-13) | [Script 9](recording-scripts.md#script-9-report-a-problem-or-ask-a-question) |

What the app will not do is its own section: [What the app will not do](using-invest-witus.md#what-the-app-will-not-do).

## Keeping these files true

Every label, path and button name in this folder was read from the templates under
`src/invest_witus_site/*/templates/`, the admin registrations (`holdings/admin.py`, `pages/admin.py`,
`prices/admin.py`, `accounts/admin.py`) and the chapter text, on 2026-10-28 at tag `v08`. When a chapter changes
a label, change it here in the same branch. The watch list section and script are read from chapter 09's
branch (`feat/tutorial-ch09`, commit `7139326`) ahead of its merge and are marked; re-read them against the merged
templates when that chapter lands.
