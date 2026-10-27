> Copied 2026-10-27 from the WitUS ecosystem's local planning notes, `gemini/witus/plans/future/invest-witus-research-2026-10-27/01-ux-benchmarks-and-three-directions.md` (researched and written 2026-10-27). Edit on copy: the example fund symbol in the direction A sketch is replaced by the placeholder `INDEX` (invariant 1). Paths to `plans/` files refer to those local notes and are not in this repo.

# Invest.WitUS: UX benchmarks and three design directions

Researched: October 27, 2026

**Scope.** Best-in-class UI and UX for Invest.WitUS (repo `invest-witus`): a Django app where a person picks an investing
method taught in a Learn.WitUS or ElementaryMBA course, runs it on an Alpaca paper account first, and the app helps them
stay with the method (rules, nudges, a journal, deviation flags), linking each rule back to the lesson that explains it.
Seed note: `plans/future/python-investing-app-seed-2026-10-27.md`.

**Evidence tags.** **V** = read today on a page or endpoint the vendor or body publishes. **I** = my inference from
V facts; not stated by the source. "Not stated" means the page I read did not say. Prices are as shown on October 27, 2026.
Benchmarks are grouped: open-source trackers and budgeting tools, strategy and backtest tools, automated and allocation
investing, plain long-term brokers, engagement-heavy brokers, power-user and charting tools, the paper broker itself,
performance reporting, and trading journals. Sites that refused me are in "Not reachable" at the end.

---

## 1. Benchmarks

### 1.1 Ghostfolio (open source portfolio tracker)

- **What and license.** "Open source wealth management software built with web technology" (V, GitHub README).
  "Licensed under the AGPLv3 License" (V). Stack: TypeScript Nx workspace, NestJS, PostgreSQL, Prisma, Redis, Angular (V).
- **Pricing.** Self-hosting is free under AGPLv3 (I, from the license). The README calls the "Ghostfolio Premium cloud
  offering" "the easiest way to get started" and says revenue covers hosting, data providers and development (V). The
  marketing pages render in the browser only, so the price text was not readable by my fetcher; Ghostfolio's own public
  `api/v1/info` endpoint returned `subscriptionOffer.price: 48` with `baseCurrency: USD` (V). The billing period is not
  stated in that response. The same endpoint reports 1,787 active users in 30 days and 9,586 GitHub stars (V).
- **Core screens.** README features: transactions, multi-account, performance (ROAI including dividends) for Today, WTD,
  MTD, YTD, 1Y, 5Y, Max, charts, "Static analysis to identify potential risks in your portfolio", import and export,
  Dark Mode, Zen Mode, a mobile-first PWA (V). The changelog names an X-ray page with rules, a FIRE calculator that
  counts cash outside the emergency fund, an allocations page, a watchlist, a markets overview with benchmarks and a
  Fear and Greed index, and a Presenter View (V, CHANGELOG entries 2.231.0 through 3.91.0, January to October 2026).
- **Pattern to borrow: X-ray rules.** A static-analysis page that runs named rules over the portfolio (for example a
  "Fees (Fee Ratio)" rule added in 2.239.0) and shows pass or fail per rule (V for the rules; I for the pass/fail framing).
  For Invest.WitUS this is the model for "method rules as checks": each taught rule becomes a check with a status.
- **Education link.** None found in the README or changelog (I: not stated).
- **Paper versus live.** Not applicable; it tracks, it does not trade (I).
- **Onboarding.** Self-host: copy `.env.example`, `docker compose up`, open localhost:3333, "Get Started"; the first user
  becomes ADMIN (V). The home page has an onboarding "Add activity" link (V, changelog 3.34.0). Value arrives after the
  first activity is entered (I).
- **Accessibility.** Recent changelog entries fix accessibility of specific buttons and icons (V, 3.88.0 and 3.89.0).
  "Zen Mode" hides numbers for calm viewing (I from the name; the README does not define it).
- **URLs.** https://github.com/ghostfolio/ghostfolio ; https://ghostfol.io/en/demo (live demo, V from README).

### 1.2 Portfolio Performance

- **What and license.** Desktop app (version 0.89.0 for Windows, macOS, Linux) plus mobile apps that calculate overall
  portfolio performance with true time-weighted return or IRR (V). "Open Source Software und lizenziert unter der Eclipse
  Public License - v1.0" (V, site footer; the README names the Eclipse Public License).
- **Pricing.** Not stated on the site, the README or the manual home.
- **Core screens.** Reports: Statement of Assets (Chart, Holdings) and Performance (Dashboard, Calculation, Chart,
  Securities, Payments, Trades) (V, manual). Taxonomies for classifying securities by asset class or region (V).
  "Rebalancing based on a user-defined asset allocation" (V). Configurable KPI dashboard (V, screenshot alt text).
- **Pattern to borrow: plan-then-track rebalancing.** The manual says you can "define and track your portfolio strategy
  with your planned asset allocation and ensure rebalancing" (V). The plan is a first-class object you measure against.
- **Education link.** The site links concepts (time-weighted return, IRR, asset allocation) to Wikipedia articles and
  has a "Basic concepts" manual section (V). This is concept-to-definition linking, not lesson-to-rule linking (I).
- **Paper versus live.** Not applicable (I).
- **Onboarding.** Manual "Getting started" runs from installation to "Define portfolio and rebalancing" and
  "Classifying assets" (V). Step count not stated.
- **Accessibility.** Not stated.
- **URLs.** https://www.portfolio-performance.info/en/ ; https://help.portfolio-performance.info/en/ ;
  https://github.com/portfolio-performance/portfolio

### 1.3 Maybe Finance (status check)

- **Status.** The GitHub repository "was archived by its owner on July 27, 2025" and is read-only; the README says
  "This repository is no longer actively maintained" (V). maybefinance.com redirects (301) to maybe.co, which did not
  resolve (DNS failure) today (V).
- **License.** "Maybe is distributed under an AGPLv3 license" (V). Stack: Ruby on Rails, PostgreSQL, Hotwire (V).
- **Pricing, screens, patterns, onboarding, accessibility.** Not stated in the README (no feature list).
- **Lesson for Invest.WitUS.** A well-funded open-source finance app can stop; the archive is still usable code (I).
  Do not depend on it.
- **URL.** https://github.com/maybe-finance/maybe

### 1.4 Firefly III (budgeting; rules engine)

- **What and license.** "A (self-hosted) manager for your personal finances" (V, GitHub README). "This work is licensed
  under the GNU Affero General Public License v3" (V). The project website and docs returned 403 (see Not reachable).
- **Pricing.** Free to self-host (I, from AGPL and the README); sponsored hosting options named: Hostinger, PikaPods (V).
  Prices not stated.
- **Core screens.** README features: rule-based transaction handling with custom rules, budgets, categories, tags,
  piggy banks (saving toward a goal), recurring transactions, income and expense reports (V).
- **Pattern to borrow: rule engine plus piggy banks.** Rules automate classification; piggy banks give a visible target
  for a pot of money (V for features; I for fit). In Invest.WitUS, a "contribution pot" per method fits DCA.
- **Education link.** Not stated.
- **Paper versus live.** Not applicable.
- **Onboarding.** Install by server, Docker, Kubernetes or third-party hosts (V). A demo site is listed at
  demo.firefly-iii.org (V, README), but it returned 403 to me.
