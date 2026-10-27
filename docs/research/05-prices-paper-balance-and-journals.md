> Copied 2026-10-27 from the WitUS ecosystem's local planning notes, `gemini/witus/plans/future/invest-witus-research-2026-10-27/05-prices-paper-balance-and-journals.md` (researched and written 2026-10-27). Edit on copy: three personal references generalized. Paths to `plans/` files refer to those local notes and are not in this repo.

# Invest.WitUS research 05: paper balance, price data, and trading journals

Written 2026-10-27. Tags: **V** = read on the page today (URL given); **I** = inferred. Prices, limits and licenses not read are written "not stated". Sites that refused me are listed under "Blocked or unread". This file does not repeat `03-law-and-vendor-terms.md` (Alpaca account terms, SnapTrade free plan, Massive individual plans); it points to it where needed.

---

## 1. Alpaca paper account starting balance

**Plain answer.** Not reliably, and not by API. Alpaca's docs still say a paper account can be reset "with arbitrary amount as you configure", but the same page says the dashboard now creates and deletes paper accounts "rather than resetting them", and an Alpaca staff member wrote in October 2025 that "The paper account equity cannot be changed" and suggested making a new account (with $100k) instead. No Alpaca page read today shows an amount field on the "Open New Paper Account" flow, a minimum or a maximum. Up to three paper accounts are allowed. No API endpoint for creating paper accounts or setting their balance was found. BAM should open the dashboard and check whether the new-account dialog asks for an amount (user task).

### 1.1 What Alpaca's docs say (V)

URL: https://docs.alpaca.markets/docs/paper-trading (same text at https://docs.alpaca.markets/us/docs/paper-trading)

- "Your initial paper trading account is created with $100k balance as a default setting." (V)
- "You can reset the paper trading account at any time later with arbitrary amount as you configure." (V)
- "You cannot change the account balance after it is created, unless you reset it." (V)
- "We've updated the dashboard to allow you to create and delete paper accounts, rather than resetting them." (V)
- "To create a new paper account, click the paper account number in the upper left corner of the dashboard" and select "Open New Paper Account". To delete: account number, then "Account Settings", then "Delete Account". (V)
- "Don't forget to generate new API keys for any newly created account." (V)
- Paper base URL: `https://paper-api.alpaca.markets`. (V)
- Minimum or maximum balance: not stated. Number of paper accounts: not stated on this page. Whether deleting an account removes its history: not stated. (V, absence)
- Simulation limits on the same page: no dividends, no order-fill emails, random partial fills 10% of the time, no market impact, slippage, queue position, price improvement or regulatory fees. (V)

### 1.2 Alpaca staff and older docs (V)

- Alpaca forum, "Paper trading balance", staff reply by Dan_Whitnable_Alpaca, October 14, 2025: "The paper account equity cannot be changed." He suggested creating a new paper account each day with $100k. URL: https://forum.alpaca.markets/t/paper-trading-balance/17970 (V)
- Alpaca forum, "Not able to reset my Alpaca paper account", staff reply by sarahvignale, March 14, 2025: "resetting an account now requires you to delete the existing paper account or create a new one." URL: https://forum.alpaca.markets/t/not-able-to-reset-my-alpaca-paper-account/16434 (V)
- Alpaca forum, "No button to reset paper account" (January to March 2025): users report "the reset button seems to have disappeared" and "the documentation still instructs us to click the reset button." No staff reply. URL: https://forum.alpaca.markets/t/no-button-to-reset-paper-account/15933 (V)
- Old docs (repository archived April 11, 2025): "Once you reset the paper trading account, the trading history of the paper trading account is wiped out" and "Please make sure to re-generate the API key as the old key is associated with your old paper trading account". URL: https://github.com/alpacahq/alpaca-docs/blob/master/content/trading/paper-trading.md (V). This describes the retired reset button, not the current create/delete flow.
- 2020 forum reply (not staff): "When you hit the reset account button, it'll ask you what you want to reset it to." URL: https://forum.alpaca.markets/t/how-to-change-starting-amount-of-paper-account/2218 (V). Retired flow.
- Alpaca Learn, "How to Start Paper Trading with Alpaca's Trading API" (published February 11, 2021, updated March 23, 2026): "Paper Trading allows up to 3 distinct simulated accounts with separate balances and positions". URL: https://alpaca.markets/learn/start-paper-trading (V)
- Third party, TradersPost blog (September 16, 2026): "You cannot change the account balance after the account is created unless you delete it and create a new one." No amount field described. URL: https://blog.traderspost.io/article/alpaca-paper-trading (V; not Alpaca's own page)

### 1.3 API (V, I)

- No Trading API endpoint to create a paper account, reset one, or set its cash was found in the docs or search results; every source describes these as dashboard actions (V, absence; https://docs.alpaca.markets/us/docs/paper-trading). Paper accounts cannot take deposits like a live account (I, from "cannot change the account balance").
- Alpaca's Broker API sandbox (for broker-dealers and RIAs, see file 03 section 3.1) funds test accounts by simulated transfers; that is a different product and not open to BAM's use case (I).

### 1.4 What it means for Invest.WitUS (I)

- **Answers:** custom balance on the current dashboard: unconfirmed, likely no (staff said equity "cannot be changed"); by API: no; min/max: not stated; reset wipes history: under the old reset, yes; under create/delete, a deleted account is gone with its keys and the history is not stated; several accounts: up to 3.
- **Design fix that does not depend on Alpaca:** if the owner wants to practise with $1,000 or $10,000, the app should keep a **"practice budget" sleeve** in its own database: the user sets a budget (e.g. $10,000), the app refuses orders that would exceed the sleeve's cash, and it computes sleeve value from its own fills. The Alpaca paper account just executes; the $100k behind it is ignored. This also matches real life better (a learner's real account will rarely hold $100k) and survives Alpaca changing the dashboard again.
- **Keep history in Invest.WitUS, not in Alpaca.** Because deleting a paper account loses its keys and possibly its history, the app should copy every order and fill into its own logbook as it happens (I).
- **User task:** BAM opens the Alpaca dashboard, clicks the paper account number, "Open New Paper Account", and notes whether an amount field appears and its limits.

