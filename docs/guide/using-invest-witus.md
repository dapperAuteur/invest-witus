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
page says **No statement yet.** with the link **Enter the first one in the admin.** The account linked to Alpaca
paper (see [Alpaca paper](#alpaca-paper-chapter-11)) also shows **Paper account** on its row, and **Paper
account** appears in the header beside **Accounts** on every page while you are signed in as the site owner.
Every row also links that account's **Logbook**, and the header shows **Logbook** for the first account with a
plan or a journal entry (decision 115). On a phone or a narrow window, signed in, the header's links fold behind a
**Menu** button; press it to open them, Escape to close. **Sign out** stays visible beside it.

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

**What you should see.** A line "From <date> to <date>. Shares and cost basis only, as the statements print
them; this comparison does not use stored prices, which are on the account page and each watched symbol's history
page." (Until 2026-10-29 it said the app "fetches no prices yet (chapter 08)", which was older than the prices
chapter.)
Then a table with one row per symbol on either statement, in symbol order: **Symbol**, **Shares before**,
**Shares after**, **Shares change**, **Cost basis before**, **Cost basis after**, **Cost basis change**.
Changes carry a sign (`+1.500000`, `-400.00`). A symbol missing from one statement counts as zero shares and
zero cost on that side. A cost basis the statement did not print reads **not shown**, and so does its change:
no number beats a wrong one.

**A split between the two statements (2026-10-29).** When the price pull has stored a split for a symbol after
the From date and on or before the To date, a note row sits under that symbol: `FUNDX: A 4-for-1 split on
2026-07-15 explains a share change of this size: 10 shares before it are 40 after it.` It ends with `That is the
whole change.` when the statement's shares match, or `The statement shows 41; the other 1 came from buying,
selling or reinvesting.` when they do not. A reverse split reads `1-for-10 reverse`. The statements themselves
are not changed. The note needs the split stored: rows fetched before 2026-10-29 have no split factor until
**Get history** is pressed for the symbol (see [Adjusted closes, splits and dividends](#adjusted-closes-splits-and-dividends-2026-10-29)).
A split on the From date itself is already in that statement's shares, so it gets no note.

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
- A cash line (kind **Cash**) shows a close of `$1.00`, the statement's own date, and `statement` as the source.
- **stale** appears beside a date more than five calendar days before today. Five covers a weekend and a
  holiday; longer than that means the pull has not run or the source has not answered for that symbol.
- A line with no stored close reads **no price yet** across the row, and a note under the table names those
  symbols: "the nightly pull has not stored a close for them. A symbol the price source does not know stays
  unpriced; the pull's log names it."
- The total adds the priced lines only.

**All accounts** returns to the list. No public page shows a price or links to these pages.

**How numbers read (2026-10-29).** Every amount of money on the signed-in pages (closes, values, totals, plan
amounts, budgets, spent, cash, buying power, equity, prices and order amounts) is US dollars to the cent with a
`$` and thousands commas: `$1,234.56`, a negative `-$1,234.56`. A close stored with more places than cents, such
as `20.005`, shows rounded half up (`$20.01`); the value beside it is still worked out from the stored close.
Share counts (shares, quantities, shares filled) show commas and up to six places with the trailing zeros
dropped: `1,234.5`, `0.123456`, `10`.

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

**A year on the first night (2026-10-29).** The first time the pull meets a symbol, held or watched, it asks for
the last 365 days instead of seven, in the same single request, and notes the symbol under **Prices**, **Price
backfills**. Symbols the pull already knew before this change get their year on the next run. A run still
makes at most 50 requests; a symbol that did not fit, or that the source refused, asks for its year again the
next night. Delete a **Price backfills** row to ask for that symbol's year again.

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
`skipped` (symbols not reached), `backfilled` (symbols whose year was fetched this run) and `schedule` (the
cron expression when Vercel fired it, empty for a call by hand). Run it again: `inserted` 0 and `unchanged` the same number. In the admin, under **Prices**, **Daily
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
3. **Fetch their history now** is ticked, with **History range** at **1 year** (since 2026-10-29). Leave it to
   fetch the new symbols' closes in the same press, or pick another range; untick it to let prices arrive with
   the nightly pull or **Fetch prices now**, as before.
4. Press **Add to the watch list**.

**What you should see.** The page reloads with a notice at the top of the page: "Added to the watch list:
FUNDX." A symbol already on the list is reported as "Already on the watch list: FUNDX." and a token outside the
rule as "Refused: <token> (<reason>)." while the valid ones are still added. With **Fetch their history now**
ticked, the symbols just added (not the ones already watched) are fetched like **Fetch history for selected**
(below, under Get history): one line per symbol, `OTHER, 1 year: 251 days added, 0 updated; earliest close
stored 2025-10-29.`, a symbol fetched in the last 10 minutes skipped and named, at most 50 requests and four
minutes. The table has **Symbol**, **Note**,
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

## A watched symbol's price history

**What it is for.** The closes the app has stored for one watched symbol, as a chart and as a table, over the
last 30, 90 or 365 days, 5 or 10 years, everything stored, or dates you pick. Like every price, it is shown to
the signed-in owner only.

**Open it.** On the account page, in the **Watch list** table, press a symbol. The address is
`/accounts/<id>/watch/<SYMBOL>/`.

**What you should see.** The symbol as the heading, the note under it, then **As of** the newest stored close with
its price and source; **stale** beside it when that close is more than five days old, as on the account page.
Then the range: **30 days · 90 days · 365 days · 5 years · 10 years · All** (90 is where it opens; the current
one is in bold), and under it **Or pick dates** with **From** and **To** and a **Show these dates** button (see
**Pick a range** below). Then a link **Compare FUNDX with other symbols**, which keeps the range, and the chart:

- **The title**, `FUNDX, last 90 days`, and under it what the line is (`Adjusted close, US dollars.` or
  `Close, US dollars.`), `Daily closes from Tiingo` (or `CSV files` on a laptop), and **as of** the last day
  in the chart.
- **The key**: a short sample of the line with `FUNDX (adjusted close, solid line)`, and, when the range has
  any, **S** Split and **D** Dividend (ex-date).
- **The axes**: dollars up the left side at round steps (`$1,180`, `$1,200`, ...), titled
  `Adjusted close, US dollars`; dates along the bottom, titled **Date**: Mondays over 30 days (`Oct 5`), month
  starts over 90 or 365 days (`Nov 2025`, `Jan 2026`, `Mar`; on a phone every other label is hidden). The days
  are spaced by the calendar, so a weekend is a small gap.
- **The line**, oldest on the left, a dot on the newest close, and an **S** or a **D** on the line on each split
  or dividend day.
- **Splits and dividends**, a table under the chart when the range has any: **Date**, **Symbol**, **Event**
  (`Split 4-for-1`, `Dividend $0.57`).

Under it, the same days as a table, newest first: **Date**, **Close**, **Adjusted close**, **Change** and
**Change %** (from the stored day before, on the line's basis), **Split or dividend**, **Source**. A range of more
than 100 stored days shows 100 rows a page, with `Rows 1 to 100 of 1,255, page 1 of 13.` and **Newest**,
**Newer**, **Older** and **Oldest** links under the table. On a phone the table scrolls sideways inside its own
box; the page does not. A screen reader reads the chart's title (the
symbol, the range, how many closes, the low and the high) and then the tables.

**Hover detail.** Move the pointer over the chart: a dashed line and a dot follow the nearest day, and the box
under the chart shows that day: the date, the **close**, the **adjusted close**, the **change** from the stored
day before in dollars and percent (`-$1.62 (-0.27%)`), and the split or dividend on that day if any. With the
keyboard, press **Tab** until the chart is outlined, then **Left** and **Right** move a day, **Home** and **End**
go to the first and last day; a screen reader announces each day. That is all the app stores per day: no
intraday prices and no volume. With JavaScript off there is no box, and the table under the chart has the same
values.

**Pick a range (2026-10-29).**

1. Press **5 years**, **10 years** or **All** for a longer view (the address gets `?days=5y`, `?days=10y` or
   `?days=all`). **All** is every close stored for the symbol; press **Get history** with **All available** first
   if you want the vendor's whole history.
2. Or, under **Or pick dates**, set **From** and **To** and press **Show these dates** (the address gets
   `?from=2020-01-02&to=2024-12-31`). The calendar only offers days between the oldest and newest stored close;
   the line under the boxes names them. Both dates set the chart and the table. To go back to a preset, press it.

The title says the range (`FUNDX, last 5 years`, `FUNDX, all stored days`, `FUNDX, 2020-01-02 to 2024-12-31`).
**Long ranges stay fast.** Over 1,000 stored days the chart draws 1,000 of them: an even spread plus the first
and last day, the lowest and highest, and every split or dividend. A line under the chart says so (`This range
has 6,953 stored days. So the chart stays fast, it draws 1,000 of them ...`), and pointing at the chart reads the
drawn days. The table under it still lists every day, 100 a page.

**What can go wrong.**

- `Pick both a From date and a To date, or one of the ranges above.`, `From (2024-12-31) must be before To
  (2020-01-02).`, `From is not a date in the form YYYY-MM-DD` or `Pick dates within the stored closes, 1999-03-10
  to 2026-10-28; ... is not.`: the dates were refused. The page shows the reason at the top, `Showing the last 90
  days instead.`, and keeps what you typed in the boxes so you can fix it.
- "No close stored yet.": the symbol was added since the last nightly run. The next run fetches its year, or
  press **Get history** on the same page.
- "No closes stored in the last 30 days." (or "from <date> to <date>"): the newest close is older than the range; the **As of** line says
  when it is from. Pick a longer range, or check the pull's `failed` list for the symbol.
- `Adjusted closes are missing for N of M days in this range, so the chart uses the unadjusted close`: the
  days were stored before 2026-10-29. Press **Get history** with **All available** once; see the next section.
  Until then a split shows as a sudden drop on the line, and the key says `(close, solid line)`.
- Only a week of closes on a symbol watched before 2026-10-29: the year arrives with the next nightly run; until
  then the chart shows what is stored.
- A 404: the symbol is not on this account's watch list, or the account is not yours.

## Adjusted closes, splits and dividends (2026-10-29)

**What they are for.** A stored close is the price as it traded that day. When a fund splits 4-for-1, its close
drops to a quarter overnight although nobody lost money, so over a long range the line shows a fake crash. The
price source also sends an **adjusted close**: every earlier close restated for the splits and dividends since,
so the line runs smooth and its change is the holder's actual return. Tiingo's end-of-day documentation (read
2026-10-29) says the adjustment "follows the standard method set forth by" the Center for Research in Security
Prices and "incorporates both split and dividend adjustments". The app now stores, per day, the close, the
adjusted close, the **split factor** (`4` on the day of a 4-for-1 split, `1` on other days; Tiingo uses the same
field for some distributions) and the **cash dividend** whose ex-date is that day (`0` on other days).

**Which one a chart uses.** The adjusted close when every day in the range has one; otherwise the close, for the
whole line, so a line never mixes the two. The key, the y-axis title and the compare table say which.

**Fill the days stored before 2026-10-29, once.**

1. Open an account's page. In the **Watch list** section, under the table, pick **All available** under
   **History range**.
2. Press **Fetch history for all**.
3. Repeat on the next account if it watches other symbols. A held symbol that is not on any watch list: add it
   to the watch list first.

**What you should see.** One line per symbol: `FUNDX, all available: 0 days added, 6,953 updated; earliest
close stored 1999-03-10.` **Updated** is the days that gained an adjusted close, a split factor and a dividend.
The history page's key then says **adjusted close**, and splits and dividends appear on the chart.

**After that, nothing to do.** Every nightly pull, Fetch prices now and Get history stores the three values. When
a new split or dividend arrives in the nightly week, the vendor's earlier adjusted closes all move by one factor;
the app moves the stored ones it did not refetch by the same factor, so the line stays continuous.

## Compare symbols (2026-10-29)

**What it is for.** Up to six of an account's symbols on one chart, to see which moved more over the same days.
Each line is rebased to **100** on its first stored day in the range, so a $500 fund and a $20 stock compare
fairly: a line at 110 is ten percent above where it started, whatever its price.

**Open it.** On the account page, under the Watch list table, press **Compare these symbols on one chart** (the
first six watched symbols are ticked), or on a symbol's history page press **Compare FUNDX with other symbols**.
The address is `/accounts/<id>/compare/?symbols=FUNDX,INDEX&days=365`.

**Use it.**

1. Under **Symbols, up to 6**, tick the symbols: the account's watch list and its holdings (not cash).
2. Pick a **Range**: 30, 90 or 365 days (365 is where it opens), 5 years, 10 years or All; or set **From** and
   **To** under **Or pick dates**, which win over the Range (since 2026-10-29). The calendar offers the days
   between the oldest and newest stored close of the symbols ticked.
3. Press **Compare**.

**What you should see.** The title (`FUNDX, INDEX: last 365 days`), a line saying each line is its symbol's
adjusted closes rebased so its first day is 100, the source and the as-of date; the key, one entry per symbol
with a different color **and** a different dash pattern (solid, dashed, dotted, dash-dot, short dashes,
dash-dot-dot), so the lines can be told apart without color; the y axis titled `Value, with each line's first day
in the range at 100`; split and dividend letters as on the history page. Under the chart, a table per symbol:
**Uses** (adjusted close or close), **First day**, **Start**, **Last day**, **End** in dollars, and **Change** in
percent. **Every day's values** opens a table of each day's rebased value and close per symbol, 100 days a page
when the range is longer, with the same **Newest** to **Oldest** links. Each line is rebased on its first stored
day inside the range you chose, so a custom range starts every line at 100 on (or just after) your **From**
date. Over 1,000 stored days the chart is thinned as on the history page, and says so.

**Hover detail.** As on the history page; the box lists every symbol that day: its rebased value
(`113.63 (start = 100)`), close, adjusted close, change from the day before, and any split or dividend. A symbol
with no close that day says so.

**What can go wrong.**

- `Not on this account's watch list or holdings, so left out: NOPE.` Only this account's symbols can be compared.
- `Up to 6 symbols at once; left out: ...` The first six in the order asked are charted.
- `No closes stored in the last 365 days for ...` Press **Get history** for it, or wait for the nightly pull.
- A refused **From** and **To** pair: the same messages as on the history page, with the default range shown.
- `The lines start on different days`: one symbol's stored history begins inside the range; each line is rebased
  on its own first day, listed in the table.
- A 404: the account is not yours.

## Fetch prices now and Get history (2026-10-29)

**What they are for.** Two buttons for the signed-in owner, so you do not wait for the nightly pull or open a
terminal for `pull_prices --since <date> --symbols <list>`. **Fetch prices now** runs the nightly pull at once
for your symbols. **Get history** fetches years of closes for one watched symbol. Like every price, what they
store is shown to you only; no public page has either button.

**Fetch prices now.**

1. Open **Accounts** in the header, or an account's page. On **Your accounts** the button sits under the list; on
   an account page it sits in the **Watch list** section, above the add form.
2. Press **Fetch prices now**.

It asks the price source for the last seven days of every symbol your accounts hold (cash excepted) or watch,
and a year for a symbol it has never fetched, one request per symbol: at most 50 requests, a one-second pause
between symbols, and no more than four minutes, so the page always answers. It is the same pull the cron runs,
limited to your symbols.

**What you should see.** The same page again, with the notices at the top:

- `Fetched closes from tiingo for 3 symbols in 3 requests: 12 inserted, 0 updated, 4 unchanged, 1 refused,
  2 backfilled, 0 skipped for budget.` **Inserted** is new days; **updated** a day whose close changed (a
  vendor's correction); **unchanged** a day already stored; **refused** a symbol the source turned down;
  **backfilled** a symbol fetched for its first year; **skipped for budget** a symbol the run did not reach.
  Press it again after ten minutes: **inserted** 0 and the same days **unchanged**.
- `Refused FUNDX: Tiingo answered 404: ...`, one line per refused symbol, with the vendor's reason.
- `A year of closes, first time: FUNDX, INDEX.` when a symbol got its first year.
- `Stopped by the 50-request limit for one run; not reached: ... The rest continue tonight.` The run stopped
  early; the nightly pull reaches them. The reason may also read **Tiingo's hourly or daily limit** (the vendor
  answered 429) or **the time one press may take**.
- `Nothing to fetch: no account of yours holds or watches a symbol.` Add a statement or a watched symbol first.

**Get history.**

1. On an account page, in the **Watch list** table, find the symbol's **History** cell. (Or open the symbol's
   history page; the **Get history** section is under the table.)