- **Accessibility.** Not stated.
- **URL.** https://github.com/firefly-iii/firefly-iii

### 1.5 Actual Budget (budgeting; rules and journaling patterns)

- **What and license.** Local-first envelope budgeting; "you can only budget cash you have on hand" (V, site). "MIT
  license" (V, GitHub README).
- **Pricing.** Free and open source (V, README). Hosted options: PikaPods "about $2.00/month", Fly.io "about
  $1.50/month" (V, README). Donations via Open Collective (V).
- **Core screens.** Budget, accounts, reports (net worth, cash flow, custom report engine), rules, schedules, bank sync
  (GoCardless, SimpleFIN), imports, undo and redo, dark mode, an API (V).
- **Pattern to borrow: rules that learn from what you do.** Each rule has conditions and actions; rules run in `pre`,
  `default` and `post` stages; "Actual will automatically create rules for you" when you rename a payee or categorize a
  transaction (V, rules docs). For Invest.WitUS: when the user overrides the method (for example skips a buy), the app
  offers to record the override as an explicit, dated exception with a reason, instead of silently drifting (I).
- **Education link.** Not stated.
- **Paper versus live.** Not applicable.
- **Onboarding.** PikaPods setup "in about two minutes" (V); a "Try the demo" link (V).
- **Accessibility.** Not stated beyond dark mode with system default theme (V).
- **URLs.** https://actualbudget.org/ ; https://actualbudget.org/docs/budgeting/rules/ ; https://github.com/actualbudget/actual

### 1.6 OpenBB

- **What and license.** The Open Data Platform (ODP) connects public and licensed data to Python, Excel, a REST API
  and MCP servers; "Distributed under the Apache License, Version 2.0" (V, GitHub README). OpenBB Workspace is the
  enterprise UI (V). The site says OpenBB is "open-sourcing the entire OpenBB product suite under a permissive open source
  license", with the Workspace codebase to be stewarded by FINOS (Linux Foundation) and assets moving to a non-profit
  named OpenBQ (V). License for the Workspace release: not stated.
- **Pricing.** Community: "Free (individual license)"; Lite: "$2,400/year (team license)"; Pro: "Custom pricing";
  Snowflake: "$500/year/seat" (V, pricing page).
- **Core screens.** Dashboards built from any data source, an app marketplace, AI agents with the same data and tools
  (V). Use cases: research, portfolio analytics, risk monitoring, client reporting (V).
- **Pattern to borrow: Python data layer under a UI.** `pip install openbb`, then `openbb-api` serves a FastAPI backend
  the UI connects to (V). For a Python learner app, the same split (Python data service, thin UI) is teachable (I).
- **Education link, paper versus live, accessibility.** Not stated. "No Python required" for workflow users (V).
- **Onboarding.** Install the package, run the API, add the backend URL in Workspace under Apps (V): three steps.
- **URLs.** https://openbb.co/ ; https://openbb.co/pricing ; https://github.com/OpenBB-finance/OpenBB

### 1.7 QuantConnect and LEAN

- **What and license.** Cloud platform to "Research, backtest, optimize and deploy multi-asset strategies on one
  platform" (V). LEAN, its engine, is "Apache-2.0", Python and C# (V, GitHub).
- **Pricing.** A Free plan exists: "Unlimited Backtesting", 1 backtest node, 1 research node, 0 live trading nodes,
  community support; paper trading shown as not included ("-") on the free column (V). Paid plan prices: not stated on
  the pricing page text I read (a Monthly/Annual toggle with no amounts was rendered).
- **Core screens.** Algorithm Lab IDE, research notebooks, backtest results (equity curve, fees, holdings, PSR, return,
  exposure, capacity) with "a research guide that flags possible overfitting", optimization heatmaps, live and paper
  panels (V, homepage).
- **Pattern to borrow: a gated promotion pipeline.** Ideas go through validation, then backtest, then out-of-sample
  paper trading, and "paper results must fall within the backtest's statistical envelope before promotion to live" (V,
  homepage). For Invest.WitUS this is the paper-to-live gate.
- **Education link.** A "Learning Center" of "interactive, step-by-step guides", plus documentation, tutorials and
  learning articles; a course purchase dialog implies some paid courses (V; prices not stated).
- **Paper versus live.** On the Deploy Live page you set the Brokerage field to "Paper Trading" (V). Paper fills market
  orders immediately and completely, with no slippage under the default model, and "Restarts ... don't save the state of
  your algorithm" (V, docs). Deployment is 10 steps including region, node, cash, notifications (V).
- **Onboarding.** "Create Free Account" (V); steps to first backtest not stated.
- **Accessibility.** Not stated.
- **URLs.** https://www.quantconnect.com/ ; https://www.quantconnect.com/pricing ;
  https://www.quantconnect.com/docs/v2/cloud-platform/live-trading/brokerages/quantconnect-paper-trading ;
  https://github.com/QuantConnect/Lean

### 1.8 Backtrader

- **What and license.** Python backtesting and trading library; "GPL-3.0 license" (V, GitHub). 122 built-in
  indicators, TA-Lib support, analyzers, sizers, broker simulator; live brokers Interactive Brokers, Visual Chart, Oanda
  (V). The README states no maintenance status; the only dated item is from 2018-11-16 (V).
- **Pricing.** Not stated (open source).
- **Core screens.** None; it is a library. Plotting uses matplotlib (V).
- **Pattern to borrow: the ten-step quickstart.** Cerebro, cash, data feed, first strategy, logic, selling, commission,
  parameters and sizing, indicators, then plotting at step 10 (V). Each step adds one idea to a running program. This is
  the shape of the follow-along Python tutorial (I).
- **Education link.** Docs, articles and recipes sections (V).
- **Paper versus live.** Not stated.
- **Accessibility.** Not applicable.
- **URLs.** https://www.backtrader.com/ ; https://www.backtrader.com/docu/quickstart/quickstart/ ;
  https://github.com/mementum/backtrader

### 1.9 Composer (visual strategy builder)

- **What and license.** Proprietary. "Build trading algorithms with AI, backtest them, then execute ... No coding skills
  required" (V). The site names it "Composer (by SoFi)" (V). Brokerage by Composer Securities LLC, "a broker-dealer
  registered with the SEC and member of FINRA / SIPC"; accounts carried by Alpaca Securities LLC and Apex Clearing (V).
- **Pricing.** Starter "$0" (automates one strategy, up to 200 nodes, unlimited building and backtesting); Advanced
  "$10/mo." (up to five strategies, 350 nodes); Pro "$32/mo." billed "$384/yr" (up to 500 strategies, 10,000 nodes, API)
  (V, pricing page). "Zero commissions, zero management fees. Other fees may apply" (V).
- **Core screens.** Symphony editor with visual logic blocks, backtester with benchmark comparison and "modeled fees and
  slippage", Discover (prebuilt strategies), Community (publish, remix, share) (V).
- **Pattern to borrow: rules as readable blocks.** "If the current price of SPY is greater than the 200d moving
  average ... buy SPY, else, buy BND"; "Sort, filter, select"; weighting by custom weight, inverse volatility, market cap
  or equal (V). A taught method rendered as a block tree is a rule the user can read aloud (I).
