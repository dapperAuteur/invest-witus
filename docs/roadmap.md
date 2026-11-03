---
app: invest
name: Invest.WitUS
stage: alpha
url: https://invest.witus.online
updated: 2026-11-02
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
- Journal with hold and skip reasons, monthly close and CSV export
- A default view saved per person; a plan edited or deleted before anything happens under it
- Report a problem or ask a question, sent to WitUS Inbox; a Help bubble on every page
- Owner drafts posts to WitUS Outbox
- Tutorial chapters 00 to 14a, one git tag per chapter (14a merged 2026-10-31)
- Migrations run automatically after each merge

## In progress
- Waitlist signups on witus.online
- Connecting reports and drafts to WitUS Inbox and Outbox (secrets being matched)

## Next
- Chapter 15: signed events to CentenarianOS and lesson links checked against Learn.WitUS
- Python tutorial course built from the chapters

## Backlog
- Compare page for methods running side by side in their own accounts (backlog 20; key slots are live)
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
