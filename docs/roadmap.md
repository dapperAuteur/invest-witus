---
app: invest
name: Invest.WitUS
stage: beta
url: https://invest.witus.online
updated: 2026-10-29
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
- Journal with hold and skip reasons, monthly close and CSV export
- Report a problem or ask a question, sent to WitUS Inbox; a Help bubble on every page
- Owner drafts posts to WitUS Outbox
- Tutorial chapters 00 to 14, one git tag per chapter
- Migrations run automatically after each merge

## In progress
- Connecting reports and drafts to WitUS Inbox and Outbox (secrets being matched)

## Next
- Chapter 14a: momentum rank changes month to month and a rolling 12-1 line
- Chapter 15: signed events to CentenarianOS and lesson links checked against Learn.WitUS
- Python tutorial course built from the chapters

## Backlog
- Practice simulator for classes, after a vetting analysis
- More momentum views: relative strength, quintiles, heatmap, path smoothness
- Quarterly momentum with a quality screen as its own method
- Placing paper sells for momentum rebalances
- Learn.WitUS lessons inside the app
- Foreign markets research
- Owner usage dashboard (chapter 16)
- A small sibling API service in a second Python framework

## Blocked on
- Inbox and Outbox slug and secret sync (task 26)
- Paper account starting amount check (task 02)
- Preview-database cleanup secrets (task 05)
- Web Analytics switch (task 06)
- Feature clip recordings (task 11)
- Legal review before anyone but the owner uses it