- **Education link.** A "Resources" menu (V); no lesson-to-block linking described (not stated).
- **Paper versus live.** Not stated on the home or pricing pages; my guessed help URL for paper trading returned 404.
- **Onboarding.** Sign up, create and fund the account, automate the first strategy (V): three steps, funding before
  automation (I).
- **Accessibility.** Not stated.
- **URLs.** https://www.composer.trade/ ; https://www.composer.trade/pricing

### 1.10 M1 Finance ("Pies")

- **What and license.** Proprietary. M1 Finance LLC (brokerage) and M1 Advisory Services, LLC (SEC-registered adviser
  behind the AI "M1 Advisor") (V).
- **Pricing.** "M1 charges a platform fee of $3/month, which is waived for clients with more than $10,000 on the
  platform"; no commission, trading or management fees for self-directed brokerage; "M1 Advisor is a free advisory
  service for M1 clients" (V, pricing page).
- **Core screens.** Pies; Earn (cash), Invest, Borrow; M1 Advisor (V).
- **Pattern to borrow: the allocation Pie with underweight-first buying.** Each holding is a Slice with "the target
  percentage"; Pies can nest; up to 100 Slices per portfolio (V, "What is a Pie"). With Auto-Invest on (the default for
  new accounts), "The algorithm first seeks to invest in underweight slices", so new money rebalances without selling;
  a minimum cash threshold stays uninvested; "All buys and sells are executed during scheduled trading windows" (9:30 AM
  or 3:00 PM ET; accounts under $25k pick one) (V, "How is my money invested"). The trade window is a built-in brake on
  impulse trading (I).
- **Education link.** Knowledge Bank, calculators (Compounding Cost, Dividend, Retirement, Savings, Coast FIRE),
  Help Center (V). Not linked rule by rule (I).
- **Paper versus live.** No paper mode stated.
- **Onboarding.** Sign up, open an account, transfer funds, choose holdings into a Pie (V): about four steps (I).
- **Limits.** No day trading, extended hours or limit orders (V).
- **Accessibility.** Not stated.
- **URLs.** https://m1.com/ ; https://m1.com/pricing/ ;
  https://help.m1.com/hc/en-us/articles/4404384976019-What-is-a-Pie ;
  https://help.m1.com/en/articles/9332081-how-is-my-money-invested

### 1.11 Betterment (goals)

- **What and license.** Proprietary. "Betterment LLC, an SEC-registered investment adviser"; brokerage by Betterment
  Securities, FINRA/SIPC member (V).
- **Pricing.** Digital: "The base price for investing accounts is $5/month", switching to "0.25% annually" with recurring
  deposits of $200 or more a month or a balance of $24,000 or more; Premium "0.65%" with a $100,000 household minimum;
  lower rates above $1M (V, pricing page). "$10 to get started" (V).
- **Core screens.** Not described on the pages read (goal tracker is linked in the footer, V).
- **Pattern to borrow: on-track and off-track goals with three fixes.** A goal is off track when "the projected future
  value ... is not sufficient to reach the target amount assuming average market performance"; the remedies are raise
  monthly contributions, lengthen the term, or make a one-time deposit (V, help article last updated March 2, 2021).
  Status plus a short list of concrete fixes is the right shape for a deviation flag (I).
- **Education link.** Education hub, risk and return pages, live chat with a licensed specialist (V).
- **Paper versus live.** No paper mode stated.
- **Onboarding.** Answer questions, connect outside accounts, set goals, receive a portfolio per goal (V): four steps.
- **Accessibility.** Not stated.
- **URLs.** https://www.betterment.com/ ; https://www.betterment.com/pricing ; https://www.betterment.com/help/off-track-goal

### 1.12 Wealthfront (automation, rebalancing, tax-loss harvesting)

- **What and license.** Proprietary automated investing, cash, brokerage, home lending (V).
- **Pricing.** "Our advisory fee for The Wealthfront Portfolio is simple, just 0.25% annually" (V, pricing page; the
  page uses a dash where I wrote a comma). Brokerage: "No fees. $1 to get started" (V). The investing page says
  automated investing starts "For as little as $500" (V).
- **Core screens.** Navigation Cash, Invest, Borrow, Learn (V).
- **Pattern to borrow: rebalancing and harvesting as silent background work.** "We'll balance your funds as the market
  moves to keep you in line with your investment targets"; tax-loss harvesting "automatically captures daily losses";
  users can "change allocation weights and even add, remove and swap ETFs" and the firm keeps managing (V). The user's
  job is to not interfere; the app's job is to keep the plan (I).
- **Education link.** Methodology whitepapers, blog, FAQ (V).
- **Paper versus live.** No paper mode stated.
- **Onboarding.** Pick an account type, choose a goal, "answer a few questions", open the account (V): about three steps.
- **Accessibility.** Not stated.
- **URLs.** https://www.wealthfront.com/ ; https://www.wealthfront.com/pricing ; https://www.wealthfront.com/investing

### 1.13 Vanguard (plain long-term UX; education linking)

- **What.** Funds, ETFs, brokerage, advice services, 529 plans (V). Fees and minimums are on linked pages, not the home
  page (V).
- **Core screens and education.** Home page carries a "5 behaviors to boost your financial health" teaser (V, search
  result for the home page) and a 15-minute market summary (V). The education hub groups "Unlock investing basics"
  (Investing, Choosing investments, Trading online, Managing your portfolio), goal guides, "Tools & calculators" and an
  eight-topic selector (V). Article-level "open an account" or "buy" links were not shown (V).