2. Pick a range: **1 year**, **5 years**, **10 years** or **All available**.
3. Press **Get history**.

One request to the price source for that symbol and range. Days already stored are left alone, so pressing it
twice adds nothing twice. Tiingo's free plan lists "30+ Years" of end-of-day history; its documentation does
not say how far back a single request may reach, so the message tells you what came back.

**What you should see.** `FUNDX, 10 years asked (from 2016-10-29): 2,512 days added, 0 updated, 3 unchanged.
Earliest close returned: 2016-10-31; earliest close now stored: 2016-10-31.` **Earliest close returned** is
the oldest day the source sent: for **All available**, that is how deep the vendor's history for the symbol
goes. The history page's **5 years**, **10 years**, **All** and **From** and **To** show the older closes (since
2026-10-29); they are also in the admin under **Prices**, **Daily closes**. Since 2026-10-29 a re-fetch of days already stored counts them as **updated** when
it brings their adjusted close, split factor and dividend for the first time.

**Several symbols at once: Fetch history for selected and Fetch history for all.**

1. On an account page, in the **Watch list** table, tick the box at the start of each symbol's **History** cell,
   or type symbols in **Or type symbols** under the table, separated by commas or spaces (`FUNDX, OTHER` or
   `FUNDX OTHER`), or both (or tick none and use **for all**).
