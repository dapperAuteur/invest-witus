# Privacy

Last updated: October 27, 2026. Plain language on purpose. A securities lawyer reviews this page and the Terms before anyone other than the operator is admitted to the app; until then it describes what the app does today and what it is built to do.

Not advice. Invest.WitUS is a learning tool. It is not a broker, not an investment adviser, and it never recommends a security.

## Who runs the app

One operator in Indiana, who builds the WitUS family of learning tools. No employees, no contractors, no one else with access to the data.

## What we store, and why

Today the app holds two kinds of data:

- **The waitlist.** Your name and email address, and the time you joined. We keep it to tell you when the app opens to learners. Nothing else is collected with it.
- **The operator's own records.** Plans, holdings entered by hand from statements, a trading journal, and paper (simulated) trades, all belonging to the operator.

When the app opens to other learners, education only and alongside the course, it will store for each person: the WitUS user id and email address from Sign in with WitUS; the plans they write; the holdings they enter; their journal; and their paper trades. Nothing is collected that the app does not use.

## Where it lives

The hosted app keeps its database at Neon, a Postgres hosting service, and runs on Vercel. A copy of the app you run yourself from the tutorial keeps a SQLite file on your own machine, in a folder git ignores.

## Who can see it

The operator only. Your holdings, plans and journal are never shown to another user, never sold, and never shared with a vendor beyond what that vendor needs to do its job (below).

## Broker keys

Paper trading keys are the default. Any broker key you give the app stays on the server, is never sent to a browser, and is never written to a log. A live-trading key is separate, optional, and only accepted behind an explicit checklist.

## Vendors

Vendors the app uses or is built to use, each named so you can read its own terms: Alpaca (paper trading and, if you choose it, live trading), Tiingo (end-of-day prices), Neon (the database), Vercel (hosting), Mailgun (email), and WitUS Inbox (where the waitlist and in-app reports are mirrored for the operator). Each vendor sees only what it needs: Alpaca sees the orders you place through it, Tiingo sees the symbols whose prices are asked for, Mailgun sees the address an email goes to.

## Market data

No market data, prices or performance figures are shown on any public page, and no one's data is shown to anyone else. Prices inside the app are for the signed-in owner of the account they value.

## Cookies

The public pages set one cookie, for the form protection Django uses (CSRF). Signing in, when it arrives, adds a session cookie. There are no advertising or analytics cookies.

## Deleting your data

Email the Contact address in the footer from the address you signed up with. A waitlist entry is deleted on request; an account, when accounts exist, is deleted with everything attached to it. Plans and the journal export to CSV first if you ask.

## Children

The app is for adults. It is not directed at anyone under 13 and does not knowingly collect their data (see COPPA in the FAQ).

## Changes

Edits to this page are commits in the repository, with dates. The "last updated" line above moves when the text does.

## Contact

Use the Contact link in the footer of every page.