- **Pattern to borrow: Vanguard's ACE behavioral design frame.** Vanguard's own article (Vanguard Canada, November 5,
  2025) names barriers ("inertia, present bias, and limited attention") and a framework: Attentiveness (benchmark the
  investor against ideal behaviors and quantify the gap), Commitment (measure success by whether investors are "on track
  to reach their goals", "not by clicks or daily engagement"), Empathy (simplify, default, break decisions into steps)
  (V). This is the most direct published statement of the product thesis Invest.WitUS needs (I).
- **Paper versus live.** No paper mode.
- **Accessibility.** Not stated on the pages read.
- **URLs.** https://investor.vanguard.com/ ; https://investor.vanguard.com/investor-resources-education ;
  https://www.vanguard.ca/en/insights/unlocking-better-outcomes-with-behavioral-design

### 1.14 Fidelity (plain long-term UX; Fidelity Learn)

- **What.** Brokerage; "No commission for online US stock and ETF trades"; options "$0.65 per contract"; bonds "$1 per
  bond" (V). Fidelity Trader+ on web, desktop and mobile (V). Paper trading: not mentioned.
- **Education.** Learning Center topics: "Financial essentials", "Life events", "Investing and trading", "Investment
  products", "Advanced trading"; series, webinars, coaching and classes (V). No learning paths or progress tracking
  shown; a "Favorites" item exists (V). Learn articles show no trade or screener call to action (V).
- **Pattern to borrow: separation of learning from trading.** The Learning Center does not push a trade from an article
  (V). For a method-adherence product, a lesson should link to the rule it explains, not to a buy button (I).
- **Accessibility.** "Skip to main content" link, a footer "Accessibility" link, new-window labels on external links,
  alt text on carousel images; some controls have generic labels (V).
- **URLs.** https://www.fidelity.com/learning-center/overview ; https://www.fidelity.com/trading/overview

### 1.15 Robinhood (what to avoid as much as borrow)

- **What.** Stocks, ETFs, crypto, options, futures and prediction markets ("Predict") in one account; "24/5
  Commission-Free Stock Trading"; Gold "$5/month" (V).
- **Engagement signals.** A crypto sweepstakes offering "$700K in crypto prizes", ending November 22, 2026 (V). Product
  list includes Social, Agents and Snacks (V). Confetti and push notifications: not mentioned on the page.
- **Education.** The Learn index exceeded my fetcher's size limit. The Learn article "What is Dollar-cost Averaging
  (DCA)?" opens "Dollar-cost averaging is a strategy of investing money in the market little by little and regularly",
  uses a worked example and a pie-slicing takeaway, and its only calls to action are "Sign up for Robinhood and get stock
  on us." and "Ready to start investing?" (V). It does not link to recurring investments (V).
- **Pattern to borrow: plain-language, example-first explainers.** The article style is good (V). **Avoid:** prizes and
  sweepstakes next to trading, and education that ends in a sign-up bonus instead of the method (I, informed by the
  FCA experiment in section 2).
- **Paper versus live.** No paper mode stated.
- **URLs.** https://robinhood.com/us/en/ ;
  https://robinhood.com/us/en/learn/articles/6OUpxPjHQc2J7g5EkmjjXY/what-is-dollar-cost-averaging-dca

### 1.16 Public.com

- **What.** Calls itself "the world's first agentic brokerage" (V). Brokerage by Public Investing, FINRA/SIPC; advisory
  by Public Advisors LLC (V).
- **Pricing.** Fee schedule (PDF): US-listed stocks and ETFs "$0" in regular and extended hours; stock and ETF options
  "$0"; index options "$0.35 per contract"; Public Reserve membership "$20 per month" or "$200 per year"; Generated
  Assets management fee 0.49%, Direct Index 0.19%; outgoing ACAT "$100" (V).
- **Core screens.** Agents (recurring self-directed transactions set up by conversation), Generated Assets (prompt to
  index, backtest against the S&P 500, invest), Income Hub, Direct Indexing, Earnings Hub, "Queue" (stage several orders
  then place them), Investment Plans (V).
- **Pattern to borrow: the Queue.** Staging orders before placing them (V) is a natural confirmation step for
  rule-generated orders (I).
- **Education link.** "Insights and Essentials" hub by topic (Stock Market, Investing, Options, Fixed Income, Retirement,
  Crypto, Alternative Investments) and investing, fixed income and options glossaries (V). Backtests are labeled
  "hypothetical" (V).
- **Paper versus live.** Not stated.
- **Onboarding.** "Fund your account in 5 minutes or less" (V).
- **URLs.** https://public.com/ ; https://public.com/learn ; https://public.com/disclosures/fee-schedule

### 1.17 Interactive Brokers

- Home page, paper trading page and IBKR Campus all returned 403. Nothing recorded; see Not reachable.

### 1.18 TradingView (charts, alerts)

- **What.** Charting and analysis platform for "100 million traders and investors" (V). Proprietary.
- **Pricing.** Basic "$0 forever" (3 price alerts, 2 indicators per chart); Essential "$12.95/ mo"; Plus "$29.95/ mo";
  Premium "$59.95/ mo"; Ultimate "$199.95/ mo", all billed annually (V). Monthly-billed prices: not shown.
- **Pattern to borrow: alerts as server-side rules with many channels.** Price, technical (indicator, strategy, drawing,
  pattern) and watchlist alerts; channels: app, toast, email, webhook ("sends a POST request to a URL you specify"),
  sound, plain text; standard alerts expire after two months, open-ended on Premium and Ultimate (V). A webhook alert is
  the model for "rule fired, send to the journal" (I).
- **Paper versus live.** Click **Trade**, choose Paper Trading from the list of brokers, Connect; "Paper Trading is
  available globally for all users"; simulated money, no deposits (V). Paper sits in the same list as real brokers, so
  the environment is chosen like a broker (I).
- **Education link.** Community ideas and scripts (V). Not tied to rules.
- **Accessibility.** Not stated.
- **URLs.** https://www.tradingview.com/ ; https://www.tradingview.com/pricing/ ;
  https://www.tradingview.com/support/solutions/43000520149-introduction-to-tradingview-alerts/ ;
  https://www.tradingview.com/support/solutions/43000516466-paper-trading-main-functionality/

### 1.19 Alpaca (the paper broker behind Invest.WitUS)

- **What.** Developer-first API broker; brokerage by Alpaca Securities LLC (dba "Alpaca Clearing"), FINRA/SIPC (V).
- **Pricing.** "Using Trading API can make stock and options trading commission-free" (V). Paper trading is "Free and
  available to all Alpaca users" (V). Data plan prices: not stated on the home page.
- **Paper versus live (the most important fact set here).** Paper accounts start with "$100k balance as a default
  setting"; reset means opening a new paper account from the account-number menu and generating new keys (V, docs).
  "Paper and live trading use separate API domains and separate credentials": `https://paper-api.alpaca.markets` versus
  `https://api.alpaca.markets`; "a paper key pair will be rejected with an HTTP 401 Unauthorized error if sent to the
  live brokerage endpoint" (V, Alpaca Learn, September 14, 2026). The dashboard's top navigation bar toggles the account
  environment to Paper Trading; keys come from the API Keys module; "The Secret Key is displayed only once" (V). Paper
  does not simulate market impact, slippage from latency, queue position, price improvement, regulatory fees or
  dividends; Paper Only accounts get IEX data only; about 10% of eligible orders get a random partial fill (V, docs).
- **Pattern to borrow: the host is the boundary.** Paper and live differ by host and key, not by a flag in the same
  session (V). Invest.WitUS should store paper and live credentials as separate records and print the host in the UI (I).
- **Education link.** "Learn" articles, including automated-trading risk guides (V).
- **Onboarding.** Docs name the steps (install SDK, create a free account, locate API keys, submit orders) without
  sequencing them (V): four steps (I).
- **Accessibility.** Not stated.
- **URLs.** https://alpaca.markets/ ; https://docs.alpaca.markets/docs/paper-trading ;
  https://alpaca.markets/learn/api-key-security-best-practices-for-alpaca-builders

### 1.20 Sharesight (performance reporting)

- **Pricing.** Free: 1 portfolio, 10 holdings; Starter "$7 USD per month billed annually" ($9.33 monthly), 30 holdings;
  Standard $18 ($24 monthly), unlimited; Premium $23.25 ($31 monthly), 10 portfolios (V).
- **Core screens.** Reports by tier: Performance, Sold Securities, All Trades (free); Diversity and Exposure (Starter);
  Future Income, Contribution Analysis, Drawdown Risk (Standard); Multi-Period (Premium) (V).
- **Pattern to borrow: Contribution Analysis.** Which holdings drove the result (V for the report name; I for use): in
  Invest.WitUS, "what part of your return came from following the rules versus from your exceptions".
- **Paper versus live.** Not applicable. **Education:** Help Centre, blog, webinars, calculators (V).
  **Onboarding:** free sign-up, no card (V). **Accessibility:** not stated. SOC 2 and GDPR stated (V).
- **URLs.** https://www.sharesight.com/ ; https://www.sharesight.com/pricing/

### 1.21 Snowball Analytics (performance and dividends)

- **Pricing.** Free "0forever" (1 portfolio, 10 holdings); Starter "79.99 / year"; Investor "149.99 / year"; Expert
  "249.99 / year"; monthly figures did not render; 14-day trial without a card (V).
- **Core screens.** Dividend calendar and income projection, dividend rating, performance with Sharpe ratio,
  diversification including fund look-through, benchmarking, "Category-based rebalancing" that "Supports monthly
  purchases and multiple strategies within one portfolio, with separate analytics per category" (V).
- **Pattern to borrow: strategies as categories inside one portfolio.** Separate analytics per strategy (V) fits a user
  who runs DCA and dividend growth side by side (I).
- **Disclosures.** "Not a registered investment advisor or broker/dealer"; content "for general information and
  education" (V). Brokerage connections via Yodlee; footer credits SnapTrade and EODHD (V).
- **Paper versus live, accessibility.** Not stated.
- **URLs.** https://snowball-analytics.com/ ; https://snowball-analytics.com/pricing

### 1.22 Investing journals and discipline tools

- **Edgewonk.** Annual "$197 per 12 months", monthly "$35 per month"; no free trial, a 14-day money-back guarantee (V).
  The "Efficiency" feature "turns discipline into something measurable" and shows "how often you follow your trading
  rules" as a percentage; the "Tiltmeter" "highlights streaks of strong and weak behavior" and overlays the equity curve;
  custom psychology stats ("Discipline & rule-following", "Impulsive or patient behavior"); a missed-trades log (V).
  **Borrow:** rule-following rate shown next to the return line (I). **Watch:** "streaks" can turn into a game (I).
  URLs: https://edgewonk.com/trading-psychology ; https://edgewonk.com/pricing
- **TradesViz.** Free "US$ 0" (3,000 executions a month); Pro US$19 a month or US$179 a year; Platinum US$29 a month or
  US$269 a year, which adds "trading rules" and trade and day plan analysis (V). Notes and tags on trades, days or
  accounts; "Trade/Day Planning" with custom checklists (V). **Borrow:** notes and tags at three levels (trade, day,
  account), mapped to order, rebalance day and method (I). URL: https://www.tradesviz.com/
- **Tradervue.** Journal with a notes system, setup tags in reports, exit analysis (V). Prices not stated on the home
  page; the pricing URL I tried returned 404. URL: https://www.tradervue.com/
- **TraderSync.** 403; see Not reachable.
- **Fit note (I).** All four are built for active traders; Invest.WitUS borrows their adherence measures but should
  journal decisions (a planned buy, a skipped buy, a rebalance) rather than trades per minute.

---

## 2. Investor UX and behavior: regulators and research

- **SEC request on digital engagement practices (2021).** Release Nos. 34-92766; IA-5833; File No. S7-10-21. The SEC
  requested comment on "digital engagement practices" or "DEPs", "including behavioral prompts, differential marketing,
  game-like features (commonly referred to as 'gamification'), and other design elements or features designed to engage
  with retail investors on digital platforms", plus the analytical tools behind them; comments were due October 1, 2021
  (V, release PDF page 1). The press release (2021-167, August 27, 2021) says the SEC wanted to understand conflicts
  from optimization practices and whether a DEP can amount to a recommendation or advice (V).
- **SEC predictive data analytics proposal (2023), withdrawn (2025).** Press release 2023-140 (July 26, 2023): firms
  would have had to evaluate and eliminate or neutralize conflicts from technologies that "optimize for, predict, guide,
  forecast, or direct investment-related behaviors or outcomes" (V). The SEC's rule page for File S7-12-23 shows the
  proposal at 88 FR 53960 (August 9, 2023) and a withdrawal (Release 33-11377 and related) issued June 12, 2025,
  effective June 17, 2025; the Commission "does not intend to issue final rules" and would issue "a new proposed rule"
  if it acts again (V). **Consequence (I):** no SEC rule today names DEPs, but the 2021 questions remain the clearest
  list of what a regulator asks about engagement design, and an app that nudges users toward trades should be able to
  answer them.
- **FCA (UK), 2022.** Warned that "frequent notifications", "in-app points and badges" and "celebratory messages for
  making trades" risk prompting consumers to act against their interests; "Some product design features could be
  contributing to problematic, even gambling-like, investor behaviour" (V, November 21, 2022).
- **FCA (UK), 2024 experiment.** Over 9,000 consumers on an experimental trading app: push notifications and points and
  prize draws raised trades by 11% and 12% and the share of trades in risky investments by 8% and 6%; low financial
  literacy users, women and ages 18 to 34 were affected more in specific conditions (V, June 20, 2024).
  **Consequence (I):** Invest.WitUS nudges must point toward the plan (fewer, scheduled actions), never toward more
  trading; no points, prizes, confetti or leaderboards on trading actions.
- **FINRA gamification page.** Returned 429 (rate limited); not used.

## 3. Design-system references for dense financial data

- **US Web Design System, table.** "Always use a header row"; "Right-align numerical data"; use a monospace font for
  currency, percentages and tallies; "Minimize the number of columns"; scrollable tables for dense numeric data;
  sticky headers for long tables; `scope` on headers; "Add title and attribution in a caption"; `aria-sort` for the
  default sort and an `aria-live="polite"` region to announce sort changes; "Scrollable tables need to be focusable"
  (`tabindex="0"`) (V).
- **US Web Design System, data visualizations.** "Your audience shouldn't be required to interact with a visualization
  to understand its message"; "Clearly state the author's intended message as text"; give the data as a table;
  use high-contrast colors or textured fill and dash patterns or marker shapes, not color alone (V).
- **GOV.UK Design System, table.** "When comparing columns of numbers, align the numbers to the right in table cells";
  captions help users "find, navigate and understand tables"; `scope` for row and column headers; split large tables
  where possible; `govuk-table--small-text-until-tablet` for small screens (Frontend 5.2 or later) (V).
- **WCAG.** WCAG 2.2 "was published on 5 October 2023, and an update was published on 12 December 2024"; it is the
  latest version and backwards compatible with 2.1 and 2.0 (V). Target: WCAG 2.2 AA (I, ecosystem choice to confirm).

---

## 4. Patterns table

| Pattern | Seen in | Why it fits method adherence |
|---|---|---|
| Rules as named checks with a status (pass, warn, fail) | Ghostfolio X-ray (V); Composer logic blocks (V) | Each taught rule becomes a visible check the user can read and the app can evaluate daily. |
| Target allocation with underweight-first buying | M1 Pies and Auto-Invest (V); Portfolio Performance rebalancing (V) | DCA and index methods stay on target with new money and no selling; drift becomes a number, not a feeling. |
| Scheduled trade windows | M1 (V) | A fixed time for orders is a brake on impulse trades; fits monthly DCA and 12-1 momentum rebalance days. |
| On track / off track with a short list of fixes | Betterment goals (V) | A deviation flag that always comes with two or three concrete, method-consistent remedies. |
| Rule-following rate next to the return line | Edgewonk Efficiency and Tiltmeter (V) | Makes discipline the headline metric, not daily profit and loss. |
| Rules that learn from overrides | Actual rules, auto-created from behavior (V) | Each skipped or extra action becomes a dated exception with a reason, so drift is explicit. |
| Notes and tags at trade, day and account level | TradesViz (V); Tradervue notes (V) | Journal entries attach to an order, a rebalance day or the method, so reviews read like a logbook. |
| Staged orders before placement | Public Queue (V) | Rule-generated orders wait for a one-tap confirm, with the rule and lesson shown beside each order. |
| Gated promotion from backtest to paper to live | QuantConnect pipeline (V) | Live is earned by paper results inside expected ranges and a written checklist, not by a toggle. |
| Paper and live separated by host and key | Alpaca (V); TradingView broker list (V) | The environment is a property of the credential, shown in the UI, so a paper key can never place a live order. |
| Server-side alerts with a webhook channel | TradingView alerts (V) | A fired rule can post to the journal and to email without the app being open. |
| Strategies as categories with separate analytics | Snowball category rebalancing (V) | A user running two taught methods sees each method's adherence and result separately. |
| Behavioral design measured by "on track", not clicks | Vanguard ACE (V) | Sets the product metric: adherence and goal progress, never engagement time. |
| Plain-language explainer with a worked example | Robinhood Learn DCA article (V) | The lesson link next to a rule should open a short, example-first explanation. |
| Background automation the user should not interfere with | Wealthfront rebalancing and harvesting (V) | The calmest way to keep a method is to let scheduled jobs do it and show the log. |
| Accessible dense tables (right-aligned monospace numbers, captions, scope, aria-sort) | USWDS and GOV.UK tables (V) | Holdings, drift and rule tables stay readable for screen readers and on phones. |
| Avoid: points, prizes, celebrations, leaderboards on trades | FCA 2022 and 2024 (V); Robinhood sweepstakes (V) | These raised trading frequency and risk in the FCA experiment; the opposite of adherence. |

---

## 5. Three design directions

### Direction A: "The Plan and the Logbook" (calm plan-and-journal app)

- **Core metaphor.** A written investment plan on the left page, a ship's logbook on the right. The app is a quiet
  keeper of a promise the user made to themselves.
- **Main screen, element by element.**
  1. Environment band across the top: "PAPER ACCOUNT, Alpaca paper-api, $100,000 simulated" in text, with a distinct
     neutral-hatched background, never color alone.
  2. The Plan card: method name ("Index investing with dollar-cost averaging"), the user's one-sentence reason, and the
     rules as a numbered list in plain words ("Buy $200 of INDEX on the 1st business day of each month"). Each rule ends
     with a "Why this rule" link to the Learn.WitUS lesson.
  3. Next action card: the one thing the method asks for next and its date ("Monday, November 2: buy $200 of INDEX"),
     with Confirm and Skip. Skip requires a reason and writes a logbook entry.
  4. On-plan status: one sentence plus a fix list, in Betterment's shape ("On plan. 9 of 9 scheduled buys made." or
     "Off plan: 2 skipped buys. Fixes: make them up on the next window; change the amount; pause the plan with a note").
  5. Allocation strip: target versus actual for each holding, as a short table with right-aligned monospace numbers and
     a caption, plus a text summary of drift.
  6. Logbook: the last five entries (automatic: orders placed, rule checks; manual: notes, tagged "feeling",
     "news", "exception").
  7. Below the fold: performance, deliberately small, with the rule-following rate printed beside it.
