# Invest.WitUS recording scripts

Ten quick-reference clips, one per feature, for BAM to record by hand. The format follows the ecosystem's
tutorial plans (witus plans 31 and 33): numbered steps, each with a **[SCREEN]** line (what to show and where
the cursor goes, with the labels exactly as the app prints them) and a **VOICE** line (the narration, first
person). Quick-reference clips run 3 to 8 steps and about 60 to 90 seconds; the VOICE lines double as the
caption text, so each is one or two plain sentences in the present tense.

House rules that apply to every script:

- **The VOICE lines are yours to loosen.** Say them your way; only the claims must stay, because each one
  matches what is on screen, read from the code.
- **One take per step** where you can, so a flubbed line costs one step, not the clip.
- **1280 by 720** is the frame (witus plan 30, section 8.3, and the tutorial recording config). Set the browser
  window to that size before pressing record, and keep it there for every clip.
- **Placeholder data only.** `INDEX`, `OTHER`, `FUNDX` and `CASH`; made-up shares and amounts; the account
  `Practice` at `Example Brokerage`. No real symbol, balance or account name reaches the screen.
- **Never on screen:** the admin password, any `.env` file or shell variable, the Vercel **Environment
  Variables** page, the cron secret, the Tiingo token, a real email address, the JSON from a production cron
  run (it lists your real holdings).
- **"Information, not advice" is said once** in every clip that shows a share count or a money amount.
- The pre-flight list is in [`recording-checklist.md`](recording-checklist.md).

Where a clip runs:

| Script | Where | Why |
|---|---|---|
| 1, 2, 7 | Production, https://invest.witus.online | Public pages hold no personal data; the sign-in only works on the registered origin |
| 3, 4 | The laptop copy, http://127.0.0.1:8000/admin/ | The admin on production holds real statements |
| 5 | Both: the Vercel dashboard for the run, then the laptop copy for the values | Production values would show real symbols; a laptop copy prices placeholders from a CSV file |
| 6 | The laptop copy, after chapter 09 merges | Same reason as 3 and 4 |
| 8 | The laptop copy, after chapter 12 merges | The journal and reviews on production are personal |
| 10 | The laptop copy, after chapter 14 merges | The ranking needs a year of closes; the laptop's planted placeholders give it without a vendor |

## Test data for the laptop copy

Prepare once, before scripts 3 to 6, with `runserver` up and the superuser signed in at `/admin/` (type the
password off camera; the browser stays signed in).

- **Account:** Name `Practice`, Broker `Example Brokerage`, Kind **Paper (practice)**, Currency **US dollar**,
  Owner the superuser, Witus user id empty.
- **Statement 1:** As of `2026-09-30`, Source `September statement`. Lines: `INDEX` 10.5 shares, cost basis
  1050.00; `FUNDX` 20 shares, cost basis 400.00; `CASH` 250 shares, cost basis empty.
- **Holdings kinds:** `INDEX` **ETF**, `FUNDX` **Mutual fund**, `CASH` **Cash**.
- **Statement 2** (script 4 enters it on camera; if you record script 5 first, enter it beforehand): As of
  `2026-10-27`, Source `October statement`. Lines: `INDEX` 12 shares, cost basis 1200.00; `OTHER` 5 shares,
  cost basis empty; `CASH` 100 shares, cost basis empty.
- **Prices:** `mkdir -p data/private/prices && cp data/sample/illustrative-daily-prices.csv data/private/prices/INDEX.csv`.
  The sample ends on 2026-09-30, so `INDEX` reads **stale** on the account page, which script 5 uses. No file
  for `OTHER`, so it reads **no price yet**.

Script 3 records the account and statement 1 being entered, so for script 3 start from empty **Accounts**,
**Holdings** and **Snapshots** tables (delete the rows in the admin, or start from a fresh `migrate`).

---

## Script 1: The landing page and the waitlist

**Target length:** 75 seconds, 6 steps. **Where:** production, signed out. **Shows money:** no.

**Preconditions and test data.** A private browser window at 1280 by 720, signed out of WitUS. A throwaway
name and address for the form (for example the name `Tutorial take` and an address at a domain you own that
reaches no one). After the take, delete the entry: `/admin/`, **Pages**, **Waitlist entries**, tick it, choose
**Delete selected waitlist entries** in the **Action:** menu, **Go**, confirm.

