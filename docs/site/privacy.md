# Privacy

Last updated: October 28, 2026. Plain language on purpose. A securities lawyer reviews this page and the Terms before anyone other than the operator is admitted to the app; until then it describes what the app does today and what it is built to do.

Not advice. Invest.WitUS is a learning tool. It is not a broker, not an investment adviser, and it never recommends a security.

## Who runs the app

One operator in Indiana, who builds the WitUS family of learning tools. No employees, no contractors, no one else with access to the data.

## What we store, and why

Today the app holds two kinds of data:

- **The waitlist.** Your name and email address, and the time you joined. We keep it to tell you when the app opens to learners. Nothing else is collected with it.
- **The operator's own records.** Plans (the method an account runs and the plan's own numbers, added October 28, 2026), holdings entered by hand from statements, the symbols on each account's watch list (added October 28, 2026), a trading journal (its entries, logged by hand, added October 28, 2026; from October 29, 2026 each entry may also hold a written reason, a state of mind chosen from a short list, and tags), the monthly reviews written about it (added October 29, 2026), and paper (simulated) trades, all belonging to the operator.

When the app opens to other learners, education only and alongside the course, it will store for each person: the WitUS user id, email address and name from Sign in with WitUS (the operator's own sign-in stores the same three today); the plans they write; the holdings they enter; their journal; and their paper trades. Nothing is collected that the app does not use.

## Where it lives

The hosted app keeps its database at Neon, a Postgres hosting service, and runs on Vercel. A copy of the app you run yourself from the tutorial keeps a SQLite file on your own machine, in a folder git ignores.

## Who can see it

The operator only. Your holdings, plans and journal are never shown to another user, never sold, and never shared with a vendor beyond what that vendor needs to do its job (below).

## Broker keys

Paper trading keys are the default. Any broker key you give the app stays on the server, is never sent to a browser, and is never written to a log. A live-trading key is separate, optional, and only accepted behind an explicit checklist.

## Vendors

Vendors the app uses or is built to use, each named so you can read its own terms: Alpaca (paper trading and, if you choose it, live trading), Tiingo (end-of-day prices), Neon (the database), Vercel (hosting and page-view analytics), Mailgun (email), and WitUS Inbox (where the waitlist and in-app reports are mirrored for the operator). Each vendor sees only what it needs: Alpaca sees the orders you place through it, Tiingo sees the symbols whose prices are asked for, Mailgun sees the address an email goes to.

## Market data

No market data, prices or performance figures are shown on any public page, and no one's data is shown to anyone else. Prices inside the app are for the signed-in owner of the account they value.

Added October 28, 2026: once a day the app asks Tiingo for the closing prices of the symbols the operator's accounts hold or watch, using the operator's own Tiingo token, and keeps them in its own database. That request carries symbols and dates, nothing about a person. A copy of the app run from the tutorial reads prices from a file on that machine and asks no one.

Added October 29, 2026: when the operator presses Confirm on an account linked to Alpaca's paper environment, the app sends Alpaca one order per symbol (the symbol, a dollar amount and an order id the app makes), using the operator's own paper keys, and keeps Alpaca's answer and the order's fill in its own database. Alpaca's cash and positions for that paper account are shown to the operator only. Paper orders are simulated; no real money moves. A copy of the app with no Alpaca keys sends nothing.

## Cookies

The public pages set one cookie, for the form protection Django uses (CSRF). Signing in adds a session cookie, which holds only a session id; the sign-in in progress and who is signed in live on the server. There are no advertising or analytics cookies.

## Analytics

Added October 28, 2026: the hosted site uses Vercel Web Analytics, which counts page views. Vercel's privacy page (read October 28, 2026) says the script sets no third-party cookies, tells visitors apart by a hash made from the request that is discarded after 24 hours, and ties no page view to an individual or an IP address. Each page view records the page, the referrer, the country, region and city, the browser, the operating system, and the device type. A copy you run on your own machine from the tutorial sends nothing.

## Deleting your data

Email the Contact address in the footer from the address you signed up with. A waitlist entry is deleted on request; an account, when accounts exist, is deleted with everything attached to it. The journal can be downloaded as a CSV file from its logbook page at any time; plans export to CSV first if you ask.

## Children

The app is for adults. It is not directed at anyone under 13 and does not knowingly collect their data (see COPPA in the FAQ).

## Changes

Edits to this page are commits in the repository, with dates. The "last updated" line above moves when the text does.

## Contact

Use the Contact link in the footer of every page.