- **Adherence mechanism.** Scheduled actions plus explicit exceptions. Nothing happens off-plan without a written
  reason; the monthly review screen shows rule-following rate (Edgewonk), exceptions list and what they cost or saved.
  Nudges are calendar reminders before a scheduled window and one email after a missed action, nothing else.
- **Paper versus live.** Paper only in phase 1. The band and the logbook header name the host. Live is a separate
  "plan copy" later, with its own band.
- **Lessons.** One link per rule and one per method; the review screen links the lesson on "staying the course".
- **Borrows from.** Betterment (on track, three fixes), M1 (targets, trade windows, underweight-first buys), Actual
  (rules and exception capture), Edgewonk (rule-following rate), TradesViz (tags at three levels), Vanguard ACE (success
  measured by on-track, not clicks), USWDS tables.
- **Main risk.** Too quiet to come back to: a user who is not reminded drifts away entirely, and momentum or value
  methods (more rules, monthly screens) may feel cramped in a calm single-column layout. It also teaches less code
  surface for the Python tutorial than Direction B.

### Direction B: "Method Console" (dashboard-dense operator console)

- **Core metaphor.** A control room for one running system. The user is the operator who supervises a machine they
  built from the course, not a trader.
- **Main screen, element by element.**
  1. Status bar (sticky): environment (PAPER, host, account number masked), equity, cash, buying power, last data pull
     time, next scheduled job, job health (last run OK or failed with a link to the log).
  2. Rule checks table: rule | status (pass, warn, fail as text and icon) | last evaluated | evidence (the number that
     decided it) | lesson. Sortable, captioned, `aria-sort`, right-aligned numbers (Ghostfolio X-ray, USWDS).
  3. Signal table for the method's universe (for 12-1 momentum: ticker, 12-month return skipping the last month, rank,
     in or out), scrollable and focusable.
  4. Order queue: orders the rules generated for the next window, each with the rule that produced it, the expected
     cost, and Approve or Hold (Public Queue). Hold requires a reason.
  5. Drift table: target, actual, difference, action at next window.
  6. Envelope chart: paper results against the backtest's expected range, with a text sentence stating whether paper is
     inside it and the data as a table (QuantConnect pipeline, USWDS data visualization guidance).
  7. Deviation log: every override, failed job and data gap, filterable.
  8. Alert settings: which rule events notify by email or webhook (TradingView).