1. **[SCREEN]** Open https://invest.witus.online/. Hold on the top of the page: the header (**Invest.WitUS**,
   **FAQ**, **Waitlist**, **Sign in**), the eyebrow **A learning tool, not advice**, the headline "Pick a method
   you learned. Practice it on paper. The app keeps you to its rules and shows you the lesson behind each
   one.", the buttons **Join the waitlist** and **Read the FAQ**.
   **VOICE:** "This is Invest dot WitUS dot online. The headline is the whole job: pick a method you learned,
   practice it on paper, and the app keeps you to that method's rules. It's a learning tool. It recommends
   nothing."
2. **[SCREEN]** Scroll to **How it works**. Hold on the three numbered steps.
   **VOICE:** "Three steps. Pick a method a course teaches. Practice it on paper. Review yourself against the
   rules. The review predicts nothing; it shows you where you left your plan and sends you back to the
   lesson."
3. **[SCREEN]** Scroll past **The courses** (both lines read "lesson coming") to the **Report a bad actor**
   callout. Hover **Where to report**; do not click.
   **VOICE:** "Every page carries this. If someone took your money, the desks that take reports are one click
   away. The app itself takes no complaints; the government does. That's its own clip."
4. **[SCREEN]** Scroll to **Waitlist**. Cursor into **Name**, type the throwaway name; into **Email**, type
   the throwaway address. Pause on the line under the fields, "Invest.WitUS is a learning tool, not advice, and
   not open to other users yet. Access later is for education, alongside the course."
   **VOICE:** "The app isn't open to other users yet. The waitlist is a name and an email, and the line under
   the form says what you'd get later: education, alongside the course."
5. **[SCREEN]** Click **Join the waitlist**. Hold on the **Thank you** page: "You are on the list. You will hear
   from us when the app opens to learners, and not before."
   **VOICE:** "That's it. No confirmation email, no drip sequence. You hear from me when the app opens to
   learners, and not before. Join twice and you're still one row."
6. **[SCREEN]** Press the browser's back button, scroll to **Roadmap**. Hold on its two lines, **Now** and
   **Next**.
   **VOICE:** "The roadmap is two lines. Now: my own accounts. Next: other learners, education only, after a
   securities lawyer has read the terms and the privacy page."

**Closing line:** "Invest dot WitUS dot online. Information, not advice."

**Retake notes.** The throwaway address is on screen in step 4; use one you would be happy to publish, or crop
the field. Pause two seconds on the headline before speaking. Scroll with the keyboard (Space, then Shift and
Space) so the motion is even. The footer's Rise Wellness block is long; do not scroll through it on camera in
this clip.

---

## Script 2: Sign in with WitUS and sign out

**Target length:** 60 seconds, 5 steps. **Where:** production. **Shows money:** no.

**Preconditions and test data.** A private window, signed out of both invest.witus.online and
accounts.witus.online, so the provider shows its sign-in page rather than sending you straight back. Your WitUS
account has a display name set (the header shows the email when it has none). Your mail client is in another
window or on another screen; the inbox is never on camera.

1. **[SCREEN]** Home page, signed out. Cursor to **Sign in** at the right end of the header; hold.
   **VOICE:** "Every WitUS app has a Sign in link in the header, with exactly that name. One account signs you
   into all of them."
2. **[SCREEN]** Click **Sign in**. Hold on accounts.witus.online: the heading **Sign in with WitUS**, the line
   "One account for the whole WitUS ecosystem. We'll email you a sign-in link.", the **Email** field, the
   button **Email me a sign-in link**. Type the address with the field cropped, or cut while typing.
   **VOICE:** "The app hands me to accounts dot WitUS dot online. No password. I type my email and ask for a
   link."
3. **[SCREEN]** Click **Email me a sign-in link**; hold on "Check your email for a sign-in link." Cut. Resume
   on the app's home page as the link lands you there.
   **VOICE:** "I open the link from my inbox, and the provider sends me back to the app."
4. **[SCREEN]** Home page, signed in: the line **Signed in as** your name, then **Open the admin**. Cursor
   along the header: **FAQ**, **Waitlist**, **Accounts**, your name, **Sign out**.
   **VOICE:** "Back on the home page, signed in. The header gained Accounts, my name, and Sign out. Open the
   admin shows only for me, the owner."
