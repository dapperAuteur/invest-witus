# Using Invest.WitUS

The user guide for the app as it runs at tag `v08` (chapters 00 to 08). One section per feature, in the order a
new owner meets them. Each section says what the feature is for, the exact clicks with the labels as they
appear, what you should see, and what can go wrong.

Two things to know before the first click:

- **Two logins exist.** The public header's **Sign in** is Sign in with WitUS: your WitUS account, no password.
  The admin at `/admin/` has its own password login, the superuser made in chapter 05. The admin login does not
  sign you in to the public site, and the WitUS sign-in reaches the admin only once your WitUS identity is
  attached to the superuser (see [Sign in and sign out](#sign-in-and-sign-out)).
- **Two copies of the app exist.** The production site at https://invest.witus.online, and a laptop copy under
  `runserver` at http://127.0.0.1:8000/. The laptop copy has no WitUS client secret, so its **Sign in** shows a
  stub page, and it reads prices from CSV files instead of Tiingo. Everything else is the same.

Every symbol on these pages (`INDEX`, `OTHER`, `FUNDX`, `CASH`) is a placeholder and every number is made up.
Information, not advice.

## Sign in and sign out

**What it is for.** One WitUS account signs you in to every app in the ecosystem. Signing in here unlocks the
**Accounts** page, where your statements are valued. Nothing on the public site needs an account.

**Sign in.**

1. On any page, press **Sign in** at the right end of the header (the footer has the same link under
   **Invest.WitUS**). The link's name is exactly "Sign in" on every page; the app's own tests fail if it changes.
2. The app sends you to accounts.witus.online. If the provider already knows you in this browser, it may send
   you straight back. Otherwise you see **Sign in with WitUS**, the line "One account for the whole WitUS
   ecosystem. We'll email you a sign-in link.", an **Email** field and the button **Email me a sign-in link**.
3. Type your email and press the button. The page says **Check your email for a sign-in link.**
4. Open the link from your inbox. The provider sends you back to the app's home page.

**What you should see.** At the top of the home page, one line: **Signed in as** your name, and, if you are the
owner, the link **Open the admin**. The header now reads **FAQ**, **Waitlist**, **Accounts**, your name, and a
**Sign out** button. Your name is the display name on your WitUS account, or your email when the account has
no name.

**Sign out.** Press **Sign out** in the header or the footer. It is a button, not a link, so a prefetch or a
stray image tag can never sign you out. The app ends its session, passes through the provider's sign-out, and
returns you to the home page with **Sign in** back in the header.

**What can go wrong.**

- The sign-in page says "Sign in with WitUS (chapter 07 of the tutorial) is not switched on in this copy of
  the app". This copy has no `WITUS_OIDC_CLIENT_SECRET`: it is a laptop copy, or a deployment that started
  before the secret was set. Every public page still works. On Vercel, set the secret and **Redeploy**.
- A page headed **Sign in did not complete** with one word in parentheses. `state`: the session cookie did not
  survive the round trip (the callback was opened in another browser, the session expired, or a laptop copy is
  running with debug off over plain HTTP). `refused`: the provider refused the token exchange, usually because
  the app's secret and the provider's differ or the provider has not restarted since its secret was set.
  `provider`: the provider was unreachable. `code`: the provider sent no code. Press **Try again**; the owner's
  log has the detail.
- The provider's page says the redirect URI is invalid. You are on a host that is not the registered origin
  (a preview deployment, for example). Only https://invest.witus.online can finish a sign-in.
- You are signed in, but the header shows a name like `witus-` followed by a long id, and **Open the admin** is
  missing. The provider's email did not match the superuser's email, or the provider did not mark it verified,
  so the app made a new ordinary user instead of linking you to the superuser. In the admin (password login),
  open **Sign in with WitUS**, **WitUS identities**, the row, and set **User** to the superuser; the next sign-in
  lands on the owner's account.
- `/accounts/` sends you to the sign-in with `?next=/accounts/` in the address. You are signed out; sign in and
  it returns you there.

## The waitlist

**What it is for.** The app is not open to other users yet. A visitor leaves a name and an email and hears when
it opens to learners. The owner reads the list in the admin and marks people approved; approval changes a
status and nothing else in this phase.

**What a visitor does.**

1. On the home page, press **Join the waitlist** in the first section (or **Waitlist** in the header; both jump
   to the **Waitlist** section near the bottom). The form also lives on its own page at `/waitlist/`, headed
   **Join the waitlist**.
2. Fill **Name** and **Email**. Under the fields is the line "Invest.WitUS is a learning tool, not advice, and
   not open to other users yet. Access later is for education, alongside the course."
3. Press **Join the waitlist**.

**What you should see.** A page headed **Thank you**: "You are on the list. You will hear from us when the app
opens to learners, and not before." with a link to the FAQ. The same address entered twice, in any capitals or
spacing, keeps one row and shows the same thank-you; the page never reveals who has signed up.

**What the owner does.**

1. Open `/admin/` and sign in with the superuser's username and password (the form reads **Username:**,
   **Password:**, **Log in**).
2. Under **Pages**, open **Waitlist entries**. The list shows **Email**, **Name**, **Status** and **Created at**,
   oldest first, with a search box and a **By status** filter on the right. New rows read **Waiting**.
3. Tick the entries to approve, choose **Approve the selected entries** in the **Action:** menu, and press
   **Go**.

**What you should see.** A message at the top, "1 waitlist entry approved." or "N waitlist entries approved.",
and the status reads **Approved**. No email goes out; the contact page names email to the operator as the one
route in this phase, and the mirror of signups to WitUS Inbox is chapter 13.

**What can go wrong.**

- The form comes back with an error under a field: the name was empty or the email was not an address. Fix it
  and submit again.
- A submission from a bot (the hidden "Leave this field empty" field was filled) is dropped silently and still
  shows the thank-you. Nothing to do.
- A 500 on submit right after a deploy, or on a laptop a debug page saying `no such table: pages_waitlistentry`:
  the migrations have not run. On a laptop, `uv run --env-file .env python manage.py migrate`; on Vercel,
  `vercel env run -e production -- uv run python manage.py migrate --database direct`.

## Accounts

**What it is for.** One account row per brokerage account you hold. The row carries the name, the broker and
the kind; it holds no balances, because those come from statements.

**Add one.**

1. In the admin, under **Holdings**, open **Accounts** and press **Add account** (or the **Add** link beside
   **Accounts** on the admin's front page).
2. Fill the form:
   - **Owner**: yourself (the superuser).
   - **Witus user id**: leave it empty. The field's help says so; Sign in with WitUS fills it the next time you
     sign in.
   - **Name**: a name of your own, for example `Practice`. One name per owner; a duplicate is refused.
   - **Broker**: "The broker's name as it appears on the statement", for example `Example Brokerage`.
   - **Kind**: one of **Brokerage (taxable)**, **Retirement**, **Paper (practice)**.
   - **Currency**: **US dollar** is the only choice in this phase.
3. Press **Save** (or **Save and add another** for the next brokerage).

**What you should see.** The **Accounts** list with the columns **Name**, **Broker**, **Kind**, **Currency**,
**Owner** and **Statements**; the new row's Statements column reads **0 statements**. On the public site, signed
in, **Accounts** in the header lists the same account under **Your accounts** with its broker and kind, and its
page says **No statement yet.** with the link **Enter the first one in the admin.**

**What can go wrong.**

- The form refuses the name: you already have an account with that name. Names are unique per owner.
- The account does not appear under **Your accounts** on the public site: it belongs to another user (the
  **Owner** field), or you are signed in with a WitUS identity that is not attached to the superuser (see
  [Sign in and sign out](#sign-in-and-sign-out)).

## Statements

**What it is for.** A statement is one dated snapshot of an account: the symbols it held on the statement's
as-of date, the shares, and the cost basis when the statement prints it. Every statement is a new row;
nothing is overwritten, so the app can show the change between any two dates.

**Enter one.**

1. In the admin, under **Holdings**, open **Snapshots** and press **Add snapshot**.
2. Fill the top of the form:
   - **Account**: pick the account.
   - **As of**: "The statement's as-of date, not the day you typed it in."
   - **Source**: where it came from, for example `September statement`. Optional.
3. In the **Snapshot lines** grid, one line per symbol (three empty rows to start; **Add another Snapshot
   line** adds more):
   - **Symbol**: in any case; it is saved in capitals.
   - **Shares**: up to six decimal places.
   - **Cost basis**: "Total cost as the statement prints it; empty if not shown." Leave it empty rather than
     typing a guess; empty and zero mean different things on the comparison page.
   - **Market value**: "Value as the statement prints it, if any." Data entry only; the app computes nothing
     from it.
   - **Notes**: free text.
   - A cash line is a symbol too: for example `CASH` with the amount as **Shares**.
4. Press **Save**.
5. Under **Holdings**, open **Holdings**. A row appeared for each new symbol with a blank **Kind**, because the
   app never guesses what a symbol is. Set each **Kind** in the list (**Stock**, **ETF**, **Mutual fund**,
   **Cash**), add a **Name** if you want one, and press **Save** at the bottom of the list. **Cash** matters: a
   cash line is valued at face and is never sent to the price source.

**What you should see.** In the **Snapshots** list: **As of**, **Account**, **Source** and **Lines**. In the
**Accounts** list, the Statements column now reads **1 statement**. Shares keep six places and money keeps
cents; a float never reaches a money field.

**Enter a second one.** Repeat with a later **As of** date for the same account. One statement per account per
date; a second statement on the same date is refused.

**The Statements page: the change between two statements.**

1. In **Accounts**, press the account's Statements link (**2 statements**).
2. The page is headed **Statements for** the account. **Statements, newest first** lists each statement's date,
   its source and its line count; each date opens that snapshot's form.
3. Under **Change between two statements**, the two newest are chosen. Pick any pair with **From** and **To**
   and press **Compare**. Picked backwards, the page sorts them: the earlier date is always From.

**What you should see.** A line "From <date> to <date>. Shares and cost basis only; the app fetches no prices
yet (chapter 08)." (The sentence is older than the prices chapter; the page is right that it shows no prices.)
Then a table with one row per symbol on either statement, in symbol order: **Symbol**, **Shares before**,
**Shares after**, **Shares change**, **Cost basis before**, **Cost basis after**, **Cost basis change**.
Changes carry a sign (`+1.500000`, `-400.00`). A symbol missing from one statement counts as zero shares and
zero cost on that side. A cost basis the statement did not print reads **not shown**, and so does its change:
no number beats a wrong one.

**What can go wrong.**

- "Snapshot with this Account and As of already exists" (or words to that effect): one statement per account
  per date. Open the existing one instead.
- The same symbol twice in one grid is refused: one line per symbol per statement.
- A line's kind stays blank in **Holdings** until you set it. A blank kind is treated as not cash, so a cash
  line with a blank kind is sent to the price source, refused there, and reads **no price yet** on the account
  page. Set it to **Cash**.
- You typed shares with more than six places or money with more than two: the app rounds on save (shares
  down to the share step, money to the cent).

## Account values

**What it is for.** The one place a value is shown, and only to the signed-in owner. Each account's page values
its latest statement at the latest close the app has stored for each symbol, with that close's date and
source beside every line.

**Open it.**

1. Signed in with WitUS on the production site (or signed in at `/admin/` on a laptop copy), press
   **Accounts** in the header, or open `/accounts/`.
2. **Your accounts** lists each account with its broker and kind. Under the list: "Each page values the
   account's latest statement at the latest close the app has stored, with the close's date beside it.
   Information, not advice."
3. Press an account.

**What you should see.** The page is headed with the account's name and broker under the eyebrow **Your
account**. One line says **Statement as of** the latest statement's date and source, and that "a close older
than five days is marked stale". Then a table: **Symbol**, **Shares**, **Close**, **As of**, **Source**,
**Value**, and a footer **Total of the priced lines**.

- A priced line shows the close, the close's date under **As of**, and the source: `tiingo` on production,
  `csv` on a laptop.
- A cash line (kind **Cash**) shows a close of `1.00`, the statement's own date, and `statement` as the source.
- **stale** appears beside a date more than five calendar days before today. Five covers a weekend and a
  holiday; longer than that means the pull has not run or the source has not answered for that symbol.
- A line with no stored close reads **no price yet** across the row, and a note under the table names those
  symbols: "the nightly pull has not stored a close for them. A symbol the price source does not know stays
  unpriced; the pull's log names it."
- The total adds the priced lines only.

**All accounts** returns to the list. No public page shows a price or links to these pages.

**What can go wrong.**

- Every line reads **no price yet** on production: the pull has not run yet since the migration, or the
  running deployment started without `TIINGO_API_KEY` (see [The nightly price pull](#the-nightly-price-pull)).
- One line reads **no price yet** while the others are priced: the price source does not know that symbol.
  On production, the run's JSON lists it under `failed` with "Tiingo answered 404"; fix the spelling in
  **Holdings** if the statement spells the ticker differently, or accept the line as unpriced. On a laptop,
  there is no `<SYMBOL>.csv` for it.
- Every line is **stale**: the cron has not run for a week (check the Cron Jobs page), or on a laptop the CSV
  file ends weeks ago.
- The page is a 404: the account belongs to another user. The page does not say whether the id exists.
- **No statement yet.**: enter one in the admin; the page links to the form.

## The nightly price pull

**What it is for.** Once a day the app stores one closing price per symbol per day in its own table, so no
page ever asks a vendor and a value always carries its date. The pull asks for the last seven days every night,
so one missed night is filled in by the next, and running it twice changes nothing.

**What it does.** For every symbol an account holds except cash, plus every symbol on a watch list (chapter 09), one request to the source for the closes of the last seven days; one row per symbol per day, written
once. A vendor's corrected close replaces its row. A symbol the vendor refuses is recorded and the others
continue; a rate limit stops the run and lists the symbols not reached. A run makes at most 50 requests, with a
one-second pause between symbols, inside Tiingo's free plan (50 requests an hour, 1,000 a day, 500 unique
symbols a month, "Internal Use Only", which is why values are shown to the signed-in owner and no one else).

**When it runs.** Vercel's cron calls `GET /api/cron/pull-prices/` once a day at 06:00 UTC (`vercel.json`,
`0 6 * * *`), which is 01:00 or 02:00 in Indiana depending on the season, after Tiingo's mutual fund NAV time.
Vercel sends `Authorization: Bearer <CRON_SECRET>` with the request; the route answers 403 to anything else
and 503, running nothing, while the secret is unset. Vercel's Hobby cron may fire anywhere inside its hour,
does not retry, and can occasionally miss or repeat a run; the seven-day window and the write-once rule cover
both.

**Run it once by hand, from Vercel.**

1. In the Vercel dashboard, open the invest-witus project, then **Settings**, then **Cron Jobs**.
2. The row for `/api/cron/pull-prices/` shows its schedule. Press **Run**. (Vercel also puts a run button on a
   deployment's summary page.)
3. Press **View Logs**. One line reads `cron: pull-prices {...}` with the JSON below.

Or from a shell, with the secret in the shell for one command and never in a file:
`curl -s -H "Authorization: Bearer $CRON_SECRET" https://invest.witus.online/api/cron/pull-prices/`

**What you should see.** HTTP 200 and JSON with `source` (`tiingo`), `since` and `until` (the seven-day window),
`symbols` (the universe), `requests`, `inserted`, `updated`, `unchanged`, `failed` (a map of symbol to reason),
`skipped` (symbols not reached) and `schedule` (the cron expression when Vercel fired it, empty for a call by
hand). Run it again: `inserted` 0 and `unchanged` the same number. In the admin, under **Prices**, **Daily
closes** lists what was stored: **Symbol**, **Date**, **Close**, **Source**, **Fetched at**, with a search box
and a **By source** filter. Deleting a row there makes the next run fetch that day again. The next morning,
**Cron Jobs** shows the scheduled run after 06:00 UTC.

**On a laptop.** With no `TIINGO_API_KEY`, the pull reads `<SYMBOL>.csv` files in chapter 02's format (`date,close`)
from `data/private/prices/`:

```sh
mkdir -p data/private/prices && cp data/sample/illustrative-daily-prices.csv data/private/prices/INDEX.csv
uv run --env-file .env python manage.py pull_prices --symbols INDEX --since 2026-09-22
```

The command prints `Source csv, <since> to <today>, 1 symbol(s), 1 request(s).` and `Inserted 7, updated 0,
unchanged 0.`; a second run prints `Inserted 0, updated 0, unchanged 7.`. Without `--symbols` it pulls every
held symbol; without `--since` the last seven days. The sample file ends on 2026-09-30, so its closes read
**stale** on the account page; add rows for recent weekdays to the file to see a fresh one.

**What can go wrong.**

- 503 with `{"error": "CRON_SECRET is not set"}`: the running deployment started before the secret existed.
  **Deployments**, the deployment's menu, **Redeploy**.
- 403: the header is wrong. From the dashboard's run button, the variable's value has a space or a quote
  around it.
- `"source": "csv"` on production: the deployment started without `TIINGO_API_KEY`; there are no CSV files on
  Vercel, so every symbol is recorded as "no file". Redeploy after setting the key.
- A symbol under `failed` with "Tiingo answered 404": the statement's symbol is not the ticker Tiingo knows,
  or Tiingo does not carry that fund. Fix it in **Holdings** or accept **no price yet** for that line.
- `skipped` is not empty: the run hit the 50-request budget or Tiingo answered 429. The next night's run picks
  them up.
- `symbols` is empty: no account holds anything but cash yet, or no statement has been entered.
- A future `--since` date is refused by the command.

## The watch list (when chapter 09 lands)

**On a branch, not merged.** Chapter 09 is built on `feat/tutorial-ch09` (commit `7139326`) while this guide is
written; it is not on `main` or on production yet. The labels below are read from that branch's template,
`watchlist/templates/watchlist/_section.html`, and its views. Re-read them once the chapter merges, in case a
word changed, and treat this section as current from that merge on.

**What it is for.** Symbols you want to follow in an account without holding them. Each watched symbol shows
the latest close the app has stored, with its date and source, the same way a held line does. There is no buy
button: a symbol reaches a plan only when you add it to the plan's universe.

**Add symbols.**

1. Open the account's page (**Accounts** in the header, then the account). Below the holdings table is the
   section **Watch list**; before anything is added it reads "Nothing on the watch list yet."
2. In **Symbols**, type one or more symbols, separated by commas or spaces. The help under the box gives the
   rule: "Letters, digits, a dot and a hyphen; up to twelve characters each." **Note (optional)** is a short
   reason, kept on the rows added now.
3. Press **Add to the watch list**.

**What you should see.** The page reloads with a notice at the top of the page: "Added to the watch list:
FUNDX." A symbol already on the list is reported as "Already on the watch list: FUNDX." and a token outside the
rule as "Refused: <token> (<reason>)." while the valid ones are still added. The table has **Symbol**, **Note**,
**Close**, **As of**, **Source** and a **Remove** button in each row. A new symbol reads **no price yet** until
the nightly pull has run, and the note under the table says so: "Prices arrive after the nightly pull: no close
is stored yet for FUNDX. A symbol the price source does not know stays unpriced; the pull's log names it." The
pull fetches every watched symbol the way it fetches every held one. Under the form: "Watching a symbol places
no order and recommends nothing. A symbol reaches a plan only when you add it to the plan's universe.
Information, not advice."

**Remove one.** Press **Remove** in the symbol's row. The notice reads "Removed FUNDX from the watch list." The
stored closes are not touched: the symbol can be watched again, or held, tomorrow.

The admin lists the same rows under **Watch list items** (**Symbol**, **Account**, **Note**, **Added at**); the
account page is where they are kept.

**What can go wrong.**

- "Enter at least one symbol." beside the box: the box was empty.
- "No symbol to add: <token> (<reason>)." beside the box: nothing typed passed the rule (empty, more than
  twelve characters, or a character other than letters, digits, a dot and a hyphen). Nothing was added.
- **no price yet** after the pull has run: the source does not know the symbol; the run's `failed` list names
  it. Fix the spelling, or remove it.
- **stale** beside a watched symbol's date: the same meaning as on the holdings table, a close more than five
  days old.
- The PRD (section 7.5) also describes "the change since you added it"; the chapter shows no such column. The
  guide follows the code.

## The FAQ and Report a bad actor

**What it is for.** The FAQ answers the questions a careful person asks about any investing app, this one
included, names the bodies that would govern a professional version of it, and lists the laws behind the
answers with links to the primary text. It opens with the section that matters most: where to report someone
who took your money.

**Open it.** Press **FAQ** in the header or the footer, or open `/faq/`. The page is headed **Invest.WitUS FAQ:
what to ask about any investing app**, with these sections:

- **Report a bad actor** (first, in a highlighted block).
- **A. Questions to ask about any investing app, and our answers**: among them "Is this app a registered
  investment adviser or broker?", "Who holds my money?", "Can I lose money, and can I lose more than I put
  in?", "Is paper trading realistic?", "What does 'information, not advice' mean in practice?", "Who do I
  complain to?" and "Who should not use this app?".
- **B. Who would govern this if it were a professional tool**.
- **C. Laws and rules that would govern the app**.
- **References**.

**Report a bad actor.** Three ways to reach it: the **Report a bad actor** callout on the home page and its
button **Where to report**; the **Report a bad actor** link under **Partners & Legal** in every footer; the
address `/faq/#report-a-bad-actor`. The block opens: "If someone took your money, pressured you, or will not
give it back, report it now. Reporting is free, you do not need a lawyer, and these desks act on reports from
ordinary people." Then one desk per kind of problem, each with its form's address:

- A broker, adviser, or anyone selling an investment: the SEC's tips, complaints and referrals form.
- A brokerage firm or its people: FINRA's complaint form.
- Anyone selling or advising in Indiana: the Indiana Securities Division's portal.
- Another state: NASAA's regulator finder.
- A bank account, loan, card, or payment app: the CFPB.
- Futures, commodities, or crypto derivatives: the CFTC.
- A scam, a deceptive sales pitch, or an unfair business practice: the FTC's ReportFraud.
- Any fraud that happened online: the FBI's Internet Crime Complaint Center (IC3).

It closes with "Keep the names, dates, screenshots and statements. If you are not sure which desk, file with
the SEC or your state regulator; they forward what is not theirs."

The app takes no complaints about other companies. The contact page (`/contact/`, **Contact** in the footer)
says the same and names email to the operator as the one route for a question, a wrong number, leaving the
waitlist, or deleting your data.

**What can go wrong.** The links on the FAQ go to government sites that change their pages. If one is dead,
the desk's home page is the fallback; tell the operator so the FAQ can be corrected.

## Alpaca paper (chapter 11)

Written for the app at `v11`. One account can be linked to your Alpaca paper account: in the admin, open the
account, set **Kind** to Paper (practice) and **Alpaca** to Alpaca paper. Give its plan a **Practice budget**, the
practice money the plan may spend (Alpaca's paper balance cannot be set, so the app keeps this number).

- **The method page** shows "This month's buys" above the view switch: the plan's amount for each symbol, the
  budget spent and left, and **Confirm** inside the buy window. One click places one market order per symbol for
  the dollar amount on Alpaca paper and writes it into the journal. A second click sends nothing. With the market
  closed the button reads "Confirm: queue for the open". If Confirm is missing, the box says why in one sentence.
- **The paper page** (`/accounts/<id>/paper/`, linked from the account page) shows Alpaca's cash, buying power,
  equity and positions beside the budget, every order the app placed with its status, and **Check orders now**,
  which copies fills into the journal. The nightly job does the same.
- Paper only: the band at the top says "Paper money. Live trading needs the checklist in a later chapter and
  separate keys."

## What the app will not do

- **Advise.** It recommends no security and never says which to buy. Every rule it checks (later chapters)
  links to the lesson that teaches it; the app judges your plan against the method, not the market.
- **Show market data on public pages.** No price, chart, return or testimonial appears on `/`, `/faq/`,
  `/privacy/`, `/terms/`, `/contact/` or the waitlist pages; a test fails if a table or a signed percentage
  appears on any of them. Values are shown to the signed-in owner only.
- **Show live quotes.** Prices are end-of-day closes, pulled once a night and stored with their date. A page
  never asks a vendor.
- **Hold or move money.** Paper only: Alpaca paper orders on your click (chapter 11). Live trading comes later,
  behind a checklist and separate keys.
- **Admit other users yet.** The waitlist is a list; approving an entry changes its status and sends nothing.
  Other learners come after the legal gate, with the course, for education only.
- **Send email.** Nothing in this phase emails anyone; the contact page is a mailto link. The mirror of signups
  and bug reports to WitUS Inbox is chapter 13.
- **Import a CSV statement.** Statements are typed into the admin; the column-mapped import is a later phase.
- **Keep your money data in git.** Real statements live in the database; the tutorial's samples use
  placeholder symbols; `data/private/` is ignored by git.

Still to come, each its own chapter: the watch list (09, built on its branch, not merged), the method engine and the three views (10), Alpaca
paper trading and the monthly review (11), the journal (12), the in-app bug reporter (13), 12-1 momentum (14),
signed events to CentenarianOS (15).

## When something goes wrong: a short table

| What you see | What it means | What to do |
|---|---|---|
| 500 on every page right after a deploy, or `/healthz/` answers 503 | The database is unreachable or the migrations have not run | Check **Storage** on the Vercel project; run the migration against Neon's direct connection; **Redeploy** |
| 500 on one form, laptop debug page says `no such table` | A migration is missing on this copy | `uv run --env-file .env python manage.py migrate` |
| **Sign in** opens a stub page | No `WITUS_OIDC_CLIENT_SECRET` in this copy | Expected on a laptop; on Vercel set it and redeploy |
| **Sign in did not complete** (`state`) | The session cookie did not survive | Try again in the same browser; on a laptop run with `--env-file .env` |
| **Sign in did not complete** (`refused`) | The provider refused the token exchange | The two secrets differ, or the provider has not restarted since its secret was set |
| Header shows `witus-<id>` instead of your name | Your WitUS identity made a new user | Re-point the identity's **User** in the admin |
| **no price yet** on every line | The pull has not run, or ran without the Tiingo key | Run the cron once; check `source` in its JSON |
| **no price yet** on one line | The source does not know that symbol | Fix the spelling in **Holdings**, or accept it |
| **stale** beside a date | The close is more than five days old | Check the Cron Jobs page for the last run |
| Cron answers 503 | `CRON_SECRET` not in the running deployment | Redeploy |
| Cron answers 403 | Wrong bearer | Check the variable's value for stray spaces or quotes |
| `CSRF verification failed` on a form | The origin is not trusted | `DJANGO_CSRF_TRUSTED_ORIGINS` must name `https://invest.witus.online` |
| `DisallowedHost` | The host is not allowed | `DJANGO_ALLOWED_HOSTS`, or Vercel's system variables are off |