- **Adherence mechanism.** The machine runs the method on schedule; the operator approves or holds. Deviation flags fire
  on holds, manual orders outside the queue, and drift past the method's band. A weekly "operator report" lists flags
  and links the lesson for each.
- **Paper versus live.** Credentials are separate records per environment; the status bar prints the host. Live is
  unlocked only by a promotion checklist (paper run length, results inside the envelope, a written incident plan, a
  typed confirmation), after which live gets its own console and status bar.
- **Lessons.** A lesson column on every rule row and a "Why" link on every flag.
- **Borrows from.** Ghostfolio X-ray, QuantConnect (pipeline, overfitting guide, paper deploy), Public Queue, TradingView
  alerts and webhooks, Alpaca host separation, OpenBB (Python data service under the UI), USWDS and GOV.UK tables.
- **Main risk.** Density invites tinkering: a screen full of live numbers is the setting the FCA found raises trading.
  It also overwhelms beginners and carries the heaviest accessibility load (many dense tables on small screens).
  Mitigation would be a read-only default and a "simple view".

### Direction C: "The Lesson Lab" (course-first app; the lesson is home, the portfolio is the lab)

- **Core metaphor.** A textbook with a lab bench beside it. Each chapter of the method's course has an experiment that
  runs on the paper account.
- **Main screen, element by element.**
  1. Course spine on the left: the chosen method's chapters (for dividend growth: what a dividend is, payout ratio,
     growth streaks, the screen, the buy rule, the review rule), each marked read, in lab, or not started. No points or
     streak counters.
  2. Current lesson panel (center): a short plain-language explainer with a worked example (Robinhood Learn style, from
     the Learn.WitUS lesson), and at the bottom, "The rule this lesson gives you" written as a readable block
     ("If payout ratio is above 75%, do not buy"), like Composer's logic blocks.
  3. Lab panel (right): the rule applied to the paper account today: which holdings pass, which fail, what order it
     would place, and a "Run this rule on the paper account" button that sends the order to a staged queue.
  4. Lab notebook under the panel: a prompt ("What did you expect? What happened?") that saves to the journal tagged
     with the chapter.
  5. Method status strip at the top: rules activated so far, rules followed this month, environment label (PAPER, host).