5. **[SCREEN]** Click **Sign out**. Hold as the page returns to the home page with **Sign in** back in the
   header.
   **VOICE:** "Sign out is a button, not a link, so nothing can sign me out by accident. It ends the app's
   session and the provider's, and lands me back here."

**Closing line:** "One account. Two states of the header. That's the whole sign-in."

**Retake notes.** Nothing from the inbox on camera, ever. If the provider skips its page because it already
knows the browser, stop, sign out at accounts.witus.online too, and retake from step 1. The display name is on
screen in step 4; if your WitUS account shows an email there, set a name before recording. Pause on the
**Check your email** line for a full two seconds before the cut so the edit has room.

---

## Script 3: Add an account and enter a statement

**Target length:** 90 seconds, 6 steps. **Where:** the laptop copy's admin. **Shows money:** yes.

**Preconditions and test data.** `runserver` up; the browser signed in at http://127.0.0.1:8000/admin/ before
recording (password off camera); **Accounts**, **Holdings** and **Snapshots** empty. The test data from the top
of this file, statement 1 only.

1. **[SCREEN]** The admin's front page, **Site administration**: the groups **Holdings** (Accounts, Holdings,
   Snapshots), **Pages** (Waitlist entries), **Prices** (Daily closes), **Sign in with WitUS** (WitUS identities).
   **VOICE:** "The admin is the back office. Everything I type about my accounts goes in here, and nothing in
   here is public."
2. **[SCREEN]** Under **Holdings**, click **Accounts**, then **Add account**. Fill: **Owner** the superuser;
   leave **Witus user id** empty; **Name** `Practice`; **Broker** `Example Brokerage`; **Kind** **Paper
   (practice)**; **Currency** **US dollar**. Click **Save**.
   **VOICE:** "One account per brokerage account. A name, the broker as the statement spells it, and a kind:
   brokerage, retirement, or paper. The WitUS user id fills itself the next time I sign in."
3. **[SCREEN]** Hold on the **Accounts** list: the row `Practice`, `Example Brokerage`, `Paper (practice)`,
   `USD`, the owner, **0 statements**.
   **VOICE:** "No balance lives on the account. Balances come from statements, dated, one row each."
4. **[SCREEN]** Under **Holdings**, click **Snapshots**, then **Add snapshot**. **Account** `Practice`; **As of**
   `2026-09-30`; **Source** `September statement`. In **Snapshot lines**: `index` 10.5 and 1050.00; `fundx` 20
   and 400.00; `cash` 250 with **Cost basis** empty. Click **Save**.
   **VOICE:** "A statement is a snapshot: the as-of date printed on it, not today, and one line per symbol.
   Shares, and the cost basis when the statement prints it. These are placeholder symbols and made-up numbers.
   Information, not advice."
5. **[SCREEN]** Hold on the **Snapshots** list: `2026-09-30`, `Practice (Example Brokerage)`, `September
   statement`, **3** under **Lines**. Click the date; hold on the grid with the symbols now in capitals.
   **VOICE:** "Saved. Symbols come back in capitals, shares keep six places, money keeps cents. Nothing here is
   ever overwritten; the next statement is a new row."
6. **[SCREEN]** Under **Holdings**, click **Holdings**: three rows with a blank **Kind**. Set `CASH` to **Cash**,
   `FUNDX` to **Mutual fund**, `INDEX` to **ETF**; click **Save** at the bottom of the list.
   **VOICE:** "The app made a holding per symbol and left the kind blank, because it never guesses what a
   symbol is. I set it. Cash matters: it's valued at face and never sent to the price source."

**Closing line:** "An account, one statement, three holdings. Next clip: a second statement, and what changed."

**Retake notes.** The admin's header shows the signed-in username at the top right; keep it a placeholder like
`owner`. Type the lines at a steady pace; the grid is the longest part, so pause after each row. If a number
lands in the wrong column, finish the take and retake step 4 alone from **Add snapshot** after deleting the
statement.

---

## Script 4: Compare two statements

**Target length:** 75 seconds, 5 steps. **Where:** the laptop copy's admin. **Shows money:** yes.