---

## 2. Price data for showing a portfolio's current value

**Need (from the brief):** current value of held stocks, ETFs and, if possible, mutual funds; end-of-day or delayed is fine; one daily pull plus an on-page refresh. Phase 1 = BAM only. Phase 2 = other users, education only.

**Plain answer.** Every free tier read today is for personal or internal use; none read today lets a free key's data be shown to other people. Two designs avoid redistribution in phase 2: (a) read each user's own positions from their own broker account (Alpaca's position object already carries `current_price` and `market_value`), and (b) let each user paste their own data key, which Tiingo's developer program explicitly allows. For phase 1, Alpaca's own position data plus Tiingo's free end-of-day prices (which include mutual fund NAVs) cover everything BAM needs at $0.

### 2.1 Alpaca Market Data (free "Basic" plan, comes with a paper account) (V)

URLs: https://docs.alpaca.markets/docs/about-market-data-api ; https://docs.alpaca.markets/us/docs/market-data-faq ; https://docs.alpaca.markets/us/docs/historical-stock-data-1 ; https://docs.alpaca.markets/reference/getallopenpositions

- Price: Basic "Free"; Algo Trader Plus "$99 / month". (V)
- Coverage: both plans "US Stocks & ETFs". Mutual funds: not stated. OTC: "Market data for OTC symbols can only be queried with a special subscription". (V)
- Real-time: Basic is "IEX" only; Algo Trader Plus is "All US Stock Exchanges". IEX "accounts for approximately ~2.5% of the market volume". (V)
- Historical: "Since 2016" on both; Basic limitation "latest 15 minutes"; "For historical queries, the `end` parameter must be at least 15 minutes old to query SIP data without a subscription." So free users get consolidated (SIP) bars, including the official daily close, once they are 15 minutes old. (V)
- Rate limit: Basic "200 / min" historical API calls; WebSocket "30 symbols". (V)
- Paper accounts: "As an Alpaca Paper Only Account holder, you are only entitled to receive and make use of IEX market data." (V, https://docs.alpaca.markets/docs/paper-trading). Tension with the FAQ's SIP-older-than-15-minutes rule is not resolved on either page; test with BAM's paper keys (I).
- Positions: the Trading API position object has `current_price` ("Current asset price per share"), `lastday_price` ("Last day's asset price per share based on the closing value of the last trading day") and `market_value` ("Total dollar amount of the position"); data is "updated live as price information is updated". (V) So for holdings inside Alpaca, the app needs no separate price feed at all (I).
- Terms: the market data docs say nothing about redistribution (V). Alpaca's Customer Agreement: "I agree not to reproduce, distribute, sell or commercially exploit the market data in any manner without written consent from Alpaca." (V, already in file 03 section 4.2.)
- Attribution: not stated.

### 2.2 Tiingo (V)

URLs: https://www.tiingo.com/about/pricing ; https://www.tiingo.com/documentation/general/overview ; https://www.tiingo.com/documentation/end-of-day ; https://www.tiingo.com/documentation/appendix/developers

- Free "Starter": "$0/month"; 50 requests per hour; 1,000 per day; 500 unique symbols per month; 1 GB per month. Power: "$30/month (or $300/year) for individuals and $50/month (or $499/year) for internal commercial use." (V)
- Coverage: "US & Chinese stocks 49,599"; "ETFs & mutual funds 60,789" on both plans. (V)
- End-of-day timing: "Most US Equity prices are available at 5:30 PM EST, however exchanges may send corrections until 8 PM EST." "Mutual Fund NAVs are available after 12 AM EST." Raw and adjusted prices, CRSP-style split and dividend adjustment. (V)
- Real-time (IEX) per plan: the pricing page lists a "Real-time Data" row but its Starter and Power cells did not render; not stated. (V, absence)
- License: both plans "Internal Use Only". "Internal use means you may only use the data for your own personal use and you may not display or share the data with another person or organization". "For Basic and Power accounts, data is for internal and personal use only. You may not redistribute the data in any form." Redistribution in "a website or app" requires contacting Tiingo. (V)
- **Developer program (the phase 2 route):** permitted "where their software requires users to supply their own Tiingo API Token"; "Each user must have their own API token."; "You may then allow the user to paste their API token in your software"; "You do not need permission if your use case qualifies for our developer program"; "Tiingo must be clearly attributed as the data source." The app must never ask for the user's Tiingo password, and may not "track, record, document, distribute, or sell user API analytic meta data". Redistributing "without requiring your users to make their own Tiingo account" needs "a redistribution license". Fees for the developer program: not stated. (V)
- Full Terms of Use: blocked (see "Blocked or unread").

### 2.3 Alpha Vantage (V)

URLs: https://www.alphavantage.co/premium/ ; https://www.alphavantage.co/documentation/ ; https://www.alphavantage.co/terms_of_service/ (a PDF)

- Free: "our standard API usage limit (25 API requests per day)". Premium from "75 requests/min ... $49.99/month" up to 1,200/min at $249.99; a second price table on the same page lists $499 to $2,499 for the same tiers without explaining the difference. (V)
- Coverage: "Core Time Series Stock Data APIs covering stocks, ETFs, and mutual funds". (V)
- Timing: `TIME_SERIES_DAILY` compact output "is available to both free and premium API keys"; `TIME_SERIES_DAILY_ADJUSTED` and intraday are premium; `GLOBAL_QUOTE` "is updated at the end of each trading day for all users"; realtime and 15-minute delayed data are premium. (V)
- Terms: license is "for personal, non-commercial use"; use is "commercial" if, among other things, "You plan to use or provide information accessed through the Alpha Vantage Platform as part of any type of commercial activity that allows individuals or entities other than User to access information directly or indirectly even if the scope of such activity falls outside of the securities industry." Also commercial if the user is "employed or ha[s] an active affiliation with ... investment advisor ... securities broker-dealer". Commercial use: "please contact us at: premium@alphavantage.co". (V)
- Attribution: not stated. Free-tier display to other users: not permitted where it lets others "access information directly or indirectly" (V); whether a free, education-only app counts as "commercial activity" is not stated (I: risky, the clause covers activity "even if" outside the securities industry).

### 2.4 Financial Modeling Prep (blocked)

- Pricing (https://site.financialmodelingprep.com/developer/docs/pricing) and Terms (https://site.financialmodelingprep.com/terms-of-service) both returned HTTP 403. Limits, coverage and terms: not stated. See "Blocked or unread".

### 2.5 Twelve Data (V)

URLs: https://twelvedata.com/pricing ; https://twelvedata.com/terms

- Basic (free): "$0" "/month"; "API requests: 8 (800 a day)"; "Websockets: 8 trial"; "Real-time US equities and ETFs"; usage "Internal non-display usage". Mutual funds on Basic: not stated. (V)
- Paid (visible prices, monthly billing): Grow "$79", Pro "$229", Ultra "$999"; the page's embedded metadata lists 29, 99 and 329 USD instead, so the price is unconfirmed. Grow includes "Internal display data access". Personal and commercial pricing are on separate tabs. (V)
- Terms ("Last updated: January 1, 2026"): prohibited: "(l) Use Free Tier data for commercial purposes"; "Redistribution" is "any publication, distribution, or provision of Data to third parties"; customers may "Redistribute or provide external display of Data only if and as expressly authorized" "(including compliance with attribution requirements)". (V)
- Meaning (I): the free key is "non-display", so even BAM's own dashboard showing Twelve Data prices sits outside the free license as written; display needs Grow or higher, and display to others needs a redistribution add-on.

### 2.6 Finnhub (partly unread)

- Pricing (https://finnhub.io/pricing), rate limits (https://finnhub.io/docs/api/rate-limit) and the quote doc (https://finnhub.io/docs/api/quote) render only a title to my fetcher (JavaScript pages); free limits and coverage: not stated. (V, absence)
- Terms (https://finnhub.io/terms-of-service, no date shown): "All plan listed on Finnhub website is strictly for personal use unless explicitly stated otherwise."; "Personal plan can't be used by any business even internally without a written approval."; "You hereby agree to not redistribute or share access to data or derived results from the data" "with anyone or any 3rd party without written approval from Finnhub."; "There is a 30 API calls/second limit on top of all plan's limit". Attribution: not stated. (V)
- Meaning (I): "derived results" means even a computed portfolio value from Finnhub prices may not be shown to others without written approval.

### 2.7 Stooq (unread)

- https://stooq.com/db/h/ and https://stooq.com/ returned empty content to my fetcher. Limits, coverage and terms: not stated. See "Blocked or unread".

### 2.8 Nasdaq Data Link (unread)

- https://data.nasdaq.com/ , https://data.nasdaq.com/databases/NAEOD and https://data.nasdaq.com/databases/WIKIP render only a page title (JavaScript). Search results describe "U.S. Equity Daily History" (from January 2014) and "North American End of Day Pricing" as Nasdaq Data Link products, with no price shown in the results. Whether any free US equity end-of-day data remains: not stated. (V for the titles only)

### 2.9 EODHD (V)

URLs: https://eodhd.com/pricing ; https://eodhd.com/financial-apis/terms-conditions

- Free: "Once you register you get 20 free API calls per day."; 1 year of end-of-day history; "15-min" delayed live data; no real-time WebSocket; "Some data types are not accessible on the free package." (V)
- Coverage: end-of-day for Stocks, ETFs, Forex, Crypto, Indices ("Global"); "End-of-day covers 150,000+ tickers worldwide"; funds appear only under Fundamentals ("Funds (US)"), which Free does not include. Mutual fund prices on Free: not stated. (V)
- Paid: EOD Historical $19.99/month or $199.00/year; ALL-IN-ONE $99.99/month or $999.90/year. (V)
- Terms (no date): a "Non-Professional User" uses the data "solely in a personal capacity"; Non-Professional Users may not engage in "Selling, reselling, retransmitting, redistributing, displaying, or granting access to the Information or Services" or "Sharing access to their account with others". "Commercial / B2B Plans" exist; their terms are not stated on the pricing page. Attribution: not stated. (V)

### 2.10 yfinance and Yahoo's terms (V; not recommended)

URLs: https://github.com/ranaroussi/yfinance ; https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html

- yfinance README: "yfinance is not affiliated, endorsed, or vetted by Yahoo, Inc."; "intended for research and educational purposes"; "You should refer to Yahoo!'s terms of use" "for details on your rights to use the actual data downloaded."; "Remember - the Yahoo! finance API is intended for personal use only." License Apache-2.0; about 25.6k stars. (V)
- Yahoo Terms of Service forbid members to "access or collect data, or attempt to access or collect data, from our Services using any automated means", including "robots, spiders, scrapers, data mining tools"; "you may not access or reuse the Services, or any portion thereof, for any commercial purpose"; and "you must not reproduce, modify, rent, lease, sell, trade, distribute, transmit, broadcast, publicly perform" content; nor use it "to create any database, archive, mobile application, data feed, widget". (V)
- Meaning (I): yfinance's own README defers to these terms, and those terms bar automated collection. Do not build on it, even for phase 1, and never in a product shown to others or to students as a pattern to copy.

### 2.11 Massive (formerly Polygon) and SnapTrade

Covered in file 03 section 4: Massive individual plans forbid "an application intended for use by end users other than you"; SnapTrade's developer terms bar storing or redistributing market data passed over its API. Not repeated here.

### 2.12 Comparison table

| Source | Free limit | US stocks / ETFs / mutual funds | Timing on free | Free key: show to other users? | Attribution |
|---|---|---|---|---|---|
| Alpaca Basic | 200/min | Yes / Yes / not stated | IEX live; SIP once 15 min old | No without Alpaca's written consent (V) | not stated |
| Alpaca positions (own account) | n/a | whatever the account holds | "updated live" | the user's own account (I) | not stated |
| Tiingo Starter | 50/hr, 1,000/day, 500 symbols/mo | Yes / Yes / Yes (NAV after 12 AM) | EOD ~5:30 PM ET; IEX per plan not stated | No; **yes via user's own token** (developer program) | Required (developer program) |
| Alpha Vantage | 25/day | Yes / Yes / Yes | EOD on quote endpoint | No (commercial if others access) | not stated |
| FMP | blocked | not stated | not stated | not stated | not stated |
| Twelve Data Basic | 8/min, 800/day | Yes / Yes / not stated | Real-time US | No; free is "non-display" | Referenced, not specified |
| Finnhub | not stated (page unread) | not stated | not stated | No, incl. "derived results" | not stated |
| Stooq | unread | not stated | not stated | not stated | not stated |
| Nasdaq Data Link | unread | not stated | not stated | not stated | not stated |
| EODHD Free | 20/day | Yes / Yes / not stated | EOD, 15-min delayed | No for non-professional users | not stated |
| yfinance (Yahoo) | n/a | n/a | n/a | Yahoo terms bar automated access | n/a |

### 2.13 Recommendation (I)

**Phase 1 (BAM only, $0):**
1. **Alpaca holdings:** read `GET /v2/positions` and `GET /v2/account`; use `current_price`, `lastday_price` and `market_value` for the on-page refresh. No separate price feed needed.
2. **Anything outside Alpaca** (a retirement-plan mutual fund, a watchlist, a manual holding): one nightly job after 12:30 AM ET pulling Tiingo end-of-day prices (covers mutual fund NAVs; 1,000 calls/day and 500 symbols/month are ample for one person). Store closes in the app's own table so charts never re-fetch history.
3. **Backup:** Alpaca historical daily bars (SIP, once 15 minutes old) for stocks and ETFs if Tiingo is down.
4. Avoid Twelve Data's free key for display (it is "non-display"), Alpha Vantage's 25/day (too small for nightly pulls of many symbols plus history), and yfinance (Yahoo terms).
5. The public waitlist page shows no prices (file 03 already says so).

**Phase 2 (other users, education only):**
1. **Default to the user's own account data.** Each learner connects their own Alpaca paper account; the app shows that account's own positions and values back to that same user. The app does not pool, cache for others, or show one user's prices to another. Whether Alpaca's Customer Agreement clause ("not to reproduce, distribute ... the market data") reaches a third-party app showing a user their own account's prices is not stated; ask Alpaca in writing before launch (user task). Also note Alpaca Trading API vs Broker API (file 03 section 3).
2. **Bring-your-own Tiingo key** for prices outside the broker (mutual funds, watchlists, lesson charts): Tiingo's developer program permits it without permission, with clear "Tiingo" attribution, no password handling, and no usage analytics on their key. Email Tiingo the program registration details anyway (their page asks for it).
3. **Course charts and examples** that every student sees (same chart for all) need either a redistribution license (Tiingo, Twelve Data add-on, Massive Businesses, Alpaca written consent) or a public-domain or self-made dataset (I: e.g. a fixed, historical teaching dataset whose license allows sharing; not researched here).
4. **What changes between phases:** phase 1 uses BAM's key server-side for BAM's eyes only; phase 2 removes every shared key from any page another person can see, moves to per-user keys or per-user broker data, adds attribution text, and gets written answers from Alpaca and Tiingo before launch. If the app ever charges or bundles with a paid course, re-read every vendor's "commercial" definition (Alpha Vantage's is the broadest read).

---

## 3. Open-source trading journals that could replace Edgewonk

**Plain answer.** Two journals are worth reading closely: **LuxAlgo Trade Journal** (MIT, TypeScript, very active, the broadest feature set, Alpaca sync, playbooks with rule checklists and adherence stats) and **Trading Journal AI** (MIT, Python FastAPI backend plus React, active, the only Python candidate, emotions and mistakes extracted from a diary). TradeNote, the best-known name, is GPL-3.0 and its code has not changed since April 2025. Recommendation: **build the journal into Invest.WitUS** (direction A's logbook) in Django, and take ideas, not code, from Edgewonk, LuxAlgo and Trading Journal AI. If any code is copied, copy only from MIT projects and keep their notices.

### 3.1 Edgewonk's own feature list (what the journal must cover) (V)

URLs: https://edgewonk.com/ ; https://edgewonk.com/features ; https://edgewonk.com/trading-psychology ; price from https://edgewonk.com/pricing (read in file 01: "$197 per 12 months", "$35 per month", no free trial, 14-day money-back guarantee)

- **Imports:** "Automated imports"; over 200 brokers ("Supported Brokers"). (V)
- **Analysis:** "50+ unique data reports"; "Automated Edge Finder" scans the journal for strengths and weaknesses; setup, instrument, entry strategy and time-of-day analysis; win rate by strategy and signal; loss analysis; weekly and monthly reports; session report cards; "Chart Lab + Analytics"; "Strategy lab to help you test new ideas"; "AI-driven analysis" in the tagline. (V)
- **Discipline:** discipline tracking (rule adherence per trade and its effect on results); mistake tracking that quantifies cost; "Instant rule-break feedback"; checklists per setup tracking which criteria were met; "Trade management optimizer". (V)
- **Psychology:** "Tiltmeter" ("a clear visual view of how disciplined your trading really is", overlayable on the equity curve); "Mental tags" (confidence, focus, stress; "Discipline & rule-following"); "Efficiency" (percentage of trades that followed the rules; "Efficiency turns discipline into something measurable"); "Trading decisions" linking entry, exit and management decisions to results to spot "recurring mistakes". (V)
- **Journaling:** "Integrated trading diary"; "Mental journal"; Notebook ("your trading diary, built in"); screenshots on trades and diary entries; "Create your own comments and tags"; "Track your strategies and setups". (V)
- **Setup:** "Create unlimited journals"; stocks, forex, futures, CFDs, crypto, options; multi-currency; day, swing and investing styles. (V)
- **Sharing:** "Share individual journals" read-only with a mentor or coach, revocable. (V)
- Not named on the pages read: missed trades, goals, chart replay, trade simulator. (V, absence)

### 3.2 Candidates (all V from the GitHub API and README on 2026-10-27 unless tagged)

| Project | License (SPDX) | Stack | Last commit | Stars | Notes |
|---|---|---|---|---|---|
| TradeNote, https://github.com/Eleven-Trading/TradeNote | GPL-3.0 | Vue, Pinia, Parse Server, MongoDB, ECharts, markerjs2 (screenshot annotation), Quill | 2025-04-14 (tag 19.0.3) | 979 | PRs still opened by others (latest updated 2026-10-13) but none merged since April 2025 |
| LuxAlgo Trade Journal, https://github.com/LuxAlgo/trade-journal | MIT | TypeScript, Next.js ("local Next.js runs" in the README), SQLite, Node 22 | 2026-10-27 | 537 | Repo created 2026-08-24; "Early release. APIs and schema may still move before 1.0."; 5 contributors |
| Trading Journal AI, https://github.com/simonro/Trading-Journal-AI | MIT | Python FastAPI (uvicorn) backend, React frontend, SQLite | 2026-10-23 | 89 | Created 2026-09-06; 4 contributors; built with Claude Code per README |
| Journedge, https://github.com/TheQuantum-Dev/journedge | MIT | Next.js 16, TypeScript, SQLite | 2026-07-28 | 42 | 3 contributors; local only |
| Deltalytix, https://github.com/hugodemenez/deltalytix | CC-BY-NC-4.0 (GitHub shows NOASSERTION; LICENSE file reads "Creative Commons Attribution-NonCommercial 4.0 International") | Next.js 16, Prisma, Postgres, Supabase, Stripe, OpenAI | 2026-10-24 | 161 | Futures and prop-firm focus |
| TradeJournal (now KovaFlow), https://github.com/Bilovodskyi/ai-trading-journal | Apache-2.0 | Next.js, Drizzle, Neon Postgres, Clerk | 2026-10-12 | 78 | README says it has a successor (KovaFlow, crypto derivatives); open repo is the old version |
| Journalit, https://github.com/Cursivez/journalit | Not open source ("Proprietary Source-Available License") | Obsidian plugin, TypeScript | 2026-10-26 | 243 | "copying, modifying, redistributing ... or creating derivative works ... is prohibited" |
| OpenTraderWorld, https://github.com/G-OTW/OpenTraderWorld | FSL-1.1-MIT (source-available, not open source until the MIT change date) | Rust, Svelte, Postgres | 2026-10-27 | 77 | "Permitted Purposes" include "non-commercial education"; bars a "Competing Use" |
| Kansoku, https://github.com/kansoku-trade/kansoku | AGPL-3.0 plus "Commons Clause" (no right to "Sell") | TypeScript, macOS desktop, Longbridge broker | 2026-09-26 | 331 | AI chart-watching app for the Longbridge broker; not a journal; excluded |
| Simple-Rich-Trading-Journal, https://github.com/Simple-Rich-Trading-Journal/Simple-Rich-Trading-Journal | CC-BY-NC-ND-4.0 (LICENSE.txt: "Attribution-NonCommercial-NoDerivatives 4.0 International") | Python, JavaScript | 2025-10-02 | 51 | No derivatives allowed: cannot adapt at all |

Searches run: GitHub repository search for "trading journal", "trade journal", "tradelog", "trading journal django", "trading diary", and topic `trading-journal`, sorted by stars. No Django journal had more than 0 stars.

### 3.3 Features of the main candidates

**TradeNote** (https://tradenote.co, https://github.com/Eleven-Trading/TradeNote) (V)
- Import: "Import trades from your broker platform"; repo `brokers/` folder has a generic CSV template and Interactive Brokers Flex Query instructions.
- Tags: "Add tags and tag groups to identify patterns, setups or mistakes."
- Rules and emotions: "Mark each of your trades and days as good or bad depending on your trading rules." Separate emotions field: not stated.
- Screenshots: "Add and annotate chart screenshots".
- Diary: "Keep a daily diary of your trading journey to work on your trader psychology."
- Stats: MFE ("Add MFE prices automatically"); dashboard screenshot; full metrics list not stated on the page.
- Hosted: cloud plan $4.99/month with 7-day trial; self-hosted free.

**LuxAlgo Trade Journal** (https://github.com/LuxAlgo/trade-journal) (V)
- Import: read-only broker sync through `@luxalgo/broker-sdk` including **Alpaca**, Charles Schwab, E*TRADE, Robinhood Crypto, tastytrade, Webull and others; "16 documented formats" of statement import including TradeZella and Tradervue CSV migration; a column mapper; manual entry.
- Engine: "Round-trip engine" with FIFO, LIFO or weighted average; partial fills and scale-ins.
- Tags, setups, mistakes: trade pages carry "ratings, stops/targets, tags, mistakes"; "Notebook & playbooks": "named setups with rule checklists scored per trade, with adherence and followed-vs-broken performance in Reports."
- Emotions: no named emotions field (V, absence); AI reflection gives "session recaps, per-trade critiques".
- Stats: net and gross P&L, win rate, profit factor, expectancy, R multiples, streaks, drawdown, time-of-day and weekday, per-symbol/tag/mistake/playbook breakdowns, a published "Edge Score" formula, P&L calendar.
- Screenshots: daily journal "autosaving Markdown notes with templates and attachments (images, PDFs)", voice dictation.
- Other: "Routines & misses" (pre, during and post session routines; "a missed-opportunity log kept out of your trading metrics"); privacy mode masking money values; export CSV, JSON, PDF.

**Trading Journal AI** (https://github.com/simonro/Trading-Journal-AI) (V)
- Import: Thinkorswim and Interactive Brokers CSV, "plus a template for any other broker".
- Engine: "Trade grouping, P&L, fees and statistics are plain code with tests."
- Setups and tags: "playbook setup tags"; Settings holds "Strategies, sources and tags in one place, with rename, merge and delete".
- Emotions and mistakes: Reports break down "by day of week, time of day, hold time, setup, grade, symbol, side, emotion"; Diary: "Claude extracts strategy, stops, R-multiples, emotional state, and mistakes, and matches them to your actual trades".
- Stats: win rate, profit factor, expectancy, drawdown, MFE/MAE, exit efficiency; "Exit Lab" replays trades on one-minute Alpaca prices ("a free Alpaca account works: it serves SIP history older than 15 minutes").
- Screenshots: diary uploads of "handwritten notes, screenshots, or typed text".
- Grading: "an AI coaching report graded on process rather than P&L".

**Journedge** (https://github.com/TheQuantum-Dev/journedge) (V)
- Pre-trade planning ("Plan your thesis, entry zone, stop, and target before the trade. Compare plan vs execution after."), playbook with per-setup performance, position sizing calculator, tags, screenshots on trades, rich-text journal, Sharpe/Sortino/Calmar, hour-of-day heatmap, MAE/MFE.

### 3.4 What the licenses mean if code is adapted into a private app that may later serve other users

- **GPL-3.0 (TradeNote).** The license text: "To \"convey\" a work means any kind of propagation that enables other parties to make or receive copies. Mere interaction with a user through a computer network, with no transfer of a copy, is not conveying." and "To \"modify\" a work means to copy from or adapt all or part of the work in a fashion requiring copyright permission". (V, GPL-3.0 text in https://github.com/Eleven-Trading/TradeNote/blob/main/LICENSE) Meaning (I): a hosted Invest.WitUS that only serves web pages would not "convey" copies, so GPL source release would not be triggered by hosting alone; but the browser JavaScript is a copy sent to the user, so any GPL front-end code (TradeNote is Vue, all front end) shipped to other users' browsers is conveyed and pulls in GPL duties for that code. Porting TradeNote's JavaScript line by line to Python is still "adapt[ing] all or part of the work" (I). Avoid copying TradeNote code.
- **AGPL-3.0 (Kansoku, and any AGPL project).** Section 13: "your modified version must prominently offer all users interacting with it remotely through a computer network" the Corresponding Source. (V, https://www.gnu.org/licenses/agpl-3.0.html, partial quote) Meaning (I): AGPL code inside a hosted app serving other users forces publishing the whole combined app's source. Do not adapt AGPL code into Invest.WitUS.
- **MIT (LuxAlgo, Trading Journal AI, Journedge).** "The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software." (V, https://github.com/LuxAlgo/trade-journal/blob/main/LICENSE) Meaning (I): copying is allowed in a private or commercial app, with the notice kept (a `THIRD_PARTY_NOTICES` file is enough).
- **Apache-2.0 (TradeJournal/KovaFlow):** permissive with notice and change-marking duties (I; Apache text not fetched today).
- **CC-BY-NC-4.0 (Deltalytix) and CC-BY-NC-ND-4.0 (Simple-Rich):** NonCommercial: "You may not use the material for commercial purposes." (V, Deltalytix LICENSE). ND forbids derivatives at all. Meaning (I): risky if Invest.WitUS ever charges or bundles with a paid course; skip.
- **FSL-1.1-MIT (OpenTraderWorld):** permits "non-commercial education" but bars a "Competing Use" in a commercial product (V, LICENSE). Skip for the same reason.
- **Ideas are free.** Feature ideas (rule adherence percentage, mental tags, playbook checklists, missed-trade log) are not protected by copyright; code and screenshots are (I; general copyright principle, no source fetched today).

### 3.5 Recommendation (I)

**Build the journal into Invest.WitUS; do not adapt a journal codebase.** Reasons:
1. No candidate is Django. The only Python one (Trading Journal AI) is FastAPI plus React plus SQLite; its domain logic is what is useful, not its app shell.
2. Invest.WitUS's journal is a logbook for a slow, rules-based investing method (direction A: planned buys, skipped buys with reasons, rebalances), not a day-trader's round-trip journal. Most of Edgewonk, TradeNote and LuxAlgo is built around intraday P&L, R multiples and prop firms, which BAM does not need.
3. Owning the data model keeps the logbook in the same Postgres as the plan, rules and Alpaca fills (see section 1.4: history must live in the app anyway).
4. Licenses: TradeNote's GPL and the NC licenses would fence off phase 2.

**Features to copy as ideas (phase 1 logbook):**
- Every Alpaca fill auto-written to the logbook (LuxAlgo's "execution" primitive; one table of fills, trades derived from it).
- Per-setup **rule checklist** scored at decision time, and **rule-following rate** ("Efficiency" in Edgewonk; "followed-vs-broken performance" in LuxAlgo) as the headline metric.
- **Mistake tags** with cost (Edgewonk mistake tracking) and **mental tags** (confidence, focus, stress; Edgewonk), stored as small fixed lists BAM can edit (Trading Journal AI's rename-and-merge tag library).
- **Skip reasons and a missed-opportunity log** kept out of performance numbers (LuxAlgo "Routines & misses").
- **Pre-trade plan vs actual** (Journedge).
- **Day or week marked good or bad by the rules, not by P&L** (TradeNote; Trading Journal AI's "graded on process rather than P&L").
- Screenshot or note attachments on a logbook entry; a weekly review page.
- Phase 2: **read-only share with a mentor** (Edgewonk), which fits a course instructor reviewing a student's logbook.

**If BAM wants to copy code anyway:** use only MIT code (LuxAlgo `packages/core` round-trip logic, Trading Journal AI's Python grouping code), keep their copyright notices, and record each copied file in a notices file.

---

## Blocked or unread

| URL | What happened | What BAM can check |
|---|---|---|
| https://site.financialmodelingprep.com/developer/docs/pricing | HTTP 403 | FMP free plan limits, coverage, display terms |
| https://site.financialmodelingprep.com/terms-of-service | HTTP 403 | FMP redistribution and display terms |
| https://app.tiingo.com/tos/ | HTTP 403 | Tiingo Terms of Use, section 7 (search snippet says API data is "internal consumption only" and attribution "Data sourced by Tiingo"; not read, so not used as V) |
| https://finnhub.io/pricing , https://finnhub.io/docs/api/rate-limit , https://finnhub.io/docs/api/quote | JavaScript pages; only a title returned | Finnhub free calls per minute and free coverage |
| https://stooq.com/db/h/ , https://stooq.com/ | Empty content returned | Stooq download limits and terms |
| https://data.nasdaq.com/ , https://data.nasdaq.com/databases/NAEOD , https://data.nasdaq.com/databases/WIKIP | JavaScript pages; only a title returned | Whether any free US end-of-day dataset remains; prices; terms |
| https://data.nasdaq.com/accesstools | HTTP 404 (redirect target of the old docs link) | n/a |
| https://www.tiingo.com/about/pricing ("Real-time Data" row) | Row cells did not render | Whether Starter includes IEX real-time |
| https://www.gnu.org/licenses/gpl-faq.html | HTTP 429 twice (rate limited); not retried further | GPL FAQ on network use; GPL-3.0 text was read from TradeNote's LICENSE instead |
| https://www.gnu.org/licenses/gpl-3.0.html | Connection dropped | Same as above |
| Alpaca dashboard, "Open New Paper Account" | Needs BAM's login | Whether an amount field appears, and its limits |

## User tasks this research suggests (not filed; the caller decides)

1. Alpaca dashboard check: does "Open New Paper Account" ask for a starting amount? (blocks the decision on the in-app "practice budget" sleeve; low urgency since the sleeve works either way).
2. Before phase 2: written questions to Alpaca (may a third-party education app show users their own paper account's prices?) and Tiingo (register under the developer program; confirm a free education app with per-user tokens qualifies).

---

## References

Alpaca. (n.d.-a). *About market data API*. Retrieved October 27, 2026, from https://docs.alpaca.markets/docs/about-market-data-api

Alpaca. (n.d.-b). *Get all open positions*. Retrieved October 27, 2026, from https://docs.alpaca.markets/reference/getallopenpositions

Alpaca. (n.d.-c). *Historical stock data*. Retrieved October 27, 2026, from https://docs.alpaca.markets/us/docs/historical-stock-data-1

Alpaca. (n.d.-d). *Market data FAQ*. Retrieved October 27, 2026, from https://docs.alpaca.markets/us/docs/market-data-faq

Alpaca. (n.d.-e). *Paper trading*. Retrieved October 27, 2026, from https://docs.alpaca.markets/docs/paper-trading

Alpaca. (n.d.-f). *Paper trading* [Archived documentation repository]. GitHub. Retrieved October 27, 2026, from https://github.com/alpacahq/alpaca-docs/blob/master/content/trading/paper-trading.md

Alpaca. (2026, March 23). *How to start paper trading with Alpaca's Trading API*. https://alpaca.markets/learn/start-paper-trading

Alpaca Community Forum. (2020). *How to change starting amount of paper account* [Online forum thread]. https://forum.alpaca.markets/t/how-to-change-starting-amount-of-paper-account/2218

Alpaca Community Forum. (2025a). *No button to reset paper account* [Online forum thread]. https://forum.alpaca.markets/t/no-button-to-reset-paper-account/15933

Alpaca Community Forum. (2025b). *Not able to reset my Alpaca paper account* [Online forum thread]. https://forum.alpaca.markets/t/not-able-to-reset-my-alpaca-paper-account/16434

Alpaca Community Forum. (2025c). *Paper trading balance* [Online forum thread]. https://forum.alpaca.markets/t/paper-trading-balance/17970

Alpha Vantage. (n.d.-a). *API documentation*. Retrieved October 27, 2026, from https://www.alphavantage.co/documentation/

Alpha Vantage. (n.d.-b). *Premium API key*. Retrieved October 27, 2026, from https://www.alphavantage.co/premium/

Alpha Vantage. (n.d.-c). *Terms of service* [PDF]. Retrieved October 27, 2026, from https://www.alphavantage.co/terms_of_service/

Bilovodskyi. (2026). *ai-trading-journal* [Computer software]. GitHub. https://github.com/Bilovodskyi/ai-trading-journal

Cursivez. (2026). *journalit* [Computer software]. GitHub. https://github.com/Cursivez/journalit

Demenez, H. (2026). *deltalytix* [Computer software]. GitHub. https://github.com/hugodemenez/deltalytix

Edgewonk. (n.d.-a). *Edgewonk*. Retrieved October 27, 2026, from https://edgewonk.com/

Edgewonk. (n.d.-b). *Features*. Retrieved October 27, 2026, from https://edgewonk.com/features

Edgewonk. (n.d.-c). *Pricing*. Retrieved October 27, 2026, from https://edgewonk.com/pricing

Edgewonk. (n.d.-d). *Trading psychology*. Retrieved October 27, 2026, from https://edgewonk.com/trading-psychology

Eleven Trading. (n.d.). *TradeNote*. Retrieved October 27, 2026, from https://tradenote.co

Eleven Trading. (2025). *TradeNote* (Version 19.0.3) [Computer software]. GitHub. https://github.com/Eleven-Trading/TradeNote

EODHD. (n.d.-a). *Pricing*. Retrieved October 27, 2026, from https://eodhd.com/pricing

EODHD. (n.d.-b). *Terms and conditions*. Retrieved October 27, 2026, from https://eodhd.com/financial-apis/terms-conditions

Finnhub. (n.d.). *Terms of service*. Retrieved October 27, 2026, from https://finnhub.io/terms-of-service

Free Software Foundation. (2007a). *GNU Affero General Public License, version 3*. https://www.gnu.org/licenses/agpl-3.0.html

Free Software Foundation. (2007b). *GNU General Public License, version 3* [License text as distributed in the TradeNote repository]. https://github.com/Eleven-Trading/TradeNote/blob/main/LICENSE

G-OTW. (2026). *OpenTraderWorld* [Computer software]. GitHub. https://github.com/G-OTW/OpenTraderWorld

Hoefflin, A. F. (2025). *Simple-Rich-Trading-Journal* [Computer software]. GitHub. https://github.com/Simple-Rich-Trading-Journal/Simple-Rich-Trading-Journal

Innei. (2026). *Kansoku* [Computer software]. GitHub. https://github.com/kansoku-trade/kansoku

LuxAlgo. (2026). *Trade journal* [Computer software]. GitHub. https://github.com/LuxAlgo/trade-journal

Roussi, R. (2026). *yfinance* [Computer software]. GitHub. https://github.com/ranaroussi/yfinance

Tape to Edge. (2026). *Trading Journal AI* [Computer software]. GitHub. https://github.com/simonro/Trading-Journal-AI

TheQuantum-Dev. (2026). *Journedge* [Computer software]. GitHub. https://github.com/TheQuantum-Dev/journedge

Tiingo. (n.d.-a). *Developer program API documentation*. Retrieved October 27, 2026, from https://www.tiingo.com/documentation/appendix/developers

Tiingo. (n.d.-b). *End-of-day API documentation*. Retrieved October 27, 2026, from https://www.tiingo.com/documentation/end-of-day

Tiingo. (n.d.-c). *General API documentation overview*. Retrieved October 27, 2026, from https://www.tiingo.com/documentation/general/overview

Tiingo. (n.d.-d). *Tiingo API pricing*. Retrieved October 27, 2026, from https://www.tiingo.com/about/pricing

TradersPost. (2026, September 16). *Alpaca paper trading: What the docs omit*. https://blog.traderspost.io/article/alpaca-paper-trading

Twelve Data. (n.d.). *Pricing*. Retrieved October 27, 2026, from https://twelvedata.com/pricing

Twelve Data. (2026, January 1). *Terms of service*. https://twelvedata.com/terms

Yahoo. (n.d.). *Yahoo terms of service*. Retrieved October 27, 2026, from https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html
