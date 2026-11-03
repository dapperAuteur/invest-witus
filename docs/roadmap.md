---
app: invest
name: Invest.WitUS
stage: alpha
url: https://invest.witus.online
updated: 2026-11-03
---

## Live now
- Landing page, waitlist, FAQ, privacy and terms
- Sign in with WitUS
- Owner back office: accounts, holdings and statement comparisons
- Nightly closing-price pull and on-demand price fetches
- Watch list with symbol pages, price history and charts with ranges and compare
- Method engine with three views: the plan and logbook, the console, the lesson lab
- Index investing with a fixed monthly amount, and 12-1 momentum
- Paper trading through Alpaca, with orders placed once and synced to the journal
- One Alpaca paper account per method: any number of key slots on the server, each account linked through its own (decisions 159, 160)
- Key slot names: the single-underscore form read too, conflicting forms refused, every unusable `ALPACA_PAPER_` name listed with its reason (decision 166)
- Journal with hold and skip reasons, monthly close and CSV export
- A default view saved per person; a plan edited or deleted before anything happens under it
- Report a problem or ask a question, sent to WitUS Inbox; a Help bubble on every page
- Owner drafts posts to WitUS Outbox
- Tutorial chapters 00 to 14a, one git tag per chapter (14a merged 2026-10-31)
- Migrations run automatically after each merge

## In progress
- Compare methods (chapter 15, decisions 167 to 171): two to four accounts on one chart with an index fund yardstick, money put in, value, gain, both returns, worst drop and how often each plan was followed; a Practice or Real badge beside every account name (decision 172; task 35, with task 34)
- The plan's amount read as the month's total with the missing parts named, a Settings page, striped tables, and the Help bubble keeping its draft (decisions 161 to 165, task 33)
- Index rules version 2: one buy of each fund a month and the month's total, so a plan split across several funds reads followed; months already closed keep version 1 (decisions 173 and 174, backlog 23, task 37, which also lands tasks 35 and 34)
- Waitlist signups on witus.online
- Connecting reports and drafts to WitUS Inbox and Outbox (secrets being matched)

## Next
- Chapter 16: signed events to CentenarianOS and lesson links checked against Learn.WitUS
- Python tutorial course built from the chapters

## Backlog
- Practice simulator for classes, after a vetting analysis
- More momentum views: relative strength, quintiles, heatmap, path smoothness
- Quarterly momentum with a quality screen as its own method
- Placing paper sells for momentum rebalances
- Learn.WitUS lessons inside the app
- Foreign markets research
- Owner usage dashboard (chapter 17)
- A small sibling API service in a second Python framework

## Blocked on
- Inbox and Outbox slug and secret sync (task 26)
- Paper account starting amount check (task 02)
- Preview-database cleanup secrets (task 05)
- Web Analytics switch (task 06)
- Feature clip recordings (task 11)
- Legal review before anyone but the owner uses it