**Preconditions and test data.** Script 3's state: the account, statement 1, the three kinds set. Statement 2's
numbers ready to type (top of this file).

1. **[SCREEN]** **Snapshots**, **Add snapshot**. **Account** `Practice`; **As of** `2026-10-27`; **Source**
   `October statement`. Lines: `INDEX` 12 and 1200.00; `OTHER` 5 with **Cost basis** empty; `CASH` 100 with
   **Cost basis** empty. Click **Save**.
   **VOICE:** "A month later, a second statement. One number changed, one symbol gone, one new, and one cost
   basis the statement didn't print."
2. **[SCREEN]** **Accounts**. Cursor to the **Statements** column, now **2 statements**. Click it.
   **VOICE:** "The account's Statements link lists every statement, newest first."
3. **[SCREEN]** The page **Statements for Practice (Example Brokerage)**: **Statements, newest first** with
   `2026-10-27 (October statement) 3 lines` and `2026-09-30 (September statement) 3 lines`. Below,
   **Change between two statements** with **From** `2026-09-30`, **To** `2026-10-27`, and **Compare**.
   **VOICE:** "Below the list, the change between any two. The two newest are picked for me; From and To
   choose any pair."
4. **[SCREEN]** Hold on the table: rows `CASH`, `FUNDX`, `INDEX`, `OTHER`; columns **Shares before**, **Shares
   after**, **Shares change**, **Cost basis before**, **Cost basis after**, **Cost basis change**. Cursor down
   the **Shares change** column (`-150.000000`, `-20.000000`, `+1.500000`, `+5.000000`), then across the `OTHER`
   row to **not shown**.
   **VOICE:** "Per symbol: shares before and after, cost before and after, each change with its sign. FUNDX
   went to zero. OTHER is new. Where a statement printed no cost basis, the table says not shown instead of a
   zero that would lie. Shares and cost basis only, straight from the statements. Information, not advice."
5. **[SCREEN]** Set **From** to `2026-10-27` and **To** to `2026-09-30`; click **Compare**. The line still reads
   "From 2026-09-30 to 2026-10-27", the table unchanged.
   **VOICE:** "Pick them backwards and the page sorts them. The earlier date is always From."

**Closing line:** "Two statements, one table of what changed, nothing overwritten."

**Retake notes.** The line under the form says the comparison "does not use stored prices" (since 2026-10-29;
takes recorded before then show the older "fetches no prices yet (chapter 08)", which was out of date: retake
the frame or cut it). Do not read either aloud as a claim about the app. Pause on the
table for three seconds before the voice starts; it is the densest frame in the set.

---

## Script 5: Account values after the nightly pull

**Target length:** 90 seconds, 6 steps in two scenes. **Where:** scene A on the Vercel dashboard (production);
scene B on the laptop copy. **Shows money:** yes.

**Preconditions and test data.** Scene A: signed in to Vercel with the invest-witus project open at
**Settings**, **Cron Jobs**; `TIINGO_API_KEY` and `CRON_SECRET` set; the **Environment Variables** page never
opened on camera. Scene B: the laptop copy with scripts 3 and 4's data, `data/private/prices/INDEX.csv` copied
from the sample, a terminal at the repository root, and the browser signed in at `/admin/`.

1. **[SCREEN]** Scene A. **Settings**, **Cron Jobs**: the row `/api/cron/pull-prices/` with `0 6 * * *`.
   **VOICE:** "Once a day, at six UTC, Vercel calls one route in the app with a secret. The route asks Tiingo
   for the last seven days of closes, one request per symbol, and stores them in the app's own table. No page
   ever asks a vendor."
2. **[SCREEN]** Press **Run** on that row. Hold until the run shows as finished. Do not press **View Logs**.
   **VOICE:** "I can run it by hand. Running it twice changes nothing: a day already stored is left alone. The
   log would list my real holdings, so this clip stops here and moves to a laptop copy."
3. **[SCREEN]** Scene B. The terminal: run
   `uv run --env-file .env python manage.py pull_prices --symbols INDEX --since 2026-09-22`, hold on
   `Inserted 7, updated 0, unchanged 0.`; run it again, hold on `Inserted 0, updated 0, unchanged 7.`
   **VOICE:** "On a laptop the same pull reads a file per symbol. Seven days in. Run it again: nothing
   inserted, seven unchanged. Same code, same promise."