- **Adherence mechanism.** Rules switch on one at a time as the learner reaches them, so the running method is always
  the part they have studied. Deviations open the chapter that taught the broken rule, with the learner's own lab note
  from when they first ran it.
- **Paper versus live.** Paper is the lab. Live appears only after the course's final chapter plus the promotion
  checklist from Direction B, as a separate "field" account with its own label.
- **Lessons.** The lesson is the home screen; phase 2 posts completion evidence to Learn.WitUS (seed note).
- **Borrows from.** QuantConnect Learning Center (interactive step-by-step guides), Backtrader quickstart (one idea per
  step), Composer blocks, Portfolio Performance (concept links), Fidelity (learning kept apart from trade buttons),
  Robinhood Learn (example-first writing, without its sign-up bonus), Snowball (separate analytics per strategy).
- **Main risk.** It depends on course content that does not yet exist for every method, and it is slow for an adult who
  already knows the method. Chapter progress can drift into gamification (progress bars and completion rewards are the
  same family as the FCA's points and badges), so completion must never be tied to trading actions.

---

## 6. Not reachable

| Source | URL | Result on October 27, 2026 |
|---|---|---|
| Firefly III website | https://www.firefly-iii.org/ | HTTP 403 |
| Firefly III docs | https://docs.firefly-iii.org/ | HTTP 403 |
| Firefly III demo | https://demo.firefly-iii.org/ | HTTP 403 |
| Interactive Brokers home | https://www.interactivebrokers.com/en/home.php | HTTP 403 |
| Interactive Brokers paper trading page | https://www.interactivebrokers.com/en/trading/free-trial.php | HTTP 403 |
| IBKR Campus | https://www.interactivebrokers.com/campus/ | HTTP 403 (ibkrcampus.com redirects here) |
| TraderSync | https://tradersync.com/ | HTTP 403 |
| FINRA, gamification investor page | https://www.finra.org/investors/insights/gamification | HTTP 429 (rate limited) |
| Maybe (company site) | https://maybe.co/ (redirect target of maybefinance.com) | DNS name did not resolve |
| Ghostfolio marketing pages | https://ghostfol.io/en/pricing , /en/features , /en/faq | Rendered client-side; only the page title was readable. Facts taken from the GitHub README, changelog and Ghostfolio's public info endpoint instead |
| Robinhood Learn index | https://robinhood.com/us/en/learn/ | Page exceeded the fetch size limit; one Learn article read instead |
| Composer paper-trading help (guessed URL) | https://help.composer.trade/en/articles/paper-trading | HTTP 404; Composer paper trading recorded as not stated |
| Tradervue pricing | https://www.tradervue.com/pricing | HTTP 404 |
| Public pricing page | https://public.com/pricing | HTTP 404; the fee schedule PDF was read instead |
| FCA research note (guessed URL) | fca.org.uk research-notes "gaming trading" page | HTTP 404; the FCA press releases were read instead |

No site was retried with a different user agent, proxy or cache copy.

---

## References

Actual Budget. (n.d.-a). *Actual: A local-first personal finance app* [Computer software]. GitHub. https://github.com/actualbudget/actual (retrieved October 27, 2026)

Actual Budget. (n.d.-b). *Actual Budget*. https://actualbudget.org/ (retrieved October 27, 2026)

Actual Budget. (n.d.-c). *Rules*. Actual Budget documentation. https://actualbudget.org/docs/budgeting/rules/ (retrieved October 27, 2026)

Alpaca. (n.d.-a). *Alpaca: Developer-first API for stock, options and crypto trading*. https://alpaca.markets/ (retrieved October 27, 2026)

Alpaca. (n.d.-b). *Paper trading*. Alpaca documentation. https://docs.alpaca.markets/docs/paper-trading (retrieved October 27, 2026)

Alpaca. (2026, September 14). *API key security best practices for Alpaca builders*. Alpaca Learn. https://alpaca.markets/learn/api-key-security-best-practices-for-alpaca-builders (retrieved October 27, 2026)

Backtrader. (n.d.-a). *Backtrader*. https://www.backtrader.com/ (retrieved October 27, 2026)

Backtrader. (n.d.-b). *Quickstart guide*. https://www.backtrader.com/docu/quickstart/quickstart/ (retrieved October 27, 2026)

Betterment. (n.d.-a). *Betterment*. https://www.betterment.com/ (retrieved October 27, 2026)

Betterment. (n.d.-b). *Pricing*. https://www.betterment.com/pricing (retrieved October 27, 2026)

Betterment. (2021, March 2). *Why does my goal say "off-track"?* Betterment Help. https://www.betterment.com/help/off-track-goal (retrieved October 27, 2026)

Composer. (n.d.-a). *Composer*. https://www.composer.trade/ (retrieved October 27, 2026)

Composer. (n.d.-b). *Pricing*. https://www.composer.trade/pricing (retrieved October 27, 2026)

Edgewonk. (n.d.-a). *Pricing*. https://edgewonk.com/pricing (retrieved October 27, 2026)

Edgewonk. (n.d.-b). *Trading psychology*. https://edgewonk.com/trading-psychology (retrieved October 27, 2026)

Fidelity Investments. (n.d.-a). *Learning Center*. https://www.fidelity.com/learning-center/overview (retrieved October 27, 2026)

Fidelity Investments. (n.d.-b). *Online trading*. https://www.fidelity.com/trading/overview (retrieved October 27, 2026)

Financial Conduct Authority. (2022, November 21). *FCA concerned about problem behaviours linked to trading app design* [Press release]. https://www.fca.org.uk/news/press-releases/fca-concerned-about-problem-behaviours-linked-trading-app-design (retrieved October 27, 2026)

Financial Conduct Authority. (2024, June 20). *FCA keeps trading apps under review over gaming concerns* [Press release]. https://www.fca.org.uk/news/press-releases/fca-keeps-trading-apps-under-review-over-gaming-concerns (retrieved October 27, 2026)

Firefly III. (n.d.). *Firefly III: A personal finances manager* [Computer software]. GitHub. https://github.com/firefly-iii/firefly-iii (retrieved October 27, 2026)

Ghostfolio. (n.d.-a). *Changelog*. GitHub. https://raw.githubusercontent.com/ghostfolio/ghostfolio/main/CHANGELOG.md (retrieved October 27, 2026)

Ghostfolio. (n.d.-b). *Ghostfolio* [Computer software]. GitHub. https://github.com/ghostfolio/ghostfolio (retrieved October 27, 2026)

Ghostfolio. (n.d.-c). *Info endpoint* [Data set]. https://ghostfol.io/api/v1/info (retrieved October 27, 2026)

GOV.UK Design System. (n.d.). *Table*. https://design-system.service.gov.uk/components/table/ (retrieved October 27, 2026)

M1 Finance. (n.d.-a). *How is my money invested?* M1 Help Center. https://help.m1.com/en/articles/9332081-how-is-my-money-invested (retrieved October 27, 2026)

M1 Finance. (n.d.-b). *M1*. https://m1.com/ (retrieved October 27, 2026)

M1 Finance. (n.d.-c). *Pricing*. https://m1.com/pricing/ (retrieved October 27, 2026)

M1 Finance. (n.d.-d). *What is a Pie?* M1 Help Center. https://help.m1.com/hc/en-us/articles/4404384976019-What-is-a-Pie (retrieved October 27, 2026)

Maybe Finance. (n.d.). *Maybe: The personal finance app for everyone* [Computer software; archived July 27, 2025]. GitHub. https://github.com/maybe-finance/maybe (retrieved October 27, 2026)

OpenBB. (n.d.-a). *OpenBB*. https://openbb.co/ (retrieved October 27, 2026)

OpenBB. (n.d.-b). *Open Data Platform by OpenBB* [Computer software]. GitHub. https://github.com/OpenBB-finance/OpenBB (retrieved October 27, 2026)

OpenBB. (n.d.-c). *Pricing*. https://openbb.co/pricing (retrieved October 27, 2026)

Portfolio Performance. (n.d.-a). *Manual*. https://help.portfolio-performance.info/en/ (retrieved October 27, 2026)

Portfolio Performance. (n.d.-b). *Portfolio Performance*. https://www.portfolio-performance.info/en/ (retrieved October 27, 2026)

Portfolio Performance. (n.d.-c). *portfolio* [Computer software]. GitHub. https://github.com/portfolio-performance/portfolio (retrieved October 27, 2026)

Public.com. (n.d.-a). *Fee schedule*. https://public.com/disclosures/fee-schedule (retrieved October 27, 2026)

Public.com. (n.d.-b). *Investing insights and essentials*. https://public.com/learn (retrieved October 27, 2026)

Public.com. (n.d.-c). *Public*. https://public.com/ (retrieved October 27, 2026)

QuantConnect. (n.d.-a). *LEAN algorithmic trading engine* [Computer software]. GitHub. https://github.com/QuantConnect/Lean (retrieved October 27, 2026)

QuantConnect. (n.d.-b). *Pricing*. https://www.quantconnect.com/pricing (retrieved October 27, 2026)

QuantConnect. (n.d.-c). *QuantConnect*. https://www.quantconnect.com/ (retrieved October 27, 2026)

QuantConnect. (n.d.-d). *QuantConnect paper trading*. QuantConnect documentation. https://www.quantconnect.com/docs/v2/cloud-platform/live-trading/brokerages/quantconnect-paper-trading (retrieved October 27, 2026)

Robinhood. (n.d.-a). *Robinhood*. https://robinhood.com/us/en/ (retrieved October 27, 2026)

Robinhood. (n.d.-b). *What is dollar-cost averaging (DCA)?* Robinhood Learn. https://robinhood.com/us/en/learn/articles/6OUpxPjHQc2J7g5EkmjjXY/what-is-dollar-cost-averaging-dca (retrieved October 27, 2026)

Sharesight. (n.d.-a). *Pricing*. https://www.sharesight.com/pricing/ (retrieved October 27, 2026)

Sharesight. (n.d.-b). *Sharesight*. https://www.sharesight.com/ (retrieved October 27, 2026)

Snowball Analytics. (n.d.-a). *Pricing*. https://snowball-analytics.com/pricing (retrieved October 27, 2026)

Snowball Analytics. (n.d.-b). *Snowball Analytics*. https://snowball-analytics.com/ (retrieved October 27, 2026)

TradesViz. (n.d.). *TradesViz*. https://www.tradesviz.com/ (retrieved October 27, 2026)

Tradervue. (n.d.). *Tradervue*. https://www.tradervue.com/ (retrieved October 27, 2026)

TradingView. (n.d.-a). *Introduction to TradingView alerts*. TradingView Support. https://www.tradingview.com/support/solutions/43000520149-introduction-to-tradingview-alerts/ (retrieved October 27, 2026)

TradingView. (n.d.-b). *Paper Trading: Main functionality*. TradingView Support. https://www.tradingview.com/support/solutions/43000516466-paper-trading-main-functionality/ (retrieved October 27, 2026)

TradingView. (n.d.-c). *Pricing*. https://www.tradingview.com/pricing/ (retrieved October 27, 2026)

TradingView. (n.d.-d). *TradingView*. https://www.tradingview.com/ (retrieved October 27, 2026)

U.S. General Services Administration. (n.d.-a). *Data visualizations*. U.S. Web Design System. https://designsystem.digital.gov/components/data-visualizations/ (retrieved October 27, 2026)

U.S. General Services Administration. (n.d.-b). *Table*. U.S. Web Design System. https://designsystem.digital.gov/components/table/ (retrieved October 27, 2026)

U.S. Securities and Exchange Commission. (2021a, August 27). *Request for information and comments on broker-dealer and investment adviser digital engagement practices, related tools and methods, and regulatory considerations and potential approaches; information and comments on investment adviser use of technology to develop and provide investment advice* (Release Nos. 34-92766; IA-5833; File No. S7-10-21). https://www.sec.gov/rules/other/2021/34-92766.pdf (retrieved October 27, 2026)

U.S. Securities and Exchange Commission. (2021b, August 27). *SEC requests information and comment on broker-dealer and investment adviser digital engagement practices* [Press release 2021-167]. https://www.sec.gov/news/press-release/2021-167 (retrieved October 27, 2026)

U.S. Securities and Exchange Commission. (2023, July 26). *SEC proposes new requirements to address risks to investors from conflicts of interest associated with the use of predictive data analytics by broker-dealers and investment advisers* [Press release 2023-140]. https://www.sec.gov/news/press-release/2023-140 (retrieved October 27, 2026)

U.S. Securities and Exchange Commission. (n.d.). *Conflicts of interest associated with the use of predictive data analytics by broker-dealers and investment advisers* (File No. S7-12-23). https://www.sec.gov/rules/2023/07/s7-12-23 (retrieved October 27, 2026)

Vanguard. (n.d.-a). *Investor resources and education*. https://investor.vanguard.com/investor-resources-education (retrieved October 27, 2026)

Vanguard. (n.d.-b). *Vanguard: Investing, retirement and advice*. https://investor.vanguard.com/ (retrieved October 27, 2026)

Vanguard Canada. (2025, November 5). *Unlocking better outcomes with behavioral design*. https://www.vanguard.ca/en/insights/unlocking-better-outcomes-with-behavioral-design (retrieved October 27, 2026)

W3C Web Accessibility Initiative. (n.d.). *WCAG 2 overview*. https://www.w3.org/WAI/standards-guidelines/wcag/ (retrieved October 27, 2026)

Wealthfront. (n.d.-a). *Automated investing*. https://www.wealthfront.com/investing (retrieved October 27, 2026)

Wealthfront. (n.d.-b). *Pricing*. https://www.wealthfront.com/pricing (retrieved October 27, 2026)

Wealthfront. (n.d.-c). *Wealthfront*. https://www.wealthfront.com/ (retrieved October 27, 2026)