2. Under the table, pick the **History range**: 1 year, 5 years, 10 years or All available.
3. Press **Fetch history for selected** or **Fetch history for all** (every symbol on this account's watch list).

One request per symbol, in symbol order, at most 50 in one press, a one-second pause between them, and no more
than four minutes. You see one line per symbol: `FUNDX, 5 years: 1,255 days added, 3 updated; earliest close
stored 2021-10-29.` Then, if any: `Skipped, fetched less than 10 minutes ago; each can run again at the time
shown: OTHER (at 2026-10-29 14:05 UTC).` and, when the run stopped early, `Stopped by the 50-request limit for
one run. The rest: press again in 60 minutes: S50, S51.` (60 minutes after the request limit or Tiingo's 429,
because the free plan counts requests per hour; 1 minute after the time limit). A ticked or typed symbol that is
not on this account's list is named and left out (`Not on this watch list, so left out: INDEX.`), a typed token
outside the symbol rule is named as `Refused: <token> (<reason>).`, and pressing **for selected** with nothing on
this list ticked or typed says `Tick or type at least one symbol on this list, or press Fetch history for all.`

**What can go wrong.**

- `Prices were fetched less than 10 minutes ago. The next Fetch prices now can run at <time>.` or `FUNDX's
  history was fetched less than 10 minutes ago. Get history can run for it again at <time>.` Each button runs
  once every ten minutes (per owner for Fetch prices now, per symbol for Get history), so a held-down button
  cannot spend the free plan's 50 requests an hour. Wait, or delete the row under **Prices**, **Manual price
  runs** in the admin.
- `FUNDX: Tiingo answered 404: ... Nothing was stored.` The source does not know the symbol. Check the spelling.
- `FUNDX: Tiingo answered 429: the hourly or daily request limit is reached. Nothing was stored. Try again after
  the hour.` The free plan's 50 requests an hour or 1,000 a day are spent; the nightly pull counts too.
- `FUNDX, all available asked (from 1900-01-01): the source returned no closes.` The source has nothing for that
  range.
- `Source csv` in the message on production: the deployment started without `TIINGO_API_KEY`.

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
- **The paper page** (`/accounts/<id>/paper/`) is **Paper account** in the header, beside **Accounts**, on every
  page while you are signed in; it is also linked from that account's row under **Your accounts** and from the
  account page. The header link is there only for the site owner (a superuser) who has an account linked to
  Alpaca paper, the same rule the page itself uses; signed out, or without a linked account, there is no link.
  The page shows Alpaca's cash, buying power,
  equity and positions beside the budget, every order the app placed with its status, and **Check orders now**,
  which copies fills into the journal. The nightly job does the same.
- Paper only: the band at the top says "Paper money. Live trading needs the checklist in a later chapter and
  separate keys."

## The journal and the monthly close (chapter 12)

Written for the app at `v12`. Everything here is on the method page (`/accounts/<id>/method/`) and the logbook
(`/accounts/<id>/logbook/`), for the account's owner only.

- **Log a hold or a skip.** The log form under every view has a **Kind**: Trade (a buy or a sell), Hold or Skip.
  A trade needs **Action**, **Symbol** and **Amount**, as before. A hold or a skip needs only the day and **Why**;
  leave Action, Amount and Shares empty. Any entry can also carry **State** (Calm, Focused, Confident, Unsure,
  Stressed or Rushed) and **Tags**, up to five words of your own separated by spaces or commas.
- **A skip explains a month with no buy.** The review still lists "No buy in 2026-03" under "Buy once in every
  month of the plan", with "Explained by a skip:" and your reason beside it. The month reads **skipped** in view
  B's Months table, and the rule reads **explained** when every finding it has is explained. A skip does not
  excuse a late buy, a wrong amount or a sale.
- **Close last month.** When a month's buy window has closed, view A shows **Close last month** with a link,
  **Review 2026-03**. The review page shows the month's findings and entries and asks three questions: **What I
  did**, **What the rules said** (started for you from the findings) and **What I'll do next month**. Press
  **Close 2026-03**. A month with no buy and no skip cannot be closed: log a skip that says why first. View B
  lists every month's review, open or closed.
- **A closed month is read-only.** Its entries cannot be added, edited or deleted, from the page or the admin.
  To change one, open the month's review and press **Reopen** with a reason. The **History** at the bottom of the
  review page lists every close, with what you wrote, and every reopen, with why, with the time and your name.
- **Change or end the plan.** Under the view switch, **Change or end this plan**. Pick **Change the numbers**
  (amount, window, symbols) and **Starting** next month, or this month while its window is still open and
  nothing is logged in it; or pick **End the plan**. **Why** is required. A change is a new version: the months
  before it stay judged by the old numbers, and view A lists the versions with their dates and reasons. Ending
  the plan keeps its months and reviews and takes you to the Lesson Lab to start another.
- **Place again** (paper accounts). If this month's order ended with nothing filled (canceled or expired), the
  box says so and the button reads **Place again**, inside the window only. It sends one new order with a new id
  ending in `-r2`; a second click sends nothing.
- **The logbook.** **Open the logbook** under the view switch: every entry with its kind, state, tags, reason,
  note and source, filtered by **Month**, **Kind** and **Tag**. **Edit** appears on lines you wrote by hand in an
  open month; a line a paper order wrote is kept in step with Alpaca and is not edited. **Download these as CSV**
  saves the filtered list as `logbook-account-<id>.csv`, with the columns `date, kind, symbol, amount, shares,
  state, tags, reason, note, source, month_closed`. A reason or note that starts with `=`, `+`, `-` or `@` is
  saved with an apostrophe in front, so a spreadsheet shows it as text.

## Report a problem or ask a question (chapter 13)

Written for the app at `v13`. The link **Report a problem or ask a question** is in the header of every page (the
last link in the list; on a phone, signed in, it is behind **Menu**) and in the footer, in the **Partners & Legal**
column under **Report a bad actor**. It works signed in or out.

- **The form.** Pick what it is about: **Something is broken (a bug)**, **An idea for the app (a feature)** or
  **A question**. Write **Your message**; leave out passwords and keys. **What page were you on?** is filled in
  from the page you came from, without anything after a `?`; change or clear it. Signed out, **Your email** is
  required so a reply can reach you; signed in, the email and name from your WitUS sign-in are used and there is
  no email box. Press **Send**.
- **Afterward.** A thank-you page. It promises no reply time, and the operator reads every report.
- **Five an hour.** A sixth report within an hour, from the same address or the same signed-in person, brings
  the form back with "You have sent five reports in the last hour". The earlier ones are saved.
- **What happens to it.** The report is saved in the app first, then sent to WitUS Inbox, where the operator
  triages every WitUS app's mail. A bug also texts the operator. If Inbox is down, the report waits and is sent
  by the nightly job; nothing is lost.
- **On a copy without Inbox** (your laptop, a learner's copy), the form says "Forwarding to WitUS Inbox is off",
  and reports are kept for the owner in the admin.
- **The owner's side.** Admin, **Reports and WitUS Inbox**, **Reports**: every report with its kind, a triage
  status you set (New, Triaged, Done) and its Inbox status (Not tried yet, Sent, Failed, will retry, or Off, will
  retry) with the last error in words. Select rows and choose **Send again to WitUS Inbox** to send them now.
  **Waitlist copies to Inbox** lists each new waitlist signup's copy the same way. On the laptop,
  `uv run --env-file .env python manage.py reports` prints the reports not marked Done.

## A second method: 12-1 momentum (chapter 14)

Written for the app at `v14`. 12-1 momentum ranks a list of candidates you write down by how much each rose over
the past year without its latest month, and puts each month's amount into the top few, in equal parts. Everything
here is on the method page and the watch list of an account that runs it, for the account's owner only. The
symbols below (`ALPHA`, `BETA`, `GAMMA`, `DELTA`) are placeholders.

- **Start it.** On an account with no method, the method page opens on **C: The Lesson Lab**, which lists both
  methods with their rules. In the start form pick **12-1 momentum, monthly top N in equal parts**, type your
  candidates in **Symbols**, the month's money in **Amount each month**, and **Top N to hold**, a number smaller
  than the number of candidates. Leave **Top N to hold** empty for index investing. Press **Start this method**.
  The message names the candidates it added to the watch list, so the nightly pull stores their closes.
- **Fetch enough history.** A candidate is ranked only when it has a close in the month 13 months back and in the
  month 2 months back, a little over a year of history. The nightly pull's first fetch of a new symbol stores one
  year, so a new candidate shows under **Not ranked** with the months it needs; press **Get 5 years of history**
  under that list, once.
- **Read the ranking.** **The ranking for 2026-11** sits above the view in A, B and C. Each candidate is a bar on
  one scale: right of the line it rose over the window, left of it it fell; the number has its sign and the word up
  or down. Filled bars are in the top N and say so; outlined bars are not. The table under the bars has the same
  ranking with the two closes each return comes from. **How to read this** explains it in four sentences.
- **This month's rebalance.** Under the ranking: **Buy $50.00 of ALPHA** for each top-N candidate (the amount
  split to the cent), and **Sell all of GAMMA** for a holding that left the top N. The app does not place sells:
  on a paper account sell in Alpaca's paper dashboard, then log the sale. A buy of a symbol you sold in the last
  30 days shows a **Wash-sale warning**.
- **The review.** The seven rules are checked like method 1's: view B's **Rule checks** shows each one's status
  and evidence, and its **Months** table has a **Top N** column with the month's top N. A month with no trade at
  all is "No rebalance"; a skip with its reason explains it, as in chapter 12.
- **On a paper account,** **This month's buys** lists the top N with their parts and **Confirm** places one order
  each, once.
- **The watch list** of a momentum account has a **12-1 return** column: `▲ up +24.3%`, `▼ down -10.5%`, or "not
  ranked", with its own **How to read this**.
- **A symbol's history page** shades this month's 12-1 window, darker, and the excluded month, lighter with a
  dashed edge and labelled "excluded". **Show the whole window** sets the range to cover it.

## Draft a post for WitUS Outbox (2026-10-29)

For the site owner only. When you want to tell people something about Invest.WitUS (that it is live, or a
milestone you choose), write it here and it lands in WitUS Outbox as a draft, where you approve it. The app
never writes a post by itself and never posts anything: Outbox does, after you approve it there.

- **Where.** Admin, **Posts to WitUS Outbox**, **Post drafts for WitUS Outbox**, **Draft a post**. Staff accounts
  that are not the superuser do not see it.
- **The form.** **Occasion**: *Invest.WitUS is live (the launch, once)* or *A milestone you choose*. **Text**: at
  most 280 characters, one text for every platform. **Platforms**: LinkedIn, X (Twitter) and Bluesky, all ticked;
  untick any you do not want. Press **Save**.
- **What you should see.** "Outbox: 3 of 3 sent." and the draft's page with one row per platform: **In Outbox**,
  Outbox's id, and Outbox's own status for it (*draft*). Then open Outbox and find the drafts under this app's
  source: edit, schedule, approve or reject each one there. The saved text is read-only here; change it in Outbox.
- **What is refused.** Anything from your accounts: an amount (`$`, dollars), a percentage, a share count, a
  cashtag (`$` and a symbol), or any symbol you hold, watch, plan, journal or have a price for. The form names
  what it found; reword it. A second launch draft is refused too ("There is a launch draft already"); use a
  milestone.
- **When Outbox is switched off** (the usual state until the owner turns it on, and always on a laptop): the rows
  read **Off, will retry** with the reason, and nothing is sent. Once `OUTBOX_TRIGGER_ENABLED` is `true` on the
  site, the nightly job sends them, or select the draft and choose **Send again to WitUS Outbox**.
- **If Outbox did not answer**, the row reads **Failed, will retry** with the reason, and the nightly job or
  **Send again** tries it later. Sending again never makes a second draft in Outbox.

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
- **Post to social networks.** The owner's **Draft a post** sends a draft to WitUS Outbox, where the owner
  approves it; nothing from an account is ever in it, and no event in the app writes a post.
- **Send email.** Nothing in this phase emails anyone; the contact page is a mailto link. Since chapter 13, new
  waitlist signups and reports are copied to WitUS Inbox, the operator's inbox, which sends nothing to you.
- **Import a CSV statement.** Statements are typed into the admin; the column-mapped import is a later phase.
- **Keep your money data in git.** Real statements live in the database; the tutorial's samples use
  placeholder symbols; `data/private/` is ignored by git.

Still to come, each its own chapter: rank changes and the rolling 12-1 line (14a), signed events to CentenarianOS
(15).

## When something goes wrong: a short table

| What you see | What it means | What to do |
|---|---|---|
| 500 on every page right after a deploy, or `/healthz/` answers 503 | The database is unreachable or the migrations have not run | Check **Storage** on the Vercel project; run the migration against Neon's direct connection; **Redeploy** |
| 500 on one form, laptop debug page says `no such table` | A migration is missing on this copy | `uv run --env-file .env python manage.py migrate` |
| **Sign in** opens a stub page | No `WITUS_OIDC_CLIENT_SECRET` in this copy | Expected on a laptop; on Vercel set it and redeploy |
| **Sign in did not complete** (`state`) | The session cookie did not survive | Try again in the same browser; on a laptop run with `--env-file .env` |
| **Sign in did not complete** (`refused`) | The provider refused the token exchange | The two secrets differ, or the provider has not restarted since its secret was set |
| Header shows `witus-<id>` instead of your name | Your WitUS identity made a new user | Re-point the identity's **User** in the admin |
| **no price yet** on every line | The pull has not run, or ran without the Tiingo key | Press **Fetch prices now**; check the source it names |
| **no price yet** on one line | The source does not know that symbol | Fix the spelling in **Holdings**, or accept it |
| **stale** beside a date | The close is more than five days old | Check the Cron Jobs page for the last run |
| Cron answers 503 | `CRON_SECRET` not in the running deployment | Redeploy |
| A report reads **Off, will retry** in the admin | The three `INBOX_` names are not all set on this deployment | Set them and redeploy; the nightly job sends the waiting rows |
| A report reads **Failed, will retry** with a 401 | Inbox does not know this source or secret, or the clock is off | Check the slug in Inbox's `INGEST_SOURCES`, redeploy Inbox, compare the secrets; then **Send again** |
| A post draft reads **Off, will retry** | `OUTBOX_TRIGGER_ENABLED` is not exactly `true`, or an `OUTBOX_` name is missing | Expected until you turn it on; set them and redeploy, then **Send again** |
| A post draft reads **Failed, will retry** with a 401 | Outbox does not know this source or secret, or the clock is off | Check the slug in Outbox's `INGEST_SOURCES`, redeploy Outbox, compare the secrets; then **Send again** |
| A post draft reads **Blocked, not sent** | The text named something from your accounts, or it was not written by the superuser | Write a new draft without it |
| Cron answers 403 | Wrong bearer | Check the variable's value for stray spaces or quotes |
| `CSRF verification failed` on a form | The origin is not trusted | `DJANGO_CSRF_TRUSTED_ORIGINS` must name `https://invest.witus.online` |
| `DisallowedHost` | The host is not allowed | `DJANGO_ALLOWED_HOSTS`, or Vercel's system variables are off |
| "2026-03 is closed. Reopen its review, with a reason, to change it." | The entry's month is closed | Open the month's review and **Reopen** it with a reason |
| "2026-03 has no buy and no skip with a reason." when closing | The month was missed and nothing says why | Log a **Skip** for that month with **Why**, then close it |
| "... less than 10 minutes ago ... can run at <time>." | A price button ran in the last ten minutes | Wait until the time named, or delete its **Manual price runs** row in the admin |