4. **[SCREEN]** The browser: open http://127.0.0.1:8000/accounts/. Hold on **Your accounts**: `Practice
   (Example Brokerage, paper (practice))` and the line "Each page values the account's latest statement at the
   latest close the app has stored, with the close's date beside it. Information, not advice."
   **VOICE:** "Accounts is the one page that shows a value, and only to the signed-in owner."
5. **[SCREEN]** Click `Practice`. Hold on **Statement as of 2026-10-27 (October statement)** and the table:
   `CASH` 100.00, close 1.00, as of 2026-10-27, source `statement`, value 100.00; `INDEX` 12.00, close 110.10,
   as of 2026-09-30 with **stale**, source `csv`, value 1321.20; `OTHER` **no price yet**; **Total of the
   priced lines** 1421.20; the note "No price yet for OTHER".
   **VOICE:** "Each line is valued at the latest close the app stored, with that close's date and source beside
   it. INDEX is marked stale: its last close is older than five days. OTHER has no close yet, so it's listed,
   not valued, and the total says what it adds: the priced lines only. Made-up numbers. Information, not
   advice."
6. **[SCREEN]** `/admin/`, **Prices**, **Daily closes**: the `INDEX` rows by **Date**, **Close**, **Source** `csv`,
   **Fetched at**.
   **VOICE:** "What the pull stored is a table I can read. Delete a row, and the next run fetches that day
   again."

**Closing line:** "A nightly pull, one row per symbol per day, and a page that shows its dates."

**Retake notes.** Scene A's only safe frames are the Cron Jobs list and the run status. The log line's JSON
names every real symbol you hold; if it opens by accident, cut it. The Vercel sidebar may show other projects'
names; crop to the page body if any of them is private. In scene B the terminal must not show `.env` or any
variable; clear it before recording. The values in step 5 depend on the day you record: `stale` appears while
the sample's last close (2026-09-30) is more than five days back, and the `CASH` line's date is statement 2's.
If you change the test data, recompute the two values and the total before recording (shares times close,
rounded to cents).

---

## Script 6: The watch list (when chapter 09 lands)

**Built on a branch, not merged.** Chapter 09 lives on `feat/tutorial-ch09` (commit `7139326`) as this is
written. Every label below is from that branch's `watchlist/templates/watchlist/_section.html` and
`watchlist/views.py`. Record after the chapter merges and the laptop copy has run its migration
(`watchlist.0001_initial`); re-read the template once before recording in case the merge changed a word.

**Target length:** 75 seconds, 6 steps. **Where:** the laptop copy, signed in at `/admin/`. **Shows money:** yes
(closes).

**Preconditions and test data.** Scripts 3 to 5's data. `FUNDX` is no longer held on statement 2, so it is the
symbol to watch. A file `data/private/prices/FUNDX.csv` in the `date,close` format with the last five weekdays
and made-up closes (around 20.00), so the pull can price it; no file for `OTHER`. The watch list empty.

1. **[SCREEN]** `/accounts/`, click `Practice`. Scroll below the holdings table to **Watch list**: "Nothing on
   the watch list yet.", the **Symbols** box with its rule under it, **Note (optional)**, the button **Add to
   the watch list**.
   **VOICE:** "Under the holdings, the watch list: symbols I follow in this account without holding them.
   Empty so far."
2. **[SCREEN]** Type `FUNDX` in **Symbols** and `a fund I might add` in **Note (optional)**; click **Add to the
   watch list**. Hold on the notice at the top of the page, "Added to the watch list: FUNDX.", then on the row:
   `FUNDX`, the note, **no price yet**, and the line "Prices arrive after the nightly pull: no close is stored
   yet for FUNDX."
   **VOICE:** "I add a symbol, with a note on why. No price yet: the page never asks a vendor. The nightly pull
   will fetch it, the same way it fetches what I hold."
3. **[SCREEN]** The terminal: `uv run --env-file .env python manage.py pull_prices --symbols FUNDX`; hold on the
   `Inserted` line. Back in the browser, reload the account page; hold on the `FUNDX` row: the close, its date,
   source `csv`.
   **VOICE:** "After the pull, the row has a close with its date and source, from the same table as everything
   else. There is no buy button. A symbol reaches a plan only when I put it in the plan's universe.
   Information, not advice."
4. **[SCREEN]** Type `OTHER, fundx` in **Symbols**; click **Add to the watch list**. Hold on the two notices,
   "Added to the watch list: OTHER." and "Already on the watch list: FUNDX.", then on the `OTHER` row reading
   **no price yet**.
   **VOICE:** "Several at once, commas or spaces, any case. One I already watch is reported, not duplicated."
5. **[SCREEN]** Click **Remove** in the `OTHER` row. Hold on "Removed OTHER from the watch list." and the table
   with `FUNDX` alone.
   **VOICE:** "Remove takes it off the list. The stored prices stay, so I can watch it again, or hold it,
   tomorrow."
6. **[SCREEN]** Scroll to the line under the form: "Watching a symbol places no order and recommends nothing.
   A symbol reaches a plan only when you add it to the plan's universe. Information, not advice."
   **VOICE:** "The line under the form says what the list is not. It places no order, and it recommends
   nothing."

**Closing line:** "A watch list, priced from the same table as everything else, with nothing to buy."

**Retake notes.** The notices sit at the top of the page and vanish on the next page load; capture each one
before scrolling. The `Inserted` count in step 3 is the number of rows in `FUNDX.csv` inside the last seven
days; say "the pull fetches it" rather than a number. The PRD describes a "change since added" column; the page
has none, so do not mention one.

## Script 7: The FAQ and reporting a bad actor

**Target length:** 75 seconds, 5 steps. **Where:** production, signed out. **Shows money:** no.

**Preconditions and test data.** A private window, signed out. Nothing to prepare.

1. **[SCREEN]** Home page. Click **FAQ** in the header. Hold on the heading **Invest.WitUS FAQ: what to ask
   about any investing app** and the paragraph under it.
   **VOICE:** "The FAQ answers the questions a careful person asks about any investing app, this one included,
   and links the law behind each answer."
2. **[SCREEN]** Hold on the first section, **Report a bad actor**, and its bold opening line.
   **VOICE:** "It opens with the most useful part. If someone took your money, pressured you, or won't give it
   back, report it. It's free, and you don't need a lawyer."
3. **[SCREEN]** Scroll slowly down the list of desks: the SEC, FINRA, the Indiana Securities Division, NASAA,
   the CFPB, the CFTC, the FTC's ReportFraud, the FBI's IC3. Stop on the closing line, "Keep the names, dates,
   screenshots and statements."
   **VOICE:** "Eight desks, one per kind of problem: a broker or adviser, a brokerage firm, Indiana, another
   state, a bank or payment app, futures and crypto derivatives, a scam, anything online. Not sure which? File
   with the SEC or your state regulator. They forward what isn't theirs."
4. **[SCREEN]** Scroll to **A. Questions to ask about any investing app, and our answers**. Cursor down the
   question headings: "Is this app a registered investment adviser or broker?", "Who holds my money?", "Can I
   lose money, and can I lose more than I put in?", "What does 'information, not advice' mean in practice?".
   Then flick past **B** and **C** to **References**.
   **VOICE:** "Then the questions themselves: is this a registered adviser, who holds my money, can I lose it,
   what does information not advice mean in practice. Then who would govern a professional version, and the
   laws, with the primary text linked."
5. **[SCREEN]** Press the browser's back button to the home page. Scroll to the **Report a bad actor** callout
   and its button **Where to report**; click it, and hold as the page lands on the FAQ's section. Then scroll
   to the footer and hover **Report a bad actor** under **Partners & Legal**.
   **VOICE:** "The same section is linked from the home page and from every footer. The app takes no
   complaints about other companies. The desks that do are one click away on every page."

**Closing line:** "Read the FAQ before you trust any investing app. This one included."

**Retake notes.** The FAQ is long; scroll with the keyboard and never faster than the eye can read a heading.
The reference list at the end is not on camera for more than a second. Nothing on this page is personal, so
production is fine.

## Script 8: Skip a month, close it, and export the logbook

**Target length:** 90 seconds, 7 steps. **Where:** the laptop copy, signed in. **Shows money:** yes (amounts).

**Preconditions and test data.** The account `Practice` running index investing from `2026-01-01`, 100.00 into
`INDEX`, days 1 to 7, with chapter 10's two buys (2026-01-02 and 2026-02-12) and nothing in March; migrated to
chapter 12 (`methods.0003`). No month closed yet. Every label below is from the templates at tag `v12`.

1. **[SCREEN]** `/accounts/<id>/method/?view=b&through=2026-03-31`. Hold on the **Rule checks** table: "Buy once
   in every month of the plan." reads **fail**; the **Months** table shows `2026-03` as **missed**.
   **VOICE:** "March has no buy, and the review says so. The method asks for one every month."
2. **[SCREEN]** Scroll to **Log an entry**. Set **Day** to `2026-03-04`, **Kind** to **Skip**, leave **Action**,
   **Symbol** and **Amount** empty, type `Practice month: I read the lesson again instead.` in **Why**, pick
   **Unsure** in **State**, type `practice` in **Tags**; click **Log it**. Hold on "Logged: 2026-03-04 skip."
   **VOICE:** "A skip is a decision, so it needs a reason. I write why, and how I felt."
3. **[SCREEN]** The same view, reloaded with `?view=b&through=2026-03-31`: the rule now reads **explained**, the
   evidence "1 finding: 2026-03 (1 explained)", March reads **skipped**, and the finding shows "Explained by a
   skip:" with the reason.
   **VOICE:** "The miss is still on the record. The reason sits beside it, and the rule reads explained, not
   failed."
4. **[SCREEN]** Click **A: The Plan and the Logbook**. Hold on **Close last month**, then click **Review 2026-01**.
   Fill **What I did** with `Bought on day 2.`, leave **What the rules said** as drafted, fill **What I'll do next
   month** with `Buy in the first week.`; click **Close 2026-01**. Hold on "Closed 2026-01. Its entries are
   read-only now."
   **VOICE:** "Once a month's window closes, I close its review in three short answers. The middle one is drafted
   from the findings."
5. **[SCREEN]** Close **2026-02** and **2026-03** the same way, saying what happened. Then on the log form try a
   buy dated `2026-03-20`; hold on "2026-03 is closed. Reopen its review, with a reason, to change it."
   **VOICE:** "A closed month is read-only. To change it, I reopen it, and I have to say why."
6. **[SCREEN]** Open **Review 2026-03**, type `The skip was logged on the wrong day.` in **Why reopen it**, click
   **Reopen 2026-03**. Scroll to **History**: one "Closed" line with the three answers, one "Reopened" line with
   the reason.
   **VOICE:** "Every close and every reopen stays in the history, with what I wrote and when."
7. **[SCREEN]** **Open the logbook** under the view switch. Pick **Skip** in **Kind**, click **Show**, then
   **Download these as CSV**; open the file in a text editor and hold on the header row.
   **VOICE:** "The logbook filters by month, kind and tag, and downloads as CSV with the same filters. What I did,
   never what it is worth. Information, not advice."

**Closing line:** "A skip with a reason, a month closed in writing, and a journal I can take with me."

**Retake notes.** The notices vanish on the next page load; capture each before clicking on. The times in
**History** are the times you pressed the buttons, in UTC. Do not open the CSV in a spreadsheet on camera: a text
editor shows the columns exactly. Reopen March before recording again, or start from a fresh copy, because a
closed month refuses step 2's skip.

## Script 9: Report a problem or ask a question

**Target length:** 60 seconds, 5 steps. **Where:** the laptop copy, signed out, then the admin signed in as the
owner. **Shows money:** no.

**Preconditions and test data.** Migrated to chapter 13 (`reports.0001`), no `INBOX_` names in `.env`, so the
form shows that forwarding is off and nothing leaves the laptop. Every label below is from the templates at tag
`v13`.

1. **[SCREEN]** `/faq/`, scrolled to the footer. Hold on **Report a problem or ask a question** in the
   **Partners & Legal** column, then click it.
   **VOICE:** "Every page has this link, in the header and in the footer, signed in or not."
2. **[SCREEN]** The form. Hold on **What page were you on?**, which already reads `/faq/`, and on the note
   "Forwarding to WitUS Inbox is off."
   **VOICE:** "It knows which page I came from. On my laptop there is no Inbox, and the form says so."
3. **[SCREEN]** Pick **A question**, type `Where does the logbook live?` in **Your message** and
   `you@example.com` in **Your email**; click **Send**. Hold on **Thank you**.
   **VOICE:** "The report is saved first. Sending it on is a separate step that can fail without losing it."
4. **[SCREEN]** `/admin/`, **Reports and WitUS Inbox**, **Reports**. Hold on the row: **A question**, **New**,
   **Off, will retry**. Open it and hold on **Last error**.
   **VOICE:** "The owner sees every report, with where its copy stands and why."
5. **[SCREEN]** Back on the list, tick the row, choose **Send again to WitUS Inbox**, click **Go**. Hold on the
   message.
   **VOICE:** "With Inbox set up, the nightly job sends anything still waiting, and this button does it now."

**Closing line:** "Saved here first, sent when it can be, and nothing lost on the way."

**Retake notes.** Five reports an hour from one address is the limit: delete the rows in the admin between
takes, or wait. With Inbox off, step 5's message reads "Send again: 1 off." and the row keeps its reason; that is
the honest answer on a laptop.

## Script 10: Start 12-1 momentum and read the ranking

**Target length:** 90 seconds, 7 steps. **Where:** the laptop copy, signed in. **Shows money:** yes (amounts and
made-up closes).

**Preconditions and test data.** Migrated to chapter 14 (`methods.0004`). An account `Momentum practice` at
`Example Brokerage`, Kind **Paper (practice)**, with no method yet. Plant the placeholder closes off camera, after
step 2, with chapter 14's Listing 14-28 (it calls `plant_candidates` for the twenty months before this one). Every
label below is from the templates at tag `v14`.

1. **[SCREEN]** `/accounts/<id>/method/` opens on **C: The Lesson Lab**. Scroll past index investing to **12-1
   momentum, monthly top N in equal parts** and hold on its seven rules, each reading "lesson coming".
   **VOICE:** "A second method, written as seven rules. I read them before I start."
2. **[SCREEN]** In **Start a method on this account**: **Method** `12-1 momentum, monthly top N in equal parts`,
   **Amount each month** `100`, **Buy window, in days** `7`, **Symbols** `ALPHA BETA GAMMA DELTA`, **Start** the
   first of this month, **Top N to hold** `2`. Click **Start this method**. Hold on the two messages.
   **VOICE:** "My candidates, chosen before any ranking, and how many to hold. The app watches them so it has their
   prices."
3. **[SCREEN]** Reload. Hold on **The ranking for** this month: three bars, ALPHA and BETA filled with "top 2",
   GAMMA outlined to the left of the line.
   **VOICE:** "Each bar is a year's change without the latest month. The two filled bars are the ones the method
   holds."
4. **[SCREEN]** Scroll to the table under the bars and read ALPHA's row: the two dates and closes and `+24.3%`.
   Then hold on **How to read this**.
   **VOICE:** "The table has the two prices behind each number, so I can check it by hand. A high rank is a fact
   about the past year, not a forecast."
5. **[SCREEN]** Hold on **Not ranked**: DELTA and the months it needs, and **Get 5 years of history for DELTA**.
   Do not press it on the laptop.
   **VOICE:** "DELTA has too little history to rank, so the method leaves it out until it has a year."
6. **[SCREEN]** **Account** page, **Watch list**: the **12-1 return** column with `▲ up`, `▼ down` and "not
   ranked". Click **ALPHA**, pick **All**, and hold on the shading and the "excluded" label.
   **VOICE:** "The darker shading is the window the return is measured over; the lighter strip is the latest month,
   which the method leaves out."
7. **[SCREEN]** Back on the method page, **This month's rebalance**: **Buy $50.00 of ALPHA**, **Buy $50.00 of
   BETA**. Hold on the last line.
   **VOICE:** "The month's money, in equal parts, into the top two. Arithmetic on my own list. Information, not
   advice."

**Closing line:** "Seven rules, one ranking, and the reason behind every number on the page."

**Retake notes.** The month in the heading is the month you record in; the planted closes move with it, so the
numbers stay the same. To record step 2 again, end the plan from **Change or end this plan** first, or delete the
account in the admin and plant again.
